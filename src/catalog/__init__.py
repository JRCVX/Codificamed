"""Subpaquete catalog de CodificaMed."""

from src.catalog.loader import Catalog, CatalogError
from src.catalog.models import CatalogEntry

__all__ = ["Catalog", "CatalogEntry", "CatalogError"]
