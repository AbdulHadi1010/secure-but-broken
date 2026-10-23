variable "region" {
  type        = string
  default     = "us-east-1"
  description = "Single region for Bedrock, Batch, S3, ECR. Chosen for widest Bedrock model catalogue and Spot depth."
}

variable "monthly_budget_usd" {
  type        = number
  default     = 100
  description = "Monthly cost cap used for AWS Budgets alerts (gross usage, before credits)."
}

variable "alert_email" {
  type        = string
  description = "Recipient for budget and cost-anomaly alerts."
}
