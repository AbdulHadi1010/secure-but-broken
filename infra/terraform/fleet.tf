# Worker fleet (D-027): identical on-demand VMs from one image of the validated measurement VM, pulling chains
# from SQS. No Spot (interruptions and cold caches would disturb measurements). Default size 0: nothing runs or
# costs anything until fleet_size, fleet_ami and fleet_commit are set for a batch.

variable "fleet_size" {
  type    = number
  default = 0
}

variable "fleet_ami" {
  type        = string
  default     = ""
  description = "AMI made from the validated worker VM (aws ec2 create-image); recorded in docs/decisions.md"
}

variable "fleet_commit" {
  type        = string
  default     = ""
  description = "git commit the workers check out (bundle uploaded by harness vm sync)"
}

resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${local.name}-jobs-dlq"
  message_retention_seconds = 1209600 # 14 days: failed chains stay visible for investigation
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${local.name}-jobs"
  visibility_timeout_seconds = 7200 # one chain (up to 5 iterations) must finish before it can reappear
  message_retention_seconds  = 1209600
  receive_wait_time_seconds  = 20
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 2 # a chain that fails twice goes to the DLQ instead of looping
  })
}

data "aws_iam_policy_document" "fleet_sqs" {
  statement {
    actions = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility", "sqs:GetQueueUrl",
    "sqs:GetQueueAttributes", "sqs:SendMessage"]
    resources = [aws_sqs_queue.jobs.arn, aws_sqs_queue.jobs_dlq.arn]
  }
}

resource "aws_iam_role_policy" "fleet_sqs" {
  name   = "fleet-sqs"
  role   = aws_iam_role.worker_vm.id
  policy = data.aws_iam_policy_document.fleet_sqs.json
}

resource "aws_instance" "fleet" {
  count                                = var.fleet_ami == "" ? 0 : var.fleet_size
  ami                                  = var.fleet_ami
  instance_type                        = var.worker_vm_instance_type
  subnet_id                            = data.aws_subnets.default.ids[0]
  vpc_security_group_ids               = [aws_security_group.worker_vm.id]
  iam_instance_profile                 = aws_iam_instance_profile.worker_vm.name
  instance_initiated_shutdown_behavior = "stop"
  user_data_replace_on_change          = true # user data runs only on first boot; a changed script needs a new instance
  user_data = templatefile("${path.module}/fleet-userdata.sh", {
    commit = var.fleet_commit
    bucket = aws_s3_bucket.artifacts.id
  })

  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 60
    encrypted   = true
  }

  tags = {
    Name   = "${local.name}-fleet-${count.index}"
    Commit = var.fleet_commit
  }
}

output "jobs_queue_url" {
  value = aws_sqs_queue.jobs.url
}

output "fleet_instance_ids" {
  value = aws_instance.fleet[*].id
}
