#!/bin/bash
# Prepara una cuenta de AWS (una vez por cuenta; en AWS Academy, una vez por sesión, porque cada
# sesión da una cuenta nueva): los buckets S3 del estado de Terraform y de los materiales, y la
# clave de Sealed Secrets. Es idempotente. Uso: bash infra/bootstrap.sh [región]
# Imprime el nombre del bucket del estado (para terraform init).
#
# Es un script y no Terraform porque el estado no puede guardarse en un bucket que aún no existe,
# y porque en AWS Academy la política de la organización impide al proveedor de Terraform leer
# la configuración de los buckets (s3:GetBucketObjectLockConfiguration).
set -euo pipefail

REGION="${1:-us-east-1}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

# Bucket privado: cifrado, versionado (recuperar una versión anterior) y sin acceso público.
private_bucket() {
  local bucket="$1"
  if ! aws s3api head-bucket --bucket "$bucket" >/dev/null 2>&1; then
    if [ "$REGION" = "us-east-1" ]; then
      aws s3api create-bucket --bucket "$bucket" --region "$REGION" >/dev/null
    else
      aws s3api create-bucket --bucket "$bucket" --region "$REGION" \
        --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
    fi
  fi
  aws s3api put-bucket-versioning --bucket "$bucket" --versioning-configuration Status=Enabled
  aws s3api put-bucket-encryption --bucket "$bucket" --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
  aws s3api put-public-access-block --bucket "$bucket" --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
}

private_bucket "rag-tfm-tfstate-$ACCOUNT"
# Los materiales de las asignaturas: nunca en Git (derechos de terceros y datos personales).
private_bucket "rag-tfm-materials-$ACCOUNT"

# La clave de Sealed Secrets también vive en la cuenta (SSM Parameter Store).
if [ -f "$(dirname "$0")/../.secrets/sealed-secrets.key" ]; then
  bash "$(dirname "$0")/sealed-secrets-key.sh" "$REGION" >&2
fi

echo "rag-tfm-tfstate-$ACCOUNT"
