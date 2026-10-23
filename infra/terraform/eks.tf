# P8 EKS validation cluster (CLAUDE.md §6 "off by default", D-038). Created only with eks_enabled = true.
# One cluster, Kubernetes 1.37 (same minor as the kind node image), VPC CNI with NetworkPolicy enforcement on,
# 2 x c6i.2xlarge nodes (same type as the kind workers). Private API endpoint only: the measurement VM (same VPC)
# drives it through an EKS access entry for its existing IAM role. No inbound access from the internet.

variable "eks_enabled" {
  type    = bool
  default = false
}

variable "eks_version" {
  type    = string
  default = "1.37"
}

data "aws_subnets" "eks" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "availability-zone"
    values = ["us-east-1a", "us-east-1b"] # EKS needs subnets in two AZs; nodes stay in us-east-1a (with the VM)
  }
}

locals {
  eks_count = var.eks_enabled ? 1 : 0
  eks_name  = "${local.name}-p8"
}

data "aws_iam_policy_document" "eks_assume" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eks_cluster" {
  count              = local.eks_count
  name               = "${local.eks_name}-cluster"
  assume_role_policy = data.aws_iam_policy_document.eks_assume.json
}

resource "aws_iam_role_policy_attachment" "eks_cluster" {
  count      = local.eks_count
  role       = aws_iam_role.eks_cluster[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_iam_role" "eks_node" {
  count              = local.eks_count
  name               = "${local.eks_name}-node"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "eks_node" {
  for_each   = var.eks_enabled ? toset(["AmazonEKSWorkerNodePolicy", "AmazonEKS_CNI_Policy", "AmazonEC2ContainerRegistryReadOnly"]) : toset([])
  role       = aws_iam_role.eks_node[0].name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/${each.value}"
}

resource "aws_eks_cluster" "p8" {
  count    = local.eks_count
  name     = local.eks_name
  version  = var.eks_version
  role_arn = aws_iam_role.eks_cluster[0].arn

  vpc_config {
    subnet_ids              = data.aws_subnets.eks.ids
    endpoint_private_access = true
    endpoint_public_access  = false
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = false
  }

  depends_on = [aws_iam_role_policy_attachment.eks_cluster]
}

# the measurement VM reaches the private API endpoint on 443
resource "aws_security_group_rule" "eks_api_from_vm" {
  count                    = local.eks_count
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_eks_cluster.p8[0].vpc_config[0].cluster_security_group_id
  source_security_group_id = aws_security_group.worker_vm.id
  description              = "kubectl from the P8 driver (measurement VM)"
}

resource "aws_eks_addon" "vpc_cni" {
  count                       = local.eks_count
  cluster_name                = aws_eks_cluster.p8[0].name
  addon_name                  = "vpc-cni"
  configuration_values        = jsonencode({ enableNetworkPolicy = "true" })
  resolve_conflicts_on_create = "OVERWRITE"
}

resource "aws_eks_node_group" "p8" {
  count           = local.eks_count
  cluster_name    = aws_eks_cluster.p8[0].name
  node_group_name = "${local.eks_name}-nodes"
  node_role_arn   = aws_iam_role.eks_node[0].arn
  subnet_ids      = data.aws_subnets.default.ids # us-east-1a, same AZ as the measurement VM
  instance_types  = [var.worker_vm_instance_type]
  capacity_type   = "ON_DEMAND"
  disk_size       = 60

  scaling_config {
    desired_size = 2
    min_size     = 2
    max_size     = 2
  }

  depends_on = [aws_iam_role_policy_attachment.eks_node, aws_eks_addon.vpc_cni]
}

resource "aws_eks_addon" "coredns" {
  count        = local.eks_count
  cluster_name = aws_eks_cluster.p8[0].name
  addon_name   = "coredns"
  depends_on   = [aws_eks_node_group.p8]
}

resource "aws_eks_addon" "kube_proxy" {
  count        = local.eks_count
  cluster_name = aws_eks_cluster.p8[0].name
  addon_name   = "kube-proxy"
}

# the measurement VM's existing role administers this one cluster (and only this one)
resource "aws_eks_access_entry" "vm" {
  count         = local.eks_count
  cluster_name  = aws_eks_cluster.p8[0].name
  principal_arn = aws_iam_role.worker_vm.arn
}

resource "aws_eks_access_policy_association" "vm" {
  count         = local.eks_count
  cluster_name  = aws_eks_cluster.p8[0].name
  principal_arn = aws_iam_role.worker_vm.arn
  policy_arn    = "arn:${data.aws_partition.current.partition}:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
  access_scope {
    type = "cluster"
  }
  depends_on = [aws_eks_access_entry.vm]
}

resource "aws_iam_role_policy" "vm_eks_describe" {
  count = local.eks_count
  name  = "p8-eks-describe"
  role  = aws_iam_role.worker_vm.id
  policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = ["eks:DescribeCluster"], Resource = aws_eks_cluster.p8[0].arn }]
  })
}

output "eks_cluster_name" {
  value = var.eks_enabled ? aws_eks_cluster.p8[0].name : null
}
