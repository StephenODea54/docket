from docket.web.diagrams import build_dag, build_erd


def make_join_edge(**overrides):
    edge = {
        "id": "edge-1",
        "job_id": "job-1",
        "left_database": "raw",
        "left_table": "orders",
        "left_column": "customer_id",
        "right_database": "raw",
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


def test_build_erd_renders_entities_columns_and_relationships():
    columns = {
        "orders": [{"Name": "customer_id", "Type": "decimal(10,2)", "Comment": None}],
        "customers": [{"Name": "id", "Type": "struct<a:string>", "Comment": "pk"}],
    }

    source = build_erd("orders", columns, [make_join_edge()])

    assert source.startswith("erDiagram")
    assert 'orders["orders"]' in source
    assert 'customers["customers"]' in source
    assert "decimal_10_2_ customer_id" in source
    assert 'struct_a_string_ id "pk"' in source
    assert 'orders ||--|| customers : "customer_id = id"' in source


def test_build_erd_sanitizes_entity_names():
    source = build_erd("weird table!", {"weird table!": []}, [])

    assert 'weird_table_["weird table!"]' in source


def test_build_erd_dedupes_repeated_joins():
    edges = [make_join_edge(), make_join_edge(id="edge-2", job_id="job-2")]

    source = build_erd("orders", {}, edges)

    assert source.count("||--||") == 1


def test_build_dag_directions_and_labels():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "summary", "write", database_name="analytics"),
    ]
    get_table_edges, get_job_edges = make_edge_fetchers(edges)

    source = build_dag(
        "orders", get_table_edges, get_job_edges, make_jobs_fetcher({"job-1": "etl"})
    )

    assert source.startswith("flowchart LR")
    assert 't_orders["raw.orders"]' in source
    assert 't_summary["analytics.summary"]' in source
    assert 'j_0(["glue: etl"])' in source
    assert "t_orders --> j_0" in source
    assert "j_0 --> t_summary" in source
    assert "class t_orders focus" in source


def test_build_dag_dedupes_cycles():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "staging", "write"),
        make_table_edge("job-2", "staging", "read"),
        make_table_edge("job-2", "orders", "write"),
    ]
    get_table_edges, get_job_edges = make_edge_fetchers(edges)

    source = build_dag(
        "orders",
        get_table_edges,
        get_job_edges,
        make_jobs_fetcher({"job-1": "etl", "job-2": "loop"}),
    )

    assert source.count('t_orders["raw.orders"]') == 1
    assert source.count("t_orders --> j_0") == 1
    assert source.count("j_1 --> t_orders") == 1


def test_build_dag_respects_depth_limit():
    edges = [
        make_table_edge("job-1", "a", "read"),
        make_table_edge("job-1", "b", "write"),
        make_table_edge("job-2", "b", "read"),
        make_table_edge("job-2", "c", "write"),
        make_table_edge("job-3", "c", "read"),
        make_table_edge("job-3", "d", "write"),
    ]
    get_table_edges, get_job_edges = make_edge_fetchers(edges)
    jobs = make_jobs_fetcher({"job-1": "one", "job-2": "two", "job-3": "three"})

    source = build_dag("a", get_table_edges, get_job_edges, jobs, max_depth=1)

    assert 't_b["raw.b"]' in source
    assert "t_c" not in source


def test_build_dag_without_edges_renders_lone_table():
    get_table_edges, get_job_edges = make_edge_fetchers([])

    source = build_dag("orders", get_table_edges, get_job_edges, make_jobs_fetcher({}))

    assert 't_orders["orders"]' in source
    assert "class t_orders focus" in source
