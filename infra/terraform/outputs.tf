output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "attempts_table" {
  value = aws_dynamodb_table.attempts.name
}

output "worker_ecr_repository_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "worker_job_role_arn" {
  value = aws_iam_role.worker_job.arn
}

output "task_execution_role_arn" {
  value = aws_iam_role.task_execution.arn
}
