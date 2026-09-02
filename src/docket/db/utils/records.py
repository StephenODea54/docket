import json
from collections.abc import Mapping, Sequence
from typing import Any

from sustained import Model


def decode_column(model: type[Model], row: Mapping[str, Any], column: str) -> Any:
    """
    Return a column value from a row, parsing json strings held by Json columns.

    Args:
        model: generic sustained Model
        row: generic dict

    Returns:
        decoded representation of the row (any).
    """
    value = row[column]
    if isinstance(value, str) and model.tableColumns[column].type_name == "JSON":
        return json.loads(value) if value else None
    return value


def serialize_columns(
    model: type[Model], row: Mapping[str, Any], columns: Sequence[str]
) -> str:
    """
    Serialize the given columns of a row into one json document.

    Args:
        model: generic sustained model
        row: generic dict
        columns: list of column names

    Returns:
        String serialization of the columns.
    """
    return json.dumps(
        {column: decode_column(model, row, column) for column in columns}, default=str
    )
