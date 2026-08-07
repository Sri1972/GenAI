# SOLUTION_DESIGN.md

**SplitPay: Complete Solution Design Document**

**Version:** 1.0  
**Date:** [Current Date]  
**Author:** Senior DevOps/Platform Engineer  
**Status:** Ready for Engineering Review & Implementation  

**Document Purpose:** This comprehensive Solution Design Document translates the PRD and TRD into a production-ready CI/CD pipeline, infrastructure architecture, monitoring strategy, deployment topology, security hardening, and operational excellence framework. It defines the complete platform infrastructure, deployment automation, observability, and reliability characteristics that enable SplitPay to ship reliably, scale safely, and operate with confidence. This document is the authoritative source of truth for DevOps, platform engineering, SRE, backend/frontend teams, QA, and product stakeholders regarding infrastructure, deployment, and operational readiness.

---

## TABLE OF CONTENTS

1. [Executive Summary: DevOps & Platform Strategy](#1-executive-summary-devops--platform-strategy)
2. [CI/CD Pipeline Architecture](#2-cicd-pipeline-architecture)
3. [Infrastructure as Code & Environment Management](#3-infrastructure-as-code--environment-management)
4. [Deployment Strategy & Release Management](#4-deployment-strategy--release-management)
5. [Monitoring, Observability & Alerting](#5-monitoring-observability--alerting)
6. [Security Hardening & Compliance](#6-security-hardening--compliance)
7. [Disaster Recovery & Business Continuity](#7-disaster-recovery--business-continuity)
8. [Cost Optimization & Resource Management](#8-cost-optimization--resource-management)
9. [Operational Runbooks & Incident Response](#9-operational-runbooks--incident-response)
10. [Performance Benchmarks & Scaling Strategy](#10-performance-benchmarks--scaling-strategy)
11. [Data Pipeline & Audit Trail Infrastructure](#11-data-pipeline--audit-trail-infrastructure)
12. [Third-Party Integration Management](#12-third-party-integration-management)
13. [Testing Strategy & Quality Gates](#13-testing-strategy--quality-gates)
14. [Assumptions, Constraints & Trade-offs](#14-assumptions-constraints--trade-offs)

---

## 1. EXECUTIVE SUMMARY: DEVOPS & PLATFORM STRATEGY

### 1.1 Mission Statement

**SplitPay DevOps ensures software gets from developer laptop to production reliably, securely, and observably.** We design and operate the infrastructure, CI/CD pipelines, monitoring systems, and deployment strategies that enable the product team to ship features confidently, respond to incidents swiftly, and scale to millions of users without operational chaos.

### 1.2 Core Principles

1. **Automate Everything Repeatable:** If a task is done more than twice, it's automated. Manual deployments, environment provisioning, and testing are eliminated in favor of code-driven, auditable automation.

2. **Fast Feedback Loops:** Developers receive build/test results in <10 minutes. Deployment failures produce actionable error messages, not cryptic logs. Observability is built-in before features ship.

3. **Reversible Deployments:** Every production deployment is reversible within 5 minutes. Blue/green or canary strategies enable safe rollbacks. No "we can't roll this back" scenarios.

4. **Blast Radius Containment:** Failures are isolated. A database migration failure doesn't take down the entire platform. A third-party API outage doesn't break core functionality.

5. **Actionable Alerts Only:** Alerts wake engineers only when action is required. If nobody needs to do anything, it's not an alert. Alert fatigue is eliminated through intelligent thresholds and context.

6. **Immutable Infrastructure:** Servers are never manually modified. All changes flow through code, CI/CD, and version control. "Works on my machine" is impossible.

7. **Secrets Management:** Secrets are never stored in code, config files, or environment variables in source control. All secrets are managed via secure vaults with audit trails.

8. **Environment Parity:** Dev, staging, and production environments are reproducible from code. Configuration drift is impossible. Staging is production-grade and exercises all deployment paths.

### 1.3 Key Success Metrics (SLIs/SLOs)

| **SLI (Service Level Indicator)** | **SLO (Service Level Objective)** | **Rationale** |
|---|---|---|
| API availability (successful HTTP responses) | 99.9% (9 nines = ~8.6s downtime/day) | Core financial transactions cannot tolerate frequent outages |
| API latency (p95 response time) | <500ms (receipt processing), <200ms (queries) | Mobile users expect snappy UX; OCR may add latency |
| Receipt processing time (OCR + calculation) | <5 seconds (p99) | Users expect immediate feedback after receipt upload |
| Payment reminder delivery (SMS/push) | 99% within 5 minutes of trigger | Reminders must reach users reliably and promptly |
| Data consistency (audit trail completeness) | 100% (zero financial transactions lost) | Every dollar owed must be auditable |
| Deployment success rate | 99.5% (max 1 failed deployment per 200 attempts) | Deployments must be safe and reliable |
| Mean time to recovery (MTTR) | <15 minutes for P1 incidents | Platform must recover quickly from failures |
| Mean time to detection (MTTD) | <5 minutes for P1 incidents | Monitoring must catch problems before customers notice |

### 1.4 Deployment Cadence & Release Strategy

- **Feature deployments:** Multiple times per day (continuous deployment to staging; controlled rollout to production)
- **Hotfixes:** Within 30 minutes of approval (via expedited CI/CD lane)
- **Database migrations:** Coordinated with feature deployments; backward-compatible; tested in staging first
- **Third-party integrations:** Canary deployment with circuit breakers (e.g., 5% of traffic to new OCR provider)
- **Infrastructure changes:** Terraform-driven; peer-reviewed; tested in staging; blue/green rollout to production

### 1.5 Target Environments

| **Environment** | **Purpose** | **Deployment Frequency** | **Data** | **Scale** |
|---|---|---|---|---|
| **Local Development** | Developer laptops; offline-first; local DB | Continuous (developer-driven) | Synthetic test data | 1 developer |
| **Staging (Pre-Prod)** | Integration testing, load testing, UAT | Every commit to `main` branch | Sanitized production-like data | 1/10th of prod capacity |
| **Production** | Live traffic; real users; real money | Controlled rollout (blue/green or canary) | Real user data (encrypted) | Auto-scaling (see §10) |
| **Disaster Recovery / DR Site** | Failover target; tested quarterly | Data replication (continuous) | Real user data (encrypted) | Standby capacity |

---

## 2. CI/CD PIPELINE ARCHITECTURE

### 2.1 Pipeline Overview

```
Developer Push to Git
    │
    ├─→ [STAGE 1: Code Quality & Security] (parallel)
    │   ├─ Lint (ESLint, Prettier)
    │   ├─ SAST (SonarQube, Snyk)
    │   ├─ Dependency scanning (npm audit, Snyk)
    │   └─ Secret scanning (Gitleaks, TruffleHog)
    │   └─ ⏱ Target: <3 minutes
    │
    ├─→ [STAGE 2: Build & Unit Tests] (parallel)
    │   ├─ Backend: Build Node.js, run unit tests
    │   ├─ Frontend: Build React Native Web, run unit tests
    │   ├─ Database: Validate schema migrations
    │   └─ ⏱ Target: <5 minutes
    │
    ├─→ [STAGE 3: Container Builds & Registry Push]
    │   ├─ Build backend Docker image (tag: git-sha)
    │   ├─ Build frontend Docker image (tag: git-sha)
    │   ├─ Scan images for vulnerabilities (Trivy, Aqua)
    │   ├─ Push to container registry (ECR / Docker Hub)
    │   └─ ⏱ Target: <5 minutes
    │
    ├─→ [STAGE 4: Deploy to Staging]
    │   ├─ Run database migrations (backward-compatible)
    │   ├─ Deploy backend services (rolling deployment)
    │   ├─ Deploy frontend (static hosting)
    │   ├─ Run smoke tests (health checks, critical API calls)
    │   └─ ⏱ Target: <10 minutes
    │
    ├─→ [STAGE 5: Integration & Functional Tests]
    │   ├─ API contract tests (Pact)
    │   ├─ End-to-end tests (Playwright: receipt upload → settlement calculation)
    │   ├─ Load tests (k6: 100 concurrent users, receipt uploads)
    │   ├─ Security tests (OWASP ZAP, dependency checks)
    │   └─ ⏱ Target: <15 minutes
    │
    ├─→ [STAGE 6: Manual Approval Gate]
    │   ├─ Product owner / tech lead review (automated checks + manual sign-off)
    │   ├─ Review staging deployment logs
    │   └─ ⏱ Typical: 15-60 minutes (async)
    │
    └─→ [STAGE 7: Deploy to Production]
        ├─ Blue/green or canary deployment
        ├─ Health checks & smoke tests
        ├─ Monitor error rates, latency, resource usage for 10 minutes
        ├─ Auto-rollback if error rate > 5% or latency > 1000ms (p95)
        └─ ⏱ Target: <10 minutes (including monitoring window)
```

### 2.2 Quality Gates (Must Pass to Proceed)

| **Gate** | **Criteria** | **Failure Action** | **Owner** |
|---|---|---|---|
| **Lint & Format** | Zero lint errors; code formatted per Prettier | Block merge | Automated (pre-commit hook) |
| **SAST** | No critical/high severity findings; approved low/medium findings | Block merge | Automated (SonarQube) |
| **Secret Scan** | Zero secrets detected in code | Block merge | Automated (Gitleaks) |
| **Unit Tests** | ≥80% code coverage; all tests pass | Block merge | Automated (Jest) |
| **Container Scan** | Zero critical vulnerabilities; approved high vulnerabilities | Block production deployment | Automated (Trivy) |
| **Smoke Tests (Staging)** | All health checks pass; critical APIs respond | Block production deployment | Automated |
| **Load Tests (Staging)** | p95 latency <1000ms at 100 concurrent users | Block production deployment | Automated (k6) |
| **Manual Approval** | Product owner / tech lead sign-off | Block production deployment | Human review |
| **Production Health** | Error rate <5%, latency p95 <500ms for 10 minutes post-deploy | Auto-rollback if violated | Automated monitoring |

### 2.3 CI/CD Technology Stack

| **Component** | **Technology** | **Rationale** |
|---|---|---|
| **Git Repository** | GitHub (or GitLab) | Standard VCS; integrates with CI/CD platforms; audit trail |
| **CI/CD Orchestration** | GitHub Actions (or GitLab CI, Jenkins) | [ASSUMPTION] GitHub Actions for simplicity; native GitHub integration |
| **Container Registry** | Amazon ECR or Docker Hub | [ASSUMPTION] ECR for AWS deployments; Docker Hub for multi-cloud |
| **Artifact Storage** | S3 (build logs, test reports) | Immutable artifact history; audit trail |
| **Code Quality** | SonarQube (self-hosted or SaaS) | SAST, code coverage, technical debt tracking |
| **Dependency Scanning** | Snyk (SaaS) | npm audit, container image scanning, license compliance |
| **Secret Scanning** | Gitleaks (open-source) | Prevents secrets in git history |
| **Load Testing** | k6 (open-source) | Scriptable, cloud-native load testing |
| **E2E Testing** | Playwright (open-source) | Cross-browser, cross-platform UI testing |
| **Container Scanning** | Trivy (open-source) | Fast, accurate vulnerability scanning |
| **Deployment Orchestration** | Kubernetes (EKS) or Docker Swarm | [ASSUMPTION] Kubernetes for production; see §3 |

### 2.4 Pipeline Configuration (GitHub Actions Example)

```yaml
name: SplitPay CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

env:
  AWS_REGION: us-east-1
  ECR_REGISTRY_BACKEND: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com/splitpay-backend
  ECR_REGISTRY_FRONTEND: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com/splitpay-frontend
  REGISTRY_IMAGE_TAG: ${{ github.sha }}

jobs:
  # STAGE 1: Code Quality & Security
  code-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history for SonarQube analysis
      
      - name: Run ESLint
        run: npm run lint
      
      - name: Run Prettier (check formatting)
        run: npm run format:check
      
      - name: SonarQube Scan
        uses: SonarSource/sonarcloud-github-action@master
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
      
      - name: Secret Scan (Gitleaks)
        uses: gitleaks/gitleaks-action@v2
      
      - name: Dependency Audit
        run: npm audit --audit-level=moderate
      
      - name: Upload quality reports to S3
        if: always()
        run: |
          aws s3 cp sonar-report.json s3://${{ secrets.ARTIFACT_BUCKET }}/ci-reports/${{ github.run_id }}/
          aws s3 cp coverage/ s3://${{ secrets.ARTIFACT_BUCKET }}/ci-reports/${{ github.run_id }}/coverage/ --recursive

  # STAGE 2: Build & Unit Tests
  build-and-test:
    runs-on: ubuntu-latest
    needs: code-quality
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Build backend
        run: npm run build:backend
      
      - name: Build frontend
        run: npm run build:frontend
      
      - name: Run unit tests
        run: npm run test:unit
      
      - name: Generate coverage report
        run: npm run test:coverage
      
      - name: Validate database migrations
        run: npm run db:validate-migrations
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: coverage/

  # STAGE 3: Container Builds & Registry Push
  build-containers:
    runs-on: ubuntu-latest
    needs: build-and-test
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build and push backend image
        uses: docker/build-push-action@v4
        with:
          context: ./backend
          push: true
          tags: |
            ${{ env.ECR_REGISTRY_BACKEND }}:${{ env.REGISTRY_IMAGE_TAG }}
            ${{ env.ECR_REGISTRY_BACKEND }}:latest
          cache-from: type=registry,ref=${{ env.ECR_REGISTRY_BACKEND }}:buildcache
          cache-to: type=registry,ref=${{ env.ECR_REGISTRY_BACKEND }}:buildcache,mode=max
      
      - name: Build and push frontend image
        uses: docker/build-push-action@v4
        with:
          context: ./frontend
          push: true
          tags: |
            ${{ env.ECR_REGISTRY_FRONTEND }}:${{ env.REGISTRY_IMAGE_TAG }}
            ${{ env.ECR_REGISTRY_FRONTEND }}:latest
          cache-from: type=registry,ref=${{ env.ECR_REGISTRY_FRONTEND }}:buildcache
          cache-to: type=registry,ref=${{ env.ECR_REGISTRY_FRONTEND }}:buildcache,mode=max
      
      - name: Scan backend image for vulnerabilities
        run: |
          trivy image --exit-code 0 --severity CRITICAL,HIGH \
            ${{ env.ECR_REGISTRY_BACKEND }}:${{ env.REGISTRY_IMAGE_TAG }}
      
      - name: Scan frontend image for vulnerabilities
        run: |
          trivy image --exit-code 0 --severity CRITICAL,HIGH \
            ${{ env.ECR_REGISTRY_FRONTEND }}:${{ env.REGISTRY_IMAGE_TAG }}

  # STAGE 4: Deploy to Staging
  deploy-staging:
    runs-on: ubuntu-latest
    needs: build-containers
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop'
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Update kubeconfig
        run: |
          aws eks update-kubeconfig --region ${{ env.AWS_REGION }} \
            --name splitpay-staging-eks
      
      - name: Run database migrations
        run: |
          kubectl set env deployment/splitpay-backend-migration \
            IMAGE_TAG=${{ env.REGISTRY_IMAGE_TAG }} \
            -n staging --record
          kubectl wait --for=condition=complete job/db-migration \
            -n staging --timeout=5m
      
      - name: Deploy backend to staging
        run: |
          kubectl set image deployment/splitpay-backend \
            splitpay-backend=${{ env.ECR_REGISTRY_BACKEND }}:${{ env.REGISTRY_IMAGE_TAG }} \
            -n staging --record
          kubectl rollout status deployment/splitpay-backend -n staging --timeout=5m
      
      - name: Deploy frontend to staging
        run: |
          kubectl set image deployment/splitpay-frontend \
            splitpay-frontend=${{ env.ECR_REGISTRY_FRONTEND }}:${{ env.REGISTRY_IMAGE_TAG }} \
            -n staging --record
          kubectl rollout status deployment/splitpay-frontend -n staging --timeout=5m
      
      - name: Run smoke tests
        run: |
          npm run test:smoke:staging
      
      - name: Notify deployment success
        if: success()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '✅ Deployed to staging: ${{ env.REGISTRY_IMAGE_TAG }}'
            })

  # STAGE 5: Integration & Functional Tests
  integration-tests:
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.ref == 'refs/heads/main' || github.ref == 'refs/heads/develop'
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run API contract tests
        run: npm run test:contract
      
      - name: Run E2E tests (Playwright)
        run: npm run test:e2e:staging
        env:
          STAGING_BASE_URL: https://staging.splitpay.dev
      
      - name: Run load tests (k6)
        run: npm run test:load:staging
        env:
          STAGING_BASE_URL: https://staging.splitpay.dev
      
      - name: Run security tests (OWASP ZAP)
        run: npm run test:security:staging
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: integration-test-results
          path: test-results/

  # STAGE 6: Manual Approval Gate (only on main branch)
  approval-gate:
    runs-on: ubuntu-latest
    needs: integration-tests
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Create deployment approval issue
        uses: actions/github-script@v6
        with:
          script: |
            const issue = await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: `Production deployment approval: ${{ github.sha }}`,
              body: `
                **Commit:** ${{ github.sha }}
                **Branch:** ${{ github.ref }}
                **Author:** ${{ github.actor }}
                
                All CI/CD quality gates passed. Awaiting manual approval for production deployment.
                
                - [ ] Code review approved
                - [ ] Staging tests passed
                - [ ] Ready for production
                
                React with 👍 to approve or 👎 to reject.
              `,
              labels: ['deployment', 'approval-required']
            });
            
            core.setOutput('approval_issue_id', issue.data.number);

  # STAGE 7: Deploy to Production (only after approval)
  deploy-production:
    runs-on: ubuntu-latest
    needs: approval-gate
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://splitpay.app
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}
      
      - name: Update kubeconfig (production)
        run: |
          aws eks update-kubeconfig --region ${{ env.AWS_REGION }} \
            --name splitpay-production-eks
      
      - name: Deploy via blue/green strategy
        run: |
          # Deploy to "green" environment
          kubectl set image deployment/splitpay-backend-green \
            splitpay-backend=${{ env.ECR_REGISTRY_BACKEND }}:${{ env.REGISTRY_IMAGE_TAG }} \
            -n production --record
          kubectl rollout status deployment/splitpay-backend-green -n production --timeout=5m
          
          # Run health checks on green
          kubectl run health-check --image=${{ env.ECR_REGISTRY_BACKEND }}:${{ env.REGISTRY_IMAGE_TAG }} \
            -n production -- npm run health-check:green
          
          # Switch traffic from blue to green
          kubectl patch service splitpay-backend -n production \
            -p '{"spec":{"selector":{"version":"green"}}}'
      
      - name: Monitor production metrics for 10 minutes
        run: |
          npm run monitor:production -- --duration=10m --fail-on-error-rate=5
      
      - name: Auto-rollback if metrics degrade
        if: failure()
        run: |
          echo "Metrics degradation detected. Rolling back to blue environment..."
          kubectl patch service splitpay-backend -n production \
            -p '{"spec":{"selector":{"version":"blue"}}}'
          exit 1
      
      - name: Promote green to blue for next deployment
        if: success()
        run: |
          kubectl patch deployment splitpay-backend-blue -n production \
            -p '{"spec":{"template":{"spec":{"containers":[{"name":"splitpay-backend","image":"${{ env.ECR_REGISTRY_BACKEND }}:${{ env.REGISTRY_IMAGE_TAG }}"}]}}}}'
      
      - name: Notify production deployment
        if: always()
        uses: actions/github-script@v6
        with:
          script: |
            const status = context.job.status === 'success' ? '✅' : '❌';
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `${status} Production deployment: ${{ env.REGISTRY_IMAGE_TAG }}`
            })
```

### 2.5 Pipeline Failure Handling

**Principle:** Failures must produce actionable error messages, not cryptic logs.

| **Failure Point** | **Root Cause Diagnosis** | **Remediation** | **Owner** |
|---|---|---|---|
| **Lint/SAST fails** | Code quality issue; automated fix or manual review | Auto-fix (Prettier, ESLint --fix) or block merge | Developer |
| **Unit tests fail** | Logic error; test flakiness; environment issue | Re-run (flakiness detection); fix logic; fix test environment | Developer |
| **Container build fails** | Dependency issue; Dockerfile error; base image unavailable | Check Dockerfile; audit dependencies; mirror base images | DevOps |
| **Staging deployment fails** | Kubernetes issue; resource constraints; config mismatch | Check pod logs; scale cluster; validate manifests | DevOps |
| **Smoke tests fail** | Health check failure; database connection issue; API error | Check pod logs; verify database; check configuration | DevOps / Backend |
| **Load tests fail** | Performance regression; resource bottleneck; third-party latency | Profile application; scale infrastructure; check third-party status | Backend / DevOps |
| **Production deployment fails** | Rollout issue; health check failure; metric degradation | Automatic rollback to previous version; investigate logs | DevOps / SRE |

### 2.6 Rollback Procedures

**Objective:** Reverse any production deployment within 5 minutes.

#### 2.6.1 Automatic Rollback

```bash
# Triggered automatically if:
# - Error rate > 5% for >2 minutes
# - Latency p95 > 1000ms for >2 minutes
# - Pod crash loops (restarts > 5 in 5 minutes)
# - Health check failures > 30% of instances

# Rollback action:
kubectl rollout undo deployment/splitpay-backend -n production
kubectl rollout status deployment/splitpay-backend -n production --timeout=5m
```

#### 2.6.2 Manual Rollback

```bash
# DevOps/SRE decision to rollback manually
kubectl rollout history deployment/splitpay-backend -n production
kubectl rollout undo deployment/splitpay-backend -n production --to-revision=<N>
kubectl rollout status deployment/splitpay-backend -n production --timeout=5m

# Verify rollback success
kubectl get pods -n production
kubectl logs -f deployment/splitpay-backend -n production
```

#### 2.6.3 Rollback Verification

```bash
# Run smoke tests against rolled-back version
npm run test:smoke:production

# Check metrics
# - Error rate < 1%
# - Latency p95 < 300ms
# - All pods healthy

# Notify team
# - Slack alert: "Rollback complete. Version X restored."
# - Create incident post-mortem issue
```

---

## 3. INFRASTRUCTURE AS CODE & ENVIRONMENT MANAGEMENT

### 3.1 Infrastructure Philosophy

**Immutable Infrastructure Principle:** All infrastructure is defined in code (Terraform), versioned in Git, peer-reviewed, and deployed via automated pipelines. Servers are never manually modified. Configuration drift is impossible.

**Environment Parity Principle:** Dev, staging, and production environments are reproducible from code. Staging is production-grade (same instance types, same database, same networking). If it works in staging, it works in production.

### 3.2 Infrastructure Stack

| **Component** | **Technology** | **Rationale** | **Tracing to Context** |
|---|---|---|---|
| **Cloud Provider** | Amazon AWS (or multi-cloud capable) | [ASSUMPTION] AWS for scalability, managed services, global infrastructure | Common choice for Node.js/PostgreSQL startups |
| **Compute** | Kubernetes (EKS) | Container orchestration; auto-scaling; declarative deployments | Supports microservices architecture (Auth, Expense, Notification services) |
| **Database** | Amazon RDS PostgreSQL | Managed relational database; automated backups; high availability | Per TRD: PostgreSQL requirement |
| **Cache** | Amazon ElastiCache Redis | Session storage, OCR result caching, rate limiting | Reduces database load; speeds up OCR cache lookups |
| **Object Storage** | Amazon S3 | Receipt images, build artifacts, logs, backups | Durable, scalable, cost-effective |
| **CDN** | Amazon CloudFront | Distribute frontend (React Native Web) globally; cache static assets | Reduces latency for mobile users globally |
| **DNS** | Amazon Route 53 | Domain management, health checks, failover routing | Enables multi-region failover |
| **Secrets Management** | AWS Secrets Manager | Store API keys, database passwords, encryption keys | Audit trail; automatic rotation; fine-grained access control |
| **Monitoring & Logging** | Amazon CloudWatch + ELK Stack (Elasticsearch, Logstash, Kibana) | Centralized logging, metrics, dashboards, alerting | See §5 for details |
| **Infrastructure as Code** | Terraform | Define all infrastructure in code; version control; peer review | Reproducible, auditable infrastructure |

### 3.3 Terraform Directory Structure

```
terraform/
├── main.tf                      # Root module; orchestrates all services
├── variables.tf                 # Input variables (region, environment, instance types, etc.)
├── outputs.tf                   # Output values (API endpoints, database hosts, etc.)
├── terraform.tfvars             # Variable values (per environment)
├── terraform.tfvars.prod        # Production-specific overrides
├── terraform.tfvars.staging     # Staging-specific overrides
│
├── modules/
│   ├── networking/              # VPC, subnets, security groups, NAT gateways
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── security_groups.tf
│   │
│   ├── eks/                     # Kubernetes cluster, node groups, RBAC
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── node_groups.tf
│   │   └── rbac.tf
│   │
│   ├── rds/                     # PostgreSQL database, parameter groups, backups
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── parameter_groups.tf
│   │
│   ├── elasticache/             # Redis cluster for caching and sessions
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── s3/                      # S3 buckets (receipts, logs, artifacts)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── lifecycle_policies.tf
│   │
│   ├── cloudfront/              # CDN for frontend distribution
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   ├── secrets/                 # AWS Secrets Manager
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   │
│   └── monitoring/              # CloudWatch dashboards, alarms, log groups
│       ├── main.tf
│       ├── variables.tf
│       ├── dashboards.tf
│       └── alarms.tf
│
├── environments/
│   ├── dev.tfvars               # Development environment
│   ├── staging.tfvars           # Staging environment
│   └── prod.tfvars              # Production environment
│
└── scripts/
    ├── plan.sh                  # Run terraform plan
    ├── apply.sh                 # Run terraform apply with safeguards
    ├── destroy.sh               # Destroy infrastructure (staging only)
    └── validate.sh              # Validate Terraform configuration
```

### 3.4 Key Terraform Modules

#### 3.4.1 Networking Module

```hcl
# modules/networking/main.tf

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.environment}-vpc"
  }
}

resource "aws_subnet" "public" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.environment}-public-subnet-${count.index + 1}"
  }
}

resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  tags = {
    Name = "${var.environment}-private-subnet-${count.index + 1}"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.environment}-igw"
  }
}

resource "aws_nat_gateway" "main" {
  count         = length(var.availability_zones)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  tags = {
    Name = "${var.environment}-nat-${count.index + 1}"
  }

  depends_on = [aws_internet_gateway.main]
}

resource "aws_security_group" "backend" {
  name        = "${var.environment}-backend-sg"
  description = "Security group for backend services"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-backend-sg"
  }
}

# [Additional security groups for database, cache, load balancer...]
```

#### 3.4.2 EKS Cluster Module

```hcl
# modules/eks/main.tf

resource "aws_eks_cluster" "main" {
  name     = "${var.environment}-eks"
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version

  vpc_config {
    subnet_ids              = concat(var.public_subnet_ids, var.private_subnet_ids)
    security_group_ids      = [var.cluster_security_group_id]
    endpoint_private_access = true
    endpoint_public_access  = true
  }

  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  tags = {
    Name = "${var.environment}-eks"
  }

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy
  ]
}

resource "aws_eks_node_group" "backend" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${var.environment}-backend-ng"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids

  scaling_config {
    desired_size = var.backend_desired_size
    max_size     = var.backend_max_size
    min_size     = var.backend_min_size
  }

  instance_types = [var.backend_instance_type]

  tags = {
    Name = "${var.environment}-backend-ng"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_policy
  ]
}

# [Additional node groups for frontend, system pods...]

# Install Kubernetes metrics server for HPA
resource "helm_release" "metrics_server" {
  name       = "metrics-server"
  repository = "https://kubernetes-sigs.github.io/metrics-server/charts"
  chart      = "metrics-server"
  namespace  = "kube-system"

  set {
    name  = "args[0]"
    value = "--kubelet-insecure-tls"
  }
}

# Install cluster autoscaler
resource "helm_release" "cluster_autoscaler" {
  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  namespace  = "kube-system"

  set {
    name  = "autoDiscovery.clusterName"
    value = aws_eks_cluster.main.name
  }
}
```

#### 3.4.3 RDS PostgreSQL Module

```hcl
# modules/rds/main.tf

resource "aws_rds_cluster" "main" {
  cluster_identifier              = "${var.environment}-postgres"
  engine                          = "aurora-postgresql"
  engine_version                  = var.postgres_version
  database_name                   = var.database_name
  master_username                 = "postgres"
  master_password                 = random_password.db_password.result
  db_subnet_group_name            = aws_db_subnet_group.main.name
  vpc_security_group_ids          = [var.db_security_group_id]
  backup_retention_period         = var.backup_retention_days
  preferred_backup_window         = "03:00-04:00"
  preferred_maintenance_window    = "mon:04:00-mon:05:00"
  enabled_cloudwatch_logs_exports = ["postgresql"]
  storage_encrypted               = true
  kms_key_id                      = aws_kms_key.rds.arn
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.environment}-postgres-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  deletion_protection             = var.environment == "prod" ? true : false

  tags = {
    Name = "${var.environment}-postgres"
  }
}

resource "aws_rds_cluster_instance" "main" {
  count              = var.instance_count
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  performance_insights_enabled    = true
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn
  auto_minor_version_upgrade      = true
  publicly_accessible             = false

  tags = {
    Name = "${var.environment}-postgres-instance-${count.index + 1}"
  }
}

# Store database password in Secrets Manager
resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${var.environment}/rds/postgres/password"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}

# [Additional configuration for parameter groups, backups, monitoring...]
```

#### 3.4.4 Secrets Manager Module

```hcl
# modules/secrets/main.tf

resource "aws_secretsmanager_secret" "ocr_api_key" {
  name                    = "${var.environment}/ocr/api_key"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "ocr_api_key" {
  secret_id     = aws_secretsmanager_secret.ocr_api_key.id
  secret_string = var.ocr_api_key  # Injected via CI/CD secrets
}

resource "aws_secretsmanager_secret" "sms_api_key" {
  name                    = "${var.environment}/sms/api_key"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "sms_api_key" {
  secret_id     = aws_secretsmanager_secret.sms_api_key.id
  secret_string = var.sms_api_key
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name                    = "${var.environment}/jwt/secret"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id     = aws_secretsmanager_secret.jwt_secret.id
  secret_string = var.jwt_secret
}

# [Additional secrets for database credentials, encryption keys, etc...]

# IAM policy to allow services to read secrets
resource "aws_iam_policy" "read_secrets" {
  name        = "${var.environment}-read-secrets"
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
          aws_secretsmanager_secret.ocr_api_key.arn,
          aws_secretsmanager_secret.sms_api_key.arn,
          aws_secretsmanager_secret.jwt_secret.arn
        ]
      }
    ]
  })
}
```

### 3.5 Terraform Deployment Workflow

#### 3.5.1 Local Development

```bash
# Developer initializes Terraform
cd terraform/
terraform init -backend-config="key=dev.tfstate" -backend-config="bucket=$TERRAFORM_STATE_BUCKET"

# Developer plans changes
terraform plan -var-file="environments/dev.tfvars" -out=tfplan

# Developer applies changes (local only, no CI/CD)
terraform apply tfplan
```

#### 3.5.2 Staging Deployment (via CI/CD)

```bash
# CI/CD pipeline runs:
terraform init -backend-config="key=staging.tfstate" -backend-config="bucket=$TERRAFORM_STATE_BUCKET"
terraform plan -var-file="environments/staging.tfvars" -out=tfplan

# Plan is saved as artifact; human reviews before apply
# After approval:
terraform apply tfplan
```

#### 3.5.3 Production Deployment (via CI/CD with Safeguards)

```bash
# CI/CD pipeline runs:
terraform init -backend-config="key=prod.tfstate" -backend-config="bucket=$TERRAFORM_STATE_BUCKET"
terraform plan -var-file="environments/prod.tfvars" -out=tfplan

# Plan is reviewed by multiple people; requires explicit approval
# Safeguards:
# - No resource deletions without manual override
# - No database downsizing
# - No security group rule removals
# - Limited to non-breaking changes

terraform apply tfplan
```

### 3.6 Environment Configuration

#### 3.6.1 Development Environment

```hcl
# environments/dev.tfvars

environment                = "dev"
region                     = "us-east-1"
vpc_cidr                   = "10.0.0.0/16"
availability_zones         = ["us-east-1a", "us-east-1b"]
kubernetes_version         = "1.27"
backend_instance_type      = "t3.medium"
backend_desired_size       = 1
backend_max_size           = 3
backend_min_size           = 1
postgres_instance_class    = "db.t3.small"
postgres_instance_count    = 1
backup_retention_days      = 7
enable_enhanced_monitoring = false
```

#### 3.6.2 Staging Environment

```hcl
# environments/staging.tfvars

environment                = "staging"
region                     = "us-east-1"
vpc_cidr                   = "10.1.0.0/16"
availability_zones         = ["us-east-1a", "us-east-1b", "us-east-1c"]
kubernetes_version         = "1.27"
backend_instance_type      = "t3.large"
backend_desired_size       = 2
backend_max_size           = 6
backend_min_size           = 2
postgres_instance_class    = "db.t3.medium"
postgres_instance_count    = 2
backup_retention_days      = 30
enable_enhanced_monitoring = true
```

#### 3.6.3 Production Environment

```hcl
# environments/prod.tfvars

environment                = "prod"
region                     = "us-east-1"
vpc_cidr                   = "10.2.0.0/16"
availability_zones         = ["us-east-1a", "us-east-1b", "us-east-1c"]
kubernetes_version         = "1.27"
backend_instance_type      = "m5.xlarge"
backend_desired_size       = 3
backend_max_size           = 20
backend_min_size           = 3
postgres_instance_class    = "db.r5.large"
postgres_instance_count    = 3
backup_retention_days      = 90
enable_enhanced_monitoring = true
enable_multi_az            = true
```

### 3.7 State Management & Locking

```hcl
# terraform/main.tf - Backend configuration

terraform {
  backend "s3" {
    bucket         = "splitpay-terraform-state"
    key            = "terraform.tfstate"  # Overridden per environment
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}
```

**State Security:**
- Terraform state stored in S3 with server-side encryption (KMS)
- State files never checked into Git
- DynamoDB table prevents concurrent modifications (state locking)
- Access controlled via IAM policies (only DevOps team)
- State backups retained for 90 days

---

## 4. DEPLOYMENT STRATEGY & RELEASE MANAGEMENT

### 4.1 Deployment Models

#### 4.1.1 Blue/Green Deployment (Primary Strategy for Production)

**Objective:** Minimize downtime; enable instant rollback.

```
Before Deployment:
  Load Balancer → Blue (v1.0.0) [Active]
                → Green (v1.0.0) [Standby]

Deployment Process:
  1. Deploy v1.1.0 to Green environment
  2. Run health checks on Green
  3. Run smoke tests on Green
  4. Switch load balancer traffic: Blue → Green
  5. Monitor metrics for 10 minutes
  6. If healthy: Blue becomes standby; Green becomes active
  7. If unhealthy: Revert traffic to Blue (instant rollback)

After Deployment:
  Load Balancer → Green (v1.1.0) [Active]
                → Blue (v1.0.0) [Standby]

Next Deployment:
  1. Deploy v1.2.0 to Blue environment
  2. Switch traffic: Green → Blue
  3. [Repeat...]
```

**Kubernetes Implementation:**

```yaml
# Deployment: splitpay-backend-blue
apiVersion: apps/v1
kind: Deployment
metadata:
  name: splitpay-backend-blue
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: splitpay-backend
      version: blue
  template:
    metadata:
      labels:
        app: splitpay-backend
        version: blue
    spec:
      containers:
      - name: splitpay-backend
        image: <ECR_REGISTRY>/splitpay-backend:v1.0.0
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20

---

# Deployment: splitpay-backend-green
apiVersion: apps/v1
kind: Deployment
metadata:
  name: splitpay-backend-green
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: splitpay-backend
      version: green
  template:
    metadata:
      labels:
        app: splitpay-backend
        version: green
    spec:
      containers:
      - name: splitpay-backend
        image: <ECR_REGISTRY>/splitpay-backend:v1.1.0
        ports:
        - containerPort: 8080
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20

---

# Service: Routes traffic based on version label
apiVersion: v1
kind: Service
metadata:
  name: splitpay-backend
  namespace: production
spec:
  selector:
    app: splitpay-backend
    version: blue  # Currently routes to blue; switched to green during deployment
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: LoadBalancer
```

**Blue/Green Switch Script:**

```bash
#!/bin/bash
# scripts/blue-green-switch.sh

ENVIRONMENT=${1:-production}
TARGET_VERSION=${2:-green}

echo "Switching traffic to $TARGET_VERSION..."

# Update service selector
kubectl patch service splitpay-backend -n $ENVIRONMENT \
  -p "{\"spec\":{\"selector\":{\"version\":\"$TARGET_VERSION\"}}}"

echo "Traffic switched to $TARGET_VERSION"

# Verify traffic distribution
sleep 5
kubectl get endpoints splitpay-backend -n $ENVIRONMENT
```

#### 4.1.2 Canary Deployment (For Risky Changes)

**Objective:** Gradually roll out changes; detect issues early.

```
Canary Rollout Strategy:
  Phase 1 (5 min):  5% traffic to v1.1.0; 95% to v1.0.0
  Phase 2 (10 min): 25% traffic to v1.1.0; 75% to v1.0.0
  Phase 3 (15 min): 50% traffic to v1.1.0; 50% to v1.0.0
  Phase 4 (20 min): 100% traffic to v1.1.0

Abort Conditions:
  - Error rate > 2% (vs. baseline 0.5%)
  - Latency p95 > 2x baseline
  - Pod crash loops detected
  - Critical alerts triggered
```

**Kubernetes Implementation (Flagger + Istio):**

```yaml
apiVersion: flagger.app/v1beta1
kind: Canary
metadata:
  name: splitpay-backend
  namespace: production
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: splitpay-backend
  progressDeadlineSeconds: 60
  service:
    port: 80
  analysis:
    interval: 1m
    threshold: 5
    maxWeight: 50
    stepWeight: 5
    metrics:
    - name: request-success-rate
      thresholdRange:
        min: 99
      interval: 1m
    - name: request-duration
      thresholdRange:
        max: 500
      interval: 1m
    webhooks:
    - name: smoke-tests
      url: http://flagger-loadtester/
      timeout: 5s
      metadata:
        type: smoke
        cmd: "curl -sd 'test' http://splitpay-backend:80/api/health"
```

#### 4.1.3 Rolling Deployment (For Non-Critical Changes)

**Objective:** Gradual rollout with zero downtime; slower than blue/green.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: splitpay-backend
  namespace: production
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Max 1 extra pod during rollout
      maxUnavailable: 0  # No pods unavailable (zero downtime)
  selector:
    matchLabels:
      app: splitpay-backend
  template:
    metadata:
      labels:
        app: splitpay-backend
    spec:
      containers:
      - name: splitpay-backend
        image: <ECR_REGISTRY>/splitpay-backend:v1.1.0
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 20
          failureThreshold: 3
```

### 4.2 Deployment Decision Matrix

| **Change Type** | **Risk Level** | **Deployment Strategy** | **Testing** | **Rollback Time** |
|---|---|---|---|---|
| **Bug fix** | Low | Rolling | Unit + smoke tests | <5 min |
| **Feature (non-financial)** | Low-Medium | Canary (5% → 100%) | Full integration tests | <5 min |
| **Feature (financial logic)** | High | Blue/green | Full integration + load tests | <1 min |
| **Database schema change** | High | Blue/green + migration | Tested in staging; backward-compatible | <5 min |
| **Third-party integration** | Medium | Canary (feature flag) | Integration tests; circuit breaker | <5 min |
| **Infrastructure change** | High | Blue/green + terraform plan review | Tested in staging; manual approval | <10 min |

### 4.3 Database Migration Strategy

**Principle:** Migrations must be backward-compatible and testable in staging.

#### 4.3.1 Expand/Contract Pattern

```sql
-- Step 1: EXPAND - Add new column (backward-compatible)
ALTER TABLE expenses ADD COLUMN settlement_status VARCHAR(50) DEFAULT 'pending';

-- Step 2: BACKFILL - Populate new column (can be done gradually)
UPDATE expenses SET settlement_status = 'completed' WHERE paid_at IS NOT NULL;

-- Step 3: Deploy new code that reads/writes settlement_status

-- Step 4: CONTRACT - Remove old column (after code uses new column for 1-2 deployments)
ALTER TABLE expenses DROP COLUMN paid_at;
```

#### 4.3.2 Migration Execution

```bash
#!/bin/bash
# scripts/run-migrations.sh

ENVIRONMENT=${1:-staging}
MIGRATION_IMAGE=${2:-splitpay-backend:latest}

echo "Running database migrations for $ENVIRONMENT..."

# Create Kubernetes job to run migrations
kubectl create job db-migration-$(date +%s) \
  --image=$MIGRATION_IMAGE \
  -n $ENVIRONMENT \
  -- npm run db:migrate

# Wait for job to complete
kubectl wait --for=condition=complete job/db-migration-* \
  -n $ENVIRONMENT \
  --timeout=5m

# Check job status
kubectl get job db-migration-* -n $ENVIRONMENT
```

#### 4.3.3 Migration Validation

```yaml
# Kubernetes Job: Validate migrations before deployment
apiVersion: batch/v1
kind: Job
metadata:
  name: db-validation
  namespace: staging
spec:
  template:
    spec:
      containers:
      - name: db-validation
        image: splitpay-backend:v1.1.0
        command:
        - /bin/sh
        - -c
        - |
          # Run migration
          npm run db:migrate
          
          # Validate schema
          npm run db:validate-schema
          
          # Run data integrity checks
          npm run db:validate-data
          
          # Rollback (optional, for testing)
          npm run db:migrate:rollback
      restartPolicy: Never
  backoffLimit: 1
```

### 4.4 Feature Flags & Progressive Rollout

**Objective:** Decouple code deployment from feature availability; enable safe rollback without code revert.

#### 4.4.1 Feature Flag Implementation

```typescript
// Backend: Feature flag service
interface FeatureFlag {
  name: string;
  enabled: boolean;
  rolloutPercentage: number;  // 0-100
  targetUsers?: string[];     // Specific user IDs
  targetGroups?: string[];    // Specific group IDs
}

class FeatureFlagService {
  async isEnabled(flagName: string, userId: string): Promise<boolean> {
    const flag = await this.getFlag(flagName);
    
    if (!flag.enabled) return false;
    
    // Check specific user/group targeting
    if (flag.targetUsers?.includes(userId)) return true;
    if (flag.targetUsers && flag.targetUsers.length > 0) return false;
    
    // Check rollout percentage (consistent hash)
    const hash = hashFunction(`${flagName}:${userId}`);
    return (hash % 100) < flag.rolloutPercentage;
  }
}

// Usage in code
async function handleReceiptUpload(req, res) {
  const isNewOCREnabled = await featureFlagService.isEnabled('new-ocr-engine', req.user.id);
  
  if (isNewOCREnabled) {
    // Use new OCR provider
    return await newOCRProvider.extract(req.file);
  } else {
    // Use existing OCR provider
    return await existingOCRProvider.extract(req.file);
  }
}
```

#### 4.4.2 Feature Flag Configuration

```yaml
# Feature flags stored in database or config service
flags:
  - name: new-ocr-engine
    enabled: true
    rolloutPercentage: 10  # Start with 10% of users
    targetUsers: []
    createdAt: 2024-01-15
    updatedAt: 2024-01-15

  - name: transaction-minimization-v2
    enabled: true
    rolloutPercentage: 50  # 50% rollout
    targetUsers: []
    createdAt: 2024-01-10
    updatedAt: 2024-01-15

  - name: recurring-splits-beta
    enabled: true
    rolloutPercentage: 0   # Disabled; only for specific users
    targetUsers: ["user-123", "user-456"]
    createdAt: 2024-01-01
    updatedAt: 2024-01-15
```

---

## 5. MONITORING, OBSERVABILITY & ALERTING

### 5.1 Observability Philosophy

**Three Pillars of Observability:**

1. **Metrics:** Quantitative measurements (requests/sec, latency, error rate, resource utilization)
2. **Logs:** Structured event records (JSON logs with correlation IDs, timestamps, severity)
3. **Traces:** Distributed request flows across services (end-to-end request tracking)

**Principle:** Observability is built-in before features ship. Monitoring is not an afterthought; it's a first-class requirement.

### 5.2 Metrics Strategy

#### 5.2.1 Core Metrics (SLIs)

| **Metric** | **Collection** | **Alert Threshold** | **Dashboard** |
|---|---|---|---|
| **API Availability** | HTTP status codes (2xx/3xx vs. 4xx/5xx) | <99.9% for 5 min | Main dashboard |
| **Request Latency (p50, p95, p99)** | Response time histogram | p95 > 500ms for 5 min | Performance dashboard |
| **Error Rate** | 5xx responses / total requests | >1% for 5 min | Main dashboard |
| **Receipt Processing Time** | Time from upload to OCR completion | p99 > 5s for 10 min | Feature-specific |
| **Payment Reminder Delivery** | SMS/push sent vs. delivered | <99% for 5 min | Notification dashboard |
| **Database Connection Pool** | Active / total connections | >80% utilization for 5 min | Infrastructure dashboard |
| **Cache Hit Rate** | Redis hits / total requests | <70% for 10 min | Cache dashboard |
| **Pod Restart Rate** | Restarts per pod per hour | >0 in 1 hour | Cluster health |
| **Disk Usage** | Used / total disk space | >80% for 5 min | Infrastructure dashboard |
| **Memory Usage** | Used / total memory | >85% for 5 min | Infrastructure dashboard |

#### 5.2.2 Instrumentation

```typescript
// Backend: Metrics instrumentation (Prometheus client)

import prometheus from 'prom-client';

// Create metrics
const httpRequestDuration = new prometheus.Histogram({
  name: 'http_request_duration_seconds',
  help: 'Duration of HTTP requests in seconds',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.1, 0.5, 1, 2, 5, 10]
});

const receiptProcessingTime = new prometheus.Histogram({
  name: 'receipt_processing_duration_seconds',
  help: 'Time to process receipt (OCR + calculation)',
  labelNames: ['ocr_provider', 'status'],
  buckets: [1, 2, 5, 10, 30]
});

const expenseCalculationErrors = new prometheus.Counter({
  name: 'expense_calculation_errors_total',
  help: 'Total expense calculation errors',
  labelNames: ['error_type', 'expense_type']
});

const paymentRemindersSent = new prometheus.Counter({
  name: 'payment_reminders_sent_total',
  help: 'Total payment reminders sent',
  labelNames: ['channel']  // 'sms', 'push'
});

// Middleware: Record HTTP metrics
app.use((req, res, next) => {
  