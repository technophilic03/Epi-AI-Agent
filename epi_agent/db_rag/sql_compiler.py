"""Deterministic SQL rendering for an exact approved dataset plan."""
from __future__ import annotations

from typing import Any

from epi_agent.artifacts import DatasetPlan, PlanField, PlanReduction


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _output_fields(plan: DatasetPlan) -> list[PlanField]:
    fields = [
        *plan.required_fields,
        *(field for concept in plan.concepts for field in concept.fields),
    ]
    seen: set[tuple[str, str, str]] = set()
    output: list[PlanField] = []
    for field in fields:
        key = (field.source, field.table, field.column)
        if key in seen:
            continue
        seen.add(key)
        output.append(field)
    return output


def _usable_reductions(plan: DatasetPlan) -> list[PlanReduction]:
    valid_strategies = {
        "latest",
        "earliest",
        "single_matching_record",
        "aggregate",
    }
    return [
        reduction
        for reduction in plan.reductions
        if (
            reduction.table
            and reduction.group_by
            and reduction.strategy in valid_strategies
        )
    ]


def _table_aliases(plan: DatasetPlan) -> dict[str, str]:
    tables: list[str] = []
    for field in _output_fields(plan):
        if field.table not in tables:
            tables.append(field.table)
    for operation in plan.operations:
        if operation.name.casefold() == "join":
            for table in (operation.left_table, operation.right_table):
                if table and table not in tables:
                    tables.append(table)
    return {table: f"t{index}" for index, table in enumerate(tables)}


def _constraints(filters: list[dict[str, Any]], alias: str) -> str:
    clauses: list[str] = []
    for entry in filters:
        for constraint in entry.get("value_constraints") or []:
            if not isinstance(constraint, dict):
                continue
            column = str(constraint.get("column") or "").strip()
            operator = str(constraint.get("operator") or "").strip()
            if not column or operator not in {"=", "!=", "<>", "<", "<=", ">", ">=", "IN"}:
                continue
            if "values" in constraint:
                values = constraint.get("values") or []
                clauses.append(f"{alias}.{_quote(column)} IN ({', '.join(_literal(value) for value in values)})")
            elif "value" in constraint:
                clauses.append(f"{alias}.{_quote(column)} {operator} {_literal(constraint['value'])}")
    return " AND ".join(clauses)


def _reduction_cte(reduction: PlanReduction, alias: str) -> str:
    source_alias = "source_row"
    where = _constraints(reduction.filters, source_alias)
    where_clause = f" WHERE {where}" if where else ""
    group_columns = [f"{source_alias}.{_quote(field.column)}" for field in reduction.group_by]
    if reduction.strategy == "aggregate":
        aggregates = [
            f"{aggregate.function.upper()}({source_alias}.{_quote(aggregate.field.column)}) AS {_quote(aggregate.field.column)}"
            for aggregate in reduction.aggregates
        ]
        return (
            f"{_quote(alias)} AS (SELECT {', '.join([*group_columns, *aggregates])} "
            f"FROM {_quote(reduction.table)} AS {source_alias}{where_clause} "
            f"GROUP BY {', '.join(group_columns)})"
        )
    if reduction.strategy == "single_matching_record":
        return f"{_quote(alias)} AS (SELECT * FROM {_quote(reduction.table)} AS {source_alias}{where_clause})"
    direction = "DESC" if reduction.strategy == "latest" else "ASC"
    order_fields = [reduction.order_by, *reduction.tie_breakers]
    order = ", ".join(f"{source_alias}.{_quote(field.column)} {direction} NULLS LAST" for field in order_fields if field)
    partition = ", ".join(group_columns)
    return (
        f"{_quote(alias)} AS (SELECT * EXCLUDE (__plan_rank) FROM ("
        f"SELECT {source_alias}.*, ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {order}) AS __plan_rank "
        f"FROM {_quote(reduction.table)} AS {source_alias}{where_clause}) AS ranked WHERE __plan_rank = 1)"
    )


def compile_dataset_plan_sql(plan: DatasetPlan) -> str:
    """Render only plan-owned sources, joins, filters, and reductions."""
    aliases = _table_aliases(plan)
    if not aliases:
        raise ValueError("Approved dataset plan has no output or linkage tables.")
    reductions = _usable_reductions(plan)
    reduced = {reduction.table: f"reduced_{index}" for index, reduction in enumerate(reductions)}
    ctes = [_reduction_cte(reduction, reduced[reduction.table]) for reduction in reductions]
    root_table = next(iter(aliases))
    root_relation = _quote(reduced[root_table]) if root_table in reduced else _quote(root_table)
    from_sql = f"FROM {root_relation} AS {aliases[root_table]}"
    joined = {root_table}
    pending = [operation for operation in plan.operations if operation.name.casefold() == "join"]
    while pending:
        for operation in list(pending):
            left, right = operation.left_table or "", operation.right_table or ""
            if left not in joined and right not in joined:
                continue
            next_table = right if left in joined else left
            left_alias, right_alias = aliases[left], aliases[right]
            terms = [f"{left_alias}.{_quote(pair.left_column)} = {right_alias}.{_quote(pair.right_column)}" for pair in operation.key_pairs]
            relation = _quote(reduced[next_table]) if next_table in reduced else _quote(next_table)
            from_sql += f" {operation.join_type.upper()} JOIN {relation} AS {aliases[next_table]} ON {' AND '.join(terms)}"
            joined.add(next_table)
            pending.remove(operation)
            break
        else:
            raise ValueError("Approved dataset plan has a disconnected join graph.")
    projection = ", ".join(
        f"{aliases[field.table]}.{_quote(field.column)} AS {_quote(field.output_column or field.column)}"
        for field in _output_fields(plan)
    )
    where = _constraints(plan.filters, aliases[root_table])
    query = f"SELECT {projection} {from_sql}"
    if where:
        query += f" WHERE {where}"
    return f"WITH {', '.join(ctes)} {query}" if ctes else query


__all__ = ["compile_dataset_plan_sql"]
