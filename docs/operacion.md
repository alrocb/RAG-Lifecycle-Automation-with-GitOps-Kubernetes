# Operación del entorno

Procedimiento para levantar, usar y destruir el entorno. Está pensado para AWS Academy Learner Lab, donde **cada sesión da una cuenta de AWS nueva y vacía** (ver `proceso.md`, 20/11). En una cuenta propia, los pasos 2 y 3 se hacen una sola vez.

Los comandos se ejecutan en Git Bash desde la raíz del repositorio. Los scripts se lanzan siempre con `bash infra/<script>.sh`, así funcionan igual en Windows, Linux y macOS sin depender de permisos de ejecución.

## Requisitos del equipo

- Terraform ≥ 1.10, AWS CLI v2, Docker Desktop.
- La clave privada de Sealed Secrets en `.secrets/sealed-secrets.key` (no está en Git; si se pierde, ver «Rotar la clave»).

## Al empezar cada sesión del Learner Lab

1. **Credenciales.** En el lab: *Start Lab* → *AWS Details* → copiar las credenciales al perfil `[learnerlab]` de `.aws/credentials` (fichero excluido de Git). Después:

   ```bash
   export AWS_SHARED_CREDENTIALS_FILE="$(cygpath -w "$PWD/.aws/credentials")" AWS_PROFILE=learnerlab
   aws sts get-caller-identity --query Account --output text   # anotar la cuenta
   ```

   Sin estas variables, la CLI usa la cuenta personal y Terraform falla con un 403 al bloquear el estado.

2. **Preparar la cuenta** (bucket del estado y clave de Sealed Secrets en SSM):

   ```bash
   BUCKET=$(bash infra/bootstrap.sh us-east-1)
   ```

   Crea también el bucket privado de materiales. Para llenarlo (y cada vez que cambien los materiales):

   ```bash
   bash infra/upload-materials.sh        # sincroniza data/ con s3://rag-tfm-materials-<cuenta>
   ```

3. **Apuntar Terraform al bucket de esta cuenta:**

   ```bash
   terraform -chdir=infra/cluster init -reconfigure -backend-config="bucket=$BUCKET" -backend-config="region=us-east-1"
   ```

4. **Crear la infraestructura** (siempre revisando el plan antes de aplicarlo):

   ```bash
   terraform -chdir=infra/cluster plan -out=cluster.tfplan
   terraform -chdir=infra/cluster apply cluster.tfplan
   terraform -chdir=infra/cluster output        # app_host, argocd_host, instance_id
   ```

5. **Esperar** ~2 minutos al arranque y unos minutos más a que Argo CD despliegue todo. No hay más pasos manuales.

## Acceso

Las direcciones web, cómo entrar (API key de la aplicación, contraseña de Argo CD) y cómo ejecutar comandos en la máquina están en [acceso.md](acceso.md).

## Desplegar un cambio

Solo hay que hacer push a `main`. El CI publica las imágenes si cambia `app/` o `mock-llm/`, escribe la etiqueta en `gitops/rag/values.yaml` y Argo CD lo aplica en un máximo de 3 minutos. Para publicar imágenes sin cambios de código: GitHub → *Actions* → *ci* → *Run workflow*.

## Actualizar la base de conocimiento

1. Cambiar los ficheros en `data/` y ejecutar `bash infra/upload-materials.sh`.
2. Esperar a la reindexación diaria (04:00 UTC) o lanzarla ya:

   ```bash
   k3s kubectl -n rag create job --from=cronjob/rag-ingest rag-ingest-manual-$(date +%s)
   ```

   (con `aws ssm send-command`, como en «Acceso»). La API sigue respondiendo con el índice anterior hasta que termina.

En un clúster recién creado no hay que hacer nada: el Job `rag-ingest-inicial` construye el primer índice solo.

## Cambiar un secreto

```bash
kubectl create secret generic rag-secrets -n rag \
  --from-literal=API_KEY=... --from-literal=LLM_API_KEY=... --dry-run=client -o yaml \
  | kubeseal --cert gitops/sealed-secrets-cert.pem --format yaml > gitops/rag/secrets/rag-secrets.yaml
```

En Windows con *Control inteligente de aplicaciones*, `kubeseal.exe` está bloqueado: usar el binario de Linux en un contenedor (`docker run --rm -i -v <carpeta>:/k debian:trixie-slim /k/kubeseal ...`).

## Al terminar

- **Fin de la jornada, misma sesión:** *End Lab*. La máquina se para; al volver a la misma sesión, k3s y los pods arrancan solos.
- **Siempre que no se vaya a volver a esa cuenta** (en el lab, al cambiar de sesión): `terraform -chdir=infra/cluster destroy` (con las variables de credenciales exportadas). Antes, exportar los resultados de las pruebas que se quieran conservar.
- **Nunca** pulsar *Reset* en el lab sin haber destruido antes: borra la cuenta, incluido el estado.

## Rotar la clave de Sealed Secrets

Si se pierde `.secrets/sealed-secrets.key`: generar un par nuevo (comando en la cabecera de `infra/sealed-secrets-key.sh`), sustituir `gitops/sealed-secrets-cert.pem`, volver a cifrar los secretos de `gitops/rag/secrets/`, subir la clave con `bootstrap.sh` y recrear el clúster.

## Problemas conocidos del entorno de desarrollo

| Síntoma | Causa | Solución |
| --- | --- | --- |
| `ImportError: DLL load failed` con spaCy | Control inteligente de aplicaciones de Windows | Las pruebas de spaCy se ejecutan en CI o en Docker |
| `Permission denied` al ejecutar `kubeseal.exe` | Ídem | Binario de Linux en contenedor |
| `failed to connect to the docker API` | Docker Desktop se ha cerrado | Volver a abrir Docker Desktop |
| Rutas raras en comandos de Docker o AWS desde Git Bash | Conversión automática de rutas de MSYS | `MSYS_NO_PATHCONV=1` y `cygpath -w` |
| `charmap codec can't encode` en la salida de AWS CLI | Consola de Windows sin UTF-8 | `PYTHONUTF8=1 PYTHONIOENCODING=utf-8` |
| 403 al bloquear el estado de Terraform | Credenciales de la cuenta personal | Exportar el perfil del lab (paso 1) |
