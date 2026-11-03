"""Corrección conservadora de errores de tipeo en términos clínicos.

No se usa un modelo generativo: se compara cada token contra el vocabulario del
catálogo CIE-10 con RapidFuzz. Las siglas, negaciones, palabras vacías y tokens
cortos quedan protegidos para evitar cambios semánticos peligrosos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process

from src.preprocess.normalize import strip_accents

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VOCAB = PROJECT_ROOT / "data" / "catalog" / "clinical_vocab.txt"

_TOKEN_PATTERN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")

# Nunca se corrigen: cambian el sentido clínico o son abreviaturas frecuentes.
PROTECTED_TERMS = {
    "no",
    "sin",
    "niega",
    "negativo",
    "negativa",
    "ausencia",
    "antecedente",
    "antecedentes",
    "familiar",
    "madre",
    "padre",
    "hijo",
    "hija",
    "hermano",
    "hermana",
    "sospecha",
    "probable",
    "posible",
    "descartar",
    "hta",
    "dm1",
    "dm2",
    "dmt2",
    "epoc",
    "icc",
    "irc",
    "erc",
    "acv",
    "evc",
    "iam",
    "iamcest",
    "iamsest",
    "sca",
    "fa",
    "tsv",
    "tep",
    "tvp",
    "itu",
    "ivu",
    "nac",
    "hbp",
    "uci",
    "uti",
    "pa",
    "ta",
    "fc",
    "fr",
    "sato2",
    "spo2",
    "hb",
    "hto",
    "leuc",
    "plq",
    "cr",
    "bun",
    "glu",
    "hba1c",
    "ldl",
    "hdl",
    "tg",
    "tsh",
    "t4l",
    "vih",
    "vhb",
    "vhc",
    "pcr",
    "vsg",
    "bk",
    "ppd",
    "tac",
    "rmn",
    "rx",
    "ecg",
    "ekg",
    "eco",
    "usg",
    "hcg",
    "ego",
    "bh",
    "qs",
    "dx",
    "tx",
}


@dataclass(frozen=True)
class TypoCorrection:
    start: int
    end: int
    original: str
    suggestion: str
    score: float


class TypoCorrector:
    """Sugiere correcciones solo cuando la similitud supera un umbral."""

    def __init__(
        self,
        vocabulary: list[str] | tuple[str, ...],
        *,
        min_length: int = 5,
        score_cutoff: float = 86.0,
        protected: set[str] | None = None,
    ) -> None:
        if not vocabulary:
            raise ValueError("El vocabulario no puede estar vacío")
        self.min_length = min_length
        self.score_cutoff = score_cutoff
        self.protected = {term.casefold() for term in (protected or PROTECTED_TERMS)}
        self.vocabulary = tuple(dict.fromkeys(word.casefold() for word in vocabulary if word.strip()))
        self._normalized_vocabulary = tuple(strip_accents(word) for word in self.vocabulary)
        self._vocabulary_set = set(self.vocabulary)
        self._normalized_set = set(self._normalized_vocabulary)

    @classmethod
    def from_file(cls, path: Path | str = DEFAULT_VOCAB, **kwargs: object) -> TypoCorrector:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"No existe el vocabulario: {path}")
        vocabulary = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        return cls(vocabulary, **kwargs)

    def correct_token(self, token: str) -> tuple[str, float] | None:
        """Devuelve ``(sugerencia, score)`` o ``None`` si no hay corrección segura."""
        folded = token.casefold()
        if len(folded) < self.min_length:
            return None
        if folded in self.protected or folded in self._vocabulary_set:
            return None
        if any(char.isdigit() for char in folded):
            return None
        if folded.isupper() and len(folded) <= 5:
            return None

        normalized = strip_accents(folded)
        if normalized in self._normalized_set:
            # Solo cambia la acentuación: se sugiere la forma del catálogo.
            index = self._normalized_vocabulary.index(normalized)
            return self.vocabulary[index], 100.0

        match = process.extractOne(
            normalized,
            self._normalized_vocabulary,
            scorer=fuzz.WRatio,
            score_cutoff=self.score_cutoff,
        )
        if match is None:
            return None
        suggestion, score, index = match
        del suggestion
        candidate = self.vocabulary[index]
        if strip_accents(candidate) == normalized:
            return candidate, 100.0
        return candidate, float(score)

    def suggest(self, text: str) -> list[TypoCorrection]:
        corrections: list[TypoCorrection] = []
        for match in _TOKEN_PATTERN.finditer(text):
            token = match.group(0)
            result = self.correct_token(token)
            if result is None:
                continue
            suggestion, score = result
            corrections.append(
                TypoCorrection(
                    start=match.start(),
                    end=match.end(),
                    original=token,
                    suggestion=suggestion,
                    score=score,
                )
            )
        return corrections

    def apply(self, text: str, corrections: list[TypoCorrection] | None = None) -> str:
        """Aplica las correcciones de derecha a izquierda para no desplazar spans."""
        selected = corrections if corrections is not None else self.suggest(text)
        result = text
        for correction in sorted(selected, key=lambda item: item.start, reverse=True):
            result = result[: correction.start] + correction.suggestion + result[correction.end :]
        return result
