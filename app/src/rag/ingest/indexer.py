import logging
from datetime import UTC, datetime
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    Distance,
    Modifier,
    PayloadSchemaType,
    PointStruct,
    SparseVectorParams,
    VectorParams,
)

from rag.context import with_context
from rag.embeddings import embed, embed_sparse
from rag.ingest.anonymize import anonymize
from rag.ingest.chunking import split
from rag.ingest.parsers import PARSERS

log = logging.getLogger("rag.ingest")

def load_documents(data_dir: Path, names: list[str]) -> list[dict]:
    """Lee data/<asignatura>/<fichero> y devuelve los fragmentos con sus metadatos."""
    payloads = []
    for path in sorted(p for p in data_dir.rglob("*") if p.is_file()):
        parser = PARSERS.get(path.suffix.lower())
        if parser is None:
            log.info("Formato no soportado, se omite: %s", path.name)
            continue
        try:
            sections = parser(path)
        except Exception:
            # Un fichero dañado no debe impedir reindexar el resto.
            log.exception("No se ha podido leer %s", path.name)
            continue
        parts = path.relative_to(data_dir).parts
        subject = parts[0] if len(parts) > 1 else "general"
        for section in sections:
            for chunk in split(anonymize(section.text, names)):
                payloads.append({
                    "text": chunk,
                    "subject": subject,
                    "material_type": path.suffix[1:].lower(),
                    "source": path.name,
                    "location": section.location,
                })
    return payloads


def current_collection(client: QdrantClient, alias: str) -> str | None:
    for a in client.get_aliases().aliases:
        if a.alias_name == alias:
            return a.collection_name
    return None


def reindex(client: QdrantClient, payloads: list[dict], alias: str) -> str:
    """Construye una colección nueva y mueve el alias a ella de forma atómica.

    Se conserva la colección anterior para poder volver atrás; las más antiguas se borran.
    """
    if not payloads:
        raise ValueError("No hay documentos que indexar")

    name = f"{alias}_{datetime.now(UTC):%Y%m%d%H%M%S%f}"
    texts = [with_context(p) for p in payloads]
    dense, sparse = embed(texts), embed_sparse(texts)
    client.create_collection(
        name,
        vectors_config={"dense": VectorParams(size=len(dense[0]), distance=Distance.COSINE)},
        # BM25: Qdrant calcula el IDF sobre la colección.
        sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
    )
    client.create_payload_index(name, "subject", field_schema=PayloadSchemaType.KEYWORD)
    client.upload_points(
        name,
        points=[
            PointStruct(id=i, vector={"dense": d, "bm25": s}, payload=p)
            for i, (d, s, p) in enumerate(zip(dense, sparse, payloads))
        ],
        wait=True,
    )

    previous = current_collection(client, alias)
    operations = [CreateAliasOperation(create_alias=CreateAlias(collection_name=name, alias_name=alias))]
    if previous:
        operations.insert(0, DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=alias)))
    client.update_collection_aliases(change_aliases_operations=operations)

    for collection in client.get_collections().collections:
        if collection.name.startswith(f"{alias}_") and collection.name not in (name, previous):
            client.delete_collection(collection.name)
    return name
