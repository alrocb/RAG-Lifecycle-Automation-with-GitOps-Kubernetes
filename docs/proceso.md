# Bitácora del proceso

Registro cronológico de lo que se ha hecho en cada fase de la metodología (sección 3.3 de la memoria), los problemas encontrados y cómo se resolvieron. Las decisiones están justificadas en [decisiones.md](decisiones.md) y las cifras, en [mediciones.md](mediciones.md).

## Resumen por fases

| Fase | Estado | Fechas | Commit principal |
| --- | --- | --- | --- |
| 1. Fundamentación y diseño | Hecha (entrega 1 de la memoria) | hasta 21/10/2026 | — |
| 2. Aplicación RAG base | Hecha | 02/11 – 06/11/2026 | `873b2fb`, `cecf09d` |
| 3. Infraestructura como código | Hecha | 06/11/2026 | `cecf09d` |
| 4. Integración continua y GitOps | Hecha y desplegada | 13/11 – 20/11/2026 | `2318273` (17/11), `3041d66` (20/11) |
| 5. Actualización de la base de conocimiento | Pendiente (la reindexación sin corte ya existe) | — | — |
| 6. Observabilidad | Pendiente (la API ya expone métricas) | — | — |
| 7. Evaluación | Pendiente | — | — |

---

## Fase 2. Aplicación RAG base

### 02/11/2026: primera versión con datos sintéticos

1. **Decisiones previas** con el usuario: GitHub Actions, LLM híbrido, AWS y Sealed Secrets (ADR-009, 015, 017, 024).
2. **Ingesta**: lectores de VTT (bloques de ~1 min), PDF (por página) y PPTX (por diapositiva); troceado de 800 caracteres con 100 de solapamiento; metadatos de asignatura, tipo, fichero y ubicación.
3. **Indexación con alias** en Qdrant (ADR-004).
4. **mock-llm** compatible con la API de OpenAI (ADR-009).
5. **API** con FastAPI: `/ask`, `/healthz`, `/readyz` y `/metrics` (latencia por etapa, tokens y errores).
6. **Docker Compose** para el desarrollo local y **CI** con pruebas.
7. **Prueba de carga con reindexación**: 8 clientes durante 40 s y dos reindexaciones a la vez; 0 errores.

Se pidió mantener el código simple: sin LangChain (ADR-002), sin abstracciones innecesarias.

### 02/11/2026: usabilidad y calidad de búsqueda

A petición del usuario, aunque la calidad de la recuperación queda fuera del núcleo del TFM, se mejoró la aplicación para que fuera usable:

1. Chat web servido por la API (ADR-011), con respuesta en *streaming* y fuentes numeradas.
2. Historial de conversación con servidor sin estado (ADR-010).
3. Búsqueda híbrida (ADR-005) y reordenación (ADR-006).
4. Variables en `docker-compose.yml` para usar un LLM real desde `.env`.
5. Anonimización con spaCy, ajustada a términos técnicos (ADR-008).

**Problema: Windows bloquea spaCy.** El Control inteligente de aplicaciones de Windows 11 bloquea las DLL de spaCy en el equipo de desarrollo. **Solución:** la prueba que usa spaCy se salta en Windows y se ejecuta en CI y en Docker (Linux), que es donde corre el sistema.

**Problema: spaCy confundía herramientas con personas** (Jenkins, Helm, Grafana). **Solución:** lista de términos técnicos que nunca se anonimizan.

### 06/11/2026: materiales reales

El usuario añadió los materiales de tres asignaturas en `data/` (129 ficheros). Al indexarlos aparecieron problemas que con los datos sintéticos no se veían, como anticipan Barnett et al. (2024):

| Problema | Diagnóstico | Solución |
| --- | --- | --- |
| 12 ficheros `.ppt` en formato binario antiguo | python-pptx solo lee `.pptx` | Conversión previa a PDF con LibreOffice en contenedor (ADR-013) |
| 9 enunciados de actividades en `.docx` | No había lector | Lector por apartados y tablas (python-docx) |
| Teams escribe «NOMBRE APELLIDO:» en cada línea | Los nombres se iban a indexar | Eliminar las etiquetas de hablante línea a línea |
| ~10 s por pregunta | La reordenación con fragmentos reales se lleva el 94 % del tiempo | 10 candidatos recortados a 400 caracteres (ADR-006) |
| «Rúbrica de la actividad 3» no encontraba el enunciado | Una tabla suelta no dice de qué actividad es | Cabecera de contexto (ADR-007) |
| ~4.800 sustituciones `[PERSONA]`, la mayoría erróneas | spaCy marca como persona palabras de transcripciones con errores | Exigir un nombre de pila conocido (ADR-008) |
| Nombres que se escapaban (sin marcar por spaCy, o no en la lista) | Cobertura | Ampliar la lista y sustituir nombres de pila en mayúscula con sus apellidos |
| Un fichero dañado detenía la ingesta | Sin control de errores por fichero | Se registra y se omite |
| «¿Qué es un WAF?» no devolvía fuentes | Se comprobó que «WAF» no aparece en ningún material | Comportamiento correcto del umbral |

El `.html` se omite porque es el mismo documento que un PDF existente.

---

## Fase 3. Infraestructura como código

### 06/11/2026: Terraform y primer despliegue

1. **Terraform** para VPC, subred, grupo de seguridad (solo 80/443), EC2 t3.large con disco cifrado, IP elástica, acceso por SSM y alerta de presupuesto (ADR-018, 020).
2. **Script de arranque** que instala k3s con la versión fijada.
3. **Adaptación al Learner Lab**: se comprobaron sus permisos con llamadas `--dry-run` antes de crear nada (t3.large permitida, t3.xlarge denegada, VPC e IP permitidas, el perfil del lab ya incluye SSM). El código pasó a admitir el perfil existente y a omitir el presupuesto (ADR-017).
4. **Bucket del estado**: el primer intento con Terraform falló porque una política de la organización (SCP) del lab impide leer la configuración de *object lock* de los buckets. Se sustituyó por `infra/bootstrap.sh` con la CLI de AWS (ADR-019).
5. **Despliegue**: `terraform apply` en 33 s; k3s listo ~1 min después; Traefik respondía desde internet en `rag.<ip>.sslip.io`.

**Problema: el clasificador de permisos de la herramienta impidió un `apply -auto-approve` sin revisión.** **Solución, que se adoptó como práctica:** siempre `plan -out`, revisar y aplicar ese plan exacto. Es además la práctica recomendada para Terraform.

**Problema: credenciales.** La CLI de AWS del equipo apunta por defecto a la cuenta personal del usuario. Un `terraform destroy` lanzado sin el perfil del lab dio un 403 al intentar bloquear el estado. **Solución:** exportar siempre `AWS_SHARED_CREDENTIALS_FILE` y `AWS_PROFILE=learnerlab` (ver [operacion.md](operacion.md)).

**Coste:** el usuario preguntó si había costes fijos. Todo se factura por horas: ~0,10 $/h encendida y ~0,25 $/día parada (disco + IP). Se recomendó destruir y recrear en lugar de mantener, aprovechando que todo es código.

---

## Fase 4. Integración continua y GitOps

### 13/11/2026: preparación sin clúster

Se preparó todo sin la máquina encendida, para no gastar créditos:

1. **Versiones** fijadas, con al menos dos semanas de antigüedad (ADR-025). Al buscarlas se detectó que **Sealed Secrets se ha trasladado** de `bitnami-labs` a `github.com/bitnami/sealed-secrets` (su antiguo repositorio de charts ya no existe). La referencia de la memoria debe actualizarse.
2. **Chart de Helm** `charts/rag`: API (con sondas de arranque, vida y disponibilidad), Qdrant como StatefulSet con volumen persistente, mock-llm e Ingress con TLS.
3. **Aplicaciones de Argo CD** en `gitops/`: cert-manager, Sealed Secrets, emisores de Let's Encrypt (producción y pruebas) y la aplicación RAG, con orden de sincronización y reintentos.
4. **Arranque automático** de Argo CD desde el script de la máquina (ADR-022).
5. **Clave de Sealed Secrets** generada localmente y secreto de la aplicación cifrado sin acceso al clúster (ADR-024). Se verificó que la clave privada lo descifra.
6. **CI** ampliado: validación de los charts, publicación de imágenes en GHCR con el SHA y commit de la etiqueta (ADR-016). Se añadió `workflow_dispatch` y el propio workflow al filtro de cambios, porque el primer commit no tocaba `app/` y no habría generado imágenes.
7. Validación local: `helm lint` y `helm template` de los charts (incluido el de Argo CD con los valores del arranque), `terraform validate`.

**Problema: Windows bloquea `kubeseal.exe`** (mismo motivo que spaCy). **Solución:** usar el binario de Linux, verificado con su checksum, dentro de un contenedor.

**Primer push** (`2318273`, 17/11): CI en verde en 3,2 min; las imágenes se publicaron en 144 s y el bot escribió la etiqueta (`7c151c1`). El usuario hizo públicas las dos imágenes en GHCR; se comprobó descargando su manifiesto sin credenciales.

### 20/11/2026: primer despliegue y cuenta nueva por sesión

1. **Hallazgo: el Learner Lab da una cuenta de AWS distinta en cada sesión** (tres cuentas distintas en tres sesiones). No persiste nada: ni el bucket del estado ni la clave en SSM ni la IP.
2. **Adaptación**:
   - `gitops/apps` pasó a ser un chart y el nombre público lo inyecta Terraform (ADR-023), para no hacer un commit por sesión.
   - `bootstrap.sh` también sube la clave de Sealed Secrets.
3. **Preparación de la cuenta**: `bootstrap.sh` creó el bucket y subió la clave a SSM sin problemas (el lab permite `ssm:PutParameter`).
4. **Despliegue**: `terraform plan` (9 recursos) y `apply` en 31 s.
5. **Arranque**: terminado en 93 s. El rol del lab pudo leer la clave de SSM, Argo CD quedó instalado y la aplicación raíz creada.
6. La aplicación raíz falló en el primer intento porque el servidor de repositorios de Argo CD aún no estaba listo (transitorio) y porque GitHub todavía no tenía el chart `gitops/apps`. El usuario hizo push (`3041d66`, CI en 1,1 min).

**Observación menor:** el componente ApplicationSet de Argo CD arrancó aunque se desactivó en los valores; en esta versión del chart la opción debe de tener otro nombre. Pendiente de ajustar (solo consume memoria).

7. **Resultado del primer despliegue GitOps.** Como el push cambiaba el workflow del CI, el filtro de cambios volvió a publicar las imágenes (etiqueta `3041d66`) y el bot hizo su commit (`b806781`). A partir de ahí, sin ninguna intervención:

   | Hora (UTC) | Evento |
   | --- | --- |
   | 09:54:44 | Nodo k3s creado (arranque de la máquina) |
   | 09:55:43 | Aplicación raíz creada por el arranque |
   | 10:21:59 | Commit del bot con la etiqueta nueva |
   | 10:22:08 | Argo CD crea las 4 aplicaciones hijas |
   | 10:22:18 | Sealed Secrets sincronizado; el `SealedSecret` se descifra con la clave traída de SSM |
   | 10:22:42 | Aplicación RAG sincronizada (API, Qdrant, mock-llm, Ingress) |
   | 10:23:17 | Emisores de Let's Encrypt sincronizados (tras reintentar hasta que existieron los CRD de cert-manager) |
   | 10:23:44 | Certificados de `rag.…` y `argocd.…` emitidos por Let's Encrypt (producción, válidos hasta el 18/02/2027) |

   **Del commit en Git al sistema completo desplegado y con HTTPS: 1 min 45 s.** Memoria usada en la máquina: 3,7 de 7,6 GiB.

8. **Estado al cerrar la Fase 4:** Argo CD responde en `https://argocd.<ip>.sslip.io` con certificado válido. La API está desplegada pero no disponible (`/readyz` falla y el Ingress devuelve 503) porque todavía no hay índice: los materiales no están en el clúster. Es exactamente el comportamiento diseñado, y lo resuelve la Fase 5.

**Comprobaciones de la Fase 4 frente a los requisitos:**

| Requisito | Evidencia |
| --- | --- |
| RNF1 Reproducibilidad | Cuenta vacía → sistema desplegado con `bootstrap.sh`, `terraform apply` y un push, sin pasos manuales en el clúster |
| RNF2 Despliegue declarativo | Todo el contenido del clúster sale de `gitops/` y `charts/`; Argo CD con `selfHeal` |
| RNF4 Seguridad | Secretos cifrados en Git y descifrados en el clúster; HTTPS con certificado de confianza; sin puertos de administración |
| OE4 | CI que prueba, publica imágenes y actualiza los manifiestos (3,2 min la primera vez) |
| OE5 | Argo CD + Helm + Sealed Secrets funcionando |

## Fase 5. Actualización de la base de conocimiento

### 20/11/2026: diseño e implementación

La reindexación sin corte ya existía desde la Fase 2 (ADR-004). Faltaba que se ejecutara en el clúster, de forma periódica y automática, con los materiales fuera de Git.

1. **Almacenamiento**: bucket S3 privado por cuenta, creado por `bootstrap.sh`, y `infra/upload-materials.sh` para sincronizarlo con `data/` (ADR-026). Subida: 128 ficheros, 89 MB, 26 s.
2. **Ingesta**: nuevas opciones `--s3-bucket` (descarga con boto3) y `--if-missing` (no hace nada si ya hay índice) (ADR-029). 2 pruebas nuevas, 36 en total.
3. **Chart**: CronJob diario y Job inicial como *hook* de sincronización de Argo CD (ADR-027). Se descartó un *hook* `PostSync` por bloqueo mutuo con la sonda de disponibilidad de la API.
4. **Credenciales**: rol de la máquina vía IMDSv2, con el límite de saltos a 2 para que lleguen los pods; en cuenta propia, permiso de solo lectura sobre el bucket (ADR-028).
5. **Configuración del entorno**: el bucket y la región se pasan desde Terraform a la aplicación raíz, igual que el nombre público (ADR-023).

Como cambia el script de arranque, el siguiente `terraform apply` **reemplaza la máquina**: el clúster se reconstruye desde cero, otra prueba de reproducibilidad.

*Continúa: despliegue y primera ingesta en el clúster.*
