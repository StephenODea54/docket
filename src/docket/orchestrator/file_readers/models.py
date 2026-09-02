from typing import TypedDict


class SourceFile(TypedDict):
    path: str
    contents: str
