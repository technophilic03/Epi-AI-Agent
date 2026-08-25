from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SCIENTIFIC_PACKAGES = (
    "lifelines",
    "matplotlib",
    "numpy",
    "openpyxl",
    "pandas",
    "pyarrow",
    "scipy",
    "seaborn",
    "statsmodels",
    "xlrd",
)
FRONTEND_BUILD_INPUTS = {
    "frontend/index.html",
    "frontend/package-lock.json",
    "frontend/package.json",
    "frontend/tsconfig.app.json",
    "frontend/tsconfig.json",
    "frontend/tsconfig.node.json",
    "frontend/vite.config.ts",
}
REQUIRED_WORKING_DEMO_PATHS = (
    "study_installer.py",
    "frontend/dist/index.html",
    "frontend/dist/build-manifest.json",
    "frontend/src/App.tsx",
)
REQUIRED_LOCAL_ONLY_PATHS = (
    ".env",
    ".github/CODEOWNERS",
    ".venv",
    "AGENTS.md",
    "docs/untracked-development-note.md",
    "frontend/node_modules",
    "__pycache__/example.pyc",
    "local_data/example.csv",
    "study_data/studies/example-study/1.0.0/database/study.duckdb",
    "run_fastapi_typescript_app.py",
    "runtime/datasets/example.csv",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frontend_source_paths(tracked_paths: Iterable[str]) -> list[str]:
    return sorted(
        path
        for path in set(tracked_paths)
        if path.startswith("frontend/src/") or path in FRONTEND_BUILD_INPUTS
    )


def _vite_version(project_root: Path) -> str:
    lock_path = project_root / "frontend" / "package-lock.json"
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    packages = payload.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("frontend/package-lock.json has no packages object")
    vite = packages.get("node_modules/vite")
    if not isinstance(vite, dict) or not str(vite.get("version") or "").strip():
        raise ValueError("frontend/package-lock.json has no installed Vite version")
    return str(vite["version"])


def create_frontend_build_manifest(
    project_root: str | Path,
    tracked_paths: Iterable[str],
) -> dict[str, Any]:
    root = Path(project_root)
    source_paths = _frontend_source_paths(tracked_paths)
    return {
        "built_at": datetime.now(UTC).isoformat(),
        "vite_version": _vite_version(root),
        "source_sha256": {
            path: _sha256(root / path)
            for path in source_paths
            if (root / path).is_file()
        },
    }


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _requirement_names(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    names: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith(("-", ".")):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)", line)
        if match:
            names.add(match.group(1).casefold().replace("_", "-"))
    return names


def _has_nonempty_example_secret(path: Path) -> list[str]:
    if not path.is_file():
        return []
    violations: list[str] = []
    secret_name = re.compile(r"(?:KEY|TOKEN|SECRET|PASSWORD)$", re.IGNORECASE)
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if secret_name.search(name.strip()) and value.strip():
            violations.append(
                f".env.example has a nonempty secret assignment for "
                f"{name.strip()} on line {line_number}"
            )
    return violations


def _forbidden_tracked_reason(path: str) -> str | None:
    pure = PurePosixPath(path)
    parts = {part.casefold() for part in pure.parts}
    lower = path.casefold()
    top_level = pure.parts[0].casefold() if pure.parts else ""
    if path == ".env":
        return "tracked local secret file"
    if top_level == "local_data":
        return "tracked local dataset"
    if top_level == "study_data":
        return "tracked installed study package"
    if top_level == "runtime":
        return "tracked runtime state"
    if "original_paper" in parts or "paper_summary" in parts:
        return "tracked source paper material"
    if pure.suffix.casefold() == ".pdf":
        return "tracked PDF"
    if "__pycache__" in parts or pure.suffix.casefold() in {".pyc", ".pyo"}:
        return "tracked Python cache"
    if pure.suffix.casefold() in {".log", ".pid", ".pem", ".key"}:
        return "tracked log, PID, or secret-like file"
    if (
        ("r_sandbox" in lower or "r_runtime" in lower)
        and "package-governed-r-analysis-design.md" not in lower
    ):
        return "tracked R runtime or sandbox"
    return None


def collect_delivery_violations(
    project_root: str | Path,
    tracked_paths: Iterable[str],
) -> list[str]:
    root = Path(project_root)
    tracked = sorted(set(tracked_paths))
    tracked_set = set(tracked)
    violations: list[str] = []

    if (
        "study_installer.py" not in tracked_set
        or not (root / "study_installer.py").is_file()
    ):
        violations.append("required study installer is missing: study_installer.py")
    if "frontend/dist/index.html" not in tracked_set:
        violations.append("required built UI is missing: frontend/dist/index.html")
    if "frontend/dist/build-manifest.json" not in tracked_set:
        violations.append(
            "required UI build manifest is missing: "
            "frontend/dist/build-manifest.json"
        )
    if not any(path.startswith("frontend/dist/assets/") for path in tracked):
        violations.append("required built UI assets are missing")

    for path in tracked:
        reason = _forbidden_tracked_reason(path)
        if reason:
            violations.append(f"{reason}: {path}")

    violations.extend(_has_nonempty_example_secret(root / ".env.example"))

    requirements = _requirement_names(root / "requirements.txt")
    for package in REQUIRED_SCIENTIFIC_PACKAGES:
        if package.casefold().replace("_", "-") not in requirements:
            violations.append(
                f"required scientific package is missing from requirements.txt: "
                f"{package}"
            )

    manifest_path = root / "frontend" / "dist" / "build-manifest.json"
    manifest = _read_manifest(manifest_path)
    if manifest is not None:
        expected = create_frontend_build_manifest(root, tracked)
        if (
            manifest.get("vite_version") != expected["vite_version"]
            or manifest.get("source_sha256") != expected["source_sha256"]
        ):
            violations.append(
                "frontend build manifest does not match current frontend sources"
            )
    elif "frontend/dist/build-manifest.json" in tracked_set:
        violations.append("frontend build manifest is not valid JSON")

    return sorted(set(violations))


def tracked_paths(project_root: str | Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=project_root,
        check=True,
        capture_output=True,
    )
    return [
        path.decode("utf-8")
        for path in result.stdout.split(b"\0")
        if path
    ]


def _ignored_paths(
    project_root: str | Path,
    candidates: Iterable[str],
) -> set[str]:
    candidate_list = list(candidates)
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=project_root,
        input="\n".join(candidate_list) + "\n",
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in {0, 1}:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return {line for line in result.stdout.splitlines() if line}


def ignored_required_paths(project_root: str | Path) -> list[str]:
    return sorted(_ignored_paths(project_root, REQUIRED_WORKING_DEMO_PATHS))


def unignored_local_paths(project_root: str | Path) -> list[str]:
    ignored = _ignored_paths(project_root, REQUIRED_LOCAL_ONLY_PATHS)
    return sorted(set(REQUIRED_LOCAL_ONLY_PATHS) - ignored)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the complete runnable working-demo boundary."
    )
    parser.add_argument(
        "--write-build-manifest",
        action="store_true",
        help="Write frontend/dist/build-manifest.json before verification.",
    )
    args = parser.parse_args()
    paths = tracked_paths(PROJECT_ROOT)
    if args.write_build_manifest:
        manifest_relative = "frontend/dist/build-manifest.json"
        manifest_path = PROJECT_ROOT / manifest_relative
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                create_frontend_build_manifest(PROJECT_ROOT, paths),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        paths = sorted({*paths, manifest_relative})
    violations = collect_delivery_violations(PROJECT_ROOT, paths)
    violations.extend(
        f"required working-demo path is ignored: {path}"
        for path in ignored_required_paths(PROJECT_ROOT)
    )
    violations.extend(
        f"local-only path is not ignored: {path}"
        for path in unignored_local_paths(PROJECT_ROOT)
    )
    violations = sorted(set(violations))
    if violations:
        for violation in violations:
            print(f"FAIL: {violation}")
        return 1
    print("PASS: working-demo is complete, runnable, and internally consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
