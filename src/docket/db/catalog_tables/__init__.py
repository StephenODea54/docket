from .client import CatalogTableClient
from .models import CatalogTableModel

MODELS = [CatalogTableModel]

__all__ = ["MODELS", "CatalogTableClient", "CatalogTableModel"]
