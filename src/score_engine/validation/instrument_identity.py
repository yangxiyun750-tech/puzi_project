"""Instrument Identity Resolution for Score Reconstruction V2.

Resolves the true canonical instrument for each Part by combining
multiple evidence sources. Audiveris instrument-name is treated as
a candidate only, never as the single source of truth.

Evidence sources (in order of reliability):
1. PDF title / instrumentation text (highest)
2. Staff-left instrument name / abbreviation
3. Staff count and grouping (grand staff detection)
4. Clef (F clef line 4, G clef line 2, C clef, PERC)
5. Pitch range (bass vs tenor vs alto vs soprano)
6. Key signature / transposition behavior
7. Note overlap with other parts (detects duplicates)
8. Audiveris instrument-name (lowest)
9. Optional: AI visual inspection of source PDF
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from score_engine.score_ir.score_ir import Part, Pitch, Score


@dataclass
class InstrumentIdentity:
    """Resolved canonical instrument identity for a Part."""
    part_id: str
    canonical_instrument: str = ""
    source_label: str = ""  # What Audiveris or the source called it
    confidence: str = "low"  # high | medium | low
    evidence: list[str] = field(default_factory=list)
    needs_verification: bool = False
    verification_reason: str = ""
    staff_count: int = 1
    clef: str = ""
    pitch_range_low: str = ""
    pitch_range_high: str = ""
    is_vocal: bool = False  # True only for genuine human-voice instruments

    def to_dict(self) -> dict[str, Any]:
        return {
            "part_id": self.part_id,
            "canonical_instrument": self.canonical_instrument,
            "source_label": self.source_label,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "needs_verification": self.needs_verification,
            "verification_reason": self.verification_reason,
            "staff_count": self.staff_count,
            "clef": self.clef,
            "pitch_range_low": self.pitch_range_low,
            "pitch_range_high": self.pitch_range_high,
            "is_vocal": self.is_vocal,
        }


class InstrumentIdentityResolver:
    """Resolve canonical instrument identities for all parts in a Score."""

    # Known instrument families by pitch range (approximate MIDI boundaries)
    RANGE_FAMILIES = {
        "Contrabass / Double Bass": (24, 48),
        "Bass Trombone / Tuba / Bassoon": (28, 58),
        "Cello / Trombone / Bassoon": (36, 72),
        "Viola / French Horn": (48, 84),
        "Violin / Flute": (55, 96),
        "Soprano / Piccolo": (60, 96),
    }

    # Vocal-specific instruments
    VOCAL_INSTRUMENTS = {
        "voice", "soprano", "alto", "tenor", "bass", "choir",
        "solo voice", "vocal", "ooh", "aah", "choir aahs",
        "voice oohs", "synth voice",
    }

    def __init__(self, pdf_text: str = "") -> None:
        self.pdf_text = pdf_text.lower()
        self.identities: list[InstrumentIdentity] = []

    def resolve(self, score: Score) -> list[InstrumentIdentity]:
        """Resolve instruments for all parts in the score."""
        self.identities = []
        for part in score.parts:
            identity = self._resolve_part(part, score)
            self.identities.append(identity)
        return self.identities

    def _resolve_part(self, part: Part, score: Score) -> InstrumentIdentity:
        """Resolve a single part's instrument identity."""
        identity = InstrumentIdentity(part_id=part.id)
        identity.source_label = part.name

        # Gather evidence
        evidence: list[str] = []

        # 1. PDF text evidence (highest priority)
        pdf_evidence = self._check_pdf_text(part)
        if pdf_evidence:
            evidence.extend(pdf_evidence)

        # 2. Staff count and structure
        staff_info = self._analyze_staff_structure(part)
        identity.staff_count = staff_info["count"]
        if staff_info["evidence"]:
            evidence.append(staff_info["evidence"])

        # 3. Clef analysis
        clef_info = self._analyze_clef(part)
        identity.clef = clef_info["clef"]
        if clef_info["evidence"]:
            evidence.append(clef_info["evidence"])

        # 4. Pitch range
        range_info = self._analyze_pitch_range(part)
        identity.pitch_range_low = range_info["low"]
        identity.pitch_range_high = range_info["high"]
        if range_info["evidence"]:
            evidence.append(range_info["evidence"])

        # 5. Overlap with other parts
        overlap_info = self._analyze_overlap(part, score)
        if overlap_info["evidence"]:
            evidence.append(overlap_info["evidence"])

        # 6. Audiveris label analysis
        audiveris_info = self._analyze_audiveris_label(part)
        if audiveris_info["evidence"]:
            evidence.append(audiveris_info["evidence"])

        identity.evidence = evidence

        # Determine canonical instrument and confidence
        self._determine_canonical(identity, part)

        # Vocal detection
        identity.is_vocal = self._is_genuine_vocal(part, identity)

        return identity

    def _check_pdf_text(self, part: Part) -> list[str]:
        """Check PDF text for instrumentation clues."""
        evidence: list[str] = []
        if not self.pdf_text:
            return evidence

        part_name_lower = part.name.lower()

        # Direct instrument mentions in PDF
        # Order: longer phrases first to avoid partial matches
        instrument_keywords = [
            ("bass trombone", "Bass Trombone"),
            ("double bass", "Double Bass"),
            ("bassoon", "Bassoon"),
            ("trombone", "Trombone"),
            ("trumpet", "Trumpet"),
            ("clarinet", "Clarinet"),
            ("piccolo", "Piccolo"),
            ("flute", "Flute"),
            ("oboe", "Oboe"),
            ("horn", "Horn"),
            ("violin", "Violin"),
            ("viola", "Viola"),
            ("cello", "Violoncello"),
            ("piano", "Piano"),
            ("harp", "Harp"),
            ("timpani", "Timpani"),
            ("soprano", "Soprano"),
            ("alto", "Alto"),
            ("tenor", "Tenor"),
            ("bass", "Bass"),
            ("voice", "Voice"),
        ]

        for keyword, canonical in instrument_keywords:
            if keyword in self.pdf_text:
                # Check if this matches the part context
                if keyword in part_name_lower or self._part_matches_keyword(part, keyword):
                    evidence.append(f"PDF title/text mentions '{canonical}'")
                    break

        return evidence

    def _part_matches_keyword(self, part: Part, keyword: str) -> bool:
        """Heuristic: does this part likely match the keyword based on position."""
        # For solo + accompaniment, first part is often the solo
        if "solo" in self.pdf_text and part.id in ("P1", "part1", "Part1"):
            # First part in a solo + accompaniment is likely the soloist
            solo_instruments = ["trombone", "violin", "cello", "flute", "oboe", "clarinet",
                               "bassoon", "horn", "trumpet", "saxophone"]
            for si in solo_instruments:
                if si in self.pdf_text:
                    # keyword may be "bass trombone", si is "trombone"
                    return keyword == si or si in keyword
        return False

    def _analyze_staff_structure(self, part: Part) -> dict[str, Any]:
        """Analyze staff count and structure."""
        result = {"count": 1, "evidence": ""}

        if not part.measures:
            return result

        # Count unique staff numbers in notes
        staff_numbers: set[int] = set()
        for measure in part.measures:
            for voice in measure.voices:
                for event in voice.events:
                    if hasattr(event, "staff"):
                        staff_numbers.add(event.staff)

        result["count"] = len(staff_numbers) if staff_numbers else 1

        if result["count"] >= 2:
            result["evidence"] = f"Grand staff: {result['count']} staves detected"
        elif result["count"] == 1:
            result["evidence"] = "Single staff"

        return result

    def _analyze_clef(self, part: Part) -> dict[str, Any]:
        """Analyze clef information."""
        result = {"clef": "", "evidence": ""}

        if not part.measures:
            return result

        # Collect clefs from first few measures
        clefs: set[str] = set()
        for measure in part.measures[:3]:
            for staff_num, clef in measure.clefs.items():
                clefs.add(f"{clef.sign}{clef.line}")

        if clefs:
            result["clef"] = "/".join(sorted(clefs))
            if "F4" in result["clef"]:
                result["evidence"] = "Bass clef (F on line 4)"
            elif "G2" in result["clef"]:
                result["evidence"] = "Treble clef (G on line 2)"
            elif "C3" in result["clef"]:
                result["evidence"] = "Alto clef (C on line 3)"
            elif "PERC" in result["clef"]:
                result["evidence"] = "Percussion clef"

        return result

    def _analyze_pitch_range(self, part: Part) -> dict[str, Any]:
        """Analyze pitch range of the part."""
        result = {"low": "", "high": "", "evidence": ""}

        all_pitches: list[Pitch] = []
        for measure in part.measures:
            for voice in measure.voices:
                for event in voice.events:
                    if hasattr(event, "pitch") and event.pitch is not None:
                        all_pitches.append(event.pitch)
                    elif hasattr(event, "notes"):
                        for note in event.notes:
                            if note.pitch is not None:
                                all_pitches.append(note.pitch)

        if not all_pitches:
            result["evidence"] = "No pitched notes found"
            return result

        min_midi = min(p.midi for p in all_pitches)
        max_midi = max(p.midi for p in all_pitches)
        min_p = next(p for p in all_pitches if p.midi == min_midi)
        max_p = next(p for p in all_pitches if p.midi == max_midi)

        alter_min = f"{min_p.alter:+d}" if min_p.alter else ""
        alter_max = f"{max_p.alter:+d}" if max_p.alter else ""
        result["low"] = f"{min_p.step}{alter_min}{min_p.octave}"
        result["high"] = f"{max_p.step}{alter_max}{max_p.octave}"

        # Determine range family
        range_family = self._classify_range(min_midi, max_midi)
        result["evidence"] = f"Pitch range: {result['low']}–{result['high']} (midi {min_midi}–{max_midi}) — {range_family}"

        return result

    def _classify_range(self, min_midi: int, max_midi: int) -> str:
        """Classify pitch range into instrument family."""
        center = (min_midi + max_midi) // 2
        for family, (lo, hi) in self.RANGE_FAMILIES.items():
            if lo <= center <= hi:
                return family
        return "Wide/unspecified range"

    def _analyze_overlap(self, part: Part, score: Score) -> dict[str, Any]:
        """Analyze note overlap with other parts (measure-by-measure)."""
        result = {"evidence": ""}

        # Build measure-indexed pitch sets for this part
        this_by_measure: dict[str, set[str]] = {}
        for measure in part.measures:
            mn = measure.number
            pitches: set[str] = set()
            for voice in measure.voices:
                for event in voice.events:
                    if hasattr(event, "pitch") and event.pitch is not None:
                        pitches.add(f"{event.pitch.step}{event.pitch.octave}")
                    elif hasattr(event, "notes"):
                        for note in event.notes:
                            if note.pitch is not None:
                                pitches.add(f"{note.pitch.step}{note.pitch.octave}")
            if pitches:
                this_by_measure[mn] = pitches

        if not this_by_measure:
            return result

        # Compare measure-by-measure with each other part
        max_overlap = 0.0
        max_overlap_part = ""
        for other in score.parts:
            if other.id == part.id:
                continue

            # Build other part's measure-indexed pitch sets
            other_by_measure: dict[str, set[str]] = {}
            for measure in other.measures:
                mn = measure.number
                pitches: set[str] = set()
                for voice in measure.voices:
                    for event in voice.events:
                        if hasattr(event, "pitch") and event.pitch is not None:
                            pitches.add(f"{event.pitch.step}{event.pitch.octave}")
                        elif hasattr(event, "notes"):
                            for note in event.notes:
                                if note.pitch is not None:
                                    pitches.add(f"{note.pitch.step}{note.pitch.octave}")
                if pitches:
                    other_by_measure[mn] = pitches

            # Measure-by-measure overlap
            matched_measures = 0
            comparable_measures = 0
            total_overlap_ratio = 0.0

            for mn, this_pitches in this_by_measure.items():
                if mn in other_by_measure:
                    comparable_measures += 1
                    other_pitches = other_by_measure[mn]
                    if other_pitches:
                        overlap = len(this_pitches & other_pitches) / len(this_pitches)
                        total_overlap_ratio += overlap
                        if overlap > 0.8:
                            matched_measures += 1

            if comparable_measures > 0:
                avg_overlap = total_overlap_ratio / comparable_measures
                if avg_overlap > max_overlap:
                    max_overlap = avg_overlap
                    max_overlap_part = other.id

        overlap_pct = max_overlap * 100
        if overlap_pct > 80:
            result["evidence"] = f"HIGH per-measure overlap ({overlap_pct:.0f}%) with {max_overlap_part} — possible duplicate"
        elif overlap_pct > 40:
            result["evidence"] = f"Moderate per-measure overlap ({overlap_pct:.0f}%) with {max_overlap_part}"
        else:
            result["evidence"] = f"Low per-measure overlap ({overlap_pct:.0f}%) with {max_overlap_part} — independent part"

        return result

    def _analyze_audiveris_label(self, part: Part) -> dict[str, Any]:
        """Analyze the Audiveris-provided label."""
        result = {"evidence": ""}
        label_lower = part.name.lower()

        if "voice" in label_lower and "voice oohs" in label_lower:
            result["evidence"] = f"Audiveris label: '{part.name}' — likely generic/synthetic instrument"
        elif "piano" in label_lower:
            result["evidence"] = f"Audiveris label: '{part.name}' — consistent with keyboard instrument"
        else:
            result["evidence"] = f"Audiveris label: '{part.name}'"

        return result

    def _determine_canonical(self, identity: InstrumentIdentity, part: Part) -> None:
        """Determine canonical instrument and confidence from evidence."""
        label_lower = part.name.lower()

        # High confidence cases
        if identity.staff_count >= 2 and "piano" in label_lower:
            identity.canonical_instrument = "Piano"
            identity.confidence = "high"
            return

        # Check PDF text evidence first
        for ev in identity.evidence:
            if "PDF title/text mentions" in ev:
                # Extract instrument name from evidence
                match = re.search(r"'(.+?)'", ev)
                if match:
                    identity.canonical_instrument = match.group(1)
                    identity.confidence = "high"
                    return

        # Check clef + range combinations for common instruments
        if "Bass clef" in identity.clef:
            if "bass-register" in str(identity.evidence).lower() or any("midi 2" in e or "midi 3" in e for e in identity.evidence):
                if "low overlap" in str(identity.evidence).lower():
                    identity.canonical_instrument = "Bass Trombone / Tuba / Bassoon / Cello"
                    identity.confidence = "medium"
                    identity.needs_verification = True
                    identity.verification_reason = "Bass clef + low range + independent part — needs visual confirmation"
                    return

        # If Audiveris says "Voice" but no lyrics and independent part
        if "voice" in label_lower and not identity.is_vocal:
            identity.canonical_instrument = "Unknown (not vocal)"
            identity.confidence = "low"
            identity.needs_verification = True
            identity.verification_reason = "Audiveris labeled 'Voice' but no vocal evidence detected"
            return

        # Fallback: trust the label with medium confidence
        identity.canonical_instrument = part.name
        identity.confidence = "low"
        identity.needs_verification = True
        identity.verification_reason = "No strong evidence to override Audiveris label"

    def _is_genuine_vocal(self, part: Part, identity: InstrumentIdentity) -> bool:
        """Determine if this is a genuine human-voice instrument."""
        label_lower = part.name.lower()

        # Check 1: Is the label a known vocal instrument?
        is_labeled_vocal = any(vi in label_lower for vi in self.VOCAL_INSTRUMENTS)

        # Check 2: Are there actual lyrics in the music?
        has_lyrics = False
        for measure in part.measures:
            for voice in measure.voices:
                for event in voice.events:
                    if hasattr(event, "lyrics") and event.lyrics:
                        has_lyrics = True
                        break
                if has_lyrics:
                    break
            if has_lyrics:
                break

        # Check 3: Is there a staff text indicating a vocalist?
        # (Not implemented in V1 — would require scanning directions)

        # Genuine vocal requires BOTH label AND lyrics
        # OR: label is explicitly a vocal type (Soprano, Alto, etc.)
        explicit_vocal_types = {"soprano", "alto", "tenor", "bass", "solo voice", "choir"}
        is_explicit_vocal = any(vt in label_lower for vt in explicit_vocal_types)

        if is_explicit_vocal:
            return True

        if is_labeled_vocal and has_lyrics:
            return True

        # "Voice Oohs" without lyrics is NOT a genuine vocal part
        return False

    def save_json(self, path: str | Path) -> None:
        data = {
            "identities": [i.to_dict() for i in self.identities],
            "vocal_parts_detected": sum(1 for i in self.identities if i.is_vocal),
            "parts_needing_verification": sum(1 for i in self.identities if i.needs_verification),
        }
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def print_report(self) -> None:
        print("=" * 60)
        print("INSTRUMENT IDENTITY RESOLUTION REPORT")
        print("=" * 60)
        for identity in self.identities:
            print(f"\n{identity.part_id}:")
            print(f"  canonical_instrument = {identity.canonical_instrument}")
            print(f"  source_label = {identity.source_label}")
            print(f"  confidence = {identity.confidence}")
            print(f"  staff_count = {identity.staff_count}")
            print(f"  clef = {identity.clef}")
            print(f"  pitch_range = {identity.pitch_range_low} – {identity.pitch_range_high}")
            print(f"  is_vocal = {identity.is_vocal}")
            print(f"  needs_verification = {identity.needs_verification}")
            if identity.verification_reason:
                print(f"  verification_reason = {identity.verification_reason}")
            print("  evidence:")
            for ev in identity.evidence:
                print(f"    - {ev}")
        print()
        print(f"Vocal parts detected: {sum(1 for i in self.identities if i.is_vocal)}")
        print(f"Parts needing verification: {sum(1 for i in self.identities if i.needs_verification)}")
