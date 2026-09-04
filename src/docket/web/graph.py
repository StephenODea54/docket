import zlib
from collections.abc import Callable, Sequence
from typing import Any

from ..db.catalog_job_table_edges import CatalogJobTableEdgeSelect
from ..db.catalog_jobs import CatalogJobSelect
from ..db.catalog_table_join_edges import CatalogTableJoinEdgeSelect
from ..db.catalog_tables import CatalogTableModel, CatalogTableSelect
from ..db.utils import decode_column

TableEdgeFetcher = Callable[[Sequence[str]], list[CatalogJobTableEdgeSelect]]
JobEdgeFetcher = Callable[[Sequence[str]], list[CatalogJobTableEdgeSelect]]
JobFetcher = Callable[[Sequence[str]], list[CatalogJobSelect]]
TableFetcher = Callable[[Sequence[str]], list[CatalogTableSelect]]

Card = dict[str, Any]
Arrow = dict[str, Any]
Figure = dict[str, Any]


def accent(name: str) -> int:
    """
    Pick a stable color ramp index between 1 and 6 for a name.

    Args:
        name: any string, usually a database name

    Returns:
        The ramp index
    """
    return zlib.crc32(name.encode()) % 6 + 1


def _partition_names(row: CatalogTableSelect | None) -> list[str]:
    """
    Extract the partition column names from a catalog table row.

    Args:
        row: the catalog table row, or None when the table is unknown

    Returns:
        The partition column names in declaration order
    """
    if row is None:
        return []
    keys = decode_column(CatalogTableModel, row, "partition_keys") or []
    return [key["Name"] for key in keys if key.get("Name")]


def _job_label(job: CatalogJobSelect | None, job_id: str) -> str:
    """
    Format a job for display, falling back to its id when unknown.

    Args:
        job: the job record, or None when it is missing
        job_id: the job PK used as the fallback label

    Returns:
        The display label
    """
    return f"{job['type']}: {job['name']}" if job else job_id


def _card(
    table: str, database: str | None, rows: list[dict[str, Any]], focus: bool = False
) -> Card:
    """
    Build one template-ready graph card.

    Args:
        table: the table name
        database: the resolved database name, or None when unknown
        rows: the column rows to show on the card
        focus: whether this card is the diagram's focus table

    Returns:
        The card dict consumed by the _graph.html partial
    """
    return {
        "key": f"{database}.{table}" if database else table,
        "database": database,
        "table": table,
        "ramp": accent(database or table),
        "rows": rows,
        "focus": focus,
    }


def build_erd(
    database_name: str,
    table_name: str,
    table_row: CatalogTableSelect,
    join_edges: Sequence[CatalogTableJoinEdgeSelect],
    get_tables_by_names: TableFetcher,
    get_jobs_by_ids: JobFetcher,
) -> Figure:
    """
    Build the join diagram for a table: cards, join-key rows, and column arrows.

    Args:
        database_name: the focus table's database
        table_name: the focus table's name
        table_row: the focus table's catalog row
        join_edges: the join edges touching the focus table
        get_tables_by_names: fetches catalog rows for the given table names
        get_jobs_by_ids: fetches the job records with the given PKs

    Returns:
        A figure dict with card layers and arrow specs
    """
    edge_tables = {edge["left_table"] for edge in join_edges} | {
        edge["right_table"] for edge in join_edges
    }
    partner_names = sorted(edge_tables - {table_name})
    catalog = {row["name"]: row for row in get_tables_by_names(partner_names)}
    databases: dict[str, str | None] = {table_name: database_name}
    for edge in join_edges:
        for side in ("left", "right"):
            name = edge[f"{side}_table"]
            if name not in databases:
                partner = catalog.get(name)
                databases[name] = edge[f"{side}_database"] or (
                    partner["database_name"] if partner else None
                )

    def key(name: str) -> str:
        database = databases.get(name)
        return f"{database}.{name}" if database else name

    join_columns: dict[str, set[str]] = {}
    for edge in join_edges:
        join_columns.setdefault(edge["left_table"], set()).add(edge["left_column"])
        join_columns.setdefault(edge["right_table"], set()).add(edge["right_column"])

    def rows_for(name: str, row: CatalogTableSelect | None) -> list[dict[str, Any]]:
        partitions = _partition_names(row)
        rows = [{"name": partition, "partition": True} for partition in partitions]
        rows += [
            {"name": column, "partition": False}
            for column in sorted(join_columns.get(name, set()) - set(partitions))
        ]
        return rows

    focus_card = _card(table_name, database_name, rows_for(table_name, table_row), True)
    partners = [
        _card(name, databases.get(name), rows_for(name, catalog.get(name)))
        for name in partner_names
    ]
    layers = [[focus_card]] + ([partners] if partners else [])
    jobs = {
        job["id"]: job
        for job in get_jobs_by_ids(sorted({edge["job_id"] for edge in join_edges}))
    }
    grouped: dict[tuple[str, str, str, str], list[str]] = {}
    for edge in join_edges:
        pair = (
            key(edge["left_table"]),
            edge["left_column"],
            key(edge["right_table"]),
            edge["right_column"],
        )
        label = _job_label(jobs.get(edge["job_id"]), edge["job_id"])
        labels = grouped.setdefault(pair, [])
        if label not in labels:
            labels.append(label)
    arrows = [
        {
            "a": f"{table_a}.{column_a}",
            "b": f"{table_b}.{column_b}",
            "ta": table_a,
            "tb": table_b,
            "job": ", ".join(labels),
        }
        for (table_a, column_a, table_b, column_b), labels in grouped.items()
    ]
    return {"layers": layers, "arrows": arrows}


def build_dag(
    database_name: str,
    table_name: str,
    get_table_edges: TableEdgeFetcher,
    get_job_edges: JobEdgeFetcher,
    get_jobs_by_ids: JobFetcher,
    get_tables_by_names: TableFetcher,
    depth: int = 2,
) -> Figure:
    """
    Build the lineage diagram for a table: layered table cards and job arrows.

    Args:
        database_name: the focus table's database
        table_name: the focus table's name
        get_table_edges: fetches the job table edges touching the given tables
        get_job_edges: fetches the job table edges for the given jobs
        get_jobs_by_ids: fetches the job records with the given PKs
        get_tables_by_names: fetches catalog rows for the given table names
        depth: maximum job hops to walk in each direction

    Returns:
        A figure dict with card layers and arrow specs
    """
    placed = {table_name}
    databases: dict[str, str | None] = {table_name: database_name}
    visited_jobs: set[str] = set()
    edges_by_id: dict[str, CatalogJobTableEdgeSelect] = {}

    def expand(frontier: set[str], inbound: str, outbound: str) -> set[str]:
        touching = get_table_edges(sorted(frontier))
        new_jobs = sorted(
            {
                edge["job_id"]
                for edge in touching
                if edge["direction"] == inbound and edge["table_name"] in frontier
            }
            - visited_jobs
        )
        if not new_jobs:
            return set()
        visited_jobs.update(new_jobs)
        following = set()
        for edge in get_job_edges(new_jobs):
            edges_by_id[edge["id"]] = edge
            if edge["database_name"]:
                databases.setdefault(edge["table_name"], edge["database_name"])
            if edge["direction"] == outbound and edge["table_name"] not in placed:
                following.add(edge["table_name"])
        return following

    def walk(inbound: str, outbound: str) -> list[list[str]]:
        layers = []
        frontier = {table_name}
        for _ in range(depth):
            following = expand(frontier, inbound, outbound)
            if not following:
                break
            placed.update(following)
            layers.append(sorted(following))
            frontier = following
        return layers

    down_layers = walk("read", "write")
    up_layers = walk("write", "read")
    catalog = {row["name"]: row for row in get_tables_by_names(sorted(placed))}
    for name, row in catalog.items():
        databases.setdefault(name, row["database_name"])

    def key(name: str) -> str:
        database = databases.get(name)
        return f"{database}.{name}" if database else name

    def cards(names: list[str]) -> list[Card]:
        return [
            _card(
                name,
                databases.get(name),
                [
                    {"name": partition, "partition": True}
                    for partition in _partition_names(catalog.get(name))
                ],
                focus=name == table_name,
            )
            for name in names
        ]

    layers = (
        [cards(names) for names in reversed(up_layers)]
        + [cards([table_name])]
        + [cards(names) for names in down_layers]
    )
    jobs = {job["id"]: job for job in get_jobs_by_ids(sorted(visited_jobs))}
    reads: dict[str, set[str]] = {}
    writes: dict[str, set[str]] = {}
    for edge in edges_by_id.values():
        if edge["table_name"] not in placed:
            continue
        target = reads if edge["direction"] == "read" else writes
        target.setdefault(edge["job_id"], set()).add(edge["table_name"])
    grouped: dict[tuple[str, str], list[str]] = {}
    for job_id in sorted(visited_jobs):
        label = _job_label(jobs.get(job_id), job_id)
        for source in sorted(reads.get(job_id, set())):
            for target in sorted(writes.get(job_id, set())):
                if source == target:
                    continue
                labels = grouped.setdefault((key(source), key(target)), [])
                if label not in labels:
                    labels.append(label)
    arrows = [
        {
            "a": source,
            "b": target,
            "ta": source,
            "tb": target,
            "head": "b",
            "job": ", ".join(labels),
        }
        for (source, target), labels in grouped.items()
    ]
    return {"layers": layers, "arrows": arrows}
