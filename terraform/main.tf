terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project    = "praca-inz"
      Env        = "test"
      RunId      = var.run_id
      Variant    = var.compute_mode
      Autoscaling = tostring(var.enable_service_autoscaling)
    }
  }
}

variable "run_id" {
  type    = string
  default = "run-001"
}

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ssm_parameter" "ecs_ami" {
  name = "/aws/service/ecs/optimized-ami/amazon-linux-2023/recommended"
}
locals {
  ecs_ami_id = jsondecode(data.aws_ssm_parameter.ecs_ami.value)["image_id"]
}



resource "random_id" "suffix" {
  byte_length = 3
}

resource "random_password" "db" {
  length  = 24
  special = false
}

locals {
  name_prefix = "${var.project_name}-${random_id.suffix.hex}"
  short       = substr(replace(local.name_prefix, "-", ""), 0, 12)

  service_names = {
    api        = "task-api-service"
    result     = "result-service"
    dispatcher = "task-dispatcher-service"
    cpu        = "cpu-worker-service"
    memory     = "memory-worker-service"
  }

  private_subnet_ids = [for s in aws_subnet.private : s.id]
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "${local.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${local.name_prefix}-igw" }
}

resource "aws_subnet" "public" {
  for_each = {
    a = { cidr = var.public_subnet_cidrs[0], az = data.aws_availability_zones.available.names[0] }
    b = { cidr = var.public_subnet_cidrs[1], az = data.aws_availability_zones.available.names[1] }
  }

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = { Name = "${local.name_prefix}-public-${each.key}" }
}

resource "aws_subnet" "private" {
  for_each = {
    a = { cidr = var.private_subnet_cidrs[0], az = data.aws_availability_zones.available.names[0] }
    b = { cidr = var.private_subnet_cidrs[1], az = data.aws_availability_zones.available.names[1] }
  }

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = false

  tags = { Name = "${local.name_prefix}-private-${each.key}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${local.name_prefix}-rt-public" }
}

resource "aws_route" "public_default" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  domain = "vpc"
  tags   = { Name = "${local.name_prefix}-nat-eip" }
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public["a"].id
  tags          = { Name = "${local.name_prefix}-nat" }

  depends_on = [aws_internet_gateway.igw]
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${local.name_prefix}-rt-private" }
}

resource "aws_route" "private_default" {
  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nat.id
}

resource "aws_route_table_association" "private" {
  for_each       = aws_subnet.private
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private.id
}

resource "aws_security_group" "alb" {
  name        = substr("${local.name_prefix}-sg-alb", 0, 63)
  description = "ALB security group"
  vpc_id      = aws_vpc.this.id

  ingress {
    from_port   = 80
    to_port     = 80
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

resource "aws_security_group" "ecs" {
  name        = substr("${local.name_prefix}-sg-ecs", 0, 63)
  description = "ECS tasks security group"
  vpc_id      = aws_vpc.this.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "rds" {
  name        = substr("${local.name_prefix}-sg-rds", 0, 63)
  description = "RDS security group"
  vpc_id      = aws_vpc.this.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "ecs_instances" {
  count       = local.is_ec2 ? 1 : 0
  name        = substr("${local.name_prefix}-sg-ecs-instances", 0, 63)
  description = "ECS EC2 instances"
  vpc_id      = aws_vpc.this.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}


resource "aws_db_subnet_group" "this" {
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = local.private_subnet_ids
}

resource "aws_db_instance" "postgres" {
  identifier              = "${local.name_prefix}-postgres"
  engine                  = "postgres"
  engine_version          = var.db_engine_version
  instance_class          = var.db_instance_class
  allocated_storage       = var.db_allocated_storage
  db_name                 = var.db_name
  username                = var.db_username
  password                = random_password.db.result
  port                    = 5432
  publicly_accessible     = false
  skip_final_snapshot     = true
  deletion_protection     = false
  backup_retention_period = 0

  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.rds.id]
}

resource "aws_secretsmanager_secret" "database_url" {
  name = "${local.name_prefix}/DATABASE_URL"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql+psycopg2://${var.db_username}:${random_password.db.result}@${aws_db_instance.postgres.address}:5432/${var.db_name}"
}

resource "aws_ecr_repository" "repos" {
  for_each = local.service_names
  force_delete = true

  name                 = "${local.name_prefix}-${each.value}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "repos" {
  for_each   = aws_ecr_repository.repos
  repository = each.value.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 20 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}
data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_instance" {
  count              = local.is_ec2 ? 1 : 0
  name               = "${local.name_prefix}-ecs-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ecs_instance_ecs" {
  count      = local.is_ec2 ? 1 : 0
  role       = aws_iam_role.ecs_instance[0].name
  policy_arn  = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "ecs_instance_ssm" {
  count      = local.is_ec2 ? 1 : 0
  role       = aws_iam_role.ecs_instance[0].name
  policy_arn  = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ecs_instance" {
  count = local.is_ec2 ? 1 : 0
  name  = "${local.name_prefix}-ecs-instance"
  role  = aws_iam_role.ecs_instance[0].name
}

resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name_prefix}-ecs-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role      = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "read_secret" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.database_url.arn]
  }
}

resource "aws_iam_policy" "read_secret" {
  name   = "${local.name_prefix}-read-secret"
  policy = data.aws_iam_policy_document.read_secret.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution_read_secret" {
  role      = aws_iam_role.ecs_execution.name
  policy_arn = aws_iam_policy.read_secret.arn
}

resource "aws_iam_role" "ecs_task" {
  name               = "${local.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}

resource "aws_ecs_cluster" "this" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "logs" {
  for_each          = local.service_names
  name              = "/ecs/${local.name_prefix}/${each.value}"
  retention_in_days = var.log_retention_days
}

resource "aws_lb" "this" {
  name               = substr("${local.name_prefix}-alb", 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [for s in aws_subnet.public : s.id]
}

resource "aws_lb_target_group" "api" {
  name        = substr("${local.short}-api-tg", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id

  health_check {
    path                = "/health"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
  }
}

resource "aws_lb_target_group" "result" {
  name        = substr("${local.short}-res-tg", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.this.id

  health_check {
    path                = "/health"
    matcher             = "200-399"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
    timeout             = 5
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener_rule" "result_paths" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 10

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.result.arn
  }

  condition {
    path_pattern {
      values = ["/dashboard*", "/stats*"]
    }
  }
}

locals {
  image_api        = "${aws_ecr_repository.repos["api"].repository_url}:${var.image_tag}"
  image_result     = "${aws_ecr_repository.repos["result"].repository_url}:${var.image_tag}"
  image_dispatcher = "${aws_ecr_repository.repos["dispatcher"].repository_url}:${var.image_tag}"
  image_cpu        = "${aws_ecr_repository.repos["cpu"].repository_url}:${var.image_tag}"
  image_memory     = "${aws_ecr_repository.repos["memory"].repository_url}:${var.image_tag}"
  db_secret_arn    = aws_secretsmanager_secret.database_url.arn
  is_fargate = var.compute_mode == "FARGATE"
  is_ec2     = var.compute_mode == "EC2"

}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name_prefix}-${local.service_names.api}"
  requires_compatibilities = local.is_fargate ? ["FARGATE"] : ["EC2"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name         = "api"
    image        = local.image_api
    essential    = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    secrets      = [{ name = "DATABASE_URL", valueFrom = local.db_secret_arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.logs["api"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
    command = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  }])
}



resource "aws_launch_template" "ecs" {
  count         = local.is_ec2 ? 1 : 0
  name_prefix   = "${local.name_prefix}-lt-"
  image_id = local.ecs_ami_id
  instance_type = var.ec2_instance_type

  iam_instance_profile {
    name = aws_iam_instance_profile.ecs_instance[0].name
  }

  vpc_security_group_ids = [aws_security_group.ecs_instances[0].id]

  user_data = base64encode(<<-EOF
  #!/bin/bash
  set -e
  mkdir -p /etc/ecs

  cat <<'EOC' >> /etc/ecs/ecs.config
  ECS_CLUSTER=${aws_ecs_cluster.this.name}
  ECS_LOGLEVEL=debug
  ECS_ENABLE_TASK_IAM_ROLE=true
  ECS_CONTAINER_INSTANCE_TAGS={"Name":"${local.name_prefix}-ecs"}
  EOC
  EOF
  )


  tag_specifications {
    resource_type = "instance"
    tags = {
      Name = "${local.name_prefix}-ecs"
    }
  }
}

resource "aws_autoscaling_group" "ecs" {
  count               = local.is_ec2 ? 1 : 0
  name                = "${local.name_prefix}-asg"
  vpc_zone_identifier = local.private_subnet_ids

  min_size         = var.ec2_asg_min
  desired_capacity = var.ec2_asg_desired
  max_size         = var.ec2_asg_max

  launch_template {
    id      = aws_launch_template.ecs[0].id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${local.name_prefix}-ecs"
    propagate_at_launch = true
  }
  tag {
  key                 = "AmazonECSManaged"
  value               = "true"
  propagate_at_launch = true
  }
}

resource "aws_ecs_capacity_provider" "ec2" {
  count = local.is_ec2 ? 1 : 0
  name  = "${local.name_prefix}-cp"

  auto_scaling_group_provider {
    auto_scaling_group_arn = aws_autoscaling_group.ecs[0].arn

    managed_scaling {
      status                    = var.enable_capacity_autoscaling ? "ENABLED" : "DISABLED"
      target_capacity           = var.capacity_provider_target_capacity
      minimum_scaling_step_size = 1
      maximum_scaling_step_size = 1
      instance_warmup_period    = 180
    }
  }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  count        = local.is_ec2 ? 1 : 0
  cluster_name = aws_ecs_cluster.this.name

  capacity_providers = [aws_ecs_capacity_provider.ec2[0].name]

  default_capacity_provider_strategy {
    capacity_provider = aws_ecs_capacity_provider.ec2[0].name
    weight            = 1
    base              = 1
  }
}


resource "aws_ecs_task_definition" "result" {
  family                   = "${local.name_prefix}-${local.service_names.result}"
  requires_compatibilities = local.is_fargate ? ["FARGATE"] : ["EC2"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name         = "result"
    image        = local.image_result
    essential    = true
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    secrets      = [{ name = "DATABASE_URL", valueFrom = local.db_secret_arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.logs["result"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
    command = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  }])
}

resource "aws_ecs_task_definition" "dispatcher" {
  family                   = "${local.name_prefix}-${local.service_names.dispatcher}"
  requires_compatibilities = local.is_fargate ? ["FARGATE"] : ["EC2"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "dispatcher"
    image     = local.image_dispatcher
    essential = true
    secrets   = [{ name = "DATABASE_URL", valueFrom = local.db_secret_arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.logs["dispatcher"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
    command = ["python", "-m", "app.main"]
  }])
}

resource "aws_ecs_task_definition" "cpu" {
  family                   = "${local.name_prefix}-${local.service_names.cpu}"
  requires_compatibilities = local.is_fargate ? ["FARGATE"] : ["EC2"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "cpu"
    image     = local.image_cpu
    essential = true
    secrets   = [{ name = "DATABASE_URL", valueFrom = local.db_secret_arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.logs["cpu"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
    command = ["python", "-m", "app.main"]
  }])
}

resource "aws_ecs_task_definition" "memory" {
  family                   = "${local.name_prefix}-${local.service_names.memory}"
  requires_compatibilities = local.is_fargate ? ["FARGATE"] : ["EC2"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "memory"
    image     = local.image_memory
    essential = true
    secrets   = [{ name = "DATABASE_URL", valueFrom = local.db_secret_arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.logs["memory"].name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "ecs"
      }
    }
    command = ["python", "-m", "app.main"]
  }])
}

resource "aws_ecs_service" "api" {
  name            = "${local.name_prefix}-${local.service_names.api}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_counts.api
  launch_type = local.is_fargate ? "FARGATE" : null
  force_new_deployment = true

  dynamic "capacity_provider_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      capacity_provider = aws_ecs_capacity_provider.ec2[0].name
      weight            = 1
      base              = 1
    }
  }
  dynamic "ordered_placement_strategy" {
  for_each = local.is_ec2 ? [1] : []
  content {
    type  = "binpack"
    field = "cpu"
  }
  }

  dynamic "ordered_placement_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      type  = "binpack"
      field = "memory"
    }
  }



  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [
  aws_lb_listener.http,
  aws_ecs_cluster_capacity_providers.this,
  ]

}

resource "aws_ecs_service" "result" {
  name            = "${local.name_prefix}-${local.service_names.result}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.result.arn
  desired_count   = var.desired_counts.result
  launch_type = local.is_fargate ? "FARGATE" : null
  force_new_deployment = true

  dynamic "capacity_provider_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      capacity_provider = aws_ecs_capacity_provider.ec2[0].name
      weight            = 1
      base              = 1
    }
  }
  dynamic "ordered_placement_strategy" {
  for_each = local.is_ec2 ? [1] : []
  content {
    type  = "binpack"
    field = "cpu"
  }
  }

  dynamic "ordered_placement_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      type  = "binpack"
      field = "memory"
    }
  }

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.result.arn
    container_name   = "result"
    container_port   = 8000
  }

  depends_on = [
  aws_lb_listener.http,
  aws_ecs_cluster_capacity_providers.this,
]

}

resource "aws_ecs_service" "dispatcher" {
  name            = "${local.name_prefix}-${local.service_names.dispatcher}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.dispatcher.arn
  desired_count   = var.desired_counts.dispatcher
  launch_type = local.is_fargate ? "FARGATE" : null
  force_new_deployment = true

  dynamic "capacity_provider_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      capacity_provider = aws_ecs_capacity_provider.ec2[0].name
      weight            = 1
      base              = 1
    }
  }
  dynamic "ordered_placement_strategy" {
  for_each = local.is_ec2 ? [1] : []
  content {
    type  = "binpack"
    field = "cpu"
  }
  }

  dynamic "ordered_placement_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      type  = "binpack"
      field = "memory"
    }
  }

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_ecs_service" "cpu" {
  name            = "${local.name_prefix}-${local.service_names.cpu}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.cpu.arn
  desired_count   = var.desired_counts.cpu
  launch_type = local.is_fargate ? "FARGATE" : null
  force_new_deployment = true

  dynamic "capacity_provider_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      capacity_provider = aws_ecs_capacity_provider.ec2[0].name
      weight            = 1
      base              = 1
    }
  }
  dynamic "ordered_placement_strategy" {
  for_each = local.is_ec2 ? [1] : []
  content {
    type  = "binpack"
    field = "cpu"
  }
  }

  dynamic "ordered_placement_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      type  = "binpack"
      field = "memory"
    }
  }

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }
}

resource "aws_ecs_service" "memory" {
  name            = "${local.name_prefix}-${local.service_names.memory}"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.memory.arn
  desired_count   = var.desired_counts.memory
  launch_type = local.is_fargate ? "FARGATE" : null
  force_new_deployment = true

  dynamic "capacity_provider_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      capacity_provider = aws_ecs_capacity_provider.ec2[0].name
      weight            = 1
      base              = 1
    }
  }

  dynamic "ordered_placement_strategy" {
  for_each = local.is_ec2 ? [1] : []
  content {
    type  = "binpack"
    field = "cpu"
  }
  }

  dynamic "ordered_placement_strategy" {
    for_each = local.is_ec2 ? [1] : []
    content {
      type  = "binpack"
      field = "memory"
    }
  }

  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  depends_on = [
  aws_ecs_cluster_capacity_providers.this,
]

}

locals {
  scalable_services = {
    dispatcher = aws_ecs_service.dispatcher.name
    cpu        = aws_ecs_service.cpu.name
    memory     = aws_ecs_service.memory.name
  }
}

resource "aws_appautoscaling_target" "ecs" {
  for_each = var.enable_service_autoscaling ? local.scalable_services : {}

  max_capacity       = var.service_autoscaling_max
  min_capacity       = 1
  resource_id        = "service/${aws_ecs_cluster.this.name}/${each.value}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  for_each = var.enable_service_autoscaling ? local.scalable_services : {}

  name               = "${local.name_prefix}-${each.key}-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.ecs[each.key].scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs[each.key].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.service_autoscaling_cpu_target
    scale_in_cooldown  = 5
    scale_out_cooldown = 5
  }
}

resource "aws_appautoscaling_policy" "memory" {
  for_each = var.enable_service_autoscaling ? local.scalable_services : {}

  name               = "${local.name_prefix}-${each.key}-memory"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs[each.key].resource_id
  scalable_dimension = aws_appautoscaling_target.ecs[each.key].scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs[each.key].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }

    target_value       = var.service_autoscaling_memory_target
    scale_in_cooldown  = 5
    scale_out_cooldown = 5
  }
}

