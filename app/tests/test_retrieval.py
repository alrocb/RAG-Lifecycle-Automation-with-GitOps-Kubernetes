from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from rag import retrieval
from rag.config import settings
from rag.ingest import indexer

DATA = Path(__file__).parent / "fixtures" / "data"


@pytest.fixture
def client(fake_models):
    client = QdrantClient(":memory:")
    indexer.reindex(client, indexer.load_documents(DATA, names=[]), settings.collection_alias)
    return client


def test_hybrid_search_finds_exact_keywords(client):
    hits = retrieval.search(client, "StatefulSet DaemonSet")
    assert hits[0].payload["subject"] == "kubernetes"


def test_search_filters_by_subject(client):
    hits = retrieval.search(client, "Deployment", subject="devops")
    assert hits and all(h.payload["subject"] == "devops" for h in hits)


def test_rerank_sorts_and_keeps_top_k(client, monkeypatch):
    monkeypatch.setattr(settings, "top_k", 1)
    hits = retrieval.search(client, "actividad pipeline")
    best = retrieval.rerank_hits("actividad pipeline", hits)
    assert len(best) == 1
    assert "pipeline" in best[0].payload["text"]


def test_rerank_drops_irrelevant_fragments(client, monkeypatch):
    # El reranker falso puntúa con el nº de palabras en común: 2 exige que coincidan ambas.
    monkeypatch.setattr(settings, "rerank_min_score", 2)
    hits = retrieval.search(client, "actividad pipeline")
    best = retrieval.rerank_hits("actividad pipeline", hits)
    assert best and all(h.score >= 2 for h in best)
    assert len(best) < len(hits)


def test_subjects(client):
    assert retrieval.subjects(client) == ["devops", "kubernetes"]
