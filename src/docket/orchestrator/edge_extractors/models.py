from typing import Literal

from pydantic import BaseModel, Field


class JobTableEdge(BaseModel):
    database: str | None
    table: str
    direction: Literal["read", "write"]
    is_dynamic: bool
    evidence: str


class TableJoinEdge(BaseModel):
    left_database: str | None
    left_table: str
    left_column: str
    right_database: str | None
    right_table: str
    right_column: str
    evidence: str


class JobEdges(BaseModel):
    table_edges: list[JobTableEdge] = Field(default_factory=list)
    join_edges: list[TableJoinEdge] = Field(default_factory=list)
