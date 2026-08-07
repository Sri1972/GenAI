# TEST_CASES.md

**SplitPay: Comprehensive Test Cases & Test Strategy**

**Version:** 1.0  
**Date:** [Current Date]  
**Author:** Senior QA Engineer  
**Status:** Ready for QA Execution & Automation Planning  

**Document Purpose:** This document provides detailed, executable test cases organized by feature/epic, covering functional, integration, end-to-end, performance, security, and edge-case scenarios. Each test case includes preconditions, step-by-step instructions, expected results, test data requirements, and priority classification. This is the authoritative source for QA execution, test automation planning, regression prevention, and quality assurance across all SplitPay features.

---

## TABLE OF CONTENTS

1. [Test Strategy Overview](#1-test-strategy-overview)
2. [Test Levels & Scope](#2-test-levels--scope)
3. [Test Execution Environment & Data Setup](#3-test-execution-environment--data-setup)
4. [Epic 1: User Authentication & Account Management](#4-epic-1-user-authentication--account-management)
5. [Epic 2: Receipt Capture & OCR Processing](#5-epic-2-receipt-capture--ocr-processing)
6. [Epic 3: Item Claiming & Expense Categorization](#6-epic-3-item-claiming--expense-categorization)
7. [Epic 4: Expense Calculation & Settlement Logic](#7-epic-4-expense-calculation--settlement-logic)
8. [Epic 5: Payment Coordination & Reminders](#8-epic-5-payment-coordination--reminders)
9. [Epic 7: Group Management & Invitations](#9-epic-7-group-management--invitations)
10. [Epic 8: Data Persistence & Audit Trail](#10-epic-8-data-persistence--audit-trail)
11. [Cross-Feature Integration Tests](#11-cross-feature-integration-tests)
12. [Performance & Load Testing](#12-performance--load-testing)
13. [Security & Compliance Testing](#13-security--compliance-testing)
14. [Regression Test Suite](#14-regression-test-suite)
15. [Test Automation Strategy](#15-test-automation-strategy)
16. [Test Data Management](#16-test-data-management)
17. [Defect Tracking & Quality Metrics](#17-defect-tracking--quality-metrics)
18. [Appendix: Test Case Template](#18-appendix-test-case-template)

---

## 1. TEST STRATEGY OVERVIEW

### 1.1 Mission Statement

**SplitPay QA ensures that every bill split is accurate, every payment reminder is delivered, and every user interaction is frictionless.** We employ a multi-layered testing strategy that catches bugs at the unit level, validates integrations at the service level, exercises end-to-end workflows, and stress-tests the system under realistic load. Quality is not a phase — it's built into every commit, every deployment, and every release.

### 1.2 Core Testing Principles

1. **Test the Behavior, Not the Implementation:** Tests validate user-facing outcomes (e.g., "settlement calculation is accurate") rather than internal implementation details (e.g., "SettlementService calls calculateMinimumTransactions()").

2. **Every Test Has a Single Clear Assertion:** Tests fail for exactly one reason. If a test fails, the failure message immediately identifies the problem.

3. **Prioritize by Risk:** Tests focus on high-risk scenarios first:
   - **Critical Risk:** Financial calculations (settlement, tax/tip allocation), authentication, data persistence
   - **High Risk:** OCR accuracy, payment reminders, group management
   - **Medium Risk:** UI responsiveness, error messages, edge cases
   - **Low Risk:** Cosmetic UI, non-critical labels, nice-to-have features

4. **Negative Testing is Non-Negotiable:** For every positive test, there's a corresponding negative test. Invalid input, unauthorized access, timeout scenarios, and error conditions are tested as rigorously as happy paths.

5. **Test at the Right Level:** Unit tests validate calculations. Integration tests validate service interactions. E2E tests validate complete user workflows. Performance tests validate system capacity. Each level has a specific purpose.

6. **Realistic Data & Volume:** Tests use realistic data volumes, not toy datasets. A receipt with 3 items hides bugs that appear with 30 items. A settlement with 2 users hides bugs that appear with 10 users.

7. **Deterministic & Repeatable:** Tests do not depend on execution order, external state, or timing. Every test is independently executable and produces the same result every time.

8. **Security is Built-In:** Every test considers security implications. Auth bypass attempts, injection attacks, privilege escalation, and data leakage are tested alongside functional requirements.

### 1.3 Testing Pyramid

```
                       ▲
                      /|\
                     / | \
                    /  |  \        E2E Tests (10%)
                   /   |   \       - Full user workflows
                  /    |    \      - Mobile & web browsers
                 /     |     \     - Real payment reminders
                /      |      \
               /       |       \
              /        |        \   Integration Tests (30%)
             /         |         \  - API contracts
            /          |          \ - Service interactions
           /           |           \- Database consistency
          /            |            \
         /             |             \
        /              |              \ Unit Tests (60%)
       /               |               \- Calculations
      /                |                \- Validation
     /                 |                 \- Algorithms
    /__________________V__________________\
```

### 1.4 Test Scope & Coverage Targets

| **Test Level** | **Coverage Target** | **Execution Time** | **Frequency** | **Owner** |
|---|---|---|---|---|
| **Unit Tests** | ≥80% code coverage (critical paths 100%) | <5 minutes | Every commit | Developers + CI |
| **Integration Tests** | 100% of API contracts, all service interactions | <15 minutes | Every commit | QA + CI |
| **E2E Tests** | All critical user journeys, happy path + error scenarios | <30 minutes | Every commit to staging | QA + CI |
| **Performance Tests** | Load: 100 concurrent users; stress: 500 concurrent users | <20 minutes | Daily on staging | QA + DevOps |
| **Security Tests** | OWASP Top 10, injection, auth bypass, data leakage | <15 minutes | Daily on staging | Security + QA |
| **Regression Suite** | All critical paths + previous defects | <30 minutes | Every production deployment | QA + CI |

### 1.5 Quality Gates

**No code is deployed to production unless:**
- [ ] All unit tests pass (≥80% coverage)
- [ ] All integration tests pass
- [ ] All E2E tests pass
- [ ] Performance tests show p95 latency <500ms (receipt processing), <200ms (queries)
- [ ] Security tests show zero critical/high vulnerabilities
- [ ] Manual regression testing on staging passes
- [ ] Product owner approval (manual sign-off)

---

## 2. TEST LEVELS & SCOPE

### 2.1 Unit Tests

**Purpose:** Validate individual functions, classes, and modules in isolation.

**Scope:**
- Business logic: calculations, algorithms, validation rules
- Error handling: exceptions, edge cases, boundary values
- Data transformations: parsing, formatting, normalization

**Examples:**
- `CalculationService.calculateTaxAllocation()` with various tax rates and item counts
- `SettlementService.minimizeTransactions()` with various debt graphs
- `ValidationService.validateEmail()` with valid/invalid/edge-case emails
- `OcrParser.parseReceiptItems()` with various receipt formats

**Technology:**
- Framework: Jest (Node.js backend), Jest (React Native frontend)
- Mocking: Jest mocks for external services (OCR provider, SMS service)
- Fixtures: Test data factories for users, receipts, expenses

**Execution:**
- Run on every commit (pre-commit hook)
- Run in CI/CD pipeline (before build)
- Developers run locally before pushing

---

### 2.2 Integration Tests

**Purpose:** Validate interactions between services, APIs, and database.

**Scope:**
- API endpoints: request validation, response format, status codes
- Service interactions: one service calls another correctly
- Database transactions: ACID properties, consistency
- Event flows: state changes trigger correct downstream actions
- External integrations: OCR provider, SMS service (mocked with contract tests)

**Examples:**
- `POST /api/v1/auth/register` creates user in DB and returns JWT token
- `POST /api/v1/receipts/:id/claim-item` validates user is in group and updates DB
- `GET /api/v1/settlements/:id` returns accurate settlement calculation
- `POST /api/v1/expenses/:id/finalize` triggers SMS reminder notifications

**Technology:**
- Framework: Jest with supertest (API testing), Sequelize test transactions
- Database: PostgreSQL test instance (reset between test suites)
- Mocking: Mocked OCR provider, SMS service (contract tests validate against real API)
- Fixtures: Seed data for users, groups, receipts, expenses

**Execution:**
- Run in CI/CD pipeline (after unit tests)
- Run on staging environment (daily smoke tests)
- Developers run locally after code changes

---

### 2.3 End-to-End (E2E) Tests

**Purpose:** Validate complete user workflows from signup to settlement.

**Scope:**
- User journeys: signup → login → upload receipt → claim items → view settlement → receive reminder
- Multi-user scenarios: group coordination, concurrent item claiming
- Error recovery: invalid input → error message → retry → success
- Mobile & web: iOS Safari, Chrome Android, desktop Chrome/Safari
- Real payment reminders: SMS/push delivery (staging environment)

**Examples:**
- **Journey 1 (Social Sarah):** Sign up → create group → invite friend → upload receipt → claim items → view settlement → receive SMS reminder
- **Journey 2 (Trip Coordinator Tina):** Create group → add 6 members → upload 3 receipts → each member claims items → view total settlement → export
- **Journey 3 (Error Recovery):** Upload receipt → OCR fails → user manually corrects items → save → calculate settlement
- **Journey 4 (Concurrent Claiming):** Two users simultaneously claim same item → system detects conflict → error message → user resolves

**Technology:**
- Framework: Playwright (cross-browser automation)
- Browsers: Chromium (Chrome), Firefox (for coverage), WebKit (Safari)
- Devices: iPhone 12 Pro, Pixel 6 (mobile viewports)
- Mocking: Real staging environment; SMS/push delivery via test accounts
- Data: Fresh test data for each test run (no test data pollution)

**Execution:**
- Run in CI/CD pipeline (after integration tests, before production deployment)
- Run on staging environment (full production-like setup)
- QA runs manually on real devices weekly

---

### 2.4 Performance & Load Testing

**Purpose:** Validate system capacity, latency, and scalability under realistic load.

**Scope:**
- Receipt upload & OCR processing: latency at 10, 50, 100, 200 concurrent users
- Settlement calculation: latency with 2, 5, 10, 20 users in group
- Payment reminder delivery: throughput of 1000, 5000, 10000 SMS/push per hour
- Database query performance: response time for settlement queries
- Concurrent data modifications: item claiming, expense finalization under load

**Scenarios:**
- **Baseline:** 10 concurrent users, normal operations, measure baseline latency/throughput
- **Load:** 100 concurrent users, sustained 10 minutes, measure p50/p95/p99 latency
- **Stress:** 500 concurrent users, 5 minutes, measure breaking point and recovery
- **Spike:** 100→500 concurrent users in 30 seconds, measure auto-scaling response
- **Soak:** 50 concurrent users, 2 hours, measure memory leaks, connection pool exhaustion

**Metrics:**
- Response time (p50, p95, p99, max)
- Throughput (requests/second)
- Error rate (% of failed requests)
- Resource utilization (CPU, memory, network)
- Database connection pool utilization
- Third-party API latency (OCR provider, SMS service)

**Technology:**
- Framework: k6 (load testing), Apache JMeter (alternative)
- Scenarios: Written in JavaScript (k6) or XML (JMeter)
- Monitoring: Real-time dashboards via Grafana, post-test analysis via CloudWatch
- Baseline: Establish baseline metrics in Sprint 0; compare future tests against baseline

**Execution:**
- Run daily on staging environment (off-peak hours)
- Run before production deployment (sanity check)
- Run after major feature changes (regression detection)

---

### 2.5 Security Testing

**Purpose:** Validate authentication, authorization, data protection, and compliance.

**Scope:**
- Authentication: login bypass, token tampering, session hijacking, credential stuffing
- Authorization: privilege escalation, horizontal escalation (access other user's data)
- Input validation: SQL injection, XSS, command injection, XXE
- Data protection: encryption at rest/in transit, password hashing, secret management
- API security: rate limiting, CORS, CSRF, HTTPS enforcement
- Third-party risks: OCR provider compromise, SMS provider compromise
- Compliance: GDPR (data deletion), PII handling, audit trails

**Test Cases:**
- **Auth Bypass:** Attempt login without password, modify JWT token, replay expired token
- **Privilege Escalation:** Claim item for another user, view another user's settlements, delete another user's group
- **Injection:** SQL injection in email field, XSS in receipt notes, command injection in OCR response parsing
- **Data Leakage:** Check response headers for sensitive data, verify PII is not logged, verify deleted data is removed
- **Rate Limiting:** Exceed rate limit, verify 429 response, verify legitimate traffic is not blocked
- **HTTPS:** Verify all API calls use HTTPS, verify certificate is valid, verify mixed content is blocked

**Technology:**
- Framework: OWASP ZAP (automated scanning), Burp Suite (manual testing), custom scripts
- Baseline: OWASP Top 10, CWE Top 25, GDPR compliance checklist
- Reporting: Vulnerability severity (critical, high, medium, low), remediation guidance

**Execution:**
- Run daily on staging environment (automated OWASP ZAP scan)
- Run weekly manual security testing (Burp Suite, custom scripts)
- Run before production deployment (security sign-off)
- External security audit (pre-launch, annually)

---

## 3. TEST EXECUTION ENVIRONMENT & DATA SETUP

### 3.1 Test Environments

| **Environment** | **Purpose** | **Data** | **Isolation** | **Teardown** |
|---|---|---|---|---|
| **Local Dev** | Developer laptop, offline-first | Synthetic test data | Complete isolation | N/A (developer-managed) |
| **Staging (Pre-Prod)** | Integration, E2E, load, security testing | Sanitized production-like data | Separate DB, separate AWS account | Reset after each test run |
| **Production** | Live traffic, real users | Real user data (encrypted) | Separate AWS account | N/A (production data) |

### 3.2 Test Data Setup & Teardown

**Principle:** Every test starts with a clean slate. No test depends on data created by another test. Teardown is automatic.

**Setup Strategy:**

1. **Database Reset:**
   - Before each integration/E2E test suite, reset PostgreSQL to baseline schema
   - Use database transactions: each test runs in a transaction that rolls back after completion
   - Avoid manual cleanup (error-prone); use transactional rollback

2. **Seed Data:**
   - Create minimal set of test users, groups, receipts before each test
   - Use test data factories (e.g., `createUser()`, `createReceipt()`) for consistent, repeatable data
   - Factories generate realistic but deterministic data (e.g., user emails: `test-user-1@splitpay.test`)

3. **Fixtures:**
   - Store common test data in `tests/fixtures/` directory
   - Examples: sample receipt images, OCR responses, settlement calculations
   - Fixtures are version-controlled and reviewed like code

**Teardown Strategy:**

1. **Transactional Rollback:**
   - Each test runs in a database transaction
   - After test completes, transaction rolls back
   - No manual cleanup needed; database is automatically clean

2. **File Cleanup:**
   - Delete uploaded receipt images from S3/local storage after test
   - Delete generated reports/exports after test
   - Use Jest afterEach() hook for cleanup

3. **External Service Cleanup:**
   - Delete test SMS/push records from staging accounts
   - Delete test user accounts from OCR provider (if applicable)
   - Use Jest afterAll() hook for suite-level cleanup

### 3.3 Test Data Requirements

**User Data:**
```javascript
// Test user factory
createUser({
  email: 'test-user-1@splitpay.test',
  password: 'TestPassword123!',
  firstName: 'Test',
  lastName: 'User',
  phoneNumber: '+1-555-0001' // For SMS testing
})
```

**Group Data:**
```javascript
// Test group factory
createGroup({
  name: 'Test Group - Dinner',
  description: 'Test group for dinner split',
  createdBy: userId,
  members: [userId1, userId2, userId3]
})
```

**Receipt Data:**
```javascript
// Test receipt factory
createReceipt({
  groupId: groupId,
  uploadedBy: userId,
  imageUrl: 's3://test-bucket/receipts/receipt-001.jpg',
  ocrStatus: 'extracted', // or 'pending', 'failed'
  lineItems: [
    { description: 'Salmon', price: 18.99 },
    { description: 'Caesar Salad', price: 12.99 },
    { description: 'Pasta', price: 15.99 }
  ],
  subtotal: 47.97,
  tax: 4.80,
  tip: 9.60,
  total: 62.37
})
```

**Expense Data:**
```javascript
// Test expense factory
createExpense({
  groupId: groupId,
  receiptId: receiptId,
  status: 'settled', // or 'pending', 'finalized'
  participants: [
    { userId: userId1, itemIds: [itemId1], amountOwed: 20.79 },
    { userId: userId2, itemIds: [itemId2], amountOwed: 15.59 },
    { userId: userId3, itemIds: [itemId3], amountOwed: 25.99 }
  ],
  settlement: [
    { from: userId2, to: userId1, amount: 5.20 },
    { from: userId3, to: userId1, amount: 5.20 }
  ]
})
```

### 3.4 Test Data Isolation & Cleanup

**Database Isolation:**
- Each test suite runs in a separate database transaction
- Changes are rolled back after test completes
- No test pollution; each test is independent

**File Isolation:**
- Test receipt images stored in `s3://test-bucket/receipts/` (not production bucket)
- Test files deleted after test completes
- No test data left in production storage

**API Isolation:**
- Test API calls use staging endpoints (not production)
- Test user accounts created in staging database (not production)
- Test SMS/push notifications sent to staging accounts (not real users)

---

## 4. EPIC 1: USER AUTHENTICATION & ACCOUNT MANAGEMENT

### 4.1 Test Scope

**Features Tested:**
- User registration with email and password
- Email verification (confirmation link)
- User login with email and password
- JWT token generation and validation
- Password reset via email
- Session management and token refresh
- User profile management (name, phone number)
- Logout and session termination

**Personas:** All (Social Sarah, Roommate Ryan, Trip Coordinator Tina)

**Critical Paths:**
1. Registration → Email Verification → Login → Access App
2. Login → JWT Token Generation → API Access
3. Password Reset → Email Link → New Password → Login
4. Profile Update → Phone Number Added → SMS Reminders Enabled

---

### 4.2 Happy Path Test Cases

#### TC-AUTH-001: User Registration with Valid Email and Password

**Test ID:** TC-AUTH-001  
**Type:** Functional / API  
**Priority:** Critical  
**Preconditions:**
- App is running and accessible
- Test email `test-user-001@splitpay.test` is not registered
- Database is in clean state

**Test Steps:**
1. Navigate to sign-up screen
2. Enter email: `test-user-001@splitpay.test`
3. Enter password: `SecurePassword123!`
4. Enter first name: `Test`
5. Enter last name: `User`
6. Confirm password: `SecurePassword123!`
7. Click "Sign Up" button
8. Observe response

**Expected Result:**
- HTTP 201 Created response
- Response body includes:
  - `user_id` (UUID)
  - `email`: `test-user-001@splitpay.test`
  - `first_name`: `Test`
  - `last_name`: `User`
  - `access_token` (JWT, expires in 1 hour)
  - `refresh_token` (JWT, expires in 30 days)
- User is redirected to email verification screen
- Email verification email is sent to registered email address
- User record is created in database with:
  - `is_active`: true
  - `email_verified`: false
  - `password_hash`: bcrypt hash (not plaintext)
  - `created_at`: current timestamp

**Test Data:**
- Email: `test-user-001@splitpay.test`
- Password: `SecurePassword123!`
- First Name: `Test`
- Last Name: `User`

**Assertions:**
- [ ] HTTP status code is 201
- [ ] Response includes valid JWT tokens
- [ ] User record exists in database
- [ ] Password is hashed (not plaintext)
- [ ] Email verification email is sent
- [ ] User is not yet able to access core features (email_verified=false)

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-AUTH-002: User Login with Valid Credentials

**Test ID:** TC-AUTH-002  
**Type:** Functional / API  
**Priority:** Critical  
**Preconditions:**
- User `test-user-002@splitpay.test` is registered and email-verified
- Password: `SecurePassword123!`
- Database is in clean state

**Test Steps:**
1. Navigate to login screen
2. Enter email: `test-user-002@splitpay.test`
3. Enter password: `SecurePassword123!`
4. Click "Login" button
5. Observe response

**Expected Result:**
- HTTP 200 OK response
- Response body includes:
  - `user_id` (UUID)
  - `email`: `test-user-002@splitpay.test`
  - `access_token` (JWT, expires in 1 hour)
  - `refresh_token` (JWT, expires in 30 days)
- User is redirected to app home screen
- JWT token is stored in secure storage (localStorage/keychain)
- Subsequent API calls include JWT token in Authorization header

**Test Data:**
- Email: `test-user-002@splitpay.test`
- Password: `SecurePassword123!`

**Assertions:**
- [ ] HTTP status code is 200
- [ ] Response includes valid JWT tokens
- [ ] access_token is valid and can be used for API calls
- [ ] refresh_token is valid and can be used to refresh access_token
- [ ] User is redirected to home screen
- [ ] JWT token is persisted in secure storage

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-AUTH-003: Email Verification Link Activates Account

**Test ID:** TC-AUTH-003  
**Type:** Functional / API  
**Priority:** Critical  
**Preconditions:**
- User `test-user-003@splitpay.test` is registered (email_verified=false)
- Email verification email has been sent
- Database is in clean state

**Test Steps:**
1. Retrieve email verification link from sent email (test account)
2. Click verification link in email
3. Observe response

**Expected Result:**
- HTTP 200 OK response
- User is redirected to app home screen
- User's `email_verified` field is set to true in database
- User can now access core features (receipt upload, expense viewing)
- Subsequent login attempts work without requiring email verification

**Test Data:**
- Email: `test-user-003@splitpay.test`
- Verification token: extracted from email link

**Assertions:**
- [ ] HTTP status code is 200
- [ ] User's email_verified flag is true in database
- [ ] User can access protected endpoints after verification
- [ ] Verification link is single-use (second click returns error)

**Automation:** Jest + supertest (API), Playwright (email link extraction)

---

#### TC-AUTH-004: Password Reset via Email

**Test ID:** TC-AUTH-004  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- User `test-user-004@splitpay.test` is registered and email-verified
- Current password: `OldPassword123!`
- Database is in clean state

**Test Steps:**
1. Navigate to login screen
2. Click "Forgot Password?" link
3. Enter email: `test-user-004@splitpay.test`
4. Click "Send Reset Link" button
5. Retrieve password reset link from sent email
6. Click reset link in email
7. Enter new password: `NewPassword456!`
8. Confirm new password: `NewPassword456!`
9. Click "Reset Password" button
10. Login with new password

**Expected Result:**
- HTTP 200 OK response for password reset request
- Password reset email is sent to registered email address
- Password reset link is valid for 1 hour (or configurable)
- After resetting password, user can login with new password: `NewPassword456!`
- Old password `OldPassword123!` no longer works
- Password reset link is single-use (second click returns error)
- User's `updated_at` timestamp is updated

**Test Data:**
- Email: `test-user-004@splitpay.test`
- Old Password: `OldPassword123!`
- New Password: `NewPassword456!`
- Reset Token: extracted from email link

**Assertions:**
- [ ] Password reset email is sent
- [ ] Reset link is valid and single-use
- [ ] New password is hashed and stored
- [ ] Old password no longer works
- [ ] User can login with new password
- [ ] Reset token expires after 1 hour

**Automation:** Jest + supertest (API), Playwright (UI + email extraction)

---

#### TC-AUTH-005: User Profile Update with Phone Number

**Test ID:** TC-AUTH-005  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- User `test-user-005@splitpay.test` is registered and email-verified
- User is logged in (valid access_token)
- Database is in clean state

**Test Steps:**
1. Navigate to profile screen
2. View current profile: name, email, phone number
3. Click "Edit Profile" button
4. Update phone number: `+1-555-0005`
5. Click "Save" button
6. Observe response

**Expected Result:**
- HTTP 200 OK response
- Response body includes updated user object:
  - `phone_number`: `+1-555-0005`
  - `updated_at`: current timestamp
- User's phone number is updated in database
- User will now receive SMS reminders at this phone number
- Profile screen displays updated phone number

**Test Data:**
- User ID: `test-user-005`
- Phone Number: `+1-555-0005`

**Assertions:**
- [ ] HTTP status code is 200
- [ ] Phone number is updated in database
- [ ] Phone number format is validated (E.164 format)
- [ ] User receives SMS reminders at new phone number

**Automation:** Jest + supertest (API), Playwright (UI)

---

### 4.3 Error Handling & Negative Test Cases

#### TC-AUTH-006: Registration with Duplicate Email

**Test ID:** TC-AUTH-006  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- User `test-user-006@splitpay.test` is already registered
- Database is in clean state

**Test Steps:**
1. Navigate to sign-up screen
2. Enter email: `test-user-006@splitpay.test` (duplicate)
3. Enter password: `SecurePassword123!`
4. Enter first name: `Test`
5. Enter last name: `User`
6. Click "Sign Up" button
7. Observe response

**Expected Result:**
- HTTP 409 Conflict response
- Error message: "Email already registered"
- No new user record is created
- Original user record is unchanged
- User is not logged in

**Test Data:**
- Email: `test-user-006@splitpay.test` (duplicate)
- Password: `SecurePassword123!`

**Assertions:**
- [ ] HTTP status code is 409
- [ ] Error message is clear and actionable
- [ ] No new user is created
- [ ] Original user is not affected

**Automation:** Jest + supertest (API)

---

#### TC-AUTH-007: Registration with Weak Password

**Test ID:** TC-AUTH-007  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- Email `test-user-007@splitpay.test` is not registered
- Database is in clean state

**Test Steps:**
1. Navigate to sign-up screen
2. Enter email: `test-user-007@splitpay.test`
3. Enter password: `weak` (too short, no uppercase, no number, no special char)
4. Click "Sign Up" button
5. Observe response

**Expected Result:**
- HTTP 400 Bad Request response
- Error message: "Password must be at least 8 characters and include uppercase letter, number, and special character"
- No user record is created
- Real-time validation shows error in password field

**Test Data:**
- Email: `test-user-007@splitpay.test`
- Password: `weak`

**Assertions:**
- [ ] HTTP status code is 400
- [ ] Error message specifies password requirements
- [ ] No user is created
- [ ] Real-time validation provides feedback

**Automation:** Jest + supertest (API), Playwright (UI validation)

---

#### TC-AUTH-008: Login with Invalid Credentials

**Test ID:** TC-AUTH-008  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- User `test-user-008@splitpay.test` is registered with password `CorrectPassword123!`
- Database is in clean state

**Test Steps:**
1. Navigate to login screen
2. Enter email: `test-user-008@splitpay.test`
3. Enter password: `WrongPassword456!` (incorrect)
4. Click "Login" button
5. Observe response

**Expected Result:**
- HTTP 401 Unauthorized response
- Error message: "Invalid email or password"
- No JWT token is returned
- User is not logged in
- Failed login attempt is logged (for security audit)

**Test Data:**
- Email: `test-user-008@splitpay.test`
- Password: `WrongPassword456!` (incorrect)

**Assertions:**
- [ ] HTTP status code is 401
- [ ] Error message is generic (does not reveal whether email or password is wrong)
- [ ] No JWT token is issued
- [ ] Failed attempt is logged

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-AUTH-009: Login with Non-Existent Email

**Test ID:** TC-AUTH-009  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- Email `nonexistent@splitpay.test` is not registered
- Database is in clean state

**Test Steps:**
1. Navigate to login screen
2. Enter email: `nonexistent@splitpay.test`
3. Enter password: `AnyPassword123!`
4. Click "Login" button
5. Observe response

**Expected Result:**
- HTTP 401 Unauthorized response
- Error message: "Invalid email or password"
- No JWT token is returned
- User is not logged in

**Test Data:**
- Email: `nonexistent@splitpay.test`
- Password: `AnyPassword123!`

**Assertions:**
- [ ] HTTP status code is 401
- [ ] Error message does not reveal whether email exists
- [ ] No JWT token is issued

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-AUTH-010: Invalid Email Format

**Test ID:** TC-AUTH-010  
**Type:** Functional / API  
**Priority:** Medium  
**Preconditions:**
- Database is in clean state

**Test Steps:**
1. Navigate to sign-up screen
2. Enter email: `invalid-email-format` (missing @domain)
3. Enter password: `SecurePassword123!`
4. Click "Sign Up" button
5. Observe response

**Expected Result:**
- HTTP 400 Bad Request response
- Error message: "Invalid email format"
- No user record is created
- Real-time validation shows error in email field

**Test Data:**
- Email: `invalid-email-format`
- Password: `SecurePassword123!`

**Assertions:**
- [ ] HTTP status code is 400
- [ ] Error message is clear
- [ ] Real-time validation catches error before submission

**Automation:** Jest + supertest (API), Playwright (UI validation)

---

#### TC-AUTH-011: Rate Limiting on Registration Attempts

**Test ID:** TC-AUTH-011  
**Type:** Functional / API  
**Priority:** Medium  
**Preconditions:**
- Database is in clean state
- Rate limit is 5 registration attempts per IP per hour

**Test Steps:**
1. Make 5 registration attempts from same IP (all fail or succeed)
2. Make 6th registration attempt from same IP
3. Observe response

**Expected Result:**
- First 5 requests: processed normally (200 or 400 depending on input)
- 6th request: HTTP 429 Too Many Requests
- Error message: "Too many registration attempts. Please try again later."
- User is blocked from further registration attempts for 1 hour
- After 1 hour, rate limit resets

**Test Data:**
- IP address: same for all requests
- Email: different for each request (to avoid duplicate email error)
- Password: valid for each request

**Assertions:**
- [ ] Rate limiting is enforced per IP
- [ ] 6th request is rejected with 429
- [ ] Rate limit resets after 1 hour
- [ ] Rate limit does not block legitimate traffic

**Automation:** Jest + supertest (API) with rate limit testing library

---

#### TC-AUTH-012: Expired Email Verification Link

**Test ID:** TC-AUTH-012  
**Type:** Functional / API  
**Priority:** Medium  
**Preconditions:**
- User `test-user-012@splitpay.test` is registered (email_verified=false)
- Email verification link was generated 25+ hours ago (expires after 24 hours)
- Database is in clean state

**Test Steps:**
1. Click expired email verification link
2. Observe response

**Expected Result:**
- HTTP 400 Bad Request response
- Error message: "Verification link has expired. Please request a new link."
- User's email_verified flag remains false
- User is redirected to request new verification link screen

**Test Data:**
- Email: `test-user-012@splitpay.test`
- Verification token: expired (>24 hours old)

**Assertions:**
- [ ] HTTP status code is 400
- [ ] Error message is clear
- [ ] User is not verified
- [ ] User can request new verification link

**Automation:** Jest + supertest (API)

---

### 4.4 Edge Cases & Boundary Value Tests

#### TC-AUTH-013: Password with Maximum Length

**Test ID:** TC-AUTH-013  
**Type:** Functional / API  
**Priority:** Low  
**Preconditions:**
- Email `test-user-013@splitpay.test` is not registered
- Database is in clean state

**Test Steps:**
1. Navigate to sign-up screen
2. Enter email: `test-user-013@splitpay.test`
3. Enter password: 256 characters (maximum safe length)
4. Click "Sign Up" button
5. Observe response

**Expected Result:**
- HTTP 201 Created response
- User is successfully registered
- Password is hashed and stored correctly
- User can login with this password

**Test Data:**
- Email: `test-user-013@splitpay.test`
- Password: `SecurePassword123!` repeated to 256 characters

**Assertions:**
- [ ] HTTP status code is 201
- [ ] Password is accepted (not truncated)
- [ ] User can login with full password

**Automation:** Jest + supertest (API)

---

#### TC-AUTH-014: Email with Special Characters (RFC 5322)

**Test ID:** TC-AUTH-014  
**Type:** Functional / API  
**Priority:** Low  
**Preconditions:**
- Database is in clean state

**Test Steps:**
1. Navigate to sign-up screen
2. Enter email: `test.user+tag@splitpay.test` (valid RFC 5322 format)
3. Enter password: `SecurePassword123!`
4. Click "Sign Up" button
5. Observe response

**Expected Result:**
- HTTP 201 Created response
- User is successfully registered with email: `test.user+tag@splitpay.test`
- Email verification email is sent to `test.user+tag@splitpay.test`

**Test Data:**
- Email: `test.user+tag@splitpay.test`
- Password: `SecurePassword123!`

**Assertions:**
- [ ] HTTP status code is 201
- [ ] Email with special characters is accepted
- [ ] Email verification email is sent correctly

**Automation:** Jest + supertest (API)

---

#### TC-AUTH-015: JWT Token Expiration and Refresh

**Test ID:** TC-AUTH-015  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- User `test-user-015@splitpay.test` is registered and logged in
- access_token has been issued (expires in 1 hour)
- refresh_token has been issued (expires in 30 days)
- Database is in clean state

**Test Steps:**
1. Wait for access_token to expire (simulate by setting token expiration to current time)
2. Make API request with expired access_token
3. Observe response
4. Use refresh_token to get new access_token
5. Make API request with new access_token
6. Observe response

**Expected Result:**
- Step 2: HTTP 401 Unauthorized response with message "Token expired"
- Step 4: HTTP 200 OK response with new access_token (expires in 1 hour)
- Step 5: HTTP 200 OK response (API call succeeds)
- New access_token is different from old token
- Old access_token is no longer valid

**Test Data:**
- User ID: `test-user-015`
- access_token: expired
- refresh_token: valid

**Assertions:**
- [ ] Expired access_token is rejected with 401
- [ ] refresh_token can be used to get new access_token
- [ ] New access_token is valid for 1 hour
- [ ] Old access_token is invalidated

**Automation:** Jest + supertest (API)

---

### 4.5 Security Test Cases

#### TC-AUTH-016: SQL Injection in Email Field

**Test ID:** TC-AUTH-016  
**Type:** Security / API  
**Priority:** Critical  
**Preconditions:**
- Database is in clean state

**Test Steps:**
1. Navigate to sign-up screen
2. Enter email: `test@splitpay.test'; DROP TABLE users; --`
3. Enter password: `SecurePassword123!`
4. Click "Sign Up" button
5. Observe response

**Expected Result:**
- HTTP 400 Bad Request response
- Error message: "Invalid email format"
- No SQL injection is executed
- Users table is not dropped
- Database remains intact

**Test Data:**
- Email: `test@splitpay.test'; DROP TABLE users; --`
- Password: `SecurePassword123!`

**Assertions:**
- [ ] HTTP status code is 400
- [ ] SQL injection is prevented (parameterized queries)
- [ ] Database is not modified
- [ ] Error message does not expose SQL details

**Automation:** Jest + supertest (API)

---

#### TC-AUTH-017: JWT Token Tampering

**Test ID:** TC-AUTH-017  
**Type:** Security / API  
**Priority:** Critical  
**Preconditions:**
- User `test-user-017@splitpay.test` is registered and logged in
- Valid access_token has been issued
- Database is in clean state

**Test Steps:**
1. Retrieve valid access_token
2. Modify token payload (e.g., change user_id)
3. Make API request with modified token
4. Observe response

**Expected Result:**
- HTTP 401 Unauthorized response
- Error message: "Invalid token"
- API request is rejected
- Modified token is not accepted
- Audit log records attempted token tampering

**Test Data:**
- access_token: valid JWT, modified payload
- Modified claim: user_id changed to different user

**Assertions:**
- [ ] HTTP status code is 401
- [ ] Modified token is rejected
- [ ] Token signature validation fails
- [ ] Tampering attempt is logged

**Automation:** Jest + supertest (API)

---

#### TC-AUTH-018: Privilege Escalation via Token Modification

**Test ID:** TC-AUTH-018  
**Type:** Security / API  
**Priority:** Critical  
**Preconditions:**
- User A `test-user-018a@splitpay.test` is registered and logged in
- User B `test-user-018b@splitpay.test` is registered and logged in
- Database is in clean state

**Test Steps:**
1. Retrieve User A's access_token
2. Modify token to claim User B's user_id
3. Use modified token to access User B's profile (GET /api/v1/users/:id)
4. Observe response

**Expected Result:**
- HTTP 401 Unauthorized response
- Error message: "Invalid token"
- User A cannot access User B's data
- Privilege escalation attempt is logged

**Test Data:**
- User A access_token: modified to User B's user_id
- Endpoint: GET /api/v1/users/user-b-id

**Assertions:**
- [ ] HTTP status code is 401
- [ ] Token signature validation fails
- [ ] Privilege escalation is prevented
- [ ] Attempt is logged

**Automation:** Jest + supertest (API)

---

#### TC-AUTH-019: Password Stored as Plaintext Vulnerability

**Test ID:** TC-AUTH-019  
**Type:** Security / Database  
**Priority:** Critical  
**Preconditions:**
- User `test-user-019@splitpay.test` is registered with password `SecurePassword123!`
- Database is in clean state

**Test Steps:**
1. Query database directly to retrieve user's password_hash
2. Compare password_hash to plaintext password `SecurePassword123!`
3. Verify password_hash is bcrypt hash (starts with $2a$, $2b$, or $2y$)

**Expected Result:**
- password_hash is NOT equal to plaintext password
- password_hash is valid bcrypt hash (format: $2b$12$...)
- password_hash cannot be reversed to plaintext password
- Bcrypt cost factor is 12+ (resistant to brute force)

**Test Data:**
- User: `test-user-019`
- Plaintext password: `SecurePassword123!`
- Database table: users

**Assertions:**
- [ ] Password is hashed (not plaintext)
- [ ] Bcrypt hash format is valid
- [ ] Bcrypt cost factor is ≥12
- [ ] Hash cannot be reversed

**Automation:** Jest + database query

---

#### TC-AUTH-020: Rate Limiting on Login Attempts

**Test ID:** TC-AUTH-020  
**Type:** Security / API  
**Priority:** High  
**Preconditions:**
- User `test-user-020@splitpay.test` is registered
- Database is in clean state
- Rate limit is 5 failed login attempts per IP per 15 minutes

**Test Steps:**
1. Make 5 failed login attempts from same IP (wrong password)
2. Make 6th login attempt from same IP
3. Observe response

**Expected Result:**
- First 5 requests: HTTP 401 Unauthorized
- 6th request: HTTP 429 Too Many Requests
- Error message: "Too many login attempts. Please try again later."
- User is blocked from login for 15 minutes
- After 15 minutes, rate limit resets

**Test Data:**
- Email: `test-user-020@splitpay.test`
- Password: `WrongPassword` (for first 5 attempts)
- IP address: same for all requests

**Assertions:**
- [ ] Rate limiting is enforced per IP
- [ ] 6th request is rejected with 429
- [ ] Rate limit blocks brute force attempts
- [ ] Rate limit resets after 15 minutes

**Automation:** Jest + supertest (API)

---

## 5. EPIC 2: RECEIPT CAPTURE & OCR PROCESSING

### 5.1 Test Scope

**Features Tested:**
- Receipt image upload (camera or photo library)
- OCR extraction of line items from receipt
- OCR result review and manual correction
- Receipt storage and retrieval
- OCR failure handling and fallback
- Receipt image validation (size, format, orientation)

**Personas:** Social Sarah, Trip Coordinator Tina

**Critical Paths:**
1. Upload Receipt → OCR Extract → Review Items → Claim Items
2. Upload Receipt → OCR Fails → Manual Correction → Save
3. Upload Receipt → Image Too Large → Error Message → Retry

---

### 5.2 Happy Path Test Cases

#### TC-RECEIPT-001: Successful Receipt Upload and OCR Extraction

**Test ID:** TC-RECEIPT-001  
**Type:** Functional / Integration  
**Priority:** Critical  
**Preconditions:**
- User `test-user-receipt-001@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image is available (sample receipt with clear line items)
- OCR provider (AWS Textract or Google Vision) is accessible
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image from photo library (or take photo from camera)
5. Confirm image selection
6. Wait for OCR processing
7. Observe OCR results

**Expected Result:**
- HTTP 200 OK response from OCR service
- Receipt record is created in database with status: `processing`
- OCR service successfully extracts line items from receipt image
- Receipt record is updated with status: `extracted`
- OCR results displayed on screen showing:
  - Receipt image (preview)
  - Extracted line items (description, price)
  - Subtotal, tax, tip, total
  - Confidence scores for each item (if available)
- User can proceed to "Claim Items" screen

**Test Data:**
- Receipt image: `tests/fixtures/receipt-001.jpg` (valid receipt with 3 items, clear text)
- Expected line items:
  - Item 1: Salmon, $18.99
  - Item 2: Caesar Salad, $12.99
  - Item 3: Pasta, $15.99
  - Subtotal: $47.97
  - Tax: $4.80 (10%)
  - Tip: $9.60 (20% of subtotal)
  - Total: $62.37

**Assertions:**
- [ ] HTTP status code is 200
- [ ] Receipt record is created with correct status
- [ ] All line items are extracted correctly
- [ ] OCR accuracy is ≥95% (items match expected values)
- [ ] Subtotal, tax, tip are calculated correctly
- [ ] OCR processing time is <5 seconds
- [ ] Receipt image is stored securely (S3)

**Automation:** Jest + supertest (API), Playwright (UI), k6 (performance)

---

#### TC-RECEIPT-002: Receipt Image Upload with Size Validation

**Test ID:** TC-RECEIPT-002  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- User `test-user-receipt-002@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt images of various sizes are available
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image (5 MB - within limit)
5. Confirm image selection
6. Observe response

**Expected Result:**
- HTTP 200 OK response
- Receipt is uploaded successfully
- OCR processing begins
- Receipt image is stored in S3

**Test Data:**
- Receipt image: 5 MB (within 10 MB limit)
- Image format: JPEG

**Assertions:**
- [ ] HTTP status code is 200
- [ ] Receipt is uploaded successfully
- [ ] Image size is validated

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-RECEIPT-003: Receipt Image Upload Exceeds Size Limit

**Test ID:** TC-RECEIPT-003  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- User `test-user-receipt-003@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image exceeds size limit (>10 MB)
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image (15 MB - exceeds limit)
5. Attempt to confirm image selection
6. Observe response

**Expected Result:**
- HTTP 413 Payload Too Large response
- Error message: "Receipt image must be smaller than 10 MB"
- Receipt is not uploaded
- User is prompted to select a smaller image
- No receipt record is created in database

**Test Data:**
- Receipt image: 15 MB (exceeds 10 MB limit)
- Image format: JPEG

**Assertions:**
- [ ] HTTP status code is 413
- [ ] Error message is clear
- [ ] Receipt is not uploaded
- [ ] No database record is created

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-RECEIPT-004: Receipt Image Format Validation

**Test ID:** TC-RECEIPT-004  
**Type:** Functional / API  
**Priority:** High  
**Preconditions:**
- User `test-user-receipt-004@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image in unsupported format is available (e.g., .bmp)
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image in unsupported format (.bmp)
5. Attempt to confirm image selection
6. Observe response

**Expected Result:**
- HTTP 400 Bad Request response
- Error message: "Unsupported image format. Please use JPEG or PNG."
- Receipt is not uploaded
- User is prompted to select supported format
- No receipt record is created in database

**Test Data:**
- Receipt image: `tests/fixtures/receipt-001.bmp` (unsupported format)

**Assertions:**
- [ ] HTTP status code is 400
- [ ] Error message specifies supported formats
- [ ] Receipt is not uploaded
- [ ] No database record is created

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-RECEIPT-005: Manual Correction of OCR Results

**Test ID:** TC-RECEIPT-005  
**Type:** Functional / UI  
**Priority:** High  
**Preconditions:**
- User `test-user-receipt-005@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Receipt has been uploaded and OCR extraction is complete (but one item is incorrect)
- OCR extracted "Salmon" as "Salman" (typo)
- Database is in clean state

**Test Steps:**
1. View OCR results on "Claim Items" screen
2. Tap on incorrect item "Salman" to edit
3. Correct item description to "Salmon"
4. Tap "Save" button
5. Observe response

**Expected Result:**
- Item is updated in UI
- Updated item is saved to database
- Item description is now "Salmon" (corrected)
- User can proceed to claim items
- Corrected data is used for settlement calculation

**Test Data:**
- Original OCR result: "Salman" (incorrect)
- Corrected item: "Salmon" (correct)

**Assertions:**
- [ ] Item description is updated in database
- [ ] Corrected item is displayed in UI
- [ ] Settlement calculation uses corrected data

**Automation:** Playwright (UI)

---

### 5.3 Error Handling & Negative Test Cases

#### TC-RECEIPT-006: OCR Processing Failure

**Test ID:** TC-RECEIPT-006  
**Type:** Functional / Integration  
**Priority:** High  
**Preconditions:**
- User `test-user-receipt-006@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image is blurry or illegible (OCR will fail)
- OCR provider is accessible
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select blurry receipt image
5. Wait for OCR processing
6. Observe response

**Expected Result:**
- HTTP 200 OK response (upload succeeds)
- Receipt record is created with status: `processing`
- OCR processing fails (OCR provider returns error)
- Receipt record is updated with status: `extraction_failed`
- User is prompted: "Could not read receipt. Please try again or enter items manually."
- User can manually enter line items or re-upload receipt

**Test Data:**
- Receipt image: `tests/fixtures/receipt-blurry.jpg` (illegible)

**Assertions:**
- [ ] OCR failure is handled gracefully
- [ ] User is notified of failure
- [ ] User can manually correct or re-upload
- [ ] No crash or error page is displayed

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-RECEIPT-007: OCR Provider Timeout

**Test ID:** TC-RECEIPT-007  
**Type:** Functional / Integration  
**Priority:** High  
**Preconditions:**
- User `test-user-receipt-007@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image is available
- OCR provider is slow (response time >10 seconds)
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image
5. Wait for OCR processing (timeout after 10 seconds)
6. Observe response

**Expected Result:**
- HTTP 504 Gateway Timeout response
- Error message: "Receipt processing took too long. Please try again."
- Receipt record is created but status remains `processing`
- User can retry OCR processing
- After retry, OCR succeeds (or times out again)

**Test Data:**
- Receipt image: `tests/fixtures/receipt-001.jpg`
- OCR timeout: 10 seconds

**Assertions:**
- [ ] Timeout is handled gracefully
- [ ] User is notified of timeout
- [ ] User can retry
- [ ] No crash or error page is displayed

**Automation:** Jest + supertest (API) with timeout simulation

---

#### TC-RECEIPT-008: Receipt Upload Without Authentication

**Test ID:** TC-RECEIPT-008  
**Type:** Security / API  
**Priority:** High  
**Preconditions:**
- Receipt image is available
- No user is logged in (no valid JWT token)
- Database is in clean state

**Test Steps:**
1. Attempt to upload receipt image via API without JWT token
2. Observe response

**Expected Result:**
- HTTP 401 Unauthorized response
- Error message: "Authentication required"
- Receipt is not uploaded
- No receipt record is created in database

**Test Data:**
- Receipt image: `tests/fixtures/receipt-001.jpg`
- JWT token: none

**Assertions:**
- [ ] HTTP status code is 401
- [ ] Unauthenticated request is rejected
- [ ] Receipt is not uploaded

**Automation:** Jest + supertest (API)

---

#### TC-RECEIPT-009: User Uploads Receipt for Group They Don't Belong To

**Test ID:** TC-RECEIPT-009  
**Type:** Security / API  
**Priority:** High  
**Preconditions:**
- User A `test-user-receipt-009a@splitpay.test` is registered and logged in
- User B `test-user-receipt-009b@splitpay.test` is registered
- Group `Test Group A` is created by User B (User A is not member)
- Receipt image is available
- Database is in clean state

**Test Steps:**
1. User A attempts to upload receipt for Group `Test Group A` (which User A doesn't belong to)
2. Observe response

**Expected Result:**
- HTTP 403 Forbidden response
- Error message: "You do not have permission to add expenses to this group"
- Receipt is not uploaded
- No receipt record is created in database
- Unauthorized access attempt is logged

**Test Data:**
- User A: `test-user-receipt-009a@splitpay.test`
- Group: `Test Group A` (created by User B)
- Receipt image: `tests/fixtures/receipt-001.jpg`

**Assertions:**
- [ ] HTTP status code is 403
- [ ] Unauthorized access is prevented
- [ ] Receipt is not uploaded
- [ ] Attempt is logged

**Automation:** Jest + supertest (API)

---

### 5.4 Edge Cases & Boundary Value Tests

#### TC-RECEIPT-010: Receipt with Single Line Item

**Test ID:** TC-RECEIPT-010  
**Type:** Functional / Integration  
**Priority:** Medium  
**Preconditions:**
- User `test-user-receipt-010@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image with single line item is available
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image with single item
5. Wait for OCR processing
6. Observe results

**Expected Result:**
- OCR successfully extracts single line item
- Receipt record is created with 1 line item
- User can claim the item
- Settlement calculation works correctly with 1 item

**Test Data:**
- Receipt image: `tests/fixtures/receipt-single-item.jpg`
- Line item: Coffee, $5.00
- Subtotal: $5.00
- Tax: $0.50
- Tip: $1.00
- Total: $6.50

**Assertions:**
- [ ] Single item is extracted correctly
- [ ] Settlement calculation is accurate
- [ ] No crashes or errors

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-RECEIPT-011: Receipt with Many Line Items (30+)

**Test ID:** TC-RECEIPT-011  
**Type:** Functional / Integration  
**Priority:** Medium  
**Preconditions:**
- User `test-user-receipt-011@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image with 30+ line items is available
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image with 30+ items
5. Wait for OCR processing
6. Observe results

**Expected Result:**
- OCR successfully extracts all 30+ line items
- Receipt record is created with 30+ line items
- UI displays all items (with scrolling if needed)
- User can claim items
- Settlement calculation works correctly with many items
- Performance is acceptable (OCR <5 seconds, UI renders <1 second)

**Test Data:**
- Receipt image: `tests/fixtures/receipt-many-items.jpg`
- Line items: 30 items (various prices)
- Subtotal: $500.00
- Tax: $50.00
- Tip: $100.00
- Total: $650.00

**Assertions:**
- [ ] All 30+ items are extracted
- [ ] UI renders all items without lag
- [ ] Settlement calculation is accurate
- [ ] Performance is acceptable

**Automation:** Jest + supertest (API), Playwright (UI), k6 (performance)

---

#### TC-RECEIPT-012: Receipt with Zero Tax

**Test ID:** TC-RECEIPT-012  
**Type:** Functional / Integration  
**Priority:** Low  
**Preconditions:**
- User `test-user-receipt-012@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image with no tax (tax-exempt location or digital service) is available
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image with zero tax
5. Wait for OCR processing
6. Observe results

**Expected Result:**
- OCR successfully extracts line items and zero tax
- Receipt record is created with tax: $0.00
- Settlement calculation correctly allocates zero tax
- User can proceed to claim items

**Test Data:**
- Receipt image: `tests/fixtures/receipt-no-tax.jpg`
- Line items: 2 items ($20.00, $15.00)
- Subtotal: $35.00
- Tax: $0.00
- Tip: $7.00
- Total: $42.00

**Assertions:**
- [ ] Zero tax is handled correctly
- [ ] Settlement calculation works with zero tax
- [ ] No crashes or errors

**Automation:** Jest + supertest (API), Playwright (UI)

---

#### TC-RECEIPT-013: Receipt with Very Small Prices

**Test ID:** TC-RECEIPT-013  
**Type:** Functional / Integration  
**Priority:** Low  
**Preconditions:**
- User `test-user-receipt-013@splitpay.test` is registered and logged in
- User is member of group `Test Group`
- Test receipt image with very small prices is available (e.g., coffee for $2.99)
- Database is in clean state

**Test Steps:**
1. Navigate to "New Expense" screen
2. Select group: `Test Group`
3. Tap "Upload Receipt" button
4. Select receipt image with small prices
5. Wait for OCR processing
6. Observe results

**Expected Result:**
- OCR successfully extracts small prices
- Receipt record is created with small prices
- Settlement calculation correctly handles small amounts
- Rounding is correct (no floating point errors)

**Test Data:**
- Receipt image: `tests/fixtures/receipt-small-prices.jpg`
- Line items: Coffee $2.99, Tea $2.99
- Subtotal: $5.98
- Tax: $0.60
- Tip: $1.20
- Total: $7.78

**Assertions:**
- [ ] Small prices are extracted correctly
- [ ] Rounding is accurate
- [ ] No floating point errors
- [ ] Settlement calculation is correct

**Automation:** Jest + supertest (API), Playwright (UI)

---

### 5.5 Performance Test Cases

#### TC-RECEIPT-PERF-001: Receipt Upload Latency at Baseline Load

**Test ID:** TC-RECEIPT-PERF-001  
**Type:** Performance / Load  
**Priority:** High  
**Preconditions:**
- Staging environment is running
- Database is in clean state
- 10 test users are created
- Test receipt image is available

**Test Steps:**
1. Simulate 10 concurrent users uploading receipts
2. Measure OCR processing time for each receipt
3. Measure P50, P95, P99 latency
4. Observe response

**Expected Result:**
- P50 latency: <2 seconds
- P95 latency: <4 seconds
- P99 latency: <5 seconds
- Error rate: 0%
- All receipts are successfully processed

**Test Data:**
- Concurrent users: 10
- Receipt image: `tests/fixtures/receipt-001.jpg`
- Duration: 5 minutes

**Assertions:**
- [ ] P95 latency is <4 seconds
- [ ] P99 latency is <5 seconds
- [ ] Error rate is 0%

**Automation:** k6 load testing

---

#### TC-RECEIPT-PERF-002: Receipt Upload Latency at Peak Load

**Test ID:** TC-RECEIPT-PERF-002  
**Type:** Performance / Load  
**Priority:** High  
**Preconditions:**
- Staging environment is running
- Database is in clean state
- 100 test users are created
- Test receipt image is available

**Test Steps:**
1. Simulate 100 concurrent users