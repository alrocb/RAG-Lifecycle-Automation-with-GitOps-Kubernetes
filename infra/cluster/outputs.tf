output "instance_id" {
  value = aws_instance.node.id
}

output "public_ip" {
  value = aws_eip.node.public_ip
}

output "app_host" {
  value = "rag.${local.ip_dashes}.sslip.io"
}

output "argocd_host" {
  value = "argocd.${local.ip_dashes}.sslip.io"
}
