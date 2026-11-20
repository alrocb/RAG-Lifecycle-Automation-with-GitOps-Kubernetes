# Ficheros del repositorio

Qué contiene cada fichero, qué hace y por qué existe. Las decisiones de fondo se justifican en [decisiones.md](decisiones.md) (ADR-xxx).

## Raíz

| Fichero | Qué es y qué hace | Por qué existe |
| --- | --- | --- |
| `README.md` | Presentación del proyecto, arranque en local, variables de configuración y enlaces a `docs/` | Punto de entrada de quien abre el repositorio |
| `docker-compose.yml` | Define el entorno local: Qdrant, mock-llm, la API y dos tareas de un solo uso (`ingest` y `convert-ppt`) | Desarrollar y probar en el equipo sin AWS ni Kubernetes |
| `.env.example` | Plantilla de variables para usar un LLM real en local (se copia a `.env`) | Documentar qué hay que rellenar sin guardar claves en Git |
| `.gitignore` | Lo que Git nunca debe guardar: `data/`, `.secrets/`, `.aws/`, `.env`, el estado y los planes de Terraform, entornos de Python | Evitar subir materiales con derechos de terceros, credenciales y secretos (ADR-014, RNF4) |
| `.gitattributes` | Fuerza saltos de línea LF en los `.sh` y `.tftpl` | En Windows, Git los convertiría a CRLF y los scripts fallarían al ejecutarse en Linux |

## `.github/workflows/`

| Fichero | Qué es y qué hace | Por qué existe |
| --- | --- | --- |
| `ci.yml` | Integración continua en GitHub Actions. En cada push y pull request: pruebas y lint de Python, validación de Terraform y de los charts. En `main`, si cambia el código: publica las imágenes en GHCR con el SHA del commit y escribe esa etiqueta en `gitops/rag/values.yaml` | OE4. El CI no despliega: escribe en Git y Argo CD despliega (ADR-015, ADR-016) |

## `app/`: la aplicación (API e ingesta)

| Fichero | Qué es y qué hace | Por qué existe |
| --- | --- | --- |
| `Dockerfile` | Construye la imagen `rag-app`: instala el paquete, crea un usuario sin privilegios y descarga los modelos dentro de la imagen | Una sola imagen para API e ingesta; arranque sin depender de internet (ADR-012) |
| `pyproject.toml` | Dependencias del paquete `rag` y de desarrollo (pytest, ruff), con versiones mínimas; spaCy y su modelo español fijados | Instalación reproducible con `pip install -e .` |
| `src/rag/config.py` | Toda la configuración, leída de variables de entorno (URL de Qdrant, LLM, modelos, umbrales…) | Un único sitio para la configuración; lo mismo funciona en local y en Kubernetes |
| `src/rag/api.py` | La API (FastAPI): `/ask`, `/ask/stream`, `/subjects`, `/healthz`, `/readyz`, `/metrics` y la página del chat. Mide la latencia de cada etapa | RF3, RF5; base de la observabilidad (OE7) |
| `src/rag/retrieval.py` | Búsqueda híbrida en Qdrant (densa + BM25 con RRF), reordenación y filtro de relevancia; lista de asignaturas | ADR-005, ADR-006 |
| `src/rag/embeddings.py` | Carga los tres modelos locales (embeddings, BM25 y reordenación) y los expone como funciones simples | ADR-003: todo en local y en CPU |
| `src/rag/context.py` | Construye la cabecera de contexto de cada fragmento («asignatura · tipo · documento · ubicación») | ADR-007: que una tabla de rúbrica se encuentre por su actividad |
| `src/rag/llm.py` | Construye el prompt y llama al LLM (respuesta completa o por partes), con el formato de la API de OpenAI | ADR-009: cambiar de proveedor sin tocar código |
| `src/rag/metrics.py` | Define las tres métricas de Prometheus: latencia por etapa, tokens y errores | OE7; datos para la evaluación |
| `src/rag/static/index.html` | El chat web: una sola página sin dependencias externas | ADR-011 |
| `src/rag/ingest/__main__.py` | Programa de ingesta (`python -m rag.ingest`): descarga de S3 si se indica, lee, anonimiza, trocea e indexa; `--if-missing` no hace nada si ya hay índice | OE6, RF4 (ADR-027, ADR-029) |
| `src/rag/ingest/parsers.py` | Lectores de VTT, PDF, PPTX y DOCX; cada uno devuelve secciones con su ubicación para citar | RF1; quita las etiquetas de hablante de Teams |
| `src/rag/ingest/anonymize.py` | Anonimización en capas: etiquetas, spaCy filtrado por nombres de pila, términos técnicos, lista manual | RF2 (ADR-008) |
| `src/rag/ingest/nombres_de_pila.txt` | ~300 nombres de pila frecuentes en España y Latinoamérica | Distinguir nombres reales de falsos positivos de spaCy |
| `src/rag/ingest/terminos_tecnicos.txt` | ~100 herramientas que spaCy confunde con personas (Helm, Jenkins…) | Que el temario no se borre al anonimizar |
| `src/rag/ingest/chunking.py` | Trocea el texto en fragmentos de 800 caracteres con 100 de solapamiento | Que una idea no se pierda entre dos fragmentos |
| `src/rag/ingest/indexer.py` | Recorre `data/<asignatura>/`, genera los fragmentos con metadatos, crea la colección nueva y mueve el alias | OE6: reindexar sin corte (ADR-004) |
| `src/rag/ingest/sources.py` | Descarga el bucket S3 de materiales a una carpeta, conservando las subcarpetas | Fase 5 (ADR-029) |
| `tests/` | 36 pruebas automáticas con pytest (lectores, anonimización, troceado, alias, búsqueda, API, descarga) y dos transcripciones inventadas en `fixtures/` | Comprobar cada pieza sin modelos reales ni red; el CI las ejecuta en cada push |

## `mock-llm/`: el LLM simulado

| Fichero | Qué es y qué hace | Por qué existe |
| --- | --- | --- |
| `app.py` | Servicio que imita `/v1/chat/completions` de OpenAI: respuesta fija, latencia configurable, recuento aproximado de tokens, también por partes | Pruebas de carga repetibles y sin coste (ADR-009) |
| `Dockerfile` | Imagen mínima del servicio | Desplegarlo como un contenedor más |

## `charts/rag/`: chart de Helm de la aplicación

| Fichero | Qué es y qué hace | Por qué existe |
| --- | --- | --- |
| `Chart.yaml` | Nombre y versión del chart | Requisito de Helm |
| `values.yaml` | Valores por defecto: imágenes, recursos, LLM, ingesta y candidatos de la reordenación en el clúster (5, ADR-031) | Un único sitio para ajustar el despliegue |
| `templates/api.yaml` | Deployment y Service de la API, con sondas de arranque (carga de modelos), de vida y de disponibilidad (`/readyz`) | La API no recibe tráfico hasta que puede responder |
| `templates/qdrant.yaml` | StatefulSet y Service de Qdrant con un volumen persistente | El índice sobrevive a reinicios del pod |
| `templates/mock-llm.yaml` | Deployment y Service del LLM simulado (solo si `llm.mock` es `true`) | Se puede quitar al usar un LLM real |
| `templates/ingress.yaml` | Entrada web por Traefik con el nombre público y el certificado de cert-manager | Acceso por HTTPS (RNF4) |
| `templates/ingest.yaml` | CronJob de reindexación diaria y Job inicial (*hook* de Argo CD con `--if-missing`) | Fase 5 (ADR-027) |
| `templates/_ingest.tpl` | Plantilla del pod de ingesta, común a los dos anteriores | No repetir la misma definición dos veces |

## `gitops/`: lo que Argo CD sincroniza

| Fichero | Qué es y qué hace | Por qué existe |
| --- | --- | --- |
| `apps/Chart.yaml`, `apps/values.yaml` | Chart *app of apps*: genera las aplicaciones de Argo CD. Sus valores (nombre público, bucket, región) los pasa Terraform | ADR-022, ADR-023: lo que depende del entorno no va en Git |
| `apps/templates/cert-manager.yaml` | Aplicación de Argo CD que instala cert-manager desde su repositorio oficial (versión fijada) | Certificados HTTPS automáticos |
| `apps/templates/sealed-secrets.yaml` | Aplicación que instala el controlador de Sealed Secrets | Descifrar en el clúster los secretos de Git |
| `apps/templates/platform.yaml` | Aplicación que aplica `gitops/platform/` | Recursos que dependen de cert-manager |
| `apps/templates/rag.yaml` | Aplicación de la app: el chart `charts/rag` con `gitops/rag/values.yaml` y los secretos de `gitops/rag/secrets/` | Une código, configuración y secretos en un despliegue |
| `platform/cluster-issuers.yaml` | Emisores de Let's Encrypt: producción y pruebas (*staging*) | Pedir los certificados (ADR-021) |
| `rag/values.yaml` | Valores del entorno; hoy solo la etiqueta de imagen, que escribe el CI | El punto donde el CI y Argo CD se encuentran (ADR-016) |
| `rag/secrets/rag-secrets.yaml` | `SealedSecret` con la API key de la app y la clave del LLM, cifrados | Secretos en Git sin exponerlos (ADR-024) |
| `sealed-secrets-cert.pem` | Certificado **público** de Sealed Secrets | Cifrar secretos sin acceso al clúster; no permite descifrar |

## `infra/`: infraestructura y scripts

| Fichero | Qué es y qué hace | Por qué existe |
| --- | --- | --- |
| `cluster/versions.tf` | Versiones de Terraform y del proveedor de AWS; estado en S3 con bloqueo | Reproducibilidad; estado fuera del equipo (ADR-019) |
| `cluster/variables.tf` | Parámetros: región, tamaño de la máquina, versiones de k3s y Argo CD, repositorio… | Adaptar a otra cuenta o región sin tocar el código |
| `cluster/main.tf` | Red (VPC, subred, rutas), grupo de seguridad (solo 80/443), rol para cuenta propia, máquina EC2, IP fija y presupuesto opcional | OE3 |
| `cluster/outputs.tf` | Lo que Terraform informa al terminar: id de la máquina, IP, direcciones y bucket | Saber a dónde conectarse |
| `cluster/install-k3s.sh.tftpl` | Script de arranque de la máquina: instala k3s, carga la clave de Sealed Secrets desde SSM, instala Argo CD y crea la aplicación raíz con los valores del entorno | Que `terraform apply` deje todo funcionando sin pasos manuales (ADR-022) |
| `cluster/terraform.tfvars.example` | Ejemplo de valores para el Learner Lab y para cuenta propia | El `terraform.tfvars` real no se versiona |
| `cluster/.terraform.lock.hcl` | Versiones exactas y huellas del proveedor de AWS | Que todos usen el mismo proveedor (ADR-025) |
| `bootstrap.sh` | Prepara una cuenta: buckets privados del estado y de los materiales, y la clave de Sealed Secrets en SSM | Lo que Terraform no puede o no debe crear (ADR-019) |
| `sealed-secrets-key.sh` | Sube la clave privada de Sealed Secrets a SSM Parameter Store | La misma clave en cada clúster (ADR-024) |
| `upload-materials.sh` | Sincroniza `data/` con el bucket de materiales | Actualizar la base de conocimiento (ADR-026) |
| `argocd-password.sh` | Muestra la contraseña de `admin` de Argo CD (vía SSM) | Entrar en el panel sin recordar comandos |

## `docs/`

| Fichero | Contenido |
| --- | --- |
| `README.md` | Índice y convenciones |
| `acceso.md` | Las direcciones web, cómo entrar y qué hacer en cada una |
| `argocd.md` | Argo CD a fondo: qué es, cómo funciona, cómo se usa aquí y qué se puede hacer desde su web |
| `operacion.md` | Procedimiento por sesión: levantar, actualizar, destruir |
| `arquitectura.md` | Componentes y flujos con diagramas |
| `decisiones.md` | Decisiones de diseño justificadas (ADR) |
| `proceso.md` | Bitácora por fases |
| `mediciones.md` | Cifras medidas |
| `ficheros.md` | Este documento |

## Ficheros locales que no están en Git

| Ruta | Qué contiene | Por qué no está en Git |
| --- | --- | --- |
| `data/` | Materiales de las asignaturas | Derechos de terceros y datos personales |
| `.secrets/sealed-secrets.key` | Clave **privada** de Sealed Secrets | Descifra todos los secretos; es el secreto raíz |
| `.secrets/api-key.txt` | API key de la aplicación en claro | Credencial |
| `.aws/credentials` | Credenciales temporales del Learner Lab | Credencial |
| `infra/cluster/terraform.tfvars` | Valores del entorno (región, perfil del lab) | Pueden incluir datos personales (correo del presupuesto) |
| `.env` | Clave del LLM real para el entorno local | Credencial |
