import json
from hashlib import sha256

from ...db.catalog_jobs import CatalogJobSelect
from ..file_readers import SourceFile
from .models import JobEdges

SYSTEM_PROMPT = """\
You are a static analyzer for AWS ETL code. You are given the source files of \
one job (a Glue script or Lambda package). Extract only what the code evidences:

- table_edges: tables/datasets the code reads or writes (Glue catalog reads, \
spark.sql, Athena queries, boto3 get_table, JDBC reads, writes/overwrites to \
catalog tables or their S3 locations). direction is "read" or "write".
- join_edges: column-level relationships between two tables: SQL JOIN ... ON \
predicates, DataFrame .join(on=...) keys, pandas merge(left_on=/right_on=/on=) \
keys, or equality filters that relate a column of one table to a column of \
another.

Rules:
- Report only what appears in the code. Every edge must include a short \
verbatim evidence snippet quoting the line(s) it came from.
- If a name is built at runtime (job arguments, environment variables, \
f-strings), set is_dynamic=true and give the best static approximation of the \
name.
- Normalize names to lowercase database/table form when the code makes the \
database clear; otherwise set the database to null.
- Resolve intermediate dataframes/CTEs/temp views back to the underlying \
tables when reporting join_edges; never report a temp view or variable name \
as a table.
- Empty lists are correct answers. Do not guess.
"""

PROMPT_VERSION = sha256(
    SYSTEM_PROMPT.encode()
    + json.dumps(JobEdges.model_json_schema(), sort_keys=True).encode()
).hexdigest()[:16]


def build_user_content(job: CatalogJobSelect, sources: list[SourceFile]) -> str:
    """
    Render one job's metadata and source files as the user message.

    Args:
        job: the catalog job the sources belong to
        sources: the job's source files

    Returns:
        The user message content
    """
    header = (
        f"job name: {job['name']}\n"
        f"job type: {job['type']}\n"
        f"runtime: {job['runtime'] or 'unknown'}"
    )
    files = [
        f"<file path={source['path']}>\n{source['contents']}\n</file>"
        for source in sources
    ]
    return "\n\n".join([header, *files])
