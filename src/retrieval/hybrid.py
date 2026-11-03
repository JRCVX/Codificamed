"""Recuperación híbrida BM25 + FAISS sobre el catálogo CIE-10."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from src.catalog.loader import Catalog
from src.catalog.models import RetrievalHit
from src.preprocess.normalize import tokens_for_matching


class Embedder(Protocol):
    def encode(self, texts: list[str], *, query: bool = False) -> np.ndarray: ...


class E5Embedder:
    """Codificador multilingüe E5 con prefijos de consulta/documento."""

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small", device: str = "cpu"):
        self.model = SentenceTransformer(model_name, device=device)

    def encode(self, texts: list[str], *, query: bool = False) -> np.ndarray:
        prefix = "query: " if query else "passage: "
        vectors = self.model.encode(
            [prefix + text for text in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=query,
            batch_size=64,
        )
        return np.asarray(vectors, dtype=np.float32)


@dataclass(frozen=True)
class CatalogDocument:
    code: str
    description: str
    english: str | None = None

    @property
    def text(self) -> str:
        return f"{self.description}. {self.english or ''}".strip()


class SparseBM25:
    """BM25 con postings invertidos; puntúa solo documentos coincidentes."""

    def __init__(self, tokenized_documents: list[list[str]], *, k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_lengths = [len(document) for document in tokenized_documents]
        self.avgdl = sum(self.doc_lengths) / max(len(self.doc_lengths), 1)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        document_frequency: Counter[str] = Counter()
        for doc_id, document in enumerate(tokenized_documents):
            frequencies = Counter(document)
            document_frequency.update(frequencies.keys())
            for token, frequency in frequencies.items():
                self.postings[token].append((doc_id, frequency))
        count = len(tokenized_documents)
        self.idf = {
            token: math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5))
            for token, frequency in document_frequency.items()
        }

    def top_indices(self, query_tokens: list[str], limit: int) -> list[tuple[int, float]]:
        scores: dict[int, float] = defaultdict(float)
        for token in set(query_tokens):
            idf = self.idf.get(token)
            if idf is None:
                continue
            for doc_id, frequency in self.postings[token]:
                norm = frequency + self.k1 * (
                    1.0 - self.b + self.b * self.doc_lengths[doc_id] / max(self.avgdl, 1.0)
                )
                scores[doc_id] += idf * frequency * (self.k1 + 1.0) / norm
        return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]


def build_faiss_index(
    catalog: Catalog,
    embedder: Embedder,
    index_path: Path | str,
    codes_path: Path | str,
    *,
    batch_size: int = 128,
) -> int:
    """Crea el índice denso y su lista de códigos en el mismo orden."""
    entries = list(catalog.entries())
    texts = [f"{entry.description_es}. {entry.description_en or ''}" for entry in entries]
    index = None
    for start in tqdm(range(0, len(texts), batch_size), desc="Embeddings CIE-10"):
        vectors = embedder.encode(texts[start : start + batch_size])
        if index is None:
            index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
    if index is None:
        raise ValueError("No se puede indexar un catálogo vacío")
    index_file, codes_file = Path(index_path), Path(codes_path)
    index_file.parent.mkdir(parents=True, exist_ok=True)
    codes_file.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_file))
    codes_file.write_text("\n".join(entry.code for entry in entries) + "\n", encoding="utf-8")
    return len(entries)


class HybridRetriever:
    """Fusiona ranking léxico y denso por Reciprocal Rank Fusion."""

    def __init__(
        self,
        catalog: Catalog,
        embedder: Embedder,
        index_path: Path | str,
        codes_path: Path | str,
        *,
        bm25_top_k: int = 50,
        dense_top_k: int = 50,
        rrf_k: int = 60,
    ) -> None:
        self.catalog = catalog
        self.embedder = embedder
        self.bm25_top_k = bm25_top_k
        self.dense_top_k = dense_top_k
        self.rrf_k = rrf_k
        self.documents = [
            CatalogDocument(item.code, item.description_es, item.description_en)
            for item in catalog.entries()
        ]
        tokenized = [tokens_for_matching(item.text) for item in tqdm(self.documents, desc="Tokens BM25")]
        self.bm25 = SparseBM25(tokenized)
        self.index = faiss.read_index(str(index_path))
        self.codes = Path(codes_path).read_text(encoding="utf-8").splitlines()
        if len(self.codes) != len(self.documents) or self.index.ntotal != len(self.documents):
            raise ValueError("El índice FAISS, su lista de códigos y el catálogo no coinciden")
        if self.codes != [item.code for item in self.documents]:
            raise ValueError("El orden de códigos guardado no coincide con el catálogo")

    def retrieve(self, query: str, *, top_k: int = 30) -> list[RetrievalHit]:
        return self.retrieve_many([query], top_k=top_k)[0]

    def retrieve_many(self, queries: list[str], *, top_k: int = 30) -> list[list[RetrievalHit]]:
        """Recupera un lote para evaluación eficiente por embeddings."""
        if top_k < 1:
            raise ValueError("top_k debe ser positivo")
        active = [index for index, query in enumerate(queries) if query.strip()]
        results: list[list[RetrievalHit]] = [[] for _ in queries]
        if not active:
            return results
        vectors = self.embedder.encode([queries[index] for index in active], query=True)
        _, dense_batch = self.index.search(vectors, min(self.dense_top_k, self.index.ntotal))
        for row, query_index in enumerate(active):
            query_tokens = tokens_for_matching(queries[query_index])
            lex_indices = self.bm25.top_indices(query_tokens, self.bm25_top_k)
            fused: dict[int, float] = {}
            ranked_sources = (
                [index for index, _ in lex_indices],
                dense_batch[row].tolist(),
            )
            for indices in ranked_sources:
                for rank, doc_index in enumerate(indices, start=1):
                    if doc_index >= 0:
                        fused[doc_index] = fused.get(doc_index, 0.0) + 1.0 / (self.rrf_k + rank)
            ranked = sorted(fused.items(), key=lambda item: item[1], reverse=True)[:top_k]
            results[query_index] = [
                RetrievalHit(
                    code=self.documents[doc_index].code,
                    description_es=self.documents[doc_index].description,
                    score=float(score),
                    rank=rank,
                    source="hybrid",
                )
                for rank, (doc_index, score) in enumerate(ranked, start=1)
            ]
        return results


def save_catalog_manifest(catalog: Catalog, path: Path | str) -> None:
    """Guarda descripciones y orden para auditar una construcción de índice."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps([item.model_dump() for item in catalog.entries()], ensure_ascii=False),
        encoding="utf-8",
    )
