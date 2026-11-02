# RAG-Lifecycle-Automation-with-GitOps-Kubernetes
An end-to-end DevOps project focused on automating the deployment, operation, and lifecycle management of RAG systems using Kubernetes (k3s), Terraform, Helm, and Argo CD. Includes CI/CD pipelines, automated knowledge base updates with zero downtime, and observability with Prometheus, Grafana, and Loki.

## Estructura

| Carpeta | Contenido |
|---|---|
| `app/` | API RAG (FastAPI) e ingesta. Una sola imagen: `uvicorn rag.api:app` o `python -m rag.ingest` |
| `mock-llm/` | LLM simulado compatible con la API de OpenAI, para pruebas sin coste |
| `docker-compose.yml` | Entorno local: Qdrant + mock-llm + API |

## Arrancar en local

```bash
docker compose up -d --build
docker compose run --rm ingest          # indexa app/tests/fixtures/data (datos sintéticos)
curl -X POST localhost:8000/ask -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
     -d '{"question": "Cuando se entrega la actividad 1?"}'
```

Para indexar materiales reales: `DATA_DIR=./data docker compose run --rm ingest`. La carpeta `data/` está en `.gitignore`; los materiales nunca se suben al repositorio. Estructura esperada: `data/<asignatura>/<fichero>.{vtt,pdf,pptx}`.

## Cómo funciona

- **Ingesta**: lee VTT (agrupado por minuto), PDF (por página) y PPTX (por diapositiva), anonimiza, trocea y genera embeddings en local con fastembed.
- **Anonimización** (antes de indexar): quita las etiquetas de voz de VTT, sustituye por `[PERSONA]` los nombres que detecta spaCy (`es_core_news_md`) y los de `NAMES_FILE`. spaCy confunde algunas herramientas con personas (Helm, Jenkins, Grafana…); los términos de [terminos_tecnicos.txt](app/src/rag/ingest/terminos_tecnicos.txt) nunca se anonimizan. Si alguno aparece como `[PERSONA]` por error, se añade ahí.
- **Reindexación sin corte**: cada ejecución crea una colección nueva `materials_<timestamp>` y mueve el alias `materials` de forma atómica. La API siempre consulta el alias. Se conserva la colección anterior para volver atrás.
- **Búsqueda**: híbrida, semántica (embeddings densos) + palabras exactas (BM25 en español), fusionada con RRF en Qdrant. Los 20 candidatos se reordenan con un cross-encoder multilingüe (`bge-reranker-v2-m3-int8`) y los 5 mejores van al LLM. Los que el reranker puntúa por debajo de `RERANK_MIN_SCORE` se descartan, así que una pregunta fuera del temario no recibe fuentes.
- **Conversación**: el cliente envía el historial; el servidor no guarda estado. En las preguntas de seguimiento se busca también con la pregunta anterior.
- **API**: `GET /` (chat), `POST /ask` (respuesta completa), `POST /ask/stream` (streaming NDJSON: `sources`, `token`…, `done`), `GET /subjects`, `GET /healthz`, `GET /readyz` (falla si no hay índice) y `GET /metrics` (latencia por etapa `retrieval`/`rerank`/`llm`/`total`, tokens y errores). Todo salvo salud y métricas exige la cabecera `X-API-Key`.
- **LLM**: cualquier API compatible con OpenAI. Por defecto el mock; para un proveedor real basta con cambiar `LLM_BASE_URL`, `LLM_MODEL` y `LLM_API_KEY`.

## Configuración

| Variable | Por defecto |
|---|---|
| `QDRANT_URL` | `http://localhost:6333` |
| `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | `http://localhost:8001/v1` / `mock` / `not-needed` |
| `API_KEY` | vacío = sin autenticación (solo local) |
| `EMBED_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `RERANK_MODEL` / `RERANK_MIN_SCORE` | `BAAI/bge-reranker-v2-m3-int8` (vacío = sin reordenación) / `-3` |
| `NER_MODEL` | `es_core_news_md` (vacío = sin detección automática de nombres) |
| `CANDIDATES` / `TOP_K` / `MAX_HISTORY` | `20` / `5` / `6` |
| `NAMES_FILE` | fichero con nombres a anonimizar, uno por línea |
| `MOCK_LATENCY_SECONDS` / `MOCK_TOKEN_SECONDS` (mock-llm) | `0.5` / `0.02` |

## Tests

```bash
cd app
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"   # en Linux/macOS: .venv/bin/pip
.venv/Scripts/pytest -q
```

En Windows con *Control inteligente de aplicaciones* activado, spaCy no puede cargarse y su test se salta; se ejecuta en CI y dentro de Docker.
