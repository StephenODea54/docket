import sqlite3
from uuid import uuid4

import pytest
from sustained import Model
from sustained.migrations import Migrator

from docket.db.catalog_job_extractions import CatalogJobExtractionClient
from docket.db.catalog_job_table_edges import CatalogJobTableEdgeClient
from docket.db.catalog_jobs import CatalogJobModel, CatalogJobSelect
from docket.db.catalog_table_join_edges import CatalogTableJoinEdgeClient
from docket.db.db import ALL_MODELS
from docket.orchestrator import FixtureEdgeExtractor, SourceFile, sync_job_edges
from docket.orchestrator.edge_extractors import JobEdges, hash_slinging_slasher
from docket.orchestrator.edge_extractors.models import JobTableEdge, TableJoinEdge

JOB_NAME = "orders_etl"


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("pragma foreign_keys = on")
    Model.bind(connection)
    Migrator(connection, []).up(models=ALL_MODELS)
    yield connection
    connection.close()


@pytest.fixture
def job(conn) -> CatalogJobSelect:
    row = {
        "id": str(uuid4()),
        "type": "glue",
        "name": JOB_NAME,
        "description": None,
        "role": None,
        "runtime": "3",
        "last_modified": None,
        "attributes": None,
    }
    CatalogJobModel.query().insert([row]).run()
    conn.commit()
    return row


def make_sources(contents: str = "select 1") -> list[SourceFile]:
    return [SourceFile(path="s3://bucket/etl.py", contents=contents)]


def make_edges() -> JobEdges:
    return JobEdges(
        table_edges=[
            JobTableEdge(
                database="raw",
                table="orders",
                direction="read",
                is_dynamic=False,
                evidence="spark.table('raw.orders')",
            ),
            JobTableEdge(
                database="raw",
                table="customers",
                direction="read",
                is_dynamic=False,
                evidence="spark.table('raw.customers')",
            ),
            JobTableEdge(
                database="mart",
                table="fct_orders",
                direction="write",
                is_dynamic=False,
                evidence="saveAsTable('mart.fct_orders')",
            ),
        ],
        join_edges=[
            TableJoinEdge(
                left_database="raw",
                left_table="orders",
                left_column="customer_id",
                right_database="raw",
                right_table="customers",
                right_column="id",
                evidence="orders.customer_id = customers.id",
            )
        ],
    )


def make_clients(conn):
    return (
        CatalogJobExtractionClient(conn),
        CatalogJobTableEdgeClient(conn),
        CatalogTableJoinEdgeClient(conn),
    )


def run_sync(extractor, job, sources, clients):
    extractions, job_table_edges, table_join_edges = clients
    return sync_job_edges(
        extractor=extractor,
        jobs=[(job, sources)],
        extractions=extractions,
        job_table_edges=job_table_edges,
        table_join_edges=table_join_edges,
    )


class TestHashSlingingSlasher:
    def test_is_stable(self):
        assert hash_slinging_slasher("m", make_sources()) == hash_slinging_slasher(
            "m", make_sources()
        )

    def test_ignores_source_order(self):
        sources = [
            SourceFile(path="a.py", contents="a"),
            SourceFile(path="b.py", contents="b"),
        ]
        assert hash_slinging_slasher("m", sources) == hash_slinging_slasher(
            "m", list(reversed(sources))
        )

    def test_changes_with_contents(self):
        first = hash_slinging_slasher("m", make_sources("select 1"))
        second = hash_slinging_slasher("m", make_sources("select 2"))
        assert first != second

    def test_changes_with_model(self):
        assert hash_slinging_slasher("m1", make_sources()) != hash_slinging_slasher(
            "m2", make_sources()
        )


class TestSyncJobEdges:
    def test_drops_unanchored_join_edges(self, conn, job):
        clients = make_clients(conn)
        edges = make_edges()
        edges.join_edges.append(
            TableJoinEdge(
                left_database=None,
                left_table="some_dataframe",
                left_column="id",
                right_database="raw",
                right_table="orders",
                right_column="id",
                evidence="some_dataframe.merge(orders, on='id')",
            )
        )
        extractor = FixtureEdgeExtractor({JOB_NAME: edges})

        run_sync(extractor, job, make_sources(), clients)

        _, _, table_join_edges = clients
        stored = table_join_edges.get_edges()
        assert [(e["left_table"], e["right_table"]) for e in stored] == [
            ("orders", "customers")
        ]

    def test_persists_extraction_and_edges(self, conn, job):
        clients = make_clients(conn)
        extractor = FixtureEdgeExtractor({JOB_NAME: make_edges()})

        refreshed = run_sync(extractor, job, make_sources(), clients)

        extractions, job_table_edges, table_join_edges = clients
        assert refreshed == [job["id"]]
        stored = extractions.get_extractions()
        assert len(stored) == 1
        assert stored[0]["model"] == "fixture"
        assert len(job_table_edges.get_edges()) == 3
        assert len(table_join_edges.get_edges()) == 1

    def test_skips_cached_job(self, conn, job):
        clients = make_clients(conn)
        extractor = FixtureEdgeExtractor({JOB_NAME: make_edges()})

        run_sync(extractor, job, make_sources(), clients)
        refreshed = run_sync(extractor, job, make_sources(), clients)

        assert refreshed == []
        assert extractor.calls == 1

    def test_reextracts_when_contents_change(self, conn, job):
        clients = make_clients(conn)
        extractor = FixtureEdgeExtractor({JOB_NAME: make_edges()})

        run_sync(extractor, job, make_sources("select 1"), clients)
        refreshed = run_sync(extractor, job, make_sources("select 2"), clients)

        assert refreshed == [job["id"]]
        assert extractor.calls == 2
        extractions, job_table_edges, _ = clients
        assert len(extractions.get_extractions()) == 1
        assert len(job_table_edges.get_edges()) == 3

    def test_skips_job_without_sources(self, conn, job):
        clients = make_clients(conn)
        extractor = FixtureEdgeExtractor({JOB_NAME: make_edges()})

        refreshed = run_sync(extractor, job, [], clients)

        assert refreshed == []
        assert extractor.calls == 0
