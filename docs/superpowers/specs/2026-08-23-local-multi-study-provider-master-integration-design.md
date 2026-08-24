# Local Multi-Study Provider Master Integration Design

## Objective

Integrate `local-multi-study-provider` into local `master` as a release-safe,
local-only application. Preserve the branch's multi-study, provider-neutral,
conversation, retrieval, frontend, and native execution behavior while keeping
Docker, AWS, Cognito, hosted-worker, and browser-managed credential components
out of the resulting `master` tree and history.

The integration also closes every important issue identified by the pre-merge
audit before `master` moves.

## Selected integration strategy

Create an isolated implementation worktree and preparation branch from the
current local `local-multi-study-provider` tip. Make and verify the
release-safety corrections there. Then create a separate finalization worktree
and named branch from the current `master` tip, apply the verified preparation
branch with `git merge --squash`, and commit the complete result as one curated
integration commit. After all gates pass, fast-forward local `master` to that
commit.

This strategy is preferred over a normal fast-forward because the feature
branch contains 411 intermediate commits, including AWS and Docker work that
was later removed. A squash preserves the final feature tree without making
those retired commits reachable from `master`. Cherry-picking individual
commits is rejected because the provider, multi-study, runtime, API, and UI
changes are tightly interdependent.

The remote feature branch is not deleted and no branch is pushed unless the
user separately authorizes those operations.

## Isolation and source-of-truth rules

The existing checkout remains on `local-multi-study-provider`; its `.env`,
runtime data, installed studies, and IDE state are not moved or edited during
integration. A project-local ignored implementation worktree is created for
`integration/local-multi-study-provider-prep` from the feature tip, as
explicitly requested by the user. After that branch passes its gates, a second
project-local ignored worktree is created for
`integration/local-multi-study-provider-master` from `master` solely to build
and validate the final squash commit.

The feature branch is the source of truth for application behavior, API/UI
contracts, provider routing, study routing, retrieval behavior, and tracked
frontend assets. If an unexpected squash conflict occurs, use the feature
version for those areas unless `master` contains a later safety mechanism that
the feature branch accidentally regressed. Every such exception must be
documented and tested. Because `master` is currently the exact merge base of
the feature branch, no content conflict is expected.

The generic `frontend/dist/build-manifest.json` remains tracked. It records
frontend source provenance and is not an AWS deployment component. The older
local-only test and design language that classified it as AWS-only are updated
to match the current project delivery policy.

## Retained product boundary

The result retains:

- native startup through `run_fastapi.py`;
- environment-based OpenAI and Anthropic credentials plus configured compatible
  providers;
- the fixed internal local identity used for conversation and storage scoping;
- multi-study discovery, study packages, catalog relationships, semantic and
  lexical retrieval, and study lineage;
- conversation history, review status, activity, cancellation, attachments,
  artifacts, and datasets;
- native subprocess-based Python analysis;
- the React/TypeScript frontend and its tracked production bundle; and
- the generic frontend build manifest.

The result excludes:

- `.dockerignore`, `Dockerfile`, and `compose.yaml`;
- `infra/aws/**`, `deploy/aws/**`, and `docs/aws/**`;
- AWS provisioning, release, recovery, DNS, installation, and smoke logic;
- Cognito configuration, token verification, and browser authentication;
- hosted Python worker launchers and deployment modes;
- browser-submitted or session-memory provider credential endpoints; and
- active documentation or source references that instruct users to use those
  removed components.

Historical design records that describe how the local-only cleanup was
performed may remain when they are clearly historical and do not act as active
operating instructions. The final reachable `master` commit must not contain
the retired infrastructure files themselves.

## Release-safety corrections

### Local network boundary

`run_fastapi.py` must reject non-loopback bind targets by default. Accepted
targets are loopback names and addresses such as `localhost`, `127.0.0.1`, and
`::1`. This is necessary because the local application assigns every request a
fixed privileged identity and exposes conversations, artifacts, provider-funded
model requests, and native Python execution.

No unauthenticated unsafe override is added as part of this integration. A
future network-hosted mode would require a separate authenticated design.

### Attachment request-body boundary

Restore an ASGI receive-layer limit for attachment routes so an oversized or
chunked multipart request is rejected while the request body is being received,
before FastAPI/Starlette finishes parsing and spooling it. Keep the existing
per-file, aggregate attachment, and declared `Content-Length` checks as
defense-in-depth.

Regression coverage must exercise an oversized request without a trustworthy
`Content-Length` header and verify HTTP 413 behavior.

### Native Python process boundary

Restore the adaptive Linux `RLIMIT_NPROC` calculation from `master`, including
headroom over the invoking user's current task count and a safe fallback.
Restore one-thread limits for OpenBLAS, OpenMP, MKL, NumExpr, and Accelerate so
NumPy/SciPy imports fit inside the process budget. Preserve the feature branch's
cooperative cancellation polling and process-group termination behavior.

Focused tests must cover the adaptive limit and required subprocess environment
variables while retaining cancellation tests.

### Repository and delivery policy

Update the local-only repository guard to permit the generic build manifest
while continuing to forbid Docker, AWS, Cognito, hosted-worker, and
browser-credential artifacts. Align `.gitignore` with the delivery verifier:
required verifier and test sources must not be hidden by blanket ignores, and
`local_data/` must be ignored as local-only user data.

The existing delivery verifier and its focused test must be present in the
integrated tree and pass. Update stale embedding fallback comments to agree
with the implemented lexical fallback. Remove the extra final blank line that
currently makes `git diff --check` fail.

## Error handling and stop conditions

The integration stops before moving `master` if:

- the squash produces an ambiguous conflict not resolved by the source-of-truth
  rules;
- a required Docker/AWS removal would also remove active local functionality;
- any committed Python or frontend test fails;
- the frontend build or build-manifest verifier fails;
- a repository scan finds a retained active infrastructure component;
- an independent reviewer identifies an unresolved critical or important issue;
  or
- verification changes user-owned runtime data or secrets.

If one of these conditions cannot be resolved from the approved design and
existing code, ask the user before continuing.

## Test-driven implementation

Each behavior correction follows red-green-refactor:

1. add or adjust the smallest focused regression test;
2. run it and confirm it fails for the expected missing behavior;
3. implement the minimal correction;
4. rerun the focused tests; and
5. run the broader affected suite before the next correction.

Pure history operations, documentation corrections, generated frontend assets,
and `.gitignore` edits do not require artificial unit tests, but their explicit
verification commands must fail before correction where practical and pass
afterward.

## Verification gates

Before local `master` moves, run and inspect all of the following:

1. focused regression tests for loopback binding, receive-layer upload limits,
   adaptive Python process limits, BLAS thread caps, and the repository boundary;
2. all committed Python tests using Python 3.12;
3. all frontend Vitest tests;
4. `npm --prefix frontend run build`;
5. build-manifest refresh and delivery verification;
6. `python -m pip check` through the Python 3.12 virtual environment;
7. `git diff --check master...HEAD`;
8. tracked-path and active-source scans for Docker, AWS, Cognito, hosted workers,
   and browser-managed provider credentials;
9. a review of the final `master..integration` diff and reachable commit shape;
   and
10. an independent pre-merge code review.

The credentialed browser smoke is a separate gate because it sends application
context to OpenAI and may incur API charges. It is run exactly once only after
the user explicitly approves that external call. If approval is not granted,
the handoff must state that this gate remains unexecuted; local `master` does not
move unless the user explicitly accepts that limitation.

## Final integration and rollback

After verification of the feature-derived preparation branch, squash it into
`integration/local-multi-study-provider-master`, run the final review and
verification there, and create one curated commit on that branch. Recheck that
local `master` still points to the audited base commit, then fast-forward it to
the integration commit and rerun the core verification on the merged result.

Keep the integration worktree and source feature branch until the merged result
passes. Do not delete branches, remove the worktree, push `master`, or delete the
remote feature branch without separate authorization. If the final verification
fails, leave `master` at its original commit and report the failure artifacts.

## Success criteria

The integration is complete only when:

- local `master` contains the intended final feature tree in one new curated
  commit;
- Docker and AWS implementation is absent from the final tree and from the new
  `master` commit's parent history;
- all important pre-merge findings are fixed with focused regression coverage;
- all approved verification gates pass with a clean worktree; and
- no remote branch or user-owned local data was changed.
