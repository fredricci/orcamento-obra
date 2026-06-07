variable "region" {
  description = "AWS region"
  type        = string
  default     = "sa-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "orcamento-obra"
}

variable "key_pair_name" {
  description = "Name of the existing EC2 key pair for SSH access"
  type        = string
}

variable "my_ip" {
  description = "Your public IP in CIDR notation for SSH access (format: x.x.x.x/32)"
  type        = string
}

variable "ami_id" {
  description = "AMI ID for Ubuntu 22.04 ARM64 in sa-east-1"
  type        = string
  # Ubuntu 22.04 LTS ARM64 (Jammy) in sa-east-1 — ami-0cbe887a8e3d99f22
  # Verify latest at: https://cloud-images.ubuntu.com/locator/ec2/
  default = "ami-0cbe887a8e3d99f22"
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t4g.small"
}

variable "domain" {
  description = "Domain or subdomain for the app (e.g. obra.duckdns.org)"
  type        = string
}
