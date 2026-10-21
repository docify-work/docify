# -----------------------------------------------------------------------------
# envs/eks-lab - Phase 12 skeleton. Intentionally creates NOTHING yet.
# See README.md. Outline to implement in P12.1:
#
# TODO 1  network      read the envs/main VPC + public/private subnets
#                      (data "aws_vpc" / "aws_subnets" by tag Project=docify)
# TODO 2  eks          aws_eks_cluster (version = var.cluster_version,
#                      public endpoint, access entries for the admin user)
#                      + aws_eks_node_group: capacity_type = "SPOT",
#                      instance_types = var.node_instance_types,
#                      scaling var.node_min..var.node_max, PUBLIC subnets
# TODO 3  identity     aws_eks_addon "eks-pod-identity-agent" + pod identity
#                      associations for: cluster-autoscaler, aws-load-balancer-
#                      controller, external-secrets, docify api/worker
# TODO 4  add-ons      cluster-autoscaler + aws-load-balancer-controller (Helm,
#                      pinned versions) - or install them via Argo CD
# TODO 5  rds          aws_db_instance postgres 17, var.rds_instance_class,
#                      private subnets, SG from nodes only, skip_final_snapshot,
#                      deletion_protection = false (lab), then
#                      CREATE EXTENSION vector
# TODO 6  outputs      cluster name/endpoint, RDS endpoint
#
# Teardown the SAME DAY: runbook R12 + scripts/whats-running.sh
# -----------------------------------------------------------------------------

locals {
  name = "docify-eks-lab"

  # Referenced so `terraform validate` / tflint see every variable as used
  # until the real resources exist.
  planned = {
    cluster_version     = var.cluster_version
    node_instance_types = var.node_instance_types
    node_scaling        = [var.node_min, var.node_max]
    rds_instance_class  = var.rds_instance_class
  }
}

output "plan" {
  description = "What this lab will create (placeholder until P12)."
  value       = merge({ name = local.name }, local.planned)
}
