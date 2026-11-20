# --- Red: VPC propia con una subred pública ---------------------------------

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "rag-tfm" }
}

resource "aws_subnet" "public" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = data.aws_availability_zones.available.names[0]
  tags              = { Name = "rag-tfm-public" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Solo HTTP/HTTPS hacia Traefik. Sin SSH ni API de Kubernetes abiertos: se accede por SSM.
resource "aws_security_group" "node" {
  name   = "rag-tfm-node"
  vpc_id = aws_vpc.main.id

  ingress {
    description = "HTTP (redireccion y validacion de Lets Encrypt)" # AWS solo admite ASCII aqui
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# --- Acceso por SSM Session Manager ------------------------------------------
# En AWS Academy Learner Lab no se pueden crear roles: se usa el perfil que ya existe
# (instance_profile_name = "LabInstanceProfile"). En una cuenta normal se crea aquí.

resource "aws_iam_role" "node" {
  count = var.instance_profile_name == null ? 1 : 0
  name  = "rag-tfm-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  count      = length(aws_iam_role.node)
  role       = aws_iam_role.node[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "node" {
  count = length(aws_iam_role.node)
  name  = "rag-tfm-node"
  role  = aws_iam_role.node[0].name
}

locals {
  instance_profile = var.instance_profile_name != null ? var.instance_profile_name : aws_iam_instance_profile.node[0].name
  # sslip.io resuelve <ip-con-guiones>.sslip.io a esa IP: DNS sin registrar dominio.
  ip_dashes = replace(aws_eip.node.public_ip, ".", "-")
}

# --- Máquina virtual con k3s --------------------------------------------------

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

resource "aws_instance" "node" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.node.id]
  iam_instance_profile   = local.instance_profile

  user_data = templatefile("${path.module}/install-k3s.sh.tftpl", {
    k3s_version          = var.k3s_version
    region               = var.region
    sealed_secrets_param = var.sealed_secrets_param
    argocd_chart_version = var.argocd_chart_version
    argocd_host          = "argocd.${local.ip_dashes}.sslip.io"
    app_host             = "rag.${local.ip_dashes}.sslip.io"
    repo_url             = var.repo_url
    git_revision         = var.git_revision
  })
  user_data_replace_on_change = true

  metadata_options {
    http_tokens = "required" # IMDSv2
  }

  root_block_device {
    volume_size = var.disk_gb
    volume_type = "gp3"
    encrypted   = true
  }

  # Una AMI nueva de Ubuntu no debe recrear el nodo en cada plan.
  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = "rag-tfm-node" }
}

# IP fija: el nombre sslip.io (y su certificado) no cambia al parar y arrancar la máquina.
resource "aws_eip" "node" {
  domain = "vpc"
  tags   = { Name = "rag-tfm" }
}

resource "aws_eip_association" "node" {
  instance_id   = aws_instance.node.id
  allocation_id = aws_eip.node.id
}

# --- Coste acotado (RNF5) -----------------------------------------------------
# Solo si se define budget_email. En el Learner Lab el tope son los propios créditos.

resource "aws_budgets_budget" "monthly" {
  count        = var.budget_email == null ? 0 : 1
  name         = "rag-tfm-mensual"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}
