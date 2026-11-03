"""Métricas de evaluación para códigos CIE-10 y predicciones clínicas."""

from __future__ import annotations

from collections.abc import Iterable


def _clean_codes(values: Iterable[str]) -> set[str]:
    cleaned: set[str] = set()
    for value in values:
        code = str(value).strip().upper()
        if code:
            cleaned.add(code)
    return cleaned


def precision_recall_f1(gold: Iterable[str], predicted: Iterable[str]) -> dict[str, float]:
    """Calcula precision/recall/F1 para dos colecciones de códigos."""
    gold_set = _clean_codes(gold)
    pred_set = _clean_codes(predicted)
    true_positives = len(gold_set & pred_set)
    false_positives = len(pred_set - gold_set)
    false_negatives = len(gold_set - pred_set)
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": true_positives,
        "fp": false_positives,
        "fn": false_negatives,
        "support": len(gold_set),
    }


def micro_precision_recall_f1(gold_batch: list[Iterable[str]], pred_batch: list[Iterable[str]]) -> dict[str, float]:
    """Agrega todas las predicciones de un dataset con enfoque micro."""
    if len(gold_batch) != len(pred_batch):
        raise ValueError("gold_batch y pred_batch deben tener la misma longitud")

    true_positives = 0
    false_positives = 0
    false_negatives = 0
    for gold, pred in zip(gold_batch, pred_batch, strict=True):
        gold_set = _clean_codes(gold)
        pred_set = _clean_codes(pred)
        true_positives += len(gold_set & pred_set)
        false_positives += len(pred_set - gold_set)
        false_negatives += len(gold_set - pred_set)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1, "tp": true_positives, "fp": false_positives, "fn": false_negatives}


def macro_average_metrics(gold_batch: list[Iterable[str]], pred_batch: list[Iterable[str]]) -> dict[str, float]:
    """Promedio simple de las métricas por caso; útil para casos con pocos códigos."""
    if len(gold_batch) != len(pred_batch):
        raise ValueError("gold_batch y pred_batch deben tener la misma longitud")

    metrics = [precision_recall_f1(gold, pred) for gold, pred in zip(gold_batch, pred_batch, strict=True)]
    keys = ("precision", "recall", "f1")
    aggregated = {key: sum(item[key] for item in metrics) / len(metrics) if metrics else 0.0 for key in keys}
    aggregated["support"] = sum(item["support"] for item in metrics)
    return aggregated
