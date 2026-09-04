from collections.abc import Callable, Sequence
from typing import TypedDict

from .db.catalog_job_table_edges import CatalogJobTableEdgeSelect
from .db.catalog_jobs import CatalogJobSelect
from .db.catalog_table_join_edges import CatalogTableJoinEdgeSelect
from .db.catalog_tables import CatalogTableSelect

TableEdgeFetcher = Callable[[Sequence[str]], list[CatalogJobTableEdgeSelect]]
JobEdgeFetcher = Callable[[Sequence[str]], list[CatalogJobTableEdgeSelect]]
JoinEdgeFetcher = Callable[[str], list[CatalogTableJoinEdgeSelect]]
JobFetcher = Callable[[Sequence[str]], list[CatalogJobSelect]]
TableFetcher = Callable[[Sequence[str]], list[CatalogTableSelect]]


class JobRef(TypedDict):
    id: str
    label: str


class TableRef(TypedDict):
    database: str | None
    table: str


class JoinRef(TypedDict):
    job: JobRef
    partner: TableRef
    evidence: str


class DependentsReport(TypedDict):
    database: str
    table: str
    in_catalog: bool
    direct_jobs: list[JobRef]
    direct_tables: list[TableRef]
    join_refs: list[JoinRef]
    transitive_jobs: list[JobRef]
    transitive_tables: list[TableRef]
    layers: list[list[str]]
    has_dependents: bool


def _key(database: str | None, table: str) -> str:
    """
    Format a table's display key, prefixing the database when known.

    Args:
        database: the table's database name, or None when unknown
        table: the table name

    Returns:
        The display key
    """
    return f"{database}.{table}" if database else table


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


def collect_dependents(
    database_name: str,
    table_name: str,
    get_table_edges: TableEdgeFetcher,
    get_job_edges: JobEdgeFetcher,
    get_join_edges: JoinEdgeFetcher,
    get_jobs_by_ids: JobFetcher,
    get_tables_by_names: TableFetcher,
    in_catalog: bool = True,
) -> DependentsReport:
    """
    Walk the downstream closure of a table: reading jobs, written tables,
    and join references.

    Args:
        database_name: the focus table's database
        table_name: the focus table's name
        get_table_edges: fetches the job table edges touching the given tables
        get_job_edges: fetches the job table edges for the given jobs
        get_join_edges: fetches the join edges touching the given table
        get_jobs_by_ids: fetches the job records with the given PKs
        get_tables_by_names: fetches catalog rows for the given table names
        in_catalog: whether the focus table exists in the catalog snapshot

    Returns:
        The dependents report
    """
    placed = {table_name}
    databases: dict[str, str | None] = {table_name: database_name or None}
    visited_jobs: set[str] = set()
    job_hops: dict[str, int] = {}
    table_hops: dict[str, int] = {}
    name_layers: list[list[str]] = []
    frontier = {table_name}
    hop = 0
    while frontier:
        hop += 1
        touching = get_table_edges(sorted(frontier))
        new_jobs = sorted(
            {
                edge["job_id"]
                for edge in touching
                if edge["direction"] == "read" and edge["table_name"] in frontier
            }
            - visited_jobs
        )
        if not new_jobs:
            break
        visited_jobs.update(new_jobs)
        for job_id in new_jobs:
            job_hops[job_id] = hop
        following = set()
        for edge in get_job_edges(new_jobs):
            if edge["database_name"]:
                databases.setdefault(edge["table_name"], edge["database_name"])
            if edge["direction"] == "write" and edge["table_name"] not in placed:
                following.add(edge["table_name"])
        for name in sorted(following):
            table_hops[name] = hop
        placed.update(following)
        if following:
            name_layers.append(sorted(following))
        frontier = following

    join_edges = [
        edge
        for edge in get_join_edges(table_name)
        if edge["left_table"] != edge["right_table"]
    ]
    join_job_ids = {edge["job_id"] for edge in join_edges}
    jobs = {
        job["id"]: job for job in get_jobs_by_ids(sorted(visited_jobs | join_job_ids))
    }
    partner_names = {
        edge["right_table"] if edge["left_table"] == table_name else edge["left_table"]
        for edge in join_edges
    }
    for row in get_tables_by_names(sorted((placed | partner_names) - {table_name})):
        databases.setdefault(row["name"], row["database_name"])

    def job_ref(job_id: str) -> JobRef:
        return {"id": job_id, "label": _job_label(jobs.get(job_id), job_id)}

    def table_ref(name: str) -> TableRef:
        return {"database": databases.get(name), "table": name}

    join_refs: list[JoinRef] = []
    for edge in join_edges:
        side = "right" if edge["left_table"] == table_name else "left"
        partner = edge[f"{side}_table"]
        if edge[f"{side}_database"]:
            databases.setdefault(partner, edge[f"{side}_database"])
        join_refs.append(
            {
                "job": job_ref(edge["job_id"]),
                "partner": table_ref(partner),
                "evidence": edge["evidence"],
            }
        )

    def job_refs(hop_filter: Callable[[int], bool]) -> list[JobRef]:
        refs = [job_ref(job_id) for job_id, h in job_hops.items() if hop_filter(h)]
        return sorted(refs, key=lambda ref: ref["label"])

    def table_refs(hop_filter: Callable[[int], bool]) -> list[TableRef]:
        refs = [table_ref(name) for name, h in table_hops.items() if hop_filter(h)]
        return sorted(refs, key=lambda ref: (ref["database"] or "", ref["table"]))

    direct_jobs = job_refs(lambda h: h == 1)
    transitive_jobs = job_refs(lambda h: h > 1)
    direct_tables = table_refs(lambda h: h == 1)
    transitive_tables = table_refs(lambda h: h > 1)
    layers = [
        [_key(databases.get(name), name) for name in names] for names in name_layers
    ]
    return {
        "database": database_name,
        "table": table_name,
        "in_catalog": in_catalog,
        "direct_jobs": direct_jobs,
        "direct_tables": direct_tables,
        "join_refs": join_refs,
        "transitive_jobs": transitive_jobs,
        "transitive_tables": transitive_tables,
        "layers": layers,
        "has_dependents": bool(direct_jobs or join_refs),
    }


def format_report(report: DependentsReport) -> str:
    """
    Render a dependents report as the human-readable listing.

    Args:
        report: the dependents report to render

    Returns:
        The multi-line listing
    """
    focus = _key(report["database"] or None, report["table"])
    if not report["has_dependents"]:
        return f"{focus} has no dependents"
    lines = [f"{focus} has dependents:", ""]
    if report["direct_jobs"]:
        lines.append(f"  jobs reading {focus} ({len(report['direct_jobs'])}):")
        lines += [f"    - {job['label']}" for job in report["direct_jobs"]]
    if report["direct_tables"]:
        lines.append(
            f"  tables written by those jobs ({len(report['direct_tables'])}):"
        )
        lines += [
            f"    - {_key(table['database'], table['table'])}"
            for table in report["direct_tables"]
        ]
    if report["join_refs"]:
        joins = sorted(
            {
                f"    - {ref['job']['label']} joins {focus} <-> "
                f"{_key(ref['partner']['database'], ref['partner']['table'])}"
                for ref in report["join_refs"]
            }
        )
        lines.append(f"  join references ({len(joins)}):")
        lines += joins
    if report["transitive_tables"] or report["transitive_jobs"]:
        lines.append(
            f"  transitive blast radius: {len(report['transitive_tables'])} more "
            f"table(s), {len(report['transitive_jobs'])} more job(s)"
        )
        lines += [
            f"    - {_key(table['database'], table['table'])}"
            for table in report["transitive_tables"]
        ]
    job_ids = {job["id"] for job in report["direct_jobs"] + report["transitive_jobs"]}
    job_ids |= {ref["job"]["id"] for ref in report["join_refs"]}
    tables = len(report["direct_tables"]) + len(report["transitive_tables"])
    verdict = (
        f"NOT SAFE: deleting {focus} breaks {len(job_ids)} job(s) "
        f"and orphans {tables} table(s)"
    )
    lines += ["", verdict]
    return "\n".join(lines)
