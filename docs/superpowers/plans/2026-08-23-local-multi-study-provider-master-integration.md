# Local Multi-Study Provider Master Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate `local-multi-study-provider` into local `master` as one release-safe commit while excluding Docker/AWS history and fixing every important pre-merge audit finding.

**Architecture:** Create an isolated preparation worktree from the local `local-multi-study-provider` tip and apply focused red-green corrections for local network binding, attachment request limits, Python subprocess limits, and repository delivery policy. After that branch passes, create a separate finalization worktree from `master`, squash the prepared feature tree into it, verify and review the complete staged tree, create one curated commit, and fast-forward `master` without moving the user's feature checkout.

**Tech Stack:** Git worktrees, Python 3.12, FastAPI/Starlette ASGI, pytest, React 19, TypeScript, Vitest, Vite, SQLite, LangGraph.

## Global Constraints

- Use `docs/superpowers/specs/2026-08-23-local-multi-study-provider-master-integration-design.md` as the approved specification.
- Keep the primary checkout on `local-multi-study-provider`; do not edit its `.env`, runtime data, installed studies, or IDE state.
- Start the implementation worktree and preparation branch from the current local `local-multi-study-provider` tip, as explicitly requested by the user.
- Start a separate finalization branch from the audited local `master` commit and squash the verified preparation branch into it.
- Treat `local-multi-study-provider` as the source of truth for application behavior, except where this plan restores a later safety guard from `master`.
- Keep `frontend/dist/build-manifest.json`; it is generic frontend provenance, not AWS infrastructure.
- Do not retain `.dockerignore`, `Dockerfile`, `compose.yaml`, `infra/aws/**`, `deploy/aws/**`, `docs/aws/**`, Cognito, hosted workers, or browser-managed credential endpoints in the final tree.
- Use `.venv/bin/python` from the Python 3.12 environment; never use the system `python3`.
- Follow red-green-refactor for every production behavior correction.
- Commit focused correction checkpoints on the feature-derived preparation branch; the final `master` branch still receives exactly one squashed integration commit.
- Do not push, delete branches, delete worktrees, or move remote refs.
- Run the credentialed browser smoke exactly once only after separate explicit user approval.

---

### Task 1: Create the feature-derived implementation workspace

**Files:**
- No tracked file changes beyond the squash result.
- Create ignored worktree: `.worktrees/local-multi-study-provider-prep/`
- Create branch: `integration/local-multi-study-provider-prep`

**Interfaces:**
- Consumes: local `master`; local `local-multi-study-provider` including the approved design and this plan.
- Produces: one isolated worktree at the exact local feature tip, ready for focused corrections without moving the user's checkout.

- [ ] **Step 1: Verify source state and worktree isolation prerequisites**

Run in the primary checkout:

```bash
git status --short --branch
git rev-parse master local-multi-study-provider
git merge-base master local-multi-study-provider
git rev-list --left-right --count master...local-multi-study-provider
git check-ignore -q .worktrees
git worktree list --porcelain
```

Expected:

- the primary checkout is clean on `local-multi-study-provider`;
- `master` is the merge base;
- the feature branch is ahead and `master` is not ahead;
- `.worktrees` is ignored; and
- neither planned preparation worktree branch/path already exists.

- [ ] **Step 2: Create the implementation worktree from the feature tip**

Run:

```bash
git worktree add .worktrees/local-multi-study-provider-prep \
  -b integration/local-multi-study-provider-prep \
  local-multi-study-provider
```

Expected: a new named worktree on `integration/local-multi-study-provider-prep`, initially equal to the current local `local-multi-study-provider` tip.

- [ ] **Step 3: Make local dependencies available without copying secrets**

Inside the integration worktree, create ignored dependency links to the primary checkout:

```bash
ln -s ../../.venv .venv
ln -s ../../../frontend/node_modules frontend/node_modules
.venv/bin/python --version
npm --prefix frontend --version
```

Expected: Python reports `3.12.x`; npm runs without installing or copying `.env`.

- [ ] **Step 4: Verify the feature-derived baseline and reproduce the known gate**

Run on the feature-derived baseline:

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run build
git status --short --branch
git ls-files -z 'tests/test_*.py' | xargs -0 .venv/bin/python -m pytest -q
```

Expected: all 21 frontend test files pass and the production build exits 0.
The committed Python suite reproduces the already audited single failure in
`tests/test_local_only_repository.py` because the old contract forbids the
generic build manifest; all other committed Python tests pass. The user has
already approved fixing that known baseline failure. Any additional failure is
a new blocker and requires investigation before continuing.

- [ ] **Step 5: Prove the feature tree already excludes infrastructure**

Run:

```bash
test ! -e .dockerignore
test ! -e Dockerfile
test ! -e compose.yaml
test ! -e infra/aws
test ! -e deploy/aws
test ! -e docs/aws
git status --short --branch
```

Expected: every `test` exits 0 and the preparation worktree is clean apart from ignored dependency links.

---

### Task 2: Align the local-only repository and delivery contract

**Files:**
- Modify: `.gitignore:19-39`
- Modify: `tests/test_local_only_repository.py:5-17`
- Create: `tests/test_working_demo_delivery.py`
- Create: `scripts/verify_working_demo_delivery.py`
- Modify: `docs/superpowers/specs/2026-08-21-local-only-branch-cleanup-design.md`
- Modify: `docs/superpowers/plans/2026-08-21-local-only-branch-cleanup.md`
- Modify: `docs/superpowers/specs/2026-08-19-public-readme-study-installation-design.md:71`
- Modify: `config/app.env:19-21`

**Interfaces:**
- Consumes: tracked frontend sources, `frontend/dist/**`, `.env.example`, `requirements.txt`, and Git's tracked/ignored path state.
- Produces: `scripts.verify_working_demo_delivery` with `tracked_paths`, `collect_delivery_violations`, `ignored_required_paths`, and `unignored_local_paths`; a local-only guard that permits the generic manifest.

- [ ] **Step 1: Correct the repository-boundary assertion and verify green**

Remove only `"frontend/dist/build-manifest.json",` from `FORBIDDEN_PATHS` in `tests/test_local_only_repository.py`. Keep every Docker/AWS path and every forbidden hosted-feature token.

Run:

```bash
.venv/bin/python -m pytest tests/test_local_only_repository.py -q
```

Expected: both tests PASS. The previous red failure proves this policy correction changes the intended assertion.

- [ ] **Step 2: Materialize the existing delivery verifier asset**

Use `apply_patch` to add the existing verifier from the primary checkout at
`/Users/xutaowang/Desktop/RA work/Epi-Agent/Epi-AI-Agent/scripts/verify_working_demo_delivery.py`
to the same relative path in the integration worktree, byte-for-byte. This is a
pre-existing workspace verifier, not a new implementation.

Run:

```bash
shasum -a 256 scripts/verify_working_demo_delivery.py
```

Expected SHA-256:

```text
9c0bcc85d593ca3744150bfcb8c13d46df5a56c1f9cdb143b544f6e13e9e0446
```

- [ ] **Step 3: Write the failing focused delivery test**

Create `tests/test_working_demo_delivery.py`:

```python
from pathlib import Path

from scripts.verify_working_demo_delivery import (
    collect_delivery_violations,
    ignored_required_paths,
    tracked_paths,
    unignored_local_paths,
)


ROOT = Path(__file__).parents[1]


def test_working_demo_delivery_contract_is_consistent() -> None:
    paths = tracked_paths(ROOT)
    assert collect_delivery_violations(ROOT, paths) == []
    assert ignored_required_paths(ROOT) == []
    assert unignored_local_paths(ROOT) == []
```

- [ ] **Step 4: Run the delivery test and confirm the policy mismatch**

Run:

```bash
.venv/bin/python -m pytest tests/test_working_demo_delivery.py -q
```

Expected: FAIL because `.gitignore` hides required `scripts/` and `tests/` paths and does not ignore `local_data/`.

- [ ] **Step 5: Correct `.gitignore` at the source**

Change the local/generated section from:

```gitignore
# Local-only development and generated content.
scripts/
tests/
runtime/
```

to:

```gitignore
# Local-only generated content.
runtime/
local_data/
```

Keep `.venv/`, `frontend/node_modules/`, `.worktrees/`, `study_data/`, and other existing local-data rules unchanged. Tests and scripts are source code and must not be hidden by blanket ignores.

- [ ] **Step 6: Update stale documentation and fallback wording**

Make these exact policy corrections:

- in `docs/superpowers/specs/2026-08-21-local-only-branch-cleanup-design.md`, replace the acceptance statement that removes the AWS-only build manifest with a statement that the generic manifest is retained and refreshed after the production build;
- in `docs/superpowers/plans/2026-08-21-local-only-branch-cleanup.md`, mark the old manifest-removal constraint as superseded by the provider integration's generic delivery policy;
- remove the extra empty final line from `docs/superpowers/specs/2026-08-19-public-readme-study-installation-design.md`; and
- replace `config/app.env:19-21` with:

```text
# DB-RAG semantic search uses the configured embedding profile. When its
# provider is unavailable, retrieval falls back to lexical matching so the
# agent can continue database extraction with reduced search quality.
```

- [ ] **Step 7: Stage and verify the delivery contract**

Run:

```bash
git add -A
.venv/bin/python -m pytest tests/test_local_only_repository.py tests/test_working_demo_delivery.py -q
.venv/bin/python scripts/verify_working_demo_delivery.py
git diff --cached --check
```

Expected: focused tests PASS, the verifier prints `PASS: working-demo is complete, runnable, and internally consistent`, and the staged diff has no whitespace errors.

- [ ] **Step 8: Commit the repository-policy checkpoint**

Run:

```bash
git commit -m "fix: align local delivery policy"
```

Expected: the preparation branch records only the Task 2 policy, verifier,
documentation, and test changes.

---

### Task 3: Enforce loopback-only native startup

**Files:**
- Modify: `run_fastapi.py:3-12,352-363`
- Modify: `tests/test_run_fastapi.py:190-215,640-670`

**Interfaces:**
- Consumes: the `--host` argument string.
- Produces: `_loopback_host(value: str) -> str`, used as the `argparse` type converter for `--host`.

- [ ] **Step 1: Write focused loopback acceptance and rejection tests**

Add to `tests/test_run_fastapi.py`:

```python
@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_parse_args_accepts_loopback_hosts(host: str) -> None:
    assert parse_args(["--host", host]).host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.20", "example.com"])
def test_parse_args_rejects_non_loopback_hosts(host: str) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--host", host])
```

Change the existing lazy-import and `main` happy-path tests to use `127.0.0.1` instead of `0.0.0.0`, including their expected uvicorn event strings.

- [ ] **Step 2: Run the rejection test and confirm red**

Run:

```bash
.venv/bin/python -m pytest tests/test_run_fastapi.py::test_parse_args_rejects_non_loopback_hosts -q
```

Expected: FAIL because the parser currently accepts at least `0.0.0.0`.

- [ ] **Step 3: Implement the minimal loopback parser**

Import `ip_address` from `ipaddress` and add before `parse_args`:

```python
def _loopback_host(value: str) -> str:
    host = value.strip()
    if host.casefold() == "localhost":
        return host
    try:
        address = ip_address(host)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--host must be localhost or a loopback IP address"
        ) from exc
    if not address.is_loopback:
        raise argparse.ArgumentTypeError(
            "--host must be localhost or a loopback IP address"
        )
    return host
```

Change the argument declaration to:

```python
parser.add_argument("--host", type=_loopback_host, default="127.0.0.1")
```

- [ ] **Step 4: Run focused and complete startup tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_run_fastapi.py -q
```

Expected: all startup tests PASS, including lazy API imports and the uvicorn invocation contract.

- [ ] **Step 5: Stage and inspect the network-boundary change**

Run:

```bash
git add run_fastapi.py tests/test_run_fastapi.py
git diff --cached --check
git diff --cached -- run_fastapi.py tests/test_run_fastapi.py
```

Expected: only loopback validation and corresponding test updates appear.

- [ ] **Step 6: Commit the loopback-boundary checkpoint**

Run:

```bash
git commit -m "fix: restrict local server binding"
```

Expected: the preparation branch records the tested loopback-only startup
change independently.

---

### Task 4: Restore receive-layer attachment request limits

**Files:**
- Modify: `api/server.py:1-130`
- Modify: `tests/test_api_server.py:1-20,730-870`

**Interfaces:**
- Consumes: ASGI `scope`, `receive`, and `send` for POST paths ending in `/attachments`.
- Produces: `AttachmentRequestBodyLimitMiddleware(app: Any, max_bytes: int)`, returning HTTP 413 before multipart parsing when received bytes exceed the configured request limit.

- [ ] **Step 1: Write a failing chunked-body middleware regression test**

Add `import asyncio`, add `from api import server`, and keep the existing `create_app` import. Add:

```python
def test_attachment_body_limiter_rejects_chunked_body_without_content_length() -> None:
    sent: list[dict] = []
    messages = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"def", "more_body": False},
    ]

    async def receive() -> dict:
        return messages.pop(0)

    async def send(message: dict) -> None:
        sent.append(message)

    async def downstream(scope, receive_limited, send_tracked) -> None:
        del scope, send_tracked
        while True:
            message = await receive_limited()
            if not message.get("more_body"):
                return

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/threads/thread-1/attachments",
        "headers": [],
    }
    middleware = server.AttachmentRequestBodyLimitMiddleware(
        downstream,
        max_bytes=4,
    )

    asyncio.run(middleware(scope, receive, send))

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413
```

- [ ] **Step 2: Run the new test and confirm red**

Run:

```bash
.venv/bin/python -m pytest tests/test_api_server.py::test_attachment_body_limiter_rejects_chunked_body_without_content_length -q
```

Expected: FAIL because `api.server.AttachmentRequestBodyLimitMiddleware` does not exist.

- [ ] **Step 3: Restore the proven ASGI limiter from `master`**

In `api/server.py`:

- import `JSONResponse` alongside `FileResponse`;
- add `_RequestBodyTooLarge(Exception)`;
- restore `AttachmentRequestBodyLimitMiddleware` exactly from `master:api/server.py`, including declared-length rejection, byte counting inside `limited_receive`, response-start tracking, and HTTP 413 JSON responses; and
- before adding `CORSMiddleware` in `create_app`, add:

```python
app.add_middleware(
    AttachmentRequestBodyLimitMiddleware,
    max_bytes=(
        attachment_limits.max_message_bytes
        + _MULTIPART_OVERHEAD_BYTES
    ),
)
```

Do not remove the endpoint's existing `Content-Length`, per-file, or aggregate checks.

- [ ] **Step 4: Run middleware and attachment-route coverage**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_api_server.py::test_attachment_body_limiter_rejects_chunked_body_without_content_length \
  tests/test_api_server.py::test_attachment_upload_rejects_oversized_file_before_runtime_staging \
  tests/test_api_server.py::test_attachment_upload_rejects_aggregate_and_count_limits -q
.venv/bin/python -m pytest tests/test_api_server.py -q
```

Expected: all focused tests and the complete API server suite PASS.

- [ ] **Step 5: Stage and inspect the request-boundary change**

Run:

```bash
git add api/server.py tests/test_api_server.py
git diff --cached --check
git diff --cached -- api/server.py tests/test_api_server.py
```

Expected: the diff restores the receive-layer limiter without changing unrelated routes.

- [ ] **Step 6: Commit the upload-boundary checkpoint**

Run:

```bash
git commit -m "fix: bound attachment request bodies"
```

Expected: the preparation branch records the tested ASGI request limiter
independently.

---

### Task 5: Restore robust native Python process limits

**Files:**
- Modify: `epi_agent/runtimes/python/local_process.py:25-125,300-320`
- Modify: `tests/test_epi_python_runtime.py:1-110`

**Interfaces:**
- Consumes: current Linux user task count, timeout, memory limit, and allowlisted parent environment.
- Produces: `_nproc_limit() -> int`, adaptive `RLIMIT_NPROC`, and one-thread BLAS/OpenMP environment controls while preserving cancellation polling.

- [ ] **Step 1: Write the failing adaptive-limit test**

Add to `tests/test_epi_python_runtime.py`:

```python
def test_python_runtime_uses_adaptive_nproc_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_process, "_nproc_limit", lambda: 384, raising=False)

    limits = {
        name: (soft, hard)
        for name, soft, hard in local_process._resource_limit_specs(
            timeout_seconds=60,
            memory_limit_bytes=None,
            platform_name="linux",
        )
    }

    assert limits["RLIMIT_NPROC"] == (384, 384)
```

- [ ] **Step 2: Extend the native-worker test with thread-pool assertions**

After obtaining `environment` in `test_python_runtime_uses_native_worker`, add:

```python
    assert {
        name: environment[name]
        for name in (
            "OPENBLAS_NUM_THREADS",
            "OMP_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_NUM_THREADS",
            "VECLIB_MAXIMUM_THREADS",
        )
    } == {
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "VECLIB_MAXIMUM_THREADS": "1",
    }
```

- [ ] **Step 3: Run both tests and confirm red**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_epi_python_runtime.py::test_python_runtime_uses_adaptive_nproc_limit \
  tests/test_epi_python_runtime.py::test_python_runtime_uses_native_worker -q
```

Expected: FAIL because `_resource_limit_specs` still hardcodes 64 and the subprocess environment lacks the five thread caps.

- [ ] **Step 4: Restore adaptive limits while preserving cancellation**

Restore these constants and `_nproc_limit()` exactly from `master:epi_agent/runtimes/python/local_process.py`:

```python
_NPROC_HEADROOM = 128
_NPROC_FLOOR = 256
_NPROC_FALLBACK = 4096
```

Use `nproc = _nproc_limit()` and `("RLIMIT_NPROC", nproc, nproc)` in `_resource_limit_specs`. Keep the feature branch's `RunCancelled`, `cancellation_point`, 0.1-second communicate polling, and process-group termination unchanged.

Add these entries to the child environment:

```python
"OPENBLAS_NUM_THREADS": "1",
"OMP_NUM_THREADS": "1",
"MKL_NUM_THREADS": "1",
"NUMEXPR_NUM_THREADS": "1",
"VECLIB_MAXIMUM_THREADS": "1",
```

- [ ] **Step 5: Run native execution and cancellation coverage**

Run:

```bash
.venv/bin/python -m pytest tests/test_epi_python_runtime.py tests/test_run_cancellation.py tests/test_cancellation_boundaries.py -q
```

Expected: all tests PASS; adaptive process limits, thread caps, and cooperative cancellation coexist.

- [ ] **Step 6: Stage and inspect the subprocess-boundary change**

Run:

```bash
git add epi_agent/runtimes/python/local_process.py tests/test_epi_python_runtime.py
git diff --cached --check
git diff --cached -- epi_agent/runtimes/python/local_process.py tests/test_epi_python_runtime.py
```

Expected: the diff restores only the proven resource safeguards and retains cancellation logic.

- [ ] **Step 7: Commit the subprocess-boundary checkpoint**

Run:

```bash
git commit -m "fix: restore robust python process limits"
```

Expected: the preparation branch records the tested process-limit and thread-cap
correction independently.

---

### Task 6: Verify the prepared branch, create the clean squash commit, and fast-forward local `master`

**Files:**
- Regenerate on preparation branch: `frontend/dist/index.html`
- Regenerate on preparation branch: `frontend/dist/assets/**`
- Refresh on preparation branch: `frontend/dist/build-manifest.json`
- Create ignored finalization worktree: `.worktrees/local-multi-study-provider-master/`
- Create branch: `integration/local-multi-study-provider-master`
- Commit: one complete squashed integration tree over `master`
- Create ignored validation worktree: `.worktrees/master-merge-validation/`

**Interfaces:**
- Consumes: verified `integration/local-multi-study-provider-prep`, local `master`, and the approved external-smoke decision.
- Produces: one reviewed commit whose only parent is the audited `master`, followed by a verified local fast-forward of `master`.

- [ ] **Step 1: Rebuild and verify the feature-derived preparation branch**

Run in `.worktrees/local-multi-study-provider-prep`:

```bash
npm --prefix frontend test -- --run
npm --prefix frontend run build
.venv/bin/python scripts/verify_working_demo_delivery.py --write-build-manifest
git add -A
.venv/bin/python scripts/verify_working_demo_delivery.py
git ls-files -z 'tests/test_*.py' | xargs -0 .venv/bin/python -m pytest -q
.venv/bin/python -m pip check
git diff --cached --check
```

Expected: frontend and committed Python suites pass, TypeScript/Vite exits 0,
the delivery verifier prints PASS, pip reports no broken requirements, and the
staged refreshed manifest has no whitespace errors.

- [ ] **Step 2: Commit any reproducible build-manifest refresh**

If Step 1 changed the tracked manifest timestamp or built assets, run:

```bash
git commit -m "build: refresh verified frontend delivery"
```

If `git status --short` is empty, record that the existing bundle and manifest
were already reproducible and do not create an empty commit.

- [ ] **Step 3: Run preparation-branch boundary scans**

Run:

```bash
! git ls-files | rg '^(\.dockerignore|Dockerfile|compose\.yaml|infra/aws/|deploy/aws/|docs/aws/)'
! rg -n \
  'CognitoTokenVerifier|REPORT_AGENT_AUTH_MODE|REPORT_AGENT_AWS_|REPORT_AGENT_COGNITO_|REPORT_AGENT_PYTHON_WORKER_LAUNCHER|/api/session/provider-key' \
  api frontend/src scripts
! rg -n -i 'docker|cognito|infra/aws|deploy/aws|docs/aws' README.md docs/working-demo.md config
git status --short --branch
```

Expected: no tracked infrastructure paths, no active hosted-feature source or
user-documentation references, and a clean preparation branch.

- [ ] **Step 4: Create the finalization worktree from `master`**

From the primary checkout run:

```bash
git worktree add .worktrees/local-multi-study-provider-master \
  -b integration/local-multi-study-provider-master \
  master
ln -s ../../.venv .worktrees/local-multi-study-provider-master/.venv
ln -s ../../../frontend/node_modules \
  .worktrees/local-multi-study-provider-master/frontend/node_modules
```

Expected: a second isolated worktree whose `HEAD` equals the audited `master`.

- [ ] **Step 5: Squash the verified preparation branch into the finalization worktree**

Run in `.worktrees/local-multi-study-provider-master`:

```bash
git merge --squash integration/local-multi-study-provider-prep
git status --short
git diff --cached --stat master
```

Expected: the squash applies without conflicts because `master` is an ancestor
of the preparation branch. Do not commit. If an unexpected conflict appears,
use the prepared feature version for application/API/UI behavior and stop for
user input if a later `master` safety guard makes the correct result ambiguous.

- [ ] **Step 6: Verify the complete staged final tree**

Run:

```bash
git ls-files -z 'tests/test_*.py' | xargs -0 .venv/bin/python -m pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
.venv/bin/python scripts/verify_working_demo_delivery.py
.venv/bin/python -m pip check
git diff --cached --check
! git ls-files | rg '^(\.dockerignore|Dockerfile|compose\.yaml|infra/aws/|deploy/aws/|docs/aws/)'
! rg -n \
  'CognitoTokenVerifier|REPORT_AGENT_AUTH_MODE|REPORT_AGENT_AWS_|REPORT_AGENT_COGNITO_|REPORT_AGENT_PYTHON_WORKER_LAUNCHER|/api/session/provider-key' \
  api frontend/src scripts
```

Expected: every suite and delivery gate passes, dependency state is consistent,
and no Docker/AWS/hosted implementation remains in the staged final tree.

- [ ] **Step 7: Prove the curated history shape before commit**

Run:

```bash
git rev-parse HEAD master
git diff --cached --stat master
git log --oneline --decorate --max-count=3
```

Expected: finalization `HEAD` still equals `master`; the entire prepared feature
is one staged tree diff, so its intermediate history will not become reachable
from the final commit.

- [ ] **Step 8: Request independent review of the complete staged tree**

Dispatch a read-only reviewer with:

- base: `master`;
- work product: the staged finalization diff plus working-tree state;
- requirements: the approved design and this plan;
- focus: Docker/AWS removal, loopback security, upload resource bounds,
  subprocess isolation, provider/study behavior, API/frontend contracts, and
  test/build evidence.

Expected: no unresolved Critical or Important findings. Fix a substantiated
finding first on the preparation branch with a focused red-green test, then
repeat Steps 1-8 so the final squash remains reproducible.

- [ ] **Step 9: Create the single curated integration commit**

Run only after all finalization gates and review pass:

```bash
git commit -m "feat: integrate local multi-study provider"
git rev-list --count master..HEAD
git rev-list --parents --max-count=1 HEAD
git status --short --branch
```

Expected: the count is exactly `1`, the new commit has exactly one parent
(`master`), and the finalization worktree is clean.

- [ ] **Step 10: Resolve the credentialed smoke gate with the user**

Ask for explicit approval to run exactly once:

```bash
.venv/bin/python scripts/smoke_awaiting_review_badge_sync_real.py \
  --timeout-seconds 300 \
  --environment-root '/Users/xutaowang/Desktop/RA work/Epi-Agent/Epi-AI-Agent'
```

Explain that the smoke sends application context to OpenAI using the configured
key and may incur API charges. If approved, run it once and preserve its
reported artifact directory. On failure or timeout, do not rerun automatically
and do not move `master`. If approval is declined, obtain explicit acceptance
of the unexecuted smoke before moving `master`.

- [ ] **Step 11: Create a separate `master` validation worktree and fast-forward**

From the primary checkout, after the smoke gate is resolved:

```bash
git worktree add .worktrees/master-merge-validation master
git -C .worktrees/master-merge-validation merge --ff-only \
  integration/local-multi-study-provider-master
ln -s ../../.venv .worktrees/master-merge-validation/.venv
ln -s ../../../frontend/node_modules \
  .worktrees/master-merge-validation/frontend/node_modules
```

Expected: `master` fast-forwards by exactly one commit; the primary checkout
remains on `local-multi-study-provider`.

- [ ] **Step 12: Verify the merged `master` result fresh**

Run in `.worktrees/master-merge-validation`:

```bash
git ls-files -z 'tests/test_*.py' | xargs -0 .venv/bin/python -m pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
.venv/bin/python scripts/verify_working_demo_delivery.py
git diff --check HEAD^..HEAD
git status --short --branch
```

Expected: Python and frontend suites pass, production build and delivery
verifier pass, the integration commit has no whitespace errors, and `master`
is clean.

- [ ] **Step 13: Preserve recovery state and report**

Leave all worktrees and source/preparation/finalization branches in place.
Report:

- old and new `master` SHAs;
- the one integration commit SHA;
- exact Python/frontend test counts;
- build, verifier, dependency, scan, and review results;
- credentialed smoke result or the user's explicit accepted waiver; and
- confirmation that nothing was pushed or deleted.
