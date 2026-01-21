variable "project_name" {
  type    = string
  default = "praca-inz"
}

variable "aws_region" {
  type    = string
  default = "eu-north-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.50.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.50.10.0/24", "10.50.11.0/24"]
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.50.20.0/24", "10.50.21.0/24"]
}

variable "db_name" {
  type    = string
  default = "tasks_db"
}

variable "db_username" {
  type    = string
  default = "tasks_user"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "image_tag" {
  type    = string
  default = "latest"
}

variable "desired_counts" {
  type = object({
    api        = number
    result     = number
    dispatcher = number
    cpu        = number
    memory     = number
  })
  default = {
    api        = 1
    result     = 1
    dispatcher = 1
    cpu        = 0
    memory     = 1
  }
}

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "db_engine_version" {
  type    = string
  default = "16"
}

variable "compute_mode" {
  type    = string
  default = "EC2"
}

variable "enable_service_autoscaling" {
  type    = bool
  default = true
}

variable "enable_capacity_autoscaling" {
  type    = bool
  default = true
}

variable "service_autoscaling_max" {
  type    = number
  default = 15
}

variable "service_autoscaling_cpu_target" {
  type    = number
  default = 50
}

variable "service_autoscaling_memory_target" {
  type    = number
  default = 15
}

variable "ec2_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "ec2_asg_min" {
  type    = number
  default = 3
}

variable "ec2_asg_desired" {
  type    = number
  default = 3
}

variable "ec2_asg_max" {
  type    = number
  default = 10
}

variable "capacity_provider_target_capacity" {
  type    = number
  default = 95
}


