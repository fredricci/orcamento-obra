# Infraestrutura — Terraform

Provisionamento da infra AWS (EC2 + EBS + EIP + SG + S3 + IAM) via Terraform.

## Pré-requisitos

- [Terraform >= 1.5](https://developer.hashicorp.com/terraform/downloads)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configurado (`aws configure`)
- Key pair EC2 existente na região `sa-east-1`
- Seu IP público (para liberar SSH)

## Variáveis obrigatórias

| Variável        | Como obter                                                                                      |
|-----------------|-------------------------------------------------------------------------------------------------|
| `key_pair_name` | Console AWS → EC2 → Key Pairs; ou crie com `aws ec2 create-key-pair --key-name minha-chave`    |
| `my_ip`         | `curl -s https://checkip.amazonaws.com` → adicione `/32` (ex: `203.0.113.42/32`)              |
| `domain`        | Seu domínio ou subdomínio DuckDNS (ex: `obra.duckdns.org`)                                    |

Variáveis opcionais (têm default):

| Variável        | Default                        |
|-----------------|--------------------------------|
| `region`        | `sa-east-1`                    |
| `project_name`  | `orcamento-obra`               |
| `ami_id`        | Ubuntu 22.04 ARM64 sa-east-1   |
| `instance_type` | `t4g.small`                    |

## Uso

```bash
cd infra/

# 1. Inicializar providers
terraform init

# 2. Revisar o plano (sem criar nada)
terraform plan \
  -var="key_pair_name=minha-chave" \
  -var="my_ip=203.0.113.42/32" \
  -var="domain=obra.duckdns.org"

# 3. Aplicar (cria os recursos)
terraform apply \
  -var="key_pair_name=minha-chave" \
  -var="my_ip=203.0.113.42/32" \
  -var="domain=obra.duckdns.org"
```

Dica: crie um arquivo `terraform.tfvars` (fora do git) pra não repetir as variáveis:

```hcl
# infra/terraform.tfvars  — NÃO commitar
key_pair_name = "minha-chave"
my_ip         = "203.0.113.42/32"
domain        = "obra.duckdns.org"
```

## Outputs

Após o apply:

```
public_ip          = "54.X.X.X"
ec2_instance_id    = "i-0abc123..."
backup_bucket_name = "orcamento-obra-backup-123456789012"
ssh_command        = "ssh ubuntu@54.X.X.X"
```

## Atualizar seu IP (quando mudar)

```bash
terraform apply -var="my_ip=NOVO_IP/32" ...
```

## Destruir tudo

```bash
terraform destroy \
  -var="key_pair_name=minha-chave" \
  -var="my_ip=203.0.113.42/32" \
  -var="domain=obra.duckdns.org"
```

Atenção: isso apaga o EC2 e o bucket S3 (incluindo os backups, se o bucket não tiver sido bloqueado).
