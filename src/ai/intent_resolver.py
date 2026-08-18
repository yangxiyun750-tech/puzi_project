"""Intent resolver — turns a raw ``TransposeIntent`` into a validated ``TransposeRequest``.

This module is entirely deterministic. It resolves:
- operation / written-vs-sounding basis
- named interval and direction
- target part(s)
- measure range

Then it validates the resulting ``TransposeRequest`` against the actual Score
and returns a ``TransposeIntentResult``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from score_engine.score_ir.score_ir import Part, Score
from score_engine.transposition.interval import Interval
from score_engine.transposition.request import TranspositionOperation, TransposeRequest

from .intent_schema import IntentContext, TransposeIntent, TransposeIntentResult
from .intent_validator import IntentValidator


# Chinese / English instrument aliases → canonical English instrument name.
_INSTRUMENT_ALIASES: dict[str, str] = {
    "小号": "Trumpet",
    "降b小号": "Trumpet",
    "短号": "Cornet",
    "长号": "Trombone",
    "低音长号": "Bass Trombone",
    "圆号": "Horn",
    "法国号": "Horn",
    "单簧管": "Clarinet",
    "黑管": "Clarinet",
    "双簧管": "Oboe",
    "大管": "Bassoon",
    "巴松": "Bassoon",
    "长笛": "Flute",
    "短笛": "Piccolo",
    "萨克斯": "Saxophone",
    "萨克斯风": "Saxophone",
    "中音萨克斯": "Alto Saxophone",
    "小提琴": "Violin",
    "中提琴": "Viola",
    "大提琴": "Cello",
    "低音提琴": "Double Bass",
    "贝斯": "Bass",
    "钢琴": "Piano",
    "竖琴": "Harp",
    "定音鼓": "Timpani",
}

# Natural-language interval aliases → (quality, number).
_INTERVAL_ALIASES: dict[tuple[str, ...], tuple[str, int]] = {
    ("半音", "小二度", "minor second", "half step", "halfstep", "semitone"): ("m", 2),
    ("全音", "大二度", "major second", "whole step", "wholestep", "tone"): ("M", 2),
    ("小三度", "minor third"): ("m", 3),
    ("大三度", "major third"): ("M", 3),
    ("纯四度", "perfect fourth", "fourth"): ("P", 4),
    ("纯五度", "perfect fifth", "fifth"): ("P", 5),
    ("小六度", "minor sixth"): ("m", 6),
    ("大六度", "major sixth"): ("m", 6),  # common speech "sixth" defaults to major
    ("小七度", "minor seventh"): ("m", 7),
    ("大七度", "major seventh"): ("M", 7),
    ("八度", "一个八度", "octave", "perfect octave"): ("P", 8),
}

# Direction keywords → direction value.
_DIRECTION_MAP: dict[tuple[str, ...], int] = {
    ("升", "上移", "提高", "up", "raise", "升高", "向上"): 1,
    ("降", "下移", "降低", "down", "lower", "向下"): -1,
}


class IntervalResolver:
    """Map natural-language interval descriptions to ``Interval``."""

    @classmethod
    def resolve(cls, description: str | None, direction_text: str | None) -> Interval | None:
        if not description:
            return None
        normalized = description.strip().lower()
        for aliases, (quality, number) in _INTERVAL_ALIASES.items():
            if any(alias.lower() in normalized for alias in aliases):
                direction = cls._resolve_direction(direction_text)
                return Interval(number, quality, direction)
        return None

    @classmethod
    def _resolve_direction(cls, direction_text: str | None) -> int:
        if not direction_text:
            return 1
        normalized = direction_text.strip().lower()
        for aliases, value in _DIRECTION_MAP.items():
            if any(alias in normalized for alias in aliases):
                return value
        return 1


class PartResolver:
    """Resolve a part description to concrete ``Part`` ids.

    Matching is deterministic and layered:

    1. ``is_all_parts`` / empty description short-circuits.
    2. Exact part-id match (query is exactly ``P1``, ``p2``, etc.).
    3. Extract ``P\\d+`` part ids from anywhere in the description; if exactly
       one valid id is mentioned, resolve to that part. This consumes model
       disambiguation like "长号 (Trombone, P3)" without hardcoding sentences.
    4. Instrument alias matching (exact and substring) against normalized
       candidate strings built from part names and instruments.
    5. If exactly one part matches, return it; multiple matches remain
       ambiguous and return ``needs_clarification``.
    """

    # Part ids are internal stable identifiers like P1, P2, P3.
    _PART_ID_RE = re.compile(r"\b(P\d+)\b", re.IGNORECASE)

    def __init__(self, score: Score) -> None:
        self.score = score
        self._part_candidates = self._build_candidates()
        self._part_id_to_part = {p.id.upper(): p for p in score.parts}

    def _build_candidates(self) -> dict[str, set[str]]:
        """Build a set of searchable strings for each part id."""
        candidates: dict[str, set[str]] = {}
        for part in self.score.parts:
            strings: set[str] = set()
            strings.add(part.id.lower())
            if part.name:
                strings.add(part.name.lower())
                strings.add(_normalize(part.name))
            if part.instrument and part.instrument.name:
                strings.add(part.instrument.name.lower())

            # Canonical names from Chinese aliases.
            for alias, canonical in _INSTRUMENT_ALIASES.items():
                if any(alias in s for s in strings):
                    strings.add(canonical.lower())
                    strings.add(_normalize(canonical))

            candidates[part.id] = strings
        return candidates

    @staticmethod
    def _normalize_query(text: str) -> str:
        """Lowercase, trim, and collapse whitespace/punctuation to single spaces.

        The original ``part_description`` is preserved in messages; this
        normalized form is used only for matching.
        """
        text = text.strip().lower()
        # Collapse runs of whitespace and common punctuation to a single space.
        text = re.sub(r"[\s\(\)\[\]\{\},/]+", " ", text)
        return text.strip()

    def _build_search_terms(self, normalized: str) -> set[str]:
        """Return all search terms derived from the normalized description."""
        terms: set[str] = set()
        if not normalized:
            return terms

        terms.add(normalized)

        # Exact alias lookup on the full normalized text.
        if normalized in _INSTRUMENT_ALIASES:
            canonical = _INSTRUMENT_ALIASES[normalized]
            terms.add(canonical.lower())
            terms.add(_normalize(canonical))

        # Substring alias lookup: any alias contained in the description.
        for alias, canonical in _INSTRUMENT_ALIASES.items():
            if alias in normalized:
                terms.add(canonical.lower())
                terms.add(_normalize(canonical))

        return {t for t in terms if t}

    def _extract_part_ids(self, normalized: str) -> set[str]:
        """Return the set of valid ``P\\d+`` ids mentioned in ``normalized``."""
        mentioned: set[str] = set()
        for match in self._PART_ID_RE.finditer(normalized):
            pid = match.group(1).upper()
            if pid in self._part_id_to_part:
                mentioned.add(pid)
        return mentioned

    def resolve(
        self,
        part_description: str | None,
        is_all_parts: bool,
    ) -> tuple[list[str] | None, str]:
        """Return (part_ids, reason).

        ``part_ids`` is None when clarification is needed; ``reason`` explains
        whether the result is resolved, ambiguous, or not found.
        """
        if is_all_parts:
            return [p.id for p in self.score.parts], "all_parts"

        if not part_description or not part_description.strip():
            return None, "missing_part_description"

        normalized = self._normalize_query(part_description)
        lower_ids = {p.id.lower(): p.id for p in self.score.parts}

        # Layer 1: exact part-id match.
        if normalized in lower_ids:
            return [lower_ids[normalized]], "exact_id"

        # Layer 2: detect part ids embedded in the description.
        mentioned_ids = self._extract_part_ids(normalized)
        if len(mentioned_ids) == 1:
            return [mentioned_ids.pop()], "id_in_description"

        # Layer 3: instrument alias and candidate-string matching.
        search_terms = self._build_search_terms(normalized)
        matched: list[str] = []
        for part_id, strings in self._part_candidates.items():
            if self._matches(search_terms, strings):
                matched.append(part_id)

        if len(matched) == 1:
            return matched, "name_match"
        if len(matched) > 1:
            return None, f"ambiguous_match:{','.join(matched)}"
        return None, "not_found"

    @staticmethod
    def _matches(terms: set[str], candidates: set[str]) -> bool:
        """Return True if any term deterministically matches a candidate string."""
        if not terms:
            return False
        for term in terms:
            for candidate in candidates:
                if not term or not candidate:
                    continue
                # Existing behaviour: query term is a substring of candidate.
                if term in candidate:
                    return True
        return False


class MeasureResolver:
    """Resolve measure descriptions to 1-based measure indices."""

    @classmethod
    def resolve(
        cls,
        start_desc: str | None,
        end_desc: str | None,
        part_ids: list[str],
        score: Score,
    ) -> tuple[int | None, int | None, str]:
        """Return (start_index, end_index, reason) where indices are 1-based.

        None values indicate the range could not be resolved.
        """
        start_token = cls._extract_token(start_desc)
        end_token = cls._extract_token(end_desc)

        if start_token is None and end_token is None:
            # Default to full range of the first resolved part.
            first_part = score.get_part(part_ids[0])
            if first_part is None:
                return None, None, "missing_part"
            return 1, len(first_part.measures), "full_range"

        if start_token is not None and end_token is None:
            end_token = start_token

        if start_token is None and end_token is not None:
            start_token = end_token

        assert start_token is not None and end_token is not None

        # Numeric ordering check only when both tokens are pure numbers.
        start_number = cls._token_to_int(start_token)
        end_number = cls._token_to_int(end_token)
        if start_number is not None and end_number is not None and start_number > end_number:
            return None, None, f"start_greater_than_end:{start_number}>{end_number}"

        # Resolve display tokens to 1-based indices in every target part.
        start_index: int | None = None
        end_index: int | None = None
        for pid in part_ids:
            part = score.get_part(pid)
            if part is None:
                return None, None, f"part_not_found:{pid}"
            part_start = cls._find_measure_index(part, start_token)
            part_end = cls._find_measure_index(part, end_token)
            if part_start is None:
                return None, None, f"measure_not_found:{start_token}"
            if part_end is None:
                return None, None, f"measure_not_found:{end_token}"
            # For V1 we require the same 1-based index in all target parts.
            if start_index is None:
                start_index = part_start
                end_index = part_end
            elif start_index != part_start or end_index != part_end:
                return None, None, f"measure_index_mismatch:{pid}"

        return start_index, end_index, "resolved"

    @classmethod
    def _extract_token(cls, desc: str | None) -> str | None:
        """Return a normalized display token for measure lookup."""
        if not desc:
            return None
        text = str(desc).strip()
        # Strip common prefixes like M/measure/第.
        text = re.sub(r"^(m|measure|第)\s*", "", text, flags=re.IGNORECASE)
        if not text:
            return None
        return text

    @classmethod
    def _token_to_int(cls, token: str) -> int | None:
        """Return integer value if the token is purely numeric, else None."""
        if token.isdigit():
            return int(token)
        return None

    @classmethod
    def _find_measure_index(cls, part: Part, token: str) -> int | None:
        """Find 1-based index of the measure whose display number equals token."""
        normalized = token.strip().lower()
        for idx, measure in enumerate(part.measures, start=1):
            if str(measure.number).strip().lower() == normalized:
                return idx
        return None


def _is_target_key_request(intent: TransposeIntent) -> bool:
    """Return True if the user asks for transposition to a specific target key.

    V1 only supports interval transposition and instrument-pitch conversion.
    Target-key requests (e.g., '移到降E大调', 'transpose to Eb major') are
    classified as unsupported without hardcoding specific sentences.
    """
    text = " ".join(
        filter(
            None,
            [
                intent.source_text,
                intent.interval_description,
                intent.clarification_question,
            ],
        )
    ).lower()

    # Chinese: verbs that introduce a target key followed by 大调/小调.
    # Examples: 移到降E大调, 移成D大调, 转成F小调, 变成降B大调.
    if re.search(r"(移|转|改|变).{0,3}[到成在为].{0,8}(大调|小调)", text):
        return True

    # English: transpose/move/change to a key with major/minor.
    # Examples: transpose to Eb major, move the whole score to D major.
    # The pattern requires "to/into" before the key and "major/minor" after it
    # so that "transpose up a major second" is not flagged.
    if re.search(
        r"\b(transpose|move|change|shift).{0,20}\b(to|into)\b.{0,20}\b(major|minor)\b",
        text,
    ):
        return True

    return False


class BasisResolver:
    """Choose the final operation from intent operation / basis fields."""

    @classmethod
    def resolve(cls, intent: TransposeIntent) -> TranspositionOperation:
        # Explicit concert/sounding conversion takes highest priority.
        if intent.operation == "written_to_sounding" or intent.basis in ("sounding", "concert"):
            return TranspositionOperation.WRITTEN_TO_SOUNDING

        # Explicit written conversion.
        if intent.operation == "sounding_to_written":
            return TranspositionOperation.SOUNDING_TO_WRITTEN

        # "written" basis only implies conversion when the user did NOT also
        # give a concrete interval (e.g. "把记谱音高升大二度" should transpose
        # written pitch by an interval, not convert sounding-to-written).
        if intent.basis == "written" and not intent.interval_description:
            return TranspositionOperation.SOUNDING_TO_WRITTEN

        # Default: relative interval transposition of written pitch.
        return TranspositionOperation.INTERVAL


def build_intent_context(score: Score) -> IntentContext:
    """Build a minimal context for the AI provider from a Score."""
    parts = []
    for part in score.parts:
        parts.append({
            "id": part.id,
            "name": part.name,
            "instrument": part.instrument.name or "",
        })

    measure_numbers: list[int] = []
    for part in score.parts:
        for measure in part.measures:
            try:
                measure_numbers.append(int(measure.number))
            except (ValueError, TypeError):
                pass

    max_measure = max(measure_numbers) if measure_numbers else 1
    if not max_measure:
        max_measure = max((len(p.measures) for p in score.parts), default=1)

    return IntentContext(
        available_parts=parts,
        min_measure=1,
        max_measure=max_measure,
        supported_intervals=[
            "minor second / 小二度 / 半音",
            "major second / 大二度 / 全音",
            "minor third / 小三度",
            "major third / 大三度",
            "perfect fourth / 纯四度",
            "perfect fifth / 纯五度",
            "minor sixth / 小六度",
            "major sixth / 大六度",
            "minor seventh / 小七度",
            "major seventh / 大七度",
            "octave / 八度 / 一个八度",
        ],
    )


@dataclass
class TransposeIntentResolver:
    """High-level resolver that orchestrates part/measure/interval resolution."""

    validator: IntentValidator | None = None

    def __post_init__(self) -> None:
        if self.validator is None:
            self.validator = IntentValidator()

    def _intent_has_complete_transpose_spec(self, intent: TransposeIntent) -> bool:
        """Return True if the intent is concrete enough to validate target existence.

        A complete spec has an allowed operation, an explicit part description,
        and (for interval transposition) an interval description. All-parts
        requests are excluded because the score always contains parts.
        """
        if intent.operation not in self.validator.ALLOWED_OPERATIONS:
            return False
        if intent.is_all_parts:
            return False
        if not intent.part_description or not intent.part_description.strip():
            return False
        if intent.operation == "transpose" and not intent.interval_description:
            return False
        return True

    def resolve(self, intent: TransposeIntent, score: Score) -> TransposeIntentResult:
        source_text = intent.source_text
        # Validate raw intent structure.
        validation = self.validator.validate_intent(intent)
        if not validation.valid:
            return TransposeIntentResult(
                status="invalid",
                request=None,
                confidence=0.0,
                ambiguities=[validation.reason],
                clarification_question=f"Invalid intent: {validation.reason}",
                source_text=source_text,
            )

        # V1 boundary: transposition to a specific target key is not supported.
        # This catches cases where the model returns needs_clarification or
        # ready for a target-key request instead of unsupported.
        if _is_target_key_request(intent):
            return TransposeIntentResult(
                status="unsupported",
                request=None,
                confidence=intent.confidence,
                clarification_question="Target-key transposition is not supported in V1.",
                source_text=source_text,
            )

        if intent.status == "needs_clarification":
            # Deterministic override: if the model asks for clarification but the
            # user already supplied a complete, concrete request targeting a part
            # that does not exist in the score, classify as invalid rather than
            # asking for clarification again. This rule is generic and applies
            # to any non-existent instrument or part id, not just specific cases.
            if self._intent_has_complete_transpose_spec(intent):
                part_resolver = PartResolver(score)
                part_ids, part_reason = part_resolver.resolve(
                    intent.part_description, False
                )
                if part_ids is None and part_reason == "not_found":
                    return TransposeIntentResult(
                        status="invalid",
                        request=None,
                        confidence=intent.confidence,
                        ambiguities=[part_reason],
                        clarification_question=(
                            f"Could not find a part matching "
                            f"'{intent.part_description}'."
                        ),
                        source_text=source_text,
                    )
            return TransposeIntentResult(
                status="needs_clarification",
                request=None,
                confidence=intent.confidence,
                clarification_question=intent.clarification_question or "Please clarify your request.",
                source_text=source_text,
            )

        if intent.status == "unsupported":
            return TransposeIntentResult(
                status="unsupported",
                request=None,
                confidence=intent.confidence,
                clarification_question=intent.clarification_question or "This transpose request is not supported.",
                source_text=source_text,
            )

        if intent.status == "invalid":
            return TransposeIntentResult(
                status="invalid",
                request=None,
                confidence=0.0,
                clarification_question=intent.clarification_question or "Could not understand the request.",
                source_text=source_text,
            )

        if intent.status == "provider_error":
            return TransposeIntentResult(
                status="provider_error",
                request=None,
                confidence=0.0,
                clarification_question=intent.clarification_question or "AI provider error.",
                source_text=source_text,
                error_reason=intent.error_reason,
                diagnostics=intent.diagnostics,
            )

        # Resolve operation.
        operation = BasisResolver.resolve(intent)

        # Resolve interval for INTERVAL operation.
        interval = None
        if operation == TranspositionOperation.INTERVAL:
            interval = IntervalResolver.resolve(
                intent.interval_description, intent.direction
            )
            if interval is None:
                return TransposeIntentResult(
                    status="needs_clarification",
                    request=None,
                    confidence=intent.confidence,
                    clarification_question=(
                        f"Could not resolve interval '{intent.interval_description}'. "
                        "Please specify, e.g. 大二度, 小三度, 纯五度, 八度."
                    ),
                    source_text=source_text,
                )

        # Resolve parts.
        part_resolver = PartResolver(score)
        part_ids, part_reason = part_resolver.resolve(
            intent.part_description, intent.is_all_parts
        )
        if part_ids is None:
            if part_reason.startswith("ambiguous_match"):
                ids = part_reason.split(":", 1)[1].split(",")
                names = [f"{p} {score.get_part(p).name}" for p in ids]
                return TransposeIntentResult(
                    status="needs_clarification",
                    request=None,
                    confidence=intent.confidence,
                    ambiguities=names,
                    clarification_question=(
                        f"'{intent.part_description}' matches multiple parts: {', '.join(names)}. "
                        "Please specify which one."
                    ),
                    source_text=source_text,
                )
            if part_reason == "missing_part_description":
                return TransposeIntentResult(
                    status="needs_clarification",
                    request=None,
                    confidence=intent.confidence,
                    clarification_question="Which part should be transposed?",
                    source_text=source_text,
                )
            return TransposeIntentResult(
                status="invalid",
                request=None,
                confidence=intent.confidence,
                ambiguities=[part_reason],
                clarification_question=(
                    f"Could not find a part matching '{intent.part_description}'."
                ),
                source_text=source_text,
            )

        # Resolve measures.
        start_idx, end_idx, measure_reason = MeasureResolver.resolve(
            intent.measure_start_description,
            intent.measure_end_description,
            part_ids,
            score,
        )
        if start_idx is None or end_idx is None:
            return TransposeIntentResult(
                status="invalid",
                request=None,
                confidence=intent.confidence,
                ambiguities=[measure_reason],
                clarification_question=f"Invalid measure range: {measure_reason}",
                source_text=source_text,
            )

        # Build candidate request.
        request = TransposeRequest(
            operation=operation,
            interval=interval,
            part_ids=part_ids,
            measure_start=start_idx,
            measure_end=end_idx,
            preserve_original=True,
        )

        # Final deterministic validation against the score.
        final_validation = self.validator.validate_request(request, score)
        if not final_validation.valid:
            return TransposeIntentResult(
                status="invalid",
                request=None,
                confidence=intent.confidence,
                ambiguities=[final_validation.reason],
                clarification_question=f"Validation failed: {final_validation.reason}",
                source_text=source_text,
            )

        return TransposeIntentResult(
            status="ready",
            request=request,
            confidence=intent.confidence,
            clarification_question="",
            source_text=source_text,
        )


def _normalize(text: str) -> str:
    """Remove common punctuation/diacritics for matching."""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()
