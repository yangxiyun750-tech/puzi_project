"""Deterministic environment readiness checks for ScoreRebuild."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Iterable

from .manifest import load_manifest, project_root


PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    version: str = ""
    path: str = ""
    detail: str = ""
    repair: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _expanded_path(template: str) -> Path | None:
    replacements = {
        "{PROGRAMFILES}": os.environ.get("ProgramFiles", ""),
        "{PROGRAMFILES_X86}": os.environ.get("ProgramFiles(x86)", ""),
        "{LOCALAPPDATA}": os.environ.get("LOCALAPPDATA", ""),
    }
    value = template
    for marker, replacement in replacements.items():
        if marker in value:
            if not replacement:
                return None
            value = value.replace(marker, replacement)
    return Path(value.replace("/", os.sep)).expanduser()


def resolve_binary(spec: dict[str, Any]) -> Path | None:
    override = os.environ.get(str(spec.get("override_env", "")), "").strip()
    if override:
        candidate = Path(os.path.expandvars(override)).expanduser()
        if candidate.is_file():
            return candidate.resolve()

    for command_name in spec.get("command_names", []):
        found = shutil.which(command_name)
        if found:
            return Path(found).resolve()

    for template in spec.get("common_windows", []):
        candidate = _expanded_path(template)
        if candidate and candidate.is_file():
            return candidate.resolve()
    return None


def resolve_manifest_binary(binary_id: str, manifest: dict[str, Any] | None = None) -> Path | None:
    """Resolve one declared executable using the canonical doctor precedence."""

    data = manifest or load_manifest()
    for spec in data.get("required_binaries", []):
        if spec.get("id") == binary_id:
            return resolve_binary(spec)
    raise KeyError(f"Unknown required binary id: {binary_id}")


def _run_version(executable: Path, args: Iterable[str], timeout: int = 25) -> tuple[bool, str, str]:
    try:
        completed = subprocess.run(
            [str(executable), *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, "", str(exc)
    combined = "\n".join(part.strip() for part in (completed.stdout, completed.stderr) if part.strip())
    lines = [line.strip() for line in combined.splitlines() if line.strip()]
    version_line = next((line for line in lines if re.search(r"\d+\.\d+", line)), lines[0] if lines else "unknown")
    ok = completed.returncode == 0 or bool(re.search(r"\d+\.\d+", combined))
    return ok, version_line[:240], combined[:1000]


def _check_python() -> CheckResult:
    version = ".".join(str(part) for part in sys.version_info[:3])
    supported = sys.version_info.major == 3 and sys.version_info.minor == 12
    return CheckResult(
        name="Python",
        status=PASS if supported else FAIL,
        version=version,
        path=str(Path(sys.executable).resolve()),
        detail="Supported range: >=3.12,<3.13.",
        repair="Install Python 3.12 and run doctor with that interpreter." if not supported else "",
    )


def _package_available(spec: dict[str, Any]) -> tuple[bool, str, str]:
    import_names = [spec["import_name"]]
    if spec.get("fallback_import_name"):
        import_names.append(spec["fallback_import_name"])
    found_import = next((name for name in import_names if importlib.util.find_spec(name) is not None), "")
    if not found_import:
        return False, "", ""
    try:
        version = metadata.version(spec["distribution"])
    except metadata.PackageNotFoundError:
        version = "installed; distribution version unavailable"
    return True, version, found_import


def _check_packages(manifest: dict[str, Any]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for required, key in ((True, "required_python_packages"), (False, "optional_python_packages")):
        for spec in manifest.get(key, []):
            available, version, import_name = _package_available(spec)
            status = PASS if available else (FAIL if required else WARN)
            purpose = spec.get("purpose", "")
            detail = f"import={import_name or spec['import_name']}; expected {spec.get('specifier', 'declared version')}"
            if purpose:
                detail = f"{detail}. {purpose}"
            requirements_file = "requirements.txt" if required else "requirements-optional.txt"
            results.append(
                CheckResult(
                    name=f"Python package: {spec['distribution']}",
                    status=status,
                    version=version,
                    path=import_name,
                    detail=detail,
                    repair=(
                        f"Run: python -m pip install -r {requirements_file}"
                        if not available
                        else ""
                    ),
                )
            )
    return results


def _check_binaries(manifest: dict[str, Any]) -> tuple[list[CheckResult], dict[str, Path]]:
    results: list[CheckResult] = []
    resolved: dict[str, Path] = {}
    for spec in manifest.get("required_binaries", []):
        executable = resolve_binary(spec)
        if executable is None:
            results.append(
                CheckResult(
                    name=spec["display_name"],
                    status=FAIL,
                    detail=f"Not found via {spec.get('override_env')}, PATH, or common Windows locations.",
                    repair=spec.get("repair", "Install the required executable."),
                )
            )
            continue
        ok, version, output = _run_version(executable, spec.get("version_args", []))
        resolved[spec["id"]] = executable
        results.append(
            CheckResult(
                name=spec["display_name"],
                status=PASS if ok else FAIL,
                version=version,
                path=str(executable),
                detail=(
                    f"Executable started. Tested baseline: {spec.get('tested_version', 'not pinned')}."
                    if ok
                    else f"Executable could not report a usable version. Output: {output}"
                ),
                repair="" if ok else spec.get("repair", "Repair or reinstall the executable."),
            )
        )
    return results, resolved


def _resolve_java(audiveris: Path | None) -> Path | None:
    override = os.environ.get("AUDIVERIS_JAVA_EXE", "").strip()
    if override and Path(override).is_file():
        return Path(override).resolve()
    if audiveris:
        bundled = audiveris.parent / "runtime" / "bin" / "java.exe"
        if bundled.is_file():
            return bundled.resolve()
    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home:
        candidate = Path(java_home) / "bin" / "java.exe"
        if candidate.is_file():
            return candidate.resolve()
    found = shutil.which("java.exe") or shutil.which("java")
    return Path(found).resolve() if found else None


def _check_java(audiveris: Path | None) -> CheckResult:
    java = _resolve_java(audiveris)
    if java is None:
        return CheckResult(
            name="Audiveris Java runtime",
            status=FAIL,
            detail="No bundled Audiveris Java, AUDIVERIS_JAVA_EXE, JAVA_HOME, or java on PATH was found.",
            repair="Reinstall Audiveris with its runtime, or set AUDIVERIS_JAVA_EXE.",
        )
    ok, version, output = _run_version(java, ["-version"])
    return CheckResult(
        name="Audiveris Java runtime",
        status=PASS if ok else FAIL,
        version=version,
        path=str(java),
        detail="Java runtime started." if ok else f"Java failed to start: {output}",
        repair="" if ok else "Reinstall Audiveris with its Java runtime or set AUDIVERIS_JAVA_EXE.",
    )


def _check_skill_files(manifest: dict[str, Any], root: Path) -> list[CheckResult]:
    results: list[CheckResult] = []
    for skill in manifest.get("required_internal_skills", []):
        paths = [skill["path"], *skill.get("resources", [])]
        missing = [relative for relative in paths if not (root / relative).is_file()]
        results.append(
            CheckResult(
                name=f"Internal Skill: {skill['name']}",
                status=FAIL if missing else PASS,
                path=str(root / skill["path"]),
                detail="All required Skill resources are present." if not missing else f"Missing: {', '.join(missing)}",
                repair="Re-download/restore the tracked project-local Skill files." if missing else "",
            )
        )
    return results


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def schema_directory(manifest: dict[str, Any], root: Path) -> Path:
    schema = manifest["musicxml_schema"]
    override = os.environ.get(schema["override_env"], "").strip()
    return Path(override).expanduser().resolve() if override else (root / schema["default_path"]).resolve()


def _check_schema(manifest: dict[str, Any], root: Path) -> CheckResult:
    schema = manifest["musicxml_schema"]
    directory = schema_directory(manifest, root)
    missing: list[str] = []
    mismatched: list[str] = []
    for name, expected_hash in schema["files"].items():
        path = directory / name
        if not path.is_file():
            missing.append(name)
        elif _sha256(path).lower() != expected_hash.lower():
            mismatched.append(name)
    if missing or mismatched:
        detail_parts = []
        if missing:
            detail_parts.append(f"missing={','.join(missing)}")
        if mismatched:
            detail_parts.append(f"hash_mismatch={','.join(mismatched)}")
        return CheckResult(
            name="MusicXML 4.0 schema",
            status=FAIL,
            version=schema["version"],
            path=str(directory),
            detail="; ".join(detail_parts),
            repair=f"Run: {schema['setup_command']} (see docs/MUSICXML_SCHEMA_SETUP.md).",
        )
    return CheckResult(
        name="MusicXML 4.0 schema",
        status=PASS,
        version=schema["version"],
        path=str(directory),
        detail=f"All {len(schema['files'])} files match the pinned SHA-256 values.",
    )


def _write_check(name: str, directory: Path, repair: str) -> CheckResult:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix="score_rebuild_doctor_", dir=directory, delete=True) as handle:
            handle.write(b"write-test")
            handle.flush()
        return CheckResult(name=name, status=PASS, path=str(directory), detail="Create/write/delete succeeded.")
    except OSError as exc:
        return CheckResult(name=name, status=FAIL, path=str(directory), detail=str(exc), repair=repair)


def run_environment_doctor() -> list[CheckResult]:
    manifest = load_manifest()
    root = project_root()
    results = [_check_python()]
    results.extend(_check_packages(manifest))
    binary_results, resolved = _check_binaries(manifest)
    results.extend(binary_results)
    results.append(_check_java(resolved.get("audiveris")))
    results.extend(_check_skill_files(manifest, root))
    results.append(_check_schema(manifest, root))
    results.append(
        _write_check(
            "Project write permission",
            root,
            "Grant the current user write permission to the project directory or move the project.",
        )
    )
    system_temp = Path(tempfile.gettempdir()).resolve()
    results.append(
        _write_check(
            "Temporary working directory",
            system_temp,
            "Set TEMP/TMP to a writable local directory with sufficient free space.",
        )
    )
    return results


def print_results(results: list[CheckResult]) -> None:
    for result in results:
        print(f"[{result.status}] {result.name}")
        if result.version:
            print(f"  version: {result.version}")
        if result.path:
            print(f"  path: {result.path}")
        if result.detail:
            print(f"  detail: {result.detail}")
        if result.repair:
            print(f"  repair: {result.repair}")
    failures = sum(result.status == FAIL for result in results)
    warnings = sum(result.status == WARN for result in results)
    print(f"\nSUMMARY: PASS={len(results) - failures - warnings} WARN={warnings} FAIL={failures}")


def environment_exit_code(results: list[CheckResult]) -> int:
    return 1 if any(result.status == FAIL for result in results) else 0
