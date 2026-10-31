# One item per attempt; pointers (S3 keys) to the raw artifacts. On-demand billing = no idle cost.

resource "aws_dynamodb_table" "attempts" {
  name         = "${local.name}-attempts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"
  range_key    = "attempt_id"

  attribute {
    name = "run_id"
    type = "S"
  }

  attribute {
    name = "attempt_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  lifecycle {
    prevent_destroy = true
  }
}
