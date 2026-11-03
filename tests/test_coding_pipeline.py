from pathlib import Path

from src.catalog.loader import Catalog
from src.catalog.models import RetrievalHit
from src.llm import MockProvider
from src.pipeline import ClinicalCodingPipeline


class FixedRetriever:
    def retrieve(self, query, *, top_k=30):
        return [
            RetrievalHit(code="I10", description_es="Hipertensión esencial", score=0.02, rank=1),
            RetrievalHit(code="R50.9", description_es="Fiebre no especificada", score=0.01, rank=2),
        ][:top_k]


def test_pipeline_checks_codes_evidence_and_rule_state(tmp_path: Path):
    catalog_path = tmp_path / "catalog.tsv"
    catalog_path.write_text(
        "code\tdescription_es\tdescription_en\nI10\tHipertensión esencial\tEssential hypertension\nR50.9\tFiebre no especificada\tFever\n",
        encoding="utf-8",
    )
    catalog = Catalog.from_tsv(catalog_path)
    response = '{"codes":['
    response += '{"code":"I10","evidence":"HTA","state":"confirmed","confidence":0.9},'
    response += '{"code":"R50.9","evidence":"Niega fiebre.","state":"confirmed","confidence":0.8},'
    response += '{"code":"Z99.1","evidence":"HTA","state":"confirmed","confidence":1.0},'
    response += '{"code":"I10","evidence":"texto inventado","state":"confirmed","confidence":1.0}]}'
    pipeline = ClinicalCodingPipeline(
        catalog=catalog,
        retriever=FixedRetriever(),
        provider=MockProvider(response),
    )

    prediction = pipeline.run("Paciente con HTA. Niega fiebre.", note_id="t1")
    assert [(item.code, item.state.value) for item in prediction.codes] == [
        ("I10", "confirmed"),
        ("R50.9", "negated"),
    ]
    assert len(prediction.warnings) == 3
    assert prediction.codes[1].evidence == "Niega fiebre."
    assert prediction.codes[1].span == (18, 31)


def test_invalid_json_gets_one_repair_then_safe_empty_output(tmp_path: Path):
    catalog_path = tmp_path / "catalog.tsv"
    catalog_path.write_text(
        "code\tdescription_es\tdescription_en\nI10\tHipertensión esencial\tEssential hypertension\nR50.9\tFiebre no especificada\tFever\n",
        encoding="utf-8",
    )
    calls = 0

    def invalid_twice(_messages):
        nonlocal calls
        calls += 1
        return "not json"

    pipeline = ClinicalCodingPipeline(
        catalog=Catalog.from_tsv(catalog_path),
        retriever=FixedRetriever(),
        provider=MockProvider(invalid_twice),
    )
    prediction = pipeline.run("Paciente con HTA.")
    assert calls == 2
    assert prediction.codes == []
    assert prediction.warnings == ["Salida JSON inválida tras un reintento; se devuelve sin códigos"]


def test_empty_llm_output_retries_strictly_before_fallback(tmp_path: Path):
    catalog_path = tmp_path / "catalog.tsv"
    catalog_path.write_text(
        "code\tdescription_es\tdescription_en\nI10\tHipertensión esencial\tEssential hypertension\nR50.9\tFiebre no especificada\tFever\n",
        encoding="utf-8",
    )
    calls = 0

    def empty_then_valid(_messages):
        nonlocal calls
        calls += 1
        if calls == 1:
            return '{"codes": []}'
        return '{"codes":[{"code":"I10","evidence":"HTA","state":"confirmed","confidence":0.9}]}'

    pipeline = ClinicalCodingPipeline(
        catalog=Catalog.from_tsv(catalog_path),
        retriever=FixedRetriever(),
        provider=MockProvider(empty_then_valid),
    )

    prediction = pipeline.run("Paciente con HTA. Niega fiebre.")

    assert calls == 2
    assert [item.code for item in prediction.codes] == ["I10"]
    assert any("reintentó con instrucción estricta" in warning for warning in prediction.warnings)
