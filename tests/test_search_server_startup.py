from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEARCH_SERVER = ROOT / "tools" / "search_server.py"


def test_search_server_imports_without_project_root_on_python_path(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy; "
            f"runpy.run_path({str(SEARCH_SERVER)!r}, "
            "run_name='search_server_import_probe')",
        ],
        cwd=tmp_path,
        env={},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
