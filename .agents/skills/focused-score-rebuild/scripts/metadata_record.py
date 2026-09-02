#!/usr/bin/env python3
"""Maintain an evidence-backed multilingual score metadata record."""
from __future__ import annotations
import argparse, json, os, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
TITLE_KINDS = ("original", "subtitle", "alternate", "translated", "romanized", "supplied")
STATUSES = ("proposed", "confirmed", "rejected")
METHODS = ("pdf_text", "ocr", "vision", "human", "music_analysis")
INFO_FIELDS = ("opus_catalog", "movement", "dedication", "tempo_text", "instrumentation",
               "lyric_language", "source_pitch_convention", "source_concert_key")

def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def require_text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")

def validate_evidence(item: dict[str, Any]) -> None:
    if item.get("method") not in METHODS or item.get("status") not in STATUSES:
        raise ValueError("Invalid evidence method or status")
    require_text(item.get("location"), "evidence.location")
    confidence = item.get("confidence")
    if confidence is not None and (not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
        raise ValueError("confidence must be null or between 0 and 1")

def validate(payload: Any) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported or missing schema_version")
    require_text(payload.get("source_pdf"), "source_pdf")
    for item in payload.get("titles", []):
        require_text(item.get("value"), "title.value")
        if item.get("kind") not in TITLE_KINDS:
            raise ValueError("Invalid title kind")
        validate_evidence(item)
    for item in payload.get("contributors", []):
        require_text(item.get("name"), "contributor.name")
        require_text(item.get("role"), "contributor.role")
        validate_evidence(item)
    info = payload.get("music_info")
    if not isinstance(info, dict) or any(key not in INFO_FIELDS for key in info):
        raise ValueError("music_info contains an unsupported field")
    for key, item in info.items():
        require_text(item.get("value"), f"music_info.{key}.value")
        validate_evidence(item)

def load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Record does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    validate(payload)
    return payload

def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2); stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        try: os.unlink(temporary)
        except OSError: pass
        raise

def status(payload: dict[str, Any]) -> str:
    display = any(x["kind"] in ("original", "supplied") and x["status"] == "confirmed"
                  for x in payload["titles"])
    pending = any(x["status"] == "proposed"
                  for group in (payload["titles"], payload["contributors"], payload["music_info"].values())
                  for x in group)
    return "PASS" if display and not pending else "REVIEW_REQUIRED"

def add_evidence(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--method", required=True, choices=METHODS)
    parser.add_argument("--location", required=True)
    parser.add_argument("--language", default="und")
    parser.add_argument("--script", default="Zyyy")
    parser.add_argument("--confidence", type=float)
    parser.add_argument("--status", default="proposed", choices=STATUSES)

def evidence(args: argparse.Namespace) -> dict[str, Any]:
    if args.confidence is not None and not 0 <= args.confidence <= 1:
        raise ValueError("--confidence must be between 0 and 1")
    return {"method": args.method, "location": args.location, "language": args.language,
            "script": args.script, "confidence": args.confidence, "status": args.status,
            "recorded_at": now()}

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("init"); p.add_argument("--record", required=True, type=Path)
    p.add_argument("--source-pdf", required=True); p.add_argument("--force", action="store_true")
    p = commands.add_parser("add-title"); p.add_argument("--record", required=True, type=Path)
    p.add_argument("--kind", required=True, choices=TITLE_KINDS); p.add_argument("--value", required=True); add_evidence(p)
    p = commands.add_parser("add-contributor"); p.add_argument("--record", required=True, type=Path)
    p.add_argument("--role", required=True); p.add_argument("--name", required=True); add_evidence(p)
    p = commands.add_parser("set-info"); p.add_argument("--record", required=True, type=Path)
    p.add_argument("--field", required=True, choices=INFO_FIELDS); p.add_argument("--value", required=True); add_evidence(p)
    for name in ("validate", "summary"):
        p = commands.add_parser(name); p.add_argument("--record", required=True, type=Path)
    return parser.parse_args(argv)

def run(args) -> int:
    if args.command == "init":
        if args.record.exists() and not args.force:
            raise ValueError(f"Refusing to overwrite existing record: {args.record}")
        payload = {"schema_version": 1, "source_pdf": args.source_pdf, "titles": [],
                   "contributors": [], "music_info": {}, "updated_at": now()}
    else:
        payload = load(args.record)
        if args.command == "add-title":
            payload["titles"].append({"kind": args.kind, "value": args.value, **evidence(args)})
        elif args.command == "add-contributor":
            payload["contributors"].append({"role": args.role, "name": args.name, **evidence(args)})
        elif args.command == "set-info":
            payload["music_info"][args.field] = {"value": args.value, **evidence(args)}
        elif args.command in ("validate", "summary"):
            print(f"VALID; METADATA_STATUS = {status(payload)}"); return 0
    payload["updated_at"] = now(); validate(payload); write(args.record, payload)
    print(f"Updated {args.record}; METADATA_STATUS = {status(payload)}"); return 0

def main(argv=None) -> int:
    try: return run(parse_args(argv))
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr); return 2

if __name__ == "__main__":
    raise SystemExit(main())
