"""Modelos locales (CPU) de fastembed: embeddings densos, BM25 y reranker."""

from functools import lru_cache

from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder
from qdrant_client.models import SparseVector

from rag.config import settings


@lru_cache
def _dense() -> TextEmbedding:
    return TextEmbedding(settings.embed_model, cache_dir=settings.embed_cache_dir)


@lru_cache
def _sparse() -> SparseTextEmbedding:
    return SparseTextEmbedding("Qdrant/bm25", cache_dir=settings.embed_cache_dir, language="spanish")


@lru_cache
def _reranker() -> TextCrossEncoder:
    return TextCrossEncoder(settings.rerank_model, cache_dir=settings.embed_cache_dir)


def embed(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in _dense().embed(texts)]


def embed_sparse(texts: list[str], query: bool = False) -> list[SparseVector]:
    # BM25 pondera distinto la consulta y los documentos.
    model = _sparse()
    vectors = model.query_embed(texts) if query else model.embed(texts)
    return [SparseVector(indices=v.indices.tolist(), values=v.values.tolist()) for v in vectors]


def rerank(query: str, documents: list[str]) -> list[float]:
    return list(_reranker().rerank(query, documents))


def warm_up() -> None:
    """Descarga y carga todos los modelos (en el build de la imagen y al arrancar la API)."""
    embed(["warm-up"])
    embed_sparse(["warm-up"])
    if settings.rerank_model:
        rerank("warm-up", ["warm-up"])
