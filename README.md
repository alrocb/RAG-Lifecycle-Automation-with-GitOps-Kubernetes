# RAG-Lifecycle-Automation-with-GitOps-Kubernetes
An end-to-end DevOps project focused on automating the deployment, operation, and lifecycle management of RAG systems using Kubernetes (k3s), Terraform, Helm, and Argo CD. Includes CI/CD pipelines, automated knowledge base updates with zero downtime, and observability with Prometheus, Grafana, and Loki.

## Estructura

| Carpeta | Contenido |
|---|---|
| `app/` | API RAG (FastAPI) e ingesta. Una sola imagen: `uvicorn rag.api:app` o `python -m rag.ingest` |
| `mock-llm/` | LLM simulado compatible con la API de OpenAI, para pruebas sin coste |
| `docker-compose.yml` | Entorno local: Qdrant + mock-llm + API |
| `charts/rag/` | Chart de Helm de la aplicación: API, Qdrant, mock-llm e Ingress con TLS |
| `gitops/` | Lo que Argo CD sincroniza: aplicaciones (`apps/`), emisores de certificados (`platform/`), valores y secretos cifrados del entorno (`rag/`) |
| `infra/sealed-secrets-key.sh` | Sube la clave de Sealed Secrets a SSM Parameter Store (una vez por cuenta) |
| `infra/bootstrap.sh` | Crea el bucket S3 del estado de Terraform (una vez) |
| `infra/cluster/` | Terraform: VPC, máquina EC2 con k3s, IP fija, acceso por SSM y alerta de presupuesto |

## Arrancar en local

```bash
docker compose up -d --build
docker compose run --rm ingest          # indexa app/tests/fixtures/data (datos sintéticos)
curl -X POST localhost:8000/ask -H "X-API-Key: dev-key" -H "Content-Type: application/json" \
     -d '{"question": "Cuando se entrega la actividad 1?"}'
```

Para indexar materiales reales (la carpeta `data/` está en `.gitignore`; los materiales nunca se suben al repositorio):

```bash
docker compose run --rm convert-ppt              # una vez: .ppt antiguos -> PDF con LibreOffice
DATA_DIR=./data docker compose run --rm ingest   # ~7 min para ~130 ficheros (7.000 fragmentos)
```

Estructura esperada: `data/<asignatura>/<fichero>.{vtt,pdf,pptx,docx}`; el nombre de la carpeta es la asignatura. Los formatos no soportados se omiten y quedan en el log.

## Cómo funciona

- **Ingesta**: lee VTT (agrupado por minuto y sin las etiquetas de quién habla), PDF (por página), PPTX (por diapositiva) y DOCX (por apartado, más sus tablas), anonimiza, trocea y genera embeddings en local con fastembed. Cada fragmento se indexa con una cabecera de contexto (asignatura · tipo de material · documento · ubicación) para que, por ejemplo, la tabla de una rúbrica se encuentre al preguntar por "la actividad 3".
- **Anonimización** (antes de indexar): sustituye por `[PERSONA]` las etiquetas de hablante, las personas que detecta spaCy (`es_core_news_md`) y las palabras en mayúscula que son un nombre de pila, junto con sus apellidos. En transcripciones automáticas spaCy marca como persona muchas palabras que no lo son, así que solo cuenta lo que contiene un nombre de [nombres_de_pila.txt](app/src/rag/ingest/nombres_de_pila.txt) y no es una herramienta de [terminos_tecnicos.txt](app/src/rag/ingest/terminos_tecnicos.txt). Con los materiales reales esto bajó de ~4.800 sustituciones (la mayoría erróneas) a ~650. `NAMES_FILE` permite añadir nombres concretos.
- **Reindexación sin corte**: cada ejecución crea una colección nueva `materials_<timestamp>` y mueve el alias `materials` de forma atómica. La API siempre consulta el alias. Se conserva la colección anterior para volver atrás.
- **Búsqueda**: híbrida, semántica (embeddings densos) + palabras exactas (BM25 en español), fusionada con RRF en Qdrant. Los 10 primeros candidatos se reordenan con un cross-encoder multilingüe (`bge-reranker-v2-m3-int8`) y los 5 mejores van al LLM. El reranker es la etapa más cara: con 20 candidatos completos tardaba ~10 s por pregunta en CPU; con 10 recortados a 400 caracteres, ~1,6 s con el mismo resultado. Los que el reranker puntúa por debajo de `RERANK_MIN_SCORE` se descartan, así que una pregunta fuera del temario no recibe fuentes.
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
| `CANDIDATES` / `RERANK_MAX_CHARS` / `TOP_K` / `MAX_HISTORY` | `10` / `400` / `5` / `6` |
| `NAMES_FILE` | fichero con nombres a anonimizar, uno por línea |
| `MOCK_LATENCY_SECONDS` / `MOCK_TOKEN_SECONDS` (mock-llm) | `0.5` / `0.02` |

## Infraestructura en AWS

Requisitos: Terraform ≥ 1.10, AWS CLI con credenciales y el [plugin de Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).

Funciona en una cuenta propia o en **AWS Academy Learner Lab** (ver `terraform.tfvars.example`). En el Learner Lab:
- Región `us-east-1`, como máximo `t3.large` y sin crear roles de IAM: se usa `LabInstanceProfile`, que ya incluye SSM.
- Una política de la organización impide a Terraform gestionar buckets S3 (no puede leer su configuración de *object lock*); por eso el bucket del estado se crea con `infra/bootstrap.sh`.
- Las credenciales cambian en cada sesión: copiarlas desde *AWS Details* al perfil `[learnerlab]` y exportar `AWS_PROFILE=learnerlab`.
- Al acabar la sesión (4 h) el lab para la máquina; al volver a arrancarla, k3s y los pods se levantan solos y la IP fija se mantiene.

```bash
# 1. Una sola vez: bucket S3 del estado (script de AWS CLI; ver el porqué en el propio script)
BUCKET=$(infra/bootstrap.sh us-east-1)   # o la región de la cuenta

# 2. Clúster (copiar antes terraform.tfvars.example a terraform.tfvars)
terraform -chdir=infra/cluster init -backend-config="bucket=$BUCKET" -backend-config="region=us-east-1"
terraform -chdir=infra/cluster plan -out=cluster.tfplan
terraform -chdir=infra/cluster apply cluster.tfplan
```

El `apply` tarda ~35 s y k3s queda instalado en ~1 min más. No hay SSH ni API de Kubernetes expuestos; todo el acceso es por SSM:

```bash
ID=$(terraform -chdir=infra/cluster output -raw instance_id)
aws ssm start-session --target $ID                     # shell en la máquina
# o un comando suelto, sin plugin de Session Manager:
aws ssm send-command --instance-ids $ID --document-name AWS-RunShellScript --parameters 'commands=["k3s kubectl get pods -A"]'
# kubeconfig (una vez) y túnel a la API de Kubernetes en localhost:6443
aws ssm start-session --target $ID --document-name AWS-StartInteractiveCommand     --parameters command="sudo cat /etc/rancher/k3s/k3s.yaml" > ~/.kube/rag-tfm.yaml   # quitar las líneas de cabecera/pie de SSM
aws ssm start-session --target $ID --document-name AWS-StartPortForwardingSession     --parameters portNumber=6443,localPortNumber=6443
KUBECONFIG=~/.kube/rag-tfm.yaml kubectl get nodes
```

Coste: unos 0,10 $/h con la máquina encendida (t3.large + disco + IP). Para ahorrar, `aws ec2 stop-instances --instance-ids $ID` (la IP fija se mantiene). Todo se destruye con `terraform -chdir=infra/cluster destroy`.

## Despliegue GitOps

`terraform apply` deja el clúster listo para GitOps sin pasos manuales: el arranque de la máquina instala k3s, carga la clave de Sealed Secrets desde SSM Parameter Store, instala Argo CD y le pasa la aplicación raíz (`gitops/apps`). Desde ahí Argo CD despliega cert-manager, Sealed Secrets, los emisores de Let's Encrypt y la aplicación.

Flujo de un cambio: push a `main` → el CI prueba, publica `ghcr.io/alrocb/rag-app` y `rag-mock-llm` con el SHA del commit y escribe esa etiqueta en `gitops/rag/values.yaml` → Argo CD lo detecta y despliega.

Pasos de una sola vez:

```bash
infra/sealed-secrets-key.sh us-east-1      # sube la clave privada de .secrets/ a SSM
# En GitHub → Packages: poner rag-app y rag-mock-llm como públicos (el clúster las descarga sin credenciales)
```

Secretos: se cifran con el certificado público del repositorio, sin acceso al clúster:

```bash
kubectl create secret generic rag-secrets -n rag --from-literal=API_KEY=... --from-literal=LLM_API_KEY=...   --dry-run=client -o yaml | kubeseal --cert gitops/sealed-secrets-cert.pem --format yaml > gitops/rag/secrets/rag-secrets.yaml
```

Si cambia la IP fija, actualizar `host` en `gitops/rag/values.yaml` con la salida `app_host` de Terraform. Argo CD queda en la salida `argocd_host` (usuario `admin`; contraseña en el secreto `argocd-initial-admin-secret`).

## Tests

```bash
cd app
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"   # en Linux/macOS: .venv/bin/pip
.venv/Scripts/pytest -q
```

En Windows con *Control inteligente de aplicaciones* activado, spaCy no puede cargarse y su test se salta; se ejecuta en CI y dentro de Docker.
