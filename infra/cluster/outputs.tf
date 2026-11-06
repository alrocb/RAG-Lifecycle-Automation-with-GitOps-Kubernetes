output "instance_id" {
  value = aws_instance.node.id
}

output "public_ip" {
  value = aws_eip.node.public_ip
}

# sslip.io resuelve <ip-con-guiones>.sslip.io a esa IP: DNS sin registrar dominio.
output "app_host" {
  value = "rag.${replace(aws_eip.node.public_ip, ".", "-")}.sslip.io"
}
