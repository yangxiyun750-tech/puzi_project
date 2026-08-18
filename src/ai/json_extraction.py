"""Deterministic JSON extraction from LLM text outputs.

No LLM is used to repair LLM output. All recovery is rule-based, bounded, and
logged via ``JSONExtractionResult`` so callers can preserve provenance.

Supported recovery paths:
- Strip Markdown `` ```json ... ``` `` fences.
- Extract a single JSON object surrounded by natural-language prose.
- Reject multiple JSON objects (ambiguous).
- Reject truncated JSON whose closing boundary cannot be determined.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class JSONExtractionResult:
    """Outcome of deterministic JSON extraction from a raw text candidate."""

    text: str
    """Normalized text (valid JSON when ``success`` is True)."""

    success: bool
    """True when ``text`` is parseable as JSON."""

    action: str
    """What extraction step succeeded or failed last.

    Success actions:
    - ``none``: the input was already valid JSON.
    - ``strip_fence``: Markdown code fence was removed.
    - ``extract_embedded``: a single JSON object was isolated from prose.

    Failure actions:
    - ``empty``: input was empty or whitespace.
    - ``multiple_objects``: more than one JSON object found.
    - ``truncated``: JSON structure is incomplete (unbalanced braces).
    - ``completely_invalid``: no JSON object could be identified.
    """

    failure_subtype: str = ""
    """Machine-readable subtype when ``success`` is False."""


class JSONExtractor:
    """Deterministic, bounded extractor for JSON embedded in LLM outputs."""

    ACTION_NONE = "none"
    ACTION_STRIP_FENCE = "strip_fence"
    ACTION_EXTRACT_EMBEDDED = "extract_embedded"
    ACTION_EMPTY = "empty_content"
    ACTION_MULTIPLE_OBJECTS = "multiple_objects"
    ACTION_TRUNCATED = "truncated"
    ACTION_COMPLETELY_INVALID = "completely_invalid"

    _FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)

    @classmethod
    def normalize(cls, text: str | None) -> JSONExtractionResult:
        """Return the best deterministic JSON candidate from ``text``.

        The contract is conservative: a JSON object is returned only when its
        boundaries can be determined without guessing missing content.
        """
        if text is None:
            text = ""
        text = str(text).strip()

        if not text:
            return JSONExtractionResult(
                "",
                success=False,
                action=cls.ACTION_EMPTY,
                failure_subtype=cls.ACTION_EMPTY,
            )

        # 1. Strip Markdown fences if present.
        unfenced = cls._strip_fence(text)
        action = cls.ACTION_STRIP_FENCE if unfenced != text else cls.ACTION_NONE
        candidate = unfenced.strip()

        # 2. Try to parse the cleaned text as-is.
        if cls._is_valid_json(candidate):
            return JSONExtractionResult(candidate, success=True, action=action)

        # 3. Try to isolate a single JSON object embedded in prose.
        embedded = cls._extract_single_object(candidate)
        if embedded is not None:
            return JSONExtractionResult(
                embedded,
                success=True,
                action=cls.ACTION_EXTRACT_EMBEDDED,
            )

        # 4. Classify why extraction failed.
        if cls._has_multiple_objects(candidate):
            return JSONExtractionResult(
                candidate,
                success=False,
                action=cls.ACTION_MULTIPLE_OBJECTS,
                failure_subtype=cls.ACTION_MULTIPLE_OBJECTS,
            )

        if cls._is_truncated(candidate):
            return JSONExtractionResult(
                candidate,
                success=False,
                action=cls.ACTION_TRUNCATED,
                failure_subtype=cls.ACTION_TRUNCATED,
            )

        return JSONExtractionResult(
            candidate,
            success=False,
            action=cls.ACTION_COMPLETELY_INVALID,
            failure_subtype=cls.ACTION_COMPLETELY_INVALID,
        )

    @classmethod
    def _strip_fence(cls, text: str) -> str:
        """Remove leading/trailing Markdown JSON fences."""
        return cls._FENCE_RE.sub("", text)

    @classmethod
    def _is_valid_json(cls, text: str) -> bool:
        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False

    @classmethod
    def _extract_single_object(cls, text: str) -> str | None:
        """Return the only balanced ``{...}`` object in ``text``, or None.

        Returns None if there are zero objects or more than one object, or if
        the isolated text is not valid JSON.
        """
        boundaries = cls._find_object_boundaries(text)
        if len(boundaries) != 1:
            return None
        start, end = boundaries[0]
        candidate = text[start : end + 1]
        if cls._is_valid_json(candidate):
            return candidate
        return None

    @classmethod
    def _find_object_boundaries(cls, text: str) -> list[tuple[int, int]]:
        """Return a list of ``(start, end)`` indices for top-level JSON objects.

        Brace matching is string-aware so braces inside JSON strings are ignored.
        """
        boundaries: list[tuple[int, int]] = []
        i = 0
        while i < len(text):
            if text[i] == "{":
                end = cls._find_matching_brace(text, i)
                if end is not None:
                    boundaries.append((i, end))
                    i = end + 1
                    continue
            i += 1
        return boundaries

    @classmethod
    def _find_matching_brace(cls, text: str, start: int) -> int | None:
        """Return the index of the ``}`` that closes the ``{`` at ``start``.

        Returns None if no matching close is found. Handles strings and
        backslash escapes.
        """
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape_next:
                    escape_next = False
                    continue
                if ch == "\\":
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        return None

    @classmethod
    def _has_multiple_objects(cls, text: str) -> bool:
        """Return True if the text contains more than one balanced JSON object."""
        return len(cls._find_object_boundaries(text)) > 1

    @classmethod
    def _is_truncated(cls, text: str) -> bool:
        """Return True if an unclosed JSON object/array boundary is detected.

        This is a conservative check: a string is truncated only if it contains
        an opening ``{`` that never closes. Multiple balanced objects with prose
        between them are classified as ``multiple_objects``, not truncated.
        """
        i = 0
        while i < len(text):
            if text[i] == "{":
                end = cls._find_matching_brace(text, i)
                if end is None:
                    return True
                i = end + 1
                continue
            i += 1
        return False
