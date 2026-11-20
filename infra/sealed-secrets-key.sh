#!/bin/bash
# Sube (una vez por cuenta) la clave de Sealed Secrets a SSM Parameter Store, de donde la lee el
# arranque de la máquina. Con la misma clave en cada recreación del clúster, los SealedSecret
# del repositorio siguen siendo válidos sin volver a cifrarlos.
# Uso: bash infra/sealed-secrets-key.sh [región]
#
# La clave se generó con:
#   openssl req -x509 -nodes -newkey rsa:4096 -days 3650 -subj "/CN=sealed-secret/O=sealed-secret" \
#     -keyout .secrets/sealed-secrets.key -out gitops/sealed-secrets-cert.pem
# La privada (.secrets/) no se versiona; el certificado público sí, para cifrar sin acceso al clúster:
#   kubeseal --cert gitops/sealed-secrets-cert.pem --format yaml < secreto.yaml
set -euo pipefail

REGION="${1:-us-east-1}"
PREFIX="/rag-tfm/sealed-secrets"
cd "$(dirname "$0")/.."

aws ssm put-parameter --region "$REGION" --overwrite --type SecureString \
  --name "$PREFIX/tls.key" --value "file://.secrets/sealed-secrets.key" >/dev/null
aws ssm put-parameter --region "$REGION" --overwrite --type String \
  --name "$PREFIX/tls.crt" --value "file://gitops/sealed-secrets-cert.pem" >/dev/null
echo "Clave subida a $PREFIX en $REGION"
