import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from prometheus_client import make_asgi_app
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint

from rag import llm, retrieval
from rag.config import settings
from rag.embeddings import warm_up
from rag.metrics import ERRORS, LATENCY, TOKENS

log = logging.getLogger("rag.api")
qdrant = QdrantClient(url=settings.qdrant_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    warm_up()  # carga los modelos antes de recibir tráfico
    yield


app = FastAPI(title="RAG API", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    subject: str | None = None
    history: list[Message] = []


def check_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="API key no válida")


def retrieve(request: AskRequest) -> list[ScoredPoint]:
    # En preguntas de seguimiento ("¿y cuándo se entrega?") se busca también con la anterior.
    previous = [m.content for m in request.history if m.role == "user"]
    query = f"{previous[-1]} {request.question}" if previous else request.question
    with LATENCY.labels("retrieval").time():
        hits = retrieval.search(qdrant, query, request.subject)
    with LATENCY.labels("rerank").time():
        return retrieval.rerank_hits(query, hits)


def to_sources(hits: list[ScoredPoint]) -> list[dict]:
    return [
        {
            "subject": hit.payload["subject"],
            "material_type": hit.payload["material_type"],
            "source": hit.payload["source"],
            "location": hit.payload["location"],
            "score": round(hit.score, 3),
        }
        for hit in hits
    ]


def record_usage(usage: llm.Usage) -> None:
    TOKENS.labels("prompt").inc(usage.prompt_tokens)
    TOKENS.labels("completion").inc(usage.completion_tokens)


@app.post("/ask", dependencies=[Depends(check_api_key)])
def ask(request: AskRequest) -> dict:
    history = [m.model_dump() for m in request.history]
    with LATENCY.labels("total").time():
        try:
            hits = retrieve(request)
            with LATENCY.labels("llm").time():
                text, usage = llm.answer(request.question, [h.payload for h in hits], history)
        except Exception:
            ERRORS.inc()
            raise
    record_usage(usage)
    return {"answer": text, "sources": to_sources(hits), "usage": usage._asdict()}


@app.post("/ask/stream", dependencies=[Depends(check_api_key)])
def ask_stream(request: AskRequest) -> StreamingResponse:
    """Una línea JSON por evento: sources, token (varios), done o error."""
    history = [m.model_dump() for m in request.history]

    def events():
        start = time.perf_counter()
        try:
            hits = retrieve(request)
            yield json.dumps({"type": "sources", "sources": to_sources(hits)}) + "\n"
            with LATENCY.labels("llm").time():
                for item in llm.stream(request.question, [h.payload for h in hits], history):
                    if isinstance(item, llm.Usage):
                        record_usage(item)
                        yield json.dumps({"type": "done", "usage": item._asdict()}) + "\n"
                    else:
                        yield json.dumps({"type": "token", "text": item}) + "\n"
        except Exception:
            ERRORS.inc()
            log.exception("Error respondiendo a /ask/stream")
            yield json.dumps({"type": "error", "detail": "Error generando la respuesta"}) + "\n"
        finally:
            LATENCY.labels("total").observe(time.perf_counter() - start)

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.get("/subjects", dependencies=[Depends(check_api_key)])
def subjects() -> list[str]:
    return retrieval.subjects(qdrant)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict:
    aliases = {a.alias_name for a in qdrant.get_aliases().aliases}
    if settings.collection_alias not in aliases:
        raise HTTPException(status_code=503, detail="La base de conocimiento aún no está indexada")
    return {"status": "ready"}
