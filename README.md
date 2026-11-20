# RAG-Lifecycle-Automation-with-GitOps-Kubernetes
An end-to-end DevOps project focused on automating the deployment, operation, and lifecycle management of RAG systems using Kubernetes (k3s), Terraform, Helm, and Argo CD. Includes CI/CD pipelines, automated knowledge base updates with zero downtime, and observability with Prometheus, Grafana, and Loki.

Trabajo fin de máster (UNIR, Máster en DevOps): asistente RAG sobre los materiales de las asignaturas, desplegado y operado con infraestructura como código y GitOps.

## Documentación

Toda la documentación está en [docs/](docs/README.md):

| Documento | Qué responde |
| --- | --- |
| [docs/acceso.md](docs/acceso.md) | Qué es cada dirección web, cómo entrar y qué se puede hacer en cada una |
| [docs/operacion.md](docs/operacion.md) | Cómo levantar, actualizar y destruir el entorno en AWS |
| [docs/ficheros.md](docs/ficheros.md) | Qué es cada fichero del repositorio, qué hace y por qué existe |
| [docs/arquitectura.md](docs/arquitectura.md) | Cómo encajan las piezas, con diagramas |
| [docs/decisiones.md](docs/decisiones.md) | Por qué se hizo cada cosa así (decisiones justificadas) |
| [docs/proceso.md](docs/proceso.md) | Qué se hizo en cada fase, problemas y soluciones |
| [docs/mediciones.md](docs/mediciones.md) | Todas las cifras medidas |

## Arrancar en local

Requiere Docker Desktop.

```bash
docker compose up -d --build              # Qdrant + mock-llm + API
docker compose run --rm ingest            # indexa los datos de prueba (app/tests/fixtures/data)
```

El chat queda en http://localhost:8000 (API key: `dev-key`).

Con los materiales reales (carpeta `data/`, que nunca se sube a Git):

```bash
docker compose run --rm convert-ppt              # una vez: .ppt antiguos -> PDF con LibreOffice
DATA_DIR=./data docker compose run --rm ingest   # ~7 min para ~130 ficheros
```

Estructura esperada: `data/<asignatura>/<fichero>.{vtt,pdf,pptx,docx}`; el nombre de la carpeta es la asignatura.

Para usar un LLM real en lugar del simulado: copiar `.env.example` a `.env`, rellenar `LLM_BASE_URL`, `LLM_MODEL` y `LLM_API_KEY`, y volver a ejecutar `docker compose up -d`.

## Configuración de la aplicación

Variables de entorno de la API y la ingesta:

| Variable | Por defecto | Para qué |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Dónde está Qdrant |
| `LLM_BASE_URL` / `LLM_MODEL` / `LLM_API_KEY` | `http://localhost:8001/v1` / `mock` / `not-needed` | Qué LLM usar (cualquier API compatible con OpenAI) |
| `API_KEY` | vacío = sin autenticación (solo local) | Clave que exige la API |
| `EMBED_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Modelo de embeddings |
| `RERANK_MODEL` / `RERANK_MIN_SCORE` | `BAAI/bge-reranker-v2-m3-int8` / `-3` | Reordenación (vacío = sin ella) y umbral de relevancia |
| `CANDIDATES` / `RERANK_MAX_CHARS` / `TOP_K` / `MAX_HISTORY` | `10` / `400` / `5` / `6` | Ajustes de la búsqueda y del historial |
| `NER_MODEL` | `es_core_news_md` | Detección de nombres (vacío = desactivada) |
| `NAMES_FILE` | — | Fichero con nombres concretos a anonimizar |
| `MATERIALS_BUCKET` | — | Bucket S3 del que la ingesta descarga los materiales |
| `MOCK_LATENCY_SECONDS` / `MOCK_TOKEN_SECONDS` (mock-llm) | `0.5` / `0.02` | Latencia simulada |

## Pruebas

```bash
cd app
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # en Linux/macOS: .venv/bin/python
.venv/Scripts/python -m pytest -q
```

En Windows con *Control inteligente de aplicaciones* activado, spaCy no puede cargarse y su prueba se salta; se ejecuta en el CI y en Docker.
