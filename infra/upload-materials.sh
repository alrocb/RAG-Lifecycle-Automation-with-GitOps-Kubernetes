#!/bin/bash
# Sube los materiales de data/ al bucket privado de la cuenta. Es la forma de actualizar la base de
# conocimiento: la siguiente ejecución de la ingesta (programada o lanzada a mano) los reindexa.
# Uso: infra/upload-materials.sh [carpeta]   (por defecto, data/)
set -euo pipefail

SRC="${1:-$(dirname "$0")/../data}"
BUCKET="rag-tfm-materials-$(aws sts get-caller-identity --query Account --output text)"

# --delete: lo que se borra de data/ también desaparece del bucket (y de la siguiente indexación).
# Los .ppt ya están convertidos a PDF y el .html duplica un PDF: no hace falta subirlos.
aws s3 sync "$SRC" "s3://$BUCKET/" --delete --only-show-errors --exclude "*.ppt" --exclude "*.html"
echo "Materiales sincronizados en s3://$BUCKET: $(aws s3 ls "s3://$BUCKET/" --recursive | wc -l) ficheros"
