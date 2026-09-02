from .client import CatalogTableJoinEdgeClient
from .models import (
    CatalogTableJoinEdgeInsert,
    CatalogTableJoinEdgeModel,
    CatalogTableJoinEdgeSelect,
)

MODELS = [CatalogTableJoinEdgeModel]

__all__ = [
    "MODELS",
    "CatalogTableJoinEdgeClient",
    "CatalogTableJoinEdgeInsert",
    "CatalogTableJoinEdgeModel",
    "CatalogTableJoinEdgeSelect",
]
