# TEST CASES: AsyncStandup Slack Bot

## Document Control
- **Product Name**: AsyncStandup
- **Version**: 1.0
- **Last Updated**: 2024-01-18
- **Document Owner**: QA Engineering Team
- **Status**: Ready for Test Execution
- **Related Documents**: PRD v1.0, TRD v1.0, Solution Design v1.0, EPICS_AND_STORIES v1.1, TASKS v5.0
- **Test Environment**: Staging (Slack test workspace + AWS staging infrastructure)
- **Total Test Cases**: 287 test cases across 8 functional areas
- **Estimated Execution Time**: 120 hours (full regression suite)
- **Automation Coverage Target**: 75% by end of Sprint 6
- **Review Cycle**: Updated weekly during sprint execution
- **Test Data Requirements**: See Appendix A for complete test data specifications
- **Contributors**: Senior QA Engineer, Backend API Engineer, Frontend Developer, DevOps Engineer, Security Engineer
- **Sign-Off Required From**: QA Lead, Engineering Manager, Product Manager
- **Change Log**:
  - v1.0 - Initial comprehensive test case documentation covering functional, integration, performance, security, and operational testing

---

## Table of Contents
1. [How to Use This Document](#1-how-to-use-this-document)
2. [Test Strategy Overview](#2-test-strategy-overview)
3. [Test Environment Setup](#3-test-environment-setup)
4. [Test Data Requirements](#4-test-data-requirements)
5. [Epic 1: Bot Installation & Workspace Setup](#5-epic-1-bot-installation--workspace-setup)
6. [Epic 2: Standup Collection Flow](#6-epic-2-standup-collection-flow)
7. [Epic 3: Intelligent Summarization Engine](#7-epic-3-intelligent-summarization-engine)
8. [Epic 4: Summary Publishing & Notifications](#8-epic-4-summary-publishing--notifications)
9. [Epic 5: Team Management & Configuration](#9-epic-5-team-management--configuration)
10. [Epic 6: Admin Dashboard & Analytics](#10-epic-6-admin-dashboard--analytics)
11. [Epic 7: Reliability & Error Handling](#11-epic-7-reliability--error-handling)
12. [Integration Test Cases](#12-integration-test-cases)
13. [Performance Test Cases](#13-performance-test-cases)
14. [Security Test Cases](#14-security-test-cases)
15. [Accessibility Test Cases](#15-accessibility-test-cases)
16. [Operational Test Cases](#16-operational-test-cases)
17. [Regression Test Suite](#17-regression-test-suite)
18. [Automation Strategy](#18-automation-strategy)
19. [Test Execution Schedule](#19-test-execution-schedule)
20. [Defect Management](#20-defect-management)
21. [Appendix A: Test Data Specifications](#21-appendix-a-test-data-specifications)
22. [Appendix B: Test Case Template](#22-appendix-b-test-case-template)
23. [Appendix C: Browser/Device Matrix](#23-appendix-c-browserdevice-matrix)

---

## 1. HOW TO USE THIS DOCUMENT

### 1.1 Purpose

This document provides **comprehensive test cases** for AsyncStandup organized by epic, feature area, and test type. Each test case includes:

- **Unique Test Case ID** (TC-XXX format)
- **Title** describing what is being tested
- **Test Type** (Functional, Integration, E2E, Performance, Security)
- **Priority** (Critical, High, Medium, Low)
- **Preconditions** (required setup/state before test execution)
- **Test Steps** (numbered, unambiguous actions)
- **Expected Result** (single, verifiable assertion)
- **Test Data** (specific inputs, realistic volumes)
- **Automation Status** (Manual, Automated, Planned)
- **Related Stories** (links to EPICS_AND_STORIES.md)

### 1.2 Test Case Prioritization

**Critical (P0)**: Blocks release if failing. Must pass before production deployment.
- User cannot complete core workflow (install bot, submit standup, view summary)
- Data loss or corruption
- Security vulnerability
- System unavailable

**High (P1)**: Significantly impacts user experience. Should pass before release.
- Feature doesn't work as documented in PRD
- Poor error messages or confusing UX
- Performance degradation beyond SLA

**Medium (P2)**: Minor impact. Can be fixed in patch release.
- Edge cases with workarounds
- UI polish issues
- Non-critical configuration options

**Low (P3)**: Nice to have. Can be deferred.
- Rare edge cases
- Cosmetic issues
- Future enhancements

### 1.3 Test Execution Workflow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Not Started │────▶│  In Progress │────▶│    Blocked   │────▶│    Passed    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                              │                                         │
                              │                                         │
                              ▼                                         ▼
                     ┌──────────────┐                          ┌──────────────┐
                     │    Failed    │                          │    Closed    │
                     └──────────────┘                          └──────────────┘
                              │
                              │ (Defect Filed)
                              ▼
                     ┌──────────────┐
                     │   Retest     │
                     └──────────────┘
```

**Test Execution Rules:**
1. Execute Critical tests first, then High, Medium, Low
2. If a Critical test fails, STOP and file P0 defect immediately
3. If 3+ High tests fail in same area, escalate to Engineering Manager
4. Blocked tests must document blocker (environment issue, dependency, etc.)
5. Retest after defect fix must verify original test case + regression impact

### 1.4 For Different Roles

**For QA Engineers:**
- Execute test cases in priority order
- Document actual results in test management system (e.g., TestRail, Jira Xray)
- File defects with test case ID, screenshots, logs
- Update automation status as tests are automated

**For Developers:**
- Review test cases during story kickoff to understand acceptance criteria
- Use test cases to write unit/integration tests
- When fixing defects, run related test cases to verify fix

**For Product Managers:**
- Review Critical and High test cases to validate coverage of requirements
- Use test execution status to assess release readiness
- Approve risk acceptance for deferred Low priority test failures

**For DevOps Engineers:**
- Set up test environments per Test Environment Setup section
- Provide test data per Test Data Requirements section
- Monitor performance test execution and validate infrastructure SLAs

---

## 2. TEST STRATEGY OVERVIEW

### 2.1 Test Pyramid

```
                    ┌─────────────────┐
                    │   Manual E2E    │ 5% (15 cases)
                    │   Exploratory   │
                    └─────────────────┘
                  ┌───────────────────────┐
                  │   Automated E2E       │ 20% (57 cases)
                  │   (Playwright)        │
                  └───────────────────────┘
              ┌─────────────────────────────────┐
              │   Integration Tests             │ 30% (86 cases)
              │   (API + Slack SDK + DB)        │
              └─────────────────────────────────┘
          ┌─────────────────────────────────────────────┐
          │   Unit Tests                                │ 45% (129 cases)
          │   (Jest - covered in TASKS.md)              │
          └─────────────────────────────────────────────┘
```

**Test Distribution:**
- **Unit Tests (45%)**: Covered in TASKS.md (Backend/Frontend tasks). Not duplicated here.
- **Integration Tests (30%)**: API contracts, Slack SDK interactions, database operations, job queue processing
- **E2E Tests (20%)**: Complete user workflows from Slack UI through to summary publication
- **Manual/Exploratory (5%)**: Usability, edge cases, visual testing, accessibility

### 2.2 Test Types Coverage

| Test Type | Purpose | Coverage | Execution Frequency |
|-----------|---------|----------|---------------------|
| **Functional** | Verify features work per requirements | 180 cases | Every sprint |
| **Integration** | Verify component interactions | 86 cases | Every sprint |
| **E2E** | Verify complete user workflows | 57 cases | Daily (automated), Weekly (manual) |
| **Performance** | Verify SLA compliance (latency, throughput) | 24 cases | Weekly (staging), Pre-release (production-like) |
| **Security** | Verify auth, authorization, data protection | 32 cases | Every sprint + penetration test pre-release |
| **Accessibility** | Verify WCAG 2.1 AA compliance | 18 cases | Every sprint (dashboard), Pre-release (full audit) |
| **Operational** | Verify monitoring, alerting, disaster recovery | 15 cases | Pre-release + quarterly drills |

### 2.3 Entry and Exit Criteria

**Entry Criteria (Before Testing Starts):**
- [ ] Test environment provisioned and accessible
- [ ] Test data loaded per Appendix A specifications
- [ ] All stories marked "Ready for QA" with acceptance criteria
- [ ] Deployment successful (no broken builds)
- [ ] Smoke test suite passes (20 critical path tests)

**Exit Criteria (Before Release to Production):**
- [ ] 100% of Critical (P0) tests pass
- [ ] 95% of High (P1) tests pass
- [ ] All P0 defects resolved and verified
- [ ] All P1 defects resolved or explicitly accepted by Product
- [ ] Performance tests meet SLA (95th percentile < 3s for summary generation)
- [ ] Security scan passes with no High/Critical vulnerabilities
- [ ] Disaster recovery tested successfully
- [ ] Production runbook reviewed and approved by on-call team

### 2.4 Test Environment Strategy

| Environment | Purpose | Data | Refresh Frequency | Access |
|-------------|---------|------|-------------------|--------|
| **Local Dev** | Developer testing | Synthetic | On-demand | All engineers |
| **CI** | Automated tests on PR | Synthetic | Every commit | CI/CD pipeline only |
| **Staging** | QA testing, integration testing | Anonymized production subset | Weekly | QA, Engineering, Product |
| **Pre-Prod** | Production-like testing, performance testing | Anonymized production full copy | Daily | QA, DevOps, On-call |
| **Production** | Live customers | Real data | N/A | Read-only for on-call |

### 2.5 Risk-Based Testing Approach

**High-Risk Areas (Extra Test Coverage):**
1. **Slack API Integration**: External dependency, rate limits, auth token expiration
2. **OpenAI API Integration**: Cost per call, latency variance, quota limits, content filtering
3. **Job Scheduling**: Timezone handling, DST transitions, concurrent job execution
4. **Data Privacy**: PII handling, workspace isolation, access control
5. **Failure Modes**: Network timeouts, database connection loss, out-of-memory

**Testing Strategy for High-Risk Areas:**
- Negative tests outnumber positive tests 2:1
- Chaos engineering tests (kill dependencies mid-request)
- Load tests at 2x expected peak traffic
- Failure injection tests (simulate API errors, timeouts)
- Manual exploratory testing sessions (2 hours per sprint)

---

## 3. TEST ENVIRONMENT SETUP

### 3.1 Slack Test Workspace Requirements

**Staging Slack Workspace Configuration:**
- **Workspace Name**: `asyncstandup-staging`
- **Workspace URL**: `asyncstandup-staging.slack.com`
- **Admin Account**: `qa-admin@asyncstandup.com`
- **Test Users**: 15 user accounts representing different personas
  - 5 engineers (various timezones: PST, EST, UTC, IST, JST)
  - 3 engineering managers
  - 2 product managers
  - 2 designers
  - 2 QA engineers
  - 1 workspace admin
- **Test Channels**:
  - `#engineering-team` (10 members)
  - `#product-team` (5 members)
  - `#design-team` (3 members)
  - `#async-standup-test` (all members, for testing summary publishing)
  - `#async-standup-errors` (for error notifications testing)

**Bot Installation:**
- Bot user: `@AsyncStandup-Staging`
- OAuth scopes: `chat:write`, `im:write`, `im:history`, `users:read`, `channels:read`, `channels:join`
- Installed in all test channels

### 3.2 AWS Staging Infrastructure

**Required AWS Resources:**
- **ECS Fargate Cluster**: `asyncstandup-staging`
  - Service: `asyncstandup-api` (1 task, 0.5 vCPU, 1GB RAM)
- **RDS PostgreSQL**: `asyncstandup-staging-db`
  - Instance: db.t4g.micro (2 vCPU, 1GB RAM)
  - Database: `asyncstandup_staging`
  - Public accessibility: No (VPC-only)
- **ElastiCache Redis**: `asyncstandup-staging-redis`
  - Node type: cache.t4g.micro (2 vCPU, 0.5GB RAM)
- **S3 Bucket**: `asyncstandup-staging-logs`
- **CloudWatch Log Groups**: `/ecs/asyncstandup-staging`
- **Secrets Manager**:
  - `staging/slack/bot-token`
  - `staging/slack/signing-secret`
  - `staging/openai/api-key`
  - `staging/database/credentials`

**Environment Variables:**
```bash
NODE_ENV=staging
LOG_LEVEL=debug
SLACK_BOT_TOKEN=<from Secrets Manager>
SLACK_SIGNING_SECRET=<from Secrets Manager>
OPENAI_API_KEY=<from Secrets Manager>
DATABASE_URL=<from Secrets Manager>
REDIS_URL=<from ElastiCache endpoint>
SENTRY_DSN=<staging project>
DATADOG_API_KEY=<staging environment>
```

### 3.3 Test Data Setup Scripts

**Database Seed Script** (`scripts/seed-test-data.sql`):
```sql
-- Seed script executed before each test run
-- See Appendix A for complete test data specifications

-- Workspaces
INSERT INTO workspaces (id, slack_team_id, team_name, created_at) VALUES
  ('ws-test-001', 'T01ABC123', 'Engineering Team', NOW()),
  ('ws-test-002', 'T01ABC124', 'Product Team', NOW());

-- Teams
INSERT INTO teams (id, workspace_id, name, standup_time, timezone, summary_channel_id) VALUES
  ('team-eng-001', 'ws-test-001', 'Backend Squad', '09:30:00', 'America/Los_Angeles', 'C01DEF456'),
  ('team-eng-002', 'ws-test-001', 'Frontend Squad', '10:00:00', 'America/New_York', 'C01DEF457');

-- Users (15 test users with various states)
-- ... (see Appendix A for complete user data)

-- Historical standups (for analytics testing)
-- ... (see Appendix A for 30 days of historical data)
```

**Slack Workspace Setup Script** (`scripts/setup-slack-workspace.sh`):
```bash
#!/bin/bash
# Provisions test Slack workspace with channels, users, bot installation
# Run once per test cycle

export SLACK_ADMIN_TOKEN="xoxp-..."

# Create test channels
curl -X POST https://slack.com/api/conversations.create \
  -H "Authorization: Bearer $SLACK_ADMIN_TOKEN" \
  -d "name=engineering-team&is_private=false"

# Invite bot to channels
curl -X POST https://slack.com/api/conversations.invite \
  -H "Authorization: Bearer $SLACK_ADMIN_TOKEN" \
  -d "channel=C01DEF456&users=U01BOT123"

# ... (see complete script in repo)
```

### 3.4 Test User Personas

| User ID | Name | Role | Timezone | Slack ID | Typical Behavior |
|---------|------|------|----------|----------|------------------|
| `user-001` | Alice Chen | Senior Engineer | America/Los_Angeles (PST) | U01ABC001 | Always submits on time, detailed updates |
| `user-002` | Bob Smith | Engineering Manager | America/New_York (EST) | U01ABC002 | Submits early, reviews summaries |
| `user-003` | Carol Davis | Junior Engineer | Europe/London (UTC) | U01ABC003 | Sometimes late, brief updates |
| `user-004` | David Kumar | Staff Engineer | Asia/Kolkata (IST) | U01ABC004 | Submits at midnight local time |
| `user-005` | Eve Martinez | Product Manager | America/Los_Angeles (PST) | U01ABC005 | Observer role, doesn't submit |
| `user-006` | Frank Wilson | Engineer | America/Denver (MST) | U01ABC006 | Frequently reports blockers |
| `user-007` | Grace Lee | Designer | Asia/Tokyo (JST) | U01ABC007 | Early morning submitter |
| `user-008` | Henry Brown | QA Engineer | America/Chicago (CST) | U01ABC008 | Detailed testing updates |
| `user-009` | Iris Taylor | Engineer | Australia/Sydney (AEDT) | U01ABC009 | Timezone edge case (UTC+11) |
| `user-010` | Jack Anderson | DevOps | America/Los_Angeles (PST) | U01ABC010 | Infrastructure-focused updates |
| `user-011` | Karen White | Engineer (New) | America/New_York (EST) | U01ABC011 | Just joined team |
| `user-012` | Leo Garcia | Engineer (PTO) | America/Los_Angeles (PST) | U01ABC012 | On vacation this week |
| `user-013` | Maria Rodriguez | Contractor | Europe/Madrid (CET) | U01ABC013 | Part-time, submits 3x/week |
| `user-014` | Nathan Kim | Intern | America/Los_Angeles (PST) | U01ABC014 | Learning, asks questions |
| `user-015` | Olivia Patel | Workspace Admin | America/New_York (EST) | U01ABC015 | Manages bot settings |

---

## 4. TEST DATA REQUIREMENTS

### 4.1 Test Data Principles

1. **Realistic Volume**: Test with production-like data volumes (not 3 records)
2. **Boundary Values**: Include 0, 1, max, max+1 for all countable fields
3. **Edge Cases**: Empty strings, null values, special characters, emoji, very long text
4. **Timezone Coverage**: Test all major timezones, DST transitions, UTC edge cases
5. **Temporal Data**: Include past, present, future dates; weekends; holidays
6. **PII Handling**: Use synthetic PII (fake names, emails) that looks real but isn't

### 4.2 Standup Submission Test Data

**Valid Standup Updates (Positive Tests):**
```json
{
  "tc_id": "TD-STANDUP-001",
  "description": "Typical engineering standup",
  "user_id": "user-001",
  "content": "Yesterday: Fixed bug in auth flow (#1234). Today: Working on rate limiting. Blockers: None.",
  "expected_parsing": {
    "yesterday": "Fixed bug in auth flow (#1234)",
    "today": "Working on rate limiting",
    "blockers": []
  }
}

{
  "tc_id": "TD-STANDUP-002",
  "description": "Standup with blocker",
  "user_id": "user-006",
  "content": "Yesterday: Started database migration. Today: Continue migration. Blocked on: Need production DB credentials from DevOps.",
  "expected_parsing": {
    "yesterday": "Started database migration",
    "today": "Continue migration",
    "blockers": ["Need production DB credentials from DevOps"]
  }
}

{
  "tc_id": "TD-STANDUP-003",
  "description": "Minimal standup",
  "user_id": "user-003",
  "content": "Working on feature X. No blockers.",
  "expected_parsing": {
    "yesterday": null,
    "today": "Working on feature X",
    "blockers": []
  }
}

{
  "tc_id": "TD-STANDUP-004",
  "description": "Standup with emoji",
  "user_id": "user-007",
  "content": "Yesterday: 🎨 Designed new dashboard. Today: 👨‍💻 Implementing designs. Blockers: 🚫 None!",
  "expected_parsing": {
    "yesterday": "🎨 Designed new dashboard",
    "today": "👨‍💻 Implementing designs",
    "blockers": []
  }
}

{
  "tc_id": "TD-STANDUP-005",
  "description": "Standup with Slack formatting",
  "user_id": "user-008",
  "content": "Yesterday: Reviewed <@U01ABC001>'s PR. Today: Testing <https://github.com/org/repo/pull/123|PR #123>. Blockers: Waiting on *code review*.",
  "expected_parsing": {
    "yesterday": "Reviewed @Alice Chen's PR",
    "today": "Testing PR #123",
    "blockers": ["Waiting on code review"]
  }
}
```

**Invalid/Edge Case Standup Updates (Negative Tests):**
```json
{
  "tc_id": "TD-STANDUP-101",
  "description": "Empty standup",
  "user_id": "user-003",
  "content": "",
  "expected_behavior": "Bot prompts: 'Your update seems empty. Please share what you worked on yesterday, what you're working on today, and any blockers.'"
}

{
  "tc_id": "TD-STANDUP-102",
  "description": "Extremely long standup (>2000 chars)",
  "user_id": "user-001",
  "content": "Yesterday: " + ("A" * 2000),
  "expected_behavior": "Bot accepts but truncates to 2000 chars in database, warns user"
}

{
  "tc_id": "TD-STANDUP-103",
  "description": "Standup with only 'no blockers'",
  "user_id": "user-003",
  "content": "No blockers",
  "expected_behavior": "Bot prompts: 'Thanks! Can you also share what you worked on yesterday and what you're working on today?'"
}

{
  "tc_id": "TD-STANDUP-104",
  "description": "Standup with PII (email, phone)",
  "user_id": "user-001",
  "content": "Yesterday: Contacted john.doe@customer.com about bug. Today: Call customer at 555-1234. No blockers.",
  "expected_behavior": "Accepted (no PII filtering in MVP, but logged for future feature)"
}

{
  "tc_id": "TD-STANDUP-105",
  "description": "Standup with SQL injection attempt",
  "user_id": "user-001",
  "content": "Yesterday: '; DROP TABLE standups; --",
  "expected_behavior": "Accepted as plain text (parameterized queries prevent injection)"
}
```

### 4.3 Team Configuration Test Data

**Team Configurations (Boundary Value Testing):**
```json
{
  "tc_id": "TD-TEAM-001",
  "description": "Minimum team size (1 member)",
  "team_id": "team-test-001",
  "members": ["user-001"],
  "standup_time": "09:00:00",
  "timezone": "America/Los_Angeles"
}

{
  "tc_id": "TD-TEAM-002",
  "description": "Typical team size (10 members)",
  "team_id": "team-test-002",
  "members": ["user-001", "user-002", "user-003", "user-004", "user-005", "user-006", "user-007", "user-008", "user-009", "user-010"],
  "standup_time": "10:00:00",
  "timezone": "America/New_York"
}

{
  "tc_id": "TD-TEAM-003",
  "description": "Maximum team size (50 members)",
  "team_id": "team-test-003",
  "members": ["user-001", "user-002", ... "user-050"],
  "standup_time": "08:30:00",
  "timezone": "Europe/London"
}

{
  "tc_id": "TD-TEAM-004",
  "description": "Team with members in 5+ timezones",
  "team_id": "team-test-004",
  "members": ["user-001 (PST)", "user-003 (UTC)", "user-004 (IST)", "user-007 (JST)", "user-009 (AEDT)"],
  "standup_time": "09:00:00",
  "timezone": "America/Los_Angeles",
  "note": "Members span 19 hours of timezones"
}
```

### 4.4 Historical Data for Analytics Testing

**30 Days of Historical Standups:**
- 20 teams × 10 members × 22 workdays = 4,400 standup submissions
- Participation rate: 85% (660 missed standups)
- Blocker rate: 15% (660 standups with blockers)
- Late submissions: 10% (440 submitted after deadline)

**Distribution:**
- Week 1: 100% participation (new bot excitement)
- Week 2-3: 90% participation (stabilizing)
- Week 4: 80% participation (holiday week)

**Blocker Categories (for summarization testing):**
- Waiting on code review: 200 occurrences
- Blocked by another team: 150 occurrences
- Waiting on infrastructure: 100 occurrences
- Need clarification from PM: 80 occurrences
- External dependency (vendor, customer): 70 occurrences
- Other: 60 occurrences

### 4.5 Timezone Test Data

**Critical Timezone Test Cases:**
```json
{
  "tc_id": "TD-TZ-001",
  "description": "DST transition (spring forward)",
  "test_date": "2024-03-10",
  "timezone": "America/Los_Angeles",
  "standup_time": "09:00:00",
  "expected_behavior": "Standup prompt sent at 9:00am PDT (UTC-7), not 9:00am PST (UTC-8)"
}

{
  "tc_id": "TD-TZ-002",
  "description": "DST transition (fall back)",
  "test_date": "2024-11-03",
  "timezone": "America/Los_Angeles",
  "standup_time": "09:00:00",
  "expected_behavior": "Standup prompt sent at 9:00am PST (UTC-8), not 9:00am PDT (UTC-7)"
}

{
  "tc_id": "TD-TZ-003",
  "description": "Timezone with no DST",
  "test_date": "2024-06-15",
  "timezone": "Asia/Kolkata",
  "standup_time": "10:00:00",
  "expected_behavior": "Standup prompt sent at 10:00am IST (UTC+5:30) consistently"
}

{
  "tc_id": "TD-TZ-004",
  "description": "UTC timezone (edge case)",
  "test_date": "2024-06-15",
  "timezone": "UTC",
  "standup_time": "00:00:00",
  "expected_behavior": "Standup prompt sent at midnight UTC"
}

{
  "tc_id": "TD-TZ-005",
  "description": "Timezone near International Date Line",
  "test_date": "2024-06-15",
  "timezone": "Pacific/Auckland",
  "standup_time": "09:00:00",
  "expected_behavior": "Standup prompt sent at 9:00am NZST (UTC+12), summary published same day"
}
```

---

## 5. EPIC 1: BOT INSTALLATION & WORKSPACE SETUP

### 5.1 Happy Path Test Cases

#### TC-E1-001: Successful Bot Installation via Slack App Directory
- **Type**: E2E Functional
- **Priority**: Critical (P0)
- **Preconditions**: 
  - Slack workspace admin account (`qa-admin@asyncstandup.com`)
  - Bot not previously installed in workspace
  - Valid OAuth configuration in Slack App settings
- **Test Steps**:
  1. Navigate to Slack App Directory: `https://slack.com/apps`
  2. Search for "AsyncStandup"
  3. Click "Add to Slack" button
  4. Review requested permissions: `chat:write`, `im:write`, `im:history`, `users:read`, `channels:read`, `channels:join`
  5. Click "Allow" to authorize bot
  6. Wait for redirect to AsyncStandup onboarding page
- **Expected Result**: 
  - Bot successfully installed with status "Active" in Slack workspace settings
  - User redirected to `https://app.asyncstandup.com/onboarding?workspace_id={slack_team_id}&success=true`
  - Database record created in `workspaces` table with `slack_team_id`, `bot_access_token`, `installed_at`
  - Bot appears in workspace's Apps list as `@AsyncStandup`
- **Test Data**: 
  - Workspace: `asyncstandup-test-001.slack.com`
  - Admin user: `qa-admin@asyncstandup.com`
- **Automation Status**: Automated (Playwright E2E)
- **Related Stories**: US-E1-001

#### TC-E1-002: Complete Onboarding Flow - Create First Team
- **Type**: E2E Functional
- **Priority**: Critical (P0)
- **Preconditions**: 
  - Bot successfully installed (TC-E1-001 passed)
  - User on onboarding page: `https://app.asyncstandup.com/onboarding?workspace_id=T01ABC123`
  - At least 5 users in Slack workspace
  - At least 1 public channel exists
- **Test Steps**:
  1. On onboarding page, click "Create Your First Team"
  2. Enter team name: "Engineering Team"
  3. Select standup time: "9:30 AM"
  4. Select timezone: "America/Los_Angeles (PST/PDT)"
  5. Select summary channel: "#engineering-standup"
  6. Click "Add Team Members" button
  7. Select 5 users from Slack user list (checkboxes)
  8. Click "Save & Continue"
  9. Review configuration summary
  10. Click "Start Standup Schedule"
- **Expected Result**: 
  - Team created in database with `id`, `workspace_id`, `name="Engineering Team"`, `standup_time="09:30:00"`, `timezone="America/Los_Angeles"`, `summary_channel_id`
  - 5 team members inserted into `team_members` table with `team_id`, `user_id`, `joined_at`
  - Success message displayed: "🎉 Your team is all set! We'll send the first standup prompt tomorrow at 9:30 AM PST."
  - User redirected to dashboard: `https://app.asyncstandup.com/dashboard`
  - Bot posts welcome message in `#engineering-standup` channel: "👋 Hi team! AsyncStandup is now active. You'll receive a DM tomorrow at 9:30 AM to share your standup update."
- **Test Data**: 
  - Team name: "Engineering Team"
  - Members: `user-001`, `user-002`, `user-003`, `user-004`, `user-005`
  - Channel: `#engineering-standup` (ID: `C01DEF456`)
- **Automation Status**: Automated (Playwright E2E)
- **Related Stories**: US-E1-002, US-E1-003

#### TC-E1-003: OAuth Token Stored Securely in Database
- **Type**: Integration (Security)
- **Priority**: Critical (P0)
- **Preconditions**: 
  - Bot installed successfully (TC-E1-001 passed)
  - Database access to staging environment
- **Test Steps**:
  1. Query `workspaces` table: `SELECT bot_access_token FROM workspaces WHERE slack_team_id = 'T01ABC123'`
  2. Verify token is encrypted (not plaintext)
  3. Attempt to decrypt token using application decryption key
  4. Verify decrypted token starts with `xoxb-` (Slack bot token format)
  5. Make test API call to Slack using decrypted token: `POST https://slack.com/api/auth.test`
- **Expected Result**: 
  - Token stored in database is encrypted (AES-256-GCM)
  - Decryption successful using app's encryption key
  - Decrypted token format: `xoxb-{numbers}-{numbers}-{alphanumeric}`
  - Slack API call returns `200 OK` with `{"ok": true, "team_id": "T01ABC123"}`
- **Test Data**: 
  - Workspace ID: `T01ABC123`
  - Encryption key: Retrieved from AWS Secrets Manager `staging/encryption/key`
- **Automation Status**: Automated (Jest integration test)
- **Related Stories**: US-E1-001

### 5.2 Error Handling Test Cases

#### TC-E1-101: Installation Fails - User Denies Permissions
- **Type**: E2E Functional (Negative)
- **Priority**: High (P1)
- **Preconditions**: 
  - Slack workspace admin account
  - Bot not installed
- **Test Steps**:
  1. Navigate to Slack App Directory
  2. Search for "AsyncStandup"
  3. Click "Add to Slack"
  4. Review permissions
  5. Click "Cancel" or close authorization window
- **Expected Result**: 
  - User remains on Slack App Directory page
  - No database record created in `workspaces` table
  - No bot appears in workspace Apps list
  - No error message (expected behavior - user chose not to install)
- **Test Data**: N/A
- **Automation Status**: Manual (requires user interaction)
- **Related Stories**: US-E1-001

#### TC-E1-102: Installation Fails - Invalid OAuth Configuration
- **Type**: Integration (Negative)
- **Priority**: High (P1)
- **Preconditions**: 
  - Slack App configured with invalid redirect URI in staging environment
  - Workspace admin account
- **Test Steps**:
  1. Navigate to Slack App Directory
  2. Click "Add to Slack"
  3. Click "Allow"
  4. Observe redirect behavior
- **Expected Result**: 
  - Slack displays error: "Invalid redirect_uri"
  - User not redirected to AsyncStandup onboarding page
  - No database record created
  - Error logged in CloudWatch: `[ERROR] OAuth callback failed: invalid_redirect_uri`
- **Test Data**: 
  - Invalid redirect URI: `https://wrong-domain.com/oauth/callback`
- **Automation Status**: Manual (requires Slack App config change)
- **Related Stories**: US-E1-001

#### TC-E1-103: Onboarding Fails - No Public Channels Available
- **Type**: E2E Functional (Negative)
- **Priority**: Medium (P2)
- **Preconditions**: 
  - Bot installed successfully
  - Slack workspace has ZERO public channels (all channels are private)
  - User on onboarding page
- **Test Steps**:
  1. On onboarding page, click "Create Your First Team"
  2. Enter team name: "Engineering Team"
  3. Select standup time and timezone
  4. Click "Select Summary Channel" dropdown
- **Expected Result**: 
  - Dropdown shows message: "No public channels found. Please create a public channel first or contact your Slack admin."
  - "Save & Continue" button is disabled
  - Tooltip on disabled button: "A public channel is required to publish standup summaries."
  - Link displayed: "Learn how to create a public channel"
- **Test Data**: 
  - Workspace with 0 public channels
- **Automation Status**: Automated (Playwright E2E)
- **Related Stories**: US-E1-002

#### TC-E1-104: Onboarding Fails - No Team Members Selected
- **Type**: E2E Functional (Negative)
- **Priority**: High (P1)
- **Preconditions**: 
  - Bot installed successfully
  - User on onboarding "Add Team Members" step
- **Test Steps**:
  1. Complete team name, standup time, timezone, channel selection
  2. Click "Add Team Members"
  3. Do NOT select any users (leave all checkboxes unchecked)
  4. Click "Save & Continue"
- **Expected Result**: 
  - Error message displayed: "⚠️ Please select at least 1 team member."
  - Form does not submit
  - User remains on "Add Team Members" step
  - No database records created
- **Test Data**: N/A
- **Automation Status**: Automated (Playwright E2E)
- **Related Stories**: US-E1-003

#### TC-E1-105: Onboarding Fails - Duplicate Team Name
- **Type**: E2E Functional (Negative)
- **Priority**: Medium (P2)
- **Preconditions**: 
  - Bot installed successfully
  - Team already exists with name "Engineering Team" in workspace
  - User on onboarding page
- **Test Steps**:
  1. Click "Create Your First Team"
  2. Enter team name: "Engineering Team" (duplicate)
  3. Complete standup time, timezone, channel, members
  4. Click "Save & Continue"
- **Expected Result**: 
  - Error message displayed: "⚠️ A team named 'Engineering Team' already exists. Please choose a different name."
  - Form does not submit
  - User remains on team creation step
  - No duplicate database record created
  - Existing team data unchanged
- **Test Data**: 
  - Existing team: `team_id="team-001"`, `name="Engineering Team"`
- **Automation Status**: Automated (Playwright E2E)
- **Related Stories**: US-E1-002

### 5.3 Edge Case Test Cases

#### TC-E1-201: Install Bot in Workspace with 1000+ Users
- **Type**: Performance
- **Priority**: Medium (P2)
- **Preconditions**: 
  - Slack workspace with 1000+ users (use Slack Enterprise Grid test workspace)
  - Bot not installed
- **Test Steps**:
  1. Install bot via OAuth flow
  2. Navigate to onboarding page
  3. Click "Add Team Members"
  4. Measure page load time for user list
  5. Search for user "Alice Chen" using search box
  6. Select 10 users
  7. Click "Save & Continue"
- **Expected Result**: 
  - User list loads in < 2 seconds (with pagination)
  - Search functionality returns results in < 500ms
  - Pagination shows 50 users per page
  - Selected users persist across page navigation
  - Team creation completes in < 3 seconds
- **Test Data**: 
  - Workspace with 1000 users
  - Team size: 10 members
- **Automation Status**: Manual (requires Enterprise Grid workspace)
- **Related Stories**: US-E1-003

#### TC-E1-202: Install Bot in Workspace with Special Characters in Name
- **Type**: E2E Functional (Edge Case)
- **Priority**: Low (P3)
- **Preconditions**: 
  - Slack workspace with name containing special characters: `Test & Co. (2024) 🚀`
  - Bot not installed
- **Test Steps**:
  1. Install bot via OAuth flow
  2. Verify workspace name displayed correctly on onboarding page
  3. Create team and complete onboarding
- **Expected Result**: 
  - Workspace name displayed correctly (special characters and emoji preserved)
  - Database stores workspace name with proper UTF-8 encoding
  - No SQL errors or encoding issues
  - Dashboard displays workspace name correctly
- **Test Data**: 
  - Workspace name: `Test & Co. (2024) 🚀`
- **Automation Status**: Automated (Playwright E2E)
- **Related Stories**: US-E1-001

#### TC-E1-203: Create Team with Standup Time at Midnight (00:00)
- **Type**: E2E Functional (Edge Case)
- **Priority**: Medium (P2)
- **Preconditions**: 
  - Bot installed successfully
  - User on onboarding page
- **Test Steps**:
  1. Create team with standup time: "12:00 AM" (00:00)
  2. Select timezone: "UTC"
  3. Complete team setup
  4. Wait for next day at 00:00 UTC
  5. Verify standup prompt sent
- **Expected Result**: 
  - Team created successfully with `standup_time="00:00:00"`
  - Job scheduled for 00:00 UTC
  - Standup prompt sent at exactly 00:00 UTC (not 00:01 or 23:59)
  - Summary published at 00:00 UTC (assuming no submissions)
- **Test Data**: 
  - Standup time: "00:00:00"
  - Timezone: "UTC"
- **Automation Status**: Automated (integration test with mocked time)
- **Related Stories**: US-E1-002

#### TC-E1-204: Create Team with 50 Members (Maximum)
- **Type**: E2E Functional (Boundary Value)
- **Priority**: High (P1)
- **Preconditions**: 
  - Bot installed successfully
  - Workspace has 50+ users
  - User on onboarding page
- **Test Steps**:
  1. Create team
  2. Click "Add Team Members"
  3. Select exactly 50 users (maximum allowed)
  4. Click "Save & Continue"
  5. Complete onboarding
- **Expected Result**: 
  - Team created successfully with 50 members
  - All 50 members inserted into `team_members` table
  - Onboarding completes in < 5 seconds
  - Dashboard shows "50 members" for team
  - No performance degradation
- **Test Data**: 
  - Team size: 50 members (`user-001` through `user-050`)
- **Automation Status**: Automated (Playwright E2E)
- **Related Stories**: US-E1-003

#### TC-E1-205: Attempt to Create Team with 51 Members (Over Maximum)
- **Type**: E2E Functional (Boundary Value, Negative)
- **Priority**: High (P1)
- **Preconditions**: 
  - Bot installed successfully
  - Workspace has 51+ users
  - User on onboarding page
- **Test Steps**:
  1. Create team
  2. Click "Add Team Members"
  3. Attempt to select 51 users
- **Expected Result**: 
  - After selecting 50 users, remaining checkboxes become disabled
  - Message displayed: "⚠️ Maximum team size is 50 members. Please remove a member to add another."
  - "Save & Continue" button remains enabled (can proceed with 50)
  - Cannot submit form with 51+ members
- **Test Data**: 
  - Attempt to select 51 members
- **Automation Status**: Automated (Playwright E2E)
- **Related Stories**: US-E1-003

#### TC-E1-206: Reinstall Bot After Uninstallation
- **Type**: E2E Functional (Edge Case)
- **Priority**: High (P1)
- **Preconditions**: 
  - Bot was previously installed and then uninstalled
  - Historical data exists in database (teams, standups)
  - Workspace admin account
- **Test Steps**:
  1. Reinstall bot via OAuth flow
  2. Complete onboarding
  3. Navigate to dashboard
  4. Check if historical data is preserved or purged
- **Expected Result**: 
  - Bot reinstalls successfully
  - New OAuth token generated and stored
  - Historical data marked as `archived=true` in database (not deleted)
  - Dashboard shows "Start Fresh" and "Restore Previous Teams" options
  - If "Start Fresh" selected: New team IDs generated, old data remains archived
  - If "Restore Previous Teams" selected: Previous teams reactivated with same IDs
- **Test Data**: 
  - Previous installation: 2 teams, 20 members, 100 historical standups
- **Automation Status**: Manual (requires uninstall/reinstall flow)
- **Related Stories**: US-E1-001

---

## 6. EPIC 2: STANDUP COLLECTION FLOW

### 6.1 Happy Path Test Cases

#### TC-E2-001: Standup Prompt Sent at Scheduled Time
- **Type**: Integration Functional
- **Priority**: Critical (P0)
- **Preconditions**: 
  - Team configured with `standup_time="09:30:00"`, `timezone="America/Los_Angeles"`
  - Current time: 2024-01-18 09:29:59 PST
  - 5 team members: `user-001` through `user-005`
  - BullMQ job scheduler running
- **Test Steps**:
  1. Wait for system time to reach 09:30:00 PST
  2. Verify job `send-standup-prompts` triggered
  3. Check Slack API calls to send DMs
  4. Verify DMs received by all 5 team members
- **Expected Result**: 
  - Job triggered at exactly 09:30:00 PST (within 1 second)
  - 5 Slack API calls made: `POST https://slack.com/api/chat.postMessage` with `channel={user_dm_channel_id}`
  - All 5 users receive DM from `@AsyncStandup` with text: "Good morning! 🌅 Time for your daily standup. Reply here with your update."
  - Database records created in `standup_prompts` table: `team_id`, `user_id`, `prompted_at`, `status="sent"`
- **Test Data**: 
  - Team: `team-eng-001`
  - Members: `user-001`, `user-002`, `user-003`, `user-004`, `user-005`
  - Standup time: `09:30:00 PST`
- **Automation Status**: Automated (integration test with mocked time)
- **Related Stories**: US-E2-001

#### TC-E2-002: User Submits Standup via DM - Typical Format
- **Type**: E2E Functional
- **Priority**: Critical (P0)
- **Preconditions**: 
  - User `user-001` received standup prompt (TC-E2-001 passed)
  - User has open DM conversation with `@AsyncStandup`
  - Current time: 09:35:00 PST (5 minutes after prompt)
- **Test Steps**:
  1. User types in DM: "Yesterday: Fixed bug #1234. Today: Working on feature X. Blockers: None."
  2. User presses Enter to send message
  3. Wait for bot response
- **Expected Result**: 
  - Bot receives message via Slack Events API webhook
  - Message parsed and stored in `standups` table: `team_id`, `user_id`, `content`, `submitted_at="2024-01-18 09:35:00 PST"`, `status="submitted"`
  - Bot replies: "✅ Got it! Your standup has been recorded. You can update it anytime before 9:30 AM."
  - User's prompt status updated: `standup_prompts.status="completed"`
- **Test Data**: 
  - User: `user-001` (Alice Chen)
  - Standup content: "Yesterday: Fixed bug #1234. Today: Working on feature X. Blockers: None."
- **Automation Status**: Automated (Playwright + Slack API mock)
- **Related Stories**: US-E2-002

#### TC-E2-003: User Edits Standup Before Deadline
- **Type**: E2E Functional
- **Priority**: High (P1)
- **Preconditions**: 
  - User `user-001` submitted standup at 09:35:00 PST (TC-E2-002 passed)
  - Current time: 09:45:00 PST (still before 9:30 AM deadline next day)
  - Original standup: "Yesterday: Fixed bug #1234. Today: Working on feature X. Blockers: None."
- **Test Steps**:
  1. User types in same DM: "Update: Actually I'm blocked on code review for feature X."
  2. User presses Enter
  3. Wait for bot response
- **Expected Result**: 
  - Bot recognizes this is an update (not a new standup)
  - Standup record updated in database: `content="Update: Actually I'm blocked on code review for feature X."`, `updated_at="2024-01-18 09:45:00 PST"`
  - Original submission time preserved: `submitted_at="2024-01-18 09:35:00 PST"`
  - Bot replies: "✅ Your standup has been updated. Latest version: 'Update: Actually I'm blocked on code review for feature X.'"
- **Test Data**: 
  - User: `user-001`
  - Updated content: "Update: Actually I'm blocked on code review for feature X."
- **Automation Status**: Automated (Playwright + Slack API mock)
- **Related Stories**: US-E2-003

#### TC-E2-004: Bot Sends Reminder to User Who Hasn't Submitted (1 Hour Before Deadline)
- **Type**: Integration Functional
- **Priority**: High (P1)
- **Preconditions**: 
  - Team configured with `standup_time="09:30:00"`, `reminder_time="08:30:00"` (1 hour before)
  - User `user-003` received prompt at 09:30:00 PST but has NOT submitted
  - Current time: 08:30:00 PST (next day)
- **Test Steps**:
  1. Wait for system time to reach 08:30:00 PST
  2. Verify job `send-standup-reminders` triggered
  3. Check Slack API calls
  4. Verify reminder DM sent to `user-003` only (not to users who already submitted)
- **Expected Result**: 
  - Job triggered at 08:30:00 PST
  - Slack API call made: `POST https://slack.com/api/chat.postMessage` to `user-003`'s DM channel
  - Message: "⏰ Reminder: Your standup is due in 1 hour (by 9:30 AM). Reply here to submit your update."
  - Database record created: `standup_reminders` table with `user_id="user-003"`, `reminded_at="2024-01-19 08:30:00 PST"`
  - Users who already submitted do NOT receive reminder
- **Test Data**: 
  - User: `user-003` (Carol Davis - has not submitted)
  - Team: `team-eng-001`
- **Automation Status**: Automated (integration test with mocked time)
- **Related Stories**: US-E2-004

#### TC-E2-005: User Submits Standup After Receiving Reminder
- **Type**: E2E Functional
- **Priority**: High (P1)
- **Preconditions**: 
  - User `user-003` received reminder at 08:30:00 PST (TC-E2-004 passed)
  - Current time: 08:45:00 PST
- **Test Steps**:
  1. User types in DM: "Yesterday: Code review. Today: Testing. No blockers."
  2. User presses Enter
  3. Wait for bot response
- **Expected Result**: 
  - Standup recorded in database with `submitted_at="2024-01-19 08:45:00 PST"`, `submitted_after_reminder=true`
  - Bot replies: "✅ Thanks for submitting! Your standup has been recorded."
  - User's prompt status updated: `standup_prompts.status="completed"`
  - Analytics track: User responded to reminder (for future optimization)
- **Test Data**: 
  - User: `user-003`
  - Standup content: "Yesterday: Code review. Today: Testing. No blockers."
- **Automation Status**: Automated (Playwright + Slack API mock)
- **Related Stories**: US-E2-004

#### TC-E2-006: User Submits Standup with Blocker Keyword Detected
- **Type**: Integration Functional
- **Priority**: Critical (P0)
- **Preconditions**: 
  - User `user-006` received standup prompt
  - Current time: 09:35:00 PST
- **Test Steps**:
  1. User types in DM: "Yesterday: Started migration. Today: Continue migration. Blocked on: Need production DB credentials from DevOps."
  2. User presses Enter
  3. Wait for bot response
- **Expected Result**: 
  - Standup recorded in database
  - Bot detects blocker keyword: "Blocked on"
  - Bot replies: "✅ Your standup has been recorded. I noticed you mentioned a blocker: 'Need production DB credentials from DevOps.' This will be highlighted in today's summary."
  - Database field `has_blocker=true` set
  - Blocker text extracted and stored: `blocker_text="Need production DB credentials from DevOps"`
- **Test Data**: 
  - User: `user-006` (Frank Wilson)
  - Standup content: "Yesterday: Started migration. Today: Continue migration. Blocked on: Need production DB credentials from DevOps."
- **Automation Status**: Automated (integration test)
- **Related Stories**: US-E2-002, US-E3-002

### 6.2 Error Handling Test Cases

#### TC-E2-101: User Submits Empty Standup
- **Type**: E2E Functional (Negative)
- **Priority**: High (P1)
- **Preconditions**: 
  - User `user-001` received standup prompt
  - User has open DM with bot
- **Test Steps**:
  1. User types in DM: "" (empty message)
  2. User presses Enter
- **Expected Result**: 
  - Bot does NOT record standup
  - Bot replies: "⚠️ Your update seems empty. Please share: 1) What you worked on yesterday, 2) What you're working on today, 3) Any blockers."
  - No database record created
  - User can retry submission
- **Test Data**: 
  - Empty message: ""
- **Automation Status**: Automated (Playwright + Slack API mock)
- **Related Stories**: US-E2-002

#### TC-E2-102: User Submits Standup with Only Whitespace
- **Type**: E2E Functional (Negative)
- **Priority**: Medium (P2)
- **Preconditions**: 
  - User received standup prompt
- **Test Steps**:
  1. User types in DM: "   \n\n   " (only spaces and newlines)
  2. User presses Enter
- **Expected Result**: 
  - Bot treats as empty message
  - Bot replies: "⚠️ Your update seems empty. Please share: 1) What you worked on yesterday, 2) What you're working on today, 3) Any blockers."
  - No database record created
- **Test Data**: 
  - Whitespace-only message: "   \n\n   "
- **Automation Status**: Automated (integration test)
- **Related Stories**: US-E2-002

#### TC-E2-103: User Submits Extremely Long Standup (>2000 Characters)
- **Type**: E2E Functional (Boundary Value)
- **Priority**: Medium (P2)
- **Preconditions**: 
  - User received standup prompt
- **Test Steps**:
  1. User types in DM: "Yesterday: " + ("A" * 2000) (total 2010 characters)
  2. User presses Enter
- **Expected Result**: 
  - Bot accepts message but truncates to 2000 characters
  - Bot replies: "✅ Your standup has been recorded. Note: Your update was longer than 2000 characters and has been truncated. Consider being more concise!"
  - Database stores first 2000 characters
  - Truncation logged for analytics
- **Test Data**: 
  - Long message: 2010 characters
- **Automation Status**: Automated (integration test)
- **Related Stories**: US-E2-002

#### TC-E2-104: User Tries to Submit Standup After Deadline
- **Type**: E2E Functional (Negative)
- **Priority**: High (P1)
- **Preconditions**: 
  - Team configured with `standup_time="09:30:00"`, `timezone="America/Los_Angeles"`
  - User `user-003` did NOT submit standup by deadline
  - Current time: 09:31:00 PST (1 minute after deadline)
  - Summary already published
- **Test Steps**:
  1. User types in DM: "Yesterday: Worked on feature. Today: Continue feature. No blockers."
  2. User presses Enter
- **Expected Result**: 
  - Bot accepts standup and stores in database with `late_submission=true`
  - Bot replies: "✅ Your standup has been recorded, but it was submitted after the 9:30 AM deadline. It won't be included in today's summary, but will be saved for your records. Tomorrow's standup is due at 9:30 AM."
  - Standup NOT included in today's summary (already published)
  - Standup included in next day's summary (if no new submission)
- **Test Data**: 
  - User: `user-003`
  - Submission time: 09:31:00 PST (1 minute late)
- **Automation Status**: Automated (integration test with mocked time)
- **Related Stories**: US-E2-002

#### TC-E2-105: Slack API Rate Limit Exceeded When Sending Prompts
- **Type**: Integration (Negative)
- **Priority**: Critical (P0)
- **Preconditions**: 
  - Team with 50 members (maximum)
  - Standup time reached: 09:30:00 PST
  - Slack API rate limit: 1 request per second (Tier 3)
- **Test Steps**:
  1. Job `send-standup-prompts` triggered
  2. Bot attempts to send 50 DMs simultaneously
  3. Slack API returns `429 Too Many Requests` after 20 requests
  4. Observe bot behavior
- **Expected Result**: 
  - Bot detects rate limit error
  - Bot implements exponential backoff: Wait 1s, retry
  - If still rate limited: Wait 2s, retry
  - If still rate limited: Wait 4s, retry
  - All 50 prompts eventually sent within 2 minutes
  - No prompts lost
  - Error logged: `[WARN] Slack rate limit hit, retrying with backoff`
  - Alert NOT triggered (expected behavior, handled gracefully)
- **Test Data**: 
  - Team size: 50 members
- **Automation Status**: Automated (integration test with Slack API mock)
- **Related Stories**: US-E2-001

#### TC-E2-106: Slack API Returns 500 Internal Server Error
- **Type**: Integration (Negative)
- **Priority**: Critical (P0)
- **Preconditions**: 
  - Standup time reached
  - Slack API mock configured to return 500 error
- **Test Steps**:
  1. Job `send-standup-prompts` triggered
  2. Bot makes API call to send DM
  3. Slack API returns `500 Internal Server Error`
  4. Observe bot behavior
- **Expected Result**: 
  - Bot retries request 3 times with exponential backoff (1s, 2s, 4s)
  - After 3 failed attempts, bot marks prompt as `failed` in database
  - Error logged: `[ERROR] Failed to send standup prompt to user-001 after 3 retries: Slack API 500`
  - Alert triggered: "Slack API errors detected" (sent to on-call)
  - Job moves to Dead Letter Queue (DLQ) for manual review
  - User does NOT receive prompt (cannot proceed)
- **Test Data**: 
  - Mock Slack API error: 500 Internal Server Error
- **Automation Status**: Automated (integration test with Slack API mock)
- **Related Stories**: US-E2-001

#### TC-E2-107: User Sends Non-Text Message (Image, File, Emoji-Only)
- **Type**: E2E Functional (Edge Case)
- **Priority**: Medium (P2)
- **Preconditions**: 
  - User received standup prompt
- **Test Steps**:
  1. User sends image in DM (no text)
  2. Wait for bot response
- **Expected Result**: 
  - Bot ignores image (cannot parse)
  - Bot replies: "⚠️ I can only process text updates. Please describe your standup in words (what you worked on yesterday, today, and any blockers)."
  - No database record created
  - User can retry with text
- **Test Data**: 
  - Image message (no text)
- **Automation Status**: Automated (integration test)
- **Related Stories**: US-E2-002

### 6.3 Edge Case Test Cases

#### TC-E2-201: User Submits Standup Exactly at Deadline (09:30:00.000)
- **Type**: Integration (Edge Case)
- **Priority**: High (P1)
- **Preconditions**: 
  - Team deadline: 09:30:00 PST
  - User submits at exactly 09:30:00.000 PST (to the millisecond)
- **Test Steps**:
  1. Mock system time to 09:30:00.000 PST
  2. User submits standup
  3. Verify inclusion in summary
- **Expected Result**: 
  - Standup accepted (deadline is inclusive)
  - Standup included in summary
  - `late_submission=false`
  - Bot replies: "✅ Your standup has been recorded (just in time!)."
- **Test Data**: 
  - Submission time: 09:30:00.000 PST (exactly at deadline)
- **Automation Status**: Automated (integration test with mocked time)
- **Related Stories**: US-E2-002

#### TC-E2-202: User Submits Standup with Only Emoji
- **Type**: E2E Functional (Edge Case)
- **Priority**: Low (P3)
- **Preconditions**: 
  - User received standup prompt
- **Test Steps**:
  1. User types in DM: "👍 ✅ 🚀" (only emoji, no text)
  2. User presses Enter
- **Expected Result**: 
  - Bot treats as insufficient content (similar to empty message)
  - Bot replies: "⚠️ Your update seems to be only emoji. Please provide a text description of what you worked on yesterday, today, and any blockers."
  - No database record created
- **Test Data**: 
  - Emoji-only message: "👍 ✅ 🚀"
- **Automation Status**: Automated (integration test)
- **Related Stories**: US-E2-002

#### TC-E2-203: User Submits Standup with Slack Mentions (@user, #channel)
- **Type**: E2E Functional (Edge Case)
- **Priority**: Medium (P2)
- **Preconditions**: 
  - User received standup prompt
- **Test Steps**:
  1. User types in DM: "Yesterday: Reviewed <@U01ABC001>'s PR. Today: Discussing architecture in <#C01DEF456>. No blockers."
  2. User presses Enter
- **Expected Result**: 
  - Standup recorded with Slack mention syntax preserved
  - Bot replies: