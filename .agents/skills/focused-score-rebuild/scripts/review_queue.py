#!/usr/bin/env python3
"""Maintain a resumable human-review queue for score reconstruction QA."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
MODES = ("guided", "fast", "expert")
SEVERITIES = ("blocking", "important", "cosmetic")
CATEGORIES = (
    "pitch", "octave", "rhythm", "rest", "chord", "voice", "structure",
    "instrument", "transposition", "lyric", "tie_slur", "tuplet", "dynamic",
    "articulation", "technique", "harp", "text", "metadata", "engraving",
)
DECISIONS = ("accept_proposal", "keep_reconstruction", "custom", "defer")
STATUSES = ("awaiting_human", "decision_recorded", "resolved", "deferred")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_queue(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Queue does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid queue JSON: {exc}") from exc
    validate_queue(payload)
    return payload


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


def require_text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def validate_queue(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Queue root must be an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Unsupported schema_version: {payload.get('schema_version')!r}")
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ValueError("project must be an object")
    require_text(project.get("title"), "project.title")
    require_text(project.get("source_pdf"), "project.source_pdf")
    if project.get("review_mode") not in MODES:
        raise ValueError(f"project.review_mode must be one of {MODES}")
    issues = payload.get("issues")
    if not isinstance(issues, list):
        raise ValueError("issues must be an array")
    seen: set[str] = set()
    for index, issue in enumerate(issues):
        prefix = f"issues[{index}]"
        if not isinstance(issue, dict):
            raise ValueError(f"{prefix} must be an object")
        for field in (
            "issue_id", "measure", "instrument", "category", "severity",
            "source_observation", "reconstructed_value", "proposed_action", "status",
        ):
            require_text(issue.get(field), f"{prefix}.{field}")
        issue_id = issue["issue_id"]
        if issue_id in seen:
            raise ValueError(f"Duplicate issue_id: {issue_id}")
        seen.add(issue_id)
        page = issue.get("page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise ValueError(f"{prefix}.page must be an integer >= 1")
        if issue["category"] not in CATEGORIES:
            raise ValueError(f"{prefix}.category must be one of {CATEGORIES}")
        if issue["severity"] not in SEVERITIES:
            raise ValueError(f"{prefix}.severity must be one of {SEVERITIES}")
        if issue["status"] not in STATUSES:
            raise ValueError(f"{prefix}.status must be one of {STATUSES}")
        confidence = issue.get("confidence")
        if confidence is not None and (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise ValueError(f"{prefix}.confidence must be null or between 0 and 1")


def issue_slug(page: int, measure: str, instrument: str, category: str) -> str:
    instrument_slug = re.sub(r"[^A-Z0-9]+", "-", instrument.upper()).strip("-") or "STAFF"
    measure_slug = re.sub(r"[^A-Z0-9]+", "-", measure.upper()).strip("-") or "UNKNOWN"
    return f"P{page:03d}-M{measure_slug}-{instrument_slug}-{category.upper()}"


def unique_issue_id(queue: dict[str, Any], base: str) -> str:
    existing = {item["issue_id"] for item in queue["issues"]}
    if base not in existing:
        return base
    suffix = 2
    while f"{base}-{suffix}" in existing:
        suffix += 1
    return f"{base}-{suffix}"


def find_issue(queue: dict[str, Any], issue_id: str) -> dict[str, Any]:
    for issue in queue["issues"]:
        if issue["issue_id"] == issue_id:
            return issue
    raise ValueError(f"Unknown issue_id: {issue_id}")


def qa_status(queue: dict[str, Any]) -> str:
    unresolved = [issue for issue in queue["issues"] if issue["status"] != "resolved"]
    if any(issue["severity"] in ("blocking", "important") for issue in unresolved):
        return "BLOCKED"
    if not unresolved:
        return "PASS"
    if all(issue["severity"] == "cosmetic" and issue["status"] == "deferred" for issue in unresolved):
        return "PASS_WITH_DEFERRED_COSMETIC_ITEMS"
    return "REVIEW_REQUIRED"


def default_log_path(queue_path: Path) -> Path:
    return queue_path.with_name("decisions.jsonl")


def summary_markdown(queue: dict[str, Any]) -> str:
    counts = {status: 0 for status in STATUSES}
    for issue in queue["issues"]:
        counts[issue["status"]] += 1
    lines = [
        "# Human Review Queue Summary", "",
        f"- Work: `{queue['project']['title']}`",
        f"- Source: `{queue['project']['source_pdf']}`",
        f"- Mode: `{queue['project']['review_mode']}`",
        f"- QA_STATUS: `{qa_status(queue)}`",
        f"- Awaiting human: {counts['awaiting_human']}",
        f"- Decision recorded, not verified: {counts['decision_recorded']}",
        f"- Resolved: {counts['resolved']}",
        f"- Deferred: {counts['deferred']}", "",
        "## Unresolved issues", "",
    ]
    order = {"blocking": 0, "important": 1, "cosmetic": 2}
    unresolved = sorted(
        (issue for issue in queue["issues"] if issue["status"] != "resolved"),
        key=lambda item: (order[item["severity"]], item["page"], str(item["measure"]), item["issue_id"]),
    )
    if not unresolved:
        lines.append("- None.")
    for issue in unresolved:
        lines.extend([
            f"### {issue['issue_id']}", "",
            f"- Location: page {issue['page']}, measure {issue['measure']}, {issue['instrument']}",
            f"- Category/severity/status: `{issue['category']} / {issue['severity']} / {issue['status']}`",
            f"- Source: {issue['source_observation']}",
            f"- Rebuilt: {issue['reconstructed_value']}",
            f"- Proposal: {issue['proposed_action']}",
        ])
        evidence = [
            issue.get("source_image"), issue.get("rebuilt_image"), issue.get("comparison_image")
        ]
        evidence = [value for value in evidence if value]
        if evidence:
            lines.append(f"- Evidence: {' | '.join(evidence)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def add_common_queue_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--queue", required=True, type=Path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create an empty review queue")
    add_common_queue_argument(init)
    init.add_argument("--title", required=True)
    init.add_argument("--source-pdf", required=True)
    init.add_argument("--mode", choices=MODES, default="guided")
    init.add_argument("--force", action="store_true")

    add = commands.add_parser("add", help="Add an unresolved review issue")
    add_common_queue_argument(add)
    add.add_argument("--issue-id")
    add.add_argument("--page", required=True, type=int)
    add.add_argument("--system")
    add.add_argument("--measure", required=True)
    add.add_argument("--instrument", required=True)
    add.add_argument("--category", required=True, choices=CATEGORIES)
    add.add_argument("--severity", required=True, choices=SEVERITIES)
    add.add_argument("--source-observation", required=True)
    add.add_argument("--reconstructed-value", required=True)
    add.add_argument("--proposed-action", required=True)
    add.add_argument("--confidence", type=float)
    add.add_argument("--source-image")
    add.add_argument("--rebuilt-image")
    add.add_argument("--comparison-image")
    add.add_argument("--notes")

    answer = commands.add_parser("answer", help="Record a human decision")
    add_common_queue_argument(answer)
    answer.add_argument("--issue", required=True)
    answer.add_argument("--decision", required=True, choices=DECISIONS)
    answer.add_argument("--value")
    answer.add_argument("--note", default="")
    answer.add_argument("--actor", default="human-reviewer")
    answer.add_argument("--decisions", type=Path)

    verify = commands.add_parser("verify", help="Record post-edit verification")
    add_common_queue_argument(verify)
    verify.add_argument("--issue", required=True)
    verify.add_argument("--result", required=True, choices=("passed", "failed"))
    verify.add_argument("--evidence", required=True)
    verify.add_argument("--actor", default="review-agent")
    verify.add_argument("--decisions", type=Path)

    summary = commands.add_parser("summary", help="Print or write a queue summary")
    add_common_queue_argument(summary)
    summary.add_argument("--output", type=Path)

    validate = commands.add_parser("validate", help="Validate queue structure and state")
    add_common_queue_argument(validate)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    if args.command == "init":
        if args.queue.exists() and not args.force:
            raise ValueError(f"Refusing to overwrite existing queue: {args.queue}")
        payload = {
            "schema_version": SCHEMA_VERSION,
            "project": {
                "title": args.title,
                "source_pdf": args.source_pdf,
                "review_mode": args.mode,
            },
            "issues": [],
        }
        validate_queue(payload)
        atomic_write_json(args.queue, payload)
        print(f"Created {args.queue} with QA_STATUS = PASS")
        return 0

    queue = load_queue(args.queue)
    if args.command == "add":
        if args.page < 1:
            raise ValueError("--page must be >= 1")
        if args.confidence is not None and not 0 <= args.confidence <= 1:
            raise ValueError("--confidence must be between 0 and 1")
        base = args.issue_id or issue_slug(args.page, args.measure, args.instrument, args.category)
        issue_id = unique_issue_id(queue, base)
        issue = {
            "issue_id": issue_id,
            "page": args.page,
            "measure": args.measure,
            "instrument": args.instrument,
            "category": args.category,
            "severity": args.severity,
            "source_observation": args.source_observation,
            "reconstructed_value": args.reconstructed_value,
            "proposed_action": args.proposed_action,
            "confidence": args.confidence,
            "status": "awaiting_human",
            "created_at": now_utc(),
        }
        for name in ("system", "source_image", "rebuilt_image", "comparison_image", "notes"):
            value = getattr(args, name)
            if value:
                issue[name] = value
        queue["issues"].append(issue)
        validate_queue(queue)
        atomic_write_json(args.queue, queue)
        print(f"Added {issue_id}; QA_STATUS = {qa_status(queue)}")
        return 0

    if args.command == "answer":
        issue = find_issue(queue, args.issue)
        if issue["status"] == "resolved":
            raise ValueError(f"Issue is already resolved: {args.issue}")
        if args.decision == "custom" and not (args.value and args.value.strip()):
            raise ValueError("--value is required for a custom decision")
        timestamp = now_utc()
        issue.update({
            "decision": args.decision,
            "decision_value": args.value or "",
            "decision_note": args.note,
            "decided_by": args.actor,
            "decided_at": timestamp,
            "status": "deferred" if args.decision == "defer" else "decision_recorded",
        })
        event = {
            "event": "answer", "issue_id": args.issue, "decision": args.decision,
            "value": args.value or "", "note": args.note, "actor": args.actor,
            "timestamp": timestamp,
        }
        validate_queue(queue)
        atomic_write_json(args.queue, queue)
        append_event(args.decisions or default_log_path(args.queue), event)
        print(f"Recorded {args.decision} for {args.issue}; QA_STATUS = {qa_status(queue)}")
        return 0

    if args.command == "verify":
        issue = find_issue(queue, args.issue)
        if args.result == "passed" and issue["status"] != "decision_recorded":
            raise ValueError("A passed verification requires a recorded, non-deferred decision")
        timestamp = now_utc()
        issue.update({
            "verification_result": args.result,
            "verification_evidence": args.evidence,
            "verified_by": args.actor,
            "verified_at": timestamp,
            "status": "resolved" if args.result == "passed" else "awaiting_human",
        })
        event = {
            "event": "verification", "issue_id": args.issue, "result": args.result,
            "evidence": args.evidence, "actor": args.actor, "timestamp": timestamp,
        }
        validate_queue(queue)
        atomic_write_json(args.queue, queue)
        append_event(args.decisions or default_log_path(args.queue), event)
        print(f"Verification {args.result} for {args.issue}; QA_STATUS = {qa_status(queue)}")
        return 0

    if args.command == "summary":
        content = summary_markdown(queue)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8", newline="\n")
            print(f"Wrote {args.output}; QA_STATUS = {qa_status(queue)}")
        else:
            print(content, end="")
        return 0

    if args.command == "validate":
        print(f"VALID; {len(queue['issues'])} issues; QA_STATUS = {qa_status(queue)}")
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
