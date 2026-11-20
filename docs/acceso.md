# Acceso y gestión del sistema desplegado

El sistema desplegado en AWS tiene dos direcciones web, y la máquina se administra sin SSH. Esta guía explica qué es cada una, cómo entrar y qué se puede hacer.

## Las direcciones y por qué tienen esa forma

| Dirección | Qué es |
| --- | --- |
| `https://rag.<ip>.sslip.io` | La aplicación: el asistente de chat sobre los materiales |
| `https://argocd.<ip>.sslip.io` | Argo CD: el panel que despliega y vigila todo lo que corre en el clúster |

`<ip>` es la IP pública de la máquina con guiones, por ejemplo `18-235-140-81`. **sslip.io** es un servicio de DNS público y gratuito: cualquier nombre que contenga una IP se resuelve a esa IP. Así hay un nombre real, con certificado HTTPS de Let's Encrypt, sin comprar ni registrar un dominio (ADR-021).

La IP cambia cada vez que se recrea la infraestructura; en el Learner Lab, en cada sesión. Las direcciones del momento las da Terraform:

```bash
terraform -chdir=infra/cluster output      # app_host y argocd_host
```

## La aplicación: `https://rag.<ip>.sslip.io`

**Para qué sirve.** Es el asistente del TFM: se hace una pregunta sobre el temario, las actividades o lo explicado en clase, y responde citando las fuentes (asignatura, fichero y minuto o página).

**Cómo entrar.**
1. Abrir la dirección en el navegador.
2. La página pide una *API key*: es la que está en `.secrets/api-key.txt` (fichero local, fuera de Git). Se guarda en el navegador y no vuelve a pedirse.
3. Escribir la pregunta. Opcionalmente, filtrar por asignatura con el desplegable.

**Si responde «503 Service Unavailable».** La aplicación está desplegada pero aún no tiene índice (la base de conocimiento vacía). Es el comportamiento diseñado: la API no acepta preguntas hasta que puede contestarlas. En un clúster nuevo, la primera ingesta se lanza sola y tarda varios minutos (Fase 5).

**Otras rutas útiles** (sin API key):

| Ruta | Qué devuelve |
| --- | --- |
| `/healthz` | `{"status":"ok"}` si el proceso está vivo |
| `/readyz` | `{"status":"ready"}` si hay índice; 503 si no |
| `/metrics` | Métricas en formato Prometheus: latencia por etapa, tokens, errores |

## Argo CD: `https://argocd.<ip>.sslip.io`

**Para qué sirve.** Argo CD es el controlador GitOps: compara lo que hay en el clúster con lo que dice el repositorio de Git y lo corrige. Su web permite **ver** el estado de todo sin usar la línea de comandos. Fue uno de los motivos para elegirlo frente a Flux (capítulo 2 de la memoria).

**Cómo entrar.**
- Usuario: `admin`
- Contraseña: se genera al azar cada vez que se crea el clúster. Para verla:

  ```bash
  export AWS_SHARED_CREDENTIALS_FILE="$(cygpath -w "$PWD/.aws/credentials")" AWS_PROFILE=learnerlab AWS_REGION=us-east-1
  bash infra/argocd-password.sh
  ```

**Qué se ve.** Cinco aplicaciones:

| Aplicación | Qué despliega |
| --- | --- |
| `root` | Las otras cuatro (patrón *app of apps*) |
| `cert-manager` | El gestor de certificados HTTPS |
| `sealed-secrets` | El controlador que descifra los secretos de Git |
| `platform` | Los emisores de certificados de Let's Encrypt |
| `rag` | La aplicación: API, Qdrant, mock-llm, ingesta y su entrada web |

Cada una muestra dos estados:
- **Sync** (*Synced* / *OutOfSync*): si el clúster coincide con Git.
- **Health** (*Healthy* / *Progressing* / *Degraded*): si lo desplegado funciona. `rag` aparece *Progressing* mientras no hay índice.

**Qué se puede hacer.**
- Pulsar una aplicación para ver el árbol de recursos (Deployment → Pods, Services, Ingress…).
- Ver los **logs** de un pod (útil para seguir la ingesta) y los **eventos**.
- **History and rollback**: el historial de despliegues, con el commit de cada uno.
- **App diff**: qué cambiaría al sincronizar.
- **Sync**: forzar una sincronización sin esperar los 3 minutos de sondeo.

**Lo que no conviene hacer:** cambiar recursos a mano, ni desde la web ni con `kubectl`. Argo CD tiene `selfHeal` activado y deshace cualquier cambio que no venga de Git. Es justo lo que mide el escenario 2 de la evaluación. Los cambios se hacen en el repositorio.

**Seguridad.** El panel es público en internet, protegido por HTTPS y por una contraseña aleatoria de 16 caracteres que cambia con cada clúster (ADR-030). No contiene los materiales ni los secretos en claro.

## La máquina (sin SSH)

No hay SSH ni puertos de administración abiertos (ADR-020). Los comandos se ejecutan con AWS Systems Manager. Ejemplo para ver todos los pods:

```bash
ID=$(terraform -chdir=infra/cluster output -raw instance_id)
CMD=$(aws ssm send-command --instance-ids $ID --document-name AWS-RunShellScript \
  --parameters 'commands=["k3s kubectl get pods -A"]' --query Command.CommandId --output text)
aws ssm get-command-invocation --command-id $CMD --instance-id $ID --query StandardOutputContent --output text
```

Comandos habituales (dentro de `commands=[...]`):

| Para | Comando |
| --- | --- |
| Estado de las aplicaciones de Argo CD | `k3s kubectl get applications -A` |
| Pods de la aplicación | `k3s kubectl -n rag get pods` |
| Logs de la ingesta | `k3s kubectl -n rag logs job/rag-ingest-inicial` |
| Lanzar una reindexación | `k3s kubectl -n rag create job --from=cronjob/rag-ingest rag-ingest-manual-1` |
| Memoria y CPU | `k3s kubectl top pods -A` |
| Log del arranque de la máquina | `tail -n 50 /var/log/cloud-init-output.log` |

Con el [plugin de Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) instalado, `aws ssm start-session --target $ID` abre una terminal interactiva en la máquina.
