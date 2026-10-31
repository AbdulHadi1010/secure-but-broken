# Dedicated measurement VM (D-023): baseline and every attempt run here, never on the researcher's laptop.
# c6i.2xlarge = fixed-performance CPUs (no burst credits), the same type Batch will use later (P5).
# No SSH, no inbound ports: access via SSM Session Manager / send-command with an IAM role.
# Stop the instance when no run is going; cost accrues per running hour (+ disk).

variable "worker_vm_instance_type" {
  type    = string
  default = "c6i.2xlarge"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "availability-zone"
    values = ["us-east-1a"]
  }
}

data "aws_ssm_parameter" "ubuntu_2404" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "aws_security_group" "worker_vm" {
  name        = "${local.name}-worker-vm"
  description = "No inbound; outbound for image pulls, Bedrock, S3"
  vpc_id      = data.aws_vpc.default.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
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

resource "aws_iam_role" "worker_vm" {
  name               = "${local.name}-worker-vm"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "worker_vm_ssm" {
  role       = aws_iam_role.worker_vm.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Same permissions as a Batch worker job: artifacts bucket, attempt table, Bedrock Converse.
resource "aws_iam_role_policy" "worker_vm" {
  name   = "worker-job"
  role   = aws_iam_role.worker_vm.id
  policy = data.aws_iam_policy_document.worker_job.json
}

resource "aws_iam_instance_profile" "worker_vm" {
  name = "${local.name}-worker-vm"
  role = aws_iam_role.worker_vm.name
}

resource "aws_instance" "worker_vm" {
  ami                                  = data.aws_ssm_parameter.ubuntu_2404.value
  instance_type                        = var.worker_vm_instance_type
  subnet_id                            = data.aws_subnets.default.ids[0]
  vpc_security_group_ids               = [aws_security_group.worker_vm.id]
  iam_instance_profile                 = aws_iam_instance_profile.worker_vm.name
  instance_initiated_shutdown_behavior = "stop"
  user_data                            = file("${path.module}/worker-vm-userdata.sh")

  metadata_options {
    http_tokens = "required" # IMDSv2 only
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = 60
    encrypted   = true
  }

  tags = {
    Name = "${local.name}-worker-vm"
  }

  lifecycle {
    ignore_changes = [ami, user_data] # a new Ubuntu image must not silently replace the measuring machine
  }
}

output "worker_vm_instance_id" {
  value = aws_instance.worker_vm.id
}

output "worker_vm_ami" {
  value = nonsensitive(aws_instance.worker_vm.ami) # public Ubuntu AMI id; the SSM parameter is only typed as sensitive
}
