"""Command-line entry point for reproducibility checks only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .capabilities import capability_exit_code, print_capability_results, run_capability_doctor
from .doctor import environment_exit_code, print_results, run_environment_doctor
from .manifest import load_manifest
from .schema import install_schema, verify_schema
from .smoke import run_smoke_test


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="score-rebuild",
        description="ScoreRebuild V0.1 reproducibility doctor and synthetic smoke test.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check executable, package, Skill, schema, and write readiness.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    capability = subparsers.add_parser(
        "capability-doctor",
        help="Check explicit reasoning, visual-review, and human-review capability declarations.",
    )
    capability.add_argument("--code-provider")
    capability.add_argument("--code-verified", action="store_true", default=None)
    capability.add_argument("--visual-provider")
    capability.add_argument("--visual-verified", action="store_true", default=None)
    capability.add_argument("--human-reviewer")
    capability.add_argument("--json", action="store_true")

    schema = subparsers.add_parser("schema-install", help="Download and SHA-256 verify the pinned MusicXML 4.0 schema.")
    schema.add_argument("--force", action="store_true", help="Replace existing mismatched/partial schema files.")
    schema.add_argument("--verify-only", action="store_true", help="Verify without downloading.")

    smoke = subparsers.add_parser("smoke-test", help="Run the non-copyrighted basic connectivity smoke test.")
    smoke.add_argument("--keep-workdir", action="store_true")

    subparsers.add_parser("manifest", help="Print the machine-readable installation manifest.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "doctor":
        results = run_environment_doctor()
        if args.json:
            print(json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False))
        else:
            print_results(results)
        return environment_exit_code(results)

    if args.command == "capability-doctor":
        results = run_capability_doctor(
            code_provider=args.code_provider,
            code_verified=args.code_verified,
            visual_provider=args.visual_provider,
            visual_verified=args.visual_verified,
            human_reviewer=args.human_reviewer,
        )
        if args.json:
            print(json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False))
        else:
            print_capability_results(results)
        return capability_exit_code(results)

    if args.command == "schema-install":
        if args.verify_only:
            valid, errors = verify_schema()
            if valid:
                print("[PASS] MusicXML schema matches the pinned manifest.")
                return 0
            print("[FAIL] MusicXML schema is unavailable or mismatched:")
            for error in errors:
                print(f"  {error}")
            return 1
        return install_schema(force=args.force)

    if args.command == "smoke-test":
        code, _ = run_smoke_test(keep_workdir=args.keep_workdir)
        return code

    if args.command == "manifest":
        print(json.dumps(load_manifest(), indent=2, ensure_ascii=False))
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")
