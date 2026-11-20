#!/bin/bash
# Prepara una cuenta de AWS (una vez por cuenta; en AWS Academy, una vez por sesión, porque cada
# sesión da una cuenta nueva): el bucket S3 del estado de Terraform y la clave de Sealed Secrets.
# Es idempotente. Uso: infra/bootstrap.sh [región]   -> imprime el nombre del bucket
#
# Es un script y no Terraform porque el estado no puede guardarse en un bucket que aún no existe,
# y porque en AWS Academy la política de la organización impide al proveedor de Terraform leer
# la configuración del bucket (s3:GetBucketObjectLockConfiguration).
set -euo pipefail

REGION="${1:-us-east-1}"
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
BUCKET="rag-tfm-tfstate-$ACCOUNT"

if ! aws s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" >/dev/null
  else
    aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
      --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  fi
fi

# Versionado para poder recuperar un estado anterior; cifrado y sin acceso público.
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# La clave de Sealed Secrets también vive en la cuenta (SSM Parameter Store).
if [ -f "$(dirname "$0")/../.secrets/sealed-secrets.key" ]; then
  "$(dirname "$0")/sealed-secrets-key.sh" "$REGION" >&2
fi

echo "$BUCKET"
