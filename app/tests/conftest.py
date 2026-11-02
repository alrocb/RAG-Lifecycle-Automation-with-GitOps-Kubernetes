import re
import zlib
from collections import Counter

import pytest
from qdrant_client.models import SparseVector

from rag import retrieval
from rag.config import settings
from rag.ingest import indexer


def words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def fake_dense(texts: list[str]) -> list[list[float]]:
    return [[1.0, float(len(t) % 7 + 1)] for t in texts]


def fake_sparse(texts: list[str], query: bool = False) -> list[SparseVector]:
    vectors = []
    for text in texts:
        counts = Counter(zlib.crc32(w.encode()) % 100_000 for w in words(text))
        vectors.append(SparseVector(indices=list(counts), values=[float(v) for v in counts.values()]))
    return vectors


def fake_rerank(query: str, documents: list[str]) -> list[float]:
    return [float(len(set(words(query)) & set(words(d)))) for d in documents]


@pytest.fixture(autouse=True)
def no_ner(monkeypatch):
    """Por defecto sin spaCy; los tests de NER lo activan explícitamente."""
    monkeypatch.setattr(settings, "ner_model", "")


@pytest.fixture
def fake_models(monkeypatch):
    """Sustituye los modelos reales para que los tests no descarguen nada."""
    for module in (indexer, retrieval):
        monkeypatch.setattr(module, "embed", fake_dense)
        monkeypatch.setattr(module, "embed_sparse", fake_sparse)
    monkeypatch.setattr(retrieval, "rerank", fake_rerank)
