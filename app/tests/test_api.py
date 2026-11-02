import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from rag import api
from rag.config import settings
from rag.llm import Usage

HIT = SimpleNamespace(
    score=0.91234,
    payload={
        "text": "La actividad 1 se entrega el 15 de noviembre.",
        "subject": "devops",
        "material_type": "vtt",
        "source": "clase-01.vtt",
        "location": "00:01:05",
    },
)
HEADERS = {"X-API-Key": "secret"}


@pytest.fixture
def queries(monkeypatch):
    """Registra las consultas que llegan a la búsqueda."""
    seen = []
    monkeypatch.setattr(settings, "api_key", "secret")
    monkeypatch.setattr(api.retrieval, "search", lambda _, query, __: seen.append(query) or [HIT])
    monkeypatch.setattr(api.retrieval, "rerank_hits", lambda _, hits: hits)
    monkeypatch.setattr(api.llm, "answer", lambda *_: ("El 15 de noviembre [1].", Usage(120, 8)))
    monkeypatch.setattr(api.llm, "stream", lambda *_: iter(["El 15 ", "de noviembre [1].", Usage(120, 8)]))
    return seen


@pytest.fixture
def client(queries):
    # Sin "with": no se ejecuta el lifespan, así que no se cargan los modelos.
    return TestClient(api.app)


def test_ask_requires_api_key(client):
    assert client.post("/ask", json={"question": "¿Cuándo?"}).status_code == 401


def test_ask_returns_answer_with_sources(client):
    response = client.post("/ask", json={"question": "¿Cuándo se entrega?"}, headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "El 15 de noviembre [1]."
    assert body["sources"][0] == {
        "subject": "devops",
        "material_type": "vtt",
        "source": "clase-01.vtt",
        "location": "00:01:05",
        "score": 0.912,
    }
    assert body["usage"] == {"prompt_tokens": 120, "completion_tokens": 8}


def test_ask_stream_sends_sources_tokens_and_usage(client):
    response = client.post("/ask/stream", json={"question": "¿Cuándo?"}, headers=HEADERS)
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [e["type"] for e in events] == ["sources", "token", "token", "done"]
    assert "".join(e["text"] for e in events if e["type"] == "token") == "El 15 de noviembre [1]."
    assert events[-1]["usage"] == {"prompt_tokens": 120, "completion_tokens": 8}


def test_follow_up_question_searches_with_previous_question(client, queries):
    history = [
        {"role": "user", "content": "Actividad 1 de DevOps"},
        {"role": "assistant", "content": "Consiste en montar un pipeline [1]."},
    ]
    client.post("/ask", json={"question": "¿Cuándo se entrega?", "history": history}, headers=HEADERS)
    assert queries == ["Actividad 1 de DevOps ¿Cuándo se entrega?"]


def test_metrics_exposes_tokens(client):
    client.post("/ask", json={"question": "x"}, headers=HEADERS)
    metrics = client.get("/metrics/").text
    assert 'rag_llm_tokens_total{type="prompt"}' in metrics
    assert 'rag_request_duration_seconds_count{stage="rerank"}' in metrics


def test_index_serves_chat_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Asistente del máster" in response.text
