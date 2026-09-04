import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from ..db.catalog_job_table_edges import CatalogJobTableEdgeSelect
from ..db.catalog_jobs import CatalogJobSelect
from ..db.catalog_table_join_edges import CatalogTableJoinEdgeSelect

TableEdgeFetcher = Callable[[Sequence[str]], list[CatalogJobTableEdgeSelect]]
JobEdgeFetcher = Callable[[Sequence[str]], list[CatalogJobTableEdgeSelect]]
JobFetcher = Callable[[Sequence[str]], list[CatalogJobSelect]]


def _mermaid_id(name: str) -> str:
    """
    Collapse a name into a mermaid-safe node identifier.

    Args:
        name: raw table, column, or type name

    Returns:
        The name with every unsafe character replaced by an underscore
    """
    return re.sub(r"[^A-Za-z0-9_]", "_", name) or "_"


def _label(text: str) -> str:
    """
    Escape a display label for use inside a quoted mermaid string.

    Args:
        text: raw display text

    Returns:
        The text with double quotes escaped
    """
    return text.replace('"', "#quot;")


def build_erd(
    table_name: str,
    columns_by_table: Mapping[str, Sequence[Mapping[str, Any]]],
    join_edges: Sequence[CatalogTableJoinEdgeSelect],
) -> str:
    """
    Build mermaid erDiagram source for a table and its join partners.

    Args:
        table_name: the table at the center of the diagram
        columns_by_table: decoded storage descriptor columns keyed by table name
        join_edges: the join edges touching the table

    Returns:
        The mermaid erDiagram source
    """
    names = [table_name]
    for edge in join_edges:
        for name in (edge["left_table"], edge["right_table"]):
            if name not in names:
                names.append(name)
    ids: dict[str, str] = {}
    for name in names:
        node_id = _mermaid_id(name)
        while node_id in ids.values():
            node_id = f"{node_id}_"
        ids[name] = node_id
    lines = ["erDiagram"]
    for name in names:
        lines.append(f'    {ids[name]}["{_label(name)}"] {{')
        for column in columns_by_table.get(name, []):
            column_type = _mermaid_id(str(column.get("Type") or "unknown"))
            column_name = _mermaid_id(str(column.get("Name") or "unknown"))
            comment = column.get("Comment")
            suffix = f' "{_label(str(comment))}"' if comment else ""
            lines.append(f"        {column_type} {column_name}{suffix}")
        lines.append("    }")
    seen: set[tuple[str, str, str]] = set()
    for edge in join_edges:
        key = (
            edge["left_table"],
            edge["right_table"],
            f"{edge['left_column']} = {edge['right_column']}",
        )
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f'    {ids[edge["left_table"]]} ||--|| {ids[edge["right_table"]]} : '
            f'"{_label(key[2])}"'
        )
    return "\n".join(lines)


def build_dag(
    table_name: str,
    get_table_edges: TableEdgeFetcher,
    get_job_edges: JobEdgeFetcher,
    get_jobs_by_ids: JobFetcher,
    max_depth: int = 3,
) -> str:
    """
    Build mermaid flowchart source for a table's job lineage.

    Args:
        table_name: the table at the center of the diagram
        get_table_edges: fetches the job table edges touching the given tables
        get_job_edges: fetches the job table edges for the given jobs
        get_jobs_by_ids: fetches the job records with the given PKs
        max_depth: maximum number of job layers to traverse

    Returns:
        The mermaid flowchart source
    """
    visited_tables = {table_name}
    visited_jobs: set[str] = set()
    edges: list[CatalogJobTableEdgeSelect] = []
    table_databases: dict[str, str] = {}
    frontier = [table_name]
    for _ in range(max_depth):
        frontier_edges = get_table_edges(frontier)
        new_job_ids = sorted({edge["job_id"] for edge in frontier_edges} - visited_jobs)
        if not new_job_ids:
            break
        visited_jobs.update(new_job_ids)
        layer_edges = get_job_edges(new_job_ids)
        edges.extend(layer_edges)
        for edge in layer_edges:
            if edge["database_name"]:
                table_databases.setdefault(edge["table_name"], edge["database_name"])
        frontier = sorted({edge["table_name"] for edge in layer_edges} - visited_tables)
        visited_tables.update(frontier)
        if not frontier:
            break
    jobs = {job["id"]: job for job in get_jobs_by_ids(sorted(visited_jobs))}
    lines = ["flowchart LR"]
    table_ids: dict[str, str] = {}
    for name in sorted(visited_tables):
        table_ids[name] = f"t_{_mermaid_id(name)}"
        database = table_databases.get(name)
        label = f"{database}.{name}" if database else name
        lines.append(f'    {table_ids[name]}["{_label(label)}"]')
    job_ids: dict[str, str] = {}
    for index, job_id in enumerate(sorted(visited_jobs)):
        job_ids[job_id] = f"j_{index}"
        job = jobs.get(job_id)
        label = f"{job['type']}: {job['name']}" if job else job_id
        lines.append(f'    {job_ids[job_id]}(["{_label(label)}"])')
    seen: set[tuple[str, str, str]] = set()
    for edge in edges:
        key = (edge["job_id"], edge["table_name"], edge["direction"])
        if key in seen or edge["table_name"] not in table_ids:
            continue
        seen.add(key)
        table_node = table_ids[edge["table_name"]]
        job_node = job_ids[edge["job_id"]]
        if edge["direction"] == "read":
            lines.append(f"    {table_node} --> {job_node}")
        else:
            lines.append(f"    {job_node} --> {table_node}")
    lines.append("    classDef focus stroke-width:3px")
    lines.append(f"    class {table_ids[table_name]} focus")
    return "\n".join(lines)
