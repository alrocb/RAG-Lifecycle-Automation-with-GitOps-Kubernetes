# Mediciones

Todas las cifras medidas hasta ahora, con su fecha, el entorno y el método. Son mediciones puntuales de desarrollo, tomadas una sola vez. Las de la evaluación (Fase 7) se repetirán varias veces y se darán con mediana y dispersión, como pide la sección 3.3.

**Entornos:**
- **Local**: equipo de desarrollo, Windows 11 con Docker Desktop (6 núcleos y 7,7 GB asignados al motor de Docker).
- **AWS**: EC2 t3.large (2 vCPU, 8 GB), us-east-1, AWS Academy Learner Lab.
- **CI**: ejecutores `ubuntu-latest` de GitHub Actions.

## Base de conocimiento

| Medida | Valor | Fecha | Notas |
| --- | --- | --- | --- |
| Ficheros de partida | 129: 45 VTT, 62 PDF, 9 DOCX, 12 PPT, 1 HTML | 06/11 | 3 asignaturas |
| Ficheros indexados | 128 (12 PPT convertidos a PDF; el HTML se omite por duplicado) | 06/11 | — |
| Fragmentos | 7.118–7.122 | 06/11 | Varía levemente según la anonimización |
| PDF con poco texto extraíble | Varias presentaciones de *Herramientas DevOps*, p. ej. 586 caracteres en 7 páginas | 06/11 | Son casi solo imágenes; su contenido está en los PDF completos de cada tema |

## Ingesta e indexación

| Medida | Valor | Entorno | Fecha | Método |
| --- | --- | --- | --- | --- |
| Reindexación completa (129 ficheros) | 405–427 s (~7 min) | Local | 06/11 | Tiempo de `docker compose run --rm ingest` |
| Desglose | ~1,5 min lectura y anonimización; ~5,5 min vectores | Local | 06/11 | Marcas de tiempo del log |
| Conversión de 12 PPT a PDF | ~2 min, incluida la instalación de LibreOffice | Local | 06/11 | `docker compose run --rm convert-ppt` |
| Subida de los materiales a S3 (128 ficheros, 89 MB) | 26 s | Local → AWS | 20/11 | `infra/upload-materials.sh` |
| Primera ingesta en el clúster (Job inicial) | ~21 min: descarga de S3 18 s · lectura y anonimización 4 min · vectores e índice ~16,5 min | AWS | 20/11 | Marcas de tiempo del log y nombre de la colección |
| Uso de recursos de la ingesta | ~1 núcleo (950–1.000 m); memoria hasta 2,95 GiB | AWS | 20/11 | `kubectl top pods` cada 2–3 min |
| Job inicial con índice ya existente (`--if-missing`) | Termina en segundos sin descargar ni reindexar | AWS | 20/11 | Log del Job |

## Anonimización

| Versión | Sustituciones `[PERSONA]` | Calidad (muestra aleatoria de 15–25 casos) | Fecha |
| --- | --- | --- | --- |
| spaCy sin filtrar (solo términos técnicos) | 4.825 (3.933 VTT, 865 PDF, 27 DOCX) | La mayoría erróneas: palabras de inicio de frase, términos mal transcritos | 06/11 |
| spaCy + nombre de pila obligatorio | 404 | Casi todas nombres reales; se escapaban nombres fuera de la lista | 06/11 |
| + nombres en mayúscula y lista ampliada | 657 | Nombres reales; algún apellido suelto | 06/11 |
| + hasta 2 apellidos | 653 (535 VTT, 116 PDF, 2 DOCX) | Nombres completos sustituidos | 06/11 |

## Latencia de las consultas

LLM simulado con 0,5 s de latencia en todas las medidas.

| Configuración | Latencia | Entorno | Fecha | Método |
| --- | --- | --- | --- | --- |
| Sin reordenación, datos sintéticos | ~0,5 s (dominada por el LLM simulado) | Local | 02/11 | `/metrics` |
| Reordenación 20 candidatos × 800 caracteres, datos reales | 8,0–10,1 s por pregunta; la reordenación supuso 63 de 67 s en 8 preguntas (94 %) | Local | 06/11 | `/metrics` (suma por etapa) |
| Reordenación de una pregunta (Packer), por configuración | 20×800: 9,86 s · 10×800: 3,19 s · 10×400: 1,59 s · 5×400: 0,75 s; mismo mejor resultado en todas | Local | 06/11 | Llamada directa al modelo en el contenedor |
| Configuración final (10×400), datos reales | 2,3–3,4 s por pregunta | Local | 06/11 | 8 preguntas de prueba |
| Búsqueda híbrida (etapa) | ~23 ms por pregunta | Local | 06/11 | `/metrics` |
| Configuración final (10×400), por HTTPS en la t3.large | 9,6–11,7 s por pregunta; media por etapa: búsqueda 0,04 s · **reordenación 9,70 s** · LLM simulado 0,46 s · total 10,20 s | AWS | 20/11 | 4 preguntas; diferencia de `/metrics` antes y después |

## Calidad de la recuperación (comprobaciones cualitativas)

| Pregunta | Resultado | Fecha |
| --- | --- | --- |
| «¿Qué es Packer y para qué sirve?» | Primera fuente: clase sobre Packer | 06/11 |
| «¿Qué es Terraform y qué es el fichero de estado?» (Herramientas DevOps) | Primera fuente: `tema5.pdf`, p. 5 | 06/11 |
| «¿Cuál es la rúbrica de la actividad 3?» (SecDevOps) | Antes de la cabecera de contexto: sin el enunciado. Después: `mudevopsact03.docx` | 06/11 |
| «¿Qué es un WAF?» | Sin fuentes; correcto, porque no aparece en los materiales | 06/11 |
| «¿Cuál es la capital de Francia?» | Sin fuentes | 06/11 |

## Disponibilidad durante la reindexación (adelanto del escenario 3)

| Configuración | Resultado | Entorno | Fecha |
| --- | --- | --- | --- |
| 8 clientes concurrentes durante 40 s, 2 reindexaciones a la vez, sin reordenación, datos sintéticos | 560 peticiones, 0 errores | Local | 02/11 |
| Ídem con reordenación (20 candidatos) | 92 peticiones, 0 errores; la reordenación en CPU limita el rendimiento | Local | 02/11 |

## Recursos

| Medida | Valor | Fecha |
| --- | --- | --- |
| Memoria de la API con los modelos cargados | ~1,5 GiB | 02/11 |
| Imagen `rag-app` | 2,13 GB; 2,53 GB con spaCy | 06/11 |
| Memoria usada en la t3.large con k3s recién instalado | ~800 MiB de 7,6 GiB | 06/11 |
| Memoria usada con todo desplegado (Argo CD, cert-manager, Sealed Secrets, API con modelos, Qdrant con índice) | 3,8 de 7,6 GiB | 20/11 |
| Memoria de la API con los modelos cargados, en el clúster | ~1,5 GiB | 20/11 |

## Infraestructura y despliegue

| Medida | Valor | Entorno | Fecha |
| --- | --- | --- | --- |
| `terraform apply` desde cero (9 recursos) | 33 s | AWS | 06/11 |
| Ídem en otra cuenta | 31 s | AWS | 20/11 |
| k3s listo tras el `apply` | ~1 min | AWS | 06/11 |
| Arranque completo (k3s + clave de Sealed Secrets + Argo CD + aplicación raíz) | 93 s desde el inicio de la máquina | AWS | 20/11 |
| Coste aproximado encendida | ~0,10 $/h (instancia 0,09 + disco + IP) | AWS | 06/11 |
| Coste aproximado parada | ~0,25 $/día (disco + IP) | AWS | 06/11 |

## Despliegue GitOps

| Medida | Valor | Entorno | Fecha | Método |
| --- | --- | --- | --- | --- |
| Commit del bot → aplicación raíz sincronizada | 17 s | AWS | 20/11 | `creationTimestamp` y `operationState.finishedAt` de las aplicaciones |
| Commit del bot → aplicación RAG sincronizada | 43 s | AWS | 20/11 | Ídem |
| Commit del bot → certificados TLS emitidos | 1 min 45 s | AWS | 20/11 | `lastTransitionTime` de los `Certificate` |
| `terraform apply` (reemplazo de la máquina) → aplicación respondiendo con índice | ~30 min (incluye ~21 min de primera ingesta y 3 min de un fallo transitorio ya corregido) | AWS | 20/11 | Horas del `apply`, de los logs y de la sonda `/readyz` |
| Memoria usada con Argo CD, cert-manager, Sealed Secrets y la aplicación (sin índice) | 3,7 de 7,6 GiB | AWS | 20/11 | `free -h` |

Primera sincronización tras el arranque: Argo CD aún no había sondeado; en régimen normal el sondeo es cada 3 minutos, así que el plazo de un cambio puede crecer hasta en 3 minutos. Se medirá en el escenario 1 de la evaluación.

## Integración continua

| Ejecución | Duración total | Detalle | Fecha |
| --- | --- | --- | --- |
| Fase 2 (`873b2fb`) | 0,8 min | Pruebas y validación | 02/11 |
| Fase 3 (`cecf09d`) | 0,8 min | Pruebas y validación de Terraform | 06/11 |
| Fase 4 (`2318273`), primera publicación de imágenes | 3,2 min | test 42 s · terraform 16 s · helm 7 s · changes 9 s · images 144 s | 17/11 |
| `3041d66` (cambia el propio workflow) | 1,1 min | Vuelve a publicar imágenes, casi todo desde la caché | 20/11 |
