# Result-First Post-SQL Reconciliation Design

## Goal

Once approved read-only SQL executes successfully and returns a persistable
dataframe, preserve that result as a `pending_review` dataset. Post-SQL checks
must describe result-shape or scientific concerns as review warnings instead of
rejecting usable data. Only storage safety, corruption, and irreconcilable
identity or lineage remain blocking.

## Scope

This is Plan 3 of the study-neutral DB-RAG simplification. It is a localized
relaxation of post-execution result reconciliation, quality inspection, and
optional relationship metadata. It does not redesign dataset planning, SQL
safety validation, durable persistence, or the review UI.

## Existing problem

DuckDB makes repeated output names unique when materializing a dataframe. For
example:

```sql
SELECT a.FID AS fid, b.FID AS fid
```

returns physical columns:

```text
fid, fid_1
```

The current persistence verifier compares the physical column list with the SQL
alias list using exact name, order, and multiplicity equality. It can therefore
raise `DATASET_DURABLE_COLLISION` after SQL has executed and the dataframe is
usable. Missing optional relationship-profile metadata can also reject the
result after execution.

## Core decision

The successfully returned dataframe is the physical result. Plan 3 preserves
its rows, column order, and DuckDB-provided unique column names. The application
does not remove duplicate-looking fields and does not rename the dataframe a
second time.

Post-SQL reconciliation records how each physical output was produced; it does
not reconstruct the dataframe to match planning metadata.

## Output reconciliation

The reconciliation inputs are:

- the final validated SQL projection list;
- the physical dataframe column list;
- the approved source tables and columns.

The system matches output columns to SQL selections by their order. “Order”
means the order of expressions in the final SQL `SELECT` list and the returned
dataframe columns, not row position.

For the repeated-alias example, reconciliation records:

```text
first SQL selection:  a.FID AS fid -> physical column fid
second SQL selection: b.FID AS fid -> physical column fid_1
```

The physical dataset keeps both `fid` and `fid_1`. Its schema metadata records
the distinct source table and column for each output.

Exact alias-list equality is removed. Reconciliation may use name and source
metadata as supporting evidence, but position is the deterministic tie-breaker
when aliases repeat. Repeated-alias suffixes and incomplete optional metadata
produce warnings, not result rejection.

A distinct projected alias that is entirely absent from the physical result is
not an alias-normalization difference. It indicates an engine, artifact, or
tampering inconsistency and remains an integrity failure. Repeated occurrences
of the same SQL alias require only one unsuffixed physical occurrence; their
additional physical outputs may use DuckDB suffixes.

## Warning contract

The post-SQL report may add warnings for:

- a repeated SQL alias disambiguated by DuckDB;
- a physical output whose optional source metadata could not be resolved;
- unavailable optional relationship-profile metrics;
- zero rows;
- duplicate declared-grain values;
- missing declared-grain fields;
- requested-concept coverage uncertainty;
- unexpected physical output names; and
- observed join expansion.

Warnings are visible in the existing dataset-review panel. They never activate
the dataset automatically and never force the agent to change approved filters,
joins, or fields.

## Data-quality timing

Before dataset-plan review, factual validation continues checking that:

- requested tables and columns exist;
- structured filter values exist individually;
- multi-table fields have an observed join path and non-null key overlap; and
- unresolved requested concepts are broadened through catalog retrieval before
  returning a visible technical resolution failure.

The planning stage does not execute every combination of filters and joins to
guarantee a nonempty intersection.

After SQL execution, the quality report measures actual row count, physical
columns, null rates, duplicate-grain values, concept coverage, and join
expansion. A zero-row result is a valid negative result. It is saved as
`pending_review` with a high-severity `ZERO_ROWS` warning. The system never
silently removes filters or loosens joins to manufacture observations.

Grain, concept, and relationship computations are best-effort additions to the
review. Failure of an optional computation adds an incomplete-quality warning;
it does not discard a structurally valid dataset. Loading the wrong dataset or
using the wrong plan remains blocking.

## Persistence and recovery

The existing deterministic dataset identity, staged writes, durable manifest,
persistence journal, promotion, commit, and replay flow remain in place.

Temporary journal, staging, promotion, or commit uncertainty remains
recoverable. The agent replays the same tool call with the same plan, SQL, and
dataset identity. It does not generate another plan or dataset identity.

If a durable staged or promoted result exists, replay reconciles it without
rerunning SQL. If no durable result was produced before interruption, replay may
execute the same validated read-only SQL again; it never invents different SQL.

## Blocking conditions retained

Plan 3 retains hard blocking for:

- a dataframe that cannot be serialized safely;
- a storage path outside the managed runtime root;
- malformed, corrupted, or manifest-mismatched durable files;
- a deterministic dataset identity attached to different plan or SQL lineage;
- a wholly missing distinct projected SQL alias;
- a dataset paired with the wrong plan or quality report;
- an invalid lifecycle state that could activate the wrong dataset; and
- nonrecoverable artifact-store capability failures.

These checks protect data identity and storage integrity. They do not encode a
particular study’s expected variables, grain, population, or scientific result.

## UI behavior

The existing dataset-review UI remains unchanged. It already renders dimensions,
columns, quality warnings, raw quality details, and approve/revise/cancel actions.
Plan 3 changes which backend conditions become warnings; it does not add another
review stage or new checkbox requirement.

## Expected implementation surface

Production changes should remain localized to:

- `epi_agent/db_rag/tools.py` for post-execution reconciliation and persistence
  lineage checks;
- `epi_agent/db_rag/persistence.py` for order-based physical-column provenance;
- `epi_agent/db_rag/quality.py` for best-effort warnings; and
- prompt wording only if needed to make warning handling explicit.

No frontend modification is expected.

## Verification

Focused tests and the dedicated internal feature smoke must prove that:

1. repeated SQL aliases materialized as `fid` and `fid_1` reach
   `pending_review`;
2. both columns and their distinct source provenance are preserved;
3. no selected column is silently removed or renamed after DuckDB execution;
4. already-unique aliases remain unchanged;
5. a zero-row dataframe reaches review with `ZERO_ROWS`;
6. unavailable optional relationship or quality metadata produces warnings;
7. distinct projected aliases that disappear entirely still fail integrity
   verification;
8. corrupted files, unsafe paths, identity collisions, and plan/quality-report
   mismatches still block; and
9. the current review UI can approve, revise, or cancel the resulting dataset.

## Non-goals

Plan 3 does not:

- relax read-only SQL safety or approved-schema validation;
- permit `SELECT *`;
- infer or remove scientifically redundant fields;
- guarantee that approved filters have a nonempty combined intersection;
- add study-specific population or grain rules;
- remove durable tamper and lineage checks; or
- redesign the dataset review panel.
