# SOLUTION DESIGN DOCUMENT: AsyncStandup Slack Bot

## Document Control
- **Product Name**: AsyncStandup
- **Version**: 1.0
- **Last Updated**: 2024-01-15
- **Document Owner**: Engineering Leadership
- **Status**: Approved for Implementation
- **Target Launch**: Q2 2024
- **Related Documents**: PRD v1.0, TRD v1.0
- **Review Cycle**: After MVP launch, then quarterly
- **Stakeholders**: Engineering, Product, Operations, Security, Design
- **Approval Required From**: VP Engineering, Director of Product, Head of Infrastructure, Security Lead
- **Change Log**: 
  - v1.0 - Initial approved design incorporating cross-functional feedback from Solutions Architect, Full Stack Developer, UI/UX Developer, Backend API Engineer, Database Engineer, and DevOps Engineer

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Component Design](#3-component-design)
4. [Data Model](#4-data-model)
5. [API Contracts](#5-api-contracts)
6. [User Experience Flows](#6-user-experience-flows)
7. [Security Design](#7-security-design)
8. [Scalability Approach](#8-scalability-approach)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Monitoring & Observability](#10-monitoring--observability)
11. [Technology Stack Decisions](#11-technology-stack-decisions)
12. [Testing Strategy](#12-testing-strategy)
13. [Migration & Evolution Path](#13-migration--evolution-path)
14. [Open Questions & Risks](#14-open-questions--risks)
15. [Appendices](#15-appendices)

---

## 1. EXECUTIVE SUMMARY

### 1.1 Design Philosophy

**Core Principle**: Build a modular monolith optimized for operational simplicity, with clear internal boundaries that enable future service extraction when scale demands it—not before.

After analyzing requirements, team capabilities, and realistic scale projections (100-500 messages/day per team, 10K messages/day across all customers at 100 teams), we are proposing a **pragmatic, operations-first architecture** that prioritizes:

1. **Simplicity**: Single deployable Node.js application, easy to reason about and debug
2. **Modularity**: Clear internal module boundaries with defined interfaces (can become microservices later)
3. **Reliability**: Fail-safe defaults, graceful degradation, comprehensive retry logic
4. **Observability**: Instrumented from day one with structured logging and business metrics
5. **Cost Efficiency**: $200-400/month infrastructure cost at 100 teams (not $2K+)
6. **Developer Experience**: Fast local development, easy testing, clear error messages

### 1.2 Key Architectural Decisions

| Decision Area | Choice | Rationale | Trade-offs Accepted |
|--------------|--------|-----------|---------------------|
| **Architecture Pattern** | Modular Monolith | Simple to deploy/debug; matches actual scale (10K msgs/day); clear module boundaries for future extraction | Harder to scale individual components independently (but we don't need to yet) |
| **Runtime** | Node.js 20 LTS | Team expertise; excellent Slack SDK; fast iteration; good for I/O-bound workloads | Not ideal for CPU-intensive tasks (but summarization is external API call) |
| **Database** | PostgreSQL 15 (RDS) | ACID guarantees; JSONB for flexible standup content; mature ecosystem; easy backups | Higher cost than DynamoDB (~$50/mo vs. $10/mo at 100 teams) but worth it for consistency |
| **Job Scheduler** | BullMQ (Redis-backed) | Reliable job queuing; retry logic; job prioritization; easy monitoring | Requires Redis (~$30/mo ElastiCache) but gives us caching + job queue |
| **Caching** | Redis 7 (ElastiCache) | Sub-ms reads for Slack tokens; rate limit tracking; BullMQ backing store | Additional infrastructure; cache invalidation complexity |
| **Hosting** | AWS ECS Fargate | Container-based; auto-scaling; no server management; easy rollbacks | More expensive than EC2 (~$100/mo vs. $30/mo) but operationally simpler |
| **NLP/Summarization** | OpenAI GPT-4 Turbo | Best-in-class summarization; no model training; fast iteration | External dependency; $0.01/request cost; need fallback strategy |
| **Observability** | DataDog (logs + metrics + APM) | Unified platform; Slack integration; good Node.js support; 14-day free trial | Premium pricing (~$100/mo at scale) but critical for operational confidence |
| **CI/CD** | GitHub Actions + Docker | Simple pipeline; preview environments; automated testing; team familiarity | GitHub-specific; need self-hosted runners for cost optimization later |

### 1.3 Why NOT Microservices?

**Current Scale Reality:**
- 100 teams × 10 people × 1 message/day = **1,000 messages/day**
- At 1,000 teams: **10,000 messages/day**
- Peak load: ~200 messages/minute during 9am EST submission window

**This is a scheduled batch job, not a real-time system.** We have:
- ✅ 24 hours between submission deadline and next standup
- ✅ No sub-second latency requirements
- ✅ Trivial concurrency (one standup per team per day)
- ✅ Predictable load patterns (morning submission spikes)

**Microservices add:**
- ❌ Distributed tracing complexity
- ❌ Network failure modes between services
- ❌ Eventual consistency debugging
- ❌ Higher infrastructure cost ($2K/mo vs. $400/mo)
- ❌ Slower development velocity (coordinating deployments)

**When we'll reconsider:**
- When we hit 10,000 teams (100K messages/day)
- When we add real-time features (live standup dashboards)
- When submission processing takes >5 minutes per team
- When we need independent scaling of components

### 1.4 System Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          SLACK WORKSPACE                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │  Team Member DM  │  │  Team Member DM  │  │  Team Member DM  │     │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘     │
│           │                     │                     │                │
│  ┌────────▼─────────────────────▼─────────────────────▼────────┐      │
│  │         Slack API (Events API + Web API)                    │      │
│  │  - message_im (inbound updates)                             │      │
│  │  - chat.postMessage (summaries + reminders)                 │      │
│  └────────┬──────────────────────────────────────────────────┬─┘      │
└───────────┼──────────────────────────────────────────────────┼────────┘
            │                                                  │
            │ HTTPS webhooks                         API calls │
            │                                                  │
┌───────────▼──────────────────────────────────────────────────▼────────┐
│                    AWS APPLICATION LOAD BALANCER                      │
│                    (SSL termination, health checks)                   │
└───────────┬───────────────────────────────────────────────────────────┘
            │
┌───────────▼───────────────────────────────────────────────────────────┐
│                   ECS FARGATE (Auto-scaling 2-10 tasks)               │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │              ASYNCSTANDUP MONOLITH (Node.js 20)                 │  │
│  │                                                                 │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │  │
│  │  │   Webhook    │  │   Job        │  │   Admin      │         │  │
│  │  │   Handler    │  │   Processor  │  │   API        │         │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │  │
│  │         │                 │                 │                  │  │
│  │  ┌──────▼─────────────────▼─────────────────▼───────┐          │  │
│  │  │            INTERNAL MODULE LAYER                 │          │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │          │  │
│  │  │  │ Submission  │  │  Summary    │  │  Slack   │ │          │  │
│  │  │  │  Module     │  │  Module     │  │  Module  │ │          │  │
│  │  │  └─────────────┘  └─────────────┘  └──────────┘ │          │  │
│  │  │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │          │  │
│  │  │  │   Team      │  │    User     │  │  OpenAI  │ │          │  │
│  │  │  │   Module    │  │   Module    │  │  Module  │ │          │  │
│  │  │  └─────────────┘  └─────────────┘  └──────────┘ │          │  │
│  │  └──────────────────────────────────────────────────┘          │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────┬───────────────────────────────────────┬───────────────────┘
            │                                       │
    ┌───────▼──────────┐                   ┌────────▼─────────┐
    │  PostgreSQL 15   │                   │   Redis 7        │
    │  (RDS Multi-AZ)  │                   │  (ElastiCache)   │
    │                  │                   │                  │
    │  - Workspaces    │                   │  - Job Queue     │
    │  - Teams         │                   │  - Rate Limits   │
    │  - Submissions   │                   │  - Token Cache   │
    │  - Summaries     │                   │  - Session Data  │
    └──────────────────┘                   └──────────────────┘
            │
    ┌───────▼──────────┐
    │   S3 Bucket      │
    │  (Backups +      │
    │   Raw Logs)      │
    └──────────────────┘

EXTERNAL DEPENDENCIES:
┌────────────────────┐      ┌────────────────────┐
│  OpenAI API        │      │  DataDog           │
│  (Summarization)   │      │  (Observability)   │
└────────────────────┘      └────────────────────┘
```

### 1.5 Data Flow Overview

**Daily Standup Lifecycle:**

```
1. REMINDER PHASE (Scheduled: 8:00am team local time)
   └─> BullMQ job triggers
   └─> Fetch teams with standup_time = "09:30"
   └─> For each team member: send DM reminder via Slack API
   └─> Log reminder_sent event

2. COLLECTION PHASE (8:00am - 9:30am team local time)
   └─> User sends DM to bot
   └─> Slack Events API webhook → /api/webhooks/slack
   └─> Validate signature + parse message
   └─> Store submission in PostgreSQL
   └─> Send confirmation message to user
   └─> If user mentions blocker → flag for immediate attention

3. SUMMARIZATION PHASE (Scheduled: 9:30am team local time)
   └─> BullMQ job triggers
   └─> Fetch all submissions for team + standup_date
   └─> Call OpenAI API with structured prompt
   └─> Parse response → extract blockers, highlights, participation
   └─> Store summary in PostgreSQL
   └─> Publish summary to team channel via Slack API
   └─> Send DM to non-participants (if configured)

4. ESCALATION PHASE (If blocker detected)
   └─> Parse blocker severity (high/medium/low)
   └─> If high: notify team lead immediately
   └─> If medium: include in summary with @mention
   └─> If low: include in summary without @mention
```

### 1.6 Success Criteria

This design will be considered successful if:

✅ **Reliability**: 99.5% uptime (max 3.6 hours downtime/month)
✅ **Performance**: 
  - Reminder delivery: <5 seconds per team
  - Submission acknowledgment: <2 seconds
  - Summary generation: <30 seconds per team
✅ **Cost**: <$500/month infrastructure at 100 teams
✅ **Operational**: Mean Time to Recovery (MTTR) <15 minutes for P1 incidents
✅ **Developer Experience**: New engineer can run locally in <30 minutes
✅ **Observability**: Can debug any issue from logs/metrics alone (no SSH required)

---

## 2. ARCHITECTURE OVERVIEW

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SYSTEMS                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   │
│  │   Slack API      │   │   OpenAI API     │   │   DataDog        │   │
│  │   (Events +      │   │   (GPT-4 Turbo)  │   │   (Observability)│   │
│  │    Web API)      │   │                  │   │                  │   │
│  └────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘   │
│           │                      │                      │              │
└───────────┼──────────────────────┼──────────────────────┼──────────────┘
            │                      │                      │
            │ HTTPS                │ HTTPS                │ HTTPS
            │                      │                      │
┌───────────▼──────────────────────▼──────────────────────▼──────────────┐
│                      APPLICATION LAYER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │              AWS APPLICATION LOAD BALANCER                    │     │
│  │  - SSL/TLS termination                                        │     │
│  │  - Health checks (/health endpoint)                           │     │
│  │  - Request routing                                            │     │
│  └────────────────────────┬──────────────────────────────────────┘     │
│                           │                                            │
│  ┌────────────────────────▼───────────────────────────────────────┐    │
│  │           ECS FARGATE CLUSTER (Auto-scaling)                  │    │
│  │                                                                │    │
│  │  ┌──────────────────────────────────────────────────────────┐ │    │
│  │  │         ASYNCSTANDUP CONTAINER (Node.js 20)              │ │    │
│  │  │                                                          │ │    │
│  │  │  ┌────────────────────────────────────────────────────┐ │ │    │
│  │  │  │         HTTP SERVER (Express.js)                   │ │ │    │
│  │  │  │                                                    │ │ │    │
│  │  │  │  Routes:                                           │ │ │    │
│  │  │  │  - POST /api/webhooks/slack                        │ │ │    │
│  │  │  │  - GET  /api/admin/teams                           │ │ │    │
│  │  │  │  - GET  /health                                    │ │ │    │
│  │  │  └────────────────────────────────────────────────────┘ │ │    │
│  │  │                                                          │ │    │
│  │  │  ┌────────────────────────────────────────────────────┐ │ │    │
│  │  │  │         JOB PROCESSOR (BullMQ Worker)              │ │ │    │
│  │  │  │                                                    │ │ │    │
│  │  │  │  Job Types:                                        │ │ │    │
│  │  │  │  - send-reminders (cron: 0 */1 * * *)             │ │ │    │
│  │  │  │  - generate-summaries (cron: 0 */1 * * *)         │ │ │    │
│  │  │  │  - process-submission (event-driven)               │ │ │    │
│  │  │  │  - retry-failed-summary (manual trigger)           │ │ │    │
│  │  │  └────────────────────────────────────────────────────┘ │ │    │
│  │  │                                                          │ │    │
│  │  │  ┌────────────────────────────────────────────────────┐ │ │    │
│  │  │  │         MODULE LAYER (Internal APIs)               │ │ │    │
│  │  │  │                                                    │ │ │    │
│  │  │  │  Core Modules:                                     │ │ │    │
│  │  │  │  - SubmissionModule (collect, validate, store)    │ │ │    │
│  │  │  │  - SummaryModule (generate, format, publish)      │ │ │    │
│  │  │  │  - SlackModule (API wrapper, retry logic)         │ │ │    │
│  │  │  │  - OpenAIModule (summarization, parsing)          │ │ │    │
│  │  │  │  - TeamModule (config, members, schedules)        │ │ │    │
│  │  │  │  - UserModule (preferences, timezone, status)     │ │ │    │
│  │  │  └────────────────────────────────────────────────────┘ │ │    │
│  │  └──────────────────────────────────────────────────────────┘ │    │
│  │                                                                │    │
│  │  Scaling Config:                                               │    │
│  │  - Min tasks: 2 (high availability)                            │    │
│  │  - Max tasks: 10 (cost cap)                                    │    │
│  │  - Scale up: CPU > 70% OR Memory > 80%                         │    │
│  │  - Scale down: CPU < 30% for 5 minutes                         │    │
│  └────────────────────────────────────────────────────────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
            │                                       │
            │                                       │
┌───────────▼──────────────┐           ┌────────────▼────────────┐
│   DATA LAYER             │           │   CACHE/QUEUE LAYER     │
├──────────────────────────┤           ├─────────────────────────┤
│                          │           │                         │
│  PostgreSQL 15 (RDS)     │           │   Redis 7 (ElastiCache) │
│  - Multi-AZ deployment   │           │   - Single node (dev)   │
│  - Automated backups     │           │   - Cluster (prod)      │
│  - Read replicas (prod)  │           │                         │
│                          │           │   Use Cases:            │
│  Tables:                 │           │   - BullMQ job queue    │
│  - workspaces            │           │   - Rate limit tracking │
│  - teams                 │           │   - Slack token cache   │
│  - team_members          │           │   - Session storage     │
│  - standup_schedules     │           │   - Feature flags       │
│  - submissions           │           │                         │
│  - summaries             │           │   Eviction: LRU         │
│  - audit_logs            │           │   TTL: 1-24 hours       │
│                          │           │                         │
│  Size: 20GB (start)      │           │   Size: 1GB (start)     │
│  IOPS: 3000 (gp3)        │           │   Type: cache.t3.micro  │
│  Connections: 100 max    │           │                         │
└──────────────────────────┘           └─────────────────────────┘
            │
            │
┌───────────▼──────────────┐
│   BACKUP LAYER           │
├──────────────────────────┤
│                          │
│  S3 Bucket               │
│  - Automated DB backups  │
│  - Application logs      │
│  - Audit trail exports   │
│                          │
│  Lifecycle:              │
│  - Standard: 30 days     │
│  - Glacier: 90 days      │
│  - Delete: 1 year        │
└──────────────────────────┘

DEPLOYMENT PIPELINE:
┌────────────────────────────────────────────────────────────────┐
│  GitHub → Actions → Build Docker → Push ECR → Deploy ECS      │
│                                                                │
│  Environments:                                                 │
│  - dev (auto-deploy on main)                                  │
│  - staging (manual approval)                                  │
│  - production (manual approval + rollback plan)               │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Request Flow Patterns

#### Pattern 1: Webhook Processing (Submission Collection)

```
┌─────────┐                                                    ┌─────────┐
│  Slack  │                                                    │  User   │
│   API   │                                                    │   DM    │
└────┬────┘                                                    └────┬────┘
     │                                                              │
     │ 1. User sends "Yesterday: Fixed auth bug"                   │
     │◄─────────────────────────────────────────────────────────────┘
     │
     │ 2. POST /api/webhooks/slack
     │    Headers: X-Slack-Signature, X-Slack-Request-Timestamp
     │    Body: { type: "event_callback", event: { ... } }
     ├───────────────────────────────────────────────────────────►┌──────────┐
     │                                                             │   ALB    │
     │                                                             └────┬─────┘
     │                                                                  │
     │ 3. Route to ECS task                                             │
     │                                                                  ├─────►┌──────────────┐
     │                                                                  │      │  Express.js  │
     │                                                                  │      │   Handler    │
     │                                                                  │      └──────┬───────┘
     │                                                                  │             │
     │                                                                  │ 4. Verify signature
     │                                                                  │    (HMAC-SHA256)
     │                                                                  │             │
     │                                                                  │ 5. If invalid: 401
     │                                                                  │◄────────────┤
     │                                                                  │             │
     │                                                                  │ 6. Parse event type
     │                                                                  │    - url_verification: respond with challenge
     │                                                                  │    - message_im: process submission
     │                                                                  │             │
     │                                                                  │ 7. Call SubmissionModule.create()
     │                                                                  │             ├─────►┌──────────────────┐
     │                                                                  │             │      │ SubmissionModule │
     │                                                                  │             │      └────────┬─────────┘
     │                                                                  │             │               │
     │                                                                  │             │ 8. Validate input
     │                                                                  │             │    - User exists?
     │                                                                  │             │    - Team configured?
     │                                                                  │             │    - Within submission window?
     │                                                                  │             │               │
     │                                                                  │             │ 9. INSERT submission
     │                                                                  │             │               ├─────►┌──────────┐
     │                                                                  │             │               │      │PostgreSQL│
     │                                                                  │             │               │◄─────┤          │
     │                                                                  │             │               │      └──────────┘
     │                                                                  │             │               │
     │                                                                  │             │ 10. Queue async processing
     │                                                                  │             │               ├─────►┌──────────┐
     │                                                                  │             │               │      │  Redis   │
     │                                                                  │             │               │      │ (BullMQ) │
     │                                                                  │             │               │◄─────┤          │
     │                                                                  │             │               │      └──────────┘
     │                                                                  │             │               │
     │                                                                  │             │ 11. Return success
     │                                                                  │             │◄──────────────┤
     │                                                                  │             │
     │                                                                  │ 12. Send confirmation DM
     │                                                                  │             ├─────►┌──────────────┐
     │                                                                  │             │      │ SlackModule  │
     │                                                                  │             │      └──────┬───────┘
     │                                                                  │             │             │
     │ 13. POST /chat.postMessage                                       │             │             │
     │◄─────────────────────────────────────────────────────────────────┴─────────────┴─────────────┘
     │    "Thanks! Your update has been recorded."
     │
     ├────────────────────────────────────────────────────────────────►
     │ 14. Display confirmation to user                                │
     │                                                                 │
     └─────────────────────────────────────────────────────────────────┘

Total Time: ~1-2 seconds
Critical Path: Slack signature verification + DB write + confirmation message
```

#### Pattern 2: Scheduled Job Processing (Summary Generation)

```
┌─────────────┐
│   BullMQ    │
│  Scheduler  │
└──────┬──────┘
       │
       │ 1. Cron triggers at 9:30am (team local time)
       │    Job: generate-summaries
       │    Payload: { teamId: "T123", date: "2024-01-15" }
       │
       ├───────────────────────────────────────────────────────────►┌──────────────┐
       │                                                             │  BullMQ      │
       │                                                             │  Worker      │
       │                                                             └──────┬───────┘
       │                                                                    │
       │ 2. Worker picks up job                                            │
       │                                                                    │
       │ 3. Call SummaryModule.generate()                                  │
       │                                                                    ├─────►┌──────────────┐
       │                                                                    │      │SummaryModule │
       │                                                                    │      └──────┬───────┘
       │                                                                    │             │
       │ 4. Fetch submissions for team + date                              │             │
       │                                                                    │             ├─────►┌──────────┐
       │                                                                    │             │      │PostgreSQL│
       │    SELECT * FROM submissions                                      │             │◄─────┤          │
       │    WHERE team_id = $1 AND standup_date = $2                       │             │      └──────────┘
       │                                                                    │             │
       │ 5. If no submissions: skip                                        │             │
       │                                                                    │             │
       │ 6. Call OpenAIModule.summarize()                                  │             │
       │                                                                    │             ├─────►┌──────────────┐
       │                                                                    │             │      │ OpenAIModule │
       │                                                                    │             │      └──────┬───────┘
       │                                                                    │             │             │
       │ 7. Build prompt:                                                  │             │             │
       │    "Summarize these standup updates. Extract blockers..."         │             │             │
       │                                                                    │             │             │
       │ 8. POST https://api.openai.com/v1/chat/completions                │             │             │
       │    Model: gpt-4-turbo                                             │             │             ├─────►┌──────────┐
       │    Max tokens: 500                                                │             │             │      │ OpenAI   │
       │    Temperature: 0.3                                               │             │             │      │   API    │
       │                                                                    │             │             │◄─────┤          │
       │                                                                    │             │             │      └──────────┘
       │ 9. Parse response:                                                │             │             │
       │    - Extract blockers (with severity)                             │             │             │
       │    - Extract highlights                                           │             │             │
       │    - Identify non-participants                                    │             │◄────────────┤
       │                                                                    │             │
       │ 10. Store summary in DB                                           │             │
       │     INSERT INTO summaries (...)                                   │             ├─────►┌──────────┐
       │                                                                    │             │      │PostgreSQL│
       │                                                                    │             │◄─────┤          │
       │                                                                    │             │      └──────────┘
       │                                                                    │             │
       │ 11. Format Slack message (Block Kit)                              │             │
       │                                                                    │             │
       │ 12. Call SlackModule.postToChannel()                              │             │
       │                                                                    │             ├─────►┌──────────────┐
       │                                                                    │             │      │  SlackModule │
       │                                                                    │             │      └──────┬───────┘
       │                                                                    │             │             │
       │ 13. POST /chat.postMessage                                        │             │             │
       │     Channel: #engineering                                         │             │             ├─────►┌──────────┐
       │     Blocks: [header, divider, blockers, highlights, ...]          │             │             │      │ Slack API│
       │                                                                    │             │             │◄─────┤          │
       │                                                                    │             │             │      └──────────┘
       │                                                                    │             │◄────────────┤
       │                                                                    │             │
       │ 14. If non-participants: send DMs                                 │             │
       │     (Optional based on team config)                               │             │
       │                                                                    │◄────────────┤
       │                                                                    │
       │ 15. Mark job complete                                             │
       │◄───────────────────────────────────────────────────────────────────┤
       │
       │ 16. Log metrics:                                                  │
       │     - summary_generation_duration_ms                              │
       │     - openai_api_latency_ms                                       │
       │     - participation_rate                                          │
       │     - blocker_count                                               │
       │                                                                   │
       └───────────────────────────────────────────────────────────────────┘

Total Time: ~10-30 seconds per team
Critical Path: OpenAI API call (5-15s) + Slack API call (1-2s)
Retry Strategy: 3 attempts with exponential backoff (1s, 5s, 15s)
Fallback: If OpenAI fails after retries, publish raw submissions
```

### 2.3 Module Boundaries & Responsibilities

#### Core Design Principle: Separation of Concerns

Each module has:
- **Single Responsibility**: One clear purpose
- **Defined Interface**: Public methods only (no direct DB access from outside)
- **Testable in Isolation**: Can be unit tested without dependencies
- **Future Service Boundary**: Could become a microservice if needed

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MODULE ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                    PRESENTATION LAYER                         │     │
│  │  (Express.js routes + BullMQ job handlers)                    │     │
│  │                                                               │     │
│  │  /api/webhooks/slack → WebhookController                      │     │
│  │  /api/admin/teams → AdminController                           │     │
│  │  /health → HealthController                                   │     │
│  └─────────────────────────┬─────────────────────────────────────┘     │
│                            │                                           │
│                            │ (calls)                                   │
│                            │                                           │
│  ┌─────────────────────────▼─────────────────────────────────────┐     │
│  │                    SERVICE LAYER                              │     │
│  │  (Business logic + orchestration)                             │     │
│  │                                                               │     │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │     │
│  │  │ SubmissionModule│  │  SummaryModule  │  │  TeamModule  │ │     │
│  │  │                 │  │                 │  │              │ │     │
│  │  │ - create()      │  │ - generate()    │  │ - getConfig()│ │     │
│  │  │ - validate()    │  │ - publish()     │  │ - addMember()│ │     │
│  │  │ - getByTeam()   │  │ - retry()       │  │ - setSchedule│ │     │
│  │  └─────────────────┘  └─────────────────┘  └──────────────┘ │     │
│  │                                                               │     │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │     │
│  │  │   UserModule    │  │  SlackModule    │  │ OpenAIModule │ │     │
│  │  │                 │  │                 │  │              │ │     │
│  │  │ - getBySlackId()│  │ - postMessage() │  │ - summarize()│ │     │
│  │  │ - updatePrefs() │  │ - sendDM()      │  │ - parse()    │ │     │
│  │  │ - getTimezone() │  │ - verifyWebhook │  │ - retry()    │ │     │
│  │  └─────────────────┘  └─────────────────┘  └──────────────┘ │     │
│  └─────────────────────────┬─────────────────────────────────────┘     │
│                            │                                           │
│                            │ (calls)                                   │
│                            │                                           │
│  ┌─────────────────────────▼─────────────────────────────────────┐     │
│  │                    DATA ACCESS LAYER                          │     │
│  │  (Database repositories + external API clients)               │     │
│  │                                                               │     │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │     │
│  │  │SubmissionRepo   │  │  SummaryRepo    │  │   TeamRepo   │ │     │
│  │  │                 │  │                 │  │              │ │     │
│  │  │ - insert()      │  │ - insert()      │  │ - findById() │ │     │
│  │  │ - findByTeam()  │  │ - findByTeam()  │  │ - update()   │ │     │
│  │  │ - update()      │  │ - findByDate()  │  │ - delete()   │ │     │
│  │  └─────────────────┘  └─────────────────┘  └──────────────┘ │     │
│  │                                                               │     │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │     │
│  │  │   UserRepo      │  │  SlackClient    │  │ OpenAIClient │ │     │
│  │  │                 │  │                 │  │              │ │     │
│  │  │ - findBySlackId│  │ - post()        │  │ - complete() │ │     │
│  │  │ - insert()      │  │ - get()         │  │ - stream()   │ │     │
│  │  │ - update()      │  │ - retryWithBackoff│ - validate() │ │     │
│  │  └─────────────────┘  └─────────────────┘  └──────────────┘ │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │                    INFRASTRUCTURE LAYER                       │     │
│  │  (Database connections, caching, logging)                     │     │
│  │                                                               │     │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐ │     │
│  │  │  PostgreSQL     │  │     Redis       │  │   Logger     │ │     │
│  │  │  Connection     │  │   Connection    │  │  (Winston)   │ │     │
│  │  │   Pool          │  │    Client       │  │              │ │     │
│  │  └─────────────────┘  └─────────────────┘  └──────────────┘ │     │
│  └───────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

CROSS-CUTTING CONCERNS (Applied at all layers):
- Error Handling (try/catch + custom error types)
- Logging (structured JSON logs with correlation IDs)
- Validation (Zod schemas at API boundaries)
- Authentication (Slack signature verification)
- Rate Limiting (Redis-backed token bucket)
- Monitoring (DataDog APM instrumentation)
```

#### Module Details

**1. SubmissionModule**
```typescript
// src/modules/submission/submission.module.ts

export class SubmissionModule {
  constructor(
    private submissionRepo: SubmissionRepository,
    private teamModule: TeamModule,
    private userModule: UserModule,
    private slackModule: SlackModule,
    private logger: Logger
  ) {}

  /**
   * Create a new standup submission
   * @throws ValidationError if input is invalid
   * @throws NotFoundError if team/user doesn't exist
   * @throws SubmissionWindowClosedError if past deadline
   */
  async create(params: {
    slackUserId: string;
    slackTeamId: string;
    message: string;
    timestamp: Date;
  }): Promise<Submission> {
    // 1. Validate user exists and is member of team
    const user = await this.userModule.getBySlackId(params.slackUserId);
    if (!user) {
      throw new NotFoundError('User not found');
    }

    // 2. Get team config (standup time, timezone)
    const team = await this.teamModule.getBySlackId(params.slackTeamId);
    if (!team) {
      throw new NotFoundError('Team not found');
    }

    // 3. Check if within submission window
    const deadline = this.calculateDeadline(team.standupTime, team.timezone);
    if (params.timestamp > deadline) {
      throw new SubmissionWindowClosedError(
        `Submission window closed at ${deadline.toISOString()}`
      );
    }

    // 4. Parse message for blockers/highlights (simple keyword detection)
    const parsed = this.parseMessage(params.message);

    // 5. Store submission
    const submission = await this.submissionRepo.insert({
      userId: user.id,
      teamId: team.id,
      standupDate: this.getStandupDate(team.timezone),
      content: params.message,
      hasBlocker: parsed.hasBlocker,
      blockerKeywords: parsed.blockerKeywords,
      submittedAt: params.timestamp,
    });

    // 6. Send confirmation DM
    await this.slackModule.sendDM({
      userId: params.slackUserId,
      text: '✅ Thanks! Your standup update has been recorded.',
    });

    // 7. Log for observability
    this.logger.info('Submission created', {
      submissionId: submission.id,
      userId: user.id,
      teamId: team.id,
      hasBlocker: parsed.hasBlocker,
    });

    return submission;
  }

  /**
   * Get all submissions for a team on a specific date
   */
  async getByTeamAndDate(
    teamId: string,
    date: Date
  ): Promise<Submission[]> {
    return this.submissionRepo.findByTeamAndDate(teamId, date);
  }

  /**
   * Simple keyword-based blocker detection
   * (More sophisticated NLP happens in summary generation)
   */
  private parseMessage(message: string): {
    hasBlocker: boolean;
    blockerKeywords: string[];
  } {
    const blockerKeywords = [
      'blocked',
      'blocker',
      'stuck',
      'waiting on',
      'need help',
      'can\'t proceed',
    ];

    const lowerMessage = message.toLowerCase();
    const found = blockerKeywords.filter(keyword =>
      lowerMessage.includes(keyword)
    );

    return {
      hasBlocker: found.length > 0,
      blockerKeywords: found,
    };
  }

  private calculateDeadline(standupTime: string, timezone: string): Date {
    // standupTime format: "09:30"
    // timezone format: "America/New_York"
    // Returns deadline in UTC
    // Implementation uses date-fns-tz
  }

  private getStandupDate(timezone: string): Date {
    // Returns the "standup date" (e.g., if standup is at 9:30am on Jan 15,
    // the standup_date is Jan 15, even though some submissions may come in
    // late on Jan 14 in UTC)
  }
}
```

**2. SummaryModule**
```typescript
// src/modules/summary/summary.module.ts

export class SummaryModule {
  constructor(
    private summaryRepo: SummaryRepository,
    private submissionModule: SubmissionModule,
    private openAIModule: OpenAIModule,
    private slackModule: SlackModule,
    private teamModule: TeamModule,
    private logger: Logger
  ) {}

  /**
   * Generate and publish summary for a team's standup
   * @throws NoSubmissionsError if no submissions to summarize
   * @throws OpenAIError if summarization fails after retries
   */
  async generate(params: {
    teamId: string;
    standupDate: Date;
  }): Promise<Summary> {
    const startTime = Date.now();

    try {
      // 1. Fetch all submissions
      const submissions = await this.submissionModule.getByTeamAndDate(
        params.teamId,
        params.standupDate
      );

      if (submissions.length === 0) {
        throw new NoSubmissionsError('No submissions to summarize');
      }

      // 2. Get team config
      const team = await this.teamModule.getById(params.teamId);
      const teamMembers = await this.teamModule.getMembers(params.teamId);

      // 3. Call OpenAI for summarization
      let summaryText: string;
      let blockers: Blocker[];
      let highlights: Highlight[];

      try {
        const aiResult = await this.openAIModule.summarize({
          submissions: submissions.map(s => ({
            author: s.user.name,
            content: s.content,
          })),
          teamSize: teamMembers.length,
        });

        summaryText = aiResult.summary;
        blockers = aiResult.blockers;
        highlights = aiResult.highlights;
      } catch (error) {
        // Fallback: publish raw submissions if AI fails
        this.logger.error('OpenAI summarization failed, using fallback', {
          error,
          teamId: params.teamId,
        });

        summaryText = this.generateFallbackSummary(submissions);
        blockers = this.extractBlockersManually(submissions);
        highlights = [];
      }

      // 4. Identify non-participants
      const participantIds = new Set(submissions.map(s => s.userId));
      const nonParticipants = teamMembers.filter(
        m => !participantIds.has(m.id)
      );

      // 5. Store summary
      const summary = await this.summaryRepo.insert({
        teamId: params.teamId,
        standupDate: params.standupDate,
        content: summaryText,
        blockers,
        highlights,
        participantCount: submissions.length,
        totalMemberCount: teamMembers.length,
        nonParticipantIds: nonParticipants.map(m => m.id),
        generatedAt: new Date(),
      });

      // 6. Publish to Slack channel
      await this.publish(summary, team);

      // 7. Send DMs to non-participants (if configured)
      if (team.config.notifyNonParticipants) {
        await this.notifyNonParticipants(nonParticipants, team);
      }

      // 8. Log metrics
      const duration = Date.now() - startTime;
      this.logger.info('Summary generated', {
        summaryId: summary.id,
        teamId: params.teamId,
        participationRate: submissions.length / teamMembers.length,
        blockerCount: blockers.length,
        durationMs: duration,
      });

      return summary;
    } catch (error) {
      this.logger.error('Summary generation failed', {
        error,
        teamId: params.teamId,
        standupDate: params.standupDate,
      });
      throw error;
    }
  }

  /**
   * Publish summary to team's Slack channel
   */
  private async publish(summary: Summary, team: Team): Promise<void> {
    const blocks = this.formatSummaryBlocks(summary, team);

    await this.slackModule.postToChannel({
      channelId: team.slackChannelId,
      text: `📊 Daily Standup Summary for ${summary.standupDate.toLocaleDateString()}`,
      blocks,
    });
  }

  /**
   * Format summary as Slack Block Kit
   */
  private formatSummaryBlocks(summary: Summary, team: Team): Block[] {
    const blocks: Block[] = [];

    // Header
    blocks.push({
      type: 'header',
      text: {
        type: 'plain_text',
        text: `📊 Daily Standup Summary`,
      },
    });

    // Participation stats
    blocks.push({
      type: 'section',
      text: {
        type: 'mrkdwn',
        text: `*Date:* ${summary.standupDate.toLocaleDateString()}\n*Participation:* ${summary.participantCount}/${summary.totalMemberCount} (${Math.round((summary.participantCount / summary.totalMemberCount) * 100)}%)`,
      },
    });

    blocks.push({ type: 'divider' });

    // Blockers (if any)
    if (summary.blockers.length > 0) {
      blocks.push({
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*🚨 Blockers (${summary.blockers.length}):*`,
        },
      });

      summary.blockers.forEach(blocker => {
        blocks.push({
          type: 'section',
          text: {
            type: 'mrkdwn',
            text: `• *${blocker.author}*: ${blocker.description}${blocker.severity === 'high' ? ' ⚠️' : ''}`,
          },
        });
      });

      blocks.push({ type: 'divider' });
    }

    // Highlights (if any)
    if (summary.highlights.length > 0) {
      blocks.push({
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*✨ Highlights (${summary.highlights.length}):*`,
        },
      });

      summary.highlights.forEach(highlight => {
        blocks.push({
          type: 'section',
          text: {
            type: 'mrkdwn',
            text: `• *${highlight.author}*: ${highlight.description}`,
          },
        });
      });

      blocks.push({ type: 'divider' });
    }

    // Summary text
    blocks.push({
      type: 'section',
      text: {
        type: 'mrkdwn',
        text: `*Summary:*\n${summary.content}`,
      },
    });

    // Non-participants (if any)
    if (summary.nonParticipantIds.length > 0) {
      const mentions = summary.nonParticipantIds
        .map(id => `<@${id}>`)
        .join(', ');

      blocks.push({
        type: 'context',
        elements: [
          {
            type: 'mrkdwn',
            text: `⏰ Didn't submit today: ${mentions}`,
          },
        ],
      });
    }

    return blocks;
  }

  /**
   * Fallback summary generation (if OpenAI fails)
   */
  private generateFallbackSummary(submissions: Submission[]): string {
    return submissions
      .map(s => `*${s.user.name}:* ${s.content}`)
      .join('\n\n');
  }

  /**
   * Manual blocker extraction (keyword-based)
   */
  private extractBlockersManually(submissions: Submission[]): Blocker[] {
    return submissions
      .filter(s => s.hasBlocker)
      .map(s => ({
        author: s.user.name,
        description: s.content,
        severity: 'medium' as const,
      }));
  }

  /**
   * Send DMs to team members who didn't submit
   */
  private async notifyNonParticipants(
    nonParticipants: User[],
    team: Team
  ): Promise<void> {
    const promises = nonParticipants.map(user =>
      this.slackModule.sendDM({
        userId: user.slackId,
        text: `👋 Hey! You didn't submit a standup update for ${team.name} today. No worries if you're out, but wanted to check in!`,
      })
    );

    await Promise.allSettled(promises);
  }
}
```

**3. SlackModule**
```typescript
// src/modules/slack/slack.module.ts

export class SlackModule {
  private client: WebClient;
  private rateLimiter: RateLimiter;

  constructor(
    private tokenCache: TokenCache, // Redis-backed
    private logger: Logger
  ) {
    this.rateLimiter = new RateLimiter({
      maxRequests: 50, // Slack tier 3: 50 requests/minute
      windowMs: 60_000,
    });
  }

  /**
   * Send a direct message to a user
   * @throws SlackAPIError if message fails after retries
   */
  async sendDM(params: {
    userId: string;
    text: string;
    blocks?: Block[];
  }): Promise<void> {
    await this.rateLimiter.acquire();

    try {
      const token = await this.getToken(params.userId);
      this.client = new WebClient(token);

      await this.retryWithBackoff(async () => {
        await this.client.chat.postMessage({
          channel: params.userId,
          text: params.text,
          blocks: params.blocks,
        });
      });

      this.logger.debug('DM sent', { userId: params.userId });
    } catch (error) {
      this.logger.error('Failed to send DM', { error, userId: params.userId });
      throw new SlackAPIError('Failed to send DM', error);
    }
  }

  /**
   * Post message to a channel
   */
  async postToChannel(params: {
    channelId: string;
    text: string;
    blocks?: Block[];
  }): Promise<void> {
    await this.rateLimiter.acquire();

    try {
      const token = await this.getToken(params.channelId);
      this.client = new WebClient(token);

      await this.retryWithBackoff(async () => {
        await this.client.chat.postMessage({
          channel: params.channelId,
          text: params.text,
          blocks: params.blocks,
        });
      });

      this.logger.debug('Message posted to channel', {
        channelId: params.channelId,
      });
    } catch (error) {
      this.logger.error('Failed to post to channel', {
        error,
        channelId: params.channelId,
      });
      throw new SlackAPIError('Failed to post to channel', error);
    }
  }

  /**
   * Verify Slack webhook signature
   * @throws UnauthorizedError if signature is invalid
   */
  verifyWebhook(params: {
    signature: string;
    timestamp: string;
    body: string;
  }): void {
    const signingSecret = process.env.SLACK_SIGNING_SECRET!;

    // Check timestamp (prevent replay attacks)
    const requestTimestamp = parseInt(params.timestamp, 10);
    const now = Math.floor(Date.now() / 1000);

    if (Math.abs(now - requestTimestamp) > 60 * 5) {
      throw new UnauthorizedError('Request timestamp too old');
    }

    // Verify signature
    const sigBasestring = `v0:${params.timestamp}:${params.body}`;
    const mySignature =
      'v0=' +
      crypto
        .createHmac('sha256', signingSecret)
        .update(sigBasestring)
        .digest('hex');

    if (
      !crypto.timingSafeEqual(
        Buffer.from(mySignature),
        Buffer.from(params.signature)
      )
    ) {
      throw new UnauthorizedError('Invalid signature');
    }
  }

  /**
   * Retry with exponential backoff
   */
  private async retryWithBackoff<T>(
    fn: () => Promise<T>,
    maxRetries = 3
  ): Promise<T> {
    let lastError: Error;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error as Error;

        if (attempt === maxRetries) {
          throw error;
        }

        // Exponential backoff: 1s, 2s, 4s
        const delayMs = Math.pow(2, attempt - 1) * 1000;
        this.logger.warn(`Retry attempt ${attempt}/${maxRetries}`, {
          delayMs,
          error: lastError.message,
        });

        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }

    throw lastError!;
  }

  private async getToken(identifier: string): Promise<string> {
    // Get Slack token from cache (Redis)
    // Token is stored during OAuth installation
    return this.tokenCache.get(identifier);
  }
}
```

**4. OpenAIModule**
```typescript
// src/modules/openai/openai.module.ts

export class OpenAIModule {
  private client: OpenAI;

  constructor(
    private logger: Logger,
    private config: {
      apiKey: string;
      model: string; // 'gpt-4-turbo'
      maxTokens: number; // 500
      temperature: number; // 0.3
    }
  ) {
    this.client = new OpenAI({ apiKey: config.apiKey });
  }

  /**
   * Summarize standup submissions using GPT-4
   * @throws OpenAIError if API call fails after retries
   */
  async summarize(params: {
    submissions: Array<{ author: string; content: string }>;
    teamSize: number;
  }): Promise<{
    summary: string;
    blockers: Blocker[];
    highlights: Highlight[];
  }> {
    const prompt = this.buildPrompt(params.submissions, params.teamSize);

    try {
      const response = await this.retryWithBackoff(async () => {
        return await this.client.chat.completions.create({
          model: this.config.model,
          messages: [
            {
              role: 'system',
              content: SYSTEM_PROMPT,
            },
            {
              role: 'user',
              content: prompt,
            },
          ],
          max_tokens: this.config.maxTokens,
          temperature: this.config.temperature,
          response_format: { type: 'json_object' }, // Structured output
        });
      });

      const result = JSON.parse(response.choices[0].message.content!);

      this.logger.debug('OpenAI summarization complete', {
        tokenUsage: response.usage,
        blockerCount: result.blockers.length,
        highlightCount: result.highlights.length,
      });

      return {
        summary: result.summary,
        blockers: result.blockers,
        highlights: result.highlights,
      };
    } catch (error) {
      this.logger.error('OpenAI summarization failed', { error });
      throw new OpenAIError('Summarization failed', error);
    }
  }

  private buildPrompt(
    submissions: Array<{ author: string; content: string }>,
    teamSize: number
  ): string {
    const submissionsText = submissions
      .map(s => `**${s.author}:**\n${s.content}`)
      .join('\n\n');

    return `
You are summarizing a daily standup for a ${teamSize}-person engineering team.

**Submissions (${submissions.length}/${teamSize} participated):**

${submissionsText}

**Your task:**
1. Write a concise 2-3 sentence summary of what the team accomplished and is working on
2. Extract all blockers (issues preventing progress) with severity (high/medium/low)
3. Extract highlights (notable achievements or milestones)

**Output format (JSON):**
{
  "summary": "2-3 sentence overview",
  "blockers": [
    { "author": "Name", "description": "Brief description", "severity": "high|medium|low" }
  ],
  "highlights": [
    { "author": "Name", "description": "Brief description" }
  ]
}

**Guidelines:**
- Focus on actionable information
- Blockers should be specific (not just "working on X")
- Highlights should be concrete achievements
- If no blockers/highlights, return empty arrays
`;
  }

  private async retryWithBackoff<T>(
    fn: () => Promise<T>,
    maxRetries = 3
  ): Promise<T> {
    let lastError: Error;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error as Error;

        // Don't retry on 4xx errors (client errors)
        if (error.status && error.status >= 400 && error.status < 500) {
          throw error;
        }

        if (attempt === maxRetries) {
          throw error;
        }

        const delayMs = Math.pow(2, attempt - 1) * 1000;
        this.logger.warn(`OpenAI retry attempt ${attempt}/${maxRetries}`, {
          delayMs,
          error: lastError.message,
        });

        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }

    throw lastError!;
  }
}

const SYSTEM_PROMPT = `
You are an AI assistant that summarizes daily standup updates for engineering teams.
Your goal is to extract the most important information: blockers, highlights, and overall progress.
Be concise but specific. Focus on actionable insights.
Always respond with valid JSON matching the requested format.
`;
```

### 2.4 Error Handling Strategy

#### Error Type Hierarchy

```typescript
// src/errors/base.error.ts

export abstract class AppError extends Error {
  abstract readonly statusCode: number;
  abstract readonly isOperational: boolean; // Can we recover?

  constructor(
    message: string,
    public readonly context?: Record<string, any>
  ) {
    super(message);
    Error.captureStackTrace(this, this