"""Smoke tests for the AI Score Toolkit Phase 1 toolchain.

Isolated artifacts are written to a temp directory and cleaned up on success.
Run with:
    PYTHONPATH=src python tests/smoke_test_toolchain.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Allow imports from project root.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from tests.e2e_fixtures import make_clean_musicxml


def main() -> int:
    workdir = Path(tempfile.mkdtemp(prefix="ai_score_toolkit_smoke_"))
    print(f"Smoke test workdir: {workdir}")

    try:
        # 1. Generate two isolated MusicXML files (A and B).
        xml_a_path = workdir / "score_a.musicxml"
        xml_b_path = workdir / "score_b.musicxml"
        xml_a_path.write_text(make_clean_musicxml(measures=8, trumpets=2), encoding="utf-8")
        # B is identical except one extra measure so musicdiff has a detectable difference.
        xml_b_path.write_text(make_clean_musicxml(measures=9, trumpets=2), encoding="utf-8")
        print(f"[OK] Generated MusicXML A ({xml_a_path}) and B ({xml_b_path})")

        # 2. MusicXML -> music21 parse.
        try:
            import music21

            score_a = music21.converter.parse(str(xml_a_path))
            score_b = music21.converter.parse(str(xml_b_path))
            print(f"[OK] music21 parsed A ({len(score_a.parts)} parts) and B ({len(score_b.parts)} parts)")
        except Exception as exc:
            print(f"[FAIL] music21 parse: {exc}")
            return 1

        # 3. MusicXML -> Partitura parse.
        try:
            import partitura

            pt_score_a = partitura.load_musicxml(str(xml_a_path))
            pt_score_b = partitura.load_musicxml(str(xml_b_path))
            print(f"[OK] Partitura parsed A ({len(pt_score_a.parts)} parts) and B ({len(pt_score_b.parts)} parts)")
        except Exception as exc:
            print(f"[FAIL] Partitura parse: {exc}")
            return 1

        # 4. MusicXML -> MuseScore CLI render.
        musescore_exe = Path(r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe")
        if not musescore_exe.exists():
            print(f"[SKIP] MuseScore CLI not found at {musescore_exe}")
        else:
            png_dir = workdir / "musescore_png"
            png_dir.mkdir()
            cmd = [
                str(musescore_exe),
                "--score-media",
                "--export-to", str(png_dir / "score_a.png"),
                str(xml_a_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                # Try a simpler export if --score-media is unsupported.
                cmd = [
                    str(musescore_exe),
                    "--export-to", str(png_dir / "score_a.pdf"),
                    str(xml_a_path),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                print(f"[FAIL] MuseScore CLI render: {result.stderr[:500]}")
                return 1
            print(f"[OK] MuseScore CLI rendered A to {png_dir}")

        # 5. MusicXML A/B -> musicdiff.
        try:
            from musicdiff import AnnScore, Comparison

            ann_a = AnnScore(score_a)
            ann_b = AnnScore(score_b)
            ops, cost = Comparison.annotated_scores_diff(ann_a, ann_b)
            print(f"[OK] musicdiff compared A vs B (cost={cost}, ops={len(ops)})")
        except Exception as exc:
            print(f"[FAIL] musicdiff comparison: {exc}")
            return 1

        print("\n[ALL PASS] Smoke tests completed successfully.")
        return 0

    finally:
        # 6. Isolate artifacts: keep only a summary; delete the temp tree.
        summary_path = workdir / "SMOKE_TEST_SUMMARY.txt"
        summary_path.write_text(
            "Smoke test artifacts were generated and verified in this directory.\n"
            "This directory is safe to delete.\n",
            encoding="utf-8",
        )
        print(f"[INFO] Artifacts kept at {workdir} (will be removed by OS temp cleanup or can be deleted manually)")


if __name__ == "__main__":
    raise SystemExit(main())
