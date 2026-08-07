# TASKS.md

**SplitPay: Implementation Task Breakdown & Effort Estimation**

**Version:** 1.0  
**Date:** [Current Date]  
**Author:** Senior DevOps/Platform Engineer + Technical Leadership Team  
**Status:** Ready for Sprint Planning & Execution  

**Document Purpose:** This document translates user stories from EPICS_AND_STORIES.md into granular, independently executable implementation tasks with effort estimates, technical dependencies, risk assessments, and acceptance criteria. Each task is scoped to be completable by a single engineer in 1-3 days. Tasks are sequenced to respect technical dependencies and enable parallel work where possible. This is the authoritative source for sprint execution, resource allocation, progress tracking, and DevOps/platform infrastructure delivery.

---

## TABLE OF CONTENTS

1. [Overview & Task Structure](#1-overview--task-structure)
2. [Cross-Epic Setup & Infrastructure Tasks (Sprint 0)](#2-cross-epic-setup--infrastructure-tasks-sprint-0)
3. [Epic 1: User Authentication & Account Management](#3-epic-1-user-authentication--account-management)
4. [Epic 2: Receipt Capture & OCR Processing](#4-epic-2-receipt-capture--ocr-processing)
5. [Epic 3: Item Claiming & Expense Categorization](#5-epic-3-item-claiming--expense-categorization)
6. [Epic 4: Expense Calculation & Settlement Logic](#6-epic-4-expense-calculation--settlement-logic)
7. [Epic 5: Payment Coordination & Reminders](#7-epic-5-payment-coordination--reminders)
8. [Epic 7: Group Management & Invitations](#8-epic-7-group-management--invitations)
9. [Epic 8: Data Persistence & Audit Trail](#9-epic-8-data-persistence--audit-trail)
10. [Epic 9: Monitoring, Observability & Operations](#10-epic-9-monitoring-observability--operations)
11. [Epic 10: Security & Compliance](#11-epic-10-security--compliance)
12. [Frontend: Responsive Design & Component Library](#12-frontend-responsive-design--component-library)
13. [Task Dependencies & Critical Path](#13-task-dependencies--critical-path)
14. [Risk Assessment & Mitigation](#14-risk-assessment--mitigation)
15. [Appendix: Task Estimation Rationale](#15-appendix-task-estimation-rationale)

---

## 1. OVERVIEW & TASK STRUCTURE

### 1.1 Task Organization & Metadata

Each task in this document includes the following metadata:

```
**Task ID:** SPLIT-XXX (unique identifier)
**Epic:** Epic N (reference to parent epic)
**Story:** SPLIT-N.M (reference to parent user story)
**Task Type:** [Infrastructure | Backend | Frontend | Database | DevOps | Testing | Documentation]
**Effort:** [X hours/days] (actual implementation time, excluding reviews)
**Complexity:** [Low | Medium | High | Critical] (technical complexity)
**Risk Level:** [Low | Medium | High] (execution risk)
**Priority:** [P0 | P1 | P2] (MVP-critical, important, nice-to-have)
**Sprint:** [Sprint 0-6] (planned sprint assignment)
**Assigned To:** [Role/Team] (recommended owner)
**Dependencies:** [List of blocking tasks] (tasks that must complete first)
**Blocks:** [List of dependent tasks] (tasks that depend on this one)
**Status:** [Not Started | In Progress | Code Review | Testing | Complete]
```

### 1.2 Effort Estimation Scale

| **Effort** | **Duration** | **Complexity** | **Typical Tasks** |
|---|---|---|---|
| **2 hours** | < 0.5 day | Trivial | Configuration, simple script, documentation |
| **4 hours** | 0.5 day | Simple | Single API endpoint, basic test, small config change |
| **8 hours** | 1 day | Moderate | Multi-step feature, integration test, moderate refactor |
| **16 hours** | 2 days | Complex | Service integration, algorithm implementation, complex feature |
| **24 hours** | 3 days | Very Complex | Multi-service orchestration, major feature, significant refactor |
| **40 hours** | 5 days | Highly Complex | Major system component, architectural change (rare) |

### 1.3 Task Sequencing Strategy

**Sprint 0 (Infrastructure & Setup - 1 week):** All cross-epic setup tasks complete before feature work begins. This ensures developers have a working local environment, CI/CD pipeline, and infrastructure.

**Sprint 1-4 (MVP Feature Development - 4 weeks):** Parallel feature development across epics, respecting dependencies. Core financial logic (Epics 4, 8) is prioritized to unblock other features.

**Sprint 5-6 (Post-MVP & Hardening - 2 weeks):** Recurring expenses (Epic 6), performance optimization, security hardening, and scaling preparation.

### 1.4 Team Structure & Role Definitions

| **Role** | **Responsibilities** | **Tasks** |
|---|---|---|
| **DevOps/Platform Engineer** | CI/CD, infrastructure, monitoring, deployment | Sprint 0 infrastructure tasks, Epic 9 tasks, ongoing pipeline maintenance |
| **Backend Engineer (API)** | Core API development, business logic | Epics 1, 2, 3, 4, 5, 7 backend tasks |
| **Backend Engineer (Data/OCR)** | OCR integration, receipt processing, data pipelines | Epic 2 OCR tasks, data pipeline setup |
| **Frontend Engineer (React Native)** | Mobile/web UI, client-side logic | Frontend tasks across all epics |
| **Database Engineer** | Schema design, migrations, optimization | Epic 8 tasks, database setup in Sprint 0 |
| **QA/Test Engineer** | Test automation, integration testing, performance testing | Testing tasks across all epics |
| **Security Engineer** | Security hardening, compliance, secrets management | Epic 10 tasks, security reviews |

---

## 2. CROSS-EPIC SETUP & INFRASTRUCTURE TASKS (SPRINT 0)

**Sprint 0 Objective:** Establish production-ready infrastructure, CI/CD pipeline, local development environment, and deployment automation. All subsequent feature work depends on these tasks completing successfully.

**Sprint 0 Duration:** 1 week (5 business days)

**Sprint 0 Success Criteria:**
- Developers can clone repo and run app locally in <5 minutes
- CI/CD pipeline is green and deployable to staging
- Staging environment is production-grade and accessible
- All secrets are managed securely (no hardcoded values in code)
- Monitoring and alerting are configured and tested
- Database schema is version-controlled and migratable
- Container images build successfully and pass security scans

---

### TASK 2.1: AWS Account Setup & Terraform Infrastructure Scaffolding

**Task ID:** SPLIT-INFRA-001  
**Epic:** Cross-Epic (Infrastructure)  
**Task Type:** DevOps/Infrastructure  
**Effort:** 16 hours (2 days)  
**Complexity:** High  
**Risk Level:** High (foundational; blocks all subsequent work)  
**Priority:** P0  
**Sprint:** Sprint 0  
**Assigned To:** DevOps/Platform Engineer  
**Dependencies:** None  
**Blocks:** SPLIT-INFRA-002, SPLIT-INFRA-003, SPLIT-INFRA-004, SPLIT-INFRA-005, SPLIT-DB-001  

**Objective:**
Set up AWS account, configure IAM roles/policies, and establish Terraform infrastructure-as-code scaffolding for dev/staging/production environments. This is the foundation for all infrastructure provisioning.

**Acceptance Criteria:**

1. **AWS Account Setup**
   - [ ] AWS account created with billing alerts configured
   - [ ] Root account MFA enabled and access restricted
   - [ ] IAM users created for DevOps engineer, CI/CD pipeline, and on-call rotation
   - [ ] IAM roles created for EC2, ECS, Lambda, RDS with least-privilege policies
   - [ ] CloudTrail enabled for audit logging of all API calls
   - [ ] VPC created with public/private subnets across 2+ AZs
   - [ ] NAT gateways configured for private subnet egress
   - [ ] Security groups created with restrictive ingress rules (principle of least privilege)

2. **Terraform Scaffolding**
   - [ ] Terraform backend configured in S3 with state locking (DynamoDB)
   - [ ] Terraform modules created for:
     - [ ] VPC and networking (subnets, security groups, NAT gateways)
     - [ ] RDS PostgreSQL (multi-AZ, automated backups, encryption at rest)
     - [ ] ECS cluster (auto-scaling group, launch template)
     - [ ] ECR container registries (backend, frontend, OCR worker)
     - [ ] ALB load balancer with target groups
     - [ ] CloudWatch log groups
     - [ ] RDS parameter groups (performance, security settings)
   - [ ] Terraform variables defined for environment-specific configuration (dev, staging, prod)
   - [ ] Terraform outputs defined for downstream reference (RDS endpoint, ALB DNS, ECR URIs)
   - [ ] `.tfvars` files created for each environment (NOT committed to Git; managed via Terraform Cloud or AWS Secrets Manager)

3. **Environment Definitions**
   - [ ] Dev environment: t3.small instances, 1 AZ, minimal redundancy
   - [ ] Staging environment: t3.medium instances, 2 AZs, production-grade configuration
   - [ ] Production environment: t3.large instances, 2+ AZs, auto-scaling, multi-region ready
   - [ ] All environments use same Terraform modules (configuration varies, not code)

4. **Documentation & Runbooks**
   - [ ] `INFRASTRUCTURE.md` created with:
     - [ ] AWS account structure and IAM roles
     - [ ] VPC topology diagram
     - [ ] RDS configuration and backup strategy
     - [ ] Scaling policies and thresholds
     - [ ] Disaster recovery topology
   - [ ] Runbook: "How to provision a new environment"
   - [ ] Runbook: "How to scale up/down resources"
   - [ ] Runbook: "How to rotate AWS credentials"

5. **Security & Compliance**
   - [ ] All resources tagged with `Environment`, `Owner`, `CostCenter`, `Compliance`
   - [ ] Encryption at rest enabled for RDS, S3, EBS volumes
   - [ ] Encryption in transit enabled (HTTPS/TLS for all APIs)
   - [ ] VPC Flow Logs enabled for network monitoring
   - [ ] AWS Config enabled to monitor compliance drift
   - [ ] No hardcoded credentials in Terraform code (all secrets via AWS Secrets Manager)

6. **Testing & Validation**
   - [ ] Terraform plan runs without errors
   - [ ] Terraform apply to dev environment succeeds
   - [ ] RDS database is accessible from ECS tasks
   - [ ] Security groups allow required traffic, block all else
   - [ ] CloudTrail logs are being recorded

**Technical Notes:**
- [ASSUMPTION] AWS is the cloud provider (specified in SOLUTION_DESIGN.md)
- [ASSUMPTION] Terraform is used for IaC (specified in SOLUTION_DESIGN.md)
- [ASSUMPTION] Multi-AZ for staging/prod (specified in SOLUTION_DESIGN.md)
- RDS backups are retained for 30 days; point-in-time recovery enabled
- S3 buckets for Terraform state, logs, and backups are versioned and encrypted
- CloudFront CDN is configured for frontend static assets (see TASK 2.5)

**Risks & Mitigations:**
- **Risk:** AWS account misconfiguration leads to security breach
  - **Mitigation:** Security review before production launch; enable GuardDuty for threat detection
- **Risk:** Terraform state corruption leads to infrastructure inconsistency
  - **Mitigation:** State locking enabled; regular backups of state; read-only replicas in secondary region

**Definition of Done:**
- Terraform code is peer-reviewed and approved
- Dev environment is provisioned and accessible
- All infrastructure is documented and version-controlled
- Security review completed with no critical findings
- Next task (SPLIT-INFRA-002) can begin

---

### TASK 2.2: PostgreSQL Database Schema & Migrations Setup

**Task ID:** SPLIT-INFRA-002  
**Epic:** Cross-Epic (Infrastructure) + Epic 8 (Data Persistence)  
**Task Type:** Database/Backend  
**Effort:** 16 hours (2 days)  
**Complexity:** High  
**Risk Level:** High (financial data integrity depends on schema correctness)  
**Priority:** P0  
**Sprint:** Sprint 0  
**Assigned To:** Database Engineer  
**Dependencies:** SPLIT-INFRA-001 (AWS RDS provisioned)  
**Blocks:** SPLIT-DB-002, SPLIT-DB-003, SPLIT-DB-004, SPLIT-DB-005, SPLIT-1.1, SPLIT-2.1  

**Objective:**
Design and implement PostgreSQL schema for SplitPay, including all tables, indexes, constraints, and audit logging infrastructure. Set up database migration framework (Sequelize or TypeORM) to version-control all schema changes.

**Acceptance Criteria:**

1. **Core Tables**
   - [ ] `users` table:
     - `user_id` (UUID, primary key)
     - `email` (VARCHAR, unique, indexed)
     - `password_hash` (VARCHAR, bcrypt)
     - `first_name`, `last_name` (VARCHAR)
     - `phone_number` (VARCHAR, nullable, for SMS)
     - `is_active` (BOOLEAN, default true)
     - `email_verified_at` (TIMESTAMP, nullable)
     - `created_at`, `updated_at` (TIMESTAMP)
     - `deleted_at` (TIMESTAMP, nullable, for soft deletes)
   - [ ] `groups` table (for grouping users for bill splits):
     - `group_id` (UUID, primary key)
     - `name` (VARCHAR)
     - `created_by` (UUID, foreign key to users)
     - `created_at`, `updated_at` (TIMESTAMP)
   - [ ] `group_members` table (junction table for users in groups):
     - `group_member_id` (UUID, primary key)
     - `group_id` (UUID, foreign key)
     - `user_id` (UUID, foreign key)
     - `joined_at` (TIMESTAMP)
     - `is_active` (BOOLEAN)
     - Unique constraint: (group_id, user_id)
   - [ ] `receipts` table:
     - `receipt_id` (UUID, primary key)
     - `group_id` (UUID, foreign key)
     - `uploaded_by` (UUID, foreign key to users)
     - `image_url` (VARCHAR, S3 path)
     - `image_hash` (VARCHAR, for deduplication)
     - `ocr_status` (ENUM: pending, processing, completed, failed)
     - `ocr_error_message` (TEXT, nullable)
     - `total_amount` (NUMERIC(10,2), cents)
     - `currency` (VARCHAR, default 'USD')
     - `created_at`, `updated_at` (TIMESTAMP)
   - [ ] `line_items` table (extracted from receipt):
     - `line_item_id` (UUID, primary key)
     - `receipt_id` (UUID, foreign key)
     - `description` (VARCHAR)
     - `amount` (NUMERIC(10,2), cents, before tax/tip)
     - `quantity` (INTEGER, default 1)
     - `ocr_confidence` (NUMERIC(3,2), 0.0-1.0)
     - `created_at` (TIMESTAMP)
   - [ ] `item_claims` table (user claims ownership of line item):
     - `claim_id` (UUID, primary key)
     - `line_item_id` (UUID, foreign key, unique)
     - `claimed_by` (UUID, foreign key to users)
     - `claimed_at` (TIMESTAMP)
   - [ ] `expenses` table (settlement record):
     - `expense_id` (UUID, primary key)
     - `receipt_id` (UUID, foreign key)
     - `group_id` (UUID, foreign key)
     - `payer_id` (UUID, foreign key to users, who paid the bill)
     - `total_amount` (NUMERIC(10,2), cents, including tax/tip)
     - `tax_amount` (NUMERIC(10,2), cents)
     - `tip_amount` (NUMERIC(10,2), cents)
     - `created_at`, `updated_at` (TIMESTAMP)
   - [ ] `expense_splits` table (per-person share of expense):
     - `split_id` (UUID, primary key)
     - `expense_id` (UUID, foreign key)
     - `user_id` (UUID, foreign key)
     - `amount_owed` (NUMERIC(10,2), cents)
     - `amount_paid` (NUMERIC(10,2), cents, default 0)
     - `status` (ENUM: pending, paid, settled)
     - `created_at`, `updated_at` (TIMESTAMP)
   - [ ] `payments` table (actual payment transactions):
     - `payment_id` (UUID, primary key)
     - `payer_id` (UUID, foreign key to users)
     - `payee_id` (UUID, foreign key to users)
     - `amount` (NUMERIC(10,2), cents)
     - `status` (ENUM: pending, completed, failed)
     - `payment_method` (VARCHAR, e.g., 'manual', 'venmo', 'paypal')
     - `external_reference` (VARCHAR, nullable, for third-party payment tracking)
     - `created_at`, `completed_at` (TIMESTAMP)
   - [ ] `audit_log` table (immutable record of all financial transactions):
     - `audit_id` (UUID, primary key)
     - `entity_type` (VARCHAR, e.g., 'expense', 'payment', 'claim')
     - `entity_id` (UUID, foreign key to relevant table)
     - `action` (VARCHAR, e.g., 'created', 'updated', 'deleted')
     - `actor_id` (UUID, foreign key to users, who made the change)
     - `old_values` (JSONB, previous state)
     - `new_values` (JSONB, new state)
     - `created_at` (TIMESTAMP, immutable)
     - `request_id` (VARCHAR, for distributed tracing)

2. **Indexes & Performance**
   - [ ] Primary keys indexed (automatic)
   - [ ] Foreign keys indexed (automatic)
   - [ ] Composite indexes:
     - [ ] `(group_id, created_at)` on receipts (for list queries)
     - [ ] `(receipt_id, claimed_by)` on item_claims (for user's claims)
     - [ ] `(expense_id, user_id)` on expense_splits (for settlement queries)
     - [ ] `(payer_id, payee_id, status)` on payments (for payment tracking)
     - [ ] `(entity_type, entity_id, created_at)` on audit_log (for audit queries)
   - [ ] Full-text search index on `line_items.description` (for receipt search)
   - [ ] Explain plans reviewed; no sequential scans on large tables

3. **Constraints & Data Integrity**
   - [ ] Foreign key constraints with CASCADE delete where appropriate (e.g., deleting group deletes members)
   - [ ] Unique constraints:
     - [ ] `users(email)` (case-insensitive)
     - [ ] `group_members(group_id, user_id)` (no duplicate group members)
     - [ ] `item_claims(line_item_id)` (each item claimed by at most one user)
   - [ ] Check constraints:
     - [ ] `receipts.total_amount > 0`
     - [ ] `expense_splits.amount_owed >= 0`
     - [ ] `payments.amount > 0`
   - [ ] NOT NULL constraints on all required fields
   - [ ] Default values set appropriately (e.g., `created_at` defaults to NOW())

4. **Migration Framework**
   - [ ] Sequelize or TypeORM ORM configured
   - [ ] Migration files created for each schema version (e.g., `001-create-users-table.js`)
   - [ ] Migrations are:
     - [ ] Backward-compatible (can rollback without data loss)
     - [ ] Idempotent (safe to run multiple times)
     - [ ] Tested (rollup and rollback tested locally)
   - [ ] Migration runner script created (`npm run db:migrate`, `npm run db:rollback`)
   - [ ] Database versioning tracked in `schema_version` table

5. **Audit & Compliance**
   - [ ] Audit logging triggers created for all financial tables:
     - [ ] INSERT triggers log new values
     - [ ] UPDATE triggers log old and new values
     - [ ] DELETE triggers log old values
   - [ ] Audit log entries include `actor_id`, `request_id`, `timestamp`
   - [ ] Audit log is immutable (triggers prevent updates/deletes)
   - [ ] Audit log retention policy: 7 years (for financial compliance)

6. **Testing & Validation**
   - [ ] Schema created successfully in dev RDS instance
   - [ ] All tables and indexes created as specified
   - [ ] Foreign key constraints enforced
   - [ ] Sample data inserted and queries execute correctly
   - [ ] Migrations tested: forward and rollback
   - [ ] Performance baseline established (query times on 1M+ row tables)

7. **Documentation**
   - [ ] Database schema diagram (ER diagram) created and documented
   - [ ] Table descriptions and column definitions documented
   - [ ] Index strategy documented
   - [ ] Audit logging strategy documented
   - [ ] Migration runbook created

**Technical Notes:**
- [ASSUMPTION] PostgreSQL is the database (specified in PRD and TRD)
- [ASSUMPTION] Sequelize or TypeORM is used for ORM (specified in SOLUTION_DESIGN.md)
- JSONB columns are used for audit_log to store flexible old/new values
- Soft deletes (`deleted_at`) are used for users to preserve audit trail
- Hard deletes are used for transient data (e.g., failed OCR attempts)
- Audit log is append-only; never updated or deleted

**Risks & Mitigations:**
- **Risk:** Schema design doesn't scale to millions of expenses
  - **Mitigation:** Partition large tables (e.g., audit_log by date); archival strategy for old data
- **Risk:** Migration locks table and causes downtime
  - **Mitigation:** Use online schema change tools (pg_upgrade) for production; test migrations on staging first

**Definition of Done:**
- Schema created and tested in dev environment
- All tables, indexes, and constraints in place
- Migration framework working and tested
- Documentation complete
- Security review completed (no SQL injection vulnerabilities, proper constraints)
- Next task (SPLIT-INFRA-003) can begin

---

### TASK 2.3: CI/CD Pipeline Setup (GitHub Actions)

**Task ID:** SPLIT-INFRA-003  
**Epic:** Cross-Epic (Infrastructure) + Epic 9 (Operations)  
**Task Type:** DevOps  
**Effort:** 24 hours (3 days)  
**Complexity:** High  
**Risk Level:** High (pipeline is critical for all deployments)  
**Priority:** P0  
**Sprint:** Sprint 0  
**Assigned To:** DevOps/Platform Engineer  
**Dependencies:** SPLIT-INFRA-001 (AWS account and ECR set up)  
**Blocks:** All feature development tasks (every commit triggers pipeline)  

**Objective:**
Implement end-to-end CI/CD pipeline using GitHub Actions that builds, tests, scans, and deploys SplitPay to staging and production. Pipeline enforces quality gates and enables safe, automated releases.

**Acceptance Criteria:**

1. **Pipeline Stages (as per SOLUTION_DESIGN.md §2.1)**
   - [ ] **Stage 1: Code Quality & Security** (target: <3 minutes)
     - [ ] Lint (ESLint for backend, frontend)
     - [ ] Format check (Prettier)
     - [ ] SAST (SonarQube or Snyk)
     - [ ] Dependency scanning (npm audit, Snyk)
     - [ ] Secret scanning (Gitleaks, TruffleHog)
     - [ ] All checks run in parallel
   - [ ] **Stage 2: Build & Unit Tests** (target: <5 minutes)
     - [ ] Backend build (Node.js, TypeScript compilation)
     - [ ] Backend unit tests (Jest, ≥80% coverage)
     - [ ] Frontend build (React Native Web, Webpack)
     - [ ] Frontend unit tests (Jest, ≥80% coverage)
     - [ ] Database schema validation
     - [ ] All builds run in parallel
   - [ ] **Stage 3: Container Builds & Registry Push** (target: <5 minutes)
     - [ ] Backend Docker image built (tag: git-sha, latest)
     - [ ] Frontend Docker image built (tag: git-sha, latest)
     - [ ] Container images scanned for vulnerabilities (Trivy)
     - [ ] Images pushed to ECR
   - [ ] **Stage 4: Deploy to Staging** (target: <10 minutes)
     - [ ] Database migrations run (backward-compatible)
     - [ ] Backend deployed (rolling deployment, 2 replicas)
     - [ ] Frontend deployed (static hosting, CloudFront invalidation)
     - [ ] Smoke tests run (health checks, critical API calls)
   - [ ] **Stage 5: Integration & Functional Tests** (target: <15 minutes)
     - [ ] API contract tests (Pact)
     - [ ] End-to-end tests (Playwright: receipt upload → settlement)
     - [ ] Load tests (k6: 100 concurrent users)
     - [ ] Security tests (OWASP ZAP, dependency checks)
   - [ ] **Stage 6: Manual Approval Gate**
     - [ ] Slack notification sent to #deployments channel
     - [ ] Approval required from tech lead or product owner
     - [ ] Approval tracked in audit log
   - [ ] **Stage 7: Deploy to Production** (target: <10 minutes)
     - [ ] Blue/green deployment (old version remains live during deploy)
     - [ ] Health checks pass on new version
     - [ ] Smoke tests pass on new version
     - [ ] Error rate monitored for 10 minutes; auto-rollback if >5%
     - [ ] Latency monitored for 10 minutes; auto-rollback if p95 >1000ms

2. **GitHub Actions Workflow Files**
   - [ ] `.github/workflows/ci.yml` (stages 1-5, runs on every push to any branch)
     - Triggers: `push`, `pull_request`
     - Runs on: `ubuntu-latest`
     - Jobs: lint, test, build, scan (parallel)
     - Artifacts: test reports, coverage reports, build logs
   - [ ] `.github/workflows/deploy-staging.yml` (stage 4, runs on push to `main`)
     - Triggers: `push` to `main` branch
     - Runs after CI pipeline passes
     - Jobs: migrate-db, deploy-backend, deploy-frontend, smoke-tests
   - [ ] `.github/workflows/deploy-production.yml` (stages 6-7, manual trigger)
     - Triggers: Manual trigger via GitHub UI or API
     - Requires approval from CODEOWNERS
     - Jobs: blue-green-deploy, health-checks, auto-rollback-on-failure

3. **Quality Gates (Blocking Criteria)**
   - [ ] Lint errors block merge to `main`
   - [ ] SAST findings (critical/high) block merge to `main`
   - [ ] Secret detection blocks merge to `main`
   - [ ] Unit test failures block merge to `main`
   - [ ] Code coverage <80% blocks merge to `main`
   - [ ] Container scan findings (critical) block production deployment
   - [ ] Staging smoke tests failure blocks production deployment
   - [ ] Load test failures (p95 >1000ms) block production deployment

4. **Secrets Management**
   - [ ] GitHub Actions secrets configured for:
     - [ ] AWS credentials (IAM role with minimal permissions)
     - [ ] Docker registry credentials (ECR)
     - [ ] Database credentials (staging/prod)
     - [ ] Third-party API keys (OCR provider, SMS, notifications)
     - [ ] Slack webhook for notifications
   - [ ] Secrets are NOT logged in pipeline output
   - [ ] Secrets are rotated every 90 days
   - [ ] Secrets access is audited

5. **Notifications & Alerting**
   - [ ] Slack notifications:
     - [ ] Build started (optional, verbose)
     - [ ] Build failed (always)
     - [ ] Build passed (always)
     - [ ] Staging deployment started (always)
     - [ ] Staging deployment failed (always)
     - [ ] Production approval required (always, @channel)
     - [ ] Production deployment started (always)
     - [ ] Production deployment failed (always, @oncall)
     - [ ] Production deployment succeeded (always)
   - [ ] Email notifications for critical failures
   - [ ] PagerDuty alerts for production incidents (see TASK 2.8)

6. **Artifact Management**
   - [ ] Build artifacts (Docker images) tagged with:
     - [ ] Git SHA (immutable reference)
     - [ ] Branch name (for debugging)
     - [ ] Semantic version (for releases)
   - [ ] Test reports archived (JUnit XML, coverage reports)
   - [ ] Build logs retained for 30 days
   - [ ] Container images retained for 90 days (old images deleted to save ECR costs)

7. **Deployment Safety**
   - [ ] Blue/green deployment: old version remains live during deploy
   - [ ] Health checks verify new version before switching traffic
   - [ ] Automatic rollback if health checks fail or error rate spikes
   - [ ] Deployment logs include:
     - [ ] Start time, end time, duration
     - [ ] Deployed version (git SHA, semantic version)
     - [ ] Deployed by (user who triggered)
     - [ ] Rollback status (if applicable)

8. **Testing & Validation**
   - [ ] Pipeline runs successfully on sample commit
   - [ ] All stages complete within target times
   - [ ] Quality gates work (intentional lint error blocks merge)
   - [ ] Secrets are not leaked in logs
   - [ ] Staging deployment succeeds
   - [ ] Production deployment succeeds (with manual approval)
   - [ ] Rollback mechanism tested and works

9. **Documentation**
   - [ ] `.github/CONTRIBUTING.md` created with:
     - [ ] How to run pipeline locally
     - [ ] How to fix common pipeline failures
     - [ ] How to skip stages (only for emergencies)
   - [ ] Pipeline diagram documented
   - [ ] Runbook: "How to deploy to production"
   - [ ] Runbook: "How to rollback a deployment"

**Technical Notes:**
- [ASSUMPTION] GitHub is the Git hosting platform (not specified, but common for startups)
- [ASSUMPTION] GitHub Actions is the CI/CD platform (specified in SOLUTION_DESIGN.md)
- [ASSUMPTION] AWS ECR is the container registry (specified in SOLUTION_DESIGN.md)
- Blue/green deployment: two ECS task sets, ALB switches between them
- Auto-rollback: CloudWatch alarms trigger Lambda function to switch traffic back
- Staging environment uses same infrastructure code as production (only config differs)

**Risks & Mitigations:**
- **Risk:** Pipeline takes too long (>30 minutes), slowing development
  - **Mitigation:** Parallelize stages, cache dependencies, use smaller test datasets
- **Risk:** False positive test failures cause deployment blocks
  - **Mitigation:** Flaky tests identified and fixed; retry logic for network-dependent tests
- **Risk:** Secrets leaked in logs or artifacts
  - **Mitigation:** GitHub Actions automatically masks secrets; regular audit of logs

**Definition of Done:**
- All pipeline stages implemented and tested
- Quality gates working
- Staging deployment successful
- Production deployment tested (with manual approval)
- Documentation complete
- Security review completed (no credential leaks, proper access controls)
- Next feature development tasks can begin

---

### TASK 2.4: Local Development Environment Setup

**Task ID:** SPLIT-INFRA-004  
**Epic:** Cross-Epic (Infrastructure)  
**Task Type:** DevOps/Documentation  
**Effort:** 8 hours (1 day)  
**Complexity:** Medium  
**Risk Level:** Low  
**Priority:** P0  
**Sprint:** Sprint 0  
**Assigned To:** DevOps/Platform Engineer + Backend Lead  
**Dependencies:** SPLIT-INFRA-001 (Terraform setup), SPLIT-INFRA-002 (Database schema)  
**Blocks:** All feature development (developers need working local environment)  

**Objective:**
Create Docker Compose setup and developer documentation that enables any engineer to run the entire SplitPay stack locally (backend, frontend, database, Redis) with a single command. This ensures environment parity between dev, staging, and production.

**Acceptance Criteria:**

1. **Docker Compose Configuration**
   - [ ] `docker-compose.yml` created with services:
     - [ ] Backend (Node.js/Express, port 3000)
     - [ ] Frontend (React Native Web dev server, port 3001)
     - [ ] PostgreSQL database (port 5432, dev data seeded)
     - [ ] Redis (port 6379, for caching and sessions)
     - [ ] Mailhog (port 1025/8025, for email testing)
   - [ ] `docker-compose.override.yml` for local development (hot reload, verbose logging)
   - [ ] Environment variables defined in `.env.local` (not committed to Git)
   - [ ] Volumes mounted for code changes (hot reload without rebuild)
   - [ ] Networks configured for service-to-service communication
   - [ ] Health checks defined for all services
   - [ ] Startup order managed (database starts before backend)

2. **Database Seeding**
   - [ ] `scripts/seed-db.sql` creates test data:
     - [ ] 10 test users (with known credentials for testing)
     - [ ] 5 test groups
     - [ ] 20 sample receipts with line items
     - [ ] Sample expenses and settlements
   - [ ] Seed script is idempotent (safe to run multiple times)
   - [ ] Seed data includes edge cases (tax rounding, large bills, etc.)

3. **Backend Setup**
   - [ ] `.env.example` created with all required environment variables
   - [ ] `package.json` scripts:
     - [ ] `npm run dev` (starts backend with hot reload)
     - [ ] `npm run test` (runs unit tests)
     - [ ] `npm run lint` (lints code)
     - [ ] `npm run db:migrate` (runs database migrations)
     - [ ] `npm run db:seed` (seeds test data)
   - [ ] TypeScript compilation configured
   - [ ] ESLint and Prettier configured
   - [ ] Jest test runner configured
   - [ ] Nodemon configured for hot reload

4. **Frontend Setup**
   - [ ] React Native Web dev server configured
   - [ ] `package.json` scripts:
     - [ ] `npm run dev` (starts dev server with hot reload)
     - [ ] `npm run test` (runs unit tests)
     - [ ] `npm run lint` (lints code)
     - [ ] `npm run build` (builds for production)
   - [ ] Webpack configured for development and production
   - [ ] ESLint and Prettier configured
   - [ ] Jest test runner configured

5. **Getting Started Guide**
   - [ ] `DEVELOPMENT.md` created with:
     - [ ] Prerequisites (Docker, Node.js version, Git)
     - [ ] Quick start (5-minute setup):
       ```bash
       git clone ...
       cd splitpay
       cp .env.example .env.local
       docker-compose up
       # App is now running at http://localhost:3001
       ```
     - [ ] Troubleshooting common issues:
       - [ ] Port already in use
       - [ ] Database connection failed
       - [ ] Hot reload not working
     - [ ] How to run tests locally
     - [ ] How to debug backend (VSCode debugger, breakpoints)
     - [ ] How to debug frontend (Chrome DevTools)
     - [ ] How to access test data (test user credentials)
     - [ ] How to reset database
     - [ ] How to access Mailhog (email testing)

6. **Debugging & Development Tools**
   - [ ] VSCode launch configuration (`.vscode/launch.json`) for debugging Node.js backend
   - [ ] Chrome DevTools configuration for frontend debugging
   - [ ] Postman collection created with sample API requests
   - [ ] Swagger/OpenAPI documentation for API endpoints (see TASK 3.2)

7. **Testing & Validation**
   - [ ] Fresh clone of repo works with `docker-compose up`
     - [ ] Backend starts and is healthy
     - [ ] Frontend starts and is accessible
     - [ ] Database migrations run successfully
     - [ ] Test data is seeded
   - [ ] Health checks pass for all services
   - [ ] Sample API call succeeds (e.g., POST /api/v1/auth/register)
   - [ ] Frontend can make API calls to backend
   - [ ] Hot reload works (code change triggers rebuild)
   - [ ] Tests run locally and pass

8. **CI/CD Integration**
   - [ ] Docker images used in compose also used in CI/CD pipeline (same base images)
   - [ ] Environment variables consistent between local and CI/CD
   - [ ] Database schema and seed data match between local and staging

**Technical Notes:**
- [ASSUMPTION] Docker and Docker Compose are used for local development (specified in SOLUTION_DESIGN.md)
- [ASSUMPTION] Node.js v18 LTS is the target runtime
- [ASSUMPTION] React Native Web is used for frontend (specified in PRD and SOLUTION_DESIGN.md)
- Hot reload uses nodemon for backend, webpack-dev-server for frontend
- Mailhog is used for email testing (no real emails sent locally)

**Risks & Mitigations:**
- **Risk:** Docker setup is complex; developers struggle to get it working
  - **Mitigation:** Comprehensive DEVELOPMENT.md; pair programming for first-time setup; video walkthrough
- **Risk:** Docker images are large; slow to build on first run
  - **Mitigation:** Pre-built images pushed to ECR; developers pull instead of building
- **Risk:** Local database state gets corrupted; developer can't recover
  - **Mitigation:** Easy reset command (`docker-compose down -v` + `docker-compose up`)

**Definition of Done:**
- Docker Compose setup tested with fresh clone
- All services start and are healthy
- DEVELOPMENT.md is complete and accurate
- Test data is seeded and accessible
- Next feature development tasks can begin

---

### TASK 2.5: Container Registry & Image Build Infrastructure

**Task ID:** SPLIT-INFRA-005  
**Epic:** Cross-Epic (Infrastructure)  
**Task Type:** DevOps  
**Effort:** 8 hours (1 day)  
**Complexity:** Medium  
**Risk Level:** Low  
**Priority:** P0  
**Sprint:** Sprint 0  
**Assigned To:** DevOps/Platform Engineer  
**Dependencies:** SPLIT-INFRA-001 (AWS account set up)  
**Blocks:** SPLIT-INFRA-003 (CI/CD pipeline needs container registry)  

**Objective:**
Set up AWS ECR (Elastic Container Registry) for storing Docker images, configure image scanning for vulnerabilities, and establish image tagging and lifecycle policies.

**Acceptance Criteria:**

1. **ECR Repositories**
   - [ ] Three ECR repositories created:
     - [ ] `splitpay-backend` (Node.js API)
     - [ ] `splitpay-frontend` (React Native Web static assets)
     - [ ] `splitpay-ocr-worker` (OCR processing service, future)
   - [ ] Each repository has:
     - [ ] Image scanning enabled (Trivy)
     - [ ] Encryption at rest enabled
     - [ ] Immutable image tags enabled (prevent overwriting)
     - [ ] Image retention policy:
       - [ ] Keep last 10 production images (semantic versions)
       - [ ] Keep last 5 staging images (git-sha tags)
       - [ ] Delete images older than 90 days (except production)

2. **Dockerfile Best Practices**
   - [ ] Backend Dockerfile:
     - [ ] Multi-stage build (build stage, runtime stage)
     - [ ] Node.js base image: `node:18-alpine` (small, secure)
     - [ ] Non-root user for runtime (security)
     - [ ] Dependencies installed in separate layer (caching)
     - [ ] Health check defined (curl or node health endpoint)
     - [ ] No secrets baked into image
   - [ ] Frontend Dockerfile:
     - [ ] Multi-stage build
     - [ ] Node.js build stage, nginx runtime stage
     - [ ] Nginx configured for SPA (all routes → index.html)
     - [ ] Gzip compression enabled
     - [ ] Cache headers configured
     - [ ] Health check defined

3. **Image Scanning & Security**
   - [ ] Trivy scans images for vulnerabilities:
     - [ ] Critical vulnerabilities block push to ECR
     - [ ] High vulnerabilities require manual approval
     - [ ] Medium/low vulnerabilities are logged
   - [ ] Images are signed (Docker Content Trust)
   - [ ] Vulnerability reports are available in ECR console
   - [ ] Automated patching for base images (e.g., Node.js security updates)

4. **Image Tagging Strategy**
   - [ ] Tags used:
     - [ ] `latest` (most recent successful build on main)
     - [ ] `staging-latest` (most recent staging deployment)
     - [ ] `prod-latest` (most recent production deployment)
     - [ ] `v1.0.0` (semantic version for releases)
     - [ ] `git-sha-abc123` (immutable reference for debugging)
   - [ ] Images are never overwritten (immutable tags enabled in ECR)

5. **Image Build Process**
   - [ ] Images built in CI/CD pipeline (see TASK 2.3)
   - [ ] Build context optimized (`.dockerignore` file)
   - [ ] Build takes <5 minutes
   - [ ] Build is reproducible (same code → same image hash)

6. **Testing & Validation**
   - [ ] Backend image builds successfully
   - [ ] Frontend image builds successfully
   - [ ] Images are pushed to ECR
   - [ ] Images are scanned for vulnerabilities
   - [ ] Images can be pulled from ECR
   - [ ] Containers start and are healthy

**Technical Notes:**
- [ASSUMPTION] AWS ECR is used for container registry (specified in SOLUTION_DESIGN.md)
- [ASSUMPTION] Alpine Linux is used for small image size and security
- Multi-stage builds reduce final image size by ~70%
- Immutable tags prevent accidental overwrites and enable easy rollback

**Risks & Mitigations:**
- **Risk:** Images are too large; slow to push/pull
  - **Mitigation:** Multi-stage builds, alpine base images, aggressive .dockerignore
- **Risk:** Vulnerable images are deployed
  - **Mitigation:** Trivy scanning in CI/CD; critical vulnerabilities block deployment

**Definition of Done:**
- ECR repositories created and configured
- Dockerfiles optimized and tested
- Images scan successfully
- Images pushed to ECR
- CI/CD pipeline can pull images for deployment

---

### TASK 2.6: Secrets Management & Environment Configuration

**Task ID:** SPLIT-INFRA-006  
**Epic:** Cross-Epic (Infrastructure) + Epic 10 (Security)  
**Task Type:** DevOps/Security  
**Effort:** 12 hours (1.5 days)  
**Complexity:** High  
**Risk Level:** High (secrets management is critical for security)  
**Priority:** P0  
**Sprint:** Sprint 0  
**Assigned To:** DevOps/Platform Engineer + Security Engineer  
**Dependencies:** SPLIT-INFRA-001 (AWS account set up)  
**Blocks:** All services that need secrets (backend, OCR worker, etc.)  

**Objective:**
Implement secure secrets management using AWS Secrets Manager and Parameter Store, ensuring no secrets are stored in code, configuration files, or environment variables in source control.

**Acceptance Criteria:**

1. **AWS Secrets Manager**
   - [ ] Secrets created for each environment:
     - [ ] Development:
       - [ ] `splitpay/dev/db-password` (PostgreSQL)
       - [ ] `splitpay/dev/jwt-secret` (JWT signing key)
       - [ ] `splitpay/dev/ocr-api-key` (OCR provider API key)
       - [ ] `splitpay/dev/sms-api-key` (SMS provider API key)
       - [ ] `splitpay/dev/email-password` (SMTP password)
     - [ ] Staging:
       - [ ] Same as dev (different values)
     - [ ] Production:
       - [ ] Same as dev (different values, more sensitive)
   - [ ] Secrets are encrypted at rest (AWS KMS)
   - [ ] Secrets are encrypted in transit (HTTPS)
   - [ ] Secrets are rotated automatically:
     - [ ] Database passwords: 90 days
     - [ ] API keys: 180 days
     - [ ] JWT secrets: 365 days
   - [ ] Secrets access is logged in CloudTrail

2. **AWS Systems Manager Parameter Store**
   - [ ] Non-sensitive configuration stored in Parameter Store:
     - [ ] `splitpay/dev/log-level` (DEBUG, INFO, WARN, ERROR)
     - [ ] `splitpay/dev/ocr-provider` (e.g., AWS Textract, Google Vision)
     - [ ] `splitpay/dev/sms-provider` (e.g., Twilio)
     - [ ] `splitpay/dev/max-receipt-size-mb` (e.g., 10)
     - [ ] `splitpay/dev/api-rate-limit` (requests per minute)
   - [ ] Parameters are versioned
   - [ ] Parameter changes are logged

3. **Application Configuration**
   - [ ] Backend loads secrets from Secrets Manager at startup:
     ```javascript
     const secrets = await secretsManager.getSecret('splitpay/prod/db-password');
     const dbPassword = JSON.parse(secrets.SecretString).password;
     ```
   - [ ] Backend loads config from Parameter Store:
     ```javascript
     const logLevel = await parameterStore.getParameter('splitpay/prod/log-level');
     ```
   - [ ] Secrets are cached in memory (not fetched on every request)
   - [ ] Secrets are refreshed every 5 minutes (rotation detection)
   - [ ] Failed secret retrieval blocks application startup

4. **IAM Roles & Access Control**
   - [ ] ECS task role has permissions to read specific secrets:
     ```json
     {
       "Effect": "Allow",
       "Action": "secretsmanager:GetSecretValue",
       "Resource": "arn:aws:secretsmanager:us-east-1:123456789:secret:splitpay/prod/*"
     }
     ```
   - [ ] CI/CD pipeline role has limited permissions (only read non-prod secrets)
   - [ ] Developer laptops do NOT have production secret access
   - [ ] Secrets access is audited (CloudTrail logs all GetSecretValue calls)

5. **Local Development**
   - [ ] `.env.local` file is git-ignored (never committed)
   - [ ] `.env.example` file contains placeholder values (no real secrets)
   - [ ] Local development uses mock secrets or test values
   - [ ] Docker Compose injects secrets from `.env.local`

6. **Secrets Rotation**
   - [ ] Automatic rotation configured for database passwords:
     - [ ] Rotation function (Lambda) updates RDS password
     - [ ] Rotation happens every 90 days
     - [ ] Rotation is tested in staging before production
   - [ ] Manual rotation process documented for API keys:
     - [ ] New key generated from provider
     - [ ] New key stored in Secrets Manager
     - [ ] Old key revoked from provider
     - [ ] Runbook: "How to rotate API keys"

7. **Secret Scanning & Audit**
   - [ ] Git pre-commit hook prevents committing secrets:
     - [ ] Gitleaks scans for patterns (AWS keys, private keys, etc.)
     - [ ] Commit blocked if secrets detected
   - [ ] CI/CD pipeline scans for secrets (redundant check)
   - [ ] Regular audit of Secrets Manager (who accessed what, when)
   - [ ] Alerts configured for suspicious access patterns

8. **Documentation**
   - [ ] `SECRETS.md` created with:
     - [ ] How to add a new secret
     - [ ] How to rotate a secret
     - [ ] How to access a secret in code
     - [ ] How to debug secret access issues
   - [ ] Runbook: "How to recover from leaked secret"

9. **Testing & Validation**
   - [ ] Secrets are readable from ECS tasks
   - [ ] Secrets are not logged or printed to console
   - [ ] Secrets are not committed to Git
   - [ ] Secret rotation works (tested in staging)
   - [ ] IAM policies are enforced (unauthorized access denied)

**Technical Notes:**
- [ASSUMPTION] AWS Secrets Manager is used for sensitive secrets (specified in SOLUTION_DESIGN.md)
- [ASSUMPTION] AWS Systems Manager Parameter Store is used for non-sensitive config
- Secrets are JSON-formatted for easy parsing
- Rotation is automatic for database passwords; manual for API keys
- Secrets are cached to avoid excessive API calls to Secrets Manager

**Risks & Mitigations:**
- **Risk:** Secrets are accidentally committed to Git
  - **Mitigation:** Git pre-commit hook with Gitleaks; GitHub secret scanning; regular audits
- **Risk:** Secrets are logged to CloudWatch
  - **Mitigation:** Redact secrets from logs (see TASK 2.9); code review to catch logging
- **Risk:** Secrets are exposed in container images
  - **Mitigation:** Secrets loaded at runtime, not baked into images

**Definition of Done:**
- Secrets Manager configured with all required secrets
- IAM roles and policies configured
- Application loads secrets at startup
- Local development works with `.env.local`
- Secret scanning in CI/CD working
- Documentation complete

---

### TASK 2.7: Monitoring & Observability Infrastructure (CloudWatch, Datadog, or similar)

**Task ID:** SPLIT-INFRA-007  
**Epic:** Cross-Epic (Infrastructure) + Epic 9 (Operations)  
**Task Type:** DevOps  
**Effort:** 20 hours (2.5 days)  
**Complexity:** High  
**Risk Level:** Medium (monitoring is critical but can be iterated)  
**Priority:** P0  
**Sprint:** Sprint 0  
**Assigned To:** DevOps/Platform Engineer  
**Dependencies:** SPLIT-INFRA-001 (AWS account), SPLIT-INFRA-003 (CI/CD pipeline)  
**Blocks:** Epic 9 tasks (observability requires infrastructure in place)  

**Objective:**
Implement comprehensive monitoring and observability infrastructure using CloudWatch (AWS native) as the primary platform, with structured logging, metrics, dashboards, and alerting. This enables rapid incident detection and response.

**Acceptance Criteria:**

1. **CloudWatch Log Groups & Streams**
   - [ ] Log groups created for each service:
     - [ ] `/aws/ecs/splitpay-backend-prod` (production backend)
     - [ ] `/aws/ecs/splitpay-backend-staging` (staging backend)
     - [ ] `/aws/ecs/splitpay-frontend-prod` (production frontend)
     - [ ] `/aws/rds/splitpay-db` (database logs)
   - [ ] Log retention configured:
     - [ ] Production: 30 days
     - [ ] Staging: 7 days
     - [ ] Development: 3 days
   - [ ] Log streams organized by task/instance ID
   - [ ] Logs are queryable via CloudWatch Insights

2. **Structured Logging**
   - [ ] All logs are JSON-formatted (not plain text):
     ```json
     {
       "timestamp": "2024-01-15T10:30:45.123Z",
       "level": "INFO",
       "service": "backend",
       "request_id": "req-abc123",
       "user_id": "user-123",
       "action": "receipt_uploaded",
       "duration_ms": 245,
       "status": "success",
       "metadata": { "receipt_id": "receipt-456", "size_bytes": 102400 }
     }
     ```
   - [ ] All logs include:
     - [ ] `timestamp` (ISO 8601)
     - [ ] `level` (DEBUG, INFO, WARN, ERROR, FATAL)
     - [ ] `service` (backend, frontend, ocr-worker, etc.)
     - [ ] `request_id` (for distributed tracing)
     - [ ] `user_id` (if applicable, for user-level debugging)
     - [ ] `action` (what happened)
     - [ ] `duration_ms` (for performance tracking)
     - [ ] `status` (success, failure, partial)
     - [ ] `metadata` (additional context)
   - [ ] Secrets are redacted from logs (passwords, API keys, tokens)

3. **Metrics & CloudWatch Dashboards**
   - [ ] Custom metrics published:
     - [ ] **API Metrics:**
       - [ ] `receipt_uploads_total` (counter, cumulative)
       - [ ] `receipt_processing_duration_ms` (histogram, p50/p95/p99)
       - [ ] `api_request_duration_ms` (histogram, per endpoint)
       - [ ] `api_errors_total` (counter, by error type)
       - [ ] `api_requests_active` (gauge, current in-flight requests)
     - [ ] **Business Metrics:**
       - [ ] `expenses_created_total` (counter)
       - [ ] `settlements_calculated_total` (counter)
       - [ ] `payments_sent_total` (counter)
       - [ ] `sms_reminders_sent_total` (counter)
       - [ ] `sms_delivery_failures_total` (counter)
     - [ ] **Infrastructure Metrics:**
       - [ ] `ecs_task_cpu_percent` (gauge)
       - [ ] `ecs_task_memory_percent` (gauge)
       - [ ] `rds_cpu_percent` (gauge)
       - [ ] `rds_connections_active` (gauge)
       - [ ] `rds_query_duration_ms` (histogram)
   - [ ] Metrics are published every 60 seconds
   - [ ] Metrics include dimensions (e.g., `service=backend`, `environment=prod`)

4. **CloudWatch Dashboards**
   - [ ] Production dashboard:
     - [ ] API latency (p50, p95, p99)
     - [ ] Error rate (total requests, error count, error %)
     - [ ] Active requests (current in-flight)
     - [ ] Receipt processing time (p95)
     - [ ] Database connections (active, max)
     - [ ] ECS task CPU and memory
     - [ ] SMS delivery success rate
     - [ ] Business metrics (expenses, settlements, payments)
   - [ ] Staging dashboard (same metrics as production)
   - [ ] On-call dashboard (alerts, recent incidents, deployment status)
   - [ ] Business metrics dashboard (for product team)

5. **Distributed Tracing (Request IDs)**
   - [ ] Request ID generated at API gateway:
     ```javascript
     const requestId = req.headers['x-request-id'] || generateUUID();
     req.requestId = requestId;
     res.setHeader('x-request-id', requestId);
     ```
   - [ ] Request ID propagated through all service calls:
     - [ ] Logged in every service
     - [ ] Included in database audit trail
     - [ ] Included in external API calls (OCR, SMS)
   - [ ] Request ID enables end-to-end tracing:
     - [ ] User uploads receipt → backend processes → OCR called → result stored
     - [ ] All steps linked by same request ID

6. **Alerting & Thresholds**
   - [ ] CloudWatch alarms created for SLO violations:
     - [ ] **API Availability:** Error rate >5% for 5 minutes → P1 alert
     - [ ] **API Latency:** p95 latency >500ms for 10 minutes → P2 alert
     - [ ] **Receipt Processing:** p95 processing time >5 seconds for 10 minutes → P2 alert
     - [ ] **Database Health:** Connection count >80% of max for 5 minutes → P1 alert
     - [ ] **ECS Task Health:** CPU >90% for 10 minutes → P2 alert
     - [ ] **SMS Delivery:** Failure rate >2% for 15 minutes → P1 alert
   - [ ] Alarms trigger:
     - [ ] Slack notification to #incidents channel
     - [ ] PagerDuty alert for P1 incidents (page on-call engineer)
     - [ ] Email to team for P2 incidents
   - [ ] Alarm resolution notifications sent when issue is resolved

7. **CloudWatch Insights Queries**
   - [ ] Pre-built queries for common debugging scenarios:
     - [ ] "Show all errors for user X"
     - [ ] "Show all failed OCR requests"
     - [ ] "Show all SMS delivery failures"
     - [ ] "Show requests slower than 1 second"
     - [ ] "Show all database errors"
   - [ ] Queries are documented and shared with team

8. **Log Aggregation & Search**
   - [ ] CloudWatch Insights enables searching across all logs
   - [ ] Queries support filtering by:
     - [ ] Service, environment, request_id, user_id, action, status
     - [ ] Time range, log level, metadata fields
   - [ ] Query results are exportable (CSV, JSON)

9. **Testing & Validation**
   - [ ] Logs are generated and visible in CloudWatch
   - [ ] Metrics are published and visible in CloudWatch
   - [ ] Dashboards display correct data
   - [ ] Alarms trigger when thresholds are breached
   - [ ] Slack notifications are sent
   - [ ] PagerDuty alerts are created

10. **Documentation**
    - [ ] `MONITORING.md` created with:
      - [ ] Dashboard overview
      - [ ] Alert thresholds and meanings
      - [ ] How to query logs
      - [ ] How to debug common issues
    - [ ] Runbook: "How to respond to P1 alerts"
    - [ ] Runbook: "How to debug slow requests"

**Technical Notes:**
- [ASSUMPTION] AWS CloudWatch is the monitoring platform (AWS native, cost-effective)
- [ASSUMPTION] Structured JSON logging is used (enables powerful queries)
- [ASSUMPTION] Request IDs are used for distributed tracing
- Metrics are published using AWS SDK or CloudWatch agent
- Alarms integrate with PagerDuty for on-call notifications

**Risks & Mitigations:**
- **Risk:** Monitoring overhead slows down application
  - **Mitigation:** Async logging, batch metric publishing, sampling for high-volume events
- **Risk:** Alert fatigue from false positives
  - **Mitigation:** Carefully tuned thresholds, tested in staging, gradual rollout
- **Risk:** Logs are too verbose; hard to find issues
  - **Mitigation:** Structured logging with consistent fields, CloudWatch Insights queries

**Definition of Done:**
- Log groups and streams created
- Structured logging implemented in backend
- Metrics published to CloudWatch
- Dashboards created and tested
- Alarms configured and tested
- Slack/PagerDuty integration working
- Documentation complete

---

### TASK 2.8: Alerting & On-Call Setup (PagerDuty Integration)

**Task ID:** SPLIT-INFRA-008  
**Epic:** Cross-Epic (Infrastructure) + Epic 9 (Operations)  
**Task Type:** DevOps  
**Effort:** 8 hours (1 day)  
**Complexity:** Medium  
**Risk Level:** Low  
**Priority:** P0  
**Sprint:** Sprint 0  
**Assigned To:** DevOps/Platform Engineer  
**Dependencies:** SPLIT-INFRA-007 (CloudWatch monitoring set up)  
**Blocks:** Production deployment (need alerting before going live)  

**Objective:**
Integrate CloudWatch alarms with PagerDuty to enable on-call incident management, escalation, and tracking. Ensure critical incidents page engineers immediately while non-critical issues are handled asynchronously.

**Acceptance Criteria:**

1. **PagerDuty Account & Setup**
   - [ ] PagerDuty account created (or integrated with existing)
   - [ ] Service created for SplitPay
   - [ ] Escalation policy created:
     - [ ] Level 1: On-call engineer (5-minute timeout)
     - [ ] Level 2: Tech lead (10-minute timeout)
     - [ ] Level 3: Engineering manager (15-minute timeout)
   - [ ] On-call schedule created (weekly rotation, Monday-Friday)
   - [ ] Team members added to schedule

2. **Incident Severity Levels**
   - [ ] P1 (Critical, page immediately):
     - [ ] API availability <95% (error rate >5%)
     - [ ] Database unavailable or connection pool exhausted
     - [ ] SMS delivery failure rate >5%
     - [ ] Data corruption or loss detected
   - [ ] P2 (High, create incident but don't page):
     - [ ] API latency p95 >500ms
     - [ ] Receipt processing latency p95 >5 seconds
     - [ ] ECS task CPU >90% for sustained period
     - [ ] Any error rate >2% but <5%
   - [ ] P3 (Low, log but don't create incident):
     - [ ] API latency p95 >200ms
     - [ ] Non-critical service degradation
     - [ ] Warnings or info-level issues

3. **CloudWatch to PagerDuty Integration**
   - [ ] SNS topic created for P1 alerts: `splitpay-alerts-p1`
   - [ ] SNS topic created for P2 alerts: `splitpay-alerts-p2`
   - [ ] CloudWatch alarms publish to SNS topics
   - [ ] SNS topics are subscribed to PagerDuty:
     - [ ] P1 topic → PagerDuty (trigger immediately)
     - [ ] P2 topic → PagerDuty (create incident, don't page)
   - [ ] PagerDuty webhook configured to post incident summaries to Slack

4. **Incident Management**
   - [ ] When P1 alert triggers:
     - [ ] PagerDuty pages on-call engineer
     - [ ] Slack notification posted to #incidents
     - [ ] Incident page created in PagerDuty with context
     - [ ] Engineer acknowledges incident (stops paging)
     - [ ] Engineer resolves incident (closes in PagerDuty)
   - [ ] When P2 alert triggers:
     - [ ] Incident created in PagerDuty (no page)
     - [ ] Slack notification posted to #incidents
     - [ ] Team reviews during business hours
   - [ ] Incident post-mortem process:
     - [ ] P1 incidents: post-mortem within 24 hours
     - [ ] P2 incidents: post-mortem within 1 week
     - [ ] Post-mortem template: what happened, why, how to prevent

5. **On-Call Rotation**
   - [ ] Weekly schedule:
     - [ ] Monday-Friday: primary on-call engineer
     - [ ] Weekend: secondary on-call (if applicable)
   - [ ] Schedule is published and accessible to team
   - [ ] Handoff process:
     - [ ] Outgoing engineer briefs incoming engineer on current issues
     - [ ] PagerDuty schedule is updated
   - [ ] Escalation policy ensures coverage if primary is unavailable

6. **Testing & Validation**
   - [ ] Test alert triggered (CloudWatch alarm)
   - [ ] SNS notification received
   - [ ] PagerDuty incident created
   - [ ] Slack notification posted
   - [ ] On-call engineer receives page (if P1)
   - [ ] Incident can be acknowledged and resolved

7. **Documentation**
   - [ ] `ON_CALL.md` created with:
     - [ ] How to acknowledge an incident
     - [ ] How to resolve an incident
     - [ ] Escalation policy and process
     - [ ] Post-mortem template and process
     - [ ] On-call rotation schedule
     - [ ] Contact info for escalation

**Technical Notes:**
- [ASSUMPTION] PagerDuty is used for on-call management (industry standard)
- [ASSUMPTION] Slack is used for team notifications
- Incidents are tracked in PagerDuty for metrics (MTTR, incident frequency)
- Post-mortems are conducted for all P1 incidents to prevent recurrence

**Risks & Mitigations:**
- **Risk:** On-call engineer is overwhelmed by false alarms
  - **Mitigation:** Careful alert tuning, testing in staging, gradual rollout
- **Risk:** On-call engineer is unreachable
  - **Mitigation:** Escalation policy ensures coverage, SMS fallback, on-call status check

**Definition of Done:**
- PagerDuty account set up with escalation policy
- CloudWatch to PagerDuty integration working
- Test incident triggered and verified
- On-call schedule created
- Documentation complete

---

### TASK 2.9: Logging Configuration & Log Redaction

**Task ID:** SPLIT-INFRA-009  
**Epic:** Cross-Epic (Infrastructure) + Epic 10 (Security)  
**Task