"""Fast, synthetic, non-copyrighted connectivity smoke test."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .doctor import resolve_binary
from .manifest import load_manifest, project_root


def _run(command: list[str], timeout: int = 150) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    output = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    return completed.returncode == 0, output[:1200]


def _binary(manifest: dict, binary_id: str) -> Path | None:
    spec = next(item for item in manifest["required_binaries"] if item["id"] == binary_id)
    return resolve_binary(spec)


def run_smoke_test(*, keep_workdir: bool = False) -> tuple[int, Path | None]:
    root = project_root()
    fixture = root / "tests" / "fixtures" / "smoke" / "minimal_score.musicxml"
    if not fixture.is_file():
        print(f"[FAIL] Synthetic smoke fixture missing: {fixture}")
        return 1, None

    try:
        parsed = ET.parse(fixture)
    except ET.ParseError as exc:
        print(f"[FAIL] Synthetic MusicXML is not well formed: {exc}")
        return 1, None
    root_element = parsed.getroot()
    if root_element.tag != "score-partwise" or root_element.get("version") != "4.0":
        print("[FAIL] Synthetic fixture is not MusicXML 4.0 score-partwise.")
        return 1, None
    print("[PASS] Synthetic, repository-authored MusicXML fixture is well formed.")

    src_path = root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    try:
        from validation.musicxml_xsd_validator import MusicXML4Validator

        xsd_result = MusicXML4Validator().validate_file(fixture)
    except Exception as exc:
        print(f"[FAIL] MusicXML schema validation could not start: {exc}")
        print("  repair: python -m score_rebuild schema-install")
        return 1, None
    if not xsd_result.xsd_valid:
        messages = "; ".join(error.message for error in xsd_result.errors[:5])
        print(f"[FAIL] Synthetic fixture failed MusicXML 4.0 XSD validation: {messages}")
        return 1, None
    print("[PASS] Synthetic fixture passed pinned MusicXML 4.0 XSD validation.")

    invariant_script = root / ".agents" / "skills" / "orchestral-score-rebuild" / "scripts" / "musicxml_invariants.py"
    ok, output = _run([sys.executable, str(invariant_script), "--self-test"], timeout=30)
    if not ok:
        print(f"[FAIL] MusicXML invariant self-test failed: {output}")
        return 1, None
    print("[PASS] MusicXML invariant checker self-test passed.")

    manifest = load_manifest()
    musescore = _binary(manifest, "musescore")
    pdftoppm = _binary(manifest, "pdftoppm")
    if musescore is None or pdftoppm is None:
        missing = [name for name, path in (("MuseScore", musescore), ("pdftoppm", pdftoppm)) if path is None]
        print(f"[FAIL] Smoke test cannot resolve: {', '.join(missing)}. Run doctor for repair instructions.")
        return 1, None

    temp_path = Path(tempfile.mkdtemp(prefix="score_rebuild_smoke_"))
    try:
        mscz = temp_path / "minimal_score.mscz"
        pdf = temp_path / "minimal_score.pdf"
        preview_prefix = temp_path / "minimal_score_preview"

        ok, output = _run([str(musescore), "--export-to", str(mscz), str(fixture)])
        if not ok or not mscz.is_file() or mscz.stat().st_size == 0:
            print(f"[FAIL] MuseScore MusicXML import/native save failed: {output}")
            return 1, temp_path if keep_workdir else None
        print(f"[PASS] MuseScore imported synthetic MusicXML and created native MSCZ ({mscz.stat().st_size} bytes).")

        ok, output = _run([str(musescore), "--export-to", str(pdf), str(mscz)])
        if not ok or not pdf.is_file() or pdf.stat().st_size == 0:
            print(f"[FAIL] MuseScore PDF export failed: {output}")
            return 1, temp_path if keep_workdir else None
        print(f"[PASS] MuseScore reopened native MSCZ and exported PDF ({pdf.stat().st_size} bytes).")

        ok, output = _run(
            [str(pdftoppm), "-png", "-r", "150", "-f", "1", "-l", "1", str(pdf), str(preview_prefix)],
            timeout=60,
        )
        previews = list(temp_path.glob("minimal_score_preview*.png"))
        if not ok or not previews:
            print(f"[FAIL] Poppler preview render failed: {output}")
            return 1, temp_path if keep_workdir else None
        print(f"[PASS] Poppler rendered the MuseScore PDF preview ({previews[0].name}).")

        print("[PASS] BASIC_PIPELINE_CONNECTIVITY")
        print("  scope: synthetic MusicXML -> XSD -> MuseScore MSCZ -> MuseScore PDF -> Poppler PNG")
        print("  note: Audiveris CLI/Java connectivity is covered by doctor; this is not a musical-quality regression test.")
        return 0, temp_path if keep_workdir else None
    finally:
        if keep_workdir:
            print(f"[INFO] Smoke artifacts kept at {temp_path}")
        else:
            shutil.rmtree(temp_path, ignore_errors=True)


def smoke_environment_hint() -> str:
    return os.environ.get("SCORE_REBUILD_SMOKE_NOTE", "")
