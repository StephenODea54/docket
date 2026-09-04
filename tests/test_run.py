import json
import sqlite3

import pytest
from sustained import Model
from sustained.migrations import Migrator

from docket.db.aws_glue_databases import AwsGlueDatabaseSelect
from docket.db.aws_glue_jobs import AwsGlueJobSelect
from docket.db.db import ALL_MODELS
from docket.orchestrator import FixtureEdgeExtractor, run
from docket.orchestrator.edge_extractors.models import JobEdges, JobTableEdge

JOB_NAME = "orders_etl"
SCRIPT_URI = "s3://bucket/etl.py"


def make_glue_database(name: str = "raw") -> AwsGlueDatabaseSelect:
    record = dict.fromkeys(AwsGlueDatabaseSelect.__annotations__)
    record["name"] = name
    return record


def make_glue_job(name: str = JOB_NAME, script: str = SCRIPT_URI) -> AwsGlueJobSelect:
    record = dict.fromkeys(AwsGlueJobSelect.__annotations__)
    record["name"] = name
    record["command"] = json.dumps({"ScriptLocation": script})
    return record


def make_edges() -> JobEdges:
    return JobEdges(
        table_edges=[
            JobTableEdge(
                database="raw",
                table="orders",
                direction="read",
                is_dynamic=False,
                evidence="spark.table('raw.orders')",
            )
        ],
        join_edges=[],
    )


class FakeAwsGlueDatabaseClient:
    def __init__(self, records):
        self.records = records

    def get_databases(self):
        return self.records


class FakeAwsGlueTableClient:
    def get_tables(self):
        return []


class FakeAwsGlueJobClient:
    def __init__(self, records):
        self.records = records

    def get_jobs(self):
        return self.records


class FakeAwsLambdaFunctionClient:
    def get_functions(self):
        return []


class FakeAwsS3ObjectClient:
    def __init__(self, bodies):
        self.bodies = bodies

    def get_object(self, bucket_name, key):
        body = self.bodies.get(f"s3://{bucket_name}/{key}")
        if body is None:
            return None
        return {"bucket_name": bucket_name, "key": key, "body": body}


class FakeDB:
    def __init__(self, conn, glue_jobs, bodies, glue_databases=()):
        from docket.db.catalog_databases import CatalogDatabaseClient
        from docket.db.catalog_job_artifacts import CatalogJobArtifactClient
        from docket.db.catalog_job_extractions import CatalogJobExtractionClient
        from docket.db.catalog_job_table_edges import CatalogJobTableEdgeClient
        from docket.db.catalog_jobs import CatalogJobClient
        from docket.db.catalog_table_join_edges import CatalogTableJoinEdgeClient
        from docket.db.catalog_tables import CatalogTableClient

        self.conn = conn
        self.clients = {
            "aws_glue_databases": FakeAwsGlueDatabaseClient(list(glue_databases)),
            "aws_glue_jobs": FakeAwsGlueJobClient(glue_jobs),
            "aws_glue_tables": FakeAwsGlueTableClient(),
            "aws_lambda_functions": FakeAwsLambdaFunctionClient(),
            "aws_s3_objects": FakeAwsS3ObjectClient(bodies),
            "catalog_databases": CatalogDatabaseClient(conn),
            "catalog_jobs": CatalogJobClient(conn),
            "catalog_job_artifacts": CatalogJobArtifactClient(conn),
            "catalog_job_extractions": CatalogJobExtractionClient(conn),
            "catalog_job_table_edges": CatalogJobTableEdgeClient(conn),
            "catalog_table_join_edges": CatalogTableJoinEdgeClient(conn),
            "catalog_tables": CatalogTableClient(conn),
        }

    def migrate(self):
        return Migrator(self.conn, []).up(models=ALL_MODELS)

    def transaction(self):
        return Model.transaction()


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("pragma foreign_keys = on")
    Model.bind(connection)
    yield connection
    connection.close()


def make_db(conn, script_body="select 1", job_names=(JOB_NAME,)):
    return FakeDB(
        conn,
        glue_jobs=[make_glue_job(name) for name in job_names],
        bodies={SCRIPT_URI: script_body},
        glue_databases=[make_glue_database()],
    )


def make_extractor():
    return FixtureEdgeExtractor({JOB_NAME: make_edges()})


def test_run_populates_catalog_and_extracts(conn):
    db = make_db(conn)
    extractor = make_extractor()

    extracted = run(db, extractor)

    jobs = db.clients["catalog_jobs"].get_jobs()
    assert [job["id"] for job in jobs] == extracted
    assert extractor.calls == 1
    artifacts = db.clients["catalog_job_artifacts"].get_artifacts()
    assert [(a["job_id"], a["reference"]) for a in artifacts] == [
        (jobs[0]["id"], SCRIPT_URI)
    ]
    assert len(db.clients["catalog_databases"].get_databases()) == 1
    edges = db.clients["catalog_job_table_edges"].get_edges()
    assert [(e["job_id"], e["table_name"]) for e in edges] == [
        (jobs[0]["id"], "orders")
    ]


def test_run_rehomes_cache_on_unchanged_sources(conn):
    extractor = make_extractor()
    run(make_db(conn), extractor)

    extracted = run(make_db(conn), extractor)

    assert extracted == []
    assert extractor.calls == 1
    db = FakeDB(conn, [], {})
    jobs = db.clients["catalog_jobs"].get_jobs()
    assert len(jobs) == 1
    edges = db.clients["catalog_job_table_edges"].get_edges()
    assert [(e["job_id"], e["table_name"]) for e in edges] == [
        (jobs[0]["id"], "orders")
    ]
    extractions = db.clients["catalog_job_extractions"].get_extractions()
    assert [e["job_id"] for e in extractions] == [jobs[0]["id"]]


def test_run_reextracts_when_sources_change(conn):
    extractor = make_extractor()
    run(make_db(conn, script_body="select 1"), extractor)

    extracted = run(make_db(conn, script_body="select 2"), extractor)

    assert len(extracted) == 1
    assert extractor.calls == 2


def test_run_drops_orphaned_jobs(conn):
    extractor = make_extractor()
    run(make_db(conn), extractor)

    extracted = run(make_db(conn, job_names=()), extractor)

    assert extracted == []
    assert extractor.calls == 1
    db = FakeDB(conn, [], {})
    assert db.clients["catalog_jobs"].get_jobs() == []
    assert db.clients["catalog_job_extractions"].get_extractions() == []
    assert db.clients["catalog_job_table_edges"].get_edges() == []
    assert db.clients["catalog_job_artifacts"].get_artifacts() == []
