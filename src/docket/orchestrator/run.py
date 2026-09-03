from collections.abc import Mapping, Sequence
from typing import Any, cast

from ..config.logger import get_logger
from ..db import DB
from ..db.aws_glue_jobs import AwsGlueJobSelect
from ..db.aws_lambda_functions import AwsLambdaFunctionSelect
from ..db.catalog_job_artifacts import CatalogJobArtifactInsert
from ..db.catalog_job_extractions import CatalogJobExtractionInsert
from ..db.catalog_job_table_edges import CatalogJobTableEdgeInsert
from ..db.catalog_jobs import CatalogJobSelect
from ..db.catalog_table_join_edges import CatalogTableJoinEdgeInsert
from .edge_extractors import EdgeExtractorStrategy, sync_job_edges
from .file_readers import GlueScriptStrategy, LambdaPackageStrategy, SourceFile

logger = get_logger("run")

JobKey = tuple[str, str]


def _job_key(job: CatalogJobSelect) -> JobKey:
    """
    Return the stable identity of a catalog job across repopulations.

    Args:
        job: catalog job row

    Returns:
        The job's (type, name) pair
    """
    return (job["type"], job["name"])


def _rehome_job_rows(
    rows: Sequence[Mapping[str, Any]],
    old_keys: Mapping[str, JobKey],
    new_ids: Mapping[JobKey, str],
) -> list[dict[str, Any]]:
    """
    Rebuild job-keyed rows against freshly inserted job ids.

    Rows whose job no longer exists are dropped.

    Args:
        rows: previously selected rows carrying an id and a job_id
        old_keys: job key per pre-truncation job id
        new_ids: post-repopulation job id per job key

    Returns:
        Insert rows pointing at the new job ids
    """
    rehomed = []
    for row in rows:
        key = old_keys.get(row["job_id"])
        new_id = new_ids.get(key) if key else None
        if new_id is None:
            continue
        insert = {name: value for name, value in row.items() if name != "id"}
        insert["job_id"] = new_id
        rehomed.append(insert)
    return rehomed


def _build_artifact_rows(
    glue_jobs: Sequence[AwsGlueJobSelect],
    lambda_functions: Sequence[AwsLambdaFunctionSelect],
    glue_scripts: GlueScriptStrategy,
    new_ids: Mapping[JobKey, str],
) -> list[CatalogJobArtifactInsert]:
    """
    Build catalog_job_artifacts rows for every repopulated job.

    Args:
        glue_jobs: glue jobs as read from AWS
        lambda_functions: lambda functions as read from AWS
        glue_scripts: strategy that resolves a glue job's script uris
        new_ids: post-repopulation job id per job key

    Returns:
        catalog_job_artifacts insert rows
    """
    rows: list[CatalogJobArtifactInsert] = []
    for record in glue_jobs:
        job_id = new_ids[("glue", record["name"])]
        for uri in dict.fromkeys(glue_scripts.get_uris(record)):
            rows.append({"job_id": job_id, "reference": uri})
    for record in lambda_functions:
        if not record["arn"]:
            logger.warning("function %s has no arn, skipping artifact", record["name"])
            continue
        rows.append(
            {"job_id": new_ids[("lambda", record["name"])], "reference": record["arn"]}
        )
    return rows


def run(db: DB, extractor: EdgeExtractorStrategy) -> list[str]:
    """
    Rebuild the catalog from AWS and extract edges for jobs whose sources changed.

    Migrates the schema, reads the AWS inventory and job sources, then
    truncates and repopulates the catalog in one transaction. Cached
    extractions and edges are carried over to the new job rows by (type,
    name), so dropped AWS resources disappear and only changed jobs hit
    the extractor.

    Args:
        db: the docket database
        extractor: the extraction strategy to run on stale jobs

    Returns:
        The ids of the jobs that were re-extracted
    """
    db.migrate()

    databases = db.clients["aws_glue_databases"].get_databases()
    tables = db.clients["aws_glue_tables"].get_tables()
    glue_jobs = db.clients["aws_glue_jobs"].get_jobs()
    lambda_functions = db.clients["aws_lambda_functions"].get_functions()

    glue_scripts = GlueScriptStrategy(db.clients["aws_s3_objects"])
    lambda_packages = LambdaPackageStrategy(db.clients["aws_lambda_functions"])
    sources: dict[JobKey, list[SourceFile]] = {}
    for record in glue_jobs:
        sources[("glue", record["name"])] = glue_scripts.get_source_files(record)
    for record in lambda_functions:
        sources[("lambda", record["name"])] = lambda_packages.get_source_files(record)

    old_keys = {
        job["id"]: _job_key(job) for job in db.clients["catalog_jobs"].get_jobs()
    }
    old_extractions = db.clients["catalog_job_extractions"].get_extractions()
    old_table_edges = db.clients["catalog_job_table_edges"].get_edges()
    old_join_edges = db.clients["catalog_table_join_edges"].get_edges()

    with db.transaction():
        db.clients["catalog_table_join_edges"].delete_edges()
        db.clients["catalog_job_table_edges"].delete_edges()
        db.clients["catalog_job_extractions"].delete_extractions()
        db.clients["catalog_job_artifacts"].delete_artifacts()
        db.clients["catalog_jobs"].delete_jobs()
        db.clients["catalog_tables"].delete_tables()
        db.clients["catalog_databases"].delete_databases()

        if databases:
            db.clients["catalog_databases"].insert_databases(databases)
        if tables:
            db.clients["catalog_tables"].insert_tables(tables)
        jobs: list[CatalogJobSelect] = []
        if glue_jobs or lambda_functions:
            jobs = db.clients["catalog_jobs"].insert_jobs(glue_jobs, lambda_functions)
        new_ids = {_job_key(job): job["id"] for job in jobs}

        artifact_rows = _build_artifact_rows(
            glue_jobs, lambda_functions, glue_scripts, new_ids
        )
        if artifact_rows:
            db.clients["catalog_job_artifacts"].insert_artifacts(artifact_rows)

        extraction_rows = cast(
            list[CatalogJobExtractionInsert],
            _rehome_job_rows(old_extractions, old_keys, new_ids),
        )
        if extraction_rows:
            db.clients["catalog_job_extractions"].insert_extractions(extraction_rows)
        table_edge_rows = cast(
            list[CatalogJobTableEdgeInsert],
            _rehome_job_rows(old_table_edges, old_keys, new_ids),
        )
        if table_edge_rows:
            db.clients["catalog_job_table_edges"].insert_edges(table_edge_rows)
        join_edge_rows = cast(
            list[CatalogTableJoinEdgeInsert],
            _rehome_job_rows(old_join_edges, old_keys, new_ids),
        )
        if join_edge_rows:
            db.clients["catalog_table_join_edges"].insert_edges(join_edge_rows)

    pairs = [(job, sources.get(_job_key(job), [])) for job in jobs]
    return sync_job_edges(
        extractor,
        pairs,
        db.clients["catalog_job_extractions"],
        db.clients["catalog_job_table_edges"],
        db.clients["catalog_table_join_edges"],
    )
