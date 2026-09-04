import json

from docket.web.graph import accent, build_dag, build_erd


def make_table_row(database_name, name, partitions=()):
    return {
        "database_name": database_name,
        "name": name,
        "partition_keys": json.dumps(
            [{"Name": partition, "Type": "string"} for partition in partitions]
        ),
    }


def make_join_edge(**overrides):
    edge = {
        "id": "edge-1",
        "job_id": "job-1",
        "left_database": "raw",
        "left_table": "orders",
        "left_column": "customer_id",
        "right_database": None,
        "right_table": "customers",
        "right_column": "id",
        "evidence": "orders.customer_id = customers.id",
    }
    edge.update(overrides)
    return edge


def make_table_edge(job_id, table_name, direction, database_name="raw"):
    return {
        "id": f"{job_id}-{table_name}-{direction}",
        "job_id": job_id,
        "database_name": database_name,
        "table_name": table_name,
        "direction": direction,
        "is_dynamic": False,
        "evidence": "select",
    }


def make_edge_fetchers(edges):
    def get_table_edges(table_names):
        return [edge for edge in edges if edge["table_name"] in set(table_names)]

    def get_job_edges(job_ids):
        return [edge for edge in edges if edge["job_id"] in set(job_ids)]

    return get_table_edges, get_job_edges


def make_jobs_fetcher(names_by_id):
    def get_jobs_by_ids(job_ids):
        return [
            {"id": job_id, "type": "glue", "name": names_by_id[job_id]}
            for job_id in job_ids
            if job_id in names_by_id
        ]

    return get_jobs_by_ids


def make_tables_fetcher(rows):
    def get_tables_by_names(names):
        return [row for row in rows if row["name"] in set(names)]

    return get_tables_by_names


def test_accent_is_stable_and_bounded():
    assert accent("raw") == accent("raw")
    assert 1 <= accent("raw") <= 6


def test_build_erd_cards_show_partitions_then_join_columns():
    table_row = make_table_row("raw", "orders", partitions=("ds",))
    figure = build_erd(
        "raw",
        "orders",
        table_row,
        [make_join_edge()],
        make_tables_fetcher([make_table_row("raw", "customers")]),
        make_jobs_fetcher({"job-1": "etl"}),
    )

    focus = figure["layers"][0][0]
    assert focus["key"] == "raw.orders"
    assert focus["focus"] is True
    assert focus["rows"] == [
        {"name": "ds", "partition": True},
        {"name": "customer_id", "partition": False},
    ]
    partner = figure["layers"][1][0]
    assert partner["key"] == "raw.customers"
    assert partner["rows"] == [{"name": "id", "partition": False}]


def test_build_erd_arrows_anchor_columns_and_merge_jobs():
    edges = [
        make_join_edge(),
        make_join_edge(id="edge-2", job_id="job-2"),
    ]
    figure = build_erd(
        "raw",
        "orders",
        make_table_row("raw", "orders"),
        edges,
        make_tables_fetcher([make_table_row("raw", "customers")]),
        make_jobs_fetcher({"job-1": "etl", "job-2": "sync"}),
    )

    assert figure["arrows"] == [
        {
            "a": "raw.orders.customer_id",
            "b": "raw.customers.id",
            "ta": "raw.orders",
            "tb": "raw.customers",
            "job": "glue: etl, glue: sync",
        }
    ]


def test_build_erd_resolves_missing_database_from_catalog():
    figure = build_erd(
        "raw",
        "orders",
        make_table_row("raw", "orders"),
        [make_join_edge()],
        make_tables_fetcher([make_table_row("crm", "customers")]),
        make_jobs_fetcher({}),
    )

    assert figure["layers"][1][0]["key"] == "crm.customers"


def test_build_erd_without_edges_renders_lone_focus():
    figure = build_erd(
        "raw",
        "orders",
        make_table_row("raw", "orders"),
        [],
        make_tables_fetcher([]),
        make_jobs_fetcher({}),
    )

    assert len(figure["layers"]) == 1
    assert figure["arrows"] == []


def test_build_dag_layers_upstream_and_downstream():
    edges = [
        make_table_edge("job-up", "source", "read"),
        make_table_edge("job-up", "orders", "write"),
        make_table_edge("job-down", "orders", "read"),
        make_table_edge("job-down", "summary", "write", database_name="analytics"),
    ]
    get_table_edges, get_job_edges = make_edge_fetchers(edges)

    figure = build_dag(
        "raw",
        "orders",
        get_table_edges,
        get_job_edges,
        make_jobs_fetcher({"job-up": "loader", "job-down": "reporter"}),
        make_tables_fetcher([make_table_row("raw", "orders")]),
    )

    keys = [[card["key"] for card in layer] for layer in figure["layers"]]
    assert keys == [["raw.source"], ["raw.orders"], ["analytics.summary"]]
    assert figure["layers"][1][0]["focus"] is True
    assert sorted(figure["arrows"], key=lambda arrow: arrow["a"]) == [
        {
            "a": "raw.orders",
            "b": "analytics.summary",
            "ta": "raw.orders",
            "tb": "analytics.summary",
            "head": "b",
            "job": "glue: reporter",
        },
        {
            "a": "raw.source",
            "b": "raw.orders",
            "ta": "raw.source",
            "tb": "raw.orders",
            "head": "b",
            "job": "glue: loader",
        },
    ]


def test_build_dag_dedupes_cycles():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "staging", "write"),
        make_table_edge("job-2", "staging", "read"),
        make_table_edge("job-2", "orders", "write"),
    ]
    get_table_edges, get_job_edges = make_edge_fetchers(edges)

    figure = build_dag(
        "raw",
        "orders",
        get_table_edges,
        get_job_edges,
        make_jobs_fetcher({"job-1": "etl", "job-2": "loop"}),
        make_tables_fetcher([]),
    )

    keys = [card["key"] for layer in figure["layers"] for card in layer]
    assert keys.count("raw.orders") == 1
    assert keys.count("raw.staging") == 1


def test_build_dag_respects_depth():
    edges = [
        make_table_edge("job-1", "a", "read"),
        make_table_edge("job-1", "b", "write"),
        make_table_edge("job-2", "b", "read"),
        make_table_edge("job-2", "c", "write"),
    ]
    get_table_edges, get_job_edges = make_edge_fetchers(edges)

    figure = build_dag(
        "raw",
        "a",
        get_table_edges,
        get_job_edges,
        make_jobs_fetcher({"job-1": "one", "job-2": "two"}),
        make_tables_fetcher([]),
        depth=1,
    )

    keys = [card["key"] for layer in figure["layers"] for card in layer]
    assert "raw.b" in keys
    assert "raw.c" not in keys


def test_build_dag_without_edges_renders_lone_focus():
    get_table_edges, get_job_edges = make_edge_fetchers([])

    figure = build_dag(
        "raw",
        "orders",
        get_table_edges,
        get_job_edges,
        make_jobs_fetcher({}),
        make_tables_fetcher([]),
    )

    assert [[card["key"] for card in layer] for layer in figure["layers"]] == [
        ["raw.orders"]
    ]
    assert figure["arrows"] == []
