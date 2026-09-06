variable "publish_shared_contract" {
  description = "Enable after the import-only baseline has been reviewed."
  type        = bool
  default     = false
}

resource "aws_ssm_parameter" "shared" {
  count = var.publish_shared_contract ? 1 : 0
  name  = "/cg-production/prod/shared/v1"
  type  = "String"
  value = jsonencode({
    version                     = 1
    vpc_id                      = aws_vpc.production.id
    subnet_ids                  = [aws_subnet.us_east_1a.id, aws_subnet.us_east_1b.id, aws_subnet.us_east_1c.id, aws_subnet.us_east_1d.id, aws_subnet.us_east_1e.id, aws_subnet.us_east_1f.id]
    database_security_group_id  = aws_security_group.database.id
    assistant_security_group_id = aws_security_group.assistant.id
    batch_security_group_id     = aws_security_group.batch.id
    database_host               = aws_db_instance.metadata.address
    database_port               = aws_db_instance.metadata.port
    asset_bucket                = aws_s3_bucket.assets.id
    thumbnail_bucket            = aws_s3_bucket.thumbnails.id
    database_secret_arn         = aws_secretsmanager_secret.database.arn
  })
}

output "job_definition_arn" {
  value = aws_batch_job_definition.extractor.arn
}
output "job_queue_arn" {
  value = aws_batch_job_queue.extractor.arn
}
output "image_uri" {
  value = jsondecode(aws_batch_job_definition.extractor.container_properties).image
}
