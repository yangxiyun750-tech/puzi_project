#!/usr/bin/env python3
"""Maintain a private question-driven catalog of reconstructed scores."""

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
REQUIRED_FIELDS = (
    "score_type", "source_quality", "genre", "purpose", "difficulty",
    "instrumentation", "rights_status",
)
OPTIONAL_FIELDS = ("language", "tags")
CHOICES = {
    "score_type": ("melody", "voice_piano", "wind_band_basic", "out_of_scope"),
    "source_quality": ("eligible", "needs_rescan", "unsupported_source"),
    "difficulty": ("beginner", "intermediate", "advanced", "unknown"),
    "rights_status": ("owned", "licensed", "public_domain", "permission_confirmed", "unknown"),
}
PROMPTS = {
    "score_type": "Which supported score family is this: melody, voice_piano, wind_band_basic, or out_of_scope?",
    "source_quality": "Is every required PDF page eligible, needs_rescan, or unsupported_source?",
    "genre": "What genre or style best describes this work?",
    "purpose": "What is the main use: practice, teaching, rehearsal, performance, arranging, audition, or archive?",
    "difficulty": "What is the practical difficulty: beginner, intermediate, advanced, or unknown?",
    "instrumentation": "What is the concise instrumentation or performing force?",
    "rights_status": "What authorizes processing: owned, licensed, public_domain, permission_confirmed, or unknown?",
    "language": "What is the lyric language, or instrumental if there are no lyrics?",
    "tags": "Which optional comma-separated tags would help group similar works?",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_text(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
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


def default_log(catalog: Path) -> Path:
    return catalog.with_name("classification_decisions.jsonl")


def entry_status(entry: dict[str, Any]) -> str:
    answers = entry["answers"]
    if answers.get("score_type") == "out_of_scope":
        return "OUT_OF_SCOPE"
    quality = answers.get("source_quality")
    if quality in ("needs_rescan", "unsupported_source"):
        return "SOURCE_BLOCKED"
    if answers.get("rights_status") == "unknown":
        return "RIGHTS_REVIEW_REQUIRED"
    if any(not answers.get(field) for field in REQUIRED_FIELDS):
        return "NEEDS_ANSWERS"
    return "CLASSIFIED"


def validate_catalog(payload: Any) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported or missing catalog schema_version")
    entries = payload.get("entries")
    collections = payload.get("collections")
    if not isinstance(entries, dict) or not isinstance(collections, dict):
        raise ValueError("entries and collections must be objects")
    for work_id, entry in entries.items():
        require_text(work_id, "work_id")
        if not isinstance(entry, dict) or entry.get("work_id") != work_id:
            raise ValueError(f"Invalid entry: {work_id}")
        require_text(entry.get("title"), f"{work_id}.title")
        require_text(entry.get("source_pdf"), f"{work_id}.source_pdf")
        answers = entry.get("answers")
        if not isinstance(answers, dict):
            raise ValueError(f"{work_id}.answers must be an object")
        for field, choices in CHOICES.items():
            value = answers.get(field)
            if value is not None and value not in choices:
                raise ValueError(f"{work_id}.{field} must be one of {choices}")
        if "tags" in answers and not isinstance(answers["tags"], list):
            raise ValueError(f"{work_id}.tags must be an array")
        memberships = entry.get("collection_ids")
        if not isinstance(memberships, list) or any(item not in collections for item in memberships):
            raise ValueError(f"{work_id}.collection_ids contains an unknown collection")
        if entry.get("status") != entry_status(entry):
            raise ValueError(f"{work_id}.status is stale")
    for collection_id, collection in collections.items():
        require_text(collection_id, "collection_id")
        if not isinstance(collection, dict) or collection.get("collection_id") != collection_id:
            raise ValueError(f"Invalid collection: {collection_id}")
        require_text(collection.get("name"), f"{collection_id}.name")


def load_catalog(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Catalog does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid catalog JSON: {exc}") from exc
    validate_catalog(payload)
    return payload


def get_entry(catalog: dict[str, Any], work_id: str) -> dict[str, Any]:
    try:
        return catalog["entries"][work_id]
    except KeyError as exc:
        raise ValueError(f"Unknown work_id: {work_id}") from exc


def parse_answer(field: str, value: str) -> Any:
    value = value.strip()
    if not value:
        raise ValueError("Answer value must not be empty")
    if field in CHOICES:
        normalized = value.lower()
        if normalized not in CHOICES[field]:
            raise ValueError(f"{field} must be one of {CHOICES[field]}")
        return normalized
    if field == "tags":
        return sorted({item.strip() for item in value.split(",") if item.strip()}, key=str.casefold)
    return value


def tokens(value: Any) -> set[str]:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return {item for item in re.split(r"[^\w\u4e00-\u9fff]+", str(value).casefold()) if item}


def similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    a, b = left["answers"], right["answers"]
    score = 0.0
    if a.get("score_type") == b.get("score_type"):
        score += 4.0
    if a.get("difficulty") == b.get("difficulty"):
        score += 2.0
    for field in ("genre", "purpose", "instrumentation", "language", "tags"):
        one, two = tokens(a.get(field, "")), tokens(b.get(field, ""))
        if one and two:
            score += len(one & two) / len(one | two)
    return score


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init")
    init.add_argument("--catalog", required=True, type=Path)
    init.add_argument("--force", action="store_true")

    start = commands.add_parser("start")
    start.add_argument("--catalog", required=True, type=Path)
    start.add_argument("--work-id", required=True)
    start.add_argument("--title", required=True)
    start.add_argument("--source-pdf", required=True)

    questions = commands.add_parser("questions")
    questions.add_argument("--catalog", required=True, type=Path)
    questions.add_argument("--work-id", required=True)
    questions.add_argument("--limit", type=int, default=3)

    answer = commands.add_parser("answer")
    answer.add_argument("--catalog", required=True, type=Path)
    answer.add_argument("--work-id", required=True)
    answer.add_argument("--field", required=True, choices=REQUIRED_FIELDS + OPTIONAL_FIELDS)
    answer.add_argument("--value", required=True)
    answer.add_argument("--actor", default="human-reviewer")
    answer.add_argument("--decisions", type=Path)

    add_collection = commands.add_parser("collection-add")
    add_collection.add_argument("--catalog", required=True, type=Path)
    add_collection.add_argument("--collection-id", required=True)
    add_collection.add_argument("--name", required=True)
    add_collection.add_argument("--description", default="")

    assign = commands.add_parser("assign")
    assign.add_argument("--catalog", required=True, type=Path)
    assign.add_argument("--work-id", required=True)
    assign.add_argument("--collection-id", required=True)
    assign.add_argument("--reason", required=True)
    assign.add_argument("--actor", default="human-reviewer")
    assign.add_argument("--decisions", type=Path)

    similar = commands.add_parser("similar")
    similar.add_argument("--catalog", required=True, type=Path)
    similar.add_argument("--work-id", required=True)
    similar.add_argument("--limit", type=int, default=5)

    summary = commands.add_parser("summary")
    summary.add_argument("--catalog", required=True, type=Path)
    validate = commands.add_parser("validate")
    validate.add_argument("--catalog", required=True, type=Path)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    if args.command == "init":
        if args.catalog.exists() and not args.force:
            raise ValueError(f"Refusing to overwrite existing catalog: {args.catalog}")
        payload = {"schema_version": SCHEMA_VERSION, "entries": {}, "collections": {}}
        atomic_write(args.catalog, payload)
        print(f"Created {args.catalog}")
        return 0

    catalog = load_catalog(args.catalog)
    if args.command == "start":
        if args.work_id in catalog["entries"]:
            raise ValueError(f"work_id already exists: {args.work_id}")
        timestamp = now_utc()
        entry = {
            "work_id": args.work_id, "title": args.title, "source_pdf": args.source_pdf,
            "answers": {}, "collection_ids": [], "status": "NEEDS_ANSWERS",
            "created_at": timestamp, "updated_at": timestamp,
        }
        catalog["entries"][args.work_id] = entry
        validate_catalog(catalog)
        atomic_write(args.catalog, catalog)
        print(f"Created {args.work_id}; CLASSIFICATION_STATUS = {entry['status']}")
        return 0

    entry = get_entry(catalog, getattr(args, "work_id", "")) if hasattr(args, "work_id") else None
    if args.command == "questions":
        if args.limit < 1 or args.limit > 3:
            raise ValueError("--limit must be from 1 through 3")
        if entry["status"] != "NEEDS_ANSWERS":
            print(f"No new questions; CLASSIFICATION_STATUS = {entry['status']}")
            return 0
        missing = [field for field in REQUIRED_FIELDS if not entry["answers"].get(field)]
        for index, field in enumerate(missing[: args.limit], 1):
            print(f"{index}. [{field}] {PROMPTS[field]}")
        return 0

    if args.command == "answer":
        parsed = parse_answer(args.field, args.value)
        timestamp = now_utc()
        entry["answers"][args.field] = parsed
        entry["updated_at"] = timestamp
        entry["status"] = entry_status(entry)
        validate_catalog(catalog)
        atomic_write(args.catalog, catalog)
        append_event(args.decisions or default_log(args.catalog), {
            "event": "classification_answer", "work_id": args.work_id,
            "field": args.field, "value": parsed, "actor": args.actor, "timestamp": timestamp,
        })
        print(f"Recorded {args.field}; CLASSIFICATION_STATUS = {entry['status']}")
        return 0

    if args.command == "collection-add":
        if args.collection_id in catalog["collections"]:
            raise ValueError(f"collection_id already exists: {args.collection_id}")
        catalog["collections"][args.collection_id] = {
            "collection_id": args.collection_id, "name": args.name,
            "description": args.description, "created_at": now_utc(),
        }
        validate_catalog(catalog)
        atomic_write(args.catalog, catalog)
        print(f"Created collection {args.collection_id}")
        return 0

    if args.command == "assign":
        if args.collection_id not in catalog["collections"]:
            raise ValueError(f"Unknown collection_id: {args.collection_id}")
        if entry["status"] != "CLASSIFIED":
            raise ValueError(f"Entry must be CLASSIFIED before assignment; got {entry['status']}")
        if args.collection_id not in entry["collection_ids"]:
            entry["collection_ids"].append(args.collection_id)
            entry["collection_ids"].sort()
        timestamp = now_utc()
        entry["updated_at"] = timestamp
        validate_catalog(catalog)
        atomic_write(args.catalog, catalog)
        append_event(args.decisions or default_log(args.catalog), {
            "event": "collection_assignment", "work_id": args.work_id,
            "collection_id": args.collection_id, "reason": args.reason,
            "actor": args.actor, "timestamp": timestamp,
        })
        print(f"Assigned {args.work_id} to {args.collection_id}")
        return 0

    if args.command == "similar":
        candidates = []
        for other_id, other in catalog["entries"].items():
            if other_id != args.work_id and other["status"] == "CLASSIFIED":
                candidates.append((similarity(entry, other), other_id, other["title"]))
        for score, work_id, title in sorted(candidates, key=lambda item: (-item[0], item[1]))[: args.limit]:
            print(f"{score:.3f}\t{work_id}\t{title}")
        return 0

    if args.command == "summary":
        counts: dict[str, int] = {}
        for item in catalog["entries"].values():
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        print(f"Entries: {len(catalog['entries'])}; Collections: {len(catalog['collections'])}")
        for status in sorted(counts):
            print(f"{status}: {counts[status]}")
        return 0

    if args.command == "validate":
        print(f"VALID; {len(catalog['entries'])} entries; {len(catalog['collections'])} collections")
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
