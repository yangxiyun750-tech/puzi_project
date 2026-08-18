"""Pitch spelling strategy for transposition.

V1 strategy:
- The diatonic target step is immutable: it is determined solely by the named
  interval number and the source step.
- The accidental is then chosen to satisfy the chromatic distance dictated by
  the interval quality.
- If that accidental falls outside the supported range [-2, +2] (double-flat to
  double-sharp), the engine reports ``SpellingError`` rather than respelling to
  a different step. The caller decides whether to treat this as unsupported.
- No enharmonic override is performed: a M3 from C always yields E, never Fb.
"""

from __future__ import annotations

from score_engine.score_ir.score_ir import Pitch
from score_engine.transposition.interval import Interval, SpellingError


def spell_transposed_pitch(source: Pitch, interval: Interval) -> Pitch:
    """Return ``source`` transposed by ``interval`` using V1 spelling rules.

    Raises:
        SpellingError: if the required accidental is outside [-2, +2].
    """
    return interval.apply(source)


def spelling_summary(source: Pitch, interval: Interval) -> dict:
    """Diagnostic summary for a transposition spelling (used by tests/reports)."""
    try:
        target = spell_transposed_pitch(source, interval)
        return {
            "source": source,
            "interval": str(interval),
            "target": target,
            "supported": True,
            "error": "",
        }
    except SpellingError as exc:
        return {
            "source": source,
            "interval": str(interval),
            "target": None,
            "supported": False,
            "error": str(exc),
        }
