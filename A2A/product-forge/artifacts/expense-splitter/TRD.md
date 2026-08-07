# Technical Requirements Document: SplitPay

**Version:** 1.0  
**Date:** [Current Date]  
**Author:** Senior Backend Engineer  
**Status:** Ready for Implementation  

**Document Purpose:** This TRD translates business requirements from the PRD into detailed technical specifications, data models, API contracts, validation rules, error handling procedures, and architectural guidance. It serves as the authoritative source for backend and frontend engineering implementation, QA test planning, and system design decisions.

---

## TABLE OF CONTENTS

1. [Executive Summary & Architectural Overview](#executive-summary--architectural-overview)
2. [Technology Stack Rationale](#technology-stack-rationale)
3. [High-Level System Architecture](#high-level-system-architecture)
4. [Service Boundaries & Domain Model](#service-boundaries--domain-model)
5. [Data Model & Entity Definitions](#data-model--entity-definitions)
6. [Business Rules & Decision Logic](#business-rules--decision-logic)
7. [API Specifications](#api-specifications)
8. [External Integration Points](#external-integration-points)
9. [Validation Rules & Constraints](#validation-rules--constraints)
10. [Error Handling & Exception Flows](#error-handling--exception-flows)
11. [Non-Functional Requirements](#non-functional-requirements)
12. [Security & Data Protection Architecture](#security--data-protection-architecture)
13. [Audit Trail & Compliance Requirements](#audit-trail--compliance-requirements)
14. [Multi-User & Concurrency Considerations](#multi-user--concurrency-considerations)
15. [Deployment & Operational Considerations](#deployment--operational-considerations)
16. [Open Questions & Assumptions](#open-questions--assumptions)

---

## 1. EXECUTIVE SUMMARY & ARCHITECTURAL OVERVIEW

### 1.1 Problem Statement (Technical Perspective)

SplitPay solves the technical challenge of transforming unstructured receipt data (photos) into structured expense records that enable:

- **Accurate item-level attribution:** OCR extracts line items from receipt images; users claim items; system records ownership
- **Fair cost allocation:** Tax and tip are distributed proportionally based on item claims; system calculates precise per-person amounts
- **Transaction minimization:** Algorithm determines the minimum number of payments required to settle all debts
- **Recurring expense automation:** System tracks recurring splits (rent, utilities) and generates monthly reminders
- **Payment coordination:** System sends SMS/push notifications to trigger actual payments

### 1.2 Core Technical Objectives

1. **Reliability:** Receipt data must be accurately extracted and unambiguously assigned to users
2. **Consistency:** All financial calculations must be deterministic and auditable
3. **Responsiveness:** Receipt scanning and bill calculation must complete in <5 seconds
4. **Scalability:** System must support concurrent receipt uploads and real-time group coordination
5. **Traceability:** Every financial transaction must have a complete audit trail
6. **Resilience:** Payment reminders must be reliably delivered; failed reminders must be retried

### 1.3 Architectural Principles

- **Microservice-oriented:** Separate concerns into OCR service, expense calculation service, payment coordination service
- **Event-driven:** State changes (receipt uploaded, item claimed, payment sent) emit events for downstream processing
- **Database per service:** Each service owns its data; services communicate via APIs and events
- **Idempotent operations:** All financial operations must be safely retryable
- **Immutable audit trail:** All financial state changes are recorded and never modified
- **Fail-safe defaults:** On ambiguity or error, default to user-favorable outcomes (e.g., smaller amount owed)

---

## 2. TECHNOLOGY STACK RATIONALE

### 2.1 Backend Runtime & Framework

**Technology:** Node.js with Express.js

**Rationale:**
- [FROM PRD] Product specifies Node.js backend
- Non-blocking I/O handles concurrent receipt uploads and real-time group coordination
- Large ecosystem for OCR integration, SMS delivery, and payment processing
- Rapid iteration for MVP development
- Same language as potential shared utilities (validation, calculation logic)

**Constraints:**
- Must use TypeScript for type safety in financial calculations
- Must implement request context tracking (request IDs) for distributed tracing

### 2.2 Database

**Technology:** PostgreSQL with Sequelize or TypeORM ORM

**Rationale:**
- [FROM PRD] Product specifies PostgreSQL
- ACID transactions essential for financial consistency
- JSON support for flexible receipt data and metadata
- Strong type system and constraints prevent data corruption
- Excellent for audit logging and historical queries

**Constraints:**
- Must use prepared statements to prevent SQL injection
- Must implement row-level security for multi-tenant data isolation
- Must support full-text search on receipt line items

### 2.3 Frontend

**Technology:** React Native Web

**Rationale:**
- [FROM PRD] Product specifies React Native Web
- Single codebase for iOS, Android, and web
- Mobile-first design supports restaurant/trip use cases
- Enables real-time UI updates as group members claim items

**Constraints:**
- Must implement offline-first receipt capture (user may be in poor connectivity)
- Must support image upload with progress indication
- Must handle real-time updates via WebSocket or polling

### 2.4 OCR Service

**Technology:** [ASSUMPTION] Third-party OCR provider (AWS Textract, Google Vision, or Tesseract)

**Rationale:**
- [FROM PRD] Product requires OCR extraction of line items from receipt images
- Third-party services provide higher accuracy than custom models
- Reduces backend complexity and training data requirements
- Scalable to handle peak receipt upload volumes

**Constraints:**
- Must implement fallback OCR provider (circuit breaker pattern)
- Must cache OCR results keyed by image hash to avoid duplicate processing
- Must handle OCR failures gracefully (present to user for manual correction)

### 2.5 SMS/Push Notification Service

**Technology:** [ASSUMPTION] Third-party provider (Twilio for SMS, Firebase Cloud Messaging for push)

**Rationale:**
- [FROM PRD] Product requires SMS payment reminders and push notifications
- Third-party services handle carrier routing, delivery guarantees, and compliance
- Reduces operational burden of maintaining SMS infrastructure

**Constraints:**
- Must implement retry queue for failed SMS/push deliveries
- Must respect user notification preferences (opt-out)
- Must include request IDs in notification metadata for traceability

---

## 3. HIGH-LEVEL SYSTEM ARCHITECTURE

### 3.1 Service Decomposition

```
┌─────────────────────────────────────────────────────────────────┐
│                     React Native Web Client                      │
│              (iOS, Android, Web via Expo/React Native)          │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTPS + WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Gateway / Load Balancer                   │
│                  (Request routing, rate limiting)                │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Auth        │ │  Expense     │ │  Notification│
│  Service     │ │  Service     │ │  Service     │
├──────────────┤ ├──────────────┤ ├──────────────┤
│ • User login │ │ • Receipt    │ │ • SMS queue  │
│ • JWT tokens │ │   upload     │ │ • Push queue │
│ • Sessions   │ │ • OCR        │ │ • Delivery   │
└──────────────┘ │   extraction │ │   tracking   │
                 │ • Item       │ └──────────────┘
                 │   claiming   │
                 │ • Expense    │
                 │   calculation│
                 │ • Settlement │
                 │   logic      │
                 └──────────────┘
        │
        └────────────────┬────────────────┐
                         ▼                ▼
                  ┌──────────────┐ ┌──────────────┐
                  │ PostgreSQL   │ │ Redis Cache  │
                  │ (Primary DB) │ │ (Session,    │
                  │              │ │  OCR cache)  │
                  └──────────────┘ └──────────────┘
```

### 3.2 Service Responsibilities

#### 3.2.1 Auth Service
- User registration and login
- JWT token generation and validation
- Session management
- Multi-user access control

#### 3.2.2 Expense Service (Core)
- Receipt ingestion and OCR orchestration
- Line item extraction and storage
- Item claiming and ownership tracking
- Expense calculation (tax/tip allocation, per-person amounts)
- Settlement algorithm (transaction minimization)
- Recurring expense management
- Group and friendship management

#### 3.2.3 Notification Service
- SMS reminder queue management
- Push notification queue management
- Delivery status tracking
- Retry logic for failed deliveries
- User notification preference enforcement

### 3.3 Data Flow: Receipt Upload to Settlement

```
1. User uploads receipt image
   ├─ Client: Validate image (size, format, orientation)
   ├─ API: Receive upload, validate auth, generate request ID
   └─ DB: Store receipt record (status: "processing")

2. OCR Extraction
   ├─ Expense Service: Extract line items via OCR provider
   ├─ Cache: Store OCR results by image hash
   └─ DB: Update receipt with extracted items (status: "items_extracted")

3. Item Claiming
   ├─ Users: Claim items they ordered
   ├─ API: Validate claims (item exists, user in group, no conflicts)
   └─ DB: Record item ownership

4. Expense Calculation
   ├─ Expense Service: Receive "expense ready" signal
   ├─ Calculate: Tax/tip allocation based on claimed items
   ├─ Calculate: Per-person totals
   └─ DB: Store calculated amounts (status: "calculated")

5. Settlement Algorithm
   ├─ Expense Service: Determine minimum payment flows
   ├─ Algorithm: Reduce debt graph to minimize transactions
   └─ DB: Record settlement (who owes whom, amounts)

6. Payment Reminders
   ├─ Notification Service: Queue SMS/push for users owing money
   ├─ Delivery: Send via Twilio/Firebase
   └─ DB: Track delivery status

7. Payment Tracking
   ├─ Users: Mark payment as sent/received
   ├─ API: Validate payment claim
   └─ DB: Record payment, update settlement status
```

---

## 4. SERVICE BOUNDARIES & DOMAIN MODEL

### 4.1 Domain Entities

#### 4.1.1 User
- Represents an individual SplitPay user
- Owns personal settings, preferences, contact information

#### 4.1.2 Group
- Represents a collection of users (e.g., "NYC Friend Group", "Apartment 4B")
- Enables shared expense tracking across multiple events
- Supports recurring expenses within the group

#### 4.1.3 Receipt
- Represents a physical receipt (photo + extracted data)
- Contains OCR-extracted line items
- Associated with exactly one group and one "payer" (person who paid the bill)

#### 4.1.4 LineItem
- Represents a single line on a receipt (e.g., "Grilled Salmon - $24.99")
- Owned by exactly one user (claimed user) or marked as "shared"
- Immutable once created; changes require new line item

#### 4.1.5 Expense
- Represents the complete bill split for a receipt
- Contains calculated per-person amounts including tax/tip
- References receipt, group, and all participants
- Immutable once finalized

#### 4.1.6 Settlement
- Represents the minimum set of payments required to resolve an expense
- Generated from expense calculation
- Records "Person A owes Person B amount X"

#### 4.1.7 RecurringExpense
- Represents a repeating split (e.g., monthly rent, utilities)
- Generates new expenses on schedule
- Supports variable amounts

#### 4.1.8 Payment
- Represents a user claiming they sent or received money
- Linked to a settlement
- Immutable once recorded

### 4.2 Service API Contracts (High-Level)

#### 4.2.1 Auth Service API
```
POST /auth/register
POST /auth/login
POST /auth/refresh-token
POST /auth/logout
GET  /auth/me
```

#### 4.2.2 Expense Service API
```
POST   /receipts                    # Upload receipt
GET    /receipts/{id}               # Retrieve receipt + items
GET    /receipts                    # List receipts (paginated)
PATCH  /receipts/{id}/items/{item_id}/claim  # Claim item
POST   /expenses                    # Create expense from receipt
GET    /expenses/{id}               # Retrieve expense + settlement
GET    /expenses                    # List expenses (paginated)
POST   /settlements/{id}/payments   # Record payment
GET    /groups                      # List user's groups
POST   /groups                      # Create group
POST   /groups/{id}/members         # Add member to group
GET    /recurring-expenses          # List recurring expenses
POST   /recurring-expenses          # Create recurring expense
```

#### 4.2.3 Notification Service API
```
GET    /notifications               # List pending notifications
POST   /notifications/{id}/resend   # Retry failed notification
PATCH  /users/{id}/notification-preferences  # Update preferences
```

---

## 5. DATA MODEL & ENTITY DEFINITIONS

### 5.1 PostgreSQL Schema

#### 5.1.1 users Table

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) NOT NULL UNIQUE,
  phone_number VARCHAR(20),
  password_hash VARCHAR(255) NOT NULL,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  profile_picture_url VARCHAR(2048),
  
  -- Notification preferences
  sms_notifications_enabled BOOLEAN DEFAULT true,
  push_notifications_enabled BOOLEAN DEFAULT true,
  email_notifications_enabled BOOLEAN DEFAULT true,
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP,
  
  CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'),
  CONSTRAINT valid_phone CHECK (phone_number IS NULL OR phone_number ~* '^\+?1?\d{9,15}$')
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_phone ON users(phone_number);
```

#### 5.1.2 groups Table

```sql
CREATE TABLE groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  created_by_user_id UUID NOT NULL REFERENCES users(id),
  
  -- Group type determines behavior (one-time dinner vs recurring rent split)
  type VARCHAR(50) NOT NULL CHECK (type IN ('one_time', 'recurring')),
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP,
  
  CONSTRAINT valid_name CHECK (name ~ '^.{1,255}$')
);

CREATE INDEX idx_groups_created_by ON groups(created_by_user_id);
```

#### 5.1.3 group_members Table

```sql
CREATE TABLE group_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(50) NOT NULL DEFAULT 'member' CHECK (role IN ('admin', 'member')),
  
  -- Audit fields
  joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  left_at TIMESTAMP,
  
  UNIQUE(group_id, user_id),
  CONSTRAINT active_member CHECK (left_at IS NULL)
);

CREATE INDEX idx_group_members_group ON group_members(group_id);
CREATE INDEX idx_group_members_user ON group_members(user_id);
```

#### 5.1.4 receipts Table

```sql
CREATE TABLE receipts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id UUID NOT NULL REFERENCES groups(id),
  payer_user_id UUID NOT NULL REFERENCES users(id),
  
  -- Image metadata
  image_url VARCHAR(2048) NOT NULL,
  image_hash VARCHAR(64),  -- SHA-256 for deduplication
  
  -- OCR extraction
  status VARCHAR(50) NOT NULL DEFAULT 'pending' 
    CHECK (status IN ('pending', 'processing', 'items_extracted', 'error', 'cancelled')),
  ocr_raw_text TEXT,  -- Raw OCR output for debugging
  ocr_error_message TEXT,
  
  -- Receipt metadata
  receipt_date DATE,
  merchant_name VARCHAR(255),
  total_amount DECIMAL(10, 2),
  currency VARCHAR(3) NOT NULL DEFAULT 'USD',
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP,
  
  CONSTRAINT valid_total CHECK (total_amount IS NULL OR total_amount >= 0)
);

CREATE INDEX idx_receipts_group ON receipts(group_id);
CREATE INDEX idx_receipts_payer ON receipts(payer_user_id);
CREATE INDEX idx_receipts_status ON receipts(status);
CREATE INDEX idx_receipts_image_hash ON receipts(image_hash);
```

#### 5.1.5 line_items Table

```sql
CREATE TABLE line_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_id UUID NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
  
  -- Item details
  name VARCHAR(255) NOT NULL,
  description TEXT,
  quantity DECIMAL(10, 2) NOT NULL DEFAULT 1.0,
  unit_price DECIMAL(10, 2) NOT NULL,
  subtotal DECIMAL(10, 2) NOT NULL,  -- quantity * unit_price
  
  -- Ownership
  claimed_by_user_id UUID REFERENCES users(id),
  is_shared BOOLEAN NOT NULL DEFAULT false,
  
  -- Status
  status VARCHAR(50) NOT NULL DEFAULT 'unclaimed'
    CHECK (status IN ('unclaimed', 'claimed', 'shared', 'error')),
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP,
  
  CONSTRAINT valid_quantity CHECK (quantity > 0),
  CONSTRAINT valid_price CHECK (unit_price >= 0 AND subtotal >= 0),
  CONSTRAINT ownership_logic CHECK (
    (is_shared = false AND claimed_by_user_id IS NOT NULL) OR
    (is_shared = true AND claimed_by_user_id IS NULL) OR
    (status = 'error')
  )
);

CREATE INDEX idx_line_items_receipt ON line_items(receipt_id);
CREATE INDEX idx_line_items_claimed_by ON line_items(claimed_by_user_id);
CREATE INDEX idx_line_items_status ON line_items(status);
```

#### 5.1.6 expenses Table

```sql
CREATE TABLE expenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_id UUID NOT NULL UNIQUE REFERENCES receipts(id),
  group_id UUID NOT NULL REFERENCES groups(id),
  
  -- Totals
  subtotal DECIMAL(10, 2) NOT NULL,
  tax_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
  tip_amount DECIMAL(10, 2) NOT NULL DEFAULT 0,
  total_amount DECIMAL(10, 2) NOT NULL,
  currency VARCHAR(3) NOT NULL DEFAULT 'USD',
  
  -- Status
  status VARCHAR(50) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'finalized', 'settled', 'cancelled')),
  
  -- Metadata
  description TEXT,
  expense_date DATE NOT NULL,
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finalized_at TIMESTAMP,
  deleted_at TIMESTAMP,
  
  CONSTRAINT valid_amounts CHECK (
    subtotal >= 0 AND tax_amount >= 0 AND tip_amount >= 0 AND total_amount >= 0
  ),
  CONSTRAINT total_equals_sum CHECK (
    total_amount = subtotal + tax_amount + tip_amount
  )
);

CREATE INDEX idx_expenses_receipt ON expenses(receipt_id);
CREATE INDEX idx_expenses_group ON expenses(group_id);
CREATE INDEX idx_expenses_status ON expenses(status);
```

#### 5.1.7 expense_participants Table

```sql
CREATE TABLE expense_participants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  expense_id UUID NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  
  -- Calculated amounts
  item_subtotal DECIMAL(10, 2) NOT NULL,  -- Sum of claimed items
  tax_share DECIMAL(10, 2) NOT NULL,      -- Proportional tax
  tip_share DECIMAL(10, 2) NOT NULL,      -- Proportional tip
  total_owed DECIMAL(10, 2) NOT NULL,     -- item_subtotal + tax_share + tip_share
  
  -- Status
  status VARCHAR(50) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'settled', 'cancelled')),
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE(expense_id, user_id),
  CONSTRAINT valid_amounts CHECK (
    item_subtotal >= 0 AND tax_share >= 0 AND tip_share >= 0 AND total_owed >= 0
  ),
  CONSTRAINT total_owed_equals_sum CHECK (
    total_owed = item_subtotal + tax_share + tip_share
  )
);

CREATE INDEX idx_expense_participants_expense ON expense_participants(expense_id);
CREATE INDEX idx_expense_participants_user ON expense_participants(user_id);
```

#### 5.1.8 settlements Table

```sql
CREATE TABLE settlements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  expense_id UUID NOT NULL REFERENCES expenses(id),
  
  -- Payment flow
  debtor_user_id UUID NOT NULL REFERENCES users(id),
  creditor_user_id UUID NOT NULL REFERENCES users(id),
  amount DECIMAL(10, 2) NOT NULL,
  currency VARCHAR(3) NOT NULL DEFAULT 'USD',
  
  -- Status
  status VARCHAR(50) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'payment_sent', 'payment_received', 'cancelled')),
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  settled_at TIMESTAMP,
  
  CONSTRAINT valid_amount CHECK (amount > 0),
  CONSTRAINT different_users CHECK (debtor_user_id != creditor_user_id)
);

CREATE INDEX idx_settlements_expense ON settlements(expense_id);
CREATE INDEX idx_settlements_debtor ON settlements(debtor_user_id);
CREATE INDEX idx_settlements_creditor ON settlements(creditor_user_id);
CREATE INDEX idx_settlements_status ON settlements(status);
```

#### 5.1.9 payments Table

```sql
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  settlement_id UUID NOT NULL REFERENCES settlements(id),
  
  -- Payment claim
  claimed_by_user_id UUID NOT NULL REFERENCES users(id),
  claimed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  -- Verification
  status VARCHAR(50) NOT NULL DEFAULT 'claimed'
    CHECK (status IN ('claimed', 'verified', 'disputed')),
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  CONSTRAINT valid_claim CHECK (
    claimed_by_user_id IN (
      SELECT debtor_user_id FROM settlements WHERE id = settlement_id
      UNION
      SELECT creditor_user_id FROM settlements WHERE id = settlement_id
    )
  )
);

CREATE INDEX idx_payments_settlement ON payments(settlement_id);
CREATE INDEX idx_payments_claimed_by ON payments(claimed_by_user_id);
```

#### 5.1.10 recurring_expenses Table

```sql
CREATE TABLE recurring_expenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id UUID NOT NULL REFERENCES groups(id),
  
  -- Recurrence details
  name VARCHAR(255) NOT NULL,
  description TEXT,
  frequency VARCHAR(50) NOT NULL CHECK (frequency IN ('weekly', 'biweekly', 'monthly')),
  base_amount DECIMAL(10, 2) NOT NULL,
  currency VARCHAR(3) NOT NULL DEFAULT 'USD',
  
  -- Participants
  payer_user_id UUID NOT NULL REFERENCES users(id),
  
  -- Schedule
  start_date DATE NOT NULL,
  end_date DATE,
  next_due_date DATE NOT NULL,
  
  -- Status
  status VARCHAR(50) NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'paused', 'cancelled')),
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  CONSTRAINT valid_amount CHECK (base_amount > 0),
  CONSTRAINT valid_dates CHECK (start_date <= next_due_date AND (end_date IS NULL OR end_date >= start_date))
);

CREATE INDEX idx_recurring_expenses_group ON recurring_expenses(group_id);
CREATE INDEX idx_recurring_expenses_payer ON recurring_expenses(payer_user_id);
CREATE INDEX idx_recurring_expenses_next_due ON recurring_expenses(next_due_date);
```

#### 5.1.11 recurring_expense_participants Table

```sql
CREATE TABLE recurring_expense_participants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  recurring_expense_id UUID NOT NULL REFERENCES recurring_expenses(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  
  -- Split configuration
  split_type VARCHAR(50) NOT NULL DEFAULT 'equal'
    CHECK (split_type IN ('equal', 'percentage', 'fixed_amount')),
  split_value DECIMAL(10, 2),  -- Percentage (0-100) or fixed amount
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  UNIQUE(recurring_expense_id, user_id),
  CONSTRAINT valid_split_value CHECK (
    (split_type = 'equal' AND split_value IS NULL) OR
    (split_type = 'percentage' AND split_value >= 0 AND split_value <= 100) OR
    (split_type = 'fixed_amount' AND split_value > 0)
  )
);

CREATE INDEX idx_recurring_participants_recurring ON recurring_expense_participants(recurring_expense_id);
```

#### 5.1.12 audit_log Table

```sql
CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Context
  user_id UUID REFERENCES users(id),
  request_id VARCHAR(36) NOT NULL,
  
  -- Action
  action_type VARCHAR(100) NOT NULL,
  entity_type VARCHAR(50) NOT NULL,
  entity_id UUID,
  
  -- Changes
  old_values JSONB,
  new_values JSONB,
  
  -- Metadata
  ip_address INET,
  user_agent TEXT,
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  CONSTRAINT valid_action CHECK (action_type IN ('create', 'update', 'delete', 'claim', 'settle'))
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_request ON audit_log(request_id);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at);
```

#### 5.1.13 notification_queue Table

```sql
CREATE TABLE notification_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- Recipient
  recipient_user_id UUID NOT NULL REFERENCES users(id),
  
  -- Notification details
  notification_type VARCHAR(50) NOT NULL
    CHECK (notification_type IN ('payment_reminder', 'payment_received', 'expense_finalized')),
  
  -- Delivery channels
  sms_status VARCHAR(50) DEFAULT 'pending'
    CHECK (sms_status IN ('pending', 'sent', 'failed', 'skipped')),
  push_status VARCHAR(50) DEFAULT 'pending'
    CHECK (push_status IN ('pending', 'sent', 'failed', 'skipped')),
  
  -- Payload
  payload JSONB NOT NULL,
  
  -- Retry logic
  retry_count INT NOT NULL DEFAULT 0,
  max_retries INT NOT NULL DEFAULT 3,
  next_retry_at TIMESTAMP,
  
  -- Audit fields
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  
  CONSTRAINT valid_retry CHECK (retry_count <= max_retries)
);

CREATE INDEX idx_notification_queue_recipient ON notification_queue(recipient_user_id);
CREATE INDEX idx_notification_queue_status ON notification_queue(sms_status, push_status);
CREATE INDEX idx_notification_queue_next_retry ON notification_queue(next_retry_at);
```

### 5.2 Entity Relationships & Constraints

```
User (1) ──────────── (N) Group
  │
  ├─ (1) ──────────── (N) Receipt
  │
  ├─ (1) ──────────── (N) LineItem (claimed_by)
  │
  ├─ (1) ──────────── (N) ExpenseParticipant
  │
  ├─ (1) ──────────── (N) Settlement (debtor/creditor)
  │
  └─ (1) ──────────── (N) RecurringExpense (payer)

Group (1) ──────────── (N) Receipt
  │
  ├─ (1) ──────────── (N) GroupMember
  │
  ├─ (1) ──────────── (N) Expense
  │
  └─ (1) ──────────── (N) RecurringExpense

Receipt (1) ──────────── (N) LineItem
  │
  └─ (1) ──────────── (1) Expense (unique)

Expense (1) ──────────── (N) ExpenseParticipant
  │
  └─ (1) ──────────── (N) Settlement

Settlement (1) ──────────── (N) Payment
```

---

## 6. BUSINESS RULES & DECISION LOGIC

### 6.1 Receipt Processing & OCR

#### Rule 6.1.1: Receipt Image Validation
**Trigger:** User uploads receipt image

**Validation:**
- Image format: JPEG, PNG, or WebP
- Image size: ≤10 MB
- Image dimensions: ≥640x480 pixels (minimum readability)
- Image orientation: Auto-corrected if needed

**Action on Failure:**
- Return 400 Bad Request with specific validation error
- Provide guidance to user (e.g., "Image too small, try higher resolution photo")

#### Rule 6.1.2: OCR Extraction
**Trigger:** Receipt image passes validation

**Process:**
1. Compute SHA-256 hash of image; check cache for prior OCR results
2. If cache hit: Return cached OCR results (skip external call)
3. If cache miss: Call OCR provider (Textract/Vision/Tesseract)
4. Parse OCR output to extract line items (name, price, quantity)
5. Store raw OCR text in `receipts.ocr_raw_text` for audit
6. Cache OCR results with 24-hour TTL

**Failure Handling:**
- OCR provider timeout (>30 seconds): Return 503 Service Unavailable
- OCR provider error: Retry up to 3 times with exponential backoff (1s, 2s, 4s)
- If all retries fail: Update receipt status to "error"; notify user to manually enter items

**Output:**
- Array of LineItem records with `status='unclaimed'`
- Update receipt status to `'items_extracted'`

#### Rule 6.1.3: Line Item Extraction
**Trigger:** OCR extraction completes

**Algorithm:**
1. Parse OCR text to identify candidate line items (typically rows with price)
2. For each candidate:
   - Extract name (text before price)
   - Extract quantity (if present, default 1.0)
   - Extract unit_price and compute subtotal
   - Validate price is positive and reasonable (< $500 per item)
3. Validate total of all line items ≈ receipt total (within 5% tolerance)
4. If line items total deviates >5% from receipt total, flag for manual review

**Constraints:**
- Minimum 1 line item per receipt
- Maximum 100 line items per receipt
- Each line item name ≥3 characters, ≤255 characters

### 6.2 Item Claiming Logic

#### Rule 6.2.1: Item Ownership Assignment
**Trigger:** User claims a line item

**Validation:**
- Item exists in receipt
- Item status is `'unclaimed'`
- User is member of receipt's group
- User is not the payer (optional: payer cannot claim items from their own receipt)

**Action:**
- Set `line_items.claimed_by_user_id = user_id`
- Set `line_items.status = 'claimed'`
- Update `line_items.updated_at = now()`
- Log audit event: `action_type='claim'`

**Failure Responses:**
- Item already claimed by another user: 409 Conflict
- User not in group: 403 Forbidden
- Item does not exist: 404 Not Found

#### Rule 6.2.2: Shared Item Handling
**Trigger:** Multiple users want to claim the same item (e.g., shared appetizer)

**Process:**
1. First user claims item normally (status → `'claimed'`)
2. Second user attempts to claim same item
3. System detects conflict; prompts for shared split
4. User selects "Mark as shared" option
5. Item status → `'shared'`; `is_shared = true`; `claimed_by_user_id = NULL`
6. Create implicit split: item cost divided equally among all users who claimed it

**Shared Item Calculation:**
- Shared item subtotal ÷ number of claimants = per-person share
- Each claimant receives share as part of `expense_participants.item_subtotal`

**Constraints:**
- Shared items must be claimed by ≥2 users
- Shared item cost split equally (no weighted splits for MVP)

#### Rule 6.2.3: Item Unclaiming
**Trigger:** User changes their mind about claimed item

**Process:**
1. Validate item was claimed by this user
2. Set `line_items.claimed_by_user_id = NULL`
3. Set `line_items.status = 'unclaimed'`
4. If item was shared, remove user from shared split

**Constraint:**
- Cannot unclaim item if expense is finalized

### 6.3 Expense Calculation Logic

#### Rule 6.3.1: Tax & Tip Allocation
**Trigger:** User finalizes an expense (marks all items claimed)

**Algorithm:**

```
INPUT:
  - line_items: array of claimed items with subtotals
  - tax_amount: total tax on receipt
  - tip_amount: total tip on receipt

PROCESS:
  1. Calculate total_item_subtotal = sum(line_items.subtotal)
  
  2. For each participant:
     a. item_subtotal = sum of items claimed by participant
     b. participant_proportion = item_subtotal / total_item_subtotal
     c. tax_share = tax_amount * participant_proportion
     d. tip_share = tip_amount * participant_proportion
     e. total_owed = item_subtotal + tax_share + tip_share

  3. Validate: sum(all tax_shares) ≈ tax_amount (within $0.01)
  4. Validate: sum(all tip_shares) ≈ tip_amount (within $0.01)
  5. Validate: sum(all total_owed) = total_item_subtotal + tax_amount + tip_amount

OUTPUT:
  - expense_participants records with calculated amounts
  - expense status → 'finalized'
```

**Rounding:**
- All monetary amounts rounded to 2 decimal places
- Rounding errors (pennies) accumulated and added to largest item owner's bill

**Example:**
```
Receipt Total: $100.00
  Item 1 (Salmon): $24.99 → claimed by Alice
  Item 2 (Steak): $28.50 → claimed by Bob
  Item 3 (Pasta): $18.99 → claimed by Charlie
  Subtotal: $72.48
  Tax: $5.79
  Tip: $21.73
  Total: $100.00

Alice proportion: $24.99 / $72.48 = 34.49%
  tax_share = $5.79 * 0.3449 = $1.997 ≈ $2.00
  tip_share = $21.73 * 0.3449 = $7.498 ≈ $7.50
  total_owed = $24.99 + $2.00 + $7.50 = $34.49

Bob proportion: $28.50 / $72.48 = 39.31%
  tax_share = $5.79 * 0.3931 = $2.277 ≈ $2.28
  tip_share = $21.73 * 0.3931 = $8.547 ≈ $8.55
  total_owed = $28.50 + $2.28 + $8.55 = $39.33

Charlie proportion: $18.99 / $72.48 = 26.20%
  tax_share = $5.79 * 0.2620 = $1.516 ≈ $1.51
  tip_share = $21.73 * 0.2620 = $5.685 ≈ $5.68
  total_owed = $18.99 + $1.51 + $5.68 = $26.18

Verification:
  sum(totals) = $34.49 + $39.33 + $26.18 = $100.00 ✓
```

#### Rule 6.3.2: Unclaimed Items
**Scenario:** Some items remain unclaimed after all users have claimed

**Decision:**
- If unclaimed items represent <5% of receipt total: Distribute equally among all participants
- If unclaimed items represent ≥5% of receipt total: Flag for manual review; prompt user to claim or discard items

### 6.4 Settlement Algorithm (Transaction Minimization)

#### Rule 6.4.1: Debt Graph Reduction
**Trigger:** Expense finalized; settlement records need to be created

**Algorithm:**

```
INPUT:
  - participants: array of users with total_owed amounts
  - payer: user who paid the receipt

PROCESS:
  1. Calculate net balance for each participant:
     net_balance = total_owed - amount_paid_by_participant
     (For non-payer, amount_paid = 0; for payer, amount_paid = receipt total)

  2. Separate into debtors (net_balance < 0) and creditors (net_balance > 0)

  3. Sort debtors by amount owed (descending)
  4. Sort creditors by amount owed (descending)

  5. While debtors exist:
     a. Take largest debtor; take largest creditor
     b. Settle minimum of (debtor_amount, creditor_amount)
     c. If debtor fully settled, remove from list
     d. If creditor fully settled, remove from list

OUTPUT:
  - Minimal set of settlement records (who owes whom, amounts)

EXAMPLE:
  Alice owes $34.49 (net_balance = -$34.49)
  Bob owes $39.33 (net_balance = -$39.33)
  Charlie owes $26.18 (net_balance = -$26.18)
  Payer (Dave) paid $100, should receive $100 back
  
  Net balances:
    Alice: -$34.49 (owes)
    Bob: -$39.33 (owes)
    Charlie: -$26.18 (owes)
    Dave: +$100.00 (owed)
  
  Settlements:
    1. Bob → Dave: $39.33
    2. Alice → Dave: $34.49
    3. Charlie → Dave: $26.18
  
  Total: 3 settlements (minimum possible)
```

**Constraints:**
- Settlement amounts must be positive (>$0.00)
- Settlement amounts must match expense_participants calculations (within $0.01)

#### Rule 6.4.2: Multi-Payer Scenarios
**Scenario:** Multiple users paid portions of the bill (e.g., one paid with card, one with cash)

**Process:**
1. For each payer, calculate their net balance
2. Apply settlement algorithm to all participants and payers
3. Generate settlement records accordingly

**[ASSUMPTION]** MVP assumes single payer per receipt; multi-payer support deferred to future release

### 6.5 Recurring Expense Logic

#### Rule 6.5.1: Recurring Expense Generation
**Trigger:** Scheduled job runs daily; checks for recurring expenses with `next_due_date <= today`

**Process:**
1. Query recurring_expenses where `next_due_date <= today` and `status = 'active'`
2. For each recurring expense:
   a. Create new Receipt record (auto-generated, no image)
   b. Create LineItem for recurring expense (name, base_amount)
   c. Create Expense record
   d. Create ExpenseParticipant records per recurring_expense_participants
   e. Calculate Settlement records
   f. Update recurring_expense.next_due_date based on frequency:
      - weekly: +7 days
      - biweekly: +14 days
      - monthly: +1 month
   g. Queue notification: "Your [Expense Name] is due today"

**Split Calculation:**
```
For each participant in recurring_expense_participants:
  IF split_type = 'equal':
    share = base_amount / num_participants
  ELSE IF split_type = 'percentage':
    share = base_amount * (split_value / 100)
  ELSE IF split_type = 'fixed_amount':
    share = split_value
  
  Create expense_participant with item_subtotal = share
```

**Constraints:**
- Recurring expense cannot end before start_date
- If end_date is reached, update status to 'completed' and do not generate new expense

#### Rule 6.5.2: Recurring Expense Cancellation
**Trigger:** User cancels recurring expense

**Process:**
1. Set recurring_expense.status = 'cancelled'
2. Do not generate future expenses for this recurring_expense
3. Existing generated expenses remain unchanged

---

## 7. API SPECIFICATIONS

### 7.1 Authentication API

#### 7.1.1 POST /auth/register

**Purpose:** Register a new user account

**Request:**
```json
{
  "email": "alice@example.com",
  "password": "SecurePassword123!",
  "first_name": "Alice",
  "last_name": "Smith",
  "phone_number": "+1-555-0123"
}
```

**Validation:**
- `email`: Valid email format; must be unique; case-insensitive
- `password`: ≥8 characters; must contain uppercase, lowercase, number, and special character
- `first_name`: 1-100 characters; alphanumeric + spaces
- `last_name`: 1-100 characters; alphanumeric + spaces
- `phone_number`: Valid E.164 format (optional); must be unique if provided

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "alice@example.com",
  "first_name": "Alice",
  "last_name": "Smith",
  "phone_number": "+1-555-0123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
- 400 Bad Request: Invalid input (validation error)
  ```json
  {
    "error": "validation_error",
    "message": "Password must contain uppercase, lowercase, number, and special character",
    "field": "password"
  }
  ```
- 409 Conflict: Email already registered
  ```json
  {
    "error": "duplicate_email",
    "message": "Email already registered"
  }
  ```

**Idempotency:** Not idempotent (creates new user on each call)

---

#### 7.1.2 POST /auth/login

**Purpose:** Authenticate user and return JWT token

**Request:**
```json
{
  "email": "alice@example.com",
  "password": "SecurePassword123!"
}
```

**Validation:**
- `email`: Required; valid email format
- `password`: Required; non-empty

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600,
  "token_type": "Bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "alice@example.com",
    "first_name": "Alice",
    "last_name": "Smith"
  }
}
```

**Error Responses:**
- 400 Bad Request: Missing required fields
- 401 Unauthorized: Invalid email or password
  ```json
  {
    "error": "invalid_credentials",
    "message": "Email or password is incorrect"
  }
  ```

**Idempotency:** Idempotent (same credentials always return same token)

**Token Details:**
- `access_token`: JWT with 1-hour expiration; includes user ID and email
- `refresh_token`: JWT with 30-day expiration; used to obtain new access token
- JWT payload:
  ```json
  {
    "sub": "550e8400-e29b-41d4-a716-446655440000",
    "email": "alice@example.com",
    "iat": 1705318200,
    "exp": 1705321800,
    "iss": "splitpay-api"
  }
  ```

---

#### 7.1.3 POST /auth/refresh-token

**Purpose:** Obtain new access token using refresh token

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

**Error Responses:**
- 401 Unauthorized: Invalid or expired refresh token

**Idempotency:** Idempotent

---

#### 7.1.4 POST /auth/logout

**Purpose:** Invalidate user's tokens (optional; tokens expire naturally)

**Request:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (204 No Content)**

**Idempotency:** Idempotent

---

#### 7.1.5 GET /auth/me

**Purpose:** Retrieve authenticated user's profile

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "alice@example.com",
  "first_name": "Alice",
  "last_name": "Smith",
  "phone_number": "+1-555-0123",
  "sms_notifications_enabled": true,
  "push_notifications_enabled": true,
  "email_notifications_enabled": false,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Error Responses:**
- 401 Unauthorized: Missing or invalid token

**Idempotency:** Idempotent

---

### 7.2 Receipt & Expense API

#### 7.2.1 POST /receipts

**Purpose:** Upload receipt image and initiate OCR processing

**Headers:**
```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

**Request:**
```
multipart/form-data:
  - file: <binary image data> (JPEG, PNG, WebP; max 10 MB)
  - group_id: "550e8400-e29b-41d4-a716-446655440001" (UUID)
  - receipt_date: "2024-01-15" (ISO 8601; optional)
  - merchant_name: "Olive Garden" (string; optional)
```

**Validation:**
- `file`: Required; JPEG/PNG/WebP; ≤10 MB; ≥640x480 pixels
- `group_id`: Required; must be UUID; user must be member of group
- `receipt_date`: Optional; ISO 8601 date format
- `merchant_name`: Optional; 1-255 characters

**Response (202 Accepted):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "group_id": "550e8400-e29b-41d4-a716-446655440001",
  "payer_user_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "image_url": "https://cdn.splitpay.com/receipts/550e8400-e29b-41d4-a716-446655440002.jpg",
  "receipt_date": "2024-01-15",
  "merchant_name": "Olive Garden",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Processing:**
- Image stored in object storage (S3/GCS)
- Receipt record created with status='processing'
- OCR job queued asynchronously
- Client polls GET /receipts/{id} to check status

**Error Responses:**
- 400 Bad Request: Invalid image format, size, or dimensions
  ```json
  {
    "error": "invalid_image",
    "message": "Image must be at least 640x480 pixels",
    "field": "file"
  }
  ```
- 401 Unauthorized: Missing or invalid token
- 403 Forbidden: User not member of group
- 404 Not Found: Group does not exist
- 413 Payload Too Large: Image exceeds 10 MB

**Idempotency:** Not idempotent (creates new receipt each time); include `X-Request-ID` for deduplication if needed

**Rate Limiting:**
- 10 receipt uploads per minute per user
- Return 429 Too Many Requests if exceeded

---

#### 7.2.2 GET /receipts/{id}

**Purpose:** Retrieve receipt and extracted line items

**Headers:**
```
Authorization: Bearer <access_token>
```

**Path Parameters:**
- `id`: Receipt UUID

**Query Parameters:**
- `include_items`: boolean (default: true) — include line items in response

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440002",
  "group_id": "550e8400-e29b-41d4-a716-446655440001",
  "payer_user_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "items_extracted",
  "image_url": "https://cdn.splitpay.com/receipts/550e8400-e29b-41d4-a716-446655440002.jpg",
  "receipt_date": "2024-01-15",
  "merchant_name": "Olive Garden",
  "total_amount": "100.00",
  "currency": "USD",
  "line_items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440003",
      "name": "Grilled Salmon",
      "quantity": 1.0,
      "unit_price": "24.99",
      "subtotal": "24.99",
      "status": "claimed",
      "claimed_by_user_id": "550e8400-e29b-41d4-a716-446655440010",
      "is_shared": false,
      "created_at": "2024-01-15T10:30:05Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440004",
      "name": "House Salad",
      "quantity": 1.0,
      "unit_price": "8.99",
      "subtotal": "8.99",
      "status": "unclaimed",
      "claimed_by_user_id": null,
      "is_shared": false,
      "created_at": "2024-01-15T10:30:05Z"
    }
  ],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:05Z"
}
```

**Processing Status Values:**
- `pending`: Image uploaded, awaiting OCR processing
- `processing`: OCR in progress
- `items_extracted`: OCR complete, line items available
- `error`: OCR failed; user should manually enter items
- `cancelled`: Receipt cancelled by user

**Error Responses:**
- 401 Unauthorized: Missing or invalid token
- 403 Forbidden: User not member of receipt's group
- 404 Not Found: Receipt does not exist

**Idempotency:** Idempotent

---

#### 7.2.3 GET /receipts

**Purpose:** List receipts for authenticated user's groups

**Headers:**
```
Authorization: Bearer <access_token>
```

**Query Parameters:**
```
?group_id=550e8400-e29b-41d4-a716-446655440001
&status=items_extracted,error
&limit=20
&offset=0
&sort_by=created_at
&sort_order=desc
```

- `group_id`: Filter by group (optional; if omitted, returns receipts from all user's groups)
- `status`: Filter by status (optional; comma-separated list)
- `limit`: Max results per page (default: 20; max: 100)
- `offset`: Pagination offset (default: 0)
- `sort_by`: Sort field (default: created_at; allowed: created_at, receipt_date, total_amount)
- `sort_order`: asc or desc (default: desc)

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "group_id": "550e8400-e29b-41d4-a716-446655440001",
      "payer_user_id": "550e8400-e29b-41d4-a716-446655440000",
      "status": "items_extracted",
      "image_url": "https://cdn.splitpay.com/receipts/550e8400-e29b-41d4-a716-446655440002.jpg",
      "receipt_date": "2024-01-15",
      "merchant_name": "Olive Garden",
      "total_amount": "100.00",
      "currency": "USD",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 42,
    "has_more": true
  }
}
```

**Idempotency:** Idempotent

**Rate Limiting:** 100 requests per minute per user

---

#### 7.2.4 PATCH /receipts/{id}/items/{item_id}/claim

**Purpose:** User claims a line item

**Headers:**
```
Authorization: Bearer <access_token>
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

**Path Parameters:**
- `id`: Receipt UUID
- `item_id`: LineItem UUID

**Request Body:**
```json
{
  "action": "claim",
  "shared": false
}
```

- `action`: "claim" or "unclaim"
- `shared`: boolean (optional; default: false) — if true, marks item as shared split

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440003",
  "name": "Grilled Salmon",
  "quantity": 1.0,
  "unit_price": "24.99",
  "subtotal": "24.99",
  "status": "claimed",
  "claimed_by_user_id": "550e8400-e29b-41d4-a716-446655440000",
  "is_shared": false,
  "updated_at": "2024-01-15T10:32:00Z"
}
```

**Validation:**
- Receipt must exist and status must be 'items_extracted'
- LineItem must exist in receipt
- User must be member of receipt's group
- If claiming: item status must be 'unclaimed' or 'shared'
- If unclaiming: item must be claimed by this user
- Cannot unclaim if expense is finalized

**Conflict Resolution (Multiple Claims):**
If second user attempts to claim already-claimed item:
- Return 409 Conflict
- Suggest "Mark as shared" option
- Response:
  ```json
  {
    "error": "item_already_claimed",
    "message": "Item already claimed by another user. Mark as shared to split?",
    "claimed_by_user_id": "550e8400-e29b-41d4-a716-446655440010",
    "suggested_action": "shared"
  }
  ```

**Error Responses:**
- 400 Bad Request: Invalid action or parameters
- 401 Unauthorized: Missing or invalid token
- 403 Forbidden: User not member of group
- 404 Not Found: Receipt or item does not exist
- 409 Conflict: Item already claimed by another user
- 422 Unprocessable Entity: Cannot unclaim if expense finalized

**Idempotency:** Idempotent (claiming same item twice is no-op)

---

#### 7.2.5 POST /expenses

**Purpose:** Create expense from receipt (finalize bill split)

**Headers:**
```
Authorization: Bearer <access_token>
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
```

**Request Body:**
```json
{
  "receipt_id": "550e8400-e29b-41d4-a716-446655440002",
  "tax_amount": "5.79",
  "tip_amount": "21.73",
  "description": "Dinner at Olive Garden - Jan 15"
}
```

**Validation:**
- `receipt_id`: Required; must exist; status must be 'items_extracted'
- `tax_amount`: Required; ≥0; ≤receipt total
- `tip_amount`: Required; ≥0; ≤receipt total
- `description`: Optional; 1-500 characters
- All line items must be claimed (or marked shared/unclaimed)
- At least one item must be claimed

**Calculation:**
1. Sum claimed item subtotals → total_item_subtotal
2. For each participant, calculate proportional tax and tip
3. Create expense_participants records
4. Apply settlement algorithm to generate settlement records
5. Create notification queue entries for payment reminders

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440005",
  "receipt_id": "550e8400-e29b-41d4-a716-446655440002",
  "group_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "finalized",
  "subtotal": "72.48",
  "tax_amount": "5.79",
  "tip_amount": "21.73",
  "total_amount": "100.00",
  "currency": "USD",
  "description": "Dinner at Olive Garden - Jan 15",
  "participants": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "first_name": "Alice",
      "email": "alice@example.com",
      "item_subtotal": "24.99",
      "tax_share": "2.00",
      "tip_share": "7.50",
      "total_owed": "34.49",
      "status": "pending"
    },
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440010",
      "first_name": "Bob",
      "email": "bob@example.com",
      "item_subtotal": "28.50",
      "tax_share": "2.28",
      "tip_share": "8.55",
      "total_owed": "39.33",
      "status": "pending"
    },
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440011",
      "first_name": "Charlie",
      "email": "charlie@example.com",
      "item_subtotal": "18.99",
      "tax_share": "1.51",
      "tip_share": "5.68",
      "total_owed": "26.18",
      "status": "pending"
    }
  ],
  "settlements": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440020",
      "debtor_user_id": "550e8400-e29b-41d4-a716-446655440000",
      "debtor_name": "Alice",
      "creditor_user_id": "550e8400-e29b-41d4-a716-446655440010",
      "creditor_name": "Bob",
      "amount": "34.49",
      "status": "pending"
    },
    {