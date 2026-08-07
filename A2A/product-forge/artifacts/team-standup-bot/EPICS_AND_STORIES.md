# EPICS & USER STORIES: AsyncStandup Slack Bot

## Document Control
- **Product Name**: AsyncStandup
- **Version**: 1.1 (Revised post-QA review)
- **Last Updated**: 2024-01-16
- **Document Owner**: Product Management
- **Status**: Ready for Sprint Planning (QA-Approved)
- **Related Documents**: PRD v1.0, TRD v1.0, Solution Design v1.0, QA Testability Review v1.0
- **Sprint Allocation**: 7 sprints (14 weeks) to MVP launch (revised from 6 sprints)
- **Total Story Points**: 168 points (revised from 147 after QA feedback)
- **Estimated Velocity**: 24 points/sprint
- **Review Cycle**: Weekly during sprint planning, updated as stories complete
- **QA Sign-Off**: Required on all stories before "Ready for Dev"
- **Change Log**:
  - v1.1 - Added explicit testability criteria, blocker detection SLA, timezone handling, LLM fallback stories per QA feedback
  - v1.0 - Initial epic/story breakdown

---

## Table of Contents
1. [Document Purpose & How to Use](#1-document-purpose--how-to-use)
2. [Assumptions & Dependencies](#2-assumptions--dependencies)
3. [Epic Overview & Roadmap](#3-epic-overview--roadmap)
4. [Epic 1: Bot Installation & Workspace Setup](#4-epic-1-bot-installation--workspace-setup)
5. [Epic 2: Standup Collection Flow](#5-epic-2-standup-collection-flow)
6. [Epic 3: Intelligent Summarization Engine](#6-epic-3-intelligent-summarization-engine)
7. [Epic 4: Summary Publishing & Notifications](#7-epic-4-summary-publishing--notifications)
8. [Epic 5: Team Management & Configuration](#8-epic-5-team-management--configuration)
9. [Epic 6: Admin Dashboard & Analytics](#9-epic-6-admin-dashboard--analytics)
10. [Epic 7: Reliability & Error Handling (NEW)](#10-epic-7-reliability--error-handling)
11. [Cross-Epic Dependencies](#11-cross-epic-dependencies)
12. [Story Estimation Guidelines](#12-story-estimation-guidelines)
13. [Definition of Done](#13-definition-of-done)
14. [Out of Scope for MVP](#14-out-of-scope-for-mvp)
15. [QA Testing Requirements per Epic](#15-qa-testing-requirements-per-epic)
16. [Appendix: Story Point Reference](#16-appendix-story-point-reference)

---

## 1. DOCUMENT PURPOSE & HOW TO USE

### 1.1 Purpose

This document translates the AsyncStandup PRD into **actionable, independently deliverable user stories** organized into epics. Each story includes:
- Standard user story format (As a [role]/I want [action]/So that [benefit])
- **Testable acceptance criteria** in Given/When/Then format (QA-approved)
- **Explicit test data requirements** and edge cases to validate
- Story point estimates using Fibonacci sequence (1, 2, 3, 5, 8, 13)
- Explicit dependencies and priority classification
- **QA sign-off requirements** before story can be marked "Done"

### 1.2 How Engineering Teams Should Use This Document

**For Product Owners:**
- Use Epic priorities to sequence sprints
- Reference acceptance criteria during sprint planning to clarify scope
- Update story status weekly (Not Started → In Progress → In Review → Done)

**For Developers:**
- Each story is independently deliverable — no partial implementations
- Acceptance criteria define the contract — if it's not listed, it's out of scope
- Check dependencies before starting a story (see Cross-Epic Dependencies section)
- Flag any acceptance criteria that seem ambiguous or untestable

**For QA Engineers:**
- Acceptance criteria are the test specification — write test cases directly from them
- **Test data requirements** are specified per story (see "Test Scenarios" subsections)
- **Edge cases** are explicitly called out — these are mandatory test cases, not optional
- Stories cannot be marked "Done" without QA sign-off on all ACs

**For DevOps/SREs:**
- Epic 7 (Reliability & Error Handling) defines SLAs and monitoring requirements
- Each story with external dependencies includes circuit breaker/retry requirements
- Infrastructure stories are tagged with `[INFRA]` prefix

### 1.3 Story Status Workflow

```
┌─────────────┐     ┌────────────┐     ┌─────────────┐     ┌──────────┐     ┌──────┐
│ Not Started │────▶│ In Progress│────▶│ Code Review │────▶│ QA Review│────▶│ Done │
└─────────────┘     └────────────┘     └─────────────┘     └──────────┘     └──────┘
                                              │                   │
                                              │                   │
                                              ▼                   ▼
                                         ┌─────────┐       ┌──────────┐
                                         │ Blocked │       │ QA Failed│
                                         └─────────┘       └──────────┘
```

**Status Definitions:**
- **Not Started**: Story is in backlog, dependencies not yet met
- **In Progress**: Developer actively working, branch created
- **Code Review**: PR open, awaiting peer review
- **Blocked**: Dependency issue, waiting on external team, or technical blocker
- **QA Review**: Code merged to staging, QA executing test cases
- **QA Failed**: One or more acceptance criteria not met, back to developer
- **Done**: All ACs passed, QA signed off, deployed to production

---

## 2. ASSUMPTIONS & DEPENDENCIES

### 2.1 Critical Assumptions (MUST BE VALIDATED BEFORE SPRINT 1)

These assumptions were clarified in response to QA feedback and are now **locked for MVP scope**:

#### **A1: Standup Submission Window**
- **Assumption**: Each team configures their own daily submission window (e.g., "midnight-9:30am in team's local timezone")
- **Default**: 12:00am - 9:30am in workspace's primary timezone
- **Rationale**: Teams span multiple timezones; forcing UTC would break UX
- **Impact**: Adds complexity to timezone handling (see Epic 2, Story 2.3)
- **Validation**: Confirmed with 3 pilot customers (all required custom windows)

#### **A2: Blocker Detection SLA**
- **Assumption**: We define "blocker" as any impediment preventing work progress
- **Detection Accuracy Target**:
  - **Explicit blockers** (user types "BLOCKED:" or "blocker:"): 100% capture rate
  - **Implicit blockers** (e.g., "waiting on code review"): 85% capture rate
  - **False positive rate**: <5% (e.g., "unblocked" should NOT be flagged)
- **Rationale**: QA needs measurable acceptance criteria for LLM-based features
- **Impact**: Requires labeled test dataset (500+ samples) and fallback rules
- **Validation**: Story 3.5 creates test dataset; Story 3.6 implements fallback

#### **A3: Multi-Team Support (MVP Scope)**
- **Assumption**: A single Slack workspace can have multiple standups (e.g., "Backend Team" + "Frontend Team")
- **Constraint**: Max 10 standups per workspace for MVP
- **Rationale**: Most customers have 2-4 distinct teams; unlimited standups add scaling complexity
- **Impact**: Data model must support `workspace_id` + `standup_id` composite keys
- **Validation**: Confirmed in TRD Section 5.1 (Data Models)

#### **A4: Non-Responder Escalation**
- **Assumption**: Users who miss deadline are flagged in summary, NO automatic manager escalation for MVP
- **Behavior**: Summary includes "❌ Not submitted: @alice, @bob" section
- **Rationale**: Manager escalation requires org chart integration (out of scope for MVP)
- **Impact**: Simpler implementation, but lower participation enforcement
- **Validation**: Acceptable per PRD success metric ("95% participation" doesn't require enforcement, just visibility)

#### **A5: Summarization Quality Bar**
- **Assumption**: Summary quality is measured by **blocker capture rate** and **information compression ratio**
- **Acceptance Criteria**:
  - Blocker capture: 85%+ (measured against labeled test set)
  - Compression ratio: 5:1 (e.g., 500 words of raw updates → 100-word summary)
  - Readability: 8th-grade reading level (Flesch-Kincaid score)
  - No hallucinations: 0% fabricated information (validated via human review)
- **Rationale**: QA needs objective pass/fail criteria for LLM outputs
- **Impact**: Requires human-labeled "golden dataset" for regression testing
- **Validation**: Story 3.5 creates dataset; Story 3.7 implements quality metrics

#### **A6: MVP Success Criteria (Phase 1 Only)**
- **Assumption**: MVP launch requires these metrics, NOT full PRD goals:
  - ✅ 80%+ standup submission rate (not 95%)
  - ✅ 90%+ blocker detection accuracy (explicit blockers only)
  - ✅ <5 second summary generation time (p95)
  - ✅ 99% message delivery success rate
  - ❌ "24-hour blocker resolution" tracking (Phase 2)
  - ❌ Participation trend analytics (Phase 2)
- **Rationale**: Full PRD goals require 6+ months of data; MVP validates core workflow
- **Impact**: Deprioritizes Epic 6 (Analytics) stories to Sprint 6-7
- **Validation**: Approved by VP Product in PRD review

### 2.2 External Dependencies

| Dependency | Owner | Required By | Risk Level | Mitigation |
|------------|-------|-------------|------------|------------|
| **Slack API Access** | Slack Platform Team | Sprint 1, Story 1.1 | 🟢 LOW | Use official Slack SDK; API stable since 2019 |
| **OpenAI GPT-4 Turbo API Key** | External Vendor | Sprint 3, Story 3.1 | 🟡 MEDIUM | Fallback to rule-based summarization (Story 3.6) |
| **AWS Account Setup** | DevOps Team | Sprint 1, Story 1.5 | 🟢 LOW | Standard company AWS org; 2-day setup |
| **Postgres RDS Instance** | DevOps Team | Sprint 1, Story 1.6 | 🟢 LOW | Use Terraform template; 1-day provisioning |
| **Redis ElastiCache Cluster** | DevOps Team | Sprint 2, Story 2.6 | 🟢 LOW | Use Terraform template; 1-day provisioning |
| **DataDog Account** | Observability Team | Sprint 1, Story 1.7 | 🟢 LOW | Company-wide license; API keys available |
| **Stripe Account (Billing)** | Finance Team | Sprint 6, Story 6.4 | 🟡 MEDIUM | Out of critical path; can launch without billing |
| **Legal Review (OAuth Scopes)** | Legal Team | Sprint 1, Story 1.2 | 🟡 MEDIUM | 1-week review cycle; start in Sprint 0 |

### 2.3 Technical Dependencies (Internal)

```
Epic 1 (Setup) ───┐
                  ├──▶ Epic 2 (Collection) ───┐
Epic 5 (Config)───┘                           ├──▶ Epic 3 (Summarization) ──▶ Epic 4 (Publishing)
                                               │
Epic 7 (Reliability) ──────────────────────────┘
```

**Critical Path**: Epic 1 → Epic 2 → Epic 3 → Epic 4 (must be sequential)
**Parallel Tracks**: Epic 5 (Config) and Epic 7 (Reliability) can develop in parallel after Epic 1

### 2.4 Data Dependencies

| Data Type | Source | Required For | Format | Validation |
|-----------|--------|--------------|--------|------------|
| **Slack Workspace Tokens** | OAuth flow (Story 1.2) | All Slack API calls | Encrypted in DB | Rotate every 90 days |
| **Team Timezone Mapping** | Slack Workspace API | Submission window calculation | IANA timezone strings | Validate against IANA DB |
| **Blocker Training Dataset** | Manual labeling (Story 3.5) | LLM fine-tuning / fallback rules | JSONL (500+ samples) | Inter-rater agreement >90% |
| **User Participation History** | Daily standup submissions | Non-responder detection | PostgreSQL time-series | 90-day retention |
| **LLM Prompt Templates** | Product/Engineering (Story 3.2) | Summarization quality | Markdown with variables | Version-controlled in Git |

---

## 3. EPIC OVERVIEW & ROADMAP

### 3.1 Epic Prioritization & Sequencing

| Epic # | Epic Name | Priority | Sprint Allocation | Story Points | Dependencies | Success Metric |
|--------|-----------|----------|-------------------|--------------|--------------|----------------|
| **Epic 1** | Bot Installation & Workspace Setup | 🔴 P0 | Sprint 1 | 21 pts | None | 100% successful OAuth flows |
| **Epic 2** | Standup Collection Flow | 🔴 P0 | Sprint 2-3 | 34 pts | Epic 1 | 90% message delivery rate |
| **Epic 3** | Intelligent Summarization Engine | 🔴 P0 | Sprint 3-4 | 42 pts | Epic 2 | 85% blocker detection accuracy |
| **Epic 4** | Summary Publishing & Notifications | 🔴 P0 | Sprint 4-5 | 28 pts | Epic 3 | 95% summary publish success |
| **Epic 5** | Team Management & Configuration | 🟡 P1 | Sprint 2, 5 | 18 pts | Epic 1 | Support 10 teams/workspace |
| **Epic 7** | Reliability & Error Handling | 🟡 P1 | Sprint 3-6 | 19 pts | Epic 2 | 99% uptime SLA |
| **Epic 6** | Admin Dashboard & Analytics | 🟢 P2 | Sprint 6-7 | 6 pts | Epic 4 | 80% admin adoption |

**Sprint Roadmap (14 weeks to MVP)**:

```
Sprint 1 (Weeks 1-2): Epic 1 Complete
  ├─ OAuth flow working
  ├─ Database schema deployed
  └─ Local dev environment ready

Sprint 2 (Weeks 3-4): Epic 2 Start + Epic 5 Start
  ├─ DM collection working (no summarization yet)
  ├─ Basic team configuration
  └─ Redis job queue operational

Sprint 3 (Weeks 5-6): Epic 2 Complete + Epic 3 Start
  ├─ Submission window enforcement
  ├─ LLM integration working
  └─ Circuit breakers implemented

Sprint 4 (Weeks 7-8): Epic 3 Complete + Epic 4 Start
  ├─ Blocker detection at 85% accuracy
  ├─ Summary formatting polished
  └─ Channel publishing working

Sprint 5 (Weeks 9-10): Epic 4 Complete + Epic 5 Complete
  ├─ Non-responder notifications
  ├─ Multi-team support validated
  └─ Timezone handling tested

Sprint 6 (Weeks 11-12): Epic 7 Complete + Epic 6 Start
  ├─ Retry logic hardened
  ├─ Monitoring dashboards live
  └─ Basic analytics available

Sprint 7 (Weeks 13-14): Epic 6 Complete + Launch Prep
  ├─ Admin dashboard polished
  ├─ Beta customer onboarding
  └─ Production launch 🚀
```

### 3.2 Epic Definitions

#### **Epic 1: Bot Installation & Workspace Setup** (21 pts, Sprint 1)
**Goal**: Enable Slack workspace admins to install AsyncStandup bot via OAuth and configure initial settings.

**User Value**: "As a Slack workspace admin, I can install the bot in under 5 minutes and have it ready to collect standups."

**Completion Criteria**:
- ✅ OAuth flow redirects to Slack, requests correct scopes, stores tokens securely
- ✅ Database schema deployed to production with migrations
- ✅ Bot appears in workspace's "Apps" directory after installation
- ✅ Health check endpoint returns 200 OK

**Key Stories**: 1.1 (OAuth), 1.2 (Permissions), 1.3 (Onboarding), 1.4 (Database), 1.5 (Infra)

---

#### **Epic 2: Standup Collection Flow** (34 pts, Sprint 2-3)
**Goal**: Bot sends daily DM prompts to team members, collects standup submissions, and stores them for summarization.

**User Value**: "As a team member, I receive a DM prompt every morning and can reply conversationally without rigid forms."

**Completion Criteria**:
- ✅ Bot sends DMs at configured time (e.g., 8:00am team timezone)
- ✅ Users can reply with free-form text (no forms/buttons required)
- ✅ Submissions stored in database with timestamp, user_id, standup_id
- ✅ Non-responders tracked by deadline (e.g., 9:30am)
- ✅ Handles 100 concurrent DM conversations without errors

**Key Stories**: 2.1 (DM Prompt), 2.2 (Submission Parsing), 2.3 (Timezone Handling), 2.4 (Deadline Tracking), 2.5 (Concurrent Users)

---

#### **Epic 3: Intelligent Summarization Engine** (42 pts, Sprint 3-4)
**Goal**: Process collected standup submissions using LLM to generate concise summaries with blockers/highlights surfaced.

**User Value**: "As an engineering manager, I get a 2-minute read summary that highlights blockers without reading 10 individual updates."

**Completion Criteria**:
- ✅ LLM integration (OpenAI GPT-4 Turbo) processes submissions
- ✅ Blocker detection accuracy: 85%+ (explicit blockers 100%, implicit 85%)
- ✅ Summary compression ratio: 5:1 (500 words → 100 words)
- ✅ Fallback to rule-based summarization if LLM fails
- ✅ Summary generation time <5 seconds (p95)
- ✅ No hallucinations (0% fabricated information)

**Key Stories**: 3.1 (LLM Integration), 3.2 (Prompt Engineering), 3.3 (Blocker Extraction), 3.4 (Summary Formatting), 3.5 (Test Dataset), 3.6 (Fallback Logic), 3.7 (Quality Metrics)

---

#### **Epic 4: Summary Publishing & Notifications** (28 pts, Sprint 4-5)
**Goal**: Publish generated summaries to configured Slack channel at deadline time (e.g., 9:30am) with non-responder alerts.

**User Value**: "As a team member, I see the daily standup summary in our team channel at 9:30am sharp, with blockers highlighted."

**Completion Criteria**:
- ✅ Summary posted to correct channel at exact deadline time
- ✅ Markdown formatting renders correctly in Slack
- ✅ Blockers highlighted with emoji (🚨) and @-mentions
- ✅ Non-responders listed with ❌ emoji
- ✅ Summary includes link to "View Raw Updates" (future: web view)
- ✅ Handles channel permission errors gracefully

**Key Stories**: 4.1 (Channel Publishing), 4.2 (Markdown Formatting), 4.3 (Blocker Highlighting), 4.4 (Non-Responder List), 4.5 (Error Handling)

---

#### **Epic 5: Team Management & Configuration** (18 pts, Sprint 2, 5)
**Goal**: Enable workspace admins to create multiple standups, configure submission windows, and manage team membership.

**User Value**: "As a workspace admin, I can set up separate standups for Backend and Frontend teams with different schedules."

**Completion Criteria**:
- ✅ Admins can create up to 10 standups per workspace
- ✅ Each standup has configurable: name, channel, submission window, timezone
- ✅ Admins can add/remove team members from standups
- ✅ Changes take effect next business day (no mid-day disruptions)
- ✅ Configuration persisted in database with audit log

**Key Stories**: 5.1 (Standup Creation), 5.2 (Team Membership), 5.3 (Schedule Configuration), 5.4 (Timezone Selection)

---

#### **Epic 6: Admin Dashboard & Analytics** (6 pts, Sprint 6-7)
**Goal**: Provide web dashboard for admins to view participation trends, summary archives, and team health metrics.

**User Value**: "As an engineering manager, I can see which team members consistently miss standups and identify participation trends."

**Completion Criteria**:
- ✅ Dashboard shows: participation rate (last 7 days), blocker count, summary archive
- ✅ Admins can download summary history as CSV
- ✅ Dashboard accessible via web (not Slack-only)
- ✅ Data refreshes every 24 hours (not real-time)

**Key Stories**: 6.1 (Participation Metrics), 6.2 (Summary Archive), 6.3 (CSV Export)

---

#### **Epic 7: Reliability & Error Handling** (19 pts, Sprint 3-6)
**Goal**: Ensure 99% uptime, graceful degradation, and comprehensive error recovery for all external dependencies.

**User Value**: "As a user, the bot works reliably even when Slack or OpenAI APIs are slow or down."

**Completion Criteria**:
- ✅ Circuit breakers on Slack API, OpenAI API, database
- ✅ Exponential backoff retry logic (3 attempts, 1s/2s/4s delays)
- ✅ Dead letter queue for failed jobs
- ✅ Monitoring alerts for: API errors, job failures, high latency
- ✅ Graceful degradation: rule-based summarization if LLM fails

**Key Stories**: 7.1 (Circuit Breakers), 7.2 (Retry Logic), 7.3 (Dead Letter Queue), 7.4 (Monitoring), 7.5 (Graceful Degradation)

---

## 4. EPIC 1: BOT INSTALLATION & WORKSPACE SETUP

**Epic Goal**: Enable Slack workspace admins to install AsyncStandup bot via OAuth and configure initial settings.

**Epic Owner**: Backend API Engineer + DevOps Engineer

**Sprint Allocation**: Sprint 1 (Weeks 1-2)

**Total Story Points**: 21 points

**Success Metrics**:
- 100% successful OAuth flows (no token refresh failures)
- Database migrations run without errors
- Health check endpoint responds <200ms

---

### Story 1.1: Implement Slack OAuth 2.0 Flow

**Story ID**: AS-1.1  
**Priority**: 🔴 P0 (Blocker for all other stories)  
**Story Points**: 5  
**Assignee**: Backend API Engineer  
**Dependencies**: None  
**QA Complexity**: Medium (requires Slack test workspace)

#### User Story
```
AS A Slack workspace admin
I WANT to install the AsyncStandup bot via a "Add to Slack" button
SO THAT the bot can access my workspace to send DMs and post summaries
```

#### Acceptance Criteria

**AC 1.1.1**: OAuth Initiation
```gherkin
GIVEN I am a Slack workspace admin
WHEN I click the "Add to Slack" button on asyncstandup.com
THEN I am redirected to Slack's OAuth authorization page
  AND the page requests these scopes:
    - chat:write (post messages)
    - im:write (send DMs)
    - users:read (get user info)
    - channels:read (list channels)
    - commands (slash commands)
  AND the redirect_uri is https://api.asyncstandup.com/auth/slack/callback
```

**AC 1.1.2**: OAuth Token Exchange
```gherkin
GIVEN I approve the OAuth request in Slack
WHEN Slack redirects to our callback URL with a temporary code
THEN our backend exchanges the code for an access token
  AND stores the token encrypted in the database
  AND associates the token with the workspace_id (team_id from Slack)
  AND the token includes: access_token, bot_user_id, team_id, team_name
```

**AC 1.1.3**: OAuth Error Handling
```gherkin
GIVEN I deny the OAuth request in Slack
WHEN Slack redirects to our callback URL with error=access_denied
THEN I see a user-friendly error page: "Installation cancelled. You can try again anytime."
  AND no database records are created
  AND the error is logged to DataDog with context: workspace_id, user_id, error_code
```

**AC 1.1.4**: Token Refresh (Future-Proofing)
```gherkin
GIVEN a workspace has an expired access token (>90 days old)
WHEN we attempt to call Slack API
THEN we detect the 401 Unauthorized error
  AND trigger token refresh flow (if refresh_token available)
  AND retry the original API call
  AND log token refresh event to DataDog
```

#### Test Scenarios (QA Must Validate)

**Test Scenario 1.1.A**: Happy Path OAuth
- **Setup**: Create test Slack workspace
- **Steps**:
  1. Click "Add to Slack" button
  2. Approve all requested scopes
  3. Verify redirect to success page
- **Expected**: Token stored in DB, bot appears in workspace

**Test Scenario 1.1.B**: Partial Scope Approval
- **Setup**: Test workspace with restricted admin permissions
- **Steps**:
  1. Click "Add to Slack"
  2. Deny `channels:read` scope
  3. Attempt to complete OAuth
- **Expected**: OAuth fails with clear error message

**Test Scenario 1.1.C**: Network Timeout During Token Exchange
- **Setup**: Simulate Slack API timeout (use network throttling)
- **Steps**:
  1. Complete OAuth approval
  2. Inject 30-second delay on Slack token endpoint
  3. Verify timeout handling
- **Expected**: User sees "Installation in progress, please wait..." then retry

**Test Scenario 1.1.D**: Duplicate Installation
- **Setup**: Workspace already has bot installed
- **Steps**:
  1. Attempt to install bot again
  2. Complete OAuth flow
- **Expected**: Existing token updated (not duplicated), user notified "Bot reinstalled successfully"

**Test Scenario 1.1.E**: SQL Injection Attack
- **Setup**: Malicious actor crafts OAuth callback with SQL in `team_name`
- **Steps**:
  1. Send callback with `team_name='; DROP TABLE workspaces; --`
  2. Verify token storage
- **Expected**: Input sanitized, no SQL execution, error logged

#### Edge Cases (Must Be Tested)
- ❌ User clicks "Back" button during OAuth flow
- ❌ OAuth callback called twice (race condition)
- ❌ Workspace with non-ASCII characters in team_name
- ❌ Token exchange returns 500 error from Slack
- ❌ Database write fails after successful token exchange

#### Technical Implementation Notes
```javascript
// Example OAuth callback handler
app.get('/auth/slack/callback', async (req, res) => {
  const { code, error } = req.query;
  
  if (error) {
    logger.error('OAuth denied', { error, ip: req.ip });
    return res.render('oauth-error', { message: 'Installation cancelled' });
  }
  
  try {
    // Exchange code for token
    const response = await slack.oauth.v2.access({
      client_id: process.env.SLACK_CLIENT_ID,
      client_secret: process.env.SLACK_CLIENT_SECRET,
      code,
      redirect_uri: process.env.OAUTH_REDIRECT_URI
    });
    
    // Store encrypted token
    await db.workspaces.upsert({
      workspace_id: response.team.id,
      access_token: encrypt(response.access_token),
      bot_user_id: response.bot_user_id,
      team_name: sanitize(response.team.name),
      installed_at: new Date()
    });
    
    res.redirect('/onboarding?workspace_id=' + response.team.id);
  } catch (err) {
    logger.error('OAuth token exchange failed', { error: err, code });
    res.status(500).render('oauth-error', { message: 'Installation failed. Please try again.' });
  }
});
```

#### Definition of Done
- [ ] Code reviewed and approved by 2 engineers
- [ ] All 5 test scenarios pass in staging environment
- [ ] Edge cases handled with appropriate error messages
- [ ] Security review completed (SQL injection, XSS, CSRF)
- [ ] DataDog logging configured for OAuth events
- [ ] QA signed off on all acceptance criteria
- [ ] Documentation updated: `/docs/oauth-flow.md`

---

### Story 1.2: Request Minimum Required Slack Permissions

**Story ID**: AS-1.2  
**Priority**: 🔴 P0  
**Story Points**: 2  
**Assignee**: Backend API Engineer  
**Dependencies**: Story 1.1  
**QA Complexity**: Low

#### User Story
```
AS A security-conscious Slack admin
I WANT the bot to request only the minimum permissions needed
SO THAT I can trust the bot won't access sensitive data unnecessarily
```

#### Acceptance Criteria

**AC 1.2.1**: Scope Documentation
```gherkin
GIVEN I am reviewing the OAuth permission request
WHEN I see the list of requested scopes
THEN each scope includes a plain-English explanation:
  - chat:write → "Post standup summaries to your team channel"
  - im:write → "Send daily standup prompts via DM"
  - users:read → "Get team member names and timezones"
  - channels:read → "Let you choose which channel to post summaries"
  - commands → "Enable /standup slash command"
AND no additional scopes are requested
```

**AC 1.2.2**: Principle of Least Privilege
```gherkin
GIVEN the bot's functionality requirements
WHEN we design the OAuth scope list
THEN we do NOT request:
  - channels:history (reading message history)
  - files:read (accessing uploaded files)
  - users:write (modifying user profiles)
  - admin scopes (workspace administration)
AND we document why each scope is necessary in /docs/permissions.md
```

**AC 1.2.3**: Legal Review Sign-Off
```gherkin
GIVEN we have finalized the OAuth scope list
WHEN we submit for legal review
THEN legal team confirms:
  - Scopes comply with GDPR data minimization principle
  - Privacy policy accurately describes data access
  - No excessive permissions requested
AND legal approval documented in Jira ticket AS-1.2
```

#### Test Scenarios

**Test Scenario 1.2.A**: Scope Minimization Audit
- **Setup**: Compare requested scopes to competitor bots (Geekbot, Standuply)
- **Steps**:
  1. Install competitor bots in test workspace
  2. Document their requested scopes
  3. Verify we request fewer or equal scopes
- **Expected**: Our bot requests ≤ competitor scope count

**Test Scenario 1.2.B**: Functionality Without Excessive Scopes
- **Setup**: Test workspace with only our requested scopes
- **Steps**:
  1. Complete full standup flow (collect → summarize → publish)
  2. Verify no "insufficient permissions" errors
- **Expected**: All features work with requested scopes

#### Definition of Done
- [ ] Legal team approved scope list (email confirmation)
- [ ] Privacy policy updated to reflect scope usage
- [ ] `/docs/permissions.md` created with scope justifications
- [ ] QA verified functionality works with minimal scopes
- [ ] Security team reviewed (no excessive permissions)

---

### Story 1.3: Build Post-Installation Onboarding Flow

**Story ID**: AS-1.3  
**Priority**: 🟡 P1  
**Story Points**: 3  
**Assignee**: Full Stack Developer  
**Dependencies**: Story 1.1  
**QA Complexity**: Medium

#### User Story
```
AS A new workspace admin who just installed the bot
I WANT a guided setup wizard
SO THAT I can configure my first standup in under 2 minutes
```

#### Acceptance Criteria

**AC 1.3.1**: Onboarding Wizard UI
```gherkin
GIVEN I just completed OAuth installation
WHEN I am redirected to the onboarding page
THEN I see a 3-step wizard:
  Step 1: "Create Your First Standup"
    - Input: Standup name (e.g., "Engineering Team")
    - Input: Select channel for summaries (dropdown of workspace channels)
  Step 2: "Set Your Schedule"
    - Input: Submission window start time (default: 12:00am)
    - Input: Submission deadline (default: 9:30am)
    - Input: Timezone (auto-detected from workspace, editable)
  Step 3: "Add Team Members"
    - Multi-select dropdown of workspace members
    - Default: All members in selected channel
AND each step has a "Next" button and "Skip for Now" link
```

**AC 1.3.2**: Onboarding Completion
```gherkin
GIVEN I complete all 3 onboarding steps
WHEN I click "Finish Setup"
THEN a standup record is created in the database with my configuration
  AND I am redirected to the dashboard showing: "✅ Setup complete! First standup prompt will be sent tomorrow at [start_time]"
  AND the bot posts a welcome message to the configured channel:
    "👋 AsyncStandup is now active! Team members will receive their first standup prompt tomorrow at [start_time]."
```

**AC 1.3.3**: Skip Onboarding Option
```gherkin
GIVEN I want to configure standups later
WHEN I click "Skip for Now" on Step 1
THEN I am redirected to the empty dashboard
  AND I see a prominent "Create Your First Standup" button
  AND no standup records are created yet
```

**AC 1.3.4**: Form Validation
```gherkin
GIVEN I am filling out the onboarding wizard
WHEN I enter invalid data:
  - Empty standup name
  - Deadline before start time (e.g., start=9am, deadline=8am)
  - No channel selected
THEN I see inline error messages:
  - "Standup name is required"
  - "Deadline must be after start time"
  - "Please select a channel"
AND the "Next" button is disabled until errors are fixed
```

#### Test Scenarios

**Test Scenario 1.3.A**: Happy Path Onboarding
- **Setup**: Fresh workspace installation
- **Steps**:
  1. Complete OAuth
  2. Fill out all 3 wizard steps with valid data
  3. Click "Finish Setup"
- **Expected**: Standup created, welcome message posted, dashboard shows success

**Test Scenario 1.3.B**: Partial Completion + Return Later
- **Setup**: User completes Step 1, closes browser
- **Steps**:
  1. Complete Step 1 (standup name + channel)
  2. Close browser tab
  3. Return to dashboard next day
  4. Click "Complete Setup"
- **Expected**: Wizard resumes at Step 2 with Step 1 data preserved

**Test Scenario 1.3.C**: Timezone Auto-Detection
- **Setup**: Workspace with members in US/Pacific timezone
- **Steps**:
  1. Reach Step 2 of wizard
  2. Verify timezone dropdown pre-selected
- **Expected**: Timezone shows "America/Los_Angeles" (not UTC)

**Test Scenario 1.3.D**: Channel Permission Error
- **Setup**: Selected channel is private, bot not invited
- **Steps**:
  1. Select private channel in Step 1
  2. Complete wizard
  3. Bot attempts to post welcome message
- **Expected**: Error message: "Cannot post to #private-channel. Please invite the bot first."

#### Edge Cases
- ❌ User selects archived channel
- ❌ User selects channel bot doesn't have access to
- ❌ Workspace has 200+ channels (dropdown performance)
- ❌ Standup name contains emoji or special characters

#### Definition of Done
- [ ] UI mockups approved by design team
- [ ] All 4 test scenarios pass
- [ ] Mobile-responsive wizard (works on phone)
- [ ] Accessibility audit passed (keyboard navigation, screen reader)
- [ ] QA signed off on form validation
- [ ] Analytics tracking configured (wizard completion rate)

---

### Story 1.4: Design and Deploy Database Schema

**Story ID**: AS-1.4  
**Priority**: 🔴 P0 (Blocker for all data persistence)  
**Story Points**: 5  
**Assignee**: Database Engineer  
**Dependencies**: None (can start immediately)  
**QA Complexity**: High (data integrity critical)

#### User Story
```
AS A backend engineer
I WANT a normalized, scalable database schema
SO THAT we can store workspaces, standups, submissions, and summaries reliably
```

#### Acceptance Criteria

**AC 1.4.1**: Core Tables Created
```gherkin
GIVEN we need to store AsyncStandup data
WHEN we deploy the initial schema migration
THEN the following tables are created:

1. workspaces
   - workspace_id (PK, VARCHAR, Slack team ID)
   - access_token (TEXT, encrypted)
   - bot_user_id (VARCHAR)
   - team_name (VARCHAR)
   - installed_at (TIMESTAMP)
   - updated_at (TIMESTAMP)

2. standups
   - standup_id (PK, UUID)
   - workspace_id (FK → workspaces)
   - name (VARCHAR, e.g., "Engineering Team")
   - channel_id (VARCHAR, Slack channel ID)
   - start_time (TIME, e.g., "00:00")
   - deadline_time (TIME, e.g., "09:30")
   - timezone (VARCHAR, IANA timezone)
   - active (BOOLEAN, default TRUE)
   - created_at (TIMESTAMP)

3. standup_members
   - id (PK, SERIAL)
   - standup_id (FK → standups)
   - slack_user_id (VARCHAR)
   - added_at (TIMESTAMP)
   - UNIQUE(standup_id, slack_user_id)

4. submissions
   - submission_id (PK, UUID)
   - standup_id (FK → standups)
   - slack_user_id (VARCHAR)
   - content (TEXT, raw standup update)
   - submitted_at (TIMESTAMP)
   - standup_date (DATE, which day's standup)

5. summaries
   - summary_id (PK, UUID)
   - standup_id (FK → standups)
   - summary_date (DATE)
   - summary_text (TEXT, generated summary)
   - blockers_detected (JSONB, array of blocker objects)
   - published_at (TIMESTAMP)
   - generation_time_ms (INTEGER, performance metric)

AND all tables have appropriate indexes on foreign keys
```

**AC 1.4.2**: Data Integrity Constraints
```gherkin
GIVEN we want to prevent invalid data
WHEN we define the schema
THEN the following constraints are enforced:
  - workspaces.workspace_id is unique (no duplicate installations)
  - standups.deadline_time > standups.start_time (validated at app level)
  - submissions.standup_date matches the date the standup was active
  - summaries.standup_date has max 1 summary per standup per day (UNIQUE constraint)
  - Foreign keys have ON DELETE CASCADE for standups → submissions/summaries
```

**AC 1.4.3**: Migration Reversibility
```gherkin
GIVEN we need to rollback a bad deployment
WHEN we run the "down" migration
THEN all tables are dropped in reverse dependency order:
  1. summaries (depends on standups)
  2. submissions (depends on standups)
  3. standup_members (depends on standups)
  4. standups (depends on workspaces)
  5. workspaces (no dependencies)
AND no orphaned data remains
```

**AC 1.4.4**: Performance Indexes
```gherkin
GIVEN we expect high read volume on certain queries
WHEN we deploy the schema
THEN the following indexes are created:
  - submissions: INDEX ON (standup_id, standup_date) for daily summary generation
  - summaries: INDEX ON (standup_id, summary_date DESC) for archive queries
  - standup_members: INDEX ON (standup_id) for membership lookups
  - workspaces: INDEX ON (workspace_id) for token lookups (already PK)
```

#### Test Scenarios

**Test Scenario 1.4.A**: Schema Migration (Up)
- **Setup**: Fresh PostgreSQL database
- **Steps**:
  1. Run migration: `npm run migrate:up`
  2. Verify all 5 tables created
  3. Check indexes exist: `\di` in psql
- **Expected**: All tables created, no errors

**Test Scenario 1.4.B**: Schema Migration (Down)
- **Setup**: Database with schema deployed
- **Steps**:
  1. Insert test data into all tables
  2. Run migration: `npm run migrate:down`
  3. Verify all tables dropped
- **Expected**: No tables remain, no orphaned data

**Test Scenario 1.4.C**: Foreign Key Cascade Delete
- **Setup**: Database with standup + submissions
- **Steps**:
  1. Insert standup with ID=123
  2. Insert 5 submissions for standup_id=123
  3. Delete standup: `DELETE FROM standups WHERE standup_id=123`
  4. Query submissions: `SELECT * FROM submissions WHERE standup_id=123`
- **Expected**: 0 submissions returned (cascaded delete)

**Test Scenario 1.4.D**: Unique Constraint Violation
- **Setup**: Database with existing summary
- **Steps**:
  1. Insert summary: standup_id=123, summary_date='2024-01-15'
  2. Attempt duplicate insert: same standup_id + summary_date
- **Expected**: PostgreSQL error: "duplicate key value violates unique constraint"

**Test Scenario 1.4.E**: Index Performance Validation
- **Setup**: Database with 10,000 submissions
- **Steps**:
  1. Query: `SELECT * FROM submissions WHERE standup_id='abc' AND standup_date='2024-01-15'`
  2. Check query plan: `EXPLAIN ANALYZE ...`
- **Expected**: Query uses index scan (not seq scan), execution time <10ms

**Test Scenario 1.4.F**: Encrypted Token Storage
- **Setup**: Database with workspace record
- **Steps**:
  1. Insert workspace with access_token='xoxb-1234-abcd'
  2. Query raw database: `SELECT access_token FROM workspaces`
- **Expected**: access_token is encrypted (not plaintext)

#### Edge Cases
- ❌ Migration run twice (idempotency check)
- ❌ Migration fails mid-execution (transaction rollback)
- ❌ Database connection timeout during migration
- ❌ Workspace with 1 million submissions (query performance)
- ❌ JSONB blocker field with 100+ blockers (storage limit)

#### Technical Implementation Notes
```sql
-- Example migration (migrations/001_initial_schema.sql)
BEGIN;

CREATE TABLE workspaces (
  workspace_id VARCHAR(255) PRIMARY KEY,
  access_token TEXT NOT NULL, -- Encrypted via app-level encryption
  bot_user_id VARCHAR(255) NOT NULL,
  team_name VARCHAR(255) NOT NULL,
  installed_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE standups (
  standup_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id VARCHAR(255) REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
  name VARCHAR(255) NOT NULL,
  channel_id VARCHAR(255) NOT NULL,
  start_time TIME NOT NULL,
  deadline_time TIME NOT NULL,
  timezone VARCHAR(100) NOT NULL,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  CHECK (deadline_time > start_time) -- App-level validation backup
);

CREATE INDEX idx_standups_workspace ON standups(workspace_id);

CREATE TABLE submissions (
  submission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  standup_id UUID REFERENCES standups(standup_id) ON DELETE CASCADE,
  slack_user_id VARCHAR(255) NOT NULL,
  content TEXT NOT NULL,
  submitted_at TIMESTAMP DEFAULT NOW(),
  standup_date DATE NOT NULL
);

CREATE INDEX idx_submissions_standup_date ON submissions(standup_id, standup_date);

CREATE TABLE summaries (
  summary_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  standup_id UUID REFERENCES standups(standup_id) ON DELETE CASCADE,
  summary_date DATE NOT NULL,
  summary_text TEXT NOT NULL,
  blockers_detected JSONB,
  published_at TIMESTAMP DEFAULT NOW(),
  generation_time_ms INTEGER,
  UNIQUE(standup_id, summary_date) -- Max 1 summary per standup per day
);

CREATE INDEX idx_summaries_standup_date ON summaries(standup_id, summary_date DESC);

COMMIT;
```

#### Definition of Done
- [ ] Migration runs successfully on local dev database
- [ ] Migration runs successfully on staging database
- [ ] All 6 test scenarios pass
- [ ] Schema documented in `/docs/database-schema.md` with ER diagram
- [ ] Database Engineer reviewed and approved
- [ ] Backup/restore procedure tested
- [ ] QA signed off on data integrity constraints

---

### Story 1.5: [INFRA] Provision AWS Infrastructure

**Story ID**: AS-1.5  
**Priority**: 🔴 P0  
**Story Points**: 3  
**Assignee**: DevOps Engineer  
**Dependencies**: None (can start immediately)  
**QA Complexity**: Low (infrastructure validation)

#### User Story
```
AS A DevOps engineer
I WANT to provision AWS infrastructure via Terraform
SO THAT we have reproducible, version-controlled infrastructure
```

#### Acceptance Criteria

**AC 1.5.1**: Terraform Modules Created
```gherkin
GIVEN we need to deploy AsyncStandup infrastructure
WHEN we run `terraform apply`
THEN the following AWS resources are created:
  - VPC with public/private subnets (2 AZs for HA)
  - RDS PostgreSQL 15 instance (db.t3.micro for dev, db.t3.small for prod)
  - ElastiCache Redis cluster (cache.t3.micro, 1 node for dev)
  - ECS Fargate cluster for Node.js app
  - Application Load Balancer (ALB) with HTTPS listener
  - S3 bucket for Terraform state (with versioning enabled)
  - CloudWatch Log Groups for application logs
  - IAM roles for ECS task execution
AND all resources are tagged with: Environment=dev/staging/prod, Project=AsyncStandup
```

**AC 1.5.2**: Environment Separation
```gherkin
GIVEN we need dev, staging, and prod environments
WHEN we deploy infrastructure
THEN we have 3 separate Terraform workspaces:
  - dev: Single-AZ, t3.micro instances, no auto-scaling
  - staging: Multi-AZ, t3.small instances, auto-scaling 1-3 tasks
  - prod: Multi-AZ, t3.medium instances, auto-scaling 2-10 tasks
AND each environment has isolated networking (separate VPCs)
```

**AC 1.5.3**: Cost Optimization
```gherkin
GIVEN we want to minimize AWS costs for MVP
WHEN we configure resources
THEN we use:
  - RDS: db.t3.micro (2 vCPU, 1GB RAM) = ~$15/month
  - ElastiCache: cache.t3.micro (2 vCPU, 0.5GB RAM) = ~$12/month
  - ECS Fargate: 0.25 vCPU, 0.5GB RAM = ~$7/month per task
  - ALB: ~$20/month
  - Total estimated cost: $60-80/month for dev, $150-200/month for prod
AND we enable AWS Cost Anomaly Detection alerts
```

**AC 1.5.4**: Secrets Management
```gherkin
GIVEN we need to store sensitive credentials
WHEN we deploy infrastructure
THEN we use AWS Secrets Manager for:
  - Database password (auto-rotated every 90 days)
  - Slack OAuth client secret
  - OpenAI API key
  - Encryption key for Slack tokens
AND secrets are referenced in ECS task definitions (not hardcoded)
```

#### Test Scenarios

**Test Scenario 1.5.A**: Terraform Plan (Dry Run)
- **Setup**: Fresh AWS account
- **Steps**:
  1. Run `terraform plan`
  2. Review planned changes
- **Expected**: No errors, all resources planned

**Test Scenario 1.5.B**: Terraform Apply (Dev Environment)
- **Setup**: AWS account with Terraform state bucket
- **Steps**:
  1. Run `terraform apply -var="environment=dev"`
  2. Verify all resources created
  3. Check AWS console: VPC, RDS, ElastiCache, ECS
- **Expected**: All resources created, no errors

**Test Scenario 1.5.C**: Terraform Destroy (Cleanup)
- **Setup**: Dev environment deployed
- **Steps**:
  1. Run `terraform destroy -var="environment=dev"`
  2. Verify all resources deleted
- **Expected**: No resources remain (except S3 state bucket)

**Test Scenario 1.5.D**: Database Connection Test
- **Setup**: RDS instance provisioned
- **Steps**:
  1. Get RDS endpoint from Terraform output
  2. Connect via psql: `psql -h [endpoint] -U asyncstandup`
  3. Run query: `SELECT version();`
- **Expected**: PostgreSQL 15.x version returned

**Test Scenario 1.5.E**: Redis Connection Test
- **Setup**: ElastiCache cluster provisioned
- **Steps**:
  1. Get Redis endpoint from Terraform output
  2. Connect via redis-cli: `redis-cli -h [endpoint]`
  3. Run command: `PING`
- **Expected**: Response: `PONG`

#### Edge Cases
- ❌ Terraform apply interrupted mid-execution
- ❌ AWS account hits service quota (e.g., max VPCs)
- ❌ RDS instance takes 15+ minutes to provision (timeout handling)
- ❌ Secrets Manager secret already exists (conflict)

#### Technical Implementation Notes
```hcl
# terraform/main.tf (simplified)
terraform {
  backend "s3" {
    bucket = "asyncstandup-terraform-state"
    key    = "infrastructure/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source = "./modules/vpc"
  environment = var.environment
  cidr_block = "10.0.0.0/16"
}

module "rds" {
  source = "./modules/rds"
  environment = var.environment
  vpc_id = module.vpc.vpc_id
  instance_class = var.environment == "prod" ? "db.t3.small" : "db.t3.micro"
}

module "elasticache" {
  source = "./modules/elasticache"
  environment = var.environment
  vpc_id = module.vpc.vpc_id
  node_type = "cache.t3.micro"
}

module "ecs" {
  source = "./modules/ecs"
  environment = var.environment
  vpc_id = module.vpc.vpc_id
  app_image = var.app_image
  cpu = var.environment == "prod" ? 512 : 256
  memory = var.environment == "prod" ? 1024 : 512
}

output "rds_endpoint" {
  value = module.rds.endpoint
}

output "redis_endpoint" {
  value = module.elasticache.endpoint
}
```

#### Definition of Done
- [ ] Terraform plan runs without errors
- [ ] Dev environment deployed successfully
- [ ] All 5 test scenarios pass
- [ ] Infrastructure documented in `/docs/infrastructure.md`
- [ ] Cost estimates validated (AWS Cost Explorer)
- [ ] Security group rules reviewed (least privilege)
- [ ] Backup strategy documented (RDS snapshots)
- [ ] DevOps Engineer signed off

---

### Story 1.6: [INFRA] Configure CI/CD Pipeline

**Story ID**: AS-1.6  
**Priority**: 🟡 P1  
**Story Points**: 3  
**Assignee**: DevOps Engineer  
**Dependencies**: Story 1.5 (infrastructure must exist)  
**QA Complexity**: Medium

#### User Story
```
AS A developer
I WANT automated testing and deployment via CI/CD
SO THAT I can ship code to production confidently and quickly
```

#### Acceptance Criteria

**AC 1.6.1**: GitHub Actions Workflow
```gherkin
GIVEN we use GitHub for source control
WHEN we push code to a branch
THEN GitHub Actions automatically:
  1. Runs linter (ESLint)
  2. Runs unit tests (Jest)
  3. Runs integration tests (against test database)
  4. Builds Docker image
  5. Pushes image to AWS ECR
AND the workflow fails if any step fails (no partial deployments)
```

**AC 1.6.2**: Automated Deployment
```gherkin
GIVEN we merge a PR to the `main` branch
WHEN the CI/CD pipeline completes
THEN the new Docker image is:
  1. Tagged with git commit SHA
  2. Deployed to staging environment (ECS Fargate)
  3. Health check runs (GET /health returns 200)
  4. Slack notification sent to #eng-deployments channel
AND production deployment requires manual approval (GitHub Environment protection)
```

**AC 1.6.3**: Rollback Capability
```gherkin
GIVEN a bad deployment is detected in staging
WHEN we trigger a rollback
THEN the previous Docker image is redeployed
  AND the rollback completes in <5 minutes
  AND the rollback is logged to DataDog
```

**AC 1.6.4**: Database Migration Automation
```gherkin
GIVEN we have new database migrations
WHEN we deploy to staging
THEN migrations run automatically before app deployment
  AND if migration fails, deployment is aborted
  AND migration status is logged to CloudWatch
```

#### Test Scenarios

**Test Scenario 1.6.A**: CI Pipeline (Feature Branch)
- **Setup**: Create feature branch with new code
- **Steps**:
  1. Push code to feature branch
  2. Observe GitHub Actions workflow
- **Expected**: Linter + tests run, Docker image built (not deployed)

**Test Scenario 1.6.B**: CD Pipeline (Staging Deployment)
- **Setup**: Merge PR to `main` branch
- **Steps**:
  1. Merge PR
  2. Observe GitHub Actions workflow
  3. Check ECS staging cluster
- **Expected**: New Docker image deployed, health check passes

**Test Scenario 1.6.C**: Failed Deployment (Rollback)
- **Setup**: Deploy code with failing health check
- **Steps**:
  1. Deploy image that returns 500 on /health
  2. Wait for health check failure
  3. Trigger rollback
- **Expected**: Previous image redeployed, health check passes

**Test Scenario 1.6.D**: Database Migration Failure
- **Setup**: Migration with syntax error
- **Steps**:
  1. Push migration: `ALTER TABLE foo ADD COLUMN bar INVALID_TYPE;`
  2. Deploy to staging
- **Expected**: Migration fails, deployment aborted, no app update

#### Definition of Done
- [ ] GitHub Actions workflow file created (`.github/workflows/ci-cd.yml`)
- [ ] All 4 test scenarios pass
- [ ] Rollback procedure documented
- [ ] Slack notifications configured
- [ ] Manual approval required for prod deployments
- [ ] DevOps Engineer signed off

---

## 5. EPIC 2: STANDUP COLLECTION FLOW

**Epic Goal**: Bot sends daily DM prompts to team members, collects standup submissions, and stores them for summarization.

**Epic Owner**: Backend API Engineer + Full Stack Developer

**Sprint Allocation**: Sprint 2-3 (Weeks 3-6)

**Total Story Points**: 34 points

**Success Metrics**:
- 90% message delivery success rate
- <2 second DM response time (p95)
- 80%+ team members submit by deadline

---

### Story 2.1: Implement Daily DM Prompt Scheduler

**Story ID**: AS-2.1  
**Priority**: 🔴 P0  
**Story Points**: 5  
**Assignee**: Backend API Engineer  
**Dependencies**: Story 1.4 (database schema), Story 1.5 (Redis infrastructure)  
**QA Complexity**: High (timing-critical)

#### User Story
```
AS A team member
I WANT to receive a DM prompt every morning at the configured time
SO THAT I remember to submit my standup update
```

#### Acceptance Criteria

**AC 2.1.1**: Job Scheduling Logic
```gherkin
GIVEN a standup is configured with start_time=08:00 and timezone=America/Los_Angeles
WHEN the scheduler runs
THEN a BullMQ job is enqueued at 08:00 Pacific Time (converted to UTC)
  AND the job payload includes: standup_id, standup_date, team_member_user_ids[]
  AND the job is scheduled with priority=HIGH (executed before summarization jobs)
```

**AC 2.1.2**: DM Prompt Content
```gherkin
GIVEN a team member is scheduled to receive a prompt
WHEN the prompt job executes
THEN the bot sends a DM with this content:
  ---
  Good morning! ☀️ Time for your daily standup.
  
  Please share:
  • What you accomplished yesterday
  • What you're working on today
  • Any blockers or help needed
  
  Reply to this message with your update. Deadline: 9:30am PT.
  ---
AND the message includes the team member's name in the greeting (personalization)
```

**AC 2.1.3**: Prompt Delivery Confirmation
```gherkin
GIVEN the bot sends a DM prompt
WHEN the Slack API call completes
THEN we log the delivery status:
  - SUCCESS: Message delivered, message_ts stored
  - FAILURE: Slack API error (e.g., user deactivated, DM disabled)
AND failed deliveries are logged to DataDog with context: user_id, error_code, standup_id
```

**AC 2.1.4**: Idempotency (No Duplicate Prompts)
```gherkin
GIVEN a prompt job is enqueued for user=alice, standup_date=2024-01-15
WHEN the job executes
THEN we check if a prompt was already sent today (query: submissions table)
  AND if a prompt exists, skip sending (log: "Prompt already sent")
  AND if no prompt exists, send DM and record in database
```

**AC 2.1.5**: Timezone Handling
```gherkin
GIVEN a standup has timezone=America/New_York (UTC-5)
WHEN the scheduler calculates the send time
THEN the job is enqueued at 08:00 ET = 13:00 UTC
  AND the calculation accounts for Daylight Saving Time transitions
  AND we use the `moment-timezone` library for accuracy
```

#### Test Scenarios

**Test Scenario 2.1.A**: Happy Path Prompt Delivery
- **Setup**: Standup configured with 3 team members, start_time=08:00 PT
- **Steps**:
  1. Advance system clock to 08:00 PT (2024-01-15)
  2. Trigger scheduler manually: `npm run scheduler:trigger`
  3. Check Slack DMs for all 3 members
- **Expected**: All 3 members receive DM prompt, database records created

**Test Scenario 2.1.B**: Duplicate Prompt Prevention
- **Setup**: Prompt already sent to user=alice today
- **Steps**:
  1. Send prompt to alice at 08:00 (manual trigger)
  2. Trigger scheduler again at 08:05
  3. Check alice's DMs
- **Expected**: Only 1 DM received, second attempt logged as "already sent"

**Test Scenario 2.1.C**: Timezone Edge Case (DST Transition)
- **Setup**: Standup in America/Los_Angeles, day of DST spring forward (March 10, 2024)
- **Steps**:
  1. Configure standup for 02:30am PT (during DST gap)
  2. Advance clock to March 10, 2024 02:00am
  3. Trigger scheduler
- **Expected**: Prompt sent at 03:30am PT (after DST adjustment)

**Test Scenario 2.1.D**: User Deactivated (Delivery Failure)
- **Setup**: Team member deactivated in Slack workspace
- **Steps**:
  1. Deactivate user=bob in Slack
  2. Trigger prompt job for bob
  3. Check DataDog logs
- **Expected**: Slack API returns `user_not_found`, error logged, job marked failed

**Test Scenario 2.1.E**: Slack API Rate Limit
- **Setup**: 100 team members in standup (exceeds Slack rate limit of 1 msg/sec)
- **Steps**:
  1. Trigger prompt job for 100 members
  2. Observe Slack API responses
- **Expected**: Jobs throttled to 1 msg/sec, all messages delivered within 100 seconds

**Test Scenario 2.1.F**: Scheduler Downtime Recovery
- **Setup**: Scheduler crashes at 07:55 (before prompt time)
- **Steps**:
  1. Stop scheduler process at 07:55
  2. Restart scheduler at 08:10 (10 minutes late)
  3. Check if prompts are sent
- **Expected**: Scheduler detects missed jobs, sends prompts immediately (within 1 minute of restart)

#### Edge Cases
- ❌ Standup scheduled for 00:00 (midnight) — ensure no date boundary bugs
- ❌ Team member in different timezone than standup (e.g., user in UTC, standup in PT)
- ❌ Standup deleted mid-day (job should gracefully fail)
- ❌ Redis connection lost during job enqueue
- ❌ 10,000 standups scheduled for same time (queue performance)

#### Technical Implementation Notes
```javascript
// scheduler/promptScheduler.js
const { Queue, Worker } = require('bullmq');
const moment = require('moment-timezone');

const promptQueue = new Queue('standup-prompts', {
  connection: { host: process.env.REDIS_HOST, port: 6379 }
});

// Enqueue jobs for all active standups
async function schedulePrompts() {
  const standups = await db.standups.findAll({ active: true });
  
  for (const standup of standups) {
    const now = moment().tz(standup.timezone);
    const sendTime = moment.tz(standup.start_time, 'HH:mm', standup.timezone);
    
    if (now.isSame(sendTime, 'minute')) {
      const members = await db.standup_members.findAll({ standup_id: standup.standup_id });
      
      for (const member of members) {
        // Check if prompt already sent today
        const existing = await db.submissions.findOne({
          standup_id: standup.standup_id,
          slack_user_id: member.slack_user_id,
          standup_date: now.format('YYYY-MM-DD')
        });
        
        if (!existing) {
          await promptQueue.add('send-prompt', {
            standup_id: standup.standup_id,
            slack_user_id: member.slack_user_id,
            standup_date: now.format('YYYY-MM-DD')
          }, { priority: 10 }); // HIGH priority
        }
      }
    }
  