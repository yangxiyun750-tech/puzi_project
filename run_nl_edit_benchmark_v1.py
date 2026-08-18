"""Standalone runner for Natural Language Music Editing Acceptance Benchmark V1.

Usage:
    $env:PYTHONPATH="src"
    python run_nl_edit_benchmark_v1.py

Output:
    reports/nl_edit_benchmark_v1.md
    reports/nl_edit_benchmark_v1.json
"""

from __future__ import annotations

from tests.test_nl_edit_benchmark_v1 import run_benchmark, write_reports


def main() -> int:
    results = run_benchmark()
    write_reports(results)
    print(f"Benchmark V1 complete: {len(results)} cases")
    print(f"Report: reports/nl_edit_benchmark_v1.md")
    print(f"Report: reports/nl_edit_benchmark_v1.json")
    for r in results:
        print(f"  {r.case_id}: {r.actual_status} ({r.resolver_status})")
    return 1 if any(r.actual_status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
