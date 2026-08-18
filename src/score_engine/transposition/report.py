"""TransposeReport — human-readable outcome of a transposition operation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from score_engine.score_ir.score_ir import Pitch


@dataclass
class NoteChange:
    """A single note pitch change applied by the engine."""

    part_id: str
    measure_number: str
    voice_id: str
    note_id: str
    before: Pitch | None
    after: Pitch | None


@dataclass
class PartReport:
    """Per-part transposition summary."""

    part_id: str
    operation: str
    transposition_provenance: str = "unknown"
    sounding_audit_available: bool = False
    notes_changed: int = 0
    key_changes: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class TransposeReport:
    """Complete report for a transposition request."""

    status: str  # "ok" | "unsupported" | "error"
    operation: str
    message: str = ""
    parts: list[PartReport] = field(default_factory=list)
    note_changes: list[NoteChange] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "operation": self.operation,
            "message": self.message,
            "warnings": self.warnings,
            "parts": [
                {
                    "part_id": p.part_id,
                    "operation": p.operation,
                    "transposition_provenance": p.transposition_provenance,
                    "sounding_audit_available": p.sounding_audit_available,
                    "notes_changed": p.notes_changed,
                    "key_changes": p.key_changes,
                    "warnings": p.warnings,
                }
                for p in self.parts
            ],
            "note_changes": [
                {
                    "part_id": nc.part_id,
                    "measure_number": nc.measure_number,
                    "voice_id": nc.voice_id,
                    "note_id": nc.note_id,
                    "before": str(nc.before) if nc.before else None,
                    "after": str(nc.after) if nc.after else None,
                }
                for nc in self.note_changes
            ],
        }
