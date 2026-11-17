variable "region" {
  type    = string
  default = "eu-west-1"
}

variable "instance_type" {
  description = "8 GB de RAM bastan para k3s, Argo CD, Qdrant, observabilidad y la API (y es el máximo del Learner Lab)"
  type        = string
  default     = "t3.large"
}

variable "disk_gb" {
  type    = number
  default = 40
}

variable "k3s_version" {
  description = "Versión fijada para que el clúster sea reproducible"
  type        = string
  default     = "v1.36.5+k3s1"
}

variable "argocd_chart_version" {
  type    = string
  default = "10.11.6"
}

variable "repo_url" {
  description = "Repositorio que Argo CD sincroniza (gitops/apps)"
  type        = string
  default     = "https://github.com/alrocb/RAG-Lifecycle-Automation-with-GitOps-Kubernetes.git"
}

variable "git_revision" {
  type    = string
  default = "main"
}

variable "sealed_secrets_param" {
  description = "Prefijo en SSM Parameter Store de la clave de Sealed Secrets (tls.key y tls.crt), subida con infra/sealed-secrets-key.sh"
  type        = string
  default     = "/rag-tfm/sealed-secrets"
}

variable "monthly_budget_usd" {
  description = "Límite mensual de gasto en la cuenta; avisa por correo al 80 % previsto y al 100 % real"
  type        = number
  default     = 50
}

variable "budget_email" {
  description = "Correo para los avisos de presupuesto (en terraform.tfvars, que no se versiona). Sin él no se crea el presupuesto"
  type        = string
  default     = null
}

variable "instance_profile_name" {
  description = "Perfil de instancia existente con permisos de SSM. Sin él se crea uno (no permitido en AWS Academy)"
  type        = string
  default     = null
}
