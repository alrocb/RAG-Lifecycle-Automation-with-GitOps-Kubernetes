# Registro de decisiones de diseño (ADR)

Cada decisión sigue el formato habitual de los *Architecture Decision Records*: contexto, decisión, alternativas consideradas, justificación y consecuencias. El criterio general es el de la sección 4.1.3 de la memoria: priorizar lo abierto, lo ligero y lo que se puede reproducir con código, y que cada pieza se pueda medir.

| ADR | Decisión | Estado |
| --- | --- | --- |
| 001 | Componentes desacoplados en contenedores | Aceptada |
| 002 | API en Python con FastAPI, sin LangChain | Aceptada |
| 003 | Embeddings, BM25 y reordenación locales en CPU | Aceptada |
| 004 | Qdrant con alias para reindexar sin corte | Aceptada |
| 005 | Búsqueda híbrida (densa + BM25) con RRF | Aceptada |
| 006 | Reordenación con 10 candidatos recortados y umbral −3 | Aceptada |
| 007 | Cabecera de contexto en cada fragmento | Aceptada |
| 008 | Anonimización en capas con lista de nombres de pila | Aceptada |
| 009 | LLM híbrido con formato de API de OpenAI | Aceptada |
| 010 | Servidor sin estado | Aceptada |
| 011 | Interfaz web servida por la propia API | Aceptada |
| 012 | Una sola imagen con los modelos dentro | Aceptada |
| 013 | Conversión previa de PPT a PDF | Aceptada |
| 014 | Materiales fuera del repositorio | Aceptada |
| 015 | GitHub Actions y GHCR | Aceptada |
| 016 | Modelo *pull*: el CI escribe en Git y Argo CD despliega | Aceptada |
| 017 | AWS Academy Learner Lab, con código válido para cuenta propia | Aceptada |
| 018 | EC2 t3.large con k3s de un nodo | Aceptada |
| 019 | Estado de Terraform en S3, creado con script | Aceptada |
| 020 | Administración por SSM, sin SSH | Aceptada |
| 021 | DNS con sslip.io y TLS con Let's Encrypt | Aceptada |
| 022 | Arranque: Argo CD instalado por k3s y *app of apps* | Aceptada |
| 023 | El nombre público lo inyecta Terraform | Aceptada |
| 024 | Sealed Secrets con clave propia guardada en SSM | Aceptada |
| 025 | Versiones fijadas y con al menos dos semanas | Aceptada |
| 026 | Materiales en un bucket S3 privado por cuenta | Aceptada |
| 027 | Ingesta en el clúster: CronJob y Job inicial con `--if-missing` | Aceptada |
| 028 | Credenciales de la ingesta: rol de la máquina vía IMDSv2 | Aceptada |
| 029 | La descarga de S3 la hace la propia ingesta | Aceptada |

---

## ADR-001. Componentes desacoplados en contenedores

- **Contexto.** OE2 pide una arquitectura modular. Un RAG tiene piezas con ciclos de vida distintos: la API está siempre en marcha, la ingesta se ejecuta de vez en cuando y el modelo de lenguaje puede cambiar de proveedor.
- **Decisión.** Cuatro componentes en contenedores separados (API, Qdrant, ingesta, LLM), comunicados por HTTP. La API y la ingesta solo se relacionan a través del alias de Qdrant.
- **Alternativas.** Un único proceso con todo dentro; Qdrant embebido en la API.
- **Justificación.** Permite actualizar o sustituir cada pieza sin tocar las demás, reindexar mientras la API responde y cambiar de LLM por configuración. Es además lo que Kubernetes gestiona de forma natural.
- **Consecuencias.** Más piezas que desplegar, que se compensa con Helm y Argo CD.

## ADR-002. API en Python con FastAPI, sin LangChain

- **Contexto.** La tabla 5 de la memoria dejaba pendiente si usar LangChain.
- **Decisión.** FastAPI con los clientes directos de Qdrant y de la API de OpenAI.
- **Alternativas.** LangChain o LlamaIndex.
- **Justificación.** El flujo son tres llamadas (vectorizar, buscar, generar). Sin capas intermedias cada etapa se cronometra por separado (latencia de búsqueda, reordenación y LLM en `/metrics`), hay menos dependencias y no hay cambios de API frecuentes de terceros. LangChain no aporta nada visible para el usuario en este caso.
- **Consecuencias.** Si en el futuro se quisieran agentes o cadenas complejas, habría que reconsiderarlo.

## ADR-003. Embeddings, BM25 y reordenación locales en CPU

- **Contexto.** La sección 4.1.1 señala que enviar los materiales a un tercero tiene implicaciones de privacidad y coste.
- **Decisión.** Generar embeddings (`paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensiones), vectores BM25 y la reordenación (`bge-reranker-v2-m3`, cuantizado) en local con fastembed, en CPU.
- **Alternativas.** API de embeddings de un proveedor; modelos más grandes (multilingual-e5-large, Qwen3-Embedding).
- **Justificación.** Indexar no envía ningún material fuera, no tiene coste por documento y no depende de la red. Se eligieron modelos multilingües (los materiales están en español) y pequeños, porque la máquina no tiene GPU.
- **Consecuencias.** La API ocupa ~1,5 GB de RAM y la imagen ~2,5 GB. La reordenación es la etapa más cara (ADR-006).

## ADR-004. Qdrant con alias para reindexar sin corte

- **Contexto.** OE6 y RF4 exigen actualizar la base de conocimiento sin interrumpir el servicio. Cambiar el modelo de embeddings obliga a reindexar todo (Gao et al., 2024).
- **Decisión.** Cada ingesta crea una colección nueva (`materials_<fecha>`), la llena entera y después mueve el alias `materials` en una operación atómica. La API consulta siempre el alias. Se conserva la colección anterior y se borran las demás.
- **Alternativas.** Actualizar la colección en caliente (añadir y borrar puntos); Milvus.
- **Justificación.** El cambio de alias es atómico según la documentación de Qdrant, así que la API nunca ve un índice a medio construir. Conservar la anterior permite volver atrás moviendo el alias. Qdrant frente a Milvus ya se justificó en el capítulo 2.
- **Consecuencias.** Durante la reindexación hay dos colecciones a la vez (el doble de disco por un rato). Comprobado con carga: 0 errores en dos reindexaciones (ver `mediciones.md`).

## ADR-005. Búsqueda híbrida (densa + BM25) con RRF

- **Contexto.** Las preguntas mezclan conceptos («qué es la infraestructura como código») y términos exactos (nombres de herramientas, siglas, códigos de actividad).
- **Decisión.** Dos búsquedas en una sola consulta a Qdrant, semántica y BM25 en español, fusionadas con Reciprocal Rank Fusion.
- **Alternativas.** Solo búsqueda densa; ponderar puntuaciones.
- **Justificación.** La búsqueda densa encuentra paráfrasis; BM25 acierta en términos exactos donde un modelo pequeño falla. RRF combina por posición y evita comparar puntuaciones de escalas distintas (Cormack et al., 2009).
- **Consecuencias.** Hay que calcular y guardar dos vectores por fragmento; el coste es pequeño.

## ADR-006. Reordenación con 10 candidatos recortados y umbral −3

- **Contexto.** Con los materiales reales, la reordenación de 20 candidatos completos tardaba ~10 s por pregunta en CPU, el 94 % del tiempo total.
- **Decisión.** Reordenar solo 10 candidatos y solo sus primeros 400 caracteres. Descartar los que puntúan por debajo de −3 (~5 % de probabilidad de ser relevantes) y quedarse con hasta 5.
- **Alternativas.** Quitar la reordenación; un modelo más pequeño (solo hay modelos en inglés de ese tamaño en fastembed).
- **Justificación.** Medido: 9,9 s → 1,6 s con el mismo mejor resultado. El umbral hace que una pregunta fuera del temario no reciba fuentes falsas.
- **Consecuencias.** Es configurable (`CANDIDATES`, `RERANK_MAX_CHARS`, `RERANK_MIN_SCORE`, `RERANK_MODEL=""` para desactivarla). En la t3.large (2 vCPU) será más lenta; es un buen ejemplo del equilibrio calidad–coste operativo para la evaluación.

## ADR-007. Cabecera de contexto en cada fragmento

- **Contexto.** Un fragmento suelto, como la tabla de una rúbrica, no dice a qué asignatura ni a qué actividad pertenece, y no aparecía al preguntar por él.
- **Decisión.** Antes de vectorizar se antepone «asignatura · tipo de material · documento · ubicación». El nombre del fichero se normaliza (`mudevops05_act1` → «actividad 1»). El texto mostrado al usuario no la incluye.
- **Alternativas.** Solo filtrar por metadatos; trocear de otra forma.
- **Justificación.** Medido: «rúbrica de la actividad 3» pasó a encontrar el enunciado correcto.
- **Consecuencias.** Depende de que los nombres de los ficheros sean informativos (los VTT con número no lo son).

## ADR-008. Anonimización en capas con lista de nombres de pila

- **Contexto.** RF2 y la sección 4.1.1: los nombres propios deben anonimizarse, sin saber de antemano qué nombres aparecen.
- **Decisión.** Tres capas: (1) quitar las etiquetas de hablante de Teams, (2) sustituir las entidades de persona que detecta spaCy (`es_core_news_md`) solo si contienen un nombre de pila de una lista de ~300 y no son un término técnico de una lista de ~100, más cualquier palabra en mayúscula que sea nombre de pila junto con hasta dos apellidos, y (3) una lista manual opcional.
- **Alternativas.** Solo spaCy; un LLM local; solo una lista manual.
- **Justificación.** spaCy solo, con transcripciones automáticas, sustituía ~4.800 palabras, la mayoría por error (borraba «Jenkins», «Helm» o «Kubernetes Engine» mal transcrito). Con las listas bajó a ~650, casi todas nombres reales. Un LLM local pide 4–8 GB de RAM, es lento y no es determinista. spaCy es rápido y da siempre el mismo resultado.
- **Consecuencias.** Se escapan nombres poco comunes que no estén en la lista; se medirá con una muestra revisada a mano.

## ADR-009. LLM híbrido con formato de API de OpenAI

- **Contexto.** Pendiente en 4.1.1 y en la tabla 5: modelo externo, local o simulado.
- **Decisión.** Un servicio simulado propio (`mock-llm`) por defecto, y un proveedor externo activable con tres variables (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`). La API habla siempre el formato de OpenAI, también en *streaming*.
- **Alternativas.** Solo proveedor externo; modelo local con Ollama.
- **Justificación.** El simulado da una carga controlada, repetible y sin coste para las pruebas (sección 3.3). El formato de OpenAI lo admiten casi todos los proveedores, así que cambiar es cambiar una URL. Un modelo local necesitaría más RAM que todo el sistema. En privacidad: con el simulado no sale ningún dato; con uno externo, solo la pregunta y hasta 5 fragmentos ya anonimizados.
- **Consecuencias.** El simulado no reproduce latencia ni calidad reales; hay que tenerlo en cuenta en la evaluación.

## ADR-010. Servidor sin estado

- **Contexto.** El chat necesita historial para las preguntas de seguimiento.
- **Decisión.** El navegador envía el historial en cada petición; el servidor no guarda nada. La búsqueda usa también la pregunta anterior.
- **Alternativas.** Guardar las conversaciones en una base de datos.
- **Justificación.** Cualquier réplica puede atender cualquier petición, que es lo que espera Kubernetes, y no hace falta otra base de datos.
- **Consecuencias.** El historial se pierde al recargar la página; aceptable para un único usuario.

## ADR-011. Interfaz web servida por la propia API

- **Decisión.** Una única página HTML sin dependencias externas, servida en `/`.
- **Alternativas.** Open WebUI u otro frontal.
- **Justificación.** No añade un componente más que desplegar, mantener y observar.

## ADR-012. Una sola imagen con los modelos dentro

- **Decisión.** La API y la ingesta comparten imagen (`rag-app`) y cambian solo de comando. Los modelos se descargan al construir la imagen.
- **Justificación.** Comparten código y modelos; un solo pipeline y una sola versión que seguir. Con los modelos dentro, el arranque no depende de la red ni de Hugging Face.
- **Consecuencias.** Imagen de ~2,5 GB. Se construye en el CI en ~2,5 min gracias a la caché.

## ADR-013. Conversión previa de PPT a PDF

- **Contexto.** 12 presentaciones están en el formato binario antiguo (`.ppt`), que python-pptx no lee.
- **Decisión.** Convertirlas una vez a PDF con LibreOffice en un contenedor de un solo uso (`docker compose run --rm convert-ppt`).
- **Alternativas.** Meter LibreOffice en la imagen de la aplicación (~400 MB más).
- **Justificación.** Es una conversión que se hace una vez por fichero; no tiene sentido cargar la imagen de producción con ella.

## ADR-014. Materiales fuera del repositorio

- **Decisión.** Los materiales viven en `data/` (excluida de Git) y, en el clúster, en almacenamiento privado (Fase 5).
- **Justificación.** Son materiales con derechos de terceros y contienen datos personales (tabla 6 de la memoria). El repositorio es público.

## ADR-015. GitHub Actions y GHCR

- **Contexto.** Pendiente en 2.1.6 y en la tabla 5.
- **Decisión.** GitHub Actions para la integración continua y GitHub Container Registry para las imágenes.
- **Alternativas.** GitLab CI/CD; Docker Hub o ECR.
- **Justificación.** El repositorio ya está en GitHub; GHCR no tiene coste para imágenes públicas y se autentica con el token del propio workflow. ECR desaparecería con cada cuenta del Learner Lab.
- **Consecuencias.** Las imágenes son públicas (no contienen datos, solo código y modelos públicos), así que el clúster las descarga sin credenciales.

## ADR-016. Modelo pull: el CI escribe en Git y Argo CD despliega

- **Contexto.** OE4 pide que el pipeline actualice los manifiestos; OE5, aplicar GitOps.
- **Decisión.** El CI prueba, publica las imágenes con el SHA del commit como etiqueta y hace un commit que escribe esa etiqueta en `gitops/rag/values.yaml`. Argo CD detecta el commit y despliega. Solo se publican imágenes si cambia `app/`, `mock-llm/` o el propio workflow; también se puede lanzar a mano.
- **Alternativas.** Que el CI despliegue directamente con `kubectl` o `helm` (modelo *push*); usar la etiqueta `latest`; Argo CD Image Updater.
- **Justificación.** Es el principio de GitOps: Git es la única fuente de verdad y un agente en el clúster tira de ella (Garfield y Rigby, 2021). El CI no necesita credenciales del clúster, que además cambia en cada sesión. El SHA identifica exactamente qué código está desplegado, permite volver atrás con un `git revert` y deja el plazo de los cambios medible (commit → despliegue), que es el escenario 1 de la evaluación.
- **Consecuencias.** Cada despliegue genera un commit automático (`deploy: imágenes <sha>`). El commit hecho con el token del workflow no vuelve a lanzar el CI, así que no hay bucles.

## ADR-017. AWS Academy Learner Lab, con código válido para cuenta propia

- **Contexto.** Proveedor de nube pendiente en la tabla 5; presupuesto limitado (RNF5).
- **Decisión.** Usar el Learner Lab que proporciona la universidad. El mismo código funciona en una cuenta propia cambiando dos variables (`region`, `instance_profile_name`).
- **Justificación.** Créditos sin coste para el estudiante. Mantener la compatibilidad con una cuenta propia reduce el riesgo de depender de un laboratorio que caduca.
- **Consecuencias.** Hay restricciones: solo `us-east-1` y `us-west-2`, sin crear roles de IAM (se usa `LabInstanceProfile`), sin facturación (no hay alerta de presupuesto), máximo t3.large, sesiones de 4 h, credenciales temporales, una política de organización que bloquea leer la configuración de los buckets y, observado después, **una cuenta nueva en cada sesión**. Todas se resolvieron o se declaran como limitación (ver `proceso.md`).

## ADR-018. EC2 t3.large con k3s de un nodo

- **Decisión.** Una única máquina t3.large (2 vCPU, 8 GB) con k3s v1.36.5, versión fijada.
- **Alternativas.** EKS (control plane de pago, no disponible en el lab sin roles); t3.xlarge (denegada en el lab).
- **Justificación.** k3s es Kubernetes completo y ligero, adecuado para un nodo (capítulo 2). 8 GB bastan para k3s, Argo CD, Qdrant, la API con sus modelos y la observabilidad.
- **Consecuencias.** Sin alta disponibilidad; resultados de rendimiento indicativos (sección 3.3).

## ADR-019. Estado de Terraform en S3, creado con script

- **Decisión.** El estado vive en un bucket S3 cifrado, versionado, sin acceso público y con bloqueo nativo (`use_lockfile`). El bucket lo crea `infra/bootstrap.sh` con la CLI de AWS.
- **Alternativas.** Estado local; crear el bucket con Terraform.
- **Justificación.** El estado remoto no depende del equipo de quien lo ejecuta y el versionado permite recuperarlo. No se crea con Terraform por dos motivos: el estado no puede guardarse en un bucket que aún no existe, y en el lab la política de la organización impide al proveedor de Terraform leer la configuración del bucket (falló tras crearlo).
- **Consecuencias.** Un paso previo por cuenta; en el lab, uno por sesión.

## ADR-020. Administración por SSM, sin SSH

- **Decisión.** El grupo de seguridad solo abre los puertos 80 y 443. La máquina se administra con AWS Systems Manager (sesiones y `send-command`).
- **Justificación.** No hay puertos de administración expuestos ni claves privadas que custodiar. El perfil del lab ya incluye los permisos de SSM.

## ADR-021. DNS con sslip.io y TLS con Let's Encrypt

- **Decisión.** El nombre público es `rag.<ip-con-guiones>.sslip.io` (y `argocd.…` para Argo CD), y cert-manager pide los certificados a Let's Encrypt con validación HTTP-01 a través de Traefik. Hay un emisor de pruebas (`letsencrypt-staging`).
- **Alternativas.** Dominio propio en Route 53; certificados autofirmados.
- **Justificación.** Un nombre real sin registrar dominio ni coste, válido para un certificado de confianza (RNF4). cert-manager renueva los certificados solo.
- **Consecuencias.** El nombre depende de la IP, que cambia al recrear la infraestructura (ADR-023).

## ADR-022. Arranque: Argo CD instalado por k3s y *app of apps*

- **Contexto.** RNF1 y RNF2: el entorno completo debe crearse desde el código y el estado del clúster debe venir de Git.
- **Decisión.** El script de arranque de la máquina instala k3s, escribe un recurso `HelmChart` que el controlador Helm de k3s usa para instalar Argo CD, y crea la aplicación raíz. Esa aplicación despliega el chart `gitops/apps`, que define el resto de aplicaciones con un orden (*sync waves*): cert-manager y Sealed Secrets, después los emisores, después la aplicación RAG.
- **Alternativas.** Instalar Argo CD a mano o desde el equipo local con Helm; gestionar todo con Terraform (proveedores de Kubernetes y Helm).
- **Justificación.** No hay ningún paso manual entre `terraform apply` y el sistema funcionando. Terraform se queda en la infraestructura y Git manda en el clúster, sin mezclar dos fuentes de verdad. Usar el controlador que ya trae k3s evita instalar Helm en la máquina.
- **Consecuencias.** Argo CD no se gestiona a sí mismo (lo instala k3s). La primera sincronización depende de que los CRD existan: se usan `SkipDryRunOnMissingResource` y reintentos.

## ADR-023. El nombre público lo inyecta Terraform

- **Contexto.** El nombre `rag.<ip>.sslip.io` depende de la IP elástica, que cambia al recrear la infraestructura; en el Learner Lab, en cada sesión.
- **Decisión.** `gitops/apps` es un chart de Helm cuyo valor `host` recibe la aplicación raíz desde Terraform; el chart lo pasa a la aplicación RAG.
- **Alternativas.** Escribir el nombre en `gitops/rag/values.yaml` y hacer un commit por sesión.
- **Justificación.** El valor depende del entorno, no de la aplicación: lo conoce quien crea el entorno. Así recrear el entorno no exige tocar Git.
- **Consecuencias.** Ese valor no está en Git, sino en el estado de Terraform y en la aplicación raíz.

## ADR-024. Sealed Secrets con clave propia guardada en SSM

- **Contexto.** Los secretos (API key de la aplicación, clave del LLM) no pueden ir en claro en Git (RNF4). Sealed Secrets genera por defecto una clave nueva en cada clúster, lo que invalidaría los secretos del repositorio en cada recreación.
- **Decisión.** Generar una vez un par de claves propio. El certificado público va en el repositorio (`gitops/sealed-secrets-cert.pem`); la clave privada, fuera de Git (`.secrets/`) y en SSM Parameter Store como `SecureString`. El arranque la lee y la carga en el clúster antes de que arranque el controlador.
- **Alternativas.** AWS Secrets Manager con External Secrets; volver a cifrar los secretos en cada recreación.
- **Justificación.** Los secretos cifrados del repositorio siguen siendo válidos en cualquier recreación, sin pasos manuales. Con el certificado en el repositorio, se cifra sin acceso al clúster. Secrets Manager tiene coste por secreto, ata a un proveedor y saca los secretos del flujo GitOps.
- **Consecuencias.** La clave privada es el secreto raíz: su copia local en `.secrets/` es la única fuera de AWS, y en el lab hay que subirla a cada cuenta nueva (`bootstrap.sh` lo hace).

## ADR-025. Versiones fijadas y con al menos dos semanas

- **Decisión.** Todas las versiones están fijadas: k3s v1.36.5, Argo CD (chart 10.11.6, app v3.5.6), cert-manager v1.21.3, Sealed Secrets (chart 2.22.0, app v0.41.2), Qdrant v1.20.0, proveedor AWS de Terraform 6.x con fichero de bloqueo y Helm 3.22.1 en el CI. Se eligen versiones publicadas hace al menos dos semanas.
- **Justificación.** La reproducibilidad (RNF1) exige que recrear el entorno dé lo mismo. Esperar dos semanas evita versiones recién publicadas con fallos aún no detectados.
- **Consecuencias.** Las actualizaciones son deliberadas: se cambia la versión en el código y pasa por el mismo flujo.

## ADR-026. Materiales en un bucket S3 privado por cuenta

- **Contexto.** Para que la ingesta se ejecute en el clúster (Fase 5), los materiales tienen que estar accesibles desde él, pero no pueden ir en Git (ADR-014) ni en la imagen.
- **Decisión.** Un bucket S3 privado (`rag-tfm-materials-<cuenta>`), cifrado, versionado y sin acceso público, creado por `infra/bootstrap.sh`. `infra/upload-materials.sh` lo sincroniza con `data/` (`aws s3 sync --delete`).
- **Alternativas.** Volumen en la propia máquina (se pierde al recrearla); incluir los materiales en una imagen privada; otro almacenamiento externo.
- **Justificación.** Es el «almacenamiento privado» que anticipa la sección 4.1.1. Sincronizar `data/` con el bucket es el gesto que representa «cambian los materiales»: lo siguiente es reindexar. El versionado permite recuperar un fichero borrado por error.
- **Consecuencias.** En el Learner Lab hay que subirlos en cada sesión (89 MB, ~26 s). Los `.ppt` (ya convertidos) y el `.html` (duplicado) no se suben.

## ADR-027. Ingesta en el clúster: CronJob y Job inicial con `--if-missing`

- **Contexto.** OE6 y RF4 piden una actualización periódica y automática. Además, un clúster recién creado no tiene índice, y la API no está disponible hasta que lo tiene (su sonda `/readyz` falla a propósito).
- **Decisión.** Dos recursos con la misma plantilla de pod:
  - un **CronJob** `rag-ingest` que reindexa a diario (04:00 UTC) y se puede lanzar a mano (`kubectl create job --from=cronjob/rag-ingest`);
  - un **Job** `rag-ingest-inicial` marcado como *hook* de sincronización de Argo CD que se ejecuta con `--if-missing`: si el índice ya existe termina en segundos; si no, lo construye.
- **Alternativas.**
  - *Hook* `PostSync`: Argo CD solo lo lanza cuando todo está sano, pero la API no está sana sin índice: bloqueo mutuo.
  - Lanzar la primera ingesta a mano: rompe RNF1 (crear el entorno desde cero sin pasos manuales).
  - Que la API indexe al arrancar: mezcla responsabilidades y haría que cada réplica reindexase.
  - Que la sonda de disponibilidad no dependa del índice: la API recibiría tráfico que no puede atender.
- **Justificación.** Un clúster nuevo se completa solo, y en un clúster que ya tiene índice cada sincronización cuesta unos segundos. El CronJob con `concurrencyPolicy: Forbid` no lanza dos reindexaciones a la vez. Ambos usan el mecanismo de alias, así que la API no se interrumpe (ADR-004).
- **Consecuencias.** La reindexación es la carga más pesada del sistema (CPU). En la t3.large compite con la API; es justo lo que mide el escenario 3 de la evaluación. El horario diario solo se cumple si la máquina está encendida (en el lab, rara vez a las 04:00); en las pruebas se lanzará a mano.

## ADR-028. Credenciales de la ingesta: rol de la máquina vía IMDSv2

- **Contexto.** La ingesta necesita leer el bucket de materiales desde un pod.
- **Decisión.** Usar las credenciales temporales del rol de la máquina (en el lab, `LabRole`; en cuenta propia, un rol con permiso de solo lectura sobre ese bucket), que el SDK obtiene del servicio de metadatos (IMDSv2). Se sube el límite de saltos de IMDSv2 a 2.
- **Alternativas.** Claves de acceso en un `SealedSecret` (en el lab las credenciales caducan cada sesión, y son claves de larga duración en cuenta propia); IRSA (requiere un proveedor OIDC propio del clúster, desproporcionado para un nodo).
- **Justificación.** No hay ninguna credencial que guardar ni rotar. El límite de saltos por defecto (1) solo deja llegar a los procesos del propio host; los pods están un salto más allá, detrás de la red del clúster.
- **Consecuencias.** Cualquier pod del nodo puede usar el rol de la máquina. Es aceptable en un clúster de un solo usuario y un solo propósito, y en cuenta propia el rol solo puede leer ese bucket y usar SSM.

## ADR-029. La descarga de S3 la hace la propia ingesta

- **Decisión.** `python -m rag.ingest --s3-bucket <bucket>` descarga los materiales con boto3 antes de indexar; con `--if-missing`, comprueba primero si hay índice y, si lo hay, no descarga nada.
- **Alternativas.** Un `initContainer` con la imagen de la CLI de AWS (`aws s3 sync`).
- **Justificación.** Con un `initContainer`, la descarga ocurriría siempre antes de poder comprobar si hace falta: cada sincronización de Argo CD bajaría 89 MB para nada. Además, se usa una sola imagen y la lógica queda cubierta por pruebas.
- **Consecuencias.** boto3 se añade a la imagen (~15 MB).
