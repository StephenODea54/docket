from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sustained import Model

from ...config.env import env
from ...config.logger import get_logger
from ...db.catalog_job_extractions import (
    CatalogJobExtractionClient,
    CatalogJobExtractionInsert,
)
from ...db.catalog_job_table_edges import (
    CatalogJobTableEdgeClient,
    CatalogJobTableEdgeInsert,
)
from ...db.catalog_jobs import CatalogJobSelect
from ...db.catalog_table_join_edges import (
    CatalogTableJoinEdgeClient,
    CatalogTableJoinEdgeInsert,
)
from ..file_readers import SourceFile
from .cache import hash_slinging_slasher
from .edge_extractor_strategies import EdgeExtractorStrategy
from .models import JobEdges
from .prompt import PROMPT_VERSION

logger = get_logger("edge_extractors")

JobSources = tuple[CatalogJobSelect, list[SourceFile]]


def _build_table_edge_rows(
    job_id: str, edges: JobEdges
) -> list[CatalogJobTableEdgeInsert]:
    """
    Map extracted table edges to catalog_job_table_edges rows.

    Args:
        job_id: PK of the job the edges were extracted from
        edges: the job's extracted edges

    Returns:
        catalog_job_table_edges insert rows
    """
    return [
        {
            "job_id": job_id,
            "database_name": edge.database,
            "table_name": edge.table,
            "direction": edge.direction,
            "is_dynamic": edge.is_dynamic,
            "evidence": edge.evidence,
        }
        for edge in edges.table_edges
    ]


def _drop_unanchored_join_edges(job_name: str, edges: JobEdges) -> JobEdges:
    """
    Drop join edges naming tables the job's table_edges do not report.

    Extractors sometimes leak dataframe or CTE names into join_edges; a
    join is only kept when both of its tables were reported as read or
    written by the same job.

    Args:
        job_name: name of the job, for logging
        edges: the job's extracted edges

    Returns:
        The edges with unanchored join edges removed
    """
    tables = {edge.table for edge in edges.table_edges}
    kept = []
    for edge in edges.join_edges:
        if edge.left_table in tables and edge.right_table in tables:
            kept.append(edge)
            continue
        logger.warning(
            "dropping unanchored join edge %s.%s = %s.%s from %s",
            edge.left_table,
            edge.left_column,
            edge.right_table,
            edge.right_column,
            job_name,
        )
    if len(kept) == len(edges.join_edges):
        return edges
    return edges.model_copy(update={"join_edges": kept})


def _build_join_edge_rows(
    job_id: str, edges: JobEdges
) -> list[CatalogTableJoinEdgeInsert]:
    """
    Map extracted join edges to catalog_table_join_edges rows.

    Args:
        job_id: PK of the job the edges were extracted from
        edges: the job's extracted edges

    Returns:
        catalog_table_join_edges insert rows
    """
    return [
        {
            "job_id": job_id,
            "left_database": edge.left_database,
            "left_table": edge.left_table,
            "left_column": edge.left_column,
            "right_database": edge.right_database,
            "right_table": edge.right_table,
            "right_column": edge.right_column,
            "evidence": edge.evidence,
        }
        for edge in edges.join_edges
    ]


def sync_job_edges(
    extractor: EdgeExtractorStrategy,
    jobs: Sequence[JobSources],
    extractions: CatalogJobExtractionClient,
    job_table_edges: CatalogJobTableEdgeClient,
    table_join_edges: CatalogTableJoinEdgeClient,
) -> list[str]:
    """
    Extract and persist edges for every job whose sources changed.

    Args:
        extractor: the extraction strategy to run on stale jobs
        jobs: catalog jobs paired with their source files
        extractions: catalog_job_extractions client
        job_table_edges: catalog_job_table_edges client
        table_join_edges: catalog_table_join_edges client

    Returns:
        The ids of the jobs that were re-extracted
    """
    cached = extractions.get_cache_keys()
    stale: list[tuple[CatalogJobSelect, list[SourceFile], str]] = []
    for job, sources in jobs:
        if not sources:
            logger.info("skipping %s, no source files", job["name"])
            continue
        cache_key = hash_slinging_slasher(extractor.model, sources)
        if cached.get(job["id"]) == cache_key:
            logger.info("skipping %s, extraction is cached", job["name"])
            continue
        stale.append((job, sources, cache_key))
    if not stale:
        logger.info("all %s job(s) cached, nothing to extract", len(jobs))
        return []

    def extract_one(item: tuple[CatalogJobSelect, list[SourceFile], str]) -> JobEdges:
        """
        Extract one stale job's edges; runs on a worker thread.

        Args:
            item: the job, its source files, and its cache key

        Returns:
            The job's extracted edges
        """
        job, sources, _ = item
        logger.info("extracting edges from %s", job["name"])
        return _drop_unanchored_join_edges(job["name"], extractor.extract(job, sources))

    with ThreadPoolExecutor(max_workers=env.llm_concurrency) as pool:
        extracted = list(pool.map(extract_one, stale))

    extraction_rows: list[CatalogJobExtractionInsert] = []
    table_edge_rows: list[CatalogJobTableEdgeInsert] = []
    join_edge_rows: list[CatalogTableJoinEdgeInsert] = []
    for (job, sources, cache_key), edges in zip(stale, extracted):
        extraction_rows.append(
            {
                "job_id": job["id"],
                "cache_key": cache_key,
                "model": extractor.model,
                "prompt_version": PROMPT_VERSION,
                "extraction": edges.model_dump_json(),
                "extracted_at": datetime.now(timezone.utc),
            }
        )
        table_edge_rows.extend(_build_table_edge_rows(job["id"], edges))
        join_edge_rows.extend(_build_join_edge_rows(job["id"], edges))

    stale_ids = [job["id"] for job, _, _ in stale]
    with Model.transaction():
        extractions.delete_extractions_by_jobs(stale_ids)
        job_table_edges.delete_job_edges(stale_ids)
        table_join_edges.delete_job_edges(stale_ids)
        extractions.insert_extractions(extraction_rows)
        if table_edge_rows:
            job_table_edges.insert_edges(table_edge_rows)
        if join_edge_rows:
            table_join_edges.insert_edges(join_edge_rows)
    logger.info("extracted edges from %s job(s)", len(stale_ids))
    return stale_ids
