terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # El bucket y la región se pasan al hacer init (ver README): cambian según la cuenta.
  # use_lockfile bloquea el estado con un fichero en S3, sin necesidad de DynamoDB.
  backend "s3" {
    key          = "cluster/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "rag-tfm", ManagedBy = "terraform" }
  }
}
