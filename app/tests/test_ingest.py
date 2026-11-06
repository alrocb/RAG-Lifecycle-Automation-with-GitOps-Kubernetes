from pathlib import Path

import pytest
from docx import Document
from pptx import Presentation
from qdrant_client import QdrantClient

from rag.config import settings
from rag.ingest import anonymize as anonymize_module
from rag.ingest import indexer
from rag.ingest.anonymize import anonymize
from rag.ingest.chunking import split
from rag.ingest.parsers import parse_docx, parse_pptx, parse_vtt

DATA = Path(__file__).parent / "fixtures" / "data"


def test_parse_vtt_groups_cues_by_time_window():
    sections = parse_vtt(DATA / "devops" / "clase-01.vtt", window=60)
    assert [s.location for s in sections] == ["00:00:01", "00:01:20"]
    assert "integración continua" in sections[0].text


def test_parse_vtt_removes_speaker_labels():
    text = parse_vtt(DATA / "devops" / "clase-01.vtt")[-1].text
    assert "GARCÍA" not in text
    assert "Profe, ¿la actividad 1 es individual o en grupo?" in text


def test_parse_docx_groups_by_heading_and_reads_tables(tmp_path):
    document = Document()
    document.add_paragraph("Actividad 1")
    document.add_heading("Objetivos", level=1)
    document.add_paragraph("Montar un pipeline de CI.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Criterio", "Puntos"
    path = tmp_path / "act1.docx"
    document.save(path)
    sections = parse_docx(path)
    assert [s.location for s in sections] == ["inicio", "Objetivos", "tabla 1"]
    assert "Montar un pipeline" in sections[1].text
    assert sections[2].text == "Criterio | Puntos"


def test_load_documents_skips_broken_files(tmp_path):
    (tmp_path / "devops").mkdir()
    (tmp_path / "devops" / "roto.pdf").write_bytes(b"esto no es un pdf")
    (tmp_path / "devops" / "notas.txt").write_text("formato no soportado")
    (tmp_path / "devops" / "clase.vtt").write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHola\n")
    payloads = indexer.load_documents(tmp_path, names=[])
    assert [p["source"] for p in payloads] == ["clase.vtt"]


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


def test_anonymize_replaces_capitalized_given_names_without_spacy():
    # Sin spaCy (desactivado en los tests) sigue sustituyendo nombres de pila en mayúscula,
    # pero no a mitad de palabra ni en minúscula.
    assert anonymize("A ver Alberto, ¿y Moisés? DevOps sin rosa", []) == (
        "A ver [PERSONA], ¿y [PERSONA]? DevOps sin rosa"
    )
    assert anonymize("Tema 3 Jesús F. Rodríguez-Aragón Universidad", []) == "Tema 3 [PERSONA] Universidad"


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


@pytest.mark.parametrize(
    ("entity", "expected"),
    [
        ("Iván Sanz", True),  # sin distinguir tildes ni mayúsculas
        ("luis", True),
        ("Ayer Juan García", True),
        ("Meetes Engine", False),  # transcripción errónea de "Kubernetes Engine"
        ("Comandos", False),
        ("Jenkins", False),
    ],
)
def test_is_person_requires_a_given_name(entity, expected):
    assert anonymize_module.is_person(entity) is expected


def test_split_with_overlap():
    chunks = split("a" * 1000, size=800, overlap=100)
    assert [len(c) for c in chunks] == [800, 300]
    assert split("   ") == []


def test_load_documents_adds_metadata():
    payloads = indexer.load_documents(DATA, names=["Luis"])
    subjects = {p["subject"] for p in payloads}
    assert subjects == {"devops", "kubernetes"}
    assert all(p["material_type"] == "vtt" for p in payloads)
    assert not any(n in p["text"] for p in payloads for n in ("Ana Pérez", "Luis", "GARCÍA"))


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
