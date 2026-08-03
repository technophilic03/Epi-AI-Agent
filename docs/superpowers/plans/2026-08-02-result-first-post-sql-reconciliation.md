# Result-First Post-SQL Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve every persistable dataframe returned by approved read-only SQL as a pending-review dataset while converting alias normalization and optional post-SQL metadata problems into review warnings.

**Architecture:** Keep the existing SQL safety, deterministic identity, staged persistence, manifest, journal, replay, and review architecture. Relax only exact SQL-alias equality, record physical-output origins by SQL selection order, and merge best-effort post-SQL warnings into the current quality report.

**Tech Stack:** Python 3.12, DuckDB, pandas, sqlglot, Pydantic, LangGraph tool contracts, pytest

## Global Constraints

- Run Python through `.venv/bin/python`; never use the system `python3`.
- Preserve every dataframe column; never remove or silently rename `fid` or `fid_1`.
- Treat DuckDB-provided physical names and order as canonical after execution.
- Keep approved-schema, read-only SQL, join, filter, and wildcard validation before execution.
- A zero-row result reaches `pending_review` with a high-severity `ZERO_ROWS` warning.
- Optional source metadata and relationship/quality metrics may warn but must not discard a structurally valid dataset.
- Unsafe paths, corrupted files, manifest mismatches, identity/lineage collisions, wrong plan/report pairings, and invalid activation states remain blocking.
- Do not change the frontend or add another review stage.
- Run the dedicated real smoke once for at most five minutes; do not rerun a failure without explicit user permission.

---

### Task 1: Replace exact alias equality with distinct-alias coverage

**Files:**
- Modify: `epi_agent/db_rag/tools.py:2493-2519,2750-2800`
- Test: `tests/test_db_rag_agent_sql.py`

**Interfaces:**
- Consumes: `_validated_sql_output_aliases(sql: str) -> list[str]` and physical `artifact["columns"]`.
- Produces: `_projected_aliases_are_covered(expected: list[str], physical: list[str]) -> bool`.

- [ ] **Step 1: Write the failing real-execution test**

Create an approved plan containing `SUBJID_PSEUDO` and `FID_PSEUDO`, both with
`output_column="subject_key"`, then use the production registry:

```python
sql = (
    'SELECT "SUBJID_PSEUDO" AS "subject_key", '
    '"FID_PSEUDO" AS "subject_key" '
    'FROM "Index Baseline"'
)
result = build_db_rag_tool_registry().invoke(
    "dbrag-validate_and_extract",
    {
        "plan_id": plan_ref.id,
        "plan_version": plan_ref.version,
        "sql": sql,
    },
    context=context,
)
dataset = context.artifact_store.require(result.artifacts[0])
dataframe, _schema = load_dataset_artifact(dataset.content)
assert dataset.status == "pending_review"
assert list(dataframe.columns) == ["subject_key", "subject_key_1"]
assert dataframe["subject_key"].tolist() == ["S1", "S2"]
assert dataframe["subject_key_1"].tolist() == ["F1", "F2"]
```

- [ ] **Step 2: Run the test and verify the current failure**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_db_rag_agent_sql.py::test_successful_duplicate_aliases_reach_pending_review
```

Expected: FAIL with `DATASET_DURABLE_COLLISION` because physical columns do not
exactly equal SQL aliases.

- [ ] **Step 3: Implement the minimal coverage helper**

Add near `_validated_sql_output_aliases`:

```python
def _projected_aliases_are_covered(
    expected: list[str],
    physical: list[str],
) -> bool:
    expected_names = {
        str(name).strip()
        for name in expected
        if str(name).strip()
    }
    physical_names = {
        str(name).strip()
        for name in physical
        if str(name).strip()
    }
    return bool(expected_names) and expected_names.issubset(physical_names)
```

Replace only the exact output-list comparison in
`_validate_canonical_dataset_lineage`:

```python
physical_columns = [
    str(column).strip()
    for column in list(artifact.get("columns") or [])
]
expected_aliases = [
    str(alias).strip()
    for alias in list(lineage.get("expected_output_aliases") or [])
]
if not _projected_aliases_are_covered(expected_aliases, physical_columns):
    raise _durable_collision(
        "Canonical dataset is missing a projected SQL alias."
    )
```

Do not change selected-field lineage, manifests, storage paths, or identity.

- [ ] **Step 4: Verify duplicate acceptance and tamper rejection**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_db_rag_agent_sql.py::test_successful_duplicate_aliases_reach_pending_review tests/test_db_rag_agent_sql.py::test_sidecar_recovery_rejects_consistently_renamed_output_alias
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add epi_agent/db_rag/tools.py
git commit -m "fix: accept disambiguated SQL output aliases"
```

### Task 2: Record physical output origins by SQL selection order

**Files:**
- Modify: `epi_agent/db_rag/persistence.py:120-270,291-465`
- Modify: `utils/dataset_artifacts.py:59-90`
- Test: `tests/test_db_rag_agent_sql.py`

**Interfaces:**
- Consumes: validated SQL, serialized approved columns, and physical dataframe columns.
- Produces: `_reconcile_output_columns(dataframe: Any, selected_columns: list[dict[str, Any]], *, sql: str) -> dict[str, Any]` with `schema`, `output_column_sources`, and `warnings`.
- Persists: `provenance["output_column_sources"]` and `provenance["post_sql_warnings"]`.

- [ ] **Step 1: Add failing provenance assertions**

Extend Task 1’s test:

```python
sources = dataset.content["provenance"]["output_column_sources"]
assert sources["subject_key"] == {
    "position": 0,
    "sql_alias": "subject_key",
    "source_fields": [
        {"source": "report_duckdb", "table": "Index Baseline", "column": "SUBJID_PSEUDO"}
    ],
}
assert sources["subject_key_1"] == {
    "position": 1,
    "sql_alias": "subject_key",
    "source_fields": [
        {"source": "report_duckdb", "table": "Index Baseline", "column": "FID_PSEUDO"}
    ],
}
assert any(
    warning["code"] == "OUTPUT_ALIAS_DISAMBIGUATED"
    for warning in dataset.content["provenance"]["post_sql_warnings"]
)
```

- [ ] **Step 2: Run the test and verify provenance is absent**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_db_rag_agent_sql.py::test_successful_duplicate_aliases_reach_pending_review
```

Expected: FAIL with `KeyError: 'output_column_sources'`.

- [ ] **Step 3: Parse ordered SQL projection bindings**

Replace the alias-dictionary and plan-position fallbacks with:

```python
def _projection_bindings(
    sql: str,
    selected_columns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    try:
        import sqlglot
        from sqlglot import exp
        expression = sqlglot.parse_one(sql, dialect="duckdb")
    except Exception:
        return []
    select = expression if isinstance(expression, exp.Select) else expression.find(exp.Select)
    if select is None:
        return []

    table_names: dict[str, str] = {}
    for table in expression.find_all(exp.Table):
        physical = str(table.name or "").strip()
        alias = str(table.alias_or_name or "").strip()
        if physical:
            table_names[physical] = physical
        if alias and physical:
            table_names[alias] = physical

    approved = [dict(column) for column in selected_columns]
    bindings: list[dict[str, Any]] = []
    for position, projection in enumerate(select.expressions or []):
        source_fields: list[dict[str, str]] = []
        for source_column in projection.find_all(exp.Column):
            source_name = str(source_column.name or "").strip()
            raw_table = str(source_column.table or "").strip()
            source_table = table_names.get(raw_table, raw_table)
            matches = [
                column for column in approved
                if str(column.get("column") or "").strip() == source_name
                and (not source_table or str(column.get("table") or "").strip() == source_table)
            ]
            if len(matches) == 1:
                matched = matches[0]
                source_fields.append(
                    {
                        key: str(matched.get(key) or "").strip()
                        for key in ("source", "table", "column")
                        if str(matched.get(key) or "").strip()
                    }
                )
        bindings.append(
            {
                "position": position,
                "sql_alias": str(projection.alias_or_name or "").strip(),
                "source_fields": source_fields,
            }
        )
    return bindings
```

- [ ] **Step 4: Reconcile without modifying the dataframe**

Add:

```python
def _reconcile_output_columns(
    dataframe: Any,
    selected_columns: list[dict[str, Any]],
    *,
    sql: str,
) -> dict[str, Any]:
    physical = [str(column) for column in dataframe.columns]
    bindings = _projection_bindings(sql, selected_columns)
    sources: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, str]] = []
    for position, physical_name in enumerate(physical):
        binding = (
            dict(bindings[position])
            if position < len(bindings)
            else {"position": position, "sql_alias": physical_name, "source_fields": []}
        )
        sources[physical_name] = binding
        sql_alias = str(binding.get("sql_alias") or "").strip()
        if sql_alias and sql_alias != physical_name:
            warnings.append(
                {
                    "code": "OUTPUT_ALIAS_DISAMBIGUATED",
                    "severity": "medium",
                    "message": f"SQL alias {sql_alias} was materialized as {physical_name}; both outputs were preserved.",
                }
            )
        if not list(binding.get("source_fields") or []):
            warnings.append(
                {
                    "code": "OUTPUT_METADATA_UNRESOLVED",
                    "severity": "medium",
                    "message": f"Optional source metadata was not resolved for physical output {physical_name}.",
                }
            )
    return {
        "schema": _build_schema_from_sources(dataframe, selected_columns, sources),
        "output_column_sources": sources,
        "warnings": warnings,
    }
```

Add the schema builder using the existing reviewed-metadata lookup:

```python
def _build_schema_from_sources(
    dataframe: Any,
    selected_columns: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    selected_by_pair = {
        (
            str(column.get("table") or "").strip(),
            str(column.get("column") or "").strip(),
        ): dict(column)
        for column in selected_columns
    }
    schema: dict[str, dict[str, Any]] = {}
    for physical_name in dataframe.columns:
        key = str(physical_name)
        source_fields = list(
            dict(sources.get(key) or {}).get("source_fields") or []
        )
        source = dict(source_fields[0]) if source_fields else {}
        pair = (
            str(source.get("table") or "").strip(),
            str(source.get("column") or "").strip(),
        )
        selected = selected_by_pair.get(pair, {})
        reviewed = _lookup_schema_variable_metadata(*pair) or {}
        metadata: dict[str, Any] = {
            "dataType": str(dataframe.dtypes[physical_name]),
        }
        description = str(
            reviewed.get("description")
            or selected.get("description")
            or ""
        ).strip()
        if description:
            metadata["description"] = description
        for field in ("values", "depends_on", "condition", "section_context"):
            value = reviewed.get(field)
            if value is not None and value != "":
                metadata[field] = value
        schema[key] = metadata
    return schema
```

Always write the physical dtype. Unresolved optional description/value metadata
is not an error.

- [ ] **Step 5: Persist reconciliation metadata**

Inside `persist_sql_subset_artifact`:

```python
dataframe = _read_value(execution_result, "dataframe")
reconciliation = _reconcile_output_columns(
    dataframe,
    selected_columns,
    sql=persisted_sql,
)
provenance["output_column_sources"] = dict(reconciliation["output_column_sources"])
provenance["post_sql_warnings"] = [dict(warning) for warning in reconciliation["warnings"]]
persistence_arguments["dataframe"] = dataframe
persistence_arguments["schema"] = dict(reconciliation["schema"])
```

Add to `_DATASET_PROVENANCE_KEYS` in `utils/dataset_artifacts.py`:

```python
"output_column_sources",
"post_sql_warnings",
```

- [ ] **Step 6: Run provenance and replay tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_db_rag_agent_sql.py -k 'duplicate_aliases or replay or manifest_mismatch'
```

Expected: selected tests PASS.

- [ ] **Step 7: Commit**

```bash
git add epi_agent/db_rag/persistence.py utils/dataset_artifacts.py
git commit -m "feat: preserve physical SQL output provenance"
```

### Task 3: Convert optional post-SQL metadata failures into warnings

**Files:**
- Modify: `epi_agent/db_rag/tools.py:1500-1545,3520-3625`
- Modify: `epi_agent/db_rag/persistence.py:291-465`
- Modify: `epi_agent/db_rag/quality.py:140-340`
- Test: `tests/test_db_rag_agent_sql.py`
- Test: `tests/test_db_rag_agent_tools.py`

**Interfaces:**
- Consumes: `provenance["post_sql_warnings"]` from Task 2.
- Produces: `_plan_relationship_metrics(...) -> tuple[list[dict[str, Any]], list[dict[str, str]]]` and quality reports containing persisted warnings.

- [ ] **Step 1: Write the failing missing-relationship test**

Create an approved joined plan whose optional relationship profile is
unavailable after approval. Execute valid joined SQL through the real registry:

```python
result = build_db_rag_tool_registry().invoke(
    "dbrag-validate_and_extract",
    {
        "plan_id": plan_ref.id,
        "plan_version": plan_ref.version,
        "sql": _linked_sql(),
    },
    context=context,
)
dataset = context.artifact_store.require(result.artifacts[0])
assert dataset.status == "pending_review"
assert any(
    warning["code"] == "RELATIONSHIP_METRICS_UNAVAILABLE"
    for warning in dataset.content["provenance"]["post_sql_warnings"]
)
```

Construct the unavailable artifact only in test state; do not add a production
artifact-deletion API.

- [ ] **Step 2: Run and verify the current hard failure**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_db_rag_agent_sql.py::test_missing_optional_relationship_metrics_warn_after_successful_sql
```

Expected: FAIL with `PLAN_RELATIONSHIP_UNPROVEN`.

- [ ] **Step 3: Return relationship metrics plus warnings**

Extract the existing lookup exactly into:

```python
def _relationship_metric_for_operation(
    context: ToolContext,
    operation: dict[str, Any],
) -> dict[str, Any]:
    relationship = _require_artifact(
        context,
        artifact_id=str(
            operation.get("relationship_artifact_id") or ""
        ).strip(),
        version=operation.get("relationship_artifact_version"),
        kind="relationship_profile",
    )
    key_pairs = _operation_key_pairs(operation)
    profile = next(
        (
            value
            for value in _relationship_profiles(relationship.content)
            if _profile_matches_operation(
                value,
                left_table=str(operation.get("left_table") or ""),
                right_table=str(operation.get("right_table") or ""),
                key_pairs=key_pairs,
            )
        ),
        None,
    )
    if profile is None:
        raise ToolExecutionError(
            "PLAN_RELATIONSHIP_UNPROVEN",
            "Approved join relationship evidence is no longer available.",
            recoverable=True,
        )
    return {
        "evidence_label": "profiled relationship risk",
        "relationship_artifact_id": relationship.id,
        "relationship_artifact_version": relationship.version,
        **dict(profile),
    }
```

Then implement:

```python
def _plan_relationship_metrics(
    context: ToolContext,
    plan: DatasetPlan,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    metrics: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    for model in plan.operations:
        operation = model.model_dump(mode="json")
        if str(operation.get("name") or "").strip().casefold() != "join":
            continue
        try:
            metrics.append(_relationship_metric_for_operation(context, operation))
        except ToolExecutionError as error:
            warnings.append(
                {
                    "code": "RELATIONSHIP_METRICS_UNAVAILABLE",
                    "severity": "medium",
                    "message": (
                        "Optional post-SQL relationship metrics were unavailable: "
                        f"{error.code}."
                    ),
                }
            )
    return metrics, warnings
```

Keep plan-stage join validation unchanged.

- [ ] **Step 4: Merge relationship and reconciliation warnings**

Add `post_sql_warnings: list[dict[str, str]] | None = None` to
`persist_sql_subset_artifact`. Merge warnings using `(code, message)` as the
deterministic key:

```python
combined = [
    *list(reconciliation["warnings"]),
    *[dict(value) for value in list(post_sql_warnings or [])],
]
provenance["post_sql_warnings"] = list(
    {
        (warning["code"], warning["message"]): warning
        for warning in combined
    }.values()
)
```

In `_persist_extraction_result`, unpack and pass both values:

```python
relationship_metrics, relationship_warnings = _plan_relationship_metrics(
    context,
    plan,
)
# existing persist_sql_subset_artifact call
post_sql_warnings=relationship_warnings,
```

- [ ] **Step 5: Add failing quality and zero-row assertions**

Inspect duplicate-alias and missing-relationship datasets and assert their
warning codes appear in `quality.content["warnings"]`. Add a real empty
extraction and assert:

```python
assert dataset.status == "pending_review"
assert dataset.content["row_count"] == 0
assert any(
    warning["code"] == "ZERO_ROWS"
    for warning in quality.content["warnings"]
)
```

Create a structurally valid dataset whose optional
`provenance["grain_columns"]` value is malformed, then assert inspection still
creates a report containing `QUALITY_CHECK_INCOMPLETE`. This test must preserve
valid dataset, plan, and SQL lineage so it exercises only optional diagnostics.

- [ ] **Step 6: Merge persisted warnings into quality reports**

Add to `quality.py`:

```python
def _persisted_post_sql_warnings(
    provenance: dict[str, Any],
) -> list[QualityWarning]:
    warnings: list[QualityWarning] = []
    for value in provenance.get("post_sql_warnings") or []:
        try:
            warnings.append(QualityWarning.model_validate(value))
        except ValueError:
            continue
    return warnings
```

Treat recorded physical outputs as reconciled:

```python
reconciled_columns = set(
    dict(provenance.get("output_column_sources") or {})
)
unexpected_columns = sorted(
    set(columns) - expected_columns - reconciled_columns
)
```

Extend `_warnings` with `inherited: list[QualityWarning]`, prepend those values,
append current zero-row/grain/concept/join warnings, then deduplicate:

```python
deduplicated = {
    (warning.code, warning.message): warning
    for warning in warnings
}
return list(deduplicated.values())
```

Wrap only optional grain/concept/relationship calculations after the dataframe
and plan lineage have been loaded successfully:

```python
optional_warnings = _persisted_post_sql_warnings(provenance)
try:
    coverage = {
        _concept_key(concept, index): bool(_concept_fields(concept))
        and all(
            column in dataframe.columns
            for column in _concept_fields(concept)
        )
        for index, concept in enumerate(plan.concepts)
    }
    duplicate_grain_rows, missing_grain_columns = _duplicate_grain_rows(
        dataframe,
        provenance,
        plan,
    )
    grain_uniqueness = _grain_uniqueness(dataframe, provenance, plan)
except (AttributeError, TypeError, ValueError) as error:
    coverage = {}
    duplicate_grain_rows = None
    missing_grain_columns = []
    grain_uniqueness = None
    optional_warnings.append(
        QualityWarning(
            code="QUALITY_CHECK_INCOMPLETE",
            severity="medium",
            message=(
                "Optional post-SQL quality diagnostics were incomplete: "
                f"{type(error).__name__}."
            ),
        )
    )
```

Do not catch dataframe loading, wrong-plan lineage, or report identity failures.

- [ ] **Step 7: Run focused quality tests**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_db_rag_agent_sql.py -k 'duplicate_aliases or relationship_metrics or zero_rows'
.venv/bin/python -m pytest -q tests/test_db_rag_agent_tools.py -k 'quality_inspection or output_aliases'
```

Expected: all selected tests PASS, including the existing high-severity
`ZERO_ROWS` contract.

- [ ] **Step 8: Commit**

```bash
git add epi_agent/db_rag/tools.py epi_agent/db_rag/persistence.py epi_agent/db_rag/quality.py
git commit -m "feat: warn on optional post SQL metadata gaps"
```

### Task 4: Verify reviewability and retained integrity boundaries

**Files:**
- Create: `scripts/smoke_post_sql_reconciliation.py`
- Test: `tests/test_db_rag_agent_sql.py`
- Test: `tests/test_db_rag_agent_reviews.py`
- Verify: `epi_agent/db_rag/tools.py`
- Verify: `epi_agent/db_rag/persistence.py`
- Verify: `epi_agent/db_rag/quality.py`
- Verify: `utils/dataset_artifacts.py`

**Interfaces:**
- Consumes: production DB-RAG tools, real DuckDB execution, persistence, quality inspection, and review contracts.
- Produces: a one-run internal smoke proving duplicate aliases and zero-row results remain reviewable without weakening integrity checks.

- [ ] **Step 1: Prove high warnings do not block approval**

Use an existing pending-dataset review helper with a zero-row quality report:

```python
monkeypatch.setattr(
    "epi_agent.db_rag.reviews.interrupt",
    lambda _payload: {"action": "approve"},
)
result = RequestDatasetReviewTool().invoke(
    {
        "dataset_id": dataset_ref.id,
        "dataset_version": dataset_ref.version,
        "quality_report_id": quality_ref.id,
        "quality_report_version": quality_ref.version,
    },
    context,
)
assert "status=active" in result.message
```

Run this beside the existing mismatched-quality-report test. If approval already
works, make no review-code change.

- [ ] **Step 2: Create the real subsystem smoke**

Create `scripts/smoke_post_sql_reconciliation.py` with this import bootstrap:

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
```

The smoke must use a temporary real DuckDB, `StudyBundle`, `SchemaCatalog`,
`DuckDbStudyDataSource`, `StateArtifactStore`, and the production DB-RAG
registry. It must assert:

1. repeated aliases persist as `fid` and `fid_1` with distinct values;
2. `output_column_sources` maps them to distinct source fields;
3. quality contains `OUTPUT_ALIAS_DISAMBIGUATED`;
4. a second approved query returns zero rows as `pending_review`;
5. its quality report contains `ZERO_ROWS`; and
6. exactly one final output line begins with `PASS:`.

Do not stub the LLM, DB-RAG, DuckDB, persistence, quality inspection, or artifact
store. This backend feature has no browser behavior.

- [ ] **Step 3: Run focused regressions**

Run:

```bash
.venv/bin/python -m pytest -q tests/test_db_rag_agent_sql.py tests/test_db_rag_agent_tools.py tests/test_db_rag_agent_reviews.py
```

Expected: zero failures. Preserve any unrelated pre-existing failure and report
it separately rather than changing unrelated code.

- [ ] **Step 4: Run syntax and diff checks**

Run:

```bash
.venv/bin/python -m py_compile epi_agent/db_rag/tools.py epi_agent/db_rag/persistence.py epi_agent/db_rag/quality.py utils/dataset_artifacts.py scripts/smoke_post_sql_reconciliation.py
git diff --check
```

Expected: exit status 0 with no syntax or whitespace errors.

- [ ] **Step 5: Run the dedicated smoke exactly once**

Run:

```bash
.venv/bin/python scripts/smoke_post_sql_reconciliation.py
```

Expected: exit status 0 and one `PASS:` line. On failure, preserve all output
and do not rerun without explicit user approval.

- [ ] **Step 6: Inspect final state**

Run:

```bash
git status --short
git diff --check
git log -4 --oneline
```

Expected: production changes are committed, local ignored tests and smoke assets
remain available, and no unrelated tracked files are modified.
