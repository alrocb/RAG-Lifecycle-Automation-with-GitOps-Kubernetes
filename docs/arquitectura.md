# Arquitectura

El sistema es un conjunto de componentes independientes en contenedores, desplegados en un clúster k3s de un solo nodo sobre una máquina virtual de AWS. Todo se crea desde código: Terraform crea la máquina y el arranque deja el clúster en manos de Argo CD, que despliega el resto desde este repositorio.

## Vista general

```mermaid
flowchart LR
  subgraph dev[Desarrollo y GitHub]
    repo[Repositorio Git<br/>código, Terraform, charts, gitops/]
    ci[GitHub Actions<br/>pruebas, validación, imágenes]
    ghcr[(GHCR<br/>imágenes)]
    tf[Terraform<br/>desde el equipo local]
  end
  subgraph aws[AWS · us-east-1]
    s3[(Bucket S3<br/>estado de Terraform)]
    mat[(Bucket S3 privado<br/>materiales)]
    ssm[(SSM Parameter Store<br/>clave de Sealed Secrets)]
    subgraph ec2[EC2 t3.large · k3s]
      traefik[Traefik<br/>entrada web 80/443]
      argocd[Argo CD]
      certm[cert-manager]
      sealed[Sealed Secrets]
      api[API rag-app]
      qdrant[(Qdrant)]
      mock[mock-llm]
      ingest[Ingesta]
    end
  end
  user[Navegador] -->|HTTPS rag.ip.sslip.io| traefik --> api
  api --> qdrant
  api --> mock
  ingest -->|colección nueva + alias| qdrant
  ingest -.->|descarga con el rol de la máquina| mat
  data[data/ local] -->|upload-materials.sh| mat
  repo --> ci -->|push imagen| ghcr
  ci -->|commit con la etiqueta| repo
  argocd -->|lee gitops/ y charts/| repo
  argocd -->|despliega| api
  ec2 -.->|descarga imágenes| ghcr
  tf --> ec2
  tf --> s3
  ec2 -.->|al arrancar| ssm
```

## Componentes

| Componente | Qué hace | Dónde está definido |
| --- | --- | --- |
| API (`rag-app`) | Recibe preguntas, busca en Qdrant, reordena, llama al LLM y responde con fuentes; sirve el chat web y las métricas | `app/src/rag/`, `charts/rag/templates/api.yaml` |
| Ingesta | Descarga los materiales del bucket privado, anonimiza, trocea, vectoriza y construye una colección nueva; mueve el alias. Se ejecuta como CronJob diario y como Job inicial (solo si no hay índice) | `app/src/rag/ingest/` (misma imagen que la API), `charts/rag/templates/ingest.yaml` |
| Bucket de materiales | Almacenamiento privado de los ficheros de las asignaturas, fuera de Git | `infra/bootstrap.sh`, `infra/upload-materials.sh` |
| Qdrant | Base de datos vectorial con vectores densos y BM25; la API consulta siempre el alias `materials` | `charts/rag/templates/qdrant.yaml` |
| mock-llm | Imita la API de OpenAI con respuesta fija y latencia configurable | `mock-llm/`, `charts/rag/templates/mock-llm.yaml` |
| Traefik | Controlador de entrada incluido en k3s; recibe el tráfico de los puertos 80 y 443 | k3s |
| cert-manager | Pide y renueva los certificados TLS a Let's Encrypt | `gitops/apps/templates/cert-manager.yaml`, `gitops/platform/` |
| Sealed Secrets | Descifra en el clúster los secretos cifrados guardados en Git | `gitops/apps/templates/sealed-secrets.yaml` |
| Argo CD | Compara el clúster con Git y lo sincroniza; corrige cambios manuales | arranque de la máquina (`infra/cluster/install-k3s.sh.tftpl`) |
| Infraestructura | VPC, subred, grupo de seguridad, EC2, IP elástica | `infra/cluster/` (Terraform) |

## Flujo de una consulta

```mermaid
flowchart LR
  q[Pregunta<br/>+ la anterior si es seguimiento] --> d[Búsqueda semántica<br/>10 resultados]
  q --> b[Búsqueda BM25<br/>10 resultados]
  d --> f[Fusión RRF<br/>10 candidatos]
  b --> f
  f --> r[Reordenación<br/>bge-reranker-v2-m3<br/>descarta si puntúa menos de −3]
  r -->|hasta 5 fragmentos| l[LLM<br/>simulado o externo]
  l --> a[Respuesta en streaming<br/>con fuentes citadas]
```

## Flujo de reindexación sin corte

```mermaid
sequenceDiagram
  participant I as Ingesta
  participant Q as Qdrant
  participant A as API
  A->>Q: consulta alias "materials" (→ colección vieja)
  I->>Q: crea materials_FECHA y la llena entera
  A->>Q: sigue consultando el alias (→ colección vieja)
  I->>Q: cambio atómico: alias → colección nueva
  A->>Q: consulta alias (→ colección nueva)
  I->>Q: borra colecciones más antiguas que la anterior
```

## Flujo de un cambio hasta producción (GitOps)

```mermaid
sequenceDiagram
  participant Dev as Desarrollador
  participant GH as GitHub (main)
  participant CI as GitHub Actions
  participant R as GHCR
  participant AR as Argo CD
  participant K as Clúster
  Dev->>GH: push (cambio en app/)
  GH->>CI: dispara el workflow
  CI->>CI: pruebas, lint, validación de Terraform y Helm
  CI->>R: publica rag-app:SHA y rag-mock-llm:SHA
  CI->>GH: commit "deploy": tag = SHA en gitops/rag/values.yaml
  AR->>GH: sondea el repositorio (cada 3 min)
  AR->>K: aplica el chart con la etiqueta nueva
  K->>R: descarga las imágenes
```

El CI no tiene credenciales del clúster: la entrega la hace Argo CD tirando de Git (modelo *pull*). Ver ADR-016.

## Arranque del clúster desde cero

```mermaid
flowchart TD
  b[infra/bootstrap.sh<br/>bucket del estado + clave en SSM] --> t[terraform apply<br/>VPC, EC2, IP elástica · ~30 s]
  t --> k[Script de arranque de la EC2]
  k --> k1[Instala k3s con versión fijada]
  k1 --> k2[Lee la clave de Sealed Secrets de SSM<br/>y la carga como secreto del clúster]
  k2 --> k3[Instala Argo CD con el controlador Helm de k3s]
  k3 --> k4[Crea la aplicación raíz con el host de la IP]
  k4 --> a[Argo CD despliega gitops/apps:<br/>cert-manager, Sealed Secrets → emisores → aplicación RAG]
```

El arranque de la máquina termina en ~93 s; a partir de ahí todo lo demás llega desde Git sin intervención manual (RNF1, RNF2).

## Organización del repositorio

| Ruta | Contenido |
| --- | --- |
| `app/` | Aplicación (API e ingesta), pruebas y Dockerfile |
| `mock-llm/` | LLM simulado |
| `charts/rag/` | Chart de Helm de la aplicación |
| `gitops/apps/` | Chart "app of apps": las aplicaciones de Argo CD |
| `gitops/platform/` | Recursos de plataforma (emisores de certificados) |
| `gitops/rag/` | Valores del entorno (etiqueta de imagen) y secretos cifrados |
| `gitops/sealed-secrets-cert.pem` | Certificado público para cifrar secretos |
| `infra/cluster/` | Terraform de la infraestructura y script de arranque |
| `infra/bootstrap.sh`, `infra/sealed-secrets-key.sh` | Preparación de cada cuenta de AWS |
| `.github/workflows/ci.yml` | Integración continua |
| `docker-compose.yml` | Entorno de desarrollo local |
| `docs/` | Esta documentación |
