"""LLM simulado compatible con /v1/chat/completions de OpenAI (con y sin streaming).

Da una carga controlada y repetible para las pruebas, sin coste ni límites de uso.
"""

import asyncio
import json
import os
import random
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

LATENCY = float(os.getenv("MOCK_LATENCY_SECONDS", "0.5"))  # hasta el primer token
JITTER = float(os.getenv("MOCK_JITTER_SECONDS", "0.1"))
TOKEN_DELAY = float(os.getenv("MOCK_TOKEN_SECONDS", "0.02"))  # entre tokens en streaming

CONTENT = (
    "Respuesta simulada: según los materiales recuperados [1], el tema se explica en clase "
    "y se complementa con la documentación de la asignatura [2]."
)

app = FastAPI(title="mock-llm")


def usage(body: dict) -> dict:
    prompt = " ".join(m.get("content", "") for m in body.get("messages", []))
    # Aproximación habitual: ~4 caracteres por token.
    prompt_tokens, completion_tokens = len(prompt) // 4, len(CONTENT) // 4
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def chunk(base: dict, **fields) -> str:
    return f"data: {json.dumps({**base, 'object': 'chat.completion.chunk', **fields})}\n\n"


async def stream(body: dict, base: dict):
    for i, word in enumerate(CONTENT.split(" ")):
        delta = {"content": word if i == 0 else f" {word}"}
        yield chunk(base, choices=[{"index": 0, "delta": delta, "finish_reason": None}])
        await asyncio.sleep(TOKEN_DELAY)
    yield chunk(base, choices=[{"index": 0, "delta": {}, "finish_reason": "stop"}])
    if body.get("stream_options", {}).get("include_usage"):
        yield chunk(base, choices=[], usage=usage(body))
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(body: dict):
    await asyncio.sleep(max(0.0, LATENCY + random.uniform(-JITTER, JITTER)))
    base = {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "created": int(time.time()),
        "model": body.get("model", "mock"),
    }
    if body.get("stream"):
        return StreamingResponse(stream(body, base), media_type="text/event-stream")
    return {
        **base,
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": CONTENT},
                "finish_reason": "stop",
            }
        ],
        "usage": usage(body),
    }


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}
