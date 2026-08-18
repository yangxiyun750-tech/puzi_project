"""OMR Normalization reporter.

Writes OMR_ISSUE_REPORT.json and a human-readable summary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from omr_normalization.issue_model import OMRNormalizationReport


class OMRReporter:
    """Serialize normalization reports to disk."""

    @staticmethod
    def save_json(report: OMRNormalizationReport, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def save_markdown(report: OMRNormalizationReport, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# OMR Normalization Report",
            "",
            f"- Input: `{report.input_path}`",
            f"- Output: `{report.output_path}`",
            f"- Total issues: {len(report.issues)}",
            f"- Safe fixes applied: {len(report.fixes_applied)}",
            "",
            "## Issue Summary",
            "",
        ]

        categories: dict[str, int] = {}
        statuses: dict[str, int] = {}
        severities: dict[str, int] = {}
        for issue in report.issues:
            categories[issue.category] = categories.get(issue.category, 0) + 1
            statuses[issue.status] = statuses.get(issue.status, 0) + 1
            severities[issue.severity] = severities.get(issue.severity, 0) + 1

        lines.append("### By Category")
        for cat, count in sorted(categories.items()):
            lines.append(f"- {cat}: {count}")
        lines.append("")

        lines.append("### By Status")
        for status, count in sorted(statuses.items()):
            lines.append(f"- {status}: {count}")
        lines.append("")

        lines.append("### By Severity")
        for sev, count in sorted(severities.items()):
            lines.append(f"- {sev}: {count}")
        lines.append("")

        if report.fixes_applied:
            lines.append("## Safe Fixes Applied")
            lines.append("")
            for fix in report.fixes_applied:
                lines.append(f"- {json.dumps(fix, ensure_ascii=False)}")
            lines.append("")

        lines.append("## Issues")
        lines.append("")
        lines.append("| ID | Category | Check | Status | Severity | Part | Measure | Voice | Description |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for issue in report.issues:
            lines.append(
                f"| {issue.issue_id} | {issue.category} | {issue.check} | "
                f"{issue.status} | {issue.severity} | {issue.part_id} | "
                f"{issue.measure_number} | {issue.voice_id} | {issue.description} |"
            )
        lines.append("")

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
