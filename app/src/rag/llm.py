from collections.abc import Iterator
from typing import NamedTuple

from openai import OpenAI

from rag.config import settings

client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)

SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas sobre los materiales del máster. "
    "Responde en español usando solo los fragmentos proporcionados y cita cada dato con su número, "
    "por ejemplo [1]. Si la respuesta no está en los fragmentos, dilo."
)


class Usage(NamedTuple):
    prompt_tokens: int
    completion_tokens: int


def build_messages(question: str, fragments: list[dict], history: list[dict]) -> list[dict]:
    context = "\n\n".join(
        f"[{i}] ({f['subject']} · {f['source']} · {f['location']})\n{f['text']}"
        for i, f in enumerate(fragments, start=1)
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history[-settings.max_history :],
        {"role": "user", "content": f"Fragmentos:\n{context}\n\nPregunta: {question}"},
    ]


def answer(question: str, fragments: list[dict], history: list[dict]) -> tuple[str, Usage]:
    response = client.chat.completions.create(
        model=settings.llm_model, messages=build_messages(question, fragments, history)
    )
    usage = response.usage
    return response.choices[0].message.content, Usage(usage.prompt_tokens, usage.completion_tokens)


def stream(question: str, fragments: list[dict], history: list[dict]) -> Iterator[str | Usage]:
    """Va devolviendo trozos de texto y, al final, el consumo de tokens."""
    chunks = client.chat.completions.create(
        model=settings.llm_model,
        messages=build_messages(question, fragments, history),
        stream=True,
        stream_options={"include_usage": True},
    )
    usage = Usage(0, 0)
    for chunk in chunks:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
        if chunk.usage:
            usage = Usage(chunk.usage.prompt_tokens, chunk.usage.completion_tokens)
    yield usage
