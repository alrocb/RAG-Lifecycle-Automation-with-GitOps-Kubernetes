from pathlib import Path

import pytest
from pptx import Presentation
from qdrant_client import QdrantClient

from rag.config import settings
from rag.ingest import anonymize as anonymize_module
from rag.ingest import indexer
from rag.ingest.anonymize import anonymize
from rag.ingest.chunking import split
from rag.ingest.parsers import parse_pptx, parse_vtt

DATA = Path(__file__).parent / "fixtures" / "data"


def test_parse_vtt_groups_cues_by_time_window():
    sections = parse_vtt(DATA / "devops" / "clase-01.vtt", window=60)
    assert [s.location for s in sections] == ["00:00:01", "00:01:20"]
    assert "integración continua" in sections[0].text


def test_parse_pptx(tmp_path):
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "GitOps"
    path = tmp_path / "tema.pptx"
    deck.save(path)
    sections = parse_pptx(path)
    assert sections[0].location == "diapositiva 1"
    assert "GitOps" in sections[0].text


def test_anonymize_removes_voice_tags_and_names():
    text = "<v Ana Pérez>Hola</v>, como dijo luis en el foro"
    assert anonymize(text, ["Luis"]) == "Hola, como dijo [PERSONA] en el foro"


def test_anonymize_detects_unknown_names_but_keeps_tools(monkeypatch):
    monkeypatch.setattr(settings, "ner_model", "es_core_news_md")
    try:
        anonymize_module._nlp()
    except ImportError:  # en Windows con Smart App Control no carga; corre en CI y Docker
        pytest.skip("spaCy no se puede cargar en este equipo")
    text = "Vale, Pedro pregunta si Argo CD sustituye a Jenkins. Helm y Grafana, como dijo luis."
    assert anonymize(text, []) == (
        "Vale, [PERSONA] pregunta si Argo CD sustituye a Jenkins. Helm y Grafana, como dijo [PERSONA]."
    )


def test_split_with_overlap():
    chunks = split("a" * 1000, size=800, overlap=100)
    assert [len(c) for c in chunks] == [800, 300]
    assert split("   ") == []


def test_load_documents_adds_metadata():
    payloads = indexer.load_documents(DATA, names=["Luis"])
    subjects = {p["subject"] for p in payloads}
    assert subjects == {"devops", "kubernetes"}
    assert all(p["material_type"] == "vtt" for p in payloads)
    assert not any("Ana Pérez" in p["text"] or "Luis" in p["text"] for p in payloads)


def test_reindex_moves_alias_and_keeps_previous(fake_models):
    client = QdrantClient(":memory:")
    payloads = indexer.load_documents(DATA, names=[])

    first = indexer.reindex(client, payloads, "materials")
    second = indexer.reindex(client, payloads, "materials")
    assert indexer.current_collection(client, "materials") == second

    third = indexer.reindex(client, payloads, "materials")
    collections = {c.name for c in client.get_collections().collections}
    assert collections == {second, third}  # la primera se ha borrado
    assert first not in collections
    assert client.count("materials").count == len(payloads)
