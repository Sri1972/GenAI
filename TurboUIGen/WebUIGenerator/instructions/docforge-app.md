# DocForge — Product Development Document Factory

## App Overview

**App name:** DocForge
**Theme:** AI-powered document creation for product development teams — PRD, TRD, and Architecture documents generated through guided wizard conversations
**Accent color:** #4F46E5

---

## Data Model

### Table: documents
| Column | Type | Description |
|--------|------|-------------|
| doc_id | text | Unique ID (DOC-001 through DOC-020) |
| title | text | Document title |
| doc_type | categorical | PRD, TRD, Architecture |
| status | categorical | Draft, In Review, Approved, Archived |
| owner | text | Document owner name |
| team | categorical | Platform, Payments, Growth, Mobile, Data, Security |
| created_date | text | YYYY-MM-DD |
| updated_date | text | YYYY-MM-DD |
| version | text | Semantic version (1.0, 1.1, 2.0, etc.) |
| parent_doc_id | text | FK to parent document (TRD links to PRD, Arch links to TRD). Null for PRDs |
| summary | text | One-sentence summary (keep under 100 chars) |
| priority | categorical | P0, P1, P2, P3 |
| target_release | text | Quarter (Q1 2025, Q2 2025, etc.) |
| completion | numeric | Percentage complete 0–100 |

**Seed rows:** 15
**Seed notes:** Include 6 PRDs, 5 TRDs (each linked to a PRD via parent_doc_id), and 4 Architecture docs (each linked to a TRD). Statuses: 40% Draft, 30% In Review, 20% Approved, 10% Archived. Mix of teams and priorities. Show 3 complete chains (PRD → TRD → Arch). Keep summaries SHORT (one sentence, no special characters or quotes).

### Table: sections
| Column | Type | Description |
|--------|------|-------------|
| section_id | text | Unique ID (SEC-0001, SEC-0002, etc.) |
| doc_id | text | FK to documents |
| section_title | text | Section heading |
| section_order | numeric | Display order (1, 2, 3, ...) |
| content | text | Plain text content of the section |
| last_edited_by | text | Who last edited |
| ai_generated | categorical | Yes, No |

**Seed rows:** 0
**Seed notes:** Do NOT seed this table — leave it empty. Sections are created dynamically through the wizard and viewer. The documents table is sufficient for the Dashboard and Documents pages.

---

## Pages

Add 5 pages to the sidebar:
1. Dashboard
2. Documents
3. Create Document
4. Document Viewer
5. AI Assistant

---

### Page 1: Dashboard
**Sidebar label:** "Dashboard"

High-level overview of all documents in the pipeline.

- **KPI row (4 cards):**
  - Total Documents (count)
  - In Review (count where status = In Review)
  - Completion Rate (average completion %)
  - Document Chains (count of complete PRD → TRD → Arch chains)

- **Charts row (2 side-by-side):**
  - Left: Stacked bar — document count by team, stacked by doc_type (PRD/TRD/Architecture)
  - Right: Donut chart — documents by status (Draft/In Review/Approved/Archived)

- **Second row (2 side-by-side):**
  - Left: Horizontal bar — documents by priority (P0 red, P1 amber, P2 blue, P3 gray)
  - Right: Bar chart — document count by target_release quarter

- **Recent Activity (full width below):** Table showing last 10 updated documents: title, type badge, owner, status badge, updated_date, completion bar.

---

### Page 2: Documents
**Sidebar label:** "Documents"

Full document registry with filtering, linked chain view, and export.

- **Filter bar:**
  - Text search: title, owner, summary
  - Dropdown: Doc Type (PRD, TRD, Architecture)
  - Dropdown: Status (Draft, In Review, Approved, Archived)
  - Dropdown: Team
  - Dropdown: Priority
  - Reset button + count badge

- **View toggle:** List view / Chain view
  - List view: standard data table
  - Chain view: grouped cards showing PRD → TRD → Architecture chains with connecting arrows

- **Data table columns (list view):**
  - Title (bold, clickable)
  - Type (colored badge: PRD=indigo, TRD=teal, Architecture=purple)
  - Status (colored badge: Draft=gray, In Review=amber, Approved=green, Archived=slate)
  - Owner
  - Team (badge)
  - Priority (P0=red, P1=amber, P2=blue, P3=gray)
  - Version
  - Target Release
  - Completion (progress bar)
  - Updated (relative date)

- Sortable columns, paginated at 12 rows
- **Export CSV** button

---

### Page 3: Create Document
**Sidebar label:** "Create"

Multi-step wizard that guides the user through creating a PRD, TRD, or Architecture document via AI-assisted conversation.

- **Step 1 — Document Type Selection:**
  - Three large clickable cards:
    - PRD (indigo icon) — "Define the what and why"
    - TRD (teal icon) — "Define the how" — shows dropdown to link to existing PRD
    - Architecture (purple icon) — "Define the system design" — shows dropdown to link to existing TRD
  - Selecting a type advances to Step 2

- **Step 2 — Guided Questions (Wizard):**
  - Left side (60%): Question panel showing one question at a time with a text area for the answer
  - Right side (40%): Live document preview building up as questions are answered
  - Questions are presented one at a time with a progress bar at the top
  - Each answer can be typed manually OR the user can click "AI Suggest" to get an AI-generated answer they can edit
  - "Next" button advances to next question, "Back" button goes to previous
  - PRD questions: What problem are we solving? Who are the target users? What are the goals? What are the user stories? What are the requirements? What are the success metrics? What is the timeline? What are the dependencies?
  - TRD questions: What is the technical approach? What systems are involved? What are the API contracts? What is the data model? What is the testing strategy? What is the migration plan? What are the technical risks?
  - Architecture questions: What is the system context? What are the containers/services? How do components interact? What is the data flow? What infrastructure is needed? What are the security considerations?

- **Step 3 — Review & Edit:**
  - Full document preview rendered as formatted content (markdown-style)
  - Each section has an "Edit with AI" button that opens an inline chat
  - The inline chat lets the user give instructions like "make this more concise" or "add a user story about mobile" and the section content updates
  - "Add Section" button to insert new sections
  - "Reorder" drag handles on sections

- **Step 4 — Export:**
  - Document title input (editable)
  - Preview of final document
  - Two export buttons: "Export as DOCX" and "Export as Markdown"
  - "Save as Draft" button to save to the documents table

---

### Page 4: Document Viewer
**Sidebar label:** "Viewer"

Read and edit existing documents with AI-assisted refinement.

- **Document selector:** Dropdown at top to pick any document from the registry
- **Document header:** Title, type badge, status badge, owner, version, dates
- **Chain navigation:** If this doc is part of a chain, show breadcrumb links (PRD → TRD → Architecture)

- **Content area:** Renders all sections of the selected document in order
  - Each section shows: heading, content (rendered markdown), last edited by, ai_generated badge
  - Hover on any section shows "Edit with AI" button
  - Clicking "Edit with AI" opens an inline prompt input below the section
  - User types a refinement instruction (e.g., "expand on the scalability requirements")
  - AI returns updated section content, shown as a diff-style preview (additions in green, removals in red)
  - User can "Accept" or "Revert"

- **Sidebar panel (right):** Document metadata card + version history + linked documents

- **Export bar (bottom):** "Export DOCX" / "Export Markdown" / "Update Status" dropdown

---

### Page 5: AI Assistant
**Sidebar label:** "AI Assistant"

General-purpose AI chat for document creation help. Three-column layout with role personas.

**Left column:** Persona selector.
- Three persona cards — name, role, colored left border. Clicking selects.
- Below: 5 prompt buttons for active persona.

**Personas:**

- **Product Manager** (accent `#4F46E5`)
  Role context: "You are helping a Product Manager write product documents. Focus on user value, business outcomes, success metrics, and clear requirements. Keep language non-technical and stakeholder-friendly."
  Prompts:
  - Draft Problem Statement
  - Generate User Stories
  - Define Success Metrics
  - Competitive Analysis
  - Stakeholder Summary

- **Tech Lead** (accent `#0D9488`)
  Role context: "You are helping a Tech Lead write technical documents. Focus on system design, API contracts, data models, scalability, and implementation trade-offs. Be precise and include technical detail."
  Prompts:
  - System Design Overview
  - API Contract Template
  - Data Model Proposal
  - Migration Strategy
  - Risk Assessment

- **Solutions Architect** (accent `#7C3AED`)
  Role context: "You are helping a Solutions Architect write architecture documents. Focus on system boundaries, integration patterns, infrastructure decisions, security posture, and non-functional requirements. Think at the system level."
  Prompts:
  - C4 Context Diagram Description
  - Integration Pattern Options
  - Infrastructure Requirements
  - Security Threat Model
  - Scalability Analysis

**Center column:** Chat panel.
- User messages in dark bubbles, AI responses in light bubbles.
- Typing indicator while waiting.
- Free-text input at bottom — user can ask anything about document creation.
- AI can respond with text, tables, or structured content blocks.
- Each AI response has a "Copy to Document" button that copies the content to clipboard.

**Right column:** Export panel.
- Four template cards:
  - PRD Template (indigo)
  - TRD Template (teal)
  - Architecture Template (purple)
  - Custom Document (slate)
- Each has "Export PPTX" button to export the chat as a slide deck.

---

## Behavior notes

1. **Document chain linking** — when creating a TRD, the wizard auto-populates context from the linked PRD. Same for Architecture from TRD.
2. **AI-assisted editing** — any section can be refined via prompt. The AI sees the full document context.
3. **Export formats** — DOCX export produces a properly formatted Word document with headings, bullets, and tables. Markdown export produces clean .md.
4. **Wizard state** — if the user navigates away mid-wizard, their progress is preserved (localStorage).
5. **Version tracking** — each save increments the version number.
6. **Response caching** — repeated AI calls with the same prompt return cached results instantly.

---

## Visual Style

Use an indigo/violet professional palette. The Create page wizard should feel clean and focused — one question at a time, no visual clutter. The Document Viewer should feel like a modern document editor (think Notion/Confluence). Cards use subtle borders and shadows. Typography-heavy — good font sizes and spacing for readability since this is a content-creation tool.
