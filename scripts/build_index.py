"""Construye FAISS sobre las descripciones del catálogo configurado."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.catalog.loader import Catalog  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.retrieval.hybrid import E5Embedder, build_faiss_index  # noqa: E402


def main() -> int:
    settings = get_settings()
    catalog = Catalog.from_tsv(settings.catalog_path)
    embedder = E5Embedder(settings.embedding_model, settings.embedding_device)
    count = build_faiss_index(
        catalog,
        embedder,
        settings.faiss_index_path,
        settings.faiss_codes_path,
        batch_size=512,
    )
    print(f"OK índice FAISS: {count:,} códigos -> {settings.faiss_index_path}")
    print(f"Orden de códigos -> {settings.faiss_codes_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
