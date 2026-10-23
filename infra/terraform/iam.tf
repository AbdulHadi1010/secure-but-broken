# P0 roles only. Batch service role, instance profile and Step Functions role are added in P5.
# Roles only, no IAM users or access keys.

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

# Task execution role: pulls the worker image from ECR and writes container logs.
resource "aws_iam_role" "task_execution" {
  name               = "${local.name}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Worker job role: what the code inside one attempt may do.
resource "aws_iam_role" "worker_job" {
  name               = "${local.name}-worker-job"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "worker_job" {
  statement {
    sid       = "ArtifactsReadWrite"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload"]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }

  statement {
    sid       = "ArtifactsList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]
  }

  statement {
    sid       = "AttemptIndex"
    actions   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.attempts.arn]
  }

  # Converse uses the InvokeModel permission. Cross-region (us.*) inference profiles fan out to
  # several US regions, hence the wildcard region on foundation-model ARNs.
  statement {
    sid     = "BedrockConverse"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:${data.aws_partition.current.partition}:bedrock:*::foundation-model/*",
      "arn:${data.aws_partition.current.partition}:bedrock:*:${local.account_id}:inference-profile/*",
    ]
  }
}

resource "aws_iam_role_policy" "worker_job" {
  name   = "worker-job"
  role   = aws_iam_role.worker_job.id
  policy = data.aws_iam_policy_document.worker_job.json
}
