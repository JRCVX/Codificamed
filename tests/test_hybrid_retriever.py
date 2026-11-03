from pathlib import Path

import numpy as np

from src.catalog.loader import Catalog
from src.retrieval.hybrid import HybridRetriever, build_faiss_index


class TinyEmbedder:
    def encode(self, texts, *, query=False):
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [1.0, 0.0]
                if "hipertension" in lowered or "hypertension" in lowered or "hta" in lowered
                else [0.0, 1.0]
            )
        values = np.asarray(vectors, dtype=np.float32)
        return values / np.linalg.norm(values, axis=1, keepdims=True)


def test_build_and_query_hybrid_index(tmp_path: Path):
    catalog_path = tmp_path / "catalog.tsv"
    catalog_path.write_text(
        "code\tdescription_es\tdescription_en\nI10\tHipertension esencial\tEssential hypertension\nR50.9\tFiebre no especificada\tFever\n",
        encoding="utf-8",
    )
    catalog = Catalog.from_tsv(catalog_path)
    index_path, codes_path = tmp_path / "index.faiss", tmp_path / "codes.txt"
    assert build_faiss_index(catalog, TinyEmbedder(), index_path, codes_path) == 2

    retriever = HybridRetriever(catalog, TinyEmbedder(), index_path, codes_path)
    hits = retriever.retrieve("Hipertension", top_k=2)
    assert "I10" in [hit.code for hit in hits]
    assert [hit.rank for hit in hits] == [1, 2]
