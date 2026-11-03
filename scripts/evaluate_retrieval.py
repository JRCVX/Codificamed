"""Mide recall@k del recuperador híbrido sobre un split CodiEsp."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.catalog.loader import Catalog  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.preprocess import ClinicalPreprocessor  # noqa: E402
from src.retrieval.hybrid import E5Embedder, HybridRetriever  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--limit", type=int, default=None, help="Límite opcional para una corrida rápida")
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "reports" / "retrieval_dev.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    catalog = Catalog.from_tsv(settings.catalog_path)
    print(f"Cargando índice y BM25 para {len(catalog):,} códigos", flush=True)
    retriever = HybridRetriever(
        catalog,
        E5Embedder(settings.embedding_model, settings.embedding_device),
        settings.faiss_index_path,
        settings.faiss_codes_path,
        bm25_top_k=settings.bm25_top_k,
        dense_top_k=settings.dense_top_k,
    )
    # Recall de recuperación aislado: evita que el corrector léxico agregue
    # latencia y permite medir retrieval con las expansiones de abreviaturas.
    preprocessor = ClinicalPreprocessor(correct_typos=False)
    data_path = PROJECT_ROOT / "data" / "processed" / f"codiesp_{args.split}.jsonl"
    records = [json.loads(line) for line in data_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.limit:
        records = records[: args.limit]

    print(f"Preparando consultas: {len(records)} notas de {args.split}", flush=True)
    queries = [preprocessor.preprocess(record["text"]).retrieval_text for record in records]
    hit_lists = retriever.retrieve_many(queries, top_k=args.top_k)
    total_gold = found = documents = documents_with_all = 0
    details = []
    for record, hits in zip(records, hit_lists, strict=True):
        gold = set(record["gold_codes"])
        retrieved = {hit.code for hit in hits}
        covered = len(gold & retrieved)
        total_gold += len(gold)
        found += covered
        documents += 1
        documents_with_all += int(gold <= retrieved)
        details.append({"id": record["id"], "gold": len(gold), "covered": covered})

    result = {
        "split": args.split,
        "documents": documents,
        "top_k": args.top_k,
        "gold_codes": total_gold,
        "retrieved_gold_codes": found,
        "recall_at_k": found / total_gold if total_gold else 0.0,
        "documents_all_gold_retrieved": documents_with_all,
        "document_coverage": documents_with_all / documents if documents else 0.0,
        "model": settings.embedding_model,
        "details": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Recall@{args.top_k}={result['recall_at_k']:.4f} "
        f"({found}/{total_gold}); notas con todos los gold={documents_with_all}/{documents}"
    )
    print(f"Reporte: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
