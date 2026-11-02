from prometheus_client import Counter, Histogram

# stage = retrieval | rerank | llm | total
LATENCY = Histogram("rag_request_duration_seconds", "Latencia de /ask por etapa", ["stage"])
# type = prompt | completion
TOKENS = Counter("rag_llm_tokens_total", "Tokens consumidos en el LLM", ["type"])
ERRORS = Counter("rag_request_errors_total", "Peticiones a /ask que han fallado")
