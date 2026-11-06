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
