# Technical Requirements Document: AsyncStandup Slack Bot

## Document Control
- **Product Name**: AsyncStandup
- **Version**: 1.0
- **Last Updated**: 2024-01-15
- **Document Owner**: Engineering & Product Leadership
- **Status**: Approved for Implementation
- **Target Launch**: Q2 2024
- **Related Documents**: PRD v1.0, Architecture Decision Records (ADRs)
- **Review Cycle**: Quarterly or upon major scope changes
- **Stakeholders**: Engineering, Product, Security, Operations, Legal

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Business Rules & Logic](#2-business-rules--logic)
3. [System Architecture](#3-system-architecture)
4. [API Specifications](#4-api-specifications)
5. [Data Models & Schema](#5-data-models--schema)
6. [Integration Requirements](#6-integration-requirements)
7. [Workflow Specifications](#7-workflow-specifications)
8. [Validation Rules](#8-validation-rules)
9. [Error Handling & Edge Cases](#9-error-handling--edge-cases)
10. [Security & Compliance](#10-security--compliance)
11. [Performance & Scalability](#11-performance--scalability)
12. [Monitoring & Observability](#12-monitoring--observability)
13. [Testing Requirements](#13-testing-requirements)
14. [Deployment & Operations](#14-deployment--operations)
15. [Open Technical Questions](#15-open-technical-questions)
16. [Appendix](#16-appendix)

---

## 1. Executive Summary

### 1.1 Technical Vision

AsyncStandup is a distributed, event-driven system that orchestrates asynchronous standup collection through Slack's API, processes submissions using NLP/AI for intelligent summarization, and publishes structured updates to team channels with high reliability (99.5% uptime SLA).

**Core Technical Principles:**
- **Boring Technology for Critical Paths**: PostgreSQL, Redis, SQS for reliability over novelty
- **Event-Driven Architecture**: Decouple collection, processing, and publishing for independent scaling
- **Fail-Safe by Default**: Every external dependency has circuit breakers, retries, and fallback strategies
- **Observable from Day One**: Structured logging, distributed tracing, business metrics instrumentation
- **API-First Design**: All functionality exposed via versioned REST APIs with OpenAPI specifications
- **Zero-Trust Security**: Every request authenticated, every input validated, every action audited

### 1.2 Key Technical Decisions

| Decision | Choice | Rationale | Trade-offs Accepted |
|----------|--------|-----------|---------------------|
| **Architecture Pattern** | Event-driven microservices | Decouples collection, processing, publishing; enables independent scaling | Increased operational complexity vs. monolith |
| **Primary Database** | PostgreSQL 15+ | Strong consistency for team/user data; JSONB for flexible standup content; mature ecosystem | Higher operational cost than managed NoSQL |
| **Message Queue** | AWS SQS + SNS | Managed service; handles 10K+ messages/sec; built-in retry/DLQ; pay-per-use | Vendor lock-in; eventual consistency model |
| **Caching Layer** | Redis 7+ (ElastiCache) | Sub-millisecond reads for Slack token lookups; session management; rate limiting | Additional infrastructure; cache invalidation complexity |
| **API Gateway** | AWS API Gateway | Managed throttling, auth, logging; WebSocket support for future real-time features | Cost at scale; 29-second timeout limit |
| **Compute** | AWS Lambda (Node.js 20) | Auto-scaling; pay-per-invocation; fast cold starts with provisioned concurrency | 15-minute execution limit; stateless design required |
| **NLP/Summarization** | OpenAI GPT-4 Turbo API | State-of-art summarization; blocker detection; no model training required | External dependency; cost per request; latency variance |
| **Observability** | DataDog | Unified logs, metrics, traces, alerts; Slack integration for on-call | Premium pricing; learning curve |
| **CI/CD** | GitHub Actions + AWS CDK | Infrastructure-as-code; preview environments; automated testing | AWS-specific; CDK learning curve |

### 1.3 System Boundaries & Scope

**IN SCOPE (MVP):**
- Slack workspace integration (OAuth, bot commands, DMs, channel posting)
- Daily standup collection via conversational DM flow
- NLP-based blocker detection and categorization
- Automated summary generation and channel posting
- Participation tracking and reminder system
- Web dashboard for team admins (configuration, analytics)
- RESTful API for all core operations

**OUT OF SCOPE (Post-MVP):**
- Multi-platform support (Teams, Discord)
- Video/audio standup submissions
- Advanced analytics (trend analysis, predictive blockers)
- Integrations with project management tools (Jira, Linear)
- Custom AI model training on team data
- Mobile native applications
- Real-time collaboration features

### 1.4 Target Metrics & SLAs

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Uptime** | 99.5% (43.8 hours downtime/year) | Synthetic monitors + real user monitoring |
| **DM Delivery Latency** | p95 < 2 seconds from scheduled time | CloudWatch metrics + custom instrumentation |
| **Summary Publication Latency** | p99 < 5 minutes from deadline | End-to-end workflow tracing |
| **API Response Time** | p95 < 500ms, p99 < 1s | API Gateway metrics + DataDog APM |
| **Data Durability** | 99.999999999% (11 nines) | AWS S3 + RDS automated backups |
| **Standup Submission Rate** | 95%+ participation by deadline | Business logic metric, tracked daily |
| **Blocker Detection Accuracy** | 90%+ precision, 85%+ recall | Manual validation sample (100 standups/week) |

---

## 2. Business Rules & Logic

### 2.1 Standup Eligibility & Participation Rules

#### 2.1.1 Decision Table: Who Must Submit a Standup?

| User State | Workspace Role | PTO Status | Last Activity | Action | Auto-Exempt? |
|------------|---------------|------------|---------------|--------|--------------|
| Active | Member/Admin | Not on PTO | <7 days ago | MUST submit | No |
| Active | Member/Admin | On PTO | Any | EXEMPT | Yes |
| Active | Bot/App | Any | Any | EXEMPT | Yes |
| Active | Guest | Not on PTO | <7 days ago | CONDITIONAL* | No |
| Onboarding (<7 days) | Member | Not on PTO | Any | EXEMPT | Yes |
| Inactive (>30 days) | Any | Any | >30 days ago | EXEMPT | Yes |
| Deactivated | Any | Any | Any | EXEMPT | Yes |

**CONDITIONAL*: Guests are exempt by default unless explicitly added to a team by admin**

#### 2.1.2 PTO Detection Logic

**Priority Order (first match wins):**
1. **Manual Flag in Bot**: User runs `/standup pto [date-range]` command
2. **Slack Status**: Status text contains keywords: `pto`, `ooo`, `vacation`, `off`, `away` (case-insensitive) + status emoji is 🏖️, 🌴, 🏝️, ✈️
3. **Calendar Integration** (Phase 2): Google Calendar "Out of Office" event
4. **Default**: Not on PTO

**Business Rules:**
- PTO status checked at 12:00am UTC daily (before reminder scheduling)
- PTO exemption expires automatically at 11:59pm on the last PTO day
- Users can pre-schedule PTO up to 90 days in advance
- PTO status visible to team admins in dashboard

#### 2.1.3 Active User Definition

A user is "active" if ANY of the following is true:
- Posted a message in the workspace in the last 14 days
- Reacted to a message in the last 14 days
- Updated their Slack profile in the last 30 days
- Explicitly marked as "active" by team admin (manual override)

**Implementation**: 
- Cache active user list per workspace in Redis (TTL: 1 hour)
- Refresh from Slack API daily at 1:00am UTC
- Fallback: If Slack API fails, use cached list from previous day

### 2.2 Standup Collection Rules

#### 2.2.1 Collection Window

| Parameter | Default Value | Configurable? | Valid Range |
|-----------|---------------|---------------|-------------|
| **Collection Start Time** | 8:00am (team timezone) | Yes | 12:00am - 11:59pm |
| **Collection Deadline** | 9:30am (team timezone) | Yes | 1 hour after start time - 11:59pm |
| **Reminder Schedule** | 8:00am (initial), 9:00am (reminder) | Yes | Up to 3 reminders |
| **Late Submission Window** | Until 5:00pm same day | Yes | 0 - 24 hours after deadline |
| **Timezone** | Workspace default OR per-team override | Yes | All IANA timezones |

**Business Rules:**
- Collection window must be at least 30 minutes
- Reminder times must be within collection window
- Late submissions accepted until 5:00pm same day (default) or disabled entirely
- All times stored in UTC, converted to team timezone for display

#### 2.2.2 Submission Format & Validation

**Required Fields:**
- At least one of: `yesterday`, `today`, `blockers` (cannot submit empty standup)
- Each field: 10-2000 characters
- Total submission: 30-5000 characters

**Optional Fields:**
- `notes` (free-form text, 0-1000 characters)
- `mood` (emoji reaction, stored but not displayed in summary)

**Validation Rules:**
```
IF all fields empty OR total_chars < 30:
  REJECT with error: "Standup too short. Please provide at least 30 characters."

IF any field > 2000 chars:
  REJECT with error: "Field 'X' too long. Maximum 2000 characters per field."

IF total_chars > 5000:
  REJECT with error: "Total standup too long. Maximum 5000 characters."

IF contains URLs > 10:
  FLAG for review (possible spam)

IF contains @channel, @here, @everyone:
  STRIP mentions (prevent notification spam)
```

#### 2.2.3 Duplicate Submission Handling

**Rule**: Last submission before deadline wins. Late submissions append to thread.

**Logic:**
```
IF submission_time <= deadline:
  OVERWRITE previous submission
  SEND confirmation: "✅ Standup updated (replaces previous submission)"

IF submission_time > deadline AND submission_time <= late_window:
  KEEP original submission in summary
  APPEND to summary thread with "🕐 Late submission from @user"
  SEND confirmation: "⚠️ Standup received late. Added to thread."

IF submission_time > late_window:
  REJECT with error: "⛔ Standup window closed. Contact your team admin."
```

### 2.3 Blocker Detection & Categorization

#### 2.3.1 Blocker Detection Algorithm

**Primary Method: NLP-based (OpenAI GPT-4 Turbo)**

**Prompt Template:**
```
You are analyzing a standup update. Extract all blockers mentioned.

A blocker is:
- Something preventing progress on a task
- A dependency on another person/team
- A technical issue requiring help
- Missing information or access

Standup text:
"""
{standup_text}
"""

Return JSON:
{
  "blockers": [
    {
      "text": "exact quote from standup",
      "category": "technical|people|process|external",
      "severity": "high|medium|low",
      "requires_action": true|false
    }
  ],
  "confidence": 0.0-1.0
}

Return empty array if no blockers found.
```

**Fallback Method: Keyword Matching (if NLP fails or low confidence)**

**High-Confidence Keywords** (95%+ precision):
- "blocked by", "waiting for", "waiting on", "can't proceed", "stuck on"
- "need help with", "need access to", "need approval"
- "dependency on", "depends on"

**Medium-Confidence Keywords** (70-90% precision):
- "issue with", "problem with", "struggling with"
- "unclear on", "confused about"
- "delayed by", "slowed down by"

**Exclusion Patterns** (false positives to ignore):
- "not blocked", "no blockers", "no issues"
- "resolved blocker", "blocker fixed"
- "will be blocked" (future tense, not current)

#### 2.3.2 Blocker Categorization

| Category | Description | Example Triggers | Default Severity |
|----------|-------------|------------------|------------------|
| **Technical** | Code issues, bugs, infrastructure | "bug in production", "API failing", "deployment broken" | Medium |
| **People** | Waiting on person/team | "waiting for review", "need @person", "blocked by design team" | High |
| **Process** | Approval, access, bureaucracy | "waiting for approval", "need access to", "paperwork pending" | Medium |
| **External** | Third-party, vendor, customer | "vendor not responding", "customer hasn't replied", "API provider down" | Low |
| **Unknown** | Cannot categorize | Any blocker that doesn't fit above | Medium |

#### 2.3.3 Severity Scoring

**Automatic Severity Assignment:**
```python
def calculate_severity(blocker):
    score = 0
    
    # High-urgency keywords
    if any(word in blocker.lower() for word in ["urgent", "critical", "production", "customer-facing", "blocking release"]):
        score += 3
    
    # People dependency (high friction)
    if blocker.category == "people":
        score += 2
    
    # Duration mentioned
    if any(phrase in blocker.lower() for phrase in ["for 2+ days", "for 3+ days", "for a week", "since monday"]):
        score += 2
    
    # Explicit "help needed"
    if any(phrase in blocker.lower() for phrase in ["need help", "urgent help", "asap"]):
        score += 1
    
    # Map score to severity
    if score >= 4:
        return "high"
    elif score >= 2:
        return "medium"
    else:
        return "low"
```

### 2.4 Summary Generation Rules

#### 2.4.1 Summary Structure

**Standard Summary Format:**
```
📊 Daily Standup Summary — [Team Name] — [Date]
Participation: X/Y submitted (Z% on time)

🚧 BLOCKERS REQUIRING ATTENTION (N)
[High severity blockers, grouped by category]

💡 HIGHLIGHTS
[Notable progress, achievements, milestones]

📋 TEAM UPDATES
[Condensed view of what everyone is working on]

⚠️ MISSING SUBMISSIONS (M)
[List of users who didn't submit]

---
🔗 View full details: [Dashboard Link]
```

#### 2.4.2 Blocker Summarization Logic

**Grouping Rules:**
1. Group by severity (high → medium → low)
2. Within severity, group by category
3. Within category, deduplicate similar blockers

**Deduplication Algorithm:**
```
FOR each blocker in category:
  IF blocker mentions same person/system as existing blocker:
    MERGE into single line: "3 people blocked by @person: [task1], [task2], [task3]"
  ELSE:
    ADD as separate line
```

**Example Output:**
```
🚧 BLOCKERS REQUIRING ATTENTION (5)

HIGH PRIORITY:
• 3 people waiting on @design-team for mockups (Alice, Bob, Carol)
• Production API returning 500 errors (Dave) — 2 days

MEDIUM PRIORITY:
• Need database migration approval (Eve)
• Staging environment down (Frank)
```

#### 2.4.3 Highlights Detection

**Highlight Criteria (any of the following):**
- Contains emoji: 🎉, 🚀, ✅, 🏆, 💯
- Keywords: "shipped", "launched", "completed", "finished", "released", "deployed"
- Phrases: "proud of", "excited about", "milestone reached"
- Pull request merged with >500 lines changed
- Mentions "customer feedback" or "user testing"

**Highlight Formatting:**
```
💡 HIGHLIGHTS
• Alice shipped the new authentication flow to production 🚀
• Bob completed the Q1 performance review process ✅
• Carol received positive feedback from 5 customers on the new UI
```

**Rules:**
- Maximum 5 highlights per summary (top 5 by engagement/importance)
- If >5 highlights detected, prioritize: shipped/launched > completed > feedback

#### 2.4.4 Team Updates Condensation

**Goal**: Reduce 10 full standups (500-1000 words each) to 100-200 word overview

**NLP Prompt:**
```
Summarize these team updates into a brief overview (100-200 words). Focus on:
1. Major themes (what is the team collectively working on?)
2. Progress indicators (how much was completed vs. started?)
3. Upcoming work (what's next?)

Updates:
{all_standup_submissions}

Format as 2-3 short paragraphs.
```

**Fallback (if NLP fails):**
- Extract all "today" tasks
- Group by keyword similarity (e.g., "authentication", "frontend", "API")
- List top 3 themes: "Team focused on: authentication (3 people), frontend redesign (2 people), bug fixes (4 people)"

### 2.5 Reminder & Escalation Rules

#### 2.5.1 Reminder Schedule

**Default Schedule:**
| Time | Type | Message | Audience |
|------|------|---------|----------|
| 8:00am | Initial DM | "Good morning! Time for your daily standup 👋" | All active users |
| 9:00am | Reminder | "⏰ Reminder: Standup due in 30 minutes" | Users who haven't submitted |
| 9:20am | Final Warning | "🚨 Last call! Standup closes in 10 minutes" | Users who haven't submitted |

**Customization Options:**
- Admins can configure 0-3 reminders per day
- Each reminder can have custom message template
- Reminders can be disabled for specific users (opt-out)

#### 2.5.2 Escalation to Team Admins

**Trigger Conditions:**
```
IF participation_rate < 80% for 3 consecutive days:
  SEND alert to team admin: "⚠️ Low standup participation (X% this week)"

IF specific_user missed 5 consecutive standups:
  SEND alert to team admin: "⚠️ @user hasn't submitted standup in 5 days"

IF blocker marked "high severity" unresolved for 2+ days:
  SEND alert to team admin: "🚨 High-priority blocker unresolved: [blocker text]"
```

**Alert Delivery:**
- DM to team admin(s)
- Optional: Email notification (if configured)
- Optional: Slack channel post (if configured)

#### 2.5.3 Missing Submission Handling

**In Summary:**
```
⚠️ MISSING SUBMISSIONS (3)
• @alice (last submitted 2 days ago)
• @bob (on vacation until Friday)
• @carol (no submission)
```

**Business Rules:**
- Show "last submitted X days ago" if >1 day
- Show PTO status if applicable
- Link to user profile for easy DM
- Do NOT publicly shame or call out users harshly

---

## 3. System Architecture

### 3.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           EXTERNAL SYSTEMS                           │
├─────────────────────────────────────────────────────────────────────┤
│  Slack API          OpenAI API         Auth0          DataDog       │
│  (Events, DMs)      (Summarization)    (User Auth)    (Observability)│
└────────┬────────────────┬───────────────┬──────────────┬────────────┘
         │                │               │              │
         │                │               │              │
┌────────▼────────────────▼───────────────▼──────────────▼────────────┐
│                       API GATEWAY (AWS)                              │
│  • Rate Limiting (1000 req/min per workspace)                       │
│  • Request Validation (OpenAPI schema)                              │
│  • JWT Authentication                                               │
│  • Request ID Generation                                            │
└────────┬─────────────────────────────────────────────────────────────┘
         │
         │
┌────────▼─────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER (AWS Lambda)                    │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │  Slack Service  │  │  Standup Service │  │  Summary Service   │ │
│  │  • Event Handler│  │  • Collection    │  │  • NLP Processing  │ │
│  │  • DM Sender    │  │  • Validation    │  │  • Publishing      │ │
│  │  • OAuth Flow   │  │  • Storage       │  │  • Formatting      │ │
│  └────────┬────────┘  └────────┬─────────┘  └─────────┬──────────┘ │
│           │                    │                       │            │
│  ┌────────▼────────┐  ┌────────▼─────────┐  ┌─────────▼──────────┐ │
│  │  User Service   │  │  Team Service    │  │  Analytics Service │ │
│  │  • CRUD         │  │  • Configuration │  │  • Metrics         │ │
│  │  • PTO Tracking │  │  • Member Mgmt   │  │  • Reporting       │ │
│  └─────────────────┘  └──────────────────┘  └────────────────────┘ │
│                                                                       │
└───────────────────────────────┬───────────────────────────────────────┘
                                │
                                │
┌───────────────────────────────▼───────────────────────────────────────┐
│                        DATA LAYER                                     │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────┐  ┌──────────────────┐  ┌─────────────────┐ │
│  │  PostgreSQL (RDS)   │  │  Redis (ElastiCache)│ │  S3 (Backups)  │ │
│  │  • Teams            │  │  • Session Cache │  │  • Audit Logs  │ │
│  │  • Users            │  │  • Rate Limiting │  │  • Exports     │ │
│  │  • Standups         │  │  • Active Users  │  │                │ │
│  │  • Summaries        │  └──────────────────┘  └─────────────────┘ │
│  └─────────────────────┘                                            │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│                     ASYNC PROCESSING (Event-Driven)                   │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  SNS Topics:                    SQS Queues:                          │
│  • standup.submitted           • reminder.queue (FIFO)               │
│  • summary.generated           • summary.queue                       │
│  • user.created                • notification.queue                  │
│                                • deadletter.queue                    │
│                                                                       │
│  EventBridge Rules:                                                  │
│  • Daily at 8:00am → Trigger reminder.lambda                        │
│  • Daily at 9:30am → Trigger summary.lambda                         │
│  • Hourly → Trigger analytics.lambda                                │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

### 3.2 Service Boundaries & Responsibilities

#### 3.2.1 Slack Service
**Responsibilities:**
- Handle all Slack API interactions (events, DMs, channel posts)
- OAuth 2.0 flow for workspace installation
- Validate Slack webhook signatures
- Manage Slack rate limits (60 req/min per workspace)

**Inputs:**
- Slack event webhooks (slash commands, DMs, reactions)
- Internal events (send DM, post summary)

**Outputs:**
- Slack API calls (send message, post to channel)
- Events published to SNS (user.messaged, command.received)

**Dependencies:**
- Slack API (external)
- User Service (internal)
- Team Service (internal)

**Error Handling:**
- Retry failed Slack API calls with exponential backoff (3 attempts)
- If user DM fails (user has DMs disabled), log warning and mark user as "unreachable"
- If channel post fails, retry 3 times, then alert admin via fallback channel

#### 3.2.2 Standup Service
**Responsibilities:**
- Accept standup submissions
- Validate submission format and content
- Store submissions in database
- Track submission status (submitted, late, missing)
- Detect duplicate submissions

**Inputs:**
- Standup submission from Slack Service
- Query requests from Summary Service

**Outputs:**
- Standup stored in database
- Event published to SNS (standup.submitted)
- Validation errors returned to caller

**Dependencies:**
- PostgreSQL (standups table)
- Redis (deduplication cache)
- User Service (validate user eligibility)

**Error Handling:**
- If database write fails, retry 3 times, then return 500 error
- If validation fails, return 400 error with specific field errors
- If duplicate submission, overwrite previous (before deadline) or reject (after deadline)

#### 3.2.3 Summary Service
**Responsibilities:**
- Fetch all standups for a team/day
- Detect blockers using NLP
- Generate summary using AI
- Format summary for Slack
- Publish summary to channel
- Track summary generation status

**Inputs:**
- Scheduled trigger (EventBridge at 9:30am)
- Manual trigger (admin dashboard)

**Outputs:**
- Summary posted to Slack channel
- Summary stored in database
- Event published to SNS (summary.generated)

**Dependencies:**
- OpenAI API (external)
- Slack Service (internal)
- Standup Service (internal)
- PostgreSQL (summaries table)

**Error Handling:**
- If OpenAI API fails, retry 2 times, then use fallback keyword-based summarization
- If Slack post fails, retry 3 times, then alert admin and store summary in database for manual posting
- If no standups submitted, post "No standups submitted today" message

#### 3.2.4 User Service
**Responsibilities:**
- CRUD operations for users
- Track user eligibility (active, PTO, onboarding)
- Manage user preferences (reminder settings, timezone)
- Sync user data from Slack (daily)

**Inputs:**
- User creation/update from Slack Service
- Query requests from other services

**Outputs:**
- User data stored in database
- Event published to SNS (user.created, user.updated)

**Dependencies:**
- PostgreSQL (users table)
- Redis (active user cache)
- Slack API (user profile sync)

**Error Handling:**
- If user not found, return 404 error
- If user data invalid, return 400 error with validation details
- If Slack sync fails, use cached data and log warning

#### 3.2.5 Team Service
**Responsibilities:**
- CRUD operations for teams
- Manage team configuration (standup time, reminders, channel)
- Manage team membership (add/remove users)
- Track team subscription status

**Inputs:**
- Team creation/update from admin dashboard
- Query requests from other services

**Outputs:**
- Team data stored in database
- Event published to SNS (team.created, team.updated)

**Dependencies:**
- PostgreSQL (teams table)
- Redis (team config cache)

**Error Handling:**
- If team not found, return 404 error
- If team data invalid, return 400 error with validation details
- If team has no active users, log warning and skip standup collection

#### 3.2.6 Analytics Service
**Responsibilities:**
- Aggregate participation metrics
- Calculate blocker resolution time
- Generate weekly/monthly reports
- Track business KPIs (MRR, churn, engagement)

**Inputs:**
- Scheduled trigger (EventBridge hourly)
- Query requests from admin dashboard

**Outputs:**
- Metrics stored in database
- Metrics pushed to DataDog
- Reports generated and stored in S3

**Dependencies:**
- PostgreSQL (read replica)
- DataDog API (external)
- S3 (report storage)

**Error Handling:**
- If metric calculation fails, log error and skip (non-critical)
- If DataDog push fails, retry 3 times, then log warning
- If S3 upload fails, retry 3 times, then alert ops team

### 3.3 Data Flow Diagrams

#### 3.3.1 Standup Collection Flow

```
┌──────────┐     1. Scheduled Event (8:00am)      ┌─────────────────┐
│EventBridge│─────────────────────────────────────>│ Reminder Lambda │
└──────────┘                                       └────────┬────────┘
                                                            │
                                                            │ 2. Fetch active users
                                                            ▼
                                                   ┌─────────────────┐
                                                   │  User Service   │
                                                   └────────┬────────┘
                                                            │
                                                            │ 3. Return eligible users
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ Reminder Lambda │
                                                   └────────┬────────┘
                                                            │
                                                            │ 4. Send DM to each user
                                                            ▼
                                                   ┌─────────────────┐
                                                   │  Slack Service  │
                                                   └────────┬────────┘
                                                            │
                                                            │ 5. DM delivered
                                                            ▼
┌──────────┐                                      ┌─────────────────┐
│   User   │<─────────────────────────────────────│   Slack App     │
└────┬─────┘                                      └─────────────────┘
     │
     │ 6. User replies with standup
     ▼
┌──────────┐     7. Webhook event                 ┌─────────────────┐
│   Slack  │─────────────────────────────────────>│  Slack Service  │
│   API    │                                      └────────┬────────┘
└──────────┘                                               │
                                                           │ 8. Parse message
                                                           ▼
                                                  ┌─────────────────┐
                                                  │ Standup Service │
                                                  └────────┬────────┘
                                                           │
                                                           │ 9. Validate & store
                                                           ▼
                                                  ┌─────────────────┐
                                                  │   PostgreSQL    │
                                                  └────────┬────────┘
                                                           │
                                                           │ 10. Publish event
                                                           ▼
                                                  ┌─────────────────┐
                                                  │    SNS Topic    │
                                                  │standup.submitted│
                                                  └─────────────────┘
```

#### 3.3.2 Summary Generation Flow

```
┌──────────┐     1. Scheduled Event (9:30am)      ┌─────────────────┐
│EventBridge│─────────────────────────────────────>│ Summary Lambda  │
└──────────┘                                       └────────┬────────┘
                                                            │
                                                            │ 2. Fetch all standups
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ Standup Service │
                                                   └────────┬────────┘
                                                            │
                                                            │ 3. Return standups
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ Summary Lambda  │
                                                   └────────┬────────┘
                                                            │
                                                            │ 4. Detect blockers (NLP)
                                                            ▼
                                                   ┌─────────────────┐
                                                   │   OpenAI API    │
                                                   └────────┬────────┘
                                                            │
                                                            │ 5. Return blockers
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ Summary Lambda  │
                                                   └────────┬────────┘
                                                            │
                                                            │ 6. Generate summary (NLP)
                                                            ▼
                                                   ┌─────────────────┐
                                                   │   OpenAI API    │
                                                   └────────┬────────┘
                                                            │
                                                            │ 7. Return summary text
                                                            ▼
                                                   ┌─────────────────┐
                                                   │ Summary Lambda  │
                                                   └────────┬────────┘
                                                            │
                                                            │ 8. Format for Slack
                                                            │ 9. Store summary
                                                            ▼
                                                   ┌─────────────────┐
                                                   │   PostgreSQL    │
                                                   └────────┬────────┘
                                                            │
                                                            │ 10. Post to channel
                                                            ▼
                                                   ┌─────────────────┐
                                                   │  Slack Service  │
                                                   └────────┬────────┘
                                                            │
                                                            │ 11. Summary posted
                                                            ▼
┌──────────┐                                      ┌─────────────────┐
│  Slack   │<─────────────────────────────────────│   Slack App     │
│ Channel  │                                      └─────────────────┘
└──────────┘
```

### 3.4 Technology Stack Details

#### 3.4.1 Compute Layer

**AWS Lambda (Node.js 20 LTS)**
- **Why Lambda?**: Auto-scaling, pay-per-invocation, fast cold starts, serverless simplicity
- **Configuration**:
  - Memory: 512 MB (most functions), 1024 MB (NLP/summarization)
  - Timeout: 30 seconds (API), 5 minutes (summarization)
  - Provisioned Concurrency: 5 instances per function (eliminate cold starts)
  - Environment: Node.js 20.x (LTS until April 2026)
  
**Alternative Considered**: ECS Fargate
- **Rejected because**: Higher operational overhead, fixed costs, overkill for MVP scale

#### 3.4.2 Database Layer

**Amazon RDS PostgreSQL 15**
- **Why PostgreSQL?**: Strong consistency, JSONB for flexible standup content, mature ecosystem, excellent query performance
- **Configuration**:
  - Instance: db.t4g.medium (2 vCPU, 4 GB RAM) for MVP
  - Storage: 100 GB GP3 SSD (3000 IOPS, 125 MB/s throughput)
  - Backups: Automated daily snapshots, 7-day retention
  - Read Replica: 1 replica for analytics queries (added in Phase 2)
  - Multi-AZ: Enabled for 99.95% availability SLA

**Schema Highlights**:
- `teams`, `users`, `standups`, `summaries`, `blockers` tables
- JSONB columns for flexible standup content (`yesterday`, `today`, `blockers`, `notes`)
- Indexes on: `team_id`, `user_id`, `date`, `created_at`
- Partitioning strategy: Partition `standups` table by month (added when >10M rows)

**Alternative Considered**: DynamoDB
- **Rejected because**: Complex query patterns (multi-field filters), need for ACID transactions, team already familiar with PostgreSQL

#### 3.4.3 Caching Layer

**Amazon ElastiCache for Redis 7**
- **Why Redis?**: Sub-millisecond reads, excellent for session management, rate limiting, active user lists
- **Configuration**:
  - Node Type: cache.t4g.micro (2 vCPU, 0.5 GB RAM) for MVP
  - Cluster Mode: Disabled (single shard sufficient for MVP)
  - Replication: 1 primary + 1 replica for high availability
  - Eviction Policy: `allkeys-lru` (least recently used)

**Cache Keys**:
- `user:active:{workspace_id}` → Set of active user IDs (TTL: 1 hour)
- `team:config:{team_id}` → Team configuration JSON (TTL: 5 minutes)
- `ratelimit:{workspace_id}:{endpoint}` → Request count (TTL: 1 minute)
- `session:{user_id}` → User session data (TTL: 24 hours)

#### 3.4.4 Message Queue

**AWS SQS + SNS**
- **Why SQS/SNS?**: Fully managed, highly scalable, built-in retry/DLQ, pay-per-use
- **Configuration**:
  - **SNS Topics**: `standup-events` (fanout to multiple subscribers)
  - **SQS Queues**: 
    - `reminder-queue` (FIFO, exactly-once delivery)
    - `summary-queue` (Standard, at-least-once delivery)
    - `notification-queue` (Standard)
    - `deadletter-queue` (catch-all for failed messages)
  - **Visibility Timeout**: 5 minutes (2x function timeout)
  - **Message Retention**: 14 days

**Event Schema**:
```json
{
  "event_type": "standup.submitted",
  "event_id": "uuid-v4",
  "timestamp": "2024-01-15T09:15:30Z",
  "workspace_id": "T12345",
  "team_id": "team-uuid",
  "user_id": "U67890",
  "payload": {
    "standup_id": "standup-uuid",
    "submission_time": "2024-01-15T09:15:30Z",
    "is_late": false
  }
}
```

#### 3.4.5 API Gateway

**AWS API Gateway (REST API)**
- **Why API Gateway?**: Managed throttling, request validation, CloudWatch integration, WebSocket support for future features
- **Configuration**:
  - **Throttling**: 1000 requests/minute per workspace (burst: 2000)
  - **Caching**: Disabled (data too dynamic)
  - **CORS**: Enabled for web dashboard
  - **Custom Domain**: `api.asyncstandup.com`
  - **Stage**: `v1` (versioned API)

**Endpoints**:
- `POST /v1/teams` → Create team
- `GET /v1/teams/{team_id}` → Get team details
- `POST /v1/standups` → Submit standup
- `GET /v1/standups?team_id={team_id}&date={date}` → List standups
- `POST /v1/summaries/generate` → Trigger summary generation (admin only)
- `GET /v1/analytics/participation?team_id={team_id}&start_date={date}&end_date={date}` → Get participation metrics

#### 3.4.6 External APIs

**Slack API**
- **Endpoints Used**:
  - `chat.postMessage` → Send DMs and channel posts
  - `users.info` → Fetch user profile
  - `users.list` → Sync workspace users
  - `conversations.history` → Fetch channel messages (for context)
  - `oauth.v2.access` → OAuth token exchange
- **Rate Limits**: 
  - Tier 1: 1 request/minute (most endpoints)
  - Tier 2: 20 requests/minute (chat.postMessage)
  - Tier 3: 50 requests/minute (users.list)
- **Error Handling**: Exponential backoff with jitter, max 3 retries

**OpenAI API (GPT-4 Turbo)**
- **Model**: `gpt-4-turbo-preview` (128K context, JSON mode)
- **Endpoints Used**:
  - `POST /v1/chat/completions` → Blocker detection, summarization
- **Rate Limits**: 
  - 10,000 tokens/minute (TPM)
  - 500 requests/minute (RPM)
- **Cost**: $0.01 per 1K input tokens, $0.03 per 1K output tokens
- **Error Handling**: Retry 2 times on 429/500 errors, fallback to keyword-based logic on 3rd failure

**Auth0 (User Authentication)**
- **Why Auth0?**: Managed user auth, social logins, MFA support, GDPR compliance
- **Configuration**:
  - **Tenant**: `asyncstandup.auth0.com`
  - **Application Type**: Single Page Application (SPA)
  - **Allowed Callbacks**: `https://app.asyncstandup.com/callback`
  - **Token Expiration**: Access tokens expire in 1 hour, refresh tokens in 30 days
- **Endpoints Used**:
  - `POST /oauth/token` → Exchange authorization code for tokens
  - `GET /userinfo` → Fetch user profile

### 3.5 Deployment Architecture

#### 3.5.1 AWS Account Structure

**Multi-Account Strategy (AWS Organizations)**:
- **Root Account**: Billing, IAM policies, organization management
- **Dev Account**: Development environment, unrestricted access for engineers
- **Staging Account**: Pre-production environment, mirrors production config
- **Production Account**: Production environment, restricted access, audit logging enabled
- **Security Account**: Centralized logging (CloudTrail, GuardDuty, Security Hub)

**Cross-Account Access**:
- Engineers have read-only access to production (via IAM roles)
- CI/CD pipeline has deployment access to all accounts (via IAM roles)
- Security team has full access to all accounts (via IAM roles)

#### 3.5.2 Network Architecture

**VPC Configuration**:
- **CIDR Block**: `10.0.0.0/16` (65,536 IPs)
- **Subnets**:
  - **Public Subnets**: `10.0.1.0/24`, `10.0.2.0/24` (NAT Gateways, Load Balancers)
  - **Private Subnets**: `10.0.11.0/24`, `10.0.12.0/24` (Lambda functions, RDS, ElastiCache)
  - **Isolated Subnets**: `10.0.21.0/24`, `10.0.22.0/24` (RDS, no internet access)
- **Availability Zones**: 2 AZs (us-east-1a, us-east-1b) for high availability
- **NAT Gateways**: 1 per AZ (for Lambda outbound internet access)

**Security Groups**:
- **Lambda SG**: Outbound to RDS, ElastiCache, internet (HTTPS only)
- **RDS SG**: Inbound from Lambda SG on port 5432
- **ElastiCache SG**: Inbound from Lambda SG on port 6379

#### 3.5.3 Infrastructure as Code (IaC)

**AWS CDK (TypeScript)**
- **Why CDK?**: Type-safe, reusable constructs, excellent for Lambda-based architectures
- **Structure**:
  ```
  infrastructure/
  ├── bin/
  │   └── app.ts                 # CDK app entry point
  ├── lib/
  │   ├── stacks/
  │   │   ├── network-stack.ts   # VPC, subnets, security groups
  │   │   ├── database-stack.ts  # RDS, ElastiCache
  │   │   ├── lambda-stack.ts    # Lambda functions, layers
  │   │   ├── api-stack.ts       # API Gateway, custom domain
  │   │   └── monitoring-stack.ts# CloudWatch, alarms
  │   └── constructs/
  │       ├── lambda-function.ts # Reusable Lambda construct
  │       └── api-endpoint.ts    # Reusable API Gateway endpoint
  ├── test/
  │   └── infrastructure.test.ts # CDK stack tests
  └── cdk.json                   # CDK configuration
  ```

**Deployment Commands**:
```bash
# Deploy to dev
npm run cdk deploy --all --profile dev

# Deploy to staging
npm run cdk deploy --all --profile staging --require-approval never

# Deploy to production (manual approval required)
npm run cdk deploy --all --profile prod
```

---

## 4. API Specifications

### 4.1 API Design Principles

**RESTful Conventions**:
- Resources are nouns (plural): `/teams`, `/users`, `/standups`
- HTTP verbs map to CRUD: `GET` (read), `POST` (create), `PUT` (update), `DELETE` (delete)
- Nested resources for relationships: `/teams/{team_id}/members`
- Query parameters for filtering/pagination: `?team_id=X&date=Y&page=1&limit=20`

**Versioning**:
- URL-based versioning: `/v1/teams`, `/v2/teams`
- Backward compatibility guaranteed within major version
- Deprecation notice 6 months before breaking changes

**Response Format**:
- Always JSON (`Content-Type: application/json`)
- Consistent envelope structure (see below)
- ISO 8601 timestamps (`2024-01-15T09:30:00Z`)
- UUIDs for all resource IDs (never sequential integers)

**Error Handling**:
- Proper HTTP status codes (see section 4.3)
- Consistent error response format (see section 4.3)
- Request IDs for traceability (in header: `X-Request-ID`)

### 4.2 API Endpoints

#### 4.2.1 Teams API

**`POST /v1/teams` — Create Team**

**Request:**
```http
POST /v1/teams HTTP/1.1
Host: api.asyncstandup.com
Authorization: Bearer {jwt_token}
Content-Type: application/json
X-Request-ID: {uuid}

{
  "name": "Engineering Team",
  "workspace_id": "T12345",
  "channel_id": "C67890",
  "timezone": "America/New_York",
  "standup_time": "09:30",
  "reminder_times": ["08:00", "09:00"],
  "late_submission_window_hours": 8
}
```

**Response (201 Created):**
```http
HTTP/1.1 201 Created
Content-Type: application/json
X-Request-ID: {uuid}

{
  "success": true,
  "data": {
    "team_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Engineering Team",
    "workspace_id": "T12345",
    "channel_id": "C67890",
    "timezone": "America/New_York",
    "standup_time": "09:30",
    "reminder_times": ["08:00", "09:00"],
    "late_submission_window_hours": 8,
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z"
  },
  "meta": {
    "request_id": "{uuid}",
    "timestamp": "2024-01-15T10:00:00Z"
  }
}
```

**Validation Rules:**
- `name`: Required, 3-100 characters, alphanumeric + spaces
- `workspace_id`: Required, matches Slack workspace ID format (`T[A-Z0-9]{8,}`)
- `channel_id`: Required, matches Slack channel ID format (`C[A-Z0-9]{8,}`)
- `timezone`: Required, valid IANA timezone (e.g., `America/New_York`)
- `standup_time`: Required, HH:MM format (24-hour), between 00:00 and 23:59
- `reminder_times`: Optional, array of 0-3 HH:MM times, all before `standup_time`
- `late_submission_window_hours`: Optional, integer 0-24, default 8

**Error Responses:**
- `400 Bad Request`: Invalid input (see section 4.3.2)
- `401 Unauthorized`: Missing or invalid JWT token
- `409 Conflict`: Team with same `workspace_id` + `channel_id` already exists
- `500 Internal Server Error`: Database error

---

**`GET /v1/teams/{team_id}` — Get Team Details**

**Request:**
```http
GET /v1/teams/550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: api.asyncstandup.com
Authorization: Bearer {jwt_token}
X-Request-ID: {uuid}
```

**Response (200 OK):**
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: {uuid}

{
  "success": true,
  "data": {
    "team_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Engineering Team",
    "workspace_id": "T12345",
    "channel_id": "C67890",
    "timezone": "America/New_York",
    "standup_time": "09:30",
    "reminder_times": ["08:00", "09:00"],
    "late_submission_window_hours": 8,
    "member_count": 12,
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:00:00Z"
  },
  "meta": {
    "request_id": "{uuid}",
    "timestamp": "2024-01-15T10:05:00Z"
  }
}
```

**Error Responses:**
- `404 Not Found`: Team does not exist
- `401 Unauthorized`: Missing or invalid JWT token
- `500 Internal Server Error`: Database error

---

**`PUT /v1/teams/{team_id}` — Update Team**

**Request:**
```http
PUT /v1/teams/550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: api.asyncstandup.com
Authorization: Bearer {jwt_token}
Content-Type: application/json
X-Request-ID: {uuid}

{
  "standup_time": "10:00",
  "reminder_times": ["08:30", "09:30"]
}
```

**Response (200 OK):**
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: {uuid}

{
  "success": true,
  "data": {
    "team_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Engineering Team",
    "workspace_id": "T12345",
    "channel_id": "C67890",
    "timezone": "America/New_York",
    "standup_time": "10:00",
    "reminder_times": ["08:30", "09:30"],
    "late_submission_window_hours": 8,
    "member_count": 12,
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T10:10:00Z"
  },
  "meta": {
    "request_id": "{uuid}",
    "timestamp": "2024-01-15T10:10:00Z"
  }
}
```

**Validation Rules:**
- All fields optional (partial update)
- Same validation rules as `POST /v1/teams`

**Error Responses:**
- `400 Bad Request`: Invalid input
- `404 Not Found`: Team does not exist
- `401 Unauthorized`: Missing or invalid JWT token
- `500 Internal Server Error`: Database error

---

**`DELETE /v1/teams/{team_id}` — Delete Team**

**Request:**
```http
DELETE /v1/teams/550e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: api.asyncstandup.com
Authorization: Bearer {jwt_token}
X-Request-ID: {uuid}
```

**Response (204 No Content):**
```http
HTTP/1.1 204 No Content
X-Request-ID: {uuid}
```

**Business Rules:**
- Soft delete (mark as deleted, don't remove from database)
- All associated standups/summaries remain accessible for 90 days
- Team can be restored within 90 days by admin

**Error Responses:**
- `404 Not Found`: Team does not exist
- `401 Unauthorized`: Missing or invalid JWT token
- `500 Internal Server Error`: Database error

---

**`GET /v1/teams/{team_id}/members` — List Team Members**

**Request:**
```http
GET /v1/teams/550e8400-e29b-41d4-a716-446655440000/members?page=1&limit=20 HTTP/1.1
Host: api.asyncstandup.com
Authorization: Bearer {jwt_token}
X-Request-ID: {uuid}
```

**Response (200 OK):**
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: {uuid}

{
  "success": true,
  "data": [
    {
      "user_id": "U12345",
      "name": "Alice Johnson",
      "email": "alice@example.com",
      "avatar_url": "https://avatars.slack-edge.com/...",
      "is_active": true,
      "is_on_pto": false,
      "joined_at": "2024-01-10T09:00:00Z"
    },
    {
      "user_id": "U67890",
      "name": "Bob Smith",
      "email": "bob@example.com",
      "avatar_url": "https://avatars.slack-edge.com/...",
      "is_active": true,
      "is_on_pto": false,
      "joined_at": "2024-01-12T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_items": 12,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  },
  "meta": {
    "request_id": "{uuid}",
    "timestamp": "2024-01-15T10:15:00Z"
  }
}
```

**Query Parameters:**
- `page`: Integer, default 1, min 1
- `limit`: Integer, default 20, min 1, max 100
- `is_active`: Boolean filter (optional)
- `is_on_pto`: Boolean filter (optional)

**Error Responses:**
- `404 Not Found`: Team does not exist
- `401 Unauthorized`: Missing or invalid JWT token
- `500 Internal Server Error`: Database error

---

#### 4.2.2 Standups API

**`POST /v1/standups` — Submit Standup**

**Request:**
```http
POST /v1/standups HTTP/1.1
Host: api.asyncstandup.com
Authorization: Bearer {jwt_token}
Content-Type: application/json
X-Request-ID: {uuid}

{
  "team_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "U12345",
  "date": "2024-01-15",
  "yesterday": "Completed authentication flow, reviewed 3 PRs",
  "today": "Working on API rate limiting, will deploy to staging",
  "blockers": "Waiting for design mockups from @design-team",
  "notes": "OOO tomorrow afternoon for dentist appointment"
}
```

**Response (201 Created):**
```http
HTTP/1.1 201 Created
Content-Type: application/json
X-Request-ID: {uuid}

{
  "success": true,
  "data": {
    "standup_id": "660e8400-e29b-41d4-a716-446655440000",
    "team_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "U12345",
    "date": "2024-01-15",
    "yesterday": "Completed authentication flow, reviewed 3 PRs",
    "today": "Working on API rate limiting, will deploy to staging",
    "blockers": "Waiting for design mockups from @design-team",
    "notes": "OOO tomorrow afternoon for dentist appointment",
    "is_late": false,
    "submitted_at": "2024-01-15T09:15:30Z",
    "created_at": "2024-01-15T09:15:30Z",
    "updated_at": "2024-01-15T09:15:30Z"
  },
  "meta": {
    "request_id": "{uuid}",
    "timestamp": "2024-01-15T09:15:30Z"
  }
}
```

**Validation Rules:**
- `team_id`: Required, valid UUID, team must exist
- `user_id`: Required, matches Slack user ID format, user must be team member
- `date`: Required, ISO 8601 date (YYYY-MM-DD), cannot be future date
- `yesterday`: Optional, 10-2000 characters
- `today`: Optional, 10-2000 characters
- `blockers`: Optional, 10-2000 characters
- `notes`: Optional, 0-1000 characters
- At least one of `yesterday`, `today`, `blockers` must be provided
- Total length: 30-5000 characters

**Business Rules:**
- If submitted before deadline: Overwrites previous submission for same date
- If submitted after deadline: Marked as `is_late: true`
- If submitted after late window closed: Rejected with 403 error

**Error Responses:**
- `400 Bad Request`: Invalid input (see section 4.3.2)
- `401 Unauthorized`: Missing or invalid JWT token
- `403 Forbidden`: Late submission window closed
- `404 Not Found`: Team or user does not exist
- `500 Internal Server Error`: Database error

---

**`GET /v1/standups` — List Standups**

**Request:**
```http
GET /v1/standups?team_id=550e8400-e29b-41d4-a716-446655440000&date=2024-01-15&page=1&limit=20 HTTP/1.1
Host: api.asyncstandup.com
Authorization: Bearer {jwt_token}
X-Request-ID: {uuid}
```

**Response (200 OK):**
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: {uuid}

{
  "success": true,
  "data": [
    {
      "standup_id": "660e8400-e29b-41d4-a716-446655440000",
      "team_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "U12345",
      "user_name": "Alice Johnson",
      "date": "2024-01-15",
      "yesterday": "Completed authentication flow, reviewed 3 PRs",
      "today": "Working on API rate limiting, will deploy to staging",
      "blockers": "Waiting for design mockups from @design-team",
      "notes": "OOO tomorrow afternoon for dentist appointment",
      "is_late": false,
      "submitted_at": "2024-01-15T09:15:30Z"
    },
    {
      "standup_id": "770e8400-e29b-41d4-a716-446655440000",
      "team_id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "U67890",
      "user_name": "Bob Smith",
      "date": "2024-01-15",
      "yesterday": "Fixed bug in payment processing",
      "today": "Code review and documentation",
      "blockers": null,
      "notes": null,
      "is_late": false,
      "submitted_at": "2024-01-15T08:45:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_items": 10,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  },
  "meta": {
    "request_id": "{uuid}",
    "timestamp": "2024-01-15T10:20:00Z"
  }
}
```

**Query Parameters:**
- `team_id`: Required, UUID
- `date`: Optional, ISO 8601 date (YYYY-MM-DD), defaults to today
- `user_id`: Optional, filter by user
- `is_late`: Optional, boolean filter
- `page`: Integer, default 1, min 1
- `limit`: Integer, default 20, min 1, max 100

**Error Responses:**
- `400 Bad Request`: Invalid query parameters
- `401 Unauthorized`: Missing or invalid JWT token
- `404 Not Found`: Team does not exist
- `500 Internal Server Error`: Database error

---

**`GET /v1/standups/{standup_id}` — Get Standup Details**

**Request:**
```http
GET /v1/standups/660e8400-e29b-41d4-a716-446655440000 HTTP/1.1
Host: api.asyncstandup.com
Authorization: Bearer {jwt_token}
X-Request-ID: {uuid}
```

**Response (200 OK):**
```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: {uuid}

{
  "success": true,
  "data": {
    "standup_id": "660e8400-e29b-41d4-a716-446655440000",
    "team_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "U12345",
    "user_name": "Alice Johnson",
    "date": "2024-01-15",
    "yesterday": "Completed authentication flow, reviewed 3 PRs",
    "today": "Working on API rate limiting, will deploy to staging",
    "blockers