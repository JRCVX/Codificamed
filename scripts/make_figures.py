#!/usr/bin/env python3
"""Genera las figuras de documentación (arquitectura y fases CRISP-ML).

No requiere Graphviz ni conexión: usa matplotlib en modo Agg.
Salidas:
  - docs/figuras/arquitectura.png
  - docs/figuras/crisp_ml_fases.png

Uso:
    python scripts/make_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "figuras"
OUT.mkdir(parents=True, exist_ok=True)

AZUL = "#1f4e79"
AZUL_CLARO = "#dce9f5"
VERDE = "#2e7d32"
VERDE_CLARO = "#e3f2e1"
NARANJA = "#b35c00"
NARANJA_CLARO = "#fdebd8"
GRIS = "#4a4a4a"
GRIS_CLARO = "#f0f0f0"
ROJO = "#a61b1b"
ROJO_CLARO = "#fbe3e3"


def caja(ax, x, y, w, h, texto, borde=AZUL, fondo=AZUL_CLARO, tam=10, peso="normal"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.35,rounding_size=0.8",
        linewidth=1.4,
        edgecolor=borde,
        facecolor=fondo,
        zorder=2,
    )
    ax.add_patch(patch)
    ax.text(
        x + w / 2,
        y + h / 2,
        texto,
        ha="center",
        va="center",
        fontsize=tam,
        color="#1a1a1a",
        fontweight=peso,
        zorder=3,
        wrap=True,
    )


def flecha(ax, x1, y1, x2, y2, color=GRIS):
    ax.add_patch(
        FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.4,
            color=color,
            zorder=1,
        )
    )


def figura_arquitectura() -> Path:
    fig, ax = plt.subplots(figsize=(16, 9.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(50, 97, "CodificaMed — arquitectura del pipeline", ha="center", va="center",
            fontsize=18, fontweight="bold", color=AZUL)
    ax.text(50, 93.5, "La recuperación y la negación son deterministas; el LLM solo razona sobre candidatos validados",
            ha="center", va="center", fontsize=10, color=GRIS, style="italic")

    caja(ax, 24, 83, 52, 7.5, "Nota clínica en texto libre\n(abreviaturas, typos, negaciones)", fondo=GRIS_CLARO, borde=GRIS, peso="bold")
    caja(ax, 14, 71, 72, 8.5, "PREPROCESO\nnormalización → expansión de abreviaturas → segmentación → tolerancia a typos\n(preserva offsets y no altera negaciones)", fondo=AZUL_CLARO)

    caja(ax, 6, 55, 40, 10, "NEGACIÓN / ESTADO\nconfirmado · negado · sospechoso\nantecedente · familiar · incierto", fondo=NARANJA_CLARO, borde=NARANJA)
    caja(ax, 54, 55, 40, 10, "CATÁLOGO CIE-10 (98.268 códigos válidos)\nBM25 + embeddings multilingües + FAISS\nrecuperación híbrida top-k", fondo=VERDE_CLARO, borde=VERDE)

    caja(ax, 14, 40, 72, 9, "PROMPT AUMENTADO\nnota + candidatos recuperados + anotaciones de negación + instrucciones y few-shot", fondo=AZUL_CLARO)

    caja(ax, 14, 25, 72, 9, "LLMProvider — interfaz única\nOllama (local) · OpenAI-compatible · Anthropic · Mock\nmismo prompt, mismo esquema, mismo parser", fondo=VERDE_CLARO, borde=VERDE)

    caja(ax, 6, 10, 40, 10, "VALIDACIÓN / GUARDRAILS\nJSON Schema + whitelist del catálogo\nalineación de evidencia + conflicto de negación", fondo=ROJO_CLARO, borde=ROJO)
    caja(ax, 54, 10, 40, 10, "AGREGACIÓN Y SALIDA\ncódigo · descripción · estado\nconfianza · evidencia · ranking", fondo=AZUL_CLARO)

    flecha(ax, 50, 83, 50, 79.5)
    flecha(ax, 35, 71, 26, 65.2)
    flecha(ax, 65, 71, 74, 65.2)
    flecha(ax, 26, 55, 26, 49.2)
    flecha(ax, 74, 55, 74, 49.2)
    flecha(ax, 50, 40, 50, 34.2)
    flecha(ax, 35, 25, 26, 20.2)
    flecha(ax, 65, 25, 74, 20.2)
    flecha(ax, 46, 15, 54, 15)
    flecha(ax, 74, 10, 74, 6.8)

    ax.text(50, 5.0, "UI Streamlit · CLI · scripts de evaluación  →  código sugerido + evidencia resaltada + estado",
            ha="center", va="center", fontsize=10.5, color=GRIS, fontweight="bold")
    ax.text(97, 55, "Fuente\nverificable", ha="right", va="center", fontsize=8.5, color=VERDE, style="italic")
    ax.text(3, 15, "Cero códigos\ninventados", ha="left", va="center", fontsize=8.5, color=ROJO, style="italic")

    fig.tight_layout()
    path = OUT / "arquitectura.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def figura_crisp() -> Path:
    fases = [
        ("1", "Comprensión\ndel negocio\ny datos"),
        ("2", "Preparación\nde datos"),
        ("3", "Modelado"),
        ("4", "Evaluación"),
        ("5", "Despliegue"),
        ("6", "Monitoreo y\nmantenimiento"),
    ]
    colores = ["#1f4e79", "#2e6da4", "#2e7d32", "#b35c00", "#6a1b9a", "#a61b1b"]
    fig, ax = plt.subplots(figsize=(15, 4.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 30)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(50, 27, "CRISP-ML(Q): seis fases con aseguramiento de calidad",
            ha="center", va="center", fontsize=16, fontweight="bold", color=AZUL)

    ancho = 14.0
    separacion = 1.6
    inicio = 2.0
    for i, ((numero, texto), color) in enumerate(zip(fases, colores, strict=True)):
        x = inicio + i * (ancho + separacion)
        caja(ax, x, 10, ancho, 9, f"Fase {numero}\n{texto}", borde=color,
             fondo=GRIS_CLARO, tam=9.5, peso="bold")
        if i < len(fases) - 1:
            flecha(ax, x + ancho, 14.5, x + ancho + separacion, 14.5, color=GRIS)

    ax.text(50, 5.2,
            "En cada fase: criterios de entrada/salida, revisión, pruebas y evidencia reproducible en docs/ESTADO.md",
            ha="center", va="center", fontsize=9.5, color=GRIS, style="italic")

    fig.tight_layout()
    path = OUT / "crisp_ml_fases.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def main() -> None:
    for path in (figura_arquitectura(), figura_crisp()):
        print(f"Figura generada: {path}")


if __name__ == "__main__":
    main()
