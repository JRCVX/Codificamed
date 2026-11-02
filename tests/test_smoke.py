"""Smoke test: verifica que el esqueleto del proyecto se importa correctamente."""

from __future__ import annotations

import importlib

import src


def test_version_is_defined() -> None:
    assert src.__version__ == "0.1.0"


def test_all_subpackages_import() -> None:
    for package in (
        "src.preprocess",
        "src.catalog",
        "src.retrieval",
        "src.negation",
        "src.ner",
        "src.llm",
        "src.pipeline",
        "src.eval",
    ):
        module = importlib.import_module(package)
        assert module.__name__ == package
