"""QA reporter — unified QA_SUMMARY.json and QA_REPORT.md.

The report organizes every issue as Part -> Measure -> Issue, with
evidence, handling result and confidence. The delivery verdict is
computed from the open issues: delivery is allowed only when no
AI_REVIEW / HUMAN_REVIEW issue remains open and every SAFE_REPAIR
issue was applied and re-verified.
"""

from __future__ import annotations

import json
from pathlib import Path

from qa.qa_model import QAReport, QAIssue, QAStatus


def _sort_key(measure_number: str):
    try:
        return (0, int(measure_number.split("X")[0]))
    except ValueError:
        return (1, measure_number)


class QAReporter:
    """Write QA_SUMMARY.json and QA_REPORT.md."""

    def __init__(self, report: QAReport) -> None:
        self.report = report

    # ------------------------------------------------------------------

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------

    def save_markdown(self, path: str | Path) -> None:
        r = self.report
        v = r.delivery_verdict
        lines = [
            f"# QA Report — {r.project}",
            "",
            f"Generated: {r.created_at}",
            "",
            "## 1. Delivery Verdict",
            "",
            f"**Delivery allowed: {'YES' if v.allowed else 'NO'}**",
            "",
            f"- Open AI_REVIEW issues: {v.open_ai_review}",
            f"- Open HUMAN_REVIEW issues: {v.open_human_review}",
            f"- Unverified SAFE_REPAIR issues: {v.unverified_safe_repair}",
            "",
        ]
        for c in v.conditions:
            lines.append(f"- {c}")
        if v.blocking_issue_ids:
            lines.append("")
            lines.append("Blocking issues: " + ", ".join(v.blocking_issue_ids))
        lines += [
            "",
            "## 2. Stage Summary",
            "",
            "| Stage | Status | Checks | PASS | SAFE_REPAIR | AI_REVIEW | HUMAN_REVIEW |",
            "|---|---|---|---|---|---|---|",
        ]
        for s in r.stages:
            lines.append(
                f"| {s.stage} | {s.status} | {s.checks_run} | "
                f"{len([i for i in s.issues if i.status == QAStatus.PASS])} | "
                f"{len([i for i in s.issues if i.status == QAStatus.SAFE_REPAIR])} | "
                f"{len([i for i in s.issues if i.status == QAStatus.AI_REVIEW])} | "
                f"{len([i for i in s.issues if i.status == QAStatus.HUMAN_REVIEW])} |"
            )
        lines += [
            "",
            "## 3. Issues by Part → Measure → Issue",
            "",
        ]

        issues = [i for i in r.all_issues() if i.status != QAStatus.PASS]
        # global issues (no part)
        global_issues = [i for i in issues if not i.part_id]
        part_issues = [i for i in issues if i.part_id]

        if global_issues:
            lines += ["### Global", ""]
            lines += [
                "| Status | Severity | Category | Check | Description | Confidence |",
                "|---|---|---|---|---|---|",
            ]
            for i in sorted(global_issues, key=lambda x: (x.status, x.severity)):
                lines.append(
                    f"| {self._status_cell(i)} | {i.severity} | {i.category} | "
                    f"{i.check} | {i.description} | {i.confidence} |"
                )
            lines.append("")

        part_ids = sorted({i.part_id for i in part_issues})
        for pid in part_ids:
            lines += [f"### Part {pid}", ""]
            pid_issues = [i for i in part_issues if i.part_id == pid]
            # part-level (no measure) first
            level = [i for i in pid_issues if not i.measure_number]
            if level:
                lines.append("**Part-level issues**")
                lines.append("")
                for i in level:
                    lines.append(
                        f"- [{i.status}] {i.severity} — {i.check}: {i.description} "
                        f"(confidence {i.confidence})"
                    )
                lines.append("")
            by_measure: dict[str, list[QAIssue]] = {}
            for i in pid_issues:
                if i.measure_number:
                    by_measure.setdefault(i.measure_number, []).append(i)
            for mn in sorted(by_measure, key=_sort_key):
                lines.append(f"**Measure {mn}**")
                lines.append("")
                lines.append("| Status | Severity | Check | Description | Evidence | Confidence |")
                lines.append("|---|---|---|---|---|---|")
                for i in by_measure[mn]:
                    ev = json.dumps(i.evidence, ensure_ascii=False)
                    if len(ev) > 80:
                        ev = ev[:77] + "..."
                    lines.append(
                        f"| {self._status_cell(i)} | {i.severity} | {i.check} | "
                        f"{i.description} | {ev} | {i.confidence} |"
                    )
                lines.append("")

        if r.fixes_applied:
            lines += [
                "## 4. SAFE_REPAIR Fixes Applied",
                "",
            ]
            for fix in r.fixes_applied:
                lines.append(
                    f"- {json.dumps(fix, ensure_ascii=False, default=str)}"
                )
            lines.append("")

        lines += [
            "## 5. Inputs",
            "",
        ]
        for k, vv in r.inputs.items():
            lines.append(f"- {k}: `{vv}`")
        lines.append("")

        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------

    @staticmethod
    def _status_cell(issue: QAIssue) -> str:
        s = issue.status
        if s == QAStatus.SAFE_REPAIR and issue.fix_applied:
            if issue.verified_after_fix == QAStatus.PASS:
                return "FIXED ✔"
            return "ESCALATED ✘"
        return s
