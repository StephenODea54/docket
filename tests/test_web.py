import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from sustained import Model
from sustained.migrations import Migrator

from docket.db.aws_glue_databases import AwsGlueDatabaseSelect
from docket.db.aws_glue_jobs import AwsGlueJobSelect
from docket.db.aws_glue_tables import AwsGlueTableSelect
from docket.db.catalog_databases import CatalogDatabaseClient
from docket.db.catalog_job_table_edges import CatalogJobTableEdgeClient
from docket.db.catalog_jobs import CatalogJobClient
from docket.db.catalog_table_join_edges import CatalogTableJoinEdgeClient
from docket.db.catalog_tables import CatalogTableClient
from docket.db.db import ALL_MODELS
from docket.web import create_app


class FakeDB:
    def __init__(self, conn):
        self.conn = conn
        self.clients = {
            "catalog_databases": CatalogDatabaseClient(conn),
            "catalog_jobs": CatalogJobClient(conn),
            "catalog_job_table_edges": CatalogJobTableEdgeClient(conn),
            "catalog_table_join_edges": CatalogTableJoinEdgeClient(conn),
            "catalog_tables": CatalogTableClient(conn),
        }


def make_glue_database(name):
    record = dict.fromkeys(AwsGlueDatabaseSelect.__annotations__)
    record["name"] = name
    return record


def make_glue_table(database_name, name, columns=(), partitions=()):
    record = dict.fromkeys(AwsGlueTableSelect.__annotations__)
    record["database_name"] = database_name
    record["name"] = name
    record["description"] = f"{name} table"
    record["storage_descriptor"] = json.dumps(
        {
            "Columns": [
                {"Name": column_name, "Type": column_type, "Comment": None}
                for column_name, column_type in columns
            ],
            "Location": f"s3://bucket/{name}",
        }
    )
    record["partition_keys"] = json.dumps(
        [{"Name": partition, "Type": "string"} for partition in partitions]
    )
    return record


def make_glue_job(name):
    record = dict.fromkeys(AwsGlueJobSelect.__annotations__)
    record["name"] = name
    record["command"] = json.dumps({"ScriptLocation": f"s3://bucket/{name}.py"})
    return record


@pytest.fixture
def client():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("pragma foreign_keys = on")
    Model.bind(conn)
    Migrator(conn, []).up(models=ALL_MODELS)
    db = FakeDB(conn)
    with Model.transaction():
        db.clients["catalog_databases"].insert_databases(
            [make_glue_database("raw"), make_glue_database("analytics")]
        )
        db.clients["catalog_tables"].insert_tables(
            [
                make_glue_table(
                    "raw",
                    "orders",
                    columns=[("id", "bigint"), ("customer_id", "bigint")],
                    partitions=("ds",),
                ),
                make_glue_table("raw", "customers", columns=[("id", "bigint")]),
                make_glue_table("analytics", "orders_summary"),
            ]
        )
        jobs = db.clients["catalog_jobs"].insert_jobs(
            glue_jobs=[make_glue_job("orders_etl"), make_glue_job("summary_sync")]
        )
        job_ids = {job["name"]: job["id"] for job in jobs}
        db.clients["catalog_job_table_edges"].insert_edges(
            [
                {
                    "job_id": job_ids["orders_etl"],
                    "database_name": "raw",
                    "table_name": "orders",
                    "direction": "read",
                    "is_dynamic": False,
                    "evidence": "spark.table('raw.orders')",
                },
                {
                    "job_id": job_ids["orders_etl"],
                    "database_name": "analytics",
                    "table_name": "orders_summary",
                    "direction": "write",
                    "is_dynamic": False,
                    "evidence": "write orders_summary",
                },
                {
                    "job_id": job_ids["summary_sync"],
                    "database_name": "analytics",
                    "table_name": "orders_summary",
                    "direction": "read",
                    "is_dynamic": False,
                    "evidence": "read orders_summary",
                },
                {
                    "job_id": job_ids["summary_sync"],
                    "database_name": "raw",
                    "table_name": "orders",
                    "direction": "write",
                    "is_dynamic": False,
                    "evidence": "write orders",
                },
            ]
        )
        db.clients["catalog_table_join_edges"].insert_edges(
            [
                {
                    "job_id": job_ids["orders_etl"],
                    "left_database": "raw",
                    "left_table": "orders",
                    "left_column": "customer_id",
                    "right_database": "raw",
                    "right_table": "customers",
                    "right_column": "id",
                    "evidence": "orders.customer_id = customers.id",
                }
            ]
        )
    yield TestClient(create_app(db))
    conn.close()


def test_index_lists_databases_and_tables(client):
    response = client.get("/")

    assert response.status_code == 200
    for name in ("raw", "analytics", "orders", "customers", "orders_summary"):
        assert name in response.text


def test_table_detail_renders_metadata_and_join_graph(client):
    response = client.get("/tables/raw/orders")

    assert response.status_code == 200
    assert "raw.orders" in response.text
    assert "customer_id" in response.text
    assert "s3://bucket/orders" in response.text
    assert "data-graph" in response.text
    assert 'data-col="raw.orders.customer_id"' in response.text
    assert 'data-col="raw.orders.ds"' in response.text
    assert 'data-table="raw.customers"' in response.text
    assert "raw.customers.id" in response.text
    assert "glue: orders_etl" in response.text
    assert "Written by" in response.text
    assert "Read by" in response.text
    assert "glue: summary_sync" in response.text
    assert "★" in response.text


def test_dag_renders_layers_and_flow_arrows(client):
    response = client.get("/dag/raw/orders")

    assert response.status_code == 200
    assert "raw.orders lineage" in response.text
    assert 'data-table="analytics.orders_summary"' in response.text
    assert "glue: orders_etl" in response.text
    assert "glue: summary_sync" in response.text
    assert '"head": "b"' in response.text


def test_dag_clamps_depth(client):
    response = client.get("/dag/raw/orders?depth=99")

    assert response.status_code == 200
    assert "raw.orders lineage" in response.text


def test_search_matches_columns_and_partitions(client):
    response = client.get("/search?q=customer")

    assert response.status_code == 200
    assert "raw.orders" in response.text
    assert "customer_id" in response.text

    response = client.get("/search?q=ds")

    assert response.status_code == 200
    assert "raw.orders" in response.text


def test_search_without_matches_or_query(client):
    assert "No columns match" in client.get("/search?q=zzz").text
    assert "Type a column name" in client.get("/search").text


def test_unknown_table_returns_404(client):
    for path in ("/tables/raw/missing", "/dag/raw/missing"):
        assert client.get(path).status_code == 404
