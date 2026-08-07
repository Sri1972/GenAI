# DEVOPS IMPLEMENTATION TASKS: AsyncStandup Slack Bot

## Document Control
- **Product Name**: AsyncStandup
- **Version**: 5.0 (DevOps/Platform Engineering Implementation Tasks)
- **Last Updated**: 2024-01-17
- **Document Owner**: Platform Engineering Team
- **Status**: Ready for Sprint Planning
- **Related Documents**: PRD v1.0, TRD v1.0, Solution Design v1.0, EPICS_AND_STORIES v1.1, TASKS v2.0, Backend API Tasks v3.0, Database Tasks v4.0
- **Sprint Allocation**: 6 sprints (12 weeks) to MVP launch
- **Team Composition**: 1 DevOps/Platform engineer + backend engineers for integration
- **Total Estimated Effort**: 140-180 hours (DevOps-specific work)
- **Review Cycle**: Weekly during sprint retrospectives
- **Infrastructure Review**: Required before any production deployment
- **Contributors**: DevOps Engineer, Backend API Engineer, Database Engineer, Security Engineer
- **Change Log**:
  - v5.0 - DevOps-specific implementation tasks with infrastructure-as-code, CI/CD pipelines, monitoring/alerting, deployment strategies, security hardening, and operational procedures
  - v4.0 - Database implementation tasks
  - v3.0 - Backend API implementation tasks
  - v2.0 - Consolidated implementation plan (all disciplines)
  - v1.0 - Original epic/story structure

---

## Table of Contents
1. [How to Use This Document](#1-how-to-use-this-document)
2. [Critical Infrastructure Decisions](#2-critical-infrastructure-decisions)
3. [DevOps Principles & Standards](#3-devops-principles--standards)
4. [Phase 0: Infrastructure Foundation (Week 1)](#4-phase-0-infrastructure-foundation-week-1)
5. [Phase 1: CI/CD Pipeline Implementation (Weeks 2-4)](#5-phase-1-cicd-pipeline-implementation-weeks-2-4)
6. [Phase 2: Monitoring & Observability (Weeks 5-7)](#6-phase-2-monitoring--observability-weeks-5-7)
7. [Phase 3: Security Hardening & Compliance (Weeks 8-9)](#7-phase-3-security-hardening--compliance-weeks-8-9)
8. [Phase 4: Production Readiness & Launch (Weeks 10-12)](#8-phase-4-production-readiness--launch-weeks-10-12)
9. [Infrastructure as Code Strategy](#9-infrastructure-as-code-strategy)
10. [Deployment Strategy & Rollback Plans](#10-deployment-strategy--rollback-plans)
11. [Secrets Management](#11-secrets-management)
12. [Container Image Management](#12-container-image-management)
13. [Environment Management](#13-environment-management)
14. [Disaster Recovery Procedures](#14-disaster-recovery-procedures)
15. [Cost Optimization Strategy](#15-cost-optimization-strategy)
16. [Security Controls & Compliance](#16-security-controls--compliance)
17. [Operational Runbooks](#17-operational-runbooks)
18. [Appendix: Tool Selection Rationale](#18-appendix-tool-selection-rationale)

---

## 1. HOW TO USE THIS DOCUMENT

### 1.1 Purpose

This document defines **all DevOps/Platform Engineering tasks** required to deploy, operate, and maintain AsyncStandup from MVP through production scale. It covers:

- Infrastructure provisioning (IaC)
- CI/CD pipeline configuration
- Monitoring, logging, and alerting setup
- Deployment strategies and rollback procedures
- Security hardening and secrets management
- Cost optimization and resource management
- Operational runbooks and incident response procedures

### 1.2 Target Audience

**For DevOps Engineers:**
- Use this as your sprint backlog for infrastructure work
- Each task includes acceptance criteria and validation steps
- Dependencies on backend/database tasks are explicitly called out

**For Backend Engineers:**
- Reference this when implementing health checks, metrics instrumentation, and logging
- Coordinate on secrets management and environment variable requirements
- Review deployment strategies to understand rollback procedures

**For Engineering Leadership:**
- Use this to track infrastructure readiness and production launch blockers
- Reference cost estimates for budget planning
- Review security controls for compliance requirements

**For Product/QA:**
- Understand environment availability (dev, staging, production)
- Reference monitoring dashboards for system health validation
- Use runbooks to understand incident response procedures

### 1.3 Task Status Workflow

```
┌─────────────┐     ┌────────────┐     ┌─────────────┐     ┌──────┐
│ Not Started │ --> │ In Progress│ --> │   In Review │ --> │ Done │
└─────────────┘     └────────────┘     └─────────────┘     └──────┘
                                              │
                                              v
                                        ┌──────────┐
                                        │ Blocked  │
                                        └──────────┘
```

**Definition of Done (DevOps-specific):**
- Infrastructure code reviewed and approved by senior engineer
- All resources provisioned in staging and tested
- Monitoring/alerting configured and validated
- Documentation updated (runbooks, architecture diagrams)
- Security review completed (if applicable)
- Cost estimates validated against budget

### 1.4 Effort Estimation Guidelines

| Story Points | Hours | Complexity Example |
|--------------|-------|--------------------|
| 1 | 2-4 | Update existing Terraform module, add environment variable |
| 2 | 4-8 | Create new Terraform module, configure basic monitoring |
| 3 | 8-16 | Setup CI/CD pipeline, implement deployment strategy |
| 5 | 16-24 | Multi-service infrastructure, complex networking setup |
| 8 | 24-40 | Full observability stack, disaster recovery implementation |
| 13 | 40+ | Production migration, major architecture change |

---

## 2. CRITICAL INFRASTRUCTURE DECISIONS

### 2.1 Hosting Platform: AWS App Runner (MVP) → ECS Fargate (Scale)

**Decision:** Start with AWS App Runner for MVP, migrate to ECS Fargate when we hit 1000+ teams.

**Rationale:**
- **App Runner**: Fully managed container service, $0 when idle, auto-scaling, simple deployment via git push
- **Cost at 100 teams**: ~$50-100/month (vs. $200+ for Fargate)
- **Operational simplicity**: No cluster management, task definitions, or load balancer configuration
- **Trade-off accepted**: 30-second cold start (acceptable for async standup collection), less granular resource control

**Migration trigger:** When we hit 1000+ teams or need:
- Sub-second cold start times
- More granular auto-scaling policies
- Multi-region deployment
- Blue/green deployment strategies

**Implementation note:** All infrastructure code will be written to support both App Runner and ECS Fargate with minimal changes (same Dockerfile, environment variables, health checks).

### 2.2 Database: PostgreSQL RDS (Single-AZ → Multi-AZ)

**Decision:** Start with PostgreSQL RDS in single-AZ for MVP, enable Multi-AZ when we hit production.

**Rationale:**
- **Single-AZ for MVP**: $30-50/month (db.t3.small), sufficient for development and beta testing
- **Multi-AZ for production**: $100-150/month, automated failover, 99.95% uptime SLA
- **Trade-off accepted**: Single point of failure during MVP (acceptable for beta customers with clear SLA expectations)

**Migration trigger:** Before production launch with paying customers.

### 2.3 Caching/Job Queue: Redis ElastiCache (Single-Node → Cluster)

**Decision:** Start with single-node Redis for MVP, enable cluster mode when we hit 10K+ jobs/day.

**Rationale:**
- **Single-node for MVP**: $15-30/month (cache.t3.micro), sufficient for 1000 teams
- **Cluster mode for scale**: $100-200/month, automatic failover, read replicas
- **Trade-off accepted**: No automatic failover during MVP (BullMQ handles job retries on Redis failure)

**Migration trigger:** When Redis CPU consistently exceeds 70% or we need high availability.

### 2.4 Monitoring/Observability: CloudWatch (MVP) → DataDog (Production)

**Decision:** Start with AWS CloudWatch for MVP, migrate to DataDog when we hit 500+ teams.

**Rationale:**
- **CloudWatch for MVP**: Free tier covers most usage, native AWS integration, no additional vendor
- **DataDog for production**: Better alerting, unified logs/metrics/traces, Slack integration
- **Trade-off accepted**: Less sophisticated dashboards during MVP (acceptable for small team)

**Migration trigger:** When CloudWatch query performance degrades or we need advanced APM features.

### 2.5 CI/CD: GitHub Actions

**Decision:** GitHub Actions for all CI/CD workflows.

**Rationale:**
- Native GitHub integration (our code already lives there)
- Free for public repos, $0.008/minute for private repos
- Mature ecosystem (Docker build/push, AWS deployment actions)
- Self-hosted runners available if we need custom compute

**No migration planned:** GitHub Actions scales to 1M+ teams.

### 2.6 Infrastructure as Code: Terraform + AWS CDK

**Decision:** Use Terraform for core infrastructure, AWS CDK for Lambda functions (if needed later).

**Rationale:**
- **Terraform**: Cloud-agnostic (easier to migrate away from AWS if needed), mature ecosystem, strong state management
- **AWS CDK**: Better for complex Lambda configurations (if we migrate from App Runner to Lambda later)
- **Trade-off accepted**: Two IaC tools to maintain (but only Terraform for MVP)

---

## 3. DEVOPS PRINCIPLES & STANDARDS

### 3.1 Infrastructure as Code Standards

**ALL infrastructure must be defined in code:**
- No manual AWS console changes in staging or production
- All resources tagged with: `Environment`, `Service`, `Owner`, `CostCenter`
- Terraform state stored in S3 with DynamoDB locking
- Separate state files per environment (dev, staging, production)

**Code review requirements:**
- All infrastructure changes require PR review by senior engineer
- Terraform plan output must be posted in PR before approval
- Breaking changes require explicit approval from engineering leadership

### 3.2 Deployment Standards

**Every deployment must have:**
- Automated health checks (HTTP 200 from `/health` endpoint)
- Rollback plan documented in runbook
- Monitoring/alerting configured before deployment
- Tested in staging environment first

**Deployment windows:**
- MVP/Beta: Deploy anytime (no customers in production yet)
- Production: Deploy Monday-Thursday 10am-4pm PT (avoid Fridays, weekends, holidays)

### 3.3 Security Standards

**Secrets management:**
- NEVER commit secrets to git (enforce via pre-commit hooks)
- All secrets stored in AWS Secrets Manager
- Secrets rotated every 90 days (automated)
- Access logged and audited

**Network security:**
- All services run in private subnets (no public IPs)
- Database accessible only from application security group
- Redis accessible only from application security group
- Load balancer in public subnet with WAF rules

**Container security:**
- Base images scanned for vulnerabilities (Trivy in CI)
- No root user in containers
- Read-only root filesystem where possible
- Secrets injected via environment variables (not baked into images)

### 3.4 Observability Standards

**Structured logging:**
- All logs in JSON format with correlation IDs
- Required fields: `timestamp`, `level`, `service`, `message`, `correlation_id`
- Log levels: `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL`
- No PII in logs (scrub user emails, Slack tokens)

**Metrics:**
- Business metrics: standup submission rate, summarization latency, publishing success rate
- Infrastructure metrics: CPU, memory, disk, network, request rate, error rate, latency (p50, p95, p99)
- Custom metrics prefixed with `asyncstandup.`

**Alerting:**
- Every alert must have a runbook link
- Alerts routed to #oncall-alerts Slack channel
- Critical alerts page on-call engineer via PagerDuty
- Alert fatigue prevention: no more than 5 alerts/week in steady state

### 3.5 Cost Optimization Standards

**Resource tagging:**
- All resources tagged with `CostCenter` for chargeback
- Unused resources deleted within 7 days
- Non-production environments shut down overnight and weekends

**Right-sizing:**
- Review instance sizes monthly
- Auto-scaling policies tuned to actual load
- Reserved instances for predictable workloads (production database)

---

## 4. PHASE 0: INFRASTRUCTURE FOUNDATION (WEEK 1)

**Goal:** Provision core infrastructure (AWS account, networking, CI/CD, secrets management) so backend engineers can start deploying code in Week 2.

**Success Criteria:**
- Dev environment fully provisioned and accessible
- CI/CD pipeline deploys "Hello World" app successfully
- Secrets management configured and tested
- Monitoring/logging infrastructure ready

---

### Task 0.1: AWS Account Setup & Organization

**Story Points:** 2  
**Estimated Hours:** 4-6  
**Owner:** DevOps Engineer  
**Dependencies:** None (start immediately)

**Description:**
Set up AWS account structure, billing alerts, IAM roles, and organizational units for multi-environment management.

**Acceptance Criteria:**
- [ ] AWS Organization created with separate accounts for dev, staging, production (or separate VPCs if using single account)
- [ ] Root account secured with MFA and access keys deleted
- [ ] IAM roles created for developers, CI/CD, and on-call engineers
- [ ] Billing alerts configured at $50, $100, $200, $500 thresholds
- [ ] CloudTrail enabled for audit logging
- [ ] Cost allocation tags enforced via AWS Config

**Implementation Steps:**

1. **Create AWS Organization:**
   ```bash
   # Using AWS CLI
   aws organizations create-organization --feature-set ALL
   
   # Create organizational units
   aws organizations create-organizational-unit \
     --parent-id r-xxxx \
     --name "Development"
   
   aws organizations create-organizational-unit \
     --parent-id r-xxxx \
     --name "Production"
   ```

2. **Setup IAM Roles:**
   ```hcl
   # terraform/modules/iam/main.tf
   resource "aws_iam_role" "developer" {
     name = "AsyncStandup-Developer"
     
     assume_role_policy = jsonencode({
       Version = "2012-10-17"
       Statement = [{
         Action = "sts:AssumeRole"
         Effect = "Allow"
         Principal = {
           AWS = "arn:aws:iam::${var.account_id}:root"
         }
       }]
     })
   }
   
   resource "aws_iam_role_policy_attachment" "developer_readonly" {
     role       = aws_iam_role.developer.name
     policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
   }
   
   resource "aws_iam_role" "cicd" {
     name = "AsyncStandup-CICD"
     
     assume_role_policy = jsonencode({
       Version = "2012-10-17"
       Statement = [{
         Action = "sts:AssumeRole"
         Effect = "Allow"
         Principal = {
           Federated = "arn:aws:iam::${var.account_id}:oidc-provider/token.actions.githubusercontent.com"
         }
         Condition = {
           StringEquals = {
             "token.actions.githubusercontent.com:sub" = "repo:asyncstandup/asyncstandup:ref:refs/heads/main"
           }
         }
       }]
     })
   }
   ```

3. **Configure Billing Alerts:**
   ```hcl
   # terraform/modules/billing/main.tf
   resource "aws_budgets_budget" "monthly" {
     name         = "AsyncStandup-Monthly-Budget"
     budget_type  = "COST"
     limit_amount = "500"
     limit_unit   = "USD"
     time_unit    = "MONTHLY"
     
     notification {
       comparison_operator = "GREATER_THAN"
       threshold           = 80
       threshold_type      = "PERCENTAGE"
       notification_type   = "ACTUAL"
       subscriber_email_addresses = ["devops@asyncstandup.com"]
     }
   }
   ```

**Validation:**
- [ ] Can assume developer role and view AWS resources
- [ ] CI/CD role can deploy to App Runner
- [ ] Billing alert email received when test threshold exceeded
- [ ] CloudTrail logs visible in CloudWatch

**Risks:**
- **Account limits:** New AWS accounts have service limits (e.g., 5 VPCs per region). Request limit increases if needed.
- **Cost overruns:** Without proper tagging, hard to track costs per environment. Enforce tagging via AWS Config.

---

### Task 0.2: Network Infrastructure (VPC, Subnets, Security Groups)

**Story Points:** 3  
**Estimated Hours:** 8-12  
**Owner:** DevOps Engineer  
**Dependencies:** Task 0.1 (AWS account setup)

**Description:**
Provision VPC with public/private subnets, NAT gateway, security groups, and network ACLs for secure multi-tier architecture.

**Acceptance Criteria:**
- [ ] VPC created with CIDR block 10.0.0.0/16
- [ ] Public subnets (10.0.1.0/24, 10.0.2.0/24) in 2 availability zones
- [ ] Private subnets (10.0.10.0/24, 10.0.11.0/24) in 2 availability zones
- [ ] NAT gateway in public subnet for outbound internet access from private subnets
- [ ] Security groups created for App Runner, RDS, Redis with least-privilege rules
- [ ] VPC Flow Logs enabled for network traffic analysis

**Implementation Steps:**

1. **Create VPC Module:**
   ```hcl
   # terraform/modules/vpc/main.tf
   resource "aws_vpc" "main" {
     cidr_block           = "10.0.0.0/16"
     enable_dns_hostnames = true
     enable_dns_support   = true
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-VPC"
       Environment = var.environment
       Service     = "AsyncStandup"
     }
   }
   
   resource "aws_subnet" "public" {
     count                   = 2
     vpc_id                  = aws_vpc.main.id
     cidr_block              = "10.0.${count.index + 1}.0/24"
     availability_zone       = data.aws_availability_zones.available.names[count.index]
     map_public_ip_on_launch = true
     
     tags = {
       Name = "AsyncStandup-${var.environment}-Public-${count.index + 1}"
       Type = "Public"
     }
   }
   
   resource "aws_subnet" "private" {
     count             = 2
     vpc_id            = aws_vpc.main.id
     cidr_block        = "10.0.${count.index + 10}.0/24"
     availability_zone = data.aws_availability_zones.available.names[count.index]
     
     tags = {
       Name = "AsyncStandup-${var.environment}-Private-${count.index + 1}"
       Type = "Private"
     }
   }
   
   resource "aws_internet_gateway" "main" {
     vpc_id = aws_vpc.main.id
     
     tags = {
       Name = "AsyncStandup-${var.environment}-IGW"
     }
   }
   
   resource "aws_eip" "nat" {
     domain = "vpc"
     
     tags = {
       Name = "AsyncStandup-${var.environment}-NAT-EIP"
     }
   }
   
   resource "aws_nat_gateway" "main" {
     allocation_id = aws_eip.nat.id
     subnet_id     = aws_subnet.public[0].id
     
     tags = {
       Name = "AsyncStandup-${var.environment}-NAT"
     }
   }
   ```

2. **Create Security Groups:**
   ```hcl
   # terraform/modules/security_groups/main.tf
   resource "aws_security_group" "app_runner" {
     name        = "AsyncStandup-${var.environment}-AppRunner"
     description = "Security group for App Runner service"
     vpc_id      = var.vpc_id
     
     egress {
       from_port   = 0
       to_port     = 0
       protocol    = "-1"
       cidr_blocks = ["0.0.0.0/0"]
       description = "Allow all outbound traffic"
     }
     
     tags = {
       Name = "AsyncStandup-${var.environment}-AppRunner-SG"
     }
   }
   
   resource "aws_security_group" "rds" {
     name        = "AsyncStandup-${var.environment}-RDS"
     description = "Security group for PostgreSQL RDS"
     vpc_id      = var.vpc_id
     
     ingress {
       from_port       = 5432
       to_port         = 5432
       protocol        = "tcp"
       security_groups = [aws_security_group.app_runner.id]
       description     = "Allow PostgreSQL access from App Runner"
     }
     
     egress {
       from_port   = 0
       to_port     = 0
       protocol    = "-1"
       cidr_blocks = ["0.0.0.0/0"]
       description = "Allow all outbound traffic"
     }
     
     tags = {
       Name = "AsyncStandup-${var.environment}-RDS-SG"
     }
   }
   
   resource "aws_security_group" "redis" {
     name        = "AsyncStandup-${var.environment}-Redis"
     description = "Security group for Redis ElastiCache"
     vpc_id      = var.vpc_id
     
     ingress {
       from_port       = 6379
       to_port         = 6379
       protocol        = "tcp"
       security_groups = [aws_security_group.app_runner.id]
       description     = "Allow Redis access from App Runner"
     }
     
     egress {
       from_port   = 0
       to_port     = 0
       protocol    = "-1"
       cidr_blocks = ["0.0.0.0/0"]
       description = "Allow all outbound traffic"
     }
     
     tags = {
       Name = "AsyncStandup-${var.environment}-Redis-SG"
     }
   }
   ```

3. **Enable VPC Flow Logs:**
   ```hcl
   resource "aws_flow_log" "main" {
     iam_role_arn    = aws_iam_role.flow_logs.arn
     log_destination = aws_cloudwatch_log_group.flow_logs.arn
     traffic_type    = "ALL"
     vpc_id          = aws_vpc.main.id
     
     tags = {
       Name = "AsyncStandup-${var.environment}-FlowLogs"
     }
   }
   ```

**Validation:**
- [ ] Can ping NAT gateway from private subnet
- [ ] Security group rules tested (can connect to RDS from App Runner, cannot connect from internet)
- [ ] VPC Flow Logs visible in CloudWatch

**Risks:**
- **NAT gateway cost:** $0.045/hour + $0.045/GB processed = ~$35/month. Consider using NAT instance for dev environment to save costs.
- **Availability zone limits:** Some AWS regions have only 2 AZs. Ensure we're using a region with 3+ AZs for production.

---

### Task 0.3: Terraform State Management

**Story Points:** 2  
**Estimated Hours:** 4-6  
**Owner:** DevOps Engineer  
**Dependencies:** Task 0.1 (AWS account setup)

**Description:**
Configure S3 backend for Terraform state with DynamoDB locking to prevent concurrent modifications and enable state versioning.

**Acceptance Criteria:**
- [ ] S3 bucket created for Terraform state with versioning enabled
- [ ] DynamoDB table created for state locking
- [ ] Separate state files for dev, staging, production environments
- [ ] State encryption enabled with AWS KMS
- [ ] Terraform backend configuration documented in README

**Implementation Steps:**

1. **Create S3 Bucket for State:**
   ```hcl
   # terraform/bootstrap/main.tf (run manually first time)
   resource "aws_s3_bucket" "terraform_state" {
     bucket = "asyncstandup-terraform-state"
     
     tags = {
       Name        = "AsyncStandup-Terraform-State"
       Environment = "Global"
     }
   }
   
   resource "aws_s3_bucket_versioning" "terraform_state" {
     bucket = aws_s3_bucket.terraform_state.id
     
     versioning_configuration {
       status = "Enabled"
     }
   }
   
   resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
     bucket = aws_s3_bucket.terraform_state.id
     
     rule {
       apply_server_side_encryption_by_default {
         sse_algorithm = "AES256"
       }
     }
   }
   
   resource "aws_s3_bucket_public_access_block" "terraform_state" {
     bucket = aws_s3_bucket.terraform_state.id
     
     block_public_acls       = true
     block_public_policy     = true
     ignore_public_acls      = true
     restrict_public_buckets = true
   }
   ```

2. **Create DynamoDB Table for Locking:**
   ```hcl
   resource "aws_dynamodb_table" "terraform_locks" {
     name         = "asyncstandup-terraform-locks"
     billing_mode = "PAY_PER_REQUEST"
     hash_key     = "LockID"
     
     attribute {
       name = "LockID"
       type = "S"
     }
     
     tags = {
       Name        = "AsyncStandup-Terraform-Locks"
       Environment = "Global"
     }
   }
   ```

3. **Configure Backend:**
   ```hcl
   # terraform/environments/dev/backend.tf
   terraform {
     backend "s3" {
       bucket         = "asyncstandup-terraform-state"
       key            = "dev/terraform.tfstate"
       region         = "us-west-2"
       dynamodb_table = "asyncstandup-terraform-locks"
       encrypt        = true
     }
   }
   ```

4. **Create Makefile for Easy Environment Management:**
   ```makefile
   # Makefile
   .PHONY: init-dev init-staging init-prod plan-dev apply-dev
   
   init-dev:
   	cd terraform/environments/dev && terraform init
   
   plan-dev:
   	cd terraform/environments/dev && terraform plan
   
   apply-dev:
   	cd terraform/environments/dev && terraform apply
   
   init-staging:
   	cd terraform/environments/staging && terraform init
   
   plan-staging:
   	cd terraform/environments/staging && terraform plan
   
   apply-staging:
   	cd terraform/environments/staging && terraform apply
   ```

**Validation:**
- [ ] Can run `terraform init` successfully
- [ ] State file visible in S3 bucket
- [ ] Concurrent `terraform apply` blocked by DynamoDB lock
- [ ] State versioning works (can restore previous state)

**Risks:**
- **State file corruption:** If state file is corrupted, infrastructure becomes unmanageable. Enable versioning and backup state file daily.
- **Lock table deletion:** If DynamoDB table is deleted, concurrent modifications can corrupt state. Protect table with deletion protection.

---

### Task 0.4: Secrets Management Setup (AWS Secrets Manager)

**Story Points:** 2  
**Estimated Hours:** 4-6  
**Owner:** DevOps Engineer  
**Dependencies:** Task 0.1 (AWS account setup)

**Description:**
Configure AWS Secrets Manager for storing sensitive credentials (Slack tokens, OpenAI API keys, database passwords) with automatic rotation and audit logging.

**Acceptance Criteria:**
- [ ] Secrets Manager configured with KMS encryption
- [ ] Secrets created for: Slack Bot Token, Slack Signing Secret, OpenAI API Key, Database Password, Redis Password
- [ ] IAM policy created for App Runner to read secrets
- [ ] Secrets rotation policy configured (90 days)
- [ ] Audit logging enabled for secret access

**Implementation Steps:**

1. **Create KMS Key for Secrets Encryption:**
   ```hcl
   # terraform/modules/secrets/main.tf
   resource "aws_kms_key" "secrets" {
     description             = "KMS key for AsyncStandup secrets encryption"
     deletion_window_in_days = 30
     enable_key_rotation     = true
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-Secrets-KMS"
       Environment = var.environment
     }
   }
   
   resource "aws_kms_alias" "secrets" {
     name          = "alias/asyncstandup-${var.environment}-secrets"
     target_key_id = aws_kms_key.secrets.key_id
   }
   ```

2. **Create Secrets:**
   ```hcl
   resource "aws_secretsmanager_secret" "slack_bot_token" {
     name        = "asyncstandup/${var.environment}/slack/bot-token"
     description = "Slack Bot OAuth Token"
     kms_key_id  = aws_kms_key.secrets.arn
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-Slack-Bot-Token"
       Environment = var.environment
     }
   }
   
   resource "aws_secretsmanager_secret_version" "slack_bot_token" {
     secret_id     = aws_secretsmanager_secret.slack_bot_token.id
     secret_string = var.slack_bot_token # Passed via Terraform variables
   }
   
   resource "aws_secretsmanager_secret" "openai_api_key" {
     name        = "asyncstandup/${var.environment}/openai/api-key"
     description = "OpenAI API Key for GPT-4 Turbo"
     kms_key_id  = aws_kms_key.secrets.arn
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-OpenAI-API-Key"
       Environment = var.environment
     }
   }
   
   resource "aws_secretsmanager_secret" "database_password" {
     name        = "asyncstandup/${var.environment}/database/password"
     description = "PostgreSQL Database Password"
     kms_key_id  = aws_kms_key.secrets.arn
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-Database-Password"
       Environment = var.environment
     }
   }
   ```

3. **Create IAM Policy for Secret Access:**
   ```hcl
   resource "aws_iam_policy" "secrets_read" {
     name        = "AsyncStandup-${var.environment}-SecretsRead"
     description = "Allow reading secrets from Secrets Manager"
     
     policy = jsonencode({
       Version = "2012-10-17"
       Statement = [
         {
           Effect = "Allow"
           Action = [
             "secretsmanager:GetSecretValue",
             "secretsmanager:DescribeSecret"
           ]
           Resource = [
             aws_secretsmanager_secret.slack_bot_token.arn,
             aws_secretsmanager_secret.openai_api_key.arn,
             aws_secretsmanager_secret.database_password.arn
           ]
         },
         {
           Effect = "Allow"
           Action = [
             "kms:Decrypt",
             "kms:DescribeKey"
           ]
           Resource = aws_kms_key.secrets.arn
         }
       ]
     })
   }
   ```

4. **Configure Secrets Rotation:**
   ```hcl
   resource "aws_secretsmanager_secret_rotation" "database_password" {
     secret_id           = aws_secretsmanager_secret.database_password.id
     rotation_lambda_arn = aws_lambda_function.rotate_db_password.arn
     
     rotation_rules {
       automatically_after_days = 90
     }
   }
   ```

**Validation:**
- [ ] Can retrieve secrets using AWS CLI: `aws secretsmanager get-secret-value --secret-id asyncstandup/dev/slack/bot-token`
- [ ] IAM policy allows App Runner to read secrets
- [ ] Secret access logged in CloudTrail

**Risks:**
- **Secret leakage:** If secrets are accidentally committed to git, they must be rotated immediately. Enforce pre-commit hooks to prevent this.
- **Rotation failures:** If rotation Lambda fails, secrets become stale. Monitor rotation failures and alert on-call engineer.

---

### Task 0.5: Container Registry Setup (ECR)

**Story Points:** 1  
**Estimated Hours:** 2-4  
**Owner:** DevOps Engineer  
**Dependencies:** Task 0.1 (AWS account setup)

**Description:**
Create AWS ECR repository for storing Docker images with lifecycle policies to clean up old images and reduce storage costs.

**Acceptance Criteria:**
- [ ] ECR repository created for AsyncStandup application
- [ ] Image scanning enabled for vulnerability detection
- [ ] Lifecycle policy configured to keep only last 10 images
- [ ] IAM policy created for CI/CD to push images
- [ ] Repository encryption enabled with KMS

**Implementation Steps:**

1. **Create ECR Repository:**
   ```hcl
   # terraform/modules/ecr/main.tf
   resource "aws_ecr_repository" "asyncstandup" {
     name                 = "asyncstandup-${var.environment}"
     image_tag_mutability = "MUTABLE"
     
     image_scanning_configuration {
       scan_on_push = true
     }
     
     encryption_configuration {
       encryption_type = "KMS"
       kms_key         = aws_kms_key.ecr.arn
     }
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-ECR"
       Environment = var.environment
     }
   }
   
   resource "aws_ecr_lifecycle_policy" "asyncstandup" {
     repository = aws_ecr_repository.asyncstandup.name
     
     policy = jsonencode({
       rules = [
         {
           rulePriority = 1
           description  = "Keep only last 10 images"
           selection = {
             tagStatus   = "any"
             countType   = "imageCountMoreThan"
             countNumber = 10
           }
           action = {
             type = "expire"
           }
         }
       ]
     })
   }
   ```

2. **Create IAM Policy for CI/CD:**
   ```hcl
   resource "aws_iam_policy" "ecr_push" {
     name        = "AsyncStandup-${var.environment}-ECR-Push"
     description = "Allow pushing images to ECR"
     
     policy = jsonencode({
       Version = "2012-10-17"
       Statement = [
         {
           Effect = "Allow"
           Action = [
             "ecr:GetAuthorizationToken"
           ]
           Resource = "*"
         },
         {
           Effect = "Allow"
           Action = [
             "ecr:BatchCheckLayerAvailability",
             "ecr:GetDownloadUrlForLayer",
             "ecr:BatchGetImage",
             "ecr:PutImage",
             "ecr:InitiateLayerUpload",
             "ecr:UploadLayerPart",
             "ecr:CompleteLayerUpload"
           ]
           Resource = aws_ecr_repository.asyncstandup.arn
         }
       ]
     })
   }
   ```

**Validation:**
- [ ] Can push image to ECR: `docker push <account-id>.dkr.ecr.us-west-2.amazonaws.com/asyncstandup-dev:latest`
- [ ] Image scanning completes successfully
- [ ] Lifecycle policy deletes old images after 10 images pushed

**Risks:**
- **Image vulnerabilities:** If base image has critical vulnerabilities, deployment should be blocked. Configure ECR to fail builds on critical vulnerabilities.

---

### Task 0.6: Monitoring Infrastructure (CloudWatch)

**Story Points:** 3  
**Estimated Hours:** 8-12  
**Owner:** DevOps Engineer  
**Dependencies:** Task 0.1 (AWS account setup)

**Description:**
Configure CloudWatch log groups, metric filters, and dashboards for application and infrastructure monitoring.

**Acceptance Criteria:**
- [ ] CloudWatch log groups created for App Runner, RDS, Redis
- [ ] Log retention set to 30 days for dev, 90 days for production
- [ ] Metric filters created for error rate, latency, business metrics
- [ ] CloudWatch dashboard created with key metrics
- [ ] Log insights queries saved for common debugging scenarios

**Implementation Steps:**

1. **Create Log Groups:**
   ```hcl
   # terraform/modules/cloudwatch/main.tf
   resource "aws_cloudwatch_log_group" "app_runner" {
     name              = "/aws/apprunner/asyncstandup-${var.environment}"
     retention_in_days = var.environment == "production" ? 90 : 30
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-AppRunner-Logs"
       Environment = var.environment
     }
   }
   
   resource "aws_cloudwatch_log_group" "rds" {
     name              = "/aws/rds/asyncstandup-${var.environment}"
     retention_in_days = var.environment == "production" ? 90 : 30
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-RDS-Logs"
       Environment = var.environment
     }
   }
   ```

2. **Create Metric Filters:**
   ```hcl
   resource "aws_cloudwatch_log_metric_filter" "error_rate" {
     name           = "AsyncStandup-${var.environment}-ErrorRate"
     log_group_name = aws_cloudwatch_log_group.app_runner.name
     pattern        = "[time, request_id, level = ERROR*, ...]"
     
     metric_transformation {
       name      = "ErrorCount"
       namespace = "AsyncStandup/${var.environment}"
       value     = "1"
     }
   }
   
   resource "aws_cloudwatch_log_metric_filter" "standup_submissions" {
     name           = "AsyncStandup-${var.environment}-StandupSubmissions"
     log_group_name = aws_cloudwatch_log_group.app_runner.name
     pattern        = "[time, request_id, level, msg = \"Standup submitted\", ...]"
     
     metric_transformation {
       name      = "StandupSubmissionCount"
       namespace = "AsyncStandup/${var.environment}"
       value     = "1"
     }
   }
   ```

3. **Create CloudWatch Dashboard:**
   ```hcl
   resource "aws_cloudwatch_dashboard" "main" {
     dashboard_name = "AsyncStandup-${var.environment}"
     
     dashboard_body = jsonencode({
       widgets = [
         {
           type = "metric"
           properties = {
             metrics = [
               ["AsyncStandup/${var.environment}", "ErrorCount", { stat = "Sum" }],
               [".", "StandupSubmissionCount", { stat = "Sum" }]
             ]
             period = 300
             stat   = "Sum"
             region = var.aws_region
             title  = "Application Metrics"
           }
         },
         {
           type = "metric"
           properties = {
             metrics = [
               ["AWS/RDS", "CPUUtilization", { stat = "Average" }],
               [".", "DatabaseConnections", { stat = "Average" }]
             ]
             period = 300
             stat   = "Average"
             region = var.aws_region
             title  = "Database Metrics"
           }
         }
       ]
     })
   }
   ```

4. **Save Log Insights Queries:**
   ```hcl
   resource "aws_cloudwatch_query_definition" "errors" {
     name = "AsyncStandup-${var.environment}-Errors"
     
     log_group_names = [
       aws_cloudwatch_log_group.app_runner.name
     ]
     
     query_string = <<-EOT
       fields @timestamp, @message, level, error
       | filter level = "ERROR"
       | sort @timestamp desc
       | limit 100
     EOT
   }
   ```

**Validation:**
- [ ] Log groups visible in CloudWatch console
- [ ] Metric filters producing data points
- [ ] Dashboard displays metrics correctly
- [ ] Log insights queries return results

**Risks:**
- **Log volume cost:** CloudWatch charges $0.50/GB ingested. Monitor log volume and adjust retention policies if costs exceed budget.

---

## 5. PHASE 1: CI/CD PIPELINE IMPLEMENTATION (WEEKS 2-4)

**Goal:** Implement automated build, test, and deployment pipelines for all environments with proper quality gates and rollback mechanisms.

**Success Criteria:**
- Developers can deploy to dev environment with single git push
- All tests run automatically in CI
- Staging deployments require manual approval
- Production deployments have automated rollback on health check failure

---

### Task 1.1: GitHub Actions Workflow for Build & Test

**Story Points:** 3  
**Estimated Hours:** 8-12  
**Owner:** DevOps Engineer  
**Dependencies:** Task 0.5 (ECR setup), Backend code repository initialized

**Description:**
Create GitHub Actions workflow to build Docker image, run tests, scan for vulnerabilities, and push to ECR on every commit.

**Acceptance Criteria:**
- [ ] Workflow triggers on push to `main` and `develop` branches
- [ ] Runs linting (ESLint), unit tests (Jest), integration tests
- [ ] Builds Docker image and scans for vulnerabilities (Trivy)
- [ ] Pushes image to ECR with git SHA tag
- [ ] Workflow fails if tests fail or critical vulnerabilities found
- [ ] Workflow completes in <5 minutes

**Implementation Steps:**

1. **Create GitHub Actions Workflow:**
   ```yaml
   # .github/workflows/build-and-test.yml
   name: Build and Test
   
   on:
     push:
       branches: [main, develop]
     pull_request:
       branches: [main, develop]
   
   env:
     AWS_REGION: us-west-2
     ECR_REPOSITORY: asyncstandup-dev
   
   jobs:
     test:
       runs-on: ubuntu-latest
       
       services:
         postgres:
           image: postgres:15
           env:
             POSTGRES_PASSWORD: testpassword
             POSTGRES_DB: asyncstandup_test
           options: >-
             --health-cmd pg_isready
             --health-interval 10s
             --health-timeout 5s
             --health-retries 5
           ports:
             - 5432:5432
         
         redis:
           image: redis:7
           options: >-
             --health-cmd "redis-cli ping"
             --health-interval 10s
             --health-timeout 5s
             --health-retries 5
           ports:
             - 6379:6379
       
       steps:
         - name: Checkout code
           uses: actions/checkout@v4
         
         - name: Setup Node.js
           uses: actions/setup-node@v4
           with:
             node-version: '20'
             cache: 'npm'
         
         - name: Install dependencies
           run: npm ci
         
         - name: Run linter
           run: npm run lint
         
         - name: Run unit tests
           run: npm run test:unit
           env:
             NODE_ENV: test
         
         - name: Run integration tests
           run: npm run test:integration
           env:
             NODE_ENV: test
             DATABASE_URL: postgresql://postgres:testpassword@localhost:5432/asyncstandup_test
             REDIS_URL: redis://localhost:6379
         
         - name: Upload test coverage
           uses: codecov/codecov-action@v3
           with:
             files: ./coverage/coverage-final.json
             fail_ci_if_error: true
     
     build:
       needs: test
       runs-on: ubuntu-latest
       
       permissions:
         id-token: write
         contents: read
       
       steps:
         - name: Checkout code
           uses: actions/checkout@v4
         
         - name: Configure AWS credentials
           uses: aws-actions/configure-aws-credentials@v4
           with:
             role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/AsyncStandup-CICD
             aws-region: ${{ env.AWS_REGION }}
         
         - name: Login to Amazon ECR
           id: login-ecr
           uses: aws-actions/amazon-ecr-login@v2
         
         - name: Build Docker image
           env:
             ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
             IMAGE_TAG: ${{ github.sha }}
           run: |
             docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
             docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
         
         - name: Scan Docker image for vulnerabilities
           uses: aquasecurity/trivy-action@master
           with:
             image-ref: ${{ steps.login-ecr.outputs.registry }}/${{ env.ECR_REPOSITORY }}:${{ github.sha }}
             format: 'sarif'
             output: 'trivy-results.sarif'
             severity: 'CRITICAL,HIGH'
             exit-code: '1'
         
         - name: Push Docker image to ECR
           if: success()
           env:
             ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
             IMAGE_TAG: ${{ github.sha }}
           run: |
             docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
             docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
         
         - name: Output image details
           env:
             ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
             IMAGE_TAG: ${{ github.sha }}
           run: |
             echo "Image: $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG"
             echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT
   ```

2. **Create Dockerfile:**
   ```dockerfile
   # Dockerfile
   FROM node:20-alpine AS builder
   
   WORKDIR /app
   
   COPY package*.json ./
   RUN npm ci --only=production
   
   COPY . .
   RUN npm run build
   
   FROM node:20-alpine
   
   # Create non-root user
   RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
   
   WORKDIR /app
   
   # Copy built application
   COPY --from=builder --chown=nodejs:nodejs /app/dist ./dist
   COPY --from=builder --chown=nodejs:nodejs /app/node_modules ./node_modules
   COPY --from=builder --chown=nodejs:nodejs /app/package.json ./
   
   USER nodejs
   
   EXPOSE 3000
   
   HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
     CMD node -e "require('http').get('http://localhost:3000/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1); })"
   
   CMD ["node", "dist/index.js"]
   ```

**Validation:**
- [ ] Workflow runs successfully on push to `main`
- [ ] Test failures cause workflow to fail
- [ ] Vulnerabilities in Docker image cause workflow to fail
- [ ] Image pushed to ECR with correct tags

**Risks:**
- **Test flakiness:** Flaky tests will block deployments. Quarantine flaky tests and fix them separately.
- **Build time:** If build time exceeds 10 minutes, consider caching Docker layers or splitting jobs.

---

### Task 1.2: Automated Deployment to Dev Environment

**Story Points:** 3  
**Estimated Hours:** 8-12  
**Owner:** DevOps Engineer  
**Dependencies:** Task 1.1 (Build workflow), Task 0.2 (VPC setup), App Runner provisioned

**Description:**
Create GitHub Actions workflow to automatically deploy to dev environment on successful build, with health check validation.

**Acceptance Criteria:**
- [ ] Workflow deploys to App Runner on push to `develop` branch
- [ ] Deployment waits for health check to pass before marking as successful
- [ ] Rollback triggered automatically if health check fails after 5 minutes
- [ ] Slack notification sent on deployment success/failure
- [ ] Deployment completes in <10 minutes

**Implementation Steps:**

1. **Provision App Runner Service (Terraform):**
   ```hcl
   # terraform/modules/app_runner/main.tf
   resource "aws_apprunner_service" "asyncstandup" {
     service_name = "asyncstandup-${var.environment}"
     
     source_configuration {
       image_repository {
         image_configuration {
           port = "3000"
           
           runtime_environment_variables = {
             NODE_ENV    = var.environment
             LOG_LEVEL   = var.environment == "production" ? "info" : "debug"
           }
           
           runtime_environment_secrets = {
             DATABASE_URL        = var.database_url_secret_arn
             REDIS_URL          = var.redis_url_secret_arn
             SLACK_BOT_TOKEN    = var.slack_bot_token_secret_arn
             OPENAI_API_KEY     = var.openai_api_key_secret_arn
           }
         }
         
         image_identifier      = "${var.ecr_repository_url}:latest"
         image_repository_type = "ECR"
       }
       
       authentication_configuration {
         access_role_arn = aws_iam_role.app_runner.arn
       }
       
       auto_deployments_enabled = false # Manual deployments via CI/CD
     }
     
     health_check_configuration {
       protocol            = "HTTP"
       path                = "/health"
       interval            = 10
       timeout             = 5
       healthy_threshold   = 1
       unhealthy_threshold = 3
     }
     
     instance_configuration {
       cpu    = "1 vCPU"
       memory = "2 GB"
     }
     
     network_configuration {
       egress_configuration {
         egress_type       = "VPC"
         vpc_connector_arn = aws_apprunner_vpc_connector.main.arn
       }
     }
     
     tags = {
       Name        = "AsyncStandup-${var.environment}"
       Environment = var.environment
     }
   }
   
   resource "aws_apprunner_vpc_connector" "main" {
     vpc_connector_name = "asyncstandup-${var.environment}-vpc-connector"
     subnets            = var.private_subnet_ids
     security_groups    = [var.app_runner_security_group_id]
     
     tags = {
       Name        = "AsyncStandup-${var.environment}-VPC-Connector"
       Environment = var.environment
     }
   }
   ```

2. **Create Deployment Workflow:**
   ```yaml
   # .github/workflows/deploy-dev.yml
   name: Deploy to Dev
   
   on:
     push:
       branches: [develop]
     workflow_dispatch:
   
   env:
     AWS_REGION: us-west-2
     APP_RUNNER_SERVICE: asyncstandup-dev
   
   jobs:
     deploy:
       runs-on: ubuntu-latest
       
       permissions:
         id-token: write
         contents: read
       
       steps:
         - name: Checkout code
           uses: actions/checkout@v4
         
         - name: Configure AWS credentials
           uses: aws-actions/configure-aws-credentials@v4
           with:
             role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/AsyncStandup-CICD
             aws-region: ${{ env.AWS_REGION }}
         
         - name: Update App Runner service
           id: deploy
           run: |
             aws apprunner update-service \
               --service-arn $(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='$APP_RUNNER_SERVICE'].ServiceArn" --output text) \
               --source-configuration ImageRepository={ImageIdentifier="${{ secrets.ECR_REGISTRY }}/asyncstandup-dev:${{ github.sha }}"}
         
         - name: Wait for deployment to complete
           run: |
             echo "Waiting for deployment to complete..."
             for i in {1..30}; do
               STATUS=$(aws apprunner describe-service --service-arn ${{ steps.deploy.outputs.service-arn }} --query 'Service.Status' --output text)
               if [ "$STATUS" == "RUNNING" ]; then
                 echo "Deployment successful!"
                 exit 0
               fi
               echo "Current status: $STATUS. Waiting 20 seconds..."
               sleep 20
             done
             echo "Deployment timed out after 10 minutes"
             exit 1
         
         - name: Validate health check
           run: |
             SERVICE_URL=$(aws apprunner describe-service --service-arn ${{ steps.deploy.outputs.service-arn }} --query 'Service.ServiceUrl' --output text)
             HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" https://$SERVICE_URL/health)
             if [ "$HEALTH_CHECK" != "200" ]; then
               echo "Health check failed with status code: $HEALTH_CHECK"
               exit 1
             fi
             echo "Health check passed!"
         
         - name: Send Slack notification on success
           if: success()
           uses: slackapi/slack-github-action@v1
           with:
             payload: |
               {
                 "text": "✅ Dev deployment successful",
                 "blocks": [
                   {
                     "type": "section",
                     "text": {
                       "type": "mrkdwn",
                       "text": "*Dev Deployment Successful* ✅\n\n*Commit:* ${{ github.sha }}\n*Author:* ${{ github.actor }}\n*Branch:* ${{ github.ref_name }}"
                     }
                   }
                 ]
               }
           env:
             SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
         
         - name: Send Slack notification on failure
           if: failure()
           uses: slackapi/slack-github-action@v1
           with:
             payload: |
               {
                 "text": "❌ Dev deployment failed",
                 "blocks": [
                   {
                     "type": "section",
                     "text": {
                       "type": "mrkdwn",
                       "text": "*Dev Deployment Failed* ❌\n\n*Commit:* ${{ github.sha }}\n*Author:* ${{ github.actor }}\n*Branch:* ${{ github.ref_name }}\n\n<${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View logs>"
                     }
                   }
                 ]
               }
           env:
             SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
   ```

**Validation:**
- [ ] Deployment triggered on push to `develop`
- [ ] Service updates successfully in App Runner
- [ ] Health check passes before marking deployment as successful
- [ ] Slack notification received

**Risks:**
- **Deployment failures:** If health check fails, App Runner will automatically roll back to previous version. Ensure health check endpoint is reliable.
- **Downtime during deployment:** App Runner has ~30 seconds of downtime during deployment. Acceptable for dev environment, but not for production.

---

### Task 1.3: Staging Deployment with Manual Approval

**Story Points:** 2  
**Estimated Hours:** 4-8  
**Owner:** DevOps Engineer  
**Dependencies:** Task 1.2 (Dev deployment), Staging environment provisioned

**Description:**
Create GitHub Actions workflow for staging deployment that requires manual approval from engineering lead before deploying.

**Acceptance Criteria:**
- [ ] Workflow triggers on push to `main` branch
- [ ] Requires manual approval from engineering lead before deploying
- [ ] Runs smoke tests after deployment
- [ ] Sends Slack notification to #engineering channel for approval request
- [ ] Deployment completes in <15 minutes after approval

**Implementation Steps:**

1. **Create Staging Deployment Workflow:**
   ```yaml
   # .github/workflows/deploy-staging.yml
   name: Deploy to Staging
   
   on:
     push:
       branches: [main]
     workflow_dispatch:
   
   env:
     AWS_REGION: us-west-2
     APP_RUNNER_SERVICE: asyncstandup-staging
   
   jobs:
     request-approval:
       runs-on: ubuntu-latest
       
       steps:
         - name: Send Slack notification for approval
           uses: slackapi/slack-github-action@v1
           with:
             payload: |
               {
                 "text": "🚀 Staging deployment approval needed",
                 "blocks": [
                   {
                     "type": "section",
                     "text": {
                       "type": "mrkdwn",
                       "text": "*Staging Deployment Approval Needed* 🚀\n\n*Commit:* ${{ github.sha }}\n*Author:* ${{ github.actor }}\n*Branch:* ${{ github.ref_name }}\n\n<${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|Approve deployment>"
                     }
                   }
                 ]
               }
           env:
             SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
     
     deploy:
       needs: request-approval
       runs-on: ubuntu-latest
       environment: staging
       
       permissions:
         id-token: write
         contents: read
       
       steps:
         - name: Checkout code
           uses: actions/checkout@v4
         
         - name: Configure AWS credentials
           uses: aws-actions/configure-aws-credentials@v4
           with:
             role-to-assume: arn:aws:iam::${{ secrets.AWS_ACCOUNT_ID }}:role/AsyncStandup-CICD
             aws-region: ${{ env.AWS_REGION }}
         
         - name: Update App Runner service
           id: deploy
           run: |
             aws apprunner update-service \
               --service-arn $(aws apprunner list-services --query "ServiceSummaryList[?ServiceName=='$APP_RUNNER_SERVICE'].ServiceArn" --output text) \
               --source-configuration ImageRepository={ImageIdentifier="${{ secrets.ECR_REGISTRY }}/asyncstandup-staging:${{ github.sha }}"}
         
         - name: Wait for deployment to complete
           run: |
             echo "Waiting for deployment to complete..."
             for i in {1..30}; do
               STATUS=$(aws apprunner describe-service --service-arn ${{ steps.deploy.outputs.service-arn }} --query 'Service.Status' --output text)
               if [ "$STATUS" == "RUNNING" ]; then
                 echo "Deployment successful!"
                 exit 0
               fi
               echo "Current status: $STATUS. Waiting 20 seconds..."
               sleep 20
             done
             echo "Deployment timed out after 10 minutes"
             exit 1
         
         - name: Run smoke tests
           run: |
             SERVICE_URL=$(aws apprunner describe-service --service-arn ${{ steps.deploy.outputs.service-arn }} --query 'Service.ServiceUrl' --output text)
             npm run test:smoke -- --base-url=https://$SERVICE_URL
         
         - name: Send Slack notification on success
           if: success()
           uses: slackapi/slack-github-action@v1
           with:
             payload: |
               {
                 "text": "✅ Staging deployment successful",
                 "blocks": [
                   {
                     "type": "section",
                     "text": {
                       "type": "mrkdwn",
                       "text": "*Staging Deployment Successful* ✅\n\n*Commit:* ${{ github.sha }}\n*Author:* ${{ github.actor }}\n*Branch:* ${{ github.ref_name }}"
                     }
                   }
                 ]
               }
           env:
             SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
   ```

2. **Configure GitHub Environment Protection:**
   - Go to GitHub repo → Settings → Environments → Create "staging" environment
   - Add required reviewers (engineering lead)
   - Set deployment branch to `main` only

**Validation:**
- [ ] Workflow pauses for approval
- [ ] Deployment proceeds after approval
- [ ] Smoke tests run successfully
- [ ] Slack notifications sent

**Risks:**
- **Approval delays:** If engineering lead is unavailable, deployment is blocked. Add backup approvers.

---

### Task 1.4: Production Deployment with Blue/Green Strategy

**Story Points:** 5  
**Estimated Hours:** 16-24  
**Owner:** DevOps Engineer  
**Dependencies:** Task 1.3 (Staging deployment), Production environment provisioned

**Description:**
Implement blue/green deployment strategy for production with automated rollback on health check failure or error rate spike.

**Acceptance Criteria:**
- [ ] Workflow triggers on manual dispatch only (no automatic production deploys)
- [ ] Deploys new version to "green" environment while "blue" serves traffic
- [ ] Runs smoke tests against green environment
- [ ] Switches traffic from blue to green if tests pass
- [ ] Automatically rolls back to blue if error rate exceeds 5% within 10 minutes
- [ ] Keeps blue environment running for 1 hour before decommissioning
- [ ] Deployment completes in <30 minutes

**Implementation Steps:**

1. **Provision Blue/Green App Runner Services:**
   ```hcl
   # terraform/modules/app_runner/main.tf
   resource "aws_apprunner_service" "blue" {
     service_name = "asyncstandup-production-blue"
     
     # Same configuration as before
     # ...
     
     tags = {
       Name        = "AsyncStandup-Production-Blue"
       Environment = "production"
       Slot        = "blue"
     }
   }
   
   resource "aws_apprunner_service" "green" {
     service_name = "asyncstandup-production-green"
     
     # Same configuration as before
     # ...
     
     tags = {
       Name        = "AsyncStandup-Production-Green"
       Environment = "production"
       Slot        = "green"
     }
   }
   
   resource "aws_route53_record" "production" {
     zone_id = var.route53_zone_id
     name    = "api.asyncstandup.com"
     type    = "CNAME"
     ttl     = 60
     
     weighted_routing_policy {
       weight = 100
     }
     
     set_identifier = "blue"
     records        = [aws_apprunner_service.blue.service_url]
   }
   ```

2. **Create Blue/Green Deployment Workflow:**
   ```yaml
   # .github/workflows/deploy-production.yml
   name: Deploy to Production (Blue/Green)
   
   on:
     workflow_dispatch:
       inputs:
         image_tag:
           description: 'Image tag to deploy'
           required: true
   
   env:
     AWS_REGION: us-west-2
     BLUE_SERVICE