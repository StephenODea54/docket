from docket.lineage import collect_dependents, format_report


def make_table_row(database_name, name):
    return {"database_name": database_name, "name": name}


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


def make_edge_fetchers(edges):
    def get_table_edges(table_names):
        return [edge for edge in edges if edge["table_name"] in set(table_names)]

    def get_job_edges(job_ids):
        return [edge for edge in edges if edge["job_id"] in set(job_ids)]

    return get_table_edges, get_job_edges


def make_join_fetcher(edges):
    def get_join_edges(table_name):
        return [
            edge
            for edge in edges
            if table_name in (edge["left_table"], edge["right_table"])
        ]

    return get_join_edges


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


def collect(edges, join_edges=(), jobs=None, tables=(), table="orders"):
    get_table_edges, get_job_edges = make_edge_fetchers(edges)
    return collect_dependents(
        "raw",
        table,
        get_table_edges,
        get_job_edges,
        make_join_fetcher(list(join_edges)),
        make_jobs_fetcher(jobs or {}),
        make_tables_fetcher(list(tables)),
    )


def test_direct_readers_and_written_tables():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "summary", "write", database_name="analytics"),
        make_table_edge("job-up", "source", "read"),
        make_table_edge("job-up", "orders", "write"),
    ]
    report = collect(edges, jobs={"job-1": "reporter", "job-up": "loader"})

    assert report["direct_jobs"] == [{"id": "job-1", "label": "glue: reporter"}]
    assert report["direct_tables"] == [{"database": "analytics", "table": "summary"}]
    assert report["transitive_jobs"] == []
    assert report["transitive_tables"] == []
    assert report["layers"] == [["analytics.summary"]]
    assert report["has_dependents"] is True


def test_transitive_hops_land_in_blast_radius():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "summary", "write"),
        make_table_edge("job-2", "summary", "read"),
        make_table_edge("job-2", "rollup", "write", database_name="analytics"),
    ]
    report = collect(edges, jobs={"job-1": "reporter", "job-2": "roller"})

    assert report["direct_tables"] == [{"database": "raw", "table": "summary"}]
    assert report["transitive_jobs"] == [{"id": "job-2", "label": "glue: roller"}]
    assert report["transitive_tables"] == [{"database": "analytics", "table": "rollup"}]
    assert report["layers"] == [["raw.summary"], ["analytics.rollup"]]


def test_join_references_count_as_dependents():
    report = collect(
        [],
        join_edges=[make_join_edge()],
        jobs={"job-1": "etl"},
        tables=[make_table_row("crm", "customers")],
    )

    assert report["direct_jobs"] == []
    assert report["join_refs"] == [
        {
            "job": {"id": "job-1", "label": "glue: etl"},
            "partner": {"database": "crm", "table": "customers"},
            "evidence": "orders.customer_id = customers.id",
        }
    ]
    assert report["has_dependents"] is True


def test_self_join_is_skipped():
    edge = make_join_edge(right_table="orders", right_database="raw")
    report = collect([], join_edges=[edge])

    assert report["join_refs"] == []
    assert report["has_dependents"] is False


def test_cycle_back_to_focus_terminates():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "staging", "write"),
        make_table_edge("job-2", "staging", "read"),
        make_table_edge("job-2", "orders", "write"),
    ]
    report = collect(edges, jobs={"job-1": "etl", "job-2": "loop"})

    tables = [table["table"] for table in report["direct_tables"]]
    assert tables == ["staging"]
    assert report["transitive_tables"] == []
    assert {job["id"] for job in report["transitive_jobs"]} == {"job-2"}


def test_self_loop_job_yields_job_but_not_focus_table():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "orders", "write"),
    ]
    report = collect(edges, jobs={"job-1": "compactor"})

    assert report["direct_jobs"] == [{"id": "job-1", "label": "glue: compactor"}]
    assert report["direct_tables"] == []
    assert report["layers"] == []


def test_unknown_job_falls_back_to_id():
    edges = [make_table_edge("job-x", "orders", "read")]
    report = collect(edges)

    assert report["direct_jobs"] == [{"id": "job-x", "label": "job-x"}]


def test_databases_backfilled_from_catalog():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "summary", "write", database_name=None),
    ]
    report = collect(
        edges,
        jobs={"job-1": "reporter"},
        tables=[make_table_row("analytics", "summary")],
    )

    assert report["direct_tables"] == [{"database": "analytics", "table": "summary"}]


def test_empty_graph_has_no_dependents():
    report = collect([])

    assert report["has_dependents"] is False
    assert report["layers"] == []


def test_format_report_lists_sections_and_verdict():
    edges = [
        make_table_edge("job-1", "orders", "read"),
        make_table_edge("job-1", "summary", "write", database_name="analytics"),
        make_table_edge("job-2", "summary", "read"),
        make_table_edge("job-2", "rollup", "write", database_name="analytics"),
    ]
    report = collect(
        edges,
        join_edges=[make_join_edge()],
        jobs={"job-1": "reporter", "job-2": "roller"},
        tables=[make_table_row("crm", "customers")],
    )
    text = format_report(report)

    assert "raw.orders has dependents:" in text
    assert "jobs reading raw.orders (1):" in text
    assert "- glue: reporter" in text
    assert "tables written by those jobs (1):" in text
    assert "- analytics.summary" in text
    assert "join references (1):" in text
    assert "- glue: reporter joins raw.orders <-> crm.customers" in text
    assert "transitive blast radius: 1 more table(s), 1 more job(s)" in text
    assert "NOT SAFE: deleting raw.orders breaks 2 job(s) and orphans 2 table(s)" in text


def test_format_report_clean():
    assert format_report(collect([])) == "raw.orders has no dependents"
