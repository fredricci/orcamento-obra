output "public_ip" {
  description = "Elastic IP address of the EC2 instance"
  value       = aws_eip.app.public_ip
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.app.id
}

output "backup_bucket_name" {
  description = "S3 bucket name for database backups"
  value       = aws_s3_bucket.backup.bucket
}

output "ssh_command" {
  description = "Ready-to-use SSH command"
  value       = "ssh ubuntu@${aws_eip.app.public_ip}"
}
