output "name_prefix" {
  value = local.name_prefix
}

output "alb_dns_name" {
  value = aws_lb.this.dns_name
}

output "ecr_repo_urls" {
  value = { for k, r in aws_ecr_repository.repos : k => r.repository_url }
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.address
}

output "secret_database_url_arn" {
  value = aws_secretsmanager_secret.database_url.arn
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_names" {
  value = {
    api        = aws_ecs_service.api.name
    result     = aws_ecs_service.result.name
    dispatcher = aws_ecs_service.dispatcher.name
    cpu        = aws_ecs_service.cpu.name
    memory     = aws_ecs_service.memory.name
  }
}
