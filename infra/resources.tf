# Adoption baseline generated from live AWS configuration. See README before applying.

resource "aws_batch_job_queue" "extractor" {
  name     = "cg-metadata-queue"
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.extractor.arn
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "thumbnails" {
  bucket = "cg-production-data-thumbnails"
  region = "us-east-1"
  rule {
    blocked_encryption_types = ["SSE-C"]
    bucket_key_enabled       = true
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudwatch_log_group" "application" {
  log_group_class   = "STANDARD"
  name              = "/aws/batch/job"
  region            = "us-east-1"
  retention_in_days = 30
  skip_destroy      = false
  tags              = {}
}

resource "aws_secretsmanager_secret" "database" {
  lifecycle {
    prevent_destroy = true
    # These deletion/replication controls have no remote value to import.
    ignore_changes = [force_overwrite_replica_secret, recovery_window_in_days]
  }
  description = "DATABASE_URL connection string for cg-metadata-db, referenced by the cg-metadata-job Batch job definition instead of a hardcoded env var"
  name        = "cg-metadata-db/database-url"
  region      = "us-east-1"
  tags        = {}
}

resource "aws_iam_role_policy_attachment" "extractor_AmazonECSTaskExecutionRolePolicy" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  role       = "CGMetadataExtractorRole"
}

resource "aws_internet_gateway" "production" {
  region = "us-east-1"
  tags   = {}
  vpc_id = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_batch_job_definition" "extractor" {
  container_properties = jsonencode({
    command = []
    environment = [{
      name  = "ASSET_BUCKET_NAME"
      value = "cg-production-data"
      }, {
      name  = "AWS_REGION"
      value = "us-east-1"
      }, {
      name  = "DETECT_SEQUENCES"
      value = "true"
      }, {
      name  = "LOG_LEVEL"
      value = "INFO"
      }, {
      name  = "MIN_PADDING"
      value = "2"
      }, {
      name  = "MIN_SEQUENCE_LENGTH"
      value = "5"
      }, {
      name  = "OVERRIDE_EXISTING"
      value = "false"
      }, {
      name  = "S3_PREFIX"
      value = "shows/"
      }, {
      name  = "SCANNER_WORKERS"
      value = "4"
      }, {
      name  = "STORAGE_TYPE"
      value = "s3"
      }, {
      name  = "THUMBNAIL_BUCKET_NAME"
      value = "cg-production-data-thumbnails"
    }]
    executionRoleArn = "arn:aws:iam::001879457662:role/CGMetadataExtractorRole"
    fargatePlatformConfiguration = {
      platformVersion = "LATEST"
    }
    image       = coalesce(var.image_uri, "001879457662.dkr.ecr.us-east-1.amazonaws.com/cg-metadata-extractor:latest")
    jobRoleArn  = "arn:aws:iam::001879457662:role/CGMetadataExtractorRole"
    mountPoints = []
    networkConfiguration = {
      assignPublicIp = "ENABLED"
    }
    resourceRequirements = [{
      type  = "VCPU"
      value = "8.0"
      }, {
      type  = "MEMORY"
      value = "53248"
    }]
    runtimePlatform = {
      cpuArchitecture       = "X86_64"
      operatingSystemFamily = "LINUX"
    }
    secrets = [{
      name      = "DATABASE_URL"
      valueFrom = "arn:aws:secretsmanager:us-east-1:001879457662:secret:cg-metadata-db/database-url-RZ9Ox9:url::"
    }]
    ulimits = []
    volumes = []
  })
  deregister_on_new_revision = true
  name                       = "cg-metadata-job"
  parameters                 = {}
  platform_capabilities      = ["FARGATE"]
  propagate_tags             = false
  region                     = "us-east-1"
  scheduling_priority        = 0
  tags                       = {}
  type                       = "container"
}

resource "aws_subnet" "us_east_1f" {
  lifecycle {
    prevent_destroy = true
  }
  assign_ipv6_address_on_creation                = false
  availability_zone                              = "us-east-1f"
  cidr_block                                     = "172.30.5.0/24"
  enable_dns64                                   = false
  enable_resource_name_dns_a_record_on_launch    = false
  enable_resource_name_dns_aaaa_record_on_launch = false
  ipv6_native                                    = false
  map_public_ip_on_launch                        = true
  private_dns_hostname_type_on_launch            = "ip-name"
  region                                         = "us-east-1"
  tags                                           = {}
  vpc_id                                         = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_subnet" "us_east_1e" {
  lifecycle {
    prevent_destroy = true
  }
  assign_ipv6_address_on_creation                = false
  availability_zone                              = "us-east-1e"
  cidr_block                                     = "172.30.4.0/24"
  enable_dns64                                   = false
  enable_resource_name_dns_a_record_on_launch    = false
  enable_resource_name_dns_aaaa_record_on_launch = false
  ipv6_native                                    = false
  map_public_ip_on_launch                        = true
  private_dns_hostname_type_on_launch            = "ip-name"
  region                                         = "us-east-1"
  tags                                           = {}
  vpc_id                                         = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_security_group" "batch" {
  lifecycle {
    prevent_destroy = true
  }
  description = "default VPC security group"
  egress = [{
    cidr_blocks      = ["0.0.0.0/0"]
    description      = ""
    from_port        = 0
    ipv6_cidr_blocks = []
    prefix_list_ids  = []
    protocol         = "-1"
    security_groups  = []
    self             = false
    to_port          = 0
  }]
  ingress = []
  name    = "default"
  region  = "us-east-1"
  tags    = {}
  vpc_id  = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_s3_bucket_public_access_block" "thumbnails" {
  block_public_acls       = true
  block_public_policy     = true
  bucket                  = "cg-production-data-thumbnails"
  ignore_public_acls      = true
  region                  = "us-east-1"
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "thumbnails" {
  bucket = "cg-production-data-thumbnails"
  policy = jsonencode({
    Statement = [{
      Action = "s3:GetObject"
      Effect = "Allow"
      Principal = {
        AWS = "arn:aws:iam::001879457662:role/cg-chatbot-lambda-role"
      }
      Resource = "arn:aws:s3:::cg-production-data-thumbnails/*"
      Sid      = "AllowLambdaReadAccess"
    }]
    Version = "2012-10-17"
  })
  region = "us-east-1"
}

resource "aws_subnet" "us_east_1b" {
  lifecycle {
    prevent_destroy = true
  }
  assign_ipv6_address_on_creation                = false
  availability_zone                              = "us-east-1b"
  cidr_block                                     = "172.30.1.0/24"
  enable_dns64                                   = false
  enable_resource_name_dns_a_record_on_launch    = false
  enable_resource_name_dns_aaaa_record_on_launch = false
  ipv6_native                                    = false
  map_public_ip_on_launch                        = true
  private_dns_hostname_type_on_launch            = "ip-name"
  region                                         = "us-east-1"
  tags                                           = {}
  vpc_id                                         = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_subnet" "us_east_1a" {
  lifecycle {
    prevent_destroy = true
  }
  assign_ipv6_address_on_creation                = false
  availability_zone                              = "us-east-1a"
  cidr_block                                     = "172.30.0.0/24"
  enable_dns64                                   = false
  enable_resource_name_dns_a_record_on_launch    = false
  enable_resource_name_dns_aaaa_record_on_launch = false
  ipv6_native                                    = false
  map_public_ip_on_launch                        = true
  private_dns_hostname_type_on_launch            = "ip-name"
  region                                         = "us-east-1"
  tags                                           = {}
  vpc_id                                         = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_subnet" "us_east_1c" {
  lifecycle {
    prevent_destroy = true
  }
  assign_ipv6_address_on_creation                = false
  availability_zone                              = "us-east-1c"
  cidr_block                                     = "172.30.2.0/24"
  enable_dns64                                   = false
  enable_resource_name_dns_a_record_on_launch    = false
  enable_resource_name_dns_aaaa_record_on_launch = false
  ipv6_native                                    = false
  map_public_ip_on_launch                        = true
  private_dns_hostname_type_on_launch            = "ip-name"
  region                                         = "us-east-1"
  tags                                           = {}
  vpc_id                                         = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_iam_role" "extractor" {
  assume_role_policy = jsonencode({
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Sid = ""
    }]
    Version = "2012-10-17"
  })
  description           = "Allows ECS tasks to call AWS services on your behalf."
  force_detach_policies = false
  max_session_duration  = 3600
  name                  = "CGMetadataExtractorRole"
  path                  = "/"
  tags                  = {}
}

resource "aws_batch_compute_environment" "extractor" {
  name         = "cg-metadata-compute"
  region       = "us-east-1"
  service_role = "arn:aws:iam::001879457662:role/aws-service-role/batch.amazonaws.com/AWSServiceRoleForBatch"
  state        = "ENABLED"
  tags         = {}
  type         = "MANAGED"
  compute_resources {
    bid_percentage     = 0
    desired_vcpus      = 0
    instance_type      = []
    max_vcpus          = 32
    min_vcpus          = 0
    security_group_ids = ["sg-0b84f22c177e4ec4a"]
    subnets            = ["subnet-048d6ffc3b5232b64", "subnet-066e1c28b3e38624e", "subnet-068dbe005b3b31383", "subnet-079e45b681c5b8eef", "subnet-0c1279d57d6837bdf", "subnet-0edcbe2b0d8b9d291"]
    tags               = {}
    type               = "FARGATE"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = "cg-production-data"
  region = "us-east-1"
  rule {
    blocked_encryption_types = ["SSE-C"]
    bucket_key_enabled       = true
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_ecr_repository" "application" {
  lifecycle {
    prevent_destroy = true
  }
  image_tag_mutability = "MUTABLE"
  name                 = "cg-metadata-extractor"
  region               = "us-east-1"
  tags                 = {}
  encryption_configuration {
    encryption_type = "AES256"
  }
  image_scanning_configuration {
    scan_on_push = false
  }
}

resource "aws_db_instance" "metadata" {
  lifecycle {
    prevent_destroy = true
  }
  allocated_storage                     = 20
  auto_minor_version_upgrade            = true
  availability_zone                     = "us-east-1a"
  backup_retention_period               = 1
  backup_target                         = "region"
  backup_window                         = "08:28-08:58"
  ca_cert_identifier                    = "rds-ca-rsa2048-g1"
  copy_tags_to_snapshot                 = true
  customer_owned_ip_enabled             = false
  database_insights_mode                = "standard"
  db_subnet_group_name                  = "default-vpc-04bb7be45c9d6b7f7"
  dedicated_log_volume                  = false
  delete_automated_backups              = true
  deletion_protection                   = false
  engine                                = "postgres"
  engine_lifecycle_support              = "open-source-rds-extended-support-disabled"
  engine_version                        = "17.9"
  iam_database_authentication_enabled   = false
  identifier                            = "cg-metadata-db"
  instance_class                        = "db.t4g.micro"
  iops                                  = 3000
  kms_key_id                            = "arn:aws:kms:us-east-1:001879457662:key/6d44d5a1-f862-4462-8c9e-b8e8c7a4ba69"
  license_model                         = "postgresql-license"
  maintenance_window                    = "wed:06:39-wed:07:09"
  max_allocated_storage                 = 1000
  monitoring_interval                   = 0
  multi_az                              = false
  network_type                          = "IPV4"
  option_group_name                     = "default:postgres-17"
  parameter_group_name                  = "default.postgres17"
  password                              = null # sensitive
  password_wo                           = null # sensitive
  performance_insights_enabled          = false
  performance_insights_kms_key_id       = "arn:aws:kms:us-east-1:001879457662:key/6d44d5a1-f862-4462-8c9e-b8e8c7a4ba69"
  performance_insights_retention_period = 0
  port                                  = 5432
  publicly_accessible                   = false
  region                                = "us-east-1"
  skip_final_snapshot                   = true
  storage_encrypted                     = true
  storage_throughput                    = 125
  storage_type                          = "gp3"
  tags                                  = {}
  username                              = "postgres"
  vpc_security_group_ids                = ["sg-0b0227fe8f2b2e60f"]
}

resource "aws_security_group" "assistant" {
  lifecycle {
    prevent_destroy = true
  }
  description = "sg for the chatbot lamdba function"
  egress = [{
    cidr_blocks      = ["0.0.0.0/0"]
    description      = ""
    from_port        = 0
    ipv6_cidr_blocks = []
    prefix_list_ids  = []
    protocol         = "-1"
    security_groups  = []
    self             = false
    to_port          = 0
  }]
  ingress = [{
    cidr_blocks      = []
    description      = "allow lambda security group access to bedrock"
    from_port        = 443
    ipv6_cidr_blocks = []
    prefix_list_ids  = []
    protocol         = "tcp"
    security_groups  = []
    self             = true
    to_port          = 443
  }]
  name   = "cg-production-chatbot-lambda-sg"
  region = "us-east-1"
  tags   = {}
  vpc_id = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_iam_role_policy_attachment" "extractor_CGMetadataExtractorPolicy" {
  policy_arn = "arn:aws:iam::001879457662:policy/CGMetadataExtractorPolicy"
  role       = "CGMetadataExtractorRole"
}

resource "aws_ecr_lifecycle_policy" "application" {
  policy = jsonencode({
    rules = [{
      action = {
        type = "expire"
      }
      description  = "Keep only the 3 most recent tagged images"
      rulePriority = 1
      selection = {
        countNumber   = 3
        countType     = "imageCountMoreThan"
        tagPrefixList = ["v"]
        tagStatus     = "tagged"
      }
      }, {
      action = {
        type = "expire"
      }
      description  = "Expire untagged images after 1 day"
      rulePriority = 2
      selection = {
        countNumber = 1
        countType   = "sinceImagePushed"
        countUnit   = "days"
        tagStatus   = "untagged"
      }
    }]
  })
  region     = "us-east-1"
  repository = "cg-metadata-extractor"
}

resource "aws_subnet" "us_east_1d" {
  lifecycle {
    prevent_destroy = true
  }
  assign_ipv6_address_on_creation                = false
  availability_zone                              = "us-east-1d"
  cidr_block                                     = "172.30.3.0/24"
  enable_dns64                                   = false
  enable_resource_name_dns_a_record_on_launch    = false
  enable_resource_name_dns_aaaa_record_on_launch = false
  ipv6_native                                    = false
  map_public_ip_on_launch                        = true
  private_dns_hostname_type_on_launch            = "ip-name"
  region                                         = "us-east-1"
  tags                                           = {}
  vpc_id                                         = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_iam_policy" "extractor_CGMetadataExtractorPolicy" {
  description = "Allows the metadata batch process access to the s3 container with the production files."
  name        = "CGMetadataExtractorPolicy"
  path        = "/"
  policy = jsonencode({
    Statement = [{
      Action   = ["s3:ListBucket", "s3:GetObject", "s3:PutObject"]
      Effect   = "Allow"
      Resource = ["arn:aws:s3:::cg-production-data", "arn:aws:s3:::cg-production-data/*", "arn:aws:s3:::cg-production-data-thumbnails", "arn:aws:s3:::cg-production-data-thumbnails/*", "arn:aws:s3:::cg-production-data-testing", "arn:aws:s3:::cg-production-data-testing/*", "arn:aws:s3:::cg-production-data-thumbnails-testing", "arn:aws:s3:::cg-production-data-thumbnails-testing/*"]
      }, {
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
      Effect   = "Allow"
      Resource = "arn:aws:logs:*:*:*"
      }, {
      Action   = "secretsmanager:GetSecretValue"
      Effect   = "Allow"
      Resource = "arn:aws:secretsmanager:us-east-1:001879457662:secret:cg-metadata-db/database-url-*"
    }]
    Version = "2012-10-17"
  })
  tags = {}
}

resource "aws_s3_bucket_public_access_block" "assets" {
  block_public_acls       = true
  block_public_policy     = true
  bucket                  = "cg-production-data"
  ignore_public_acls      = true
  region                  = "us-east-1"
  restrict_public_buckets = true
}

resource "aws_route_table" "production" {
  propagating_vgws = []
  region           = "us-east-1"
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = "igw-0aeac8f9ebd5d5aad"
  }
  tags   = {}
  vpc_id = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_security_group" "database" {
  lifecycle {
    prevent_destroy = true
  }
  description = "Security group for metadata db"
  egress = [{
    cidr_blocks      = ["0.0.0.0/0"]
    description      = ""
    from_port        = 0
    ipv6_cidr_blocks = []
    prefix_list_ids  = []
    protocol         = "-1"
    security_groups  = []
    self             = false
    to_port          = 0
  }]
  ingress = [{
    cidr_blocks      = ["98.19.64.23/32"]
    description      = "allow me to connect to the db from my local computer"
    from_port        = 5432
    ipv6_cidr_blocks = []
    prefix_list_ids  = []
    protocol         = "tcp"
    security_groups  = []
    self             = false
    to_port          = 5432
    }, {
    cidr_blocks      = []
    description      = "allow lambda function access to database"
    from_port        = 5432
    ipv6_cidr_blocks = []
    prefix_list_ids  = []
    protocol         = "tcp"
    security_groups  = ["sg-0412872e9f94acb2b"]
    self             = false
    to_port          = 5432
    }, {
    cidr_blocks      = []
    description      = "allow metadata extractor batch compute environment access to the database"
    from_port        = 5432
    ipv6_cidr_blocks = []
    prefix_list_ids  = []
    protocol         = "tcp"
    security_groups  = ["sg-0b84f22c177e4ec4a"]
    self             = false
    to_port          = 5432
  }]
  name   = "cg-metadata-db-sg"
  region = "us-east-1"
  tags   = {}
  vpc_id = "vpc-04bb7be45c9d6b7f7"
}

resource "aws_db_subnet_group" "production" {
  lifecycle {
    prevent_destroy = true
  }
  description = "Created from the RDS Management Console"
  name        = "default-vpc-04bb7be45c9d6b7f7"
  region      = "us-east-1"
  subnet_ids  = ["subnet-048d6ffc3b5232b64", "subnet-066e1c28b3e38624e", "subnet-068dbe005b3b31383", "subnet-079e45b681c5b8eef", "subnet-0c1279d57d6837bdf", "subnet-0edcbe2b0d8b9d291"]
  tags        = {}
}

resource "aws_s3_bucket" "assets" {
  lifecycle {
    prevent_destroy = true
  }
  bucket              = "cg-production-data"
  force_destroy       = false
  object_lock_enabled = false
  region              = "us-east-1"
  tags                = {}
}

resource "aws_s3_bucket" "thumbnails" {
  lifecycle {
    prevent_destroy = true
  }
  bucket              = "cg-production-data-thumbnails"
  force_destroy       = false
  object_lock_enabled = false
  region              = "us-east-1"
  tags                = {}
}

resource "aws_s3_bucket_lifecycle_configuration" "assets" {
  bucket                                 = "cg-production-data"
  region                                 = "us-east-1"
  transition_default_minimum_object_size = "all_storage_classes_128K"
  rule {
    id     = "MoveToIntelligentTiering"
    status = "Enabled"
    transition {
      days          = 0
      storage_class = "INTELLIGENT_TIERING"
    }
  }
}

resource "aws_vpc" "production" {
  lifecycle {
    prevent_destroy = true
  }
  assign_generated_ipv6_cidr_block     = false
  cidr_block                           = "172.30.0.0/16"
  enable_dns_hostnames                 = true
  enable_dns_support                   = true
  enable_network_address_usage_metrics = false
  instance_tenancy                     = "default"
  region                               = "us-east-1"
  tags                                 = {}
}
