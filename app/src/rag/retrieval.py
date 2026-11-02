from qdrant_client import QdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Prefetch,
    ScoredPoint,
)

from rag.config import settings
from rag.embeddings import embed, embed_sparse, rerank


def search(client: QdrantClient, query: str, subject: str | None = None) -> list[ScoredPoint]:
    """Búsqueda híbrida: semántica (densa) + palabras exactas (BM25), fusionadas con RRF."""
    # Siempre se consulta el alias, nunca la colección física: así la reindexación no corta el servicio.
    query_filter = None
    if subject:
        query_filter = Filter(must=[FieldCondition(key="subject", match=MatchValue(value=subject))])
    limit = settings.candidates
    return client.query_points(
        settings.collection_alias,
        prefetch=[
            Prefetch(query=embed([query])[0], using="dense", filter=query_filter, limit=limit),
            Prefetch(
                query=embed_sparse([query], query=True)[0],
                using="bm25",
                filter=query_filter,
                limit=limit,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=limit,
        with_payload=True,
    ).points


def rerank_hits(query: str, hits: list[ScoredPoint]) -> list[ScoredPoint]:
    """Reordena los candidatos con un cross-encoder, descarta los irrelevantes y deja los top_k."""
    if settings.rerank_model and hits:
        scores = rerank(query, [hit.payload["text"] for hit in hits])
        for hit, score in zip(hits, scores):
            hit.score = score
        relevant = [hit for hit in hits if hit.score >= settings.rerank_min_score]
        hits = sorted(relevant, key=lambda hit: hit.score, reverse=True)
    return hits[: settings.top_k]


def subjects(client: QdrantClient) -> list[str]:
    result = client.facet(settings.collection_alias, key="subject", limit=100)
    return sorted(hit.value for hit in result.hits)
