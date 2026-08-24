#!/usr/bin/env python3
"""Render real model-produced LaTeX through FastAPI and the compiled UI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.auth import LOCAL_SESSION_ID


QUERY = (
    "Give the PDF and CDF of the standard normal distribution. Use LaTeX "
    "with an inline \\(Z \\sim \\mathcal{N}(0,1)\\) statement and display "
    "\\[...\\] equations for both the PDF and CDF."
)
LOCAL_API_HEADERS = {"X-Epi-Session-ID": LOCAL_SESSION_ID}
MESSAGE_LABEL = "Ask a question about your dataset!"


def _launch_browser(playwright: Any) -> Any:
    try:
        return playwright.chromium.launch()
    except Exception as error:
        if "Executable doesn't exist" not in str(error):
            raise
        return playwright.chromium.launch(channel="chrome")


def _find_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
            try:
                candidate.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError("Could not find an available local port.")


def _remaining_ms(deadline: float) -> int:
    return max(1, int((deadline - time.monotonic()) * 1000))


def _wait_for_health(
    api_url: str,
    deadline: float,
    process: subprocess.Popen[Any],
) -> None:
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"FastAPI exited early with code {process.returncode}."
            )
        try:
            response = requests.get(f"{api_url}/api/health", timeout=2)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.25)
    raise TimeoutError("FastAPI did not become ready.")


def _thread_state(api_url: str) -> dict[str, Any]:
    conversations = requests.get(
        f"{api_url}/api/conversations",
        headers=LOCAL_API_HEADERS,
        timeout=5,
    )
    conversations.raise_for_status()
    items = conversations.json().get("items") or []
    if len(items) != 1:
        raise AssertionError(
            f"Expected exactly one conversation, received {items!r}."
        )
    response = requests.get(
        f"{api_url}/api/threads/{items[0]['thread_id']}/state",
        headers=LOCAL_API_HEADERS,
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def _write_failure_diagnostics(
    *,
    artifact_dir: Path,
    api_url: str,
    page: Any | None,
    error: BaseException,
) -> None:
    (artifact_dir / "failure.txt").write_text(
        "".join(traceback.format_exception(error)),
        encoding="utf-8",
    )
    if page is not None:
        try:
            (artifact_dir / "failure-page.txt").write_text(
                page.locator("body").inner_text(),
                encoding="utf-8",
            )
            page.screenshot(
                path=str(artifact_dir / "failure-screenshot.png"),
                full_page=True,
            )
        except Exception:
            pass
    try:
        state = _thread_state(api_url)
        (artifact_dir / "failure-state.json").write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _wait_for_rendered_math(page: Any, deadline: float) -> None:
    assistant = page.locator(".message-assistant .message-body").last
    assistant.wait_for(timeout=_remaining_ms(deadline))
    assistant.locator(".katex").first.wait_for(
        timeout=_remaining_ms(deadline)
    )
    assistant.locator(".katex-display").first.wait_for(
        timeout=_remaining_ms(deadline)
    )
    while time.monotonic() < deadline:
        if page.get_by_label(MESSAGE_LABEL).is_enabled(timeout=500):
            return
        time.sleep(0.25)
    raise AssertionError("Composer did not re-enable after the LaTeX response.")


def run(args: argparse.Namespace) -> int:
    if not 1 <= args.timeout_seconds <= 300:
        raise ValueError("The feature smoke is limited to five minutes.")
    deadline = time.monotonic() + args.timeout_seconds
    artifact_dir = (
        args.artifact_dir.expanduser().resolve()
        if args.artifact_dir
        else Path(tempfile.mkdtemp(prefix="katex-conversation-smoke-"))
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    runtime_root = artifact_dir / "runtime"
    runtime_root.mkdir(parents=True, exist_ok=True)

    from utils.env_loader import load_app_environment

    environment_root = args.environment_root.expanduser().resolve()
    load_app_environment(environment_root)
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise RuntimeError(
            "A real OPENAI_API_KEY is required via the environment or "
            f"{environment_root / '.env'}."
        )
    static_dir = REPO_ROOT / "frontend" / "dist"
    if not (static_dir / "index.html").is_file():
        raise RuntimeError("Build frontend/dist before running this smoke.")

    host = "127.0.0.1"
    port = _find_port(host, args.api_port)
    api_url = f"http://{host}:{port}"
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "REPORT_AGENT_RUNTIME_ROOT": str(runtime_root),
            "REPORT_AGENT_CHECKPOINT_DB_PATH": str(
                runtime_root / "agent_memory_fastapi.db"
            ),
            "REPORT_AGENT_STATIC_DIR": str(static_dir),
            "REPORT_AGENT_STUDY_ROOT": str(environment_root / "study_data"),
        }
    )
    api_log = (artifact_dir / "api.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.app:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT,
        env=environment,
        stdout=api_log,
        stderr=subprocess.STDOUT,
        text=True,
    )

    from playwright.sync_api import sync_playwright

    page: Any | None = None
    try:
        _wait_for_health(api_url, deadline, process)
        with sync_playwright() as playwright:
            browser = _launch_browser(playwright)
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 950})
                page.goto(
                    api_url,
                    wait_until="networkidle",
                    timeout=_remaining_ms(deadline),
                )
                field = page.get_by_label(MESSAGE_LABEL)
                field.wait_for(timeout=_remaining_ms(deadline))
                field.fill(QUERY)
                page.get_by_role("button", name="Send", exact=True).click()
                _wait_for_rendered_math(page, deadline)

                assistant = page.locator(".message-assistant .message-body").last
                if assistant.locator(".katex").count() < 3:
                    raise AssertionError("Expected at least three rendered formulas.")
                if assistant.locator(".katex-display").count() < 2:
                    raise AssertionError("Expected PDF and CDF display equations.")

                state = _thread_state(api_url)
                (artifact_dir / "thread-state.json").write_text(
                    json.dumps(state, indent=2), encoding="utf-8"
                )
                if state.get("run", {}).get("state") != "done":
                    raise AssertionError(f"Unexpected run state: {state['run']!r}")
                assistant_sources = [
                    str(message.get("text") or "")
                    for message in state.get("conversation") or []
                    if message.get("role") == "assistant"
                ]
                if not assistant_sources or not any(
                    "\\[" in text and "\\(" in text for text in assistant_sources
                ):
                    raise AssertionError(
                        "Raw API state did not retain inline and display LaTeX."
                    )

                (artifact_dir / "final-page-text.txt").write_text(
                    page.locator("body").inner_text(), encoding="utf-8"
                )
                page.screenshot(
                    path=str(artifact_dir / "final-screenshot.png"), full_page=True
                )
            finally:
                browser.close()
    except BaseException as error:
        _write_failure_diagnostics(
            artifact_dir=artifact_dir,
            api_url=api_url,
            page=page,
            error=error,
        )
        print(f"FAIL KaTeX conversation smoke; diagnostics: {artifact_dir}")
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        api_log.close()

    print(f"PASS KaTeX conversation smoke; diagnostics: {artifact_dir}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render real model LaTeX through FastAPI and compiled UI."
    )
    parser.add_argument("--api-port", type=int, default=8890)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument(
        "--environment-root",
        type=Path,
        default=REPO_ROOT,
        help="Project root whose .env and study_data should be used.",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(run(_parser().parse_args()))
