# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Internal Notes App with Tags and Search

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Status:** Ready for Engineering Handoff  
**Owner:** Product Management

---

## TABLE OF CONTENTS
1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [User Personas](#user-personas)
4. [Goals & Success Metrics](#goals--success-metrics)
5. [Feature Requirements](#feature-requirements)
6. [Out of Scope](#out-of-scope)
7. [Data Governance & Access Control](#data-governance--access-control)
8. [Risks & Mitigations](#risks--mitigations)
9. [Open Questions](#open-questions)
10. [Appendix: Acceptance Criteria](#appendix-acceptance-criteria)

---

## EXECUTIVE SUMMARY

**Product Name:** Internal Notes App  
**Product Category:** Enterprise Productivity / Knowledge Management  
**Target Users:** Knowledge workers within organizations who need to capture, organize, and retrieve internal notes quickly

**Vision Statement:**  
Enable teams to capture institutional knowledge and personal insights in a centralized, searchable repository where notes are organized through flexible tagging and discoverable through powerful search—reducing time spent hunting for information and preventing knowledge loss when team members leave.

**Business Rationale:**  
Organizations lose productivity when employees cannot quickly locate relevant notes, decisions, or context. Existing solutions are either too complex (wiki/documentation platforms) or too fragmented (email, chat, local files). This product fills the gap: a lightweight, team-accessible notes app that balances simplicity with discoverability.

**Success Definition:**  
Within 6 months of launch, achieve 60% DAU (Daily Active Users) among target organization, with users reporting 40% reduction in time spent searching for information compared to pre-app workflows.

---

## PROBLEM STATEMENT

### The Core Problem
Knowledge workers spend significant time searching for information scattered across email, chat, local files, and shared drives. When critical context or decisions are stored in personal notes or individual inboxes, institutional knowledge is lost when employees leave, and team members cannot access relevant information when needed.

### Evidence of the Problem
- **[ASSUMPTION]** Typical knowledge worker spends 15-30 minutes per day searching for information they've previously encountered
- **[ASSUMPTION]** 40% of organizational knowledge exists only in individual note-taking apps (OneNote, Apple Notes, Notion personal workspaces) with no team visibility
- **[ASSUMPTION]** When employees leave, 60% of their contextual knowledge is inaccessible to remaining team members
- **[ASSUMPTION]** Current solutions require either: (a) high overhead to maintain (wikis, documentation platforms), or (b) are too fragmented to be useful (email, chat threads)

### Why Existing Solutions Fall Short
| Solution | Strength | Weakness |
|----------|----------|----------|
| Email/Chat | Familiar, real-time | Ephemeral, unsearchable, scattered |
| Personal Note Apps (OneNote, Apple Notes) | Simple, fast | No team access, knowledge silos |
| Wiki/Documentation Platforms | Centralized, searchable | High friction to create/maintain, overkill for quick notes |
| Shared Drives (Google Drive, SharePoint) | Centralized | Poor search, no tagging, high noise |

### Target Problem Scope
This product solves the problem for **internal, team-level note-taking** where:
- Notes are created quickly (not formal documentation)
- Information needs to be discoverable by team members
- Tagging provides flexible organization without rigid hierarchies
- Search is the primary discovery mechanism

---

## USER PERSONAS

### Persona 1: Sarah, Knowledge Worker / Individual Contributor
**Role:** Software Engineer, Product Manager, or Analyst  
**Organization Size:** Mid-market (100-1000 employees)  
**Age/Experience:** 28-40, 5-10 years in role  

**Goals:**
- Capture quick notes during meetings, research, or problem-solving without disrupting workflow
- Retrieve past decisions, code snippets, or context when needed
- Share relevant notes with teammates without manual forwarding

**Pain Points:**
- Spends 20+ minutes per week searching through email or chat for past decisions
- Maintains personal note app (OneNote, Notion) that teammates can't access
- Forgets where she stored important context (which app, which folder)
- Duplicates notes across multiple tools

**Behaviors:**
- Creates 5-10 notes per week
- Searches for notes 2-3 times per week
- Prefers keyboard shortcuts and fast capture
- Uses tags intuitively (doesn't want to learn complex taxonomy)

**Success Metric:** Sarah finds a previously-created note in under 30 seconds using search or tags

---

### Persona 2: Marcus, Team Lead / Manager
**Role:** Engineering Manager, Product Lead, or Department Head  
**Organization Size:** Mid-market (100-1000 employees)  
**Age/Experience:** 35-50, 8-15 years in role  

**Goals:**
- Ensure team knowledge is accessible and not siloed in individual note apps
- Quickly reference team decisions, project context, and lessons learned
- Onboard new team members by providing access to institutional knowledge
- Audit what notes exist and who has access (compliance/governance)

**Pain Points:**
- Team members maintain separate note systems; can't find information when needed
- New hires spend days asking "where is X documented?"
- No visibility into what knowledge exists or where it's stored
- Concerned about knowledge loss when team members leave

**Behaviors:**
- Searches for notes 5-10 times per week (on behalf of team)
- Wants to enforce tagging standards to prevent chaos
- Needs to understand access permissions and audit trails
- Occasionally deletes or reorganizes notes

**Success Metric:** Marcus can locate any team decision or context within 1 minute; new hires are onboarded to the notes app within their first week

---

### Persona 3: Alex, IT Administrator / Compliance Officer
**Role:** IT Admin, Security Officer, or Compliance Manager  
**Organization Size:** Mid-market (100-1000 employees)  
**Age/Experience:** 30-55, 5-20 years in role  

**Goals:**
- Ensure data security and prevent unauthorized access to sensitive notes
- Maintain audit trails for compliance (SOC 2, HIPAA, etc.)
- Manage user access and permissions at scale
- Prevent data loss through retention policies and backups

**Pain Points:**
- Concerned about uncontrolled data proliferation in new tools
- Needs clear audit logs for regulatory requirements
- Worried about accidental data deletion or unauthorized sharing
- Needs to enforce data retention and deletion policies

**Behaviors:**
- Sets up access controls and permissions once, then monitors
- Reviews audit logs quarterly or when incidents occur
- Needs clear documentation of data handling practices
- Wants to prevent cross-organization data leakage (if multi-tenant)

**Success Metric:** Alex can generate an audit report showing who created/edited/deleted/viewed notes in the past 90 days; all access controls are enforced without manual intervention

---

## GOALS & SUCCESS METRICS

### Product Goals (6-Month Horizon)

**Goal 1: Drive Adoption**  
Achieve 60% DAU (Daily Active Users) among target organization within 6 months of launch.

| Metric | Target | Measurement |
|--------|--------|-------------|
| DAU / MAU Ratio | 60% | Daily active users ÷ monthly active users |
| Time to First Note | < 2 minutes | Time from app access to first note creation |
| Onboarding Completion Rate | 85% | % of invited users who create first note within 7 days |

---

**Goal 2: Reduce Information Search Time**  
Enable users to find information 40% faster than current workflows (email, chat, personal notes).

| Metric | Target | Measurement |
|--------|--------|-------------|
| Avg Search Time | < 30 seconds | Time from search initiation to finding relevant note |
| Search Success Rate | 80% | % of searches that result in user finding what they need |
| Notes Found via Search vs. Browse | 70% search | % of notes accessed through search vs. tag browsing |
| Reduction in "Where is X?" Questions | 40% reduction | Reduction in Slack/email queries asking for information location |

---

**Goal 3: Prevent Knowledge Silos**  
Shift 50% of team notes from personal apps to shared app within 6 months.

| Metric | Target | Measurement |
|--------|--------|-------------|
| Notes Created in App | 500+ per month | Total notes created in app (by month 6) |
| Team Visibility of Notes | 80% | % of notes accessible to at least 2+ team members |
| Reduction in Personal Note App Usage | 50% | Survey: % reduction in personal OneNote/Notion usage for team notes |

---

**Goal 4: Enable Governance & Compliance**  
Provide IT/compliance teams with full audit trails and access controls to meet regulatory requirements.

| Metric | Target | Measurement |
|--------|--------|-------------|
| Audit Log Completeness | 100% | All create/edit/delete/view actions logged with timestamp, user, action |
| Access Control Enforcement | 100% | No unauthorized access; all permission checks pass security audit |
| Compliance Report Generation | < 5 min | Time to generate audit report for any 90-day period |

---

### Success Criteria by Persona

**Sarah (Individual Contributor):**
- Creates first note within 2 minutes of app access
- Finds a previously-created note in < 30 seconds using search
- Uses tags to organize notes without manual instruction
- Shares a note with teammate within first week

**Marcus (Team Lead):**
- Locates any team decision or context within 1 minute
- Onboards new hires to app within first week
- Reviews team notes monthly to ensure knowledge is current
- Identifies and resolves tag inconsistencies (e.g., "bug" vs. "bugs")

**Alex (IT Admin):**
- Generates audit report showing all note activity in < 5 minutes
- Enforces access controls without manual intervention
- Implements data retention policy (e.g., delete notes after 2 years)
- Confirms zero cross-organization data leakage (if multi-tenant)

---

## FEATURE REQUIREMENTS

### P0 Features (Must Ship)
**Definition:** Features without which the product is not viable. Shipping is blocked if any P0 feature is incomplete or broken.

---

#### P0.1: Create & Edit Notes
**User Story:**  
As Sarah, I want to quickly capture a note with a title and body text so that I can record information without friction.

**Acceptance Criteria:**
- User can create a new note with a title (required, max 255 characters) and body text (required, max 50,000 characters)
- Note creation takes < 2 seconds from click to save
- User can edit note title and body after creation
- Edit timestamp is recorded (for audit purposes)
- User can see a "last edited" indicator on the note
- Notes are auto-saved every 30 seconds during editing (no manual save required)
- User receives confirmation when note is saved (visual indicator, not modal)

**Out of Scope (P0.1):**
- Rich text formatting (bold, italic, links) — P1 feature
- Markdown support — P1 feature
- Note templates — P2 feature
- Collaborative real-time editing — P2 feature

---

#### P0.2: Tag Notes
**User Story:**  
As Sarah, I want to tag notes with keywords so that I can organize them flexibly without rigid folder hierarchies.

**Acceptance Criteria:**
- User can add one or more tags to a note (minimum 1, maximum 10 tags per note)
- Tags are text strings (max 50 characters each)
- User can create new tags on-the-fly while editing a note
- User can remove tags from a note
- Tags are case-insensitive (e.g., "Bug" and "bug" are treated as the same tag)
- Tag names can contain letters, numbers, hyphens, and underscores (no special characters)
- User sees a list of existing tags as they type (autocomplete)
- Tag creation is available to all users (no admin-only restriction) — [ASSUMPTION: Tag governance is permissive in MVP]

**Out of Scope (P0.2):**
- Tag hierarchy (parent-child relationships) — P1 feature
- Tag deletion by admins — P1 feature
- Tag usage analytics — P2 feature
- Tag renaming/merging — P2 feature

---

#### P0.3: Search Notes
**User Story:**  
As Sarah, I want to search for notes by keyword so that I can quickly find information without browsing through all notes.

**Acceptance Criteria:**
- User can enter a search query (text string, max 255 characters)
- Search returns notes where the query matches:
  - Note title (partial match, case-insensitive)
  - Note body (partial match, case-insensitive)
  - Note tags (exact match, case-insensitive)
- Search results are returned in < 1 second for typical queries (< 1000 notes)
- Search results are ranked by relevance (title matches ranked higher than body matches)
- User can see search result preview (first 100 characters of matching note body)
- User can click a result to open the full note
- Search is scoped to notes the user has access to (no cross-permission leakage)
- Empty search returns all notes accessible to the user (sorted by last edited date, newest first)

**Out of Scope (P0.3):**
- Fuzzy/typo-tolerant search — P1 feature
- Advanced query syntax (AND, OR, NOT operators) — P1 feature
- Search filters (by date, creator, tag) — P1 feature
- Search history / saved searches — P2 feature

---

#### P0.4: View & Access Notes
**User Story:**  
As Sarah, I want to view notes I've created or that have been shared with me so that I can access information when needed.

**Acceptance Criteria:**
- User can view a list of all notes they have access to
- List shows note title, last edited date, and tags
- User can click a note to open and read it
- User can see who created the note and when
- User can see the last editor and when it was last edited
- Notes are sorted by last edited date (newest first) by default
- User can see a note count (e.g., "Showing 47 notes")
- User cannot view notes they don't have access to (permission check enforced)

**Out of Scope (P0.4):**
- Custom sorting/filtering — P1 feature
- Favorites/starred notes — P1 feature
- Note preview on hover — P1 feature
- Bulk actions (select multiple notes) — P2 feature

---

#### P0.5: Access Control & Permissions
**User Story:**  
As Marcus, I want to control who can view, edit, and delete notes so that sensitive information is protected and team knowledge is shared appropriately.

**Acceptance Criteria:**
- Note creator has full permissions (view, edit, delete)
- Note creator can share a note with specific team members or teams
- Shared users can view and edit the note (read/write access)
- Shared users cannot delete the note (only creator can delete)
- Shared users cannot change permissions (only creator can)
- User can see who has access to a note (permission list)
- User can revoke access to a note at any time
- Access changes are logged in audit trail (who changed permissions, when)
- [ASSUMPTION] Default sharing scope is "creator only" (notes are private by default)
- [ASSUMPTION] No public/organization-wide sharing in MVP (explicit sharing only)

**Out of Scope (P0.5):**
- Role-based access control (RBAC) — P1 feature
- Team-level permissions — P1 feature
- Granular permissions (view-only vs. edit) — P1 feature
- Permission inheritance — P2 feature

---

#### P0.6: Delete Notes
**User Story:**  
As Sarah, I want to delete notes I no longer need so that I can keep my notes organized and remove outdated information.

**Acceptance Criteria:**
- Note creator can delete a note they created
- Non-creators cannot delete notes (even if they have edit access)
- Delete action requires confirmation (modal: "Are you sure?")
- Deleted notes are soft-deleted (moved to trash, not permanently removed)
- Soft-deleted notes are not visible in search or note list
- Soft-deleted notes can be recovered by creator within 30 days
- After 30 days, soft-deleted notes are permanently deleted
- Delete action is logged in audit trail (who deleted, when, note ID)
- [ASSUMPTION] Admins can force-delete notes (P1 feature)

**Out of Scope (P0.6):**
- Permanent delete option — P1 feature
- Bulk delete — P2 feature
- Delete recovery by admins — P1 feature

---

#### P0.7: Audit Logging
**User Story:**  
As Alex, I want to maintain an audit trail of all note activity so that I can meet compliance requirements and investigate incidents.

**Acceptance Criteria:**
- All note actions are logged: create, edit, delete, view, share, permission change
- Each log entry includes: timestamp, user ID, action type, note ID, details (e.g., what changed)
- Audit logs are immutable (cannot be edited or deleted after creation)
- Audit logs are retained for minimum 90 days (configurable by admin)
- Audit logs can be exported in CSV format for compliance reporting
- Audit logs are not visible to regular users (only admins)
- Audit logs include failed access attempts (e.g., user tried to view note they don't have access to)

**Out of Scope (P0.7):**
- Real-time audit alerts — P1 feature
- Audit log search/filtering UI — P1 feature
- Automated compliance reports — P1 feature

---

### P1 Features (High Priority, Ship in Next Release)
**Definition:** Features that significantly improve user experience or address critical gaps. Should ship within 1-2 releases after MVP.

---

#### P1.1: Tag Management & Governance
**User Story:**  
As Marcus, I want to manage tags across the organization so that we maintain a consistent tagging taxonomy and prevent tag chaos.

**Acceptance Criteria:**
- Admins can view a list of all tags in use and their frequency (how many notes use each tag)
- Admins can rename tags (all notes using old tag are updated)
- Admins can delete tags (notes are not deleted, just untagged)
- Admins can mark tags as "deprecated" (warning shown when used)
- Admins can define a list of "approved tags" (optional; if enabled, users can only use approved tags)
- Users see a warning if they use a deprecated tag
- Tag management is logged in audit trail

---

#### P1.2: Advanced Search
**User Story:**  
As Sarah, I want to search with more precision so that I can find exactly what I'm looking for without wading through irrelevant results.

**Acceptance Criteria:**
- Search supports filters: by tag, by creator, by date range (created/edited)
- Search supports boolean operators: AND, OR, NOT (e.g., "bug AND urgent")
- Search supports fuzzy matching (typo tolerance, e.g., "serch" finds "search")
- Search results can be sorted by: relevance (default), date created, date edited, creator
- Search results show which field matched (title, body, tag)
- Search results show a snippet of matching text in body (with query highlighted)

---

#### P1.3: Granular Permissions
**User Story:**  
As Marcus, I want to grant different permission levels (view-only vs. edit) so that I can control who can modify sensitive notes.

**Acceptance Criteria:**
- Note creator can grant "view-only" or "edit" access to specific users
- View-only users can read the note but cannot edit or delete
- Edit users can read and modify the note but cannot delete or change permissions
- Permission levels are shown in the permission list
- Permission changes are logged in audit trail

---

#### P1.4: Team-Level Sharing
**User Story:**  
As Marcus, I want to share notes with entire teams so that I don't have to add individual users one by one.

**Acceptance Criteria:**
- Note creator can share a note with a team (not just individuals)
- All current and future team members have access to the note
- Team membership changes are reflected automatically (new members gain access, removed members lose access)
- Team-level sharing is shown in the permission list
- Team-level sharing can be revoked at any time

---

#### P1.5: Role-Based Access Control (RBAC)
**User Story:**  
As Alex, I want to define roles (admin, team lead, user) with different permissions so that I can enforce governance at scale.

**Acceptance Criteria:**
- Admin role: can manage users, tags, audit logs, retention policies, and delete any note
- Team Lead role: can manage team members and view team audit logs
- User role: can create, edit, and share notes (default)
- Roles are assigned by admins
- Role-based permissions are enforced across the app

---

#### P1.6: Soft Delete Recovery
**User Story:**  
As Sarah, I want to recover a note I accidentally deleted so that I don't lose important information.

**Acceptance Criteria:**
- Deleted notes are moved to a "Trash" section (visible to creator only)
- Creator can view trash and see deleted notes
- Creator can restore a deleted note (moves back to active notes)
- Trash shows deletion date and time
- Trash is automatically emptied after 30 days (permanent deletion)
- Admins can force-delete notes from trash

---

#### P1.7: Note History & Versioning
**User Story:**  
As Sarah, I want to see previous versions of a note so that I can track changes and revert if needed.

**Acceptance Criteria:**
- Note history shows all edits (timestamp, editor, changes made)
- User can view a previous version of the note
- User can revert to a previous version (creates a new edit, doesn't overwrite history)
- History is retained for minimum 90 days
- History is shown in a side panel or modal (not inline)

---

#### P1.8: Bulk Actions
**User Story:**  
As Marcus, I want to perform actions on multiple notes at once so that I can manage notes more efficiently.

**Acceptance Criteria:**
- User can select multiple notes (checkbox)
- Bulk actions: add tag, remove tag, change permissions, move to trash
- Bulk actions show confirmation (e.g., "Add tag 'urgent' to 5 notes?")
- Bulk actions are logged in audit trail

---

### P2 Features (Nice-to-Have, Future Releases)
**Definition:** Features that enhance the product but are not critical for MVP. Ship after P0 and P1 are stable.

---

#### P2.1: Rich Text Formatting
- Support bold, italic, underline, code blocks, lists, tables
- Markdown preview
- Copy-paste from external documents

#### P2.2: Note Templates
- Pre-defined templates for common note types (meeting notes, decision log, incident report)
- Custom templates created by admins
- Template suggestions when creating a new note

#### P2.3: Collaborative Real-Time Editing
- Multiple users can edit the same note simultaneously
- Real-time cursor positions and changes
- Conflict resolution (merge edits or last-write-wins)

#### P2.4: Favorites & Pinning
- Users can mark notes as favorites (starred)
- Favorites appear at the top of the note list
- Users can pin notes to their dashboard

#### P2.5: Note Sharing & Collaboration
- Share notes via link (with optional expiration)
- Comment on notes (threaded discussions)
- @mention users in comments

#### P2.6: Integrations
- Slack integration (save Slack messages as notes, post notes to Slack)
- Email integration (forward emails as notes)
- Calendar integration (link notes to calendar events)

#### P2.7: Analytics & Insights
- Dashboard showing note creation trends, most-used tags, top contributors
- Usage analytics by team or department
- Knowledge gaps (topics with few notes)

#### P2.8: Mobile App
- Native iOS and Android apps
- Offline note creation (sync when online)
- Mobile-optimized UI

#### P2.9: Data Export & Backup
- Export all notes as PDF or markdown
- Scheduled backups
- Data portability (export in standard format)

#### P2.10: Advanced Retention Policies
- Automatic deletion of notes older than X days
- Archive old notes (read-only, not searchable)
- Retention policies by tag or team

---

## OUT OF SCOPE

### Explicitly Out of Scope (MVP & Beyond)

| Feature | Reason | Potential Future Release |
|---------|--------|--------------------------|
| Rich text formatting (bold, italic, etc.) | Adds complexity; plain text sufficient for MVP | P1 or P2 |
| Markdown support | Not required for initial use cases | P1 or P2 |
| Collaborative real-time editing | Requires complex conflict resolution; not needed for MVP | P2 |
| Mobile apps (iOS/Android) | Web app sufficient for initial launch; mobile can follow | P2 |
| Integrations (Slack, email, calendar) | Out of scope for MVP; can be added later | P2 |
| Advanced analytics dashboard | Not critical for MVP success | P2 |
| Note templates | Users can create their own templates manually | P2 |
| Comments/threaded discussions | Not required for initial use cases | P2 |
| Favorites/pinning | Nice-to-have but not essential | P2 |
| Automated compliance reports | Manual export sufficient for MVP | P1 |
| Public/organization-wide sharing | Explicit sharing only in MVP | P1 |
| Granular permissions (view-only) | Edit/delete distinction sufficient for MVP | P1 |
| Team-level sharing | Individual sharing sufficient for MVP | P1 |
| Note versioning/history | Audit logs sufficient for MVP | P1 |
| Bulk actions | Can be added after MVP | P1 |
| Advanced query syntax (AND, OR, NOT) | Basic search sufficient for MVP | P1 |
| Fuzzy search | Exact/partial match sufficient for MVP | P1 |
| Search filters (by date, creator) | Basic search sufficient for MVP | P1 |
| Tag hierarchy (parent-child) | Flat tags sufficient for MVP | P1 |
| Tag deletion/renaming | Tag management can be added later | P1 |
| Admin-only tag creation | Permissive tagging in MVP | P1 |
| Permanent delete option | Soft delete with 30-day recovery sufficient | P1 |
| Permanent delete by admins | Can be added in P1 | P1 |
| Real-time audit alerts | Manual audit log review sufficient for MVP | P1 |
| Audit log search UI | CSV export sufficient for MVP | P1 |
| Data export (PDF, markdown) | Can be added later | P2 |
| Scheduled backups | Infrastructure responsibility | P2 |
| Archive functionality | Can be added later | P2 |
| Offline note creation | Web app only in MVP | P2 |

### Non-Features (Will Not Build)
- **AI/ML features** (auto-tagging, smart suggestions) — out of scope for this product
- **Social features** (likes, reactions, followers) — not aligned with product vision
- **Gamification** (badges, points, leaderboards) — not aligned with product vision
- **Video/audio notes** — out of scope; text-only in MVP
- **Encryption at rest** — handled by infrastructure; not a product feature
- **Single sign-on (SSO)** — handled by infrastructure; not a product feature
- **Multi-language support** — English only in MVP; can be added later

---

## DATA GOVERNANCE & ACCESS CONTROL

### Data Ownership & Access Model

#### Note Ownership
- **Creator Ownership:** The user who creates a note is the owner and has full permissions (view, edit, delete, share)
- **Default Access:** Notes are **private by default** — only the creator can view them
- **Explicit Sharing:** Creator can explicitly share a note with specific users or teams
- **No Implicit Sharing:** Notes are never automatically shared based on team membership or role (except team-level sharing in P1)

#### Access Levels (MVP)
| Permission | Creator | Shared User | Non-Shared User |
|-----------|---------|-------------|-----------------|
| View | ✓ | ✓ | ✗ |
| Edit | ✓ | ✓ | ✗ |
| Delete | ✓ | ✗ | ✗ |
| Share/Change Permissions | ✓ | ✗ | ✗ |

**Note:** P1 will introduce granular permissions (view-only vs. edit).

#### Multi-Tenant Isolation (If Applicable)
- **[ASSUMPTION]** MVP is single-tenant (one organization only)
- **[ASSUMPTION]** If multi-tenant support is added later, strict data isolation must be enforced:
  - Notes from Organization A cannot be accessed by Organization B
  - Search results are scoped to the user's organization
  - Audit logs are segregated by organization
  - Tags are organization-specific (no cross-org tag sharing)

### Tag Governance (MVP)

#### Tag Creation & Lifecycle
- **Who Can Create Tags:** Any user can create tags (permissive model in MVP)
- **Tag Naming Rules:**
  - Max 50 characters
  - Case-insensitive (e.g., "Bug" and "bug" are the same)
  - Allowed characters: letters, numbers, hyphens, underscores
  - No special characters (!, @, #, $, %, etc.)
  - No leading/trailing spaces
- **Tag Deletion:** Tags cannot be deleted in MVP (P1 feature)
- **Tag Renaming:** Tags cannot be renamed in MVP (P1 feature)
- **Tag Hierarchy:** Flat tags only in MVP; no parent-child relationships (P1 feature)

#### Tag Governance Escalation (P1)
- Admins can rename tags (all notes updated automatically)
- Admins can delete tags (notes are untagged, not deleted)
- Admins can mark tags as "deprecated" (warning shown when used)
- Admins can define "approved tags" (optional; if enabled, users can only use approved tags)

### Search Scope & Permissions

#### What Search Covers
- **Note Title:** Partial match, case-insensitive
- **Note Body:** Partial match, case-insensitive
- **Note Tags:** Exact match, case-insensitive
- **Metadata:** NOT searchable in MVP (created date, creator name, etc.) — P1 feature

#### Search Permissions
- Search results are **scoped to notes the user has access to**
- Users cannot search notes they don't have permission to view
- Search does not reveal the existence of notes the user cannot access
- Cross-permission data leakage is prevented by permission checks on every search result

#### Search Performance Boundary
- **[ASSUMPTION]** MVP is optimized for organizations with up to 10,000 notes
- **[ASSUMPTION]** Search should return results in < 1 second for typical queries
- **[ASSUMPTION]** If performance degrades beyond 10,000 notes, indexing strategy will be revisited (TRD)

### Data Retention & Compliance

#### Soft Delete & Recovery
- **Soft Delete:** Deleted notes are moved to trash, not permanently removed
- **Trash Visibility:** Only the note creator can see deleted notes in trash
- **Recovery Window:** Creator can recover a deleted note within 30 days
- **Permanent Deletion:** After 30 days, soft-deleted notes are permanently deleted (automatic)
- **Admin Override:** Admins can force-delete notes from trash (P1 feature)

#### Audit Logging
- **Logged Actions:** Create, edit, delete, view, share, permission change
- **Log Contents:** Timestamp, user ID, action type, note ID, details (what changed)
- **Immutability:** Audit logs cannot be edited or deleted after creation
- **Retention:** Audit logs retained for minimum 90 days (configurable by admin in P1)
- **Access:** Audit logs visible to admins only (not regular users)
- **Failed Access Attempts:** Logged (e.g., user tried to view note they don't have access to)

#### Data Export & Portability
- **Export:** Not available in MVP (P2 feature)
- **Backup:** Infrastructure responsibility (not a product feature)
- **Data Portability:** Can be added in P2

#### Compliance Considerations
- **[ASSUMPTION]** Product must support SOC 2 compliance (audit logs, access controls, data retention)
- **[ASSUMPTION]** Product must support HIPAA compliance if used in healthcare (encryption, audit trails, access controls)
- **[ASSUMPTION]** Product must support GDPR compliance if used in EU (data export, deletion, consent)
- **[ASSUMPTION]** Specific compliance requirements should be validated with Alex (IT Admin persona) before P1 planning

### Conflict & Concurrency (MVP)

#### Simultaneous Editing
- **[ASSUMPTION]** MVP does not support simultaneous editing by multiple users
- **[ASSUMPTION]** If two users edit the same note, last-write-wins (later edit overwrites earlier edit)
- **[ASSUMPTION]** Edit timestamps are recorded to track who edited last
- **[ASSUMPTION]** Real-time collaborative editing is a P2 feature

#### Offline Editing
- **[ASSUMPTION]** MVP is web-only; offline editing not supported
- **[ASSUMPTION]** Offline editing can be added in P2 (mobile app)

#### Stale Data Handling
- **[ASSUMPTION]** If a user's session becomes stale, they are prompted to refresh
- **[ASSUMPTION]** If a note is deleted while user is viewing it, user sees an error message
- **[ASSUMPTION]** If a user's permissions are revoked while viewing a note, they are logged out

---

## RISKS & MITIGATIONS

### Risk 1: Tag Chaos & Taxonomy Explosion
**Risk:** Without governance, users create inconsistent tags (e.g., "bug", "bugs", "defect", "issue"), making search ineffective.

**Likelihood:** High  
**Impact:** High (defeats core value proposition of discoverability)

**Mitigation:**
- MVP: Provide tag autocomplete and suggestions to encourage reuse
- MVP: Show tag frequency (how many notes use each tag) to guide users
- P1: Implement tag management UI for admins to rename/merge tags
- P1: Implement "approved tags" feature (optional; admins can enforce a whitelist)
- P1: Implement tag deprecation warnings

**Owner:** Product Manager (MVP), Engineering (implementation)

---

### Risk 2: Adoption Resistance (Competing with Personal Note Apps)
**Risk:** Users continue using personal note apps (OneNote, Notion) instead of adopting the shared app, defeating the goal of preventing knowledge silos.

**Likelihood:** High  
**Impact:** High (product fails to achieve business goals)

**Mitigation:**
- MVP: Make note creation extremely fast (< 2 seconds) to reduce friction
- MVP: Provide clear onboarding and training materials
- P1: Implement Slack/email integrations to capture notes from existing workflows
- P1: Implement team-level sharing to make shared notes more valuable
- P1: Implement analytics dashboard to show team adoption and value
- Organizational: Secure executive sponsorship and team lead buy-in before launch
- Organizational: Conduct user research with Sarah and Marcus personas to understand barriers

**Owner:** Product Manager (strategy), Marketing (adoption), Leadership (sponsorship)

---

### Risk 3: Performance Degradation at Scale
**Risk:** Search and note loading become slow as the number of notes grows beyond 10,000.

**Likelihood:** Medium  
**Impact:** High (core feature becomes unusable)

**Mitigation:**
- MVP: Set performance targets (search < 1 second, load < 500ms)
- MVP: Implement monitoring and alerting for performance degradation
- MVP: Document performance boundary (optimized for up to 10,000 notes)
- P1: Implement search indexing strategy (TRD) to improve performance
- P1: Implement pagination/lazy loading for note lists
- P1: Implement caching for frequently-accessed notes

**Owner:** Engineering (implementation), Product Manager (monitoring)

---

### Risk 4: Data Security & Unauthorized Access
**Risk:** Sensitive notes are accessed by unauthorized users due to permission bugs or misconfiguration.

**Likelihood:** Medium  
**Impact:** Critical (compliance violation, data breach)

**Mitigation:**
- MVP: Implement strict permission checks on every note access (view, edit, delete)
- MVP: Implement audit logging for all access attempts (including failed attempts)
- MVP: Conduct security review before launch (penetration testing, code review)
- MVP: Implement role-based access control (RBAC) in P1
- MVP: Implement encryption at rest (infrastructure responsibility)
- MVP: Implement encryption in transit (HTTPS, TLS)
- Organizational: Conduct security training for admins and users

**Owner:** Engineering (implementation), Security (review), IT Admin (training)

---

### Risk 5: Knowledge Loss Due to Accidental Deletion
**Risk:** Users accidentally delete important notes and cannot recover them (if recovery window is too short or not communicated).

**Likelihood:** Medium  
**Impact:** Medium (user frustration, potential data loss)

**Mitigation:**
- MVP: Implement soft delete with 30-day recovery window
- MVP: Require confirmation before deletion (modal: "Are you sure?")
- MVP: Show deleted notes in a "Trash" section (visible to creator)
- MVP: Communicate recovery window clearly in UI
- P1: Implement note versioning/history to allow reverting to previous versions
- P1: Implement admin override to force-delete notes

**Owner:** Product Manager (UX), Engineering (implementation)

---

### Risk 6: Compliance & Audit Trail Gaps
**Risk:** Audit logs are incomplete or missing, making it impossible to meet compliance requirements (SOC 2, HIPAA, GDPR).

**Likelihood:** Medium  
**Impact:** Critical (compliance violation, regulatory fines)

**Mitigation:**
- MVP: Implement comprehensive audit logging (create, edit, delete, view, share, permission change)
- MVP: Make audit logs immutable (cannot be edited or deleted)
- MVP: Retain audit logs for minimum 90 days
- MVP: Implement audit log export (CSV) for compliance reporting
- MVP: Conduct compliance review before launch (with Alex persona)
- P1: Implement automated compliance reports
- P1: Implement real-time audit alerts for suspicious activity

**Owner:** Engineering (implementation), IT Admin (compliance review)

---

### Risk 7: Concurrent Editing Conflicts
**Risk:** If two users edit the same note simultaneously, one user's changes are lost (last-write-wins).

**Likelihood:** Low (MVP doesn't support simultaneous editing)  
**Impact:** Medium (user frustration, data loss)

**Mitigation:**
- MVP: Document that simultaneous editing is not supported
- MVP: Implement edit locking (if user A is editing, user B sees a "locked" indicator)
- MVP: Implement conflict detection (warn user if note was edited by someone else while they were editing)
- P2: Implement real-time collaborative editing with conflict resolution

**Owner:** Product Manager (documentation), Engineering (implementation)

---

### Risk 8: Multi-Tenant Data Leakage (If Applicable)
**Risk:** If multi-tenant support is added, notes from Organization A could be accessed by Organization B due to permission bugs.

**Likelihood:** Low (MVP is single-tenant)  
**Impact:** Critical (data breach, compliance violation)

**Mitigation:**
- MVP: Single-tenant only (no multi-tenant support)
- P1+: If multi-tenant is added, implement strict data isolation:
  - Separate databases or schemas per organization
  - Permission checks scoped to organization
  - Search results scoped to organization
  - Audit logs segregated by organization
- P1+: Conduct security review before multi-tenant launch

**Owner:** Product Manager (architecture decision), Engineering (implementation)

---

### Risk 9: Tag Governance Enforcement
**Risk:** Admins define "approved tags" but users continue creating unapproved tags, defeating governance goals.

**Likelihood:** Medium  
**Impact:** Low (governance goal not achieved, but product still functional)

**Mitigation:**
- P1: Implement "approved tags" feature (optional; admins can enforce)
- P1: Show warning when user tries to create unapproved tag
- P1: Provide admin dashboard showing tag usage and compliance
- P1: Implement tag deprecation warnings
- Organizational: Communicate tag governance policy to users

**Owner:** Product Manager (policy), Engineering (implementation)

---

### Risk 10: Onboarding Friction
**Risk:** Users don't complete onboarding or create first note, leading to low adoption.

**Likelihood:** Medium  
**Impact:** High (product fails to achieve adoption goals)

**Mitigation:**
- MVP: Make first note creation < 2 seconds (minimal friction)
- MVP: Provide in-app onboarding tutorial (optional, can be skipped)
- MVP: Provide clear documentation and help resources
- MVP: Conduct user testing with Sarah and Marcus personas to identify friction points
- P1: Implement email onboarding campaign
- P1: Implement team lead dashboard to track team adoption
- Organizational: Provide training and support during launch

**Owner:** Product Manager (UX), Marketing (onboarding campaign)

---

## OPEN QUESTIONS

### Critical Questions (Must Answer Before MVP Launch)

1. **Multi-Tenant Support:**
   - Is this product for a single organization or multiple organizations?
   - If multi-tenant, what's the data isolation strategy?
   - **Owner:** Product Manager, Leadership

2. **Compliance Requirements:**
   - What compliance standards must this product meet (SOC 2, HIPAA, GDPR, etc.)?
   - What audit trail requirements exist?
   - **Owner:** IT Admin (Alex), Compliance Officer

3. **Tag Governance:**
   - Should tag creation be restricted to admins, or permissive (any user)?
   - Should there be an "approved tags" whitelist?
   - **Owner:** Product Manager, Marcus (Team Lead)

4. **Search Performance Boundary:**
   - What's the expected number of notes at launch? In 1 year?
   - What's the acceptable search latency?
   - **Owner:** Product Manager, Engineering

5. **Concurrent Editing:**
   - Should the product support simultaneous editing by multiple users?
   - If yes, what's the conflict resolution strategy (merge, last-write-wins, etc.)?
   - **Owner:** Product Manager, Engineering

6. **Data Retention Policy:**
   - How long should soft-deleted notes be recoverable (30 days, 90 days, etc.)?
   - How long should audit logs be retained?
   - **Owner:** IT Admin (Alex), Compliance Officer

7. **Organizational Rollout:**
   - What's the target launch date?
   - Which teams/departments will be included in MVP launch?
   - What's the adoption target (% of employees)?
   - **Owner:** Product Manager, Leadership

### Important Questions (Should Answer Before P1 Planning)

8. **Tag Hierarchy:**
   - Should tags support parent-child relationships (e.g., "bug/critical", "bug/minor")?
   - Or should tags remain flat?
   - **Owner:** Product Manager, Marcus (Team Lead)

9. **Team-Level Sharing:**
   - Should notes be shareable with entire teams?
   - Should team membership changes automatically update note access?
   - **Owner:** Product Manager, Marcus (Team Lead)

10. **Granular Permissions:**
    - Should there be different permission levels (view-only vs. edit)?
    - Or should shared users always have edit access?
    - **Owner:** Product Manager, Marcus (Team Lead)

11. **Note Versioning:**
    - Should the product track note edit history?
    - Should users be able to revert to previous versions?
    - **Owner:** Product Manager, Sarah (Individual Contributor)

12. **Integrations:**
    - Should the product integrate with Slack, email, or other tools?
    - If yes, which integrations are highest priority?
    - **Owner:** Product Manager, Sarah (Individual Contributor)

### Nice-to-Have Questions (Can Answer Later)

13. **Mobile Support:**
    - Should there be native iOS/Android apps, or is web-only sufficient?
    - **Owner:** Product Manager

14. **Analytics:**
    - Should there be a dashboard showing note creation trends, tag usage, etc.?
    - **Owner:** Product Manager, Marcus (Team Lead)

15. **Rich Text Formatting:**
    - Should notes support bold, italic, lists, code blocks, etc.?
    - Or should notes remain plain text?
    - **Owner:** Product Manager, Sarah (Individual Contributor)

---

## APPENDIX: ACCEPTANCE CRITERIA

### P0 Feature Acceptance Criteria (Detailed)

#### P0.1: Create & Edit Notes — Acceptance Criteria

**Scenario 1: Create a New Note**
- Given: User is logged in and on the app home page
- When: User clicks "New Note" button
- Then: A new note form appears with empty title and body fields
- And: User can type in the title field (max 255 characters)
- And: User can type in the body field (max 50,000 characters)
- And: User can click "Save" button
- And: Note is saved within 2 seconds
- And: User sees a success confirmation (visual indicator, not modal)
- And: Note appears in the note list with the title and current timestamp

**Scenario 2: Edit an Existing Note**
- Given: User is viewing a note they created
- When: User clicks "Edit" button
- Then: Note title and body become editable
- And: User can modify the title and body
- And: User can click "Save" button
- And: Note is saved within 2 seconds
- And: "Last edited" timestamp is updated
- And: User sees a success confirmation

**Scenario 3: Auto-Save During Editing**
- Given: User is editing a note
- When: User has not clicked "Save" for 30 seconds
- Then: Note is automatically saved
- And: User sees a subtle auto-save indicator (e.g., "Saved" text)
- And: No modal or disruptive notification appears

**Scenario 4: Validation**
- Given: User is creating a new note
- When: User leaves the title field empty and clicks "Save"
- Then: An error message appears: "Title is required"
- And: Note is not saved
- When: User enters a title and clicks "Save"
- Then: Note is saved successfully

**Scenario 5: Character Limits**
- Given: User is editing a note
- When: User tries to enter more than 255 characters in the title field
- Then: The title field stops accepting input at 255 characters
- When: User tries to enter more than 50,000 characters in the body field
- Then: The body field stops accepting input at 50,000 characters

---

#### P0.2: Tag Notes — Acceptance Criteria

**Scenario 1: Add a Tag to a Note**
- Given: User is editing a note
- When: User clicks the "Add Tag" button
- Then: A tag input field appears
- And: User can type a tag name (e.g., "bug")
- And: User can press Enter or click "Add"
- Then: The tag is added to the note
- And: The tag appears as a chip/badge below the title
- And: The tag input field clears and is ready for another tag

**Scenario 2: Create a New Tag**
- Given: User is adding a tag to a note
- When: User types a tag name that doesn't exist yet (e.g., "urgent")
- And: User presses Enter or clicks "Add"
- Then: The new tag is created and added to the note
- And: The tag is now available for other notes (autocomplete)

**Scenario 3: Tag Autocomplete**
- Given: User is adding a tag to a note
- When: User starts typing "bu"
- Then: A dropdown appears with suggestions: "bug", "build", "business"
- And: User can click a suggestion to add it
- Or: User can continue typing to filter suggestions
- Or: User can press Escape to close the dropdown

**Scenario 4: Remove a Tag**
- Given: User is editing a note with tags
- When: User clicks the "X" button on a tag chip
- Then: The tag is removed from the note
- And: The tag is no longer displayed on the note

**Scenario 5: Tag Validation**
- Given: User is adding a tag to a note
- When: User tries to add a tag with special characters (e.g., "bug!")
- Then: An error message appears: "Tags can only contain letters, numbers, hyphens, and underscores"
- And: The tag is not added
- When: User enters a valid tag name (e.g., "bug-critical")
- Then: The tag is added successfully

**Scenario 6: Tag Limits**
- Given: User is editing a note with 10 tags
- When: User tries to add an 11th tag
- Then: An error message appears: "Maximum 10 tags per note"
- And: The tag is not added

**Scenario 7: Case Insensitivity**
- Given: A note has the tag "Bug"
- When: User adds a tag "bug" to another note
- Then: The system treats "Bug" and "bug" as the same tag
- And: Both notes appear when searching for "bug" or "Bug"

---

#### P0.3: Search Notes — Acceptance Criteria

**Scenario 1: Search by Title**
- Given: User is on the app home page
- When: User enters "meeting" in the search box
- Then: Search results appear showing notes with "meeting" in the title
- And: Results are returned in < 1 second
- And: Results are ranked by relevance (title matches first)

**Scenario 2: Search by Body**
- Given: User is on the app home page
- When: User enters "database" in the search box
- Then: Search results appear showing notes with "database" in the body
- And: Results show a preview of the matching text (first 100 characters)

**Scenario 3: Search by Tag**
- Given: User is on the app home page
- When: User enters "urgent" in the search box
- Then: Search results appear showing notes tagged with "urgent"
- And: Results are ranked below title/body matches

**Scenario 4: Empty Search**
- Given: User is on the app home page
- When: User clears the search box (empty query)
- Then: All notes accessible to the user are displayed
- And: Notes are sorted by last edited date (newest first)

**Scenario 5: No Results**
- Given: User is on the app home page
- When: User enters a search query that matches no notes (e.g., "xyzabc")
- Then: A message appears: "No notes found"
- And: No results are displayed

**Scenario 6: Search Permissions**
- Given: User A created a note "Secret Project"
- And: User A did not share the note with User B
- When: User B searches for "Secret Project"
- Then: The note does not appear in User B's search results
- And: User B does not see any indication that the note exists

**Scenario 7: Search Result Click**
- Given: User is viewing search results
- When: User clicks on a search result
- Then: The full note is displayed
- And: The search query is highlighted in the note body

**Scenario 8: Case Insensitivity**
- Given: A note has the title "Meeting Notes"
- When: User searches for "meeting notes" (lowercase)
- Then: The note appears in the search results

---

#### P0.4: View & Access Notes — Acceptance Criteria

**Scenario 1: View Note List**
- Given: User is logged in
- When: User navigates to the app home page
- Then: A list of all notes the user has access to is displayed
- And: Each note shows: title, last edited date, tags
- And: Notes are sorted by last edited date (newest first)
- And: A note count is displayed (e.g., "Showing 47 notes")

**Scenario 2: View Note Details**
- Given: User is viewing the note list
- When: User clicks on a note
- Then: The full note is displayed with:
  - Title
  - Body text
  - Tags
  - Creator name and creation date
  - Last editor name and last edited date
  - Edit button
  - Delete button
  - Share button

**Scenario 3: View Note Metadata**
- Given: User is viewing a note
- When: User looks at the note metadata
- Then: The following information is displayed:
  - "Created by [Creator Name] on [Date]"
  - "Last edited by [Editor Name] on [Date]"

**Scenario 4: Permission Check**
- Given: User A created a note and did not share it with User B
- When: User B tries to access the note (via direct link or search)
- Then: An error message appears: "You don't have access to this note"
- And: The note is not displayed

**Scenario 5: Empty Note List**
- Given: User has not created any notes and no notes have been shared with them
- When: User navigates to the app home page
- Then: A message appears: "No notes yet. Create your first note!"
- And: A "New Note" button is displayed

---

#### P0.5: Access Control & Permissions — Acceptance Criteria

**Scenario 1: Creator Has Full Permissions**
- Given: User A created a note
- When: User A views the note
- Then: User A can:
  - View the note
  - Edit the note
  - Delete the note
  - Share the note with others
  - Change permissions

**Scenario 2: Share Note with Specific User**
- Given: User A created a note
- When: User A clicks the "Share" button
- Then: A share dialog appears
- And: User A can enter the name or email of User B
- And: User A can click "Share"
- Then: User B now has access to the note
- And: User B can view and edit the note

**Scenario 3: Shared User Cannot Delete**
- Given: User A shared a note with User B
- When: User B views the note
- Then: User B can view and edit the note
- But: User B cannot delete the note
- And: The delete button is not visible or is disabled

**Scenario 4: Shared User Cannot Change Permissions**
- Given: User A shared a note with User B
- When: User B views the note
- Then: User B cannot share the note with others
- And: The share button is not visible or is disabled

**Scenario 5: View Permission List**
- Given: User A created a note and shared it with User B and User C
- When: User A clicks the "Share" button
- Then: A list of users with access is displayed:
  - User A (Creator)
  - User B (Shared)
  - User C (Shared)

**Scenario 6: Revoke Access**
- Given: User A shared a note with User B
- When: User A clicks the "Share" button
- And: User A clicks "Remove" next to User B
- Then: User B no longer has access to the note
- And: User B cannot view the note

**Scenario 7: Permission Change Audit**
- Given: User A shared a note with User B
- When: User A revokes access to User B
- Then: An audit log entry is created:
  - Action: "Permission Changed"
  - User: User A
  - Timestamp: [Current Time]
  - Details: "Revoked access for User B"

**Scenario 8: Default Private**
- Given: User A creates a new note
- When: User A saves the note
- Then: The note is private by default
- And: Only User A can access the note
- And: No other users have access

---

#### P0.6: Delete Notes — Acceptance Criteria

**Scenario 1: Delete a Note**
- Given: User A created a note
- When: User A clicks the "Delete" button
- Then: A confirmation dialog appears: "Are you sure you want to delete this note?"
- And: User A can click "Cancel" or "Delete"
- When: User A clicks "Delete"
- Then: The note is moved to trash (soft delete)
- And: The note is no longer visible in the note list
- And: A success message appears: "Note deleted"

**Scenario 2: Non-Creator Cannot Delete**
- Given: User A shared a note with User B
- When: User B views the note
- Then: User B cannot delete the note
- And: The delete button is not visible or is disabled

**Scenario 3: View Trash**
- Given: User A deleted a note
- When: User A clicks the "Trash" link
- Then: A list of deleted notes is displayed
- And: Each deleted note shows: title, deletion date
- And: User A can click a note to view it

**Scenario 4: Recover from Trash**
- Given: User A deleted a note and it's in trash
- When: User A clicks the "Restore" button
- Then: The note is moved back to the active notes list
- And: The note is no longer in trash
- And: A success message appears: "Note restored"

**Scenario 5: Permanent Deletion After 30 Days**
- Given: User A deleted a note 30 days ago
- When: The system runs the cleanup job
- Then: The note is permanently deleted (hard delete)
- And: The note cannot be recovered
- And: An audit log entry is created: "Note permanently deleted"

**Scenario 6: Delete Audit Log**
- Given: User A deleted a note
- When: An admin views the audit log
- Then: An entry is visible:
  - Action: "Delete"
  - User: User A
  - Timestamp: [Current Time]
  - Note ID: [Note ID]
  - Details: "Note moved to trash"

---

#### P0.7: Audit Logging — Acceptance Criteria

**Scenario 1: Create Action Logged**
- Given: User A creates a new note
- When: The note is saved
- Then: An audit log entry is created:
  - Timestamp: [Current Time]
  - User ID: [User A ID]
  - Action: "Create"
  - Note ID: [Note ID]
  - Details: "Note created with title 'Meeting Notes'"

**Scenario 2: Edit Action Logged**
- Given: User A edits a note
- When: The note is saved
- Then: An audit log entry is created:
  - Timestamp: [Current Time]
  - User ID: [User A ID]
  - Action: "Edit"
  - Note ID: [Note ID]
  - Details: "Note title changed from 'Meeting' to 'Meeting Notes'"

**Scenario 3: Delete Action Logged**
- Given: User A deletes a note
- When: The note is moved to trash
- Then: An audit log entry is created:
  - Timestamp: [Current Time]
  - User ID: [User A ID]
  - Action: "Delete"
  - Note ID: [Note ID]
  - Details: "Note moved to trash"

**Scenario 4: View Action Logged**
- Given: User A views a note
- When: The note is displayed
- Then: An audit log entry is created:
  - Timestamp: [Current Time]
  - User ID: [User A ID]
  - Action: "View"
  - Note ID: [Note ID]

**Scenario 5: Share Action Logged**
- Given: User A shares a note with User B
- When: The share is confirmed
- Then: An audit log entry is created:
  - Timestamp: [Current Time]
  - User ID: [User A ID]
  - Action: "Share"
  - Note ID: [Note ID]
  - Details: "Note shared with User B"

**Scenario 6: Permission Change Logged**
- Given: User A revokes access to a note from User B
- When: The permission change is confirmed
- Then: An audit log entry is created:
  - Timestamp: [Current Time]
  - User ID: [User A ID]
  - Action: "Permission Changed"
  - Note ID: [Note ID]
  - Details: "Revoked access for User B"

**Scenario 7: Failed Access Attempt Logged**
- Given: User B tries to view a note they don't have access to
- When: The access is denied
- Then: An audit log entry is created:
  - Timestamp: [Current Time]
  - User ID: [User B ID]
  - Action: "Failed Access"
  - Note ID: [Note ID]
  - Details: "User attempted to view note without permission"

**Scenario 8: Audit Log Immutability**
- Given: An audit log entry exists
- When: An admin tries to edit or delete the audit log entry
- Then: The action is denied
- And: An error message appears: "Audit logs cannot be modified"

**Scenario 9: Audit Log Retention**
- Given: An audit log entry was created 90 days ago
- When: The system runs the cleanup job
- Then: The audit log entry is retained (not deleted)
- When: An audit log entry was created 91 days ago
- Then: The audit log entry is deleted (after 90-day retention period)

**Scenario 10: Audit Log Export**
- Given: An admin is on the audit log page
- When: The admin clicks "Export to CSV"
- Then: A CSV file is generated with all audit log entries
- And: The CSV includes: timestamp, user ID, action, note ID, details
- And: The file is downloaded to the admin's computer

---

## DOCUMENT SIGN-OFF

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Manager | [Name] | [Date] | [Signature] |
| Engineering Lead | [Name] | [Date] | [Signature] |
| IT Admin / Security | [Name] | [Date] | [Signature] |
| Leadership / Sponsor | [Name] | [Date] | [Signature] |

---

## VERSION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | [Current Date] | Product Manager | Initial PRD for MVP launch |

---

## DOCUMENT METADATA

- **Document Type:** Product Requirements Document (PRD)
- **Product:** Internal Notes App with Tags and Search
- **Status:** Ready for Engineering Handoff
- **Audience:** Engineering, Product, Design, IT Admin, Leadership
- **Distribution:** Internal Only
- **Last Review Date:** [Current Date]
- **Next Review Date:** [Date + 30 days]

---

**END OF DOCUMENT**