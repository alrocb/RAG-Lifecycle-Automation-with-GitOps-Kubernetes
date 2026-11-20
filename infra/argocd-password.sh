#!/bin/bash
# Muestra la contraseña del usuario "admin" de Argo CD. Argo CD la genera al azar cada vez que se
# crea el clúster y la guarda en el secreto argocd-initial-admin-secret; se lee con SSM (sin SSH).
# Uso: bash infra/argocd-password.sh
set -euo pipefail

ID=$(terraform -chdir="$(dirname "$0")/cluster" output -raw instance_id)
CMD=$(aws ssm send-command --instance-ids "$ID" --document-name AWS-RunShellScript \
  --parameters 'commands=["k3s kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath={.data.password} | base64 -d"]' \
  --query Command.CommandId --output text)
sleep 3
aws ssm get-command-invocation --command-id "$CMD" --instance-id "$ID" --query StandardOutputContent --output text
