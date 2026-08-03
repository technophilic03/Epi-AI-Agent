#!/usr/bin/env python3
"""Run the real FastAPI + TypeScript study-neutral dataset-plan smoke.

The smoke intentionally uses the installed study, configured model, runtime
catalog, DuckDB, DB-RAG tools, FastAPI, and Vite. It verifies the plan review
contract and leaves any subsequent SQL/extraction outcome as diagnostics.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import os
import sys
import time
import traceback
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.env_loader import load_app_environment
import scripts.e2e_fastapi_typescript_full_chain_real as harness


FRONTEND_DIR = REPO_ROOT / "frontend"
DEFAULT_ARTIFACT_DIR = "/tmp/report-fastapi-typescript-study-neutral-plan-smoke"
DEFAULT_QUERY = (
    "Create a filtered extraction for index cases with final loss to follow-up "
    "outcome, age, and sex, joining Baseline Clinical and Demographic Information "
    "Cohort A to Final Outcome Determination Cohort A by SUBJID. Keep only Male "
    "participants."
)
MESSAGE_LABEL = "Ask a question about your dataset!"
MAX_TIMEOUT_SECONDS = 300.0


def _log(message: str) -> None:
    print(f"[study-neutral-plan-smoke] {message}", flush=True)


def _bounded_timeout(value: str) -> float:
    try:
        timeout = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be a number") from exc
    if timeout <= 0 or timeout > MAX_TIMEOUT_SECONDS:
        raise argparse.ArgumentTypeError("timeout must be between 0 and 300 seconds")
    return timeout


def _remaining_ms(deadline: float, *, cap_ms: int = 30_000) -> int:
    return max(1, min(cap_ms, int(max(0.0, deadline - time.monotonic()) * 1000)))


def _page_text(page: Any) -> str:
    return harness._page_text(page)


def _fetch_export(page: Any, ui_url: str) -> dict[str, Any] | None:
    return harness._fetch_thread_export(page, ui_url)


def _find_catalog_summary(exported: dict[str, Any]) -> dict[str, Any] | None:
    for record in dict(dict(exported.get("artifacts") or {}).get("files") or {}).values():
        if not isinstance(record, dict) or record.get("kind") != "catalog_search":
            continue
        stored = record.get("content")
        content = (
            stored.get("content")
            if isinstance(stored, dict) and isinstance(stored.get("content"), dict)
            else stored
        )
        if isinstance(content, dict) and isinstance(content.get("retrieval_summary"), dict):
            return dict(content["retrieval_summary"])
    return None


def _approved_plan(exported: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for record in dict(dict(exported.get("artifacts") or {}).get("files") or {}).values():
        if not isinstance(record, dict) or record.get("kind") != "dataset_plan":
            continue
        stored = record.get("content")
        if not isinstance(stored, dict) or stored.get("status") != "approved":
            continue
        provenance = dict(stored.get("provenance") or {})
        if provenance.get("review_action") == "approve_selected_plan":
            content = stored.get("content")
            if isinstance(content, dict):
                candidates.append(content)
    return candidates[-1] if candidates else None


def _plan_review_state(exported: dict[str, Any]) -> dict[str, Any] | None:
    interrupt = exported.get("active_interrupt")
    if not isinstance(interrupt, dict) or interrupt.get("type") != "dataset_plan_review":
        return None
    return interrupt


def _wait_for_plan_review(page: Any, ui_url: str, *, deadline: float) -> tuple[dict[str, Any], dict[str, Any]]:
    last_body = ""
    while time.monotonic() < deadline:
        last_body = _page_text(page)
        exported = _fetch_export(page, ui_url)
        interrupt = _plan_review_state(exported or {}) if exported else None
        if (
            interrupt is not None
            and "Review dataset plan" in last_body
            and page.get_by_role("button", name="Approve plan and extract").count() > 0
        ):
            return exported, interrupt
        time.sleep(0.5)
    raise AssertionError(
        "Timed out waiting for dataset_plan_review. "
        f"Last page text excerpt:\n{last_body[-4000:]}"
    )


def _assert_review_view(interrupt: dict[str, Any]) -> list[str]:
    view = dict(interrupt.get("view") or {})
    groups = list(view.get("concept_groups") or [])
    if not groups:
        raise AssertionError("Dataset-plan review rendered no concept groups.")
    required = list(view.get("required_fields") or [])
    filters = list(view.get("filters") or [])
    joins = list(view.get("joins") or [])
    if not required:
        raise AssertionError("Dataset-plan review rendered no required identifier.")
    if not filters:
        raise AssertionError("Dataset-plan review rendered no filter values.")
    if not joins:
        raise AssertionError("Dataset-plan review rendered no join information.")
    requested_keys = [
        str(column.get("key") or "")
        for group in groups
        for column in list(dict(group).get("columns") or [])
        if isinstance(column, dict)
        and list(column.get("roles") or []) == ["requested"]
        and str(column.get("key") or "")
    ]
    if len(requested_keys) < 2:
        raise AssertionError("Dataset-plan review rendered fewer than two requested fields.")
    return requested_keys


def _approve_one_unchecked_field(page: Any, requested_keys: list[str], *, deadline: float) -> str:
    checkbox = page.get_by_role("checkbox").first
    checkbox.wait_for(state="visible", timeout=_remaining_ms(deadline))
    label = str(checkbox.get_attribute("aria-label") or "")
    if not label:
        raise AssertionError("Requested field checkbox did not expose an aria-label.")
    checkbox.uncheck(timeout=_remaining_ms(deadline))
    if checkbox.is_checked():
        raise AssertionError("Requested field checkbox remained checked after unchecking.")
    if not page.get_by_role("button", name="Approve plan and extract").is_enabled(
        timeout=_remaining_ms(deadline)
    ):
        raise AssertionError("Plan approval became disabled after unchecking one field.")
    return label


def _run_browser_flow(args: argparse.Namespace, *, artifact_dir: Path, ui_url: str) -> None:
    from playwright.sync_api import sync_playwright

    deadline = time.monotonic() + args.timeout_seconds
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headful)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        try:
            page.goto(ui_url, wait_until="domcontentloaded", timeout=_remaining_ms(deadline))
            page.get_by_role("heading", name="AI Agent for RePORT").wait_for(
                timeout=_remaining_ms(deadline)
            )
            page.get_by_role("region", name="Conversation", exact=True).wait_for(
                timeout=_remaining_ms(deadline)
            )
            harness._submit_chat_message(page, args.query, deadline=deadline)
            exported, interrupt = _wait_for_plan_review(page, ui_url, deadline=deadline)
            summary = _find_catalog_summary(exported)
            if not summary or not summary.get("probes"):
                raise AssertionError("No catalog retrieval_summary with per-probe counts was stored.")
            if not all(
                "unique_table_count" in probe and "unique_column_count" in probe
                for probe in summary["probes"]
                if isinstance(probe, dict)
            ):
                raise AssertionError("Catalog retrieval summary omitted per-probe breadth counts.")
            requested_keys = _assert_review_view(interrupt)
            selected_column_keys = list(requested_keys)
            initial_interrupt_count = int(
                dict(exported.get("diagnostics") or {}).get("interrupt_count") or 0
            )
            unchecked_label = _approve_one_unchecked_field(
                page, requested_keys, deadline=deadline
            )
            if not harness._click_button_when_enabled(
                page, "Approve plan and extract", deadline=deadline
            ):
                raise AssertionError("Approve plan and extract did not become clickable.")
            _log(f"approved plan after unchecking {unchecked_label}")

            approved = None
            saw_second_plan_review = False
            last_export = exported
            while time.monotonic() < deadline:
                body = _page_text(page)
                current = _fetch_export(page, ui_url)
                if current:
                    last_export = current
                    if _plan_review_state(current) is not None:
                        saw_second_plan_review = True
                    approved = _approved_plan(current) or approved
                if "Review DB-RAG SQL before execution" in body:
                    if not harness._click_button_when_enabled(
                        page, "Approve & Run", deadline=deadline
                    ):
                        raise AssertionError("Approve & Run did not become clickable.")
                    continue
                if approved is not None and "Review dataset plan" not in body and (
                    "Agent is working" not in body
                    or dict(last_export.get("run") or {}).get("state") in {"error", "done", "timeout"}
                ):
                    break
                time.sleep(0.5)
            if approved is None:
                raise AssertionError("No approved selected dataset plan was stored after approval.")
            if saw_second_plan_review:
                raise AssertionError("Approval triggered a second dataset-plan review.")
            if initial_interrupt_count < 1:
                raise AssertionError("Initial plan review did not register an interrupt.")
            approved_keys = {
                f"{field.get('source')}::{field.get('table')}::{field.get('column')}"
                for concept in list(approved.get("concepts") or [])
                for field in list(dict(concept).get("fields") or [])
                if isinstance(field, dict)
            }
            if len(approved_keys) != len(selected_column_keys) - 1:
                raise AssertionError(
                    "Approved plan did not contain exactly the selected requested fields. "
                    f"expected={len(selected_column_keys) - 1} actual={len(approved_keys)}"
                )
            if not approved.get("required_fields"):
                raise AssertionError("Approved selected plan lost required identifiers.")
            if not approved.get("filters"):
                raise AssertionError("Approved selected plan lost reviewed filters.")
            (artifact_dir / "final-page-text.txt").write_text(_page_text(page), encoding="utf-8")
            export_path = harness._write_thread_export(page, artifact_dir, ui_url)
            if export_path:
                _log(f"wrote thread export to {export_path}")
            page.screenshot(path=str(artifact_dir / "final-screenshot.png"), full_page=True)
        except Exception as exc:
            diagnostics = harness._write_failure_diagnostics(
                page, artifact_dir, exc, ui_url=ui_url
            )
            raise AssertionError(f"{type(exc).__name__}: {exc}\n{diagnostics}") from exc
        finally:
            browser.close()


def run(args: argparse.Namespace) -> int:
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    load_app_environment(REPO_ROOT)
    host = "127.0.0.1"
    try:
        api_port = harness._find_available_port(host, args.api_port)
        ui_port = harness._find_available_port(host, args.ui_port)
    except Exception:
        (artifact_dir / "failure-traceback.txt").write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )
        raise
    api_url = f"http://{host}:{api_port}"
    ui_url = f"http://{host}:{ui_port}"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["REPORT_AGENT_API_WORKFLOW_TIMEOUT_SECONDS"] = str(args.timeout_seconds)
    env["VITE_API_BASE"] = api_url
    api_process = None
    vite_process = None
    try:
        api_process = harness._start_process(
            name="api",
            args=[
                str(REPO_ROOT / ".venv/bin/python"),
                "-m",
                "uvicorn",
                "api.app:app",
                "--host",
                host,
                "--port",
                str(api_port),
            ],
            cwd=REPO_ROOT,
            env=env,
            log_path=artifact_dir / "api.log",
        )
        vite_process = harness._start_process(
            name="vite",
            args=[
                "npm",
                "run",
                "dev",
                "--",
                "--port",
                str(ui_port),
                "--strictPort",
            ],
            cwd=FRONTEND_DIR,
            env=env,
            log_path=artifact_dir / "vite.log",
        )
        processes = [api_process, vite_process]
        readiness_deadline = time.monotonic() + min(60.0, args.timeout_seconds)
        harness._wait_for_http(
            f"{api_url}/docs",
            deadline=readiness_deadline,
            name="FastAPI",
            expected_status=200,
            processes=processes,
        )
        harness._wait_for_http(
            ui_url,
            deadline=readiness_deadline,
            name="Vite",
            expected_status=200,
            processes=processes,
        )
        _run_browser_flow(args, artifact_dir=artifact_dir, ui_url=ui_url)
        print("PASS FastAPI + TypeScript study-neutral dataset-plan smoke", flush=True)
        return 0
    finally:
        harness._terminate_process(vite_process)
        harness._terminate_process(api_process)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the real study-neutral dataset-plan browser smoke."
    )
    parser.add_argument("--api-port", type=int, default=8010)
    parser.add_argument("--ui-port", type=int, default=5173)
    parser.add_argument("--timeout-seconds", type=_bounded_timeout, default=MAX_TIMEOUT_SECONDS)
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--artifact-dir", default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--headful", action="store_true")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
