# EPICS_AND_STORIES.md

**SplitPay: Comprehensive Epics & User Stories**

**Version:** 1.0  
**Date:** [Current Date]  
**Author:** Product Management & Engineering  
**Status:** Ready for Sprint Planning & QA Review  

**Document Purpose:** This document decomposes the SplitPay PRD, TRD, and Solution Design into structured Epics and User Stories with comprehensive acceptance criteria, story points, dependencies, testability notes, and priority levels. Each story is independently deliverable, testable, and traceable to business requirements. This is the authoritative source for sprint planning, backlog management, engineering execution, and QA test planning.

---

## TABLE OF CONTENTS

1. [Overview & Backlog Structure](#overview--backlog-structure)
2. [Epic 1: User Authentication & Account Management](#epic-1-user-authentication--account-management)
3. [Epic 2: Receipt Capture & OCR Processing](#epic-2-receipt-capture--ocr-processing)
4. [Epic 3: Item Claiming & Expense Categorization](#epic-3-item-claiming--expense-categorization)
5. [Epic 4: Expense Calculation & Settlement Logic](#epic-4-expense-calculation--settlement-logic)
6. [Epic 5: Payment Coordination & Reminders](#epic-5-payment-coordination--reminders)
7. [Epic 6: Recurring Expenses (Roommate Mode)](#epic-6-recurring-expenses-roommate-mode)
8. [Epic 7: Group Management & Invitations](#epic-7-group-management--invitations)
9. [Epic 8: Data Persistence & Audit Trail](#epic-8-data-persistence--audit-trail)
10. [Epic 9: Monitoring, Observability & Operations](#epic-9-monitoring-observability--operations)
11. [Epic 10: Security & Compliance](#epic-10-security--compliance)
12. [Cross-Epic Dependencies & Sequencing](#cross-epic-dependencies--sequencing)
13. [Backlog Priority & Release Planning](#backlog-priority--release-planning)
14. [Appendix: Story Point Estimation Scale](#appendix-story-point-estimation-scale)
15. [Appendix: QA Test Planning & Testability Notes](#appendix-qa-test-planning--testability-notes)

---

## OVERVIEW & BACKLOG STRUCTURE

### Product Backlog Organization

The SplitPay backlog is organized into 10 major epics that align with the PRD's core features and the TRD's service boundaries:

| **Epic** | **Description** | **Primary Personas** | **Estimated Effort** | **MVP** |
|---|---|---|---|---|
| **Epic 1** | User Authentication & Account Management | All | 13 SP | ✓ Yes |
| **Epic 2** | Receipt Capture & OCR Processing | Social Sarah, Trip Coordinator Tina | 21 SP | ✓ Yes |
| **Epic 3** | Item Claiming & Expense Categorization | Social Sarah, Trip Coordinator Tina | 13 SP | ✓ Yes |
| **Epic 4** | Expense Calculation & Settlement Logic | All | 34 SP | ✓ Yes |
| **Epic 5** | Payment Coordination & Reminders | All | 13 SP | ✓ Yes |
| **Epic 6** | Recurring Expenses (Roommate Mode) | Roommate Ryan | 21 SP | ✗ Post-MVP |
| **Epic 7** | Group Management & Invitations | All | 13 SP | ✓ Yes |
| **Epic 8** | Data Persistence & Audit Trail | All (compliance) | 21 SP | ✓ Yes |
| **Epic 9** | Monitoring, Observability & Operations | DevOps / SRE | 34 SP | ✓ Yes |
| **Epic 10** | Security & Compliance | All (security) | 21 SP | ✓ Yes |
| | **TOTAL (MVP)** | | **152 SP** | |
| | **TOTAL (Post-MVP)** | | **21 SP** | |
| | **GRAND TOTAL** | | **173 SP** | |

### Backlog Sequencing Strategy

**Phase 1 (MVP - Sprint 1-4):** Epics 1, 2, 3, 4, 5, 7, 8, 9, 10 (152 SP)
- Users can sign up, photograph receipts, claim items, calculate splits, and receive reminders
- Platform is monitored, secure, and auditable
- Target: Ship to closed beta (50-100 users) by end of Phase 1

**Phase 2 (Post-MVP - Sprint 5-6):** Epic 6 + refinements (21 SP)
- Roommate mode with recurring expenses
- Target: Ship to general availability

### Story Point Scale

| **Points** | **Effort** | **Complexity** | **Risk** | **Examples** |
|---|---|---|---|---|
| **1** | <2 hours | Trivial | None | Update label, fix typo, add constant |
| **2** | 2-4 hours | Simple | Low | Simple API endpoint, basic validation |
| **3** | 4-8 hours | Moderate | Low | Form submission, data retrieval |
| **5** | 8-16 hours | Complex | Medium | Multi-step workflow, integration |
| **8** | 16-32 hours | Very Complex | Medium-High | Service integration, algorithm implementation |
| **13** | 32-64 hours | Highly Complex | High | Multi-service orchestration, migration |
| **21** | 64-128 hours | Extremely Complex | Very High | Major feature area, significant refactoring |
| **34** | 128+ hours | Architectural | Critical | Core platform capability, major redesign |

---

## EPIC 1: USER AUTHENTICATION & ACCOUNT MANAGEMENT

**Epic Goal:** Enable users to create accounts, authenticate securely, and manage their profiles. Establish the identity foundation for all downstream features.

**Business Value:** Users cannot use SplitPay without accounts. Authentication is the gating mechanism for all other features.

**Primary Personas:** All (Social Sarah, Roommate Ryan, Trip Coordinator Tina)

**Success Metrics:**
- User signup completion rate ≥80%
- Login success rate ≥99.9%
- JWT token validation latency <50ms (p99)
- Zero unauthorized access incidents

**Acceptance Criteria (Epic-Level):**
- Users can sign up with email and password
- Users can log in with email and password
- Users can reset forgotten passwords via email
- Users can view and edit their profile (name, phone number for SMS)
- Sessions are secure and expire appropriately
- All authentication flows are HTTPS-only
- Passwords are hashed with bcrypt (minimum 12 rounds)
- JWT tokens are signed and validated on every API request

---

### STORY 1.1: User Registration with Email & Password

**Story ID:** SPLIT-1.1  
**Epic:** Epic 1  
**Story Type:** Feature  
**Story Points:** 5  
**Priority:** P0 (Critical)  
**Sprint:** Sprint 1  
**Assigned To:** Backend (Auth Service)  
**Dependencies:** None  

**User Story:**
> As a new user (Social Sarah, Roommate Ryan, Trip Coordinator Tina)  
> I want to create an account with my email and password  
> So that I can access SplitPay and start splitting bills with friends

**Description:**
Users arrive at SplitPay and need a frictionless way to sign up. The registration flow should be mobile-friendly (React Native Web), validate inputs in real-time, and provide clear error messages. After successful registration, users should be automatically logged in and redirected to the app home screen.

**Acceptance Criteria:**

1. **Registration Form UI (Frontend)**
   - [ ] React Native Web form displays with email and password fields
   - [ ] Form includes "Sign Up" button and "Already have an account? Log In" link
   - [ ] Email field validates format in real-time (RFC 5322 compliant)
   - [ ] Password field requires minimum 8 characters, 1 uppercase, 1 number, 1 special character
   - [ ] Password confirmation field matches password field
   - [ ] Real-time validation error messages appear below fields (not blocking)
   - [ ] Form is accessible (WCAG 2.1 AA): labels, keyboard navigation, screen reader support
   - [ ] Form works on mobile (iOS Safari, Chrome Android) and desktop (Chrome, Safari)

2. **Backend Registration Endpoint (`POST /api/v1/auth/register`)**
   - [ ] Endpoint accepts JSON: `{ email, password, firstName, lastName }`
   - [ ] Email is validated and normalized (lowercase, trimmed, RFC 5322)
   - [ ] Password validation: minimum 8 chars, 1 uppercase, 1 number, 1 special char
   - [ ] Email uniqueness is checked (case-insensitive) — return 409 Conflict if duplicate
   - [ ] Password is hashed with bcrypt (minimum 12 rounds) before storage
   - [ ] User record is created in PostgreSQL with:
     - `user_id` (UUID)
     - `email` (unique, indexed)
     - `password_hash` (bcrypt)
     - `first_name`
     - `last_name`
     - `phone_number` (nullable, for SMS)
     - `created_at` (timestamp)
     - `updated_at` (timestamp)
     - `is_active` (boolean, default true)
   - [ ] Email verification flow is triggered (see STORY 1.2 for email verification)
   - [ ] Response returns 201 Created with JWT token (access_token, refresh_token) and user object
   - [ ] Response includes token expiration times (access_token: 1 hour, refresh_token: 30 days)

3. **Error Handling**
   - [ ] Invalid email format → 400 Bad Request with message "Invalid email format"
   - [ ] Password too weak → 400 Bad Request with message "Password must contain uppercase, number, special character"
   - [ ] Email already registered → 409 Conflict with message "Email already registered"
   - [ ] Missing required fields → 400 Bad Request with message listing missing fields
   - [ ] Database error (network, constraint) → 500 Internal Server Error with generic message (no DB details leaked)
   - [ ] Rate limiting: max 5 registration attempts per IP per hour → 429 Too Many Requests

4. **Security**
   - [ ] Request must be HTTPS (enforced at load balancer)
   - [ ] Password is never logged or stored in plaintext
   - [ ] Bcrypt cost factor is 12+ (mitigates brute force)
   - [ ] Password reset tokens are generated and stored (see STORY 1.3)
   - [ ] Endpoint is not vulnerable to SQL injection (parameterized queries)
   - [ ] Endpoint is not vulnerable to timing attacks (constant-time comparison for email uniqueness check)

5. **Audit & Logging**
   - [ ] Successful registration is logged: `{ timestamp, user_id, email, action: "user_registered", ip_address }`
   - [ ] Failed registration attempts are logged: `{ timestamp, email, action: "registration_failed", reason, ip_address }`
   - [ ] Logs do not contain passwords or sensitive data
   - [ ] Logs are stored in centralized logging system (see Epic 9)

6. **Notifications**
   - [ ] Email verification link is sent (see STORY 1.2)
   - [ ] No SMS is sent at registration time

**Technical Considerations:**
- [ASSUMPTION] Email verification is required before user can access core features (see STORY 1.2)
- [ASSUMPTION] JWT tokens are used for session management (not server-side sessions)
- [ASSUMPTION] Bcrypt library: `bcryptjs` (Node.js) or `bcrypt` (native)
- [ASSUMPTION] Email service: Transactional email provider (SendGrid, AWS SES, etc.)
- Database schema migration required (see Epic 8)

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test password validation regex (valid: "Test1234!", "Pass@word1"; invalid: "password", "Pass", "Pass@123word" [too long])
- Test email normalization (lowercase, trim whitespace)
- Test bcrypt hashing is deterministic (same password, different hash; different password, different hash)
- Test JWT token generation includes all required claims

*Integration Tests:*
- Test registration endpoint with valid inputs → 201 Created, JWT tokens returned
- Test registration with duplicate email → 409 Conflict
- Test registration with weak password → 400 Bad Request
- Test registration with invalid email format → 400 Bad Request
- Test registration with missing fields → 400 Bad Request
- Test rate limiting: 6 requests from same IP in 1 hour → 5th succeeds, 6th returns 429

*API Contract Tests (Pact):*
- Frontend expects response: `{ access_token, refresh_token, user: { user_id, email, first_name, last_name } }`
- Frontend expects 201 status code on success, 400/409 on error

*End-to-End Tests (Playwright):*
- User fills registration form with valid email and password → form submits → redirected to home screen → user is logged in
- User fills registration form with duplicate email → error message displayed → form remains visible for retry
- User fills registration form with weak password → error message displayed → form remains visible for retry

*Security Tests:*
- Attempt SQL injection in email field: `test@example.com' OR '1'='1` → should be treated as literal string, not SQL
- Attempt to register with password containing HTML: `<script>alert('xss')</script>` → password is stored as-is, not executed
- Verify password is not returned in response (only access_token and user object)

*Performance Tests:*
- Registration endpoint latency p95 <200ms under 100 concurrent requests
- Database write latency p95 <100ms

*Testability Gaps & Questions:*
- **Q1:** Should registration require email verification before account is "active"? (Affects STORY 1.2 dependency)
- **Q2:** Should we support social login (Google, Apple) in MVP or post-MVP?
- **Q3:** What is the password reset flow? (Addressed in STORY 1.3)
- **Q4:** Should we collect phone number at registration or later? (Affects SMS reminders in Epic 5)

---

### STORY 1.2: Email Verification & Confirmation

**Story ID:** SPLIT-1.2  
**Epic:** Epic 1  
**Story Type:** Feature  
**Story Points:** 3  
**Priority:** P0 (Critical)  
**Sprint:** Sprint 1  
**Assigned To:** Backend (Auth Service) + Frontend  
**Dependencies:** STORY 1.1 (User Registration)  

**User Story:**
> As a newly registered user  
> I want to verify my email address  
> So that SplitPay can confirm I own the email and use it for password resets and payment reminders

**Description:**
After registration (STORY 1.1), users receive a verification email with a unique link. Clicking the link confirms ownership of the email and activates the account. Unverified accounts can log in but cannot access core features (receipt upload, expense calculation).

**Acceptance Criteria:**

1. **Email Verification Flow**
   - [ ] After successful registration (STORY 1.1), email verification link is sent within 30 seconds
   - [ ] Verification email includes:
     - Personalized greeting: "Hi [First Name]"
     - Clear call-to-action: "Verify your email"
     - Verification link: `https://app.splitpay.com/verify?token=[unique_token]`
     - Expiration notice: "This link expires in 24 hours"
     - Fallback: 6-digit code that can be entered manually
   - [ ] Verification token is:
     - Cryptographically random (256-bit entropy)
     - Stored in database with user_id, expiration_time (24 hours), and is_used flag
     - Single-use (cannot be reused after verification)
   - [ ] Verification token is NOT sent in URL as plaintext; instead, token is hashed and only the hash is stored

2. **Email Verification Endpoint (`POST /api/v1/auth/verify-email`)**
   - [ ] Endpoint accepts JSON: `{ token }` or `{ email, code }` (code is 6-digit fallback)
   - [ ] Token is validated:
     - Token exists in database
     - Token has not expired (24-hour window)
     - Token has not been used (is_used flag is false)
     - Token matches user_id from request context (if user is authenticated) or email (if not)
   - [ ] On success:
     - Token is marked as used (is_used = true)
     - User record is updated: `email_verified = true`, `email_verified_at = now()`
     - Response returns 200 OK with message "Email verified successfully"
   - [ ] On failure:
     - Token expired → 400 Bad Request with message "Verification link expired. Request a new one."
     - Token invalid/not found → 400 Bad Request with message "Invalid verification link"
     - Token already used → 400 Bad Request with message "Verification link already used"

3. **Resend Verification Email (`POST /api/v1/auth/resend-verification`)**
   - [ ] Endpoint accepts JSON: `{ email }`
   - [ ] User is looked up by email
   - [ ] If user is already verified, return 200 OK (do not leak whether email exists)
   - [ ] If user is not verified:
     - New verification token is generated
     - Previous tokens are marked as expired (is_used = true)
     - New verification email is sent
     - Return 200 OK with message "Verification email sent"
   - [ ] Rate limiting: max 3 resend requests per email per hour → 429 Too Many Requests

4. **Frontend Verification Flow**
   - [ ] React Native Web page displays at `/verify` route
   - [ ] Page accepts `token` query parameter from email link
   - [ ] Page displays loading state while verifying
   - [ ] On success: redirect to home screen with success message "Email verified!"
   - [ ] On failure: display error message and "Resend verification email" link
   - [ ] Fallback: manual code entry field (6 digits) with submit button

5. **Account Access Control**
   - [ ] Unverified users (email_verified = false) can:
     - [ ] View profile
     - [ ] Update password
     - [ ] Access settings
   - [ ] Unverified users cannot:
     - [ ] Upload receipts
     - [ ] Join groups
     - [ ] Claim items
     - [ ] View expenses
   - [ ] Attempting to access restricted feature displays message: "Please verify your email first. Check your inbox for a verification link."
   - [ ] Verified users (email_verified = true) can access all features

6. **Audit & Logging**
   - [ ] Successful email verification is logged: `{ timestamp, user_id, email, action: "email_verified" }`
   - [ ] Failed verification attempts are logged: `{ timestamp, email, action: "verification_failed", reason }`

**Technical Considerations:**
- [ASSUMPTION] Verification tokens are hashed before storage (not stored in plaintext)
- [ASSUMPTION] Token generation uses `crypto.randomBytes(32)` (Node.js)
- [ASSUMPTION] Token hashing uses SHA-256
- [ASSUMPTION] Email service is configured to send transactional emails (SendGrid, AWS SES, etc.)
- [ASSUMPTION] Email verification is required before core features are accessible (affects feature gating)

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test token generation is cryptographically random (different tokens on each call)
- Test token hashing is deterministic (same token → same hash)
- Test token expiration logic (24-hour window)
- Test 6-digit code generation and validation

*Integration Tests:*
- Test email verification endpoint with valid token → 200 OK, user.email_verified = true
- Test email verification with expired token → 400 Bad Request
- Test email verification with already-used token → 400 Bad Request
- Test resend verification email → new token generated, email sent, 200 OK
- Test rate limiting on resend: 4 requests in 1 hour → 4th request returns 429
- Test unverified user attempting to upload receipt → 403 Forbidden with message about email verification

*API Contract Tests:*
- Frontend expects response: `{ message: "Email verified successfully" }` on 200 OK
- Frontend expects error response with descriptive message on 400

*End-to-End Tests:*
- User registers with email → receives verification email → clicks verification link → redirected to home screen → can now upload receipt
- User registers with email → does not verify → attempts to upload receipt → error message "Please verify your email first"
- User registers with email → loses verification email → clicks "Resend verification email" → receives new email → verifies successfully

*Security Tests:*
- Attempt to reuse verification token twice → second attempt fails with "already used" error
- Attempt to use expired token → fails with "expired" error
- Attempt to use token for wrong user → fails (token is user-specific)
- Verify token is not leaked in logs, error messages, or response bodies

*Performance Tests:*
- Email verification endpoint latency p95 <100ms
- Email delivery latency p95 <5 seconds (from trigger to user inbox)

*Testability Gaps & Questions:*
- **Q1:** Should unverified users be able to log in immediately after registration? (Affects feature gating)
- **Q2:** Should we send SMS verification code as alternative to email? (Post-MVP)
- **Q3:** What is the user experience if verification email is lost? (Resend flow is covered, but UX clarity needed)

---

### STORY 1.3: Password Reset & Recovery

**Story ID:** SPLIT-1.3  
**Epic:** Epic 1  
**Story Type:** Feature  
**Story Points:** 5  
**Priority:** P0 (Critical)  
**Sprint:** Sprint 1  
**Assigned To:** Backend (Auth Service) + Frontend  
**Dependencies:** STORY 1.1 (User Registration), STORY 1.2 (Email Verification)  

**User Story:**
> As a user who has forgotten my password  
> I want to reset it via email  
> So that I can regain access to my account without contacting support

**Description:**
Users who forget their password can request a password reset. An email with a reset link is sent. Clicking the link allows them to set a new password. Reset tokens expire after 1 hour and are single-use.

**Acceptance Criteria:**

1. **Forgot Password Request (`POST /api/v1/auth/forgot-password`)**
   - [ ] Endpoint accepts JSON: `{ email }`
   - [ ] Email is looked up in database (case-insensitive)
   - [ ] If email exists:
     - Password reset token is generated (256-bit entropy, hashed before storage)
     - Token is stored with user_id, expiration_time (1 hour), is_used flag
     - Password reset email is sent
     - Return 200 OK with message "If an account exists with this email, a password reset link has been sent" (do not leak whether email exists)
   - [ ] If email does not exist:
     - Return 200 OK with same message (do not leak whether email exists)
   - [ ] Rate limiting: max 5 password reset requests per email per hour → 429 Too Many Requests

2. **Password Reset Email**
   - [ ] Email includes:
     - Personalized greeting: "Hi [First Name]"
     - Clear call-to-action: "Reset your password"
     - Reset link: `https://app.splitpay.com/reset-password?token=[unique_token]`
     - Expiration notice: "This link expires in 1 hour"
     - Security notice: "If you didn't request this, ignore this email"
     - Fallback: manual token entry field on reset page
   - [ ] Email is sent within 30 seconds of request

3. **Password Reset Endpoint (`POST /api/v1/auth/reset-password`)**
   - [ ] Endpoint accepts JSON: `{ token, newPassword, newPasswordConfirm }`
   - [ ] Token is validated:
     - Token exists in database
     - Token has not expired (1-hour window)
     - Token has not been used (is_used flag is false)
   - [ ] New password is validated:
     - Minimum 8 characters
     - 1 uppercase letter
     - 1 number
     - 1 special character
     - Password is not same as previous password (check against password_hash history)
   - [ ] On success:
     - Token is marked as used (is_used = true)
     - User password_hash is updated with new password (bcrypt, 12+ rounds)
     - All existing JWT tokens for user are invalidated (token blacklist or rotation)
     - Response returns 200 OK with message "Password reset successfully. You can now log in with your new password."
   - [ ] On failure:
     - Token expired → 400 Bad Request with message "Password reset link expired. Request a new one."
     - Token invalid → 400 Bad Request with message "Invalid password reset link"
     - Token already used → 400 Bad Request with message "Password reset link already used"
     - Password invalid → 400 Bad Request with message "Password must be 8+ characters with uppercase, number, special character"

4. **Frontend Password Reset Flow**
   - [ ] React Native Web page displays at `/reset-password` route
   - [ ] Page accepts `token` query parameter from email link
   - [ ] Page displays:
     - New password field (masked)
     - Confirm password field (masked)
     - "Reset Password" button
     - "Back to Login" link
   - [ ] Real-time password validation (same rules as registration)
   - [ ] On success: redirect to login page with message "Password reset successfully. Please log in with your new password."
   - [ ] On failure: display error message and "Request new reset link" button

5. **Forgot Password Page (`/forgot-password`)**
   - [ ] React Native Web page displays email input field
   - [ ] Page includes explanation: "Enter the email address associated with your account"
   - [ ] On submit: display message "If an account exists with this email, a password reset link has been sent"
   - [ ] Page includes "Back to Login" link

6. **Audit & Logging**
   - [ ] Password reset request is logged: `{ timestamp, email, action: "password_reset_requested", ip_address }`
   - [ ] Successful password reset is logged: `{ timestamp, user_id, email, action: "password_reset_successful" }`
   - [ ] Failed password reset attempts are logged: `{ timestamp, email, action: "password_reset_failed", reason, ip_address }`

**Technical Considerations:**
- [ASSUMPTION] Password reset tokens expire after 1 hour (shorter than email verification tokens)
- [ASSUMPTION] All existing JWT tokens are invalidated after password reset (forces re-login on all devices)
- [ASSUMPTION] Password history is maintained to prevent reuse of previous passwords
- [ASSUMPTION] Email service is configured for transactional emails

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test password reset token generation is cryptographically random
- Test token expiration logic (1-hour window)
- Test password validation (valid: "Test1234!", "Pass@word1"; invalid: "password", "Pass", "Pass@123word" [too long])
- Test password history check (prevent reuse)

*Integration Tests:*
- Test forgot password request with valid email → 200 OK, email sent
- Test forgot password request with nonexistent email → 200 OK (do not leak email existence)
- Test forgot password request rate limiting: 6 requests in 1 hour → 6th returns 429
- Test password reset with valid token → 200 OK, password updated, user can log in with new password
- Test password reset with expired token → 400 Bad Request
- Test password reset with already-used token → 400 Bad Request
- Test password reset with weak new password → 400 Bad Request
- Test password reset invalidates all existing JWT tokens (user must re-login on all devices)

*API Contract Tests:*
- Frontend expects response: `{ message: "Password reset successfully..." }` on 200 OK
- Frontend expects error response with descriptive message on 400

*End-to-End Tests:*
- User logs in → clicks "Forgot Password" → enters email → receives reset email → clicks reset link → enters new password → redirected to login page → logs in with new password successfully
- User requests password reset twice in 1 hour → second request succeeds (rate limit is per-email)
- User requests password reset → loses email → clicks "Resend password reset link" → receives new email → resets password successfully

*Security Tests:*
- Attempt to use password reset token for wrong user → fails
- Attempt to reuse password reset token twice → second attempt fails
- Attempt to use expired token → fails with "expired" error
- Verify password is never logged or exposed in error messages
- Verify token is not leaked in logs
- Verify password reset invalidates all existing sessions (user must re-login everywhere)

*Performance Tests:*
- Password reset endpoint latency p95 <200ms
- Email delivery latency p95 <5 seconds

*Testability Gaps & Questions:*
- **Q1:** Should we implement password reset via SMS as alternative to email? (Post-MVP)
- **Q2:** Should we implement "remember me" functionality to reduce password reset frequency? (Post-MVP)
- **Q3:** Should we implement multi-factor authentication (MFA) for password reset? (Post-MVP, security consideration)

---

### STORY 1.4: User Login with Email & Password

**Story ID:** SPLIT-1.4  
**Epic:** Epic 1  
**Story Type:** Feature  
**Story Points:** 5  
**Priority:** P0 (Critical)  
**Sprint:** Sprint 1  
**Assigned To:** Backend (Auth Service) + Frontend  
**Dependencies:** STORY 1.1 (User Registration)  

**User Story:**
> As a registered user  
> I want to log in with my email and password  
> So that I can access my account and start splitting bills

**Description:**
Users can authenticate with email and password. On successful login, they receive JWT tokens (access_token and refresh_token) and are redirected to the app home screen. Failed login attempts are rate-limited and logged.

**Acceptance Criteria:**

1. **Login Form UI (Frontend)**
   - [ ] React Native Web form displays with email and password fields
   - [ ] Form includes "Log In" button and "Don't have an account? Sign Up" link
   - [ ] Form includes "Forgot Password?" link
   - [ ] Email field validates format in real-time
   - [ ] Real-time validation error messages appear below fields (not blocking)
   - [ ] Form is accessible (WCAG 2.1 AA): labels, keyboard navigation, screen reader support
   - [ ] Form works on mobile (iOS Safari, Chrome Android) and desktop (Chrome, Safari)
   - [ ] On submit, form displays loading state (button disabled, spinner)
   - [ ] On success, user is redirected to home screen
   - [ ] On failure, error message is displayed (e.g., "Invalid email or password")

2. **Backend Login Endpoint (`POST /api/v1/auth/login`)**
   - [ ] Endpoint accepts JSON: `{ email, password }`
   - [ ] Email is normalized (lowercase, trimmed)
   - [ ] User is looked up by email
   - [ ] If user not found → 401 Unauthorized with message "Invalid email or password" (do not leak whether email exists)
   - [ ] If user found:
     - Password is compared against password_hash using bcrypt (constant-time comparison)
     - If password matches:
       - Check if user's email is verified (email_verified = true)
       - If not verified → 403 Forbidden with message "Please verify your email first. Check your inbox for a verification link."
       - If verified:
         - Access token is generated (JWT, signed with RS256, expiration 1 hour)
         - Refresh token is generated (JWT, signed with RS256, expiration 30 days)
         - User login event is recorded: `{ user_id, login_at, ip_address, user_agent }`
         - Response returns 200 OK with tokens and user object
     - If password does not match → 401 Unauthorized with message "Invalid email or password"

3. **JWT Token Structure**
   - [ ] Access token claims:
     - `sub` (subject): user_id
     - `email`: user email
     - `iat` (issued at): timestamp
     - `exp` (expiration): 1 hour from iat
     - `type`: "access"
   - [ ] Refresh token claims:
     - `sub` (subject): user_id
     - `iat` (issued at): timestamp
     - `exp` (expiration): 30 days from iat
     - `type`: "refresh"
   - [ ] Both tokens are signed with RS256 (asymmetric signing)
   - [ ] Public key is available for token verification

4. **Rate Limiting & Brute Force Protection**
   - [ ] Max 5 failed login attempts per email per 15 minutes → 429 Too Many Requests
   - [ ] Max 5 failed login attempts per IP per 15 minutes → 429 Too Many Requests
   - [ ] After 5 failed attempts, account is temporarily locked for 15 minutes
   - [ ] User receives email notification: "Multiple failed login attempts detected. If this wasn't you, reset your password."
   - [ ] Successful login resets failed attempt counter

5. **Session Management**
   - [ ] Access token is stored client-side (React Native Web local storage or secure storage)
   - [ ] Refresh token is stored client-side (React Native Web secure storage, HttpOnly cookie on web)
   - [ ] Access token is sent in Authorization header on every API request: `Authorization: Bearer [access_token]`
   - [ ] If access token expires, refresh token is used to obtain new access token (see STORY 1.5)
   - [ ] User can log out by clearing tokens client-side (see STORY 1.6)

6. **Error Handling**
   - [ ] Invalid email format → 400 Bad Request
   - [ ] Missing email or password → 400 Bad Request
   - [ ] User not found → 401 Unauthorized with message "Invalid email or password"
   - [ ] Password incorrect → 401 Unauthorized with message "Invalid email or password"
   - [ ] Email not verified → 403 Forbidden with message "Please verify your email first"
   - [ ] Account locked (too many failed attempts) → 429 Too Many Requests with message "Account temporarily locked. Try again later or reset your password."
   - [ ] Database error → 500 Internal Server Error with generic message

7. **Audit & Logging**
   - [ ] Successful login is logged: `{ timestamp, user_id, email, action: "login_successful", ip_address, user_agent }`
   - [ ] Failed login attempts are logged: `{ timestamp, email, action: "login_failed", reason, ip_address, user_agent }`
   - [ ] Account lockout is logged: `{ timestamp, email, action: "account_locked", ip_address }`

**Technical Considerations:**
- [ASSUMPTION] JWT tokens are used for stateless authentication (no server-side session storage)
- [ASSUMPTION] RS256 (RSA) signing is used for JWT (asymmetric, allows public key verification)
- [ASSUMPTION] Refresh tokens are stored in HttpOnly cookies (web) or secure storage (mobile)
- [ASSUMPTION] Rate limiting is enforced at API gateway or middleware level
- [ASSUMPTION] Failed login attempts are tracked in Redis for performance (not database)

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test JWT token generation includes all required claims
- Test JWT token signature verification (valid signature passes, invalid fails)
- Test bcrypt password comparison (correct password matches, incorrect doesn't)
- Test email normalization (lowercase, trim)

*Integration Tests:*
- Test login with valid email and password → 200 OK, access_token and refresh_token returned
- Test login with invalid email → 401 Unauthorized, message "Invalid email or password"
- Test login with incorrect password → 401 Unauthorized, message "Invalid email or password"
- Test login with unverified email → 403 Forbidden, message "Please verify your email first"
- Test login rate limiting: 6 failed attempts in 15 minutes → 6th returns 429, account locked
- Test successful login resets failed attempt counter
- Test login with locked account → 429 Too Many Requests, message "Account temporarily locked"

*API Contract Tests:*
- Frontend expects response: `{ access_token, refresh_token, user: { user_id, email, first_name, last_name } }` on 200 OK
- Frontend expects error response with descriptive message on 401/403/429

*End-to-End Tests:*
- User registers → verifies email → logs in with correct password → redirected to home screen → can access app
- User logs in with incorrect password → error message displayed → form remains visible for retry
- User logs in → logs out → attempts to access protected route → redirected to login page
- User logs in on device A → logs in on device B → both devices have valid access tokens (independent sessions)

*Security Tests:*
- Attempt login with SQL injection: `admin' OR '1'='1` → treated as literal email, not SQL
- Attempt login with very long password (1MB) → request rejected or timeout
- Verify access token is sent in Authorization header (not in URL or body)
- Verify refresh token is stored in HttpOnly cookie (not accessible to JavaScript)
- Verify password is never returned in response or logs
- Verify rate limiting is per-email AND per-IP (distributed attack mitigation)

*Performance Tests:*
- Login endpoint latency p95 <200ms under 100 concurrent requests
- Bcrypt password verification latency p95 <100ms (bcrypt is intentionally slow)

*Testability Gaps & Questions:*
- **Q1:** Should we implement "remember me" to extend session duration? (Post-MVP)
- **Q2:** Should we support biometric login (Face ID, Touch ID) on mobile? (Post-MVP)
- **Q3:** What is the behavior if user logs in on many devices simultaneously? (Currently unlimited)

---

### STORY 1.5: JWT Token Refresh & Expiration

**Story ID:** SPLIT-1.5  
**Epic:** Epic 1  
**Story Type:** Feature  
**Story Points:** 3  
**Priority:** P0 (Critical)  
**Sprint:** Sprint 1  
**Assigned To:** Backend (Auth Service) + Frontend  
**Dependencies:** STORY 1.4 (User Login)  

**User Story:**
> As a logged-in user  
> I want my session to remain active without re-entering my password  
> So that I can use the app seamlessly while maintaining security

**Description:**
Access tokens expire after 1 hour for security. When an access token expires, the client uses the refresh token (30-day expiration) to obtain a new access token without requiring the user to re-enter their password. If the refresh token also expires, the user must log in again.

**Acceptance Criteria:**

1. **Token Refresh Endpoint (`POST /api/v1/auth/refresh`)**
   - [ ] Endpoint accepts JSON: `{ refresh_token }` (or reads from HttpOnly cookie on web)
   - [ ] Refresh token is validated:
     - Token exists and is not expired
     - Token is valid JWT with correct signature
     - Token type claim is "refresh"
   - [ ] On success:
     - New access token is generated (1-hour expiration)
     - New refresh token is generated (30-day expiration)
     - Response returns 200 OK with new tokens
   - [ ] On failure:
     - Token expired → 401 Unauthorized with message "Session expired. Please log in again."
     - Token invalid → 401 Unauthorized with message "Invalid session. Please log in again."

2. **Frontend Token Refresh Logic**
   - [ ] Frontend intercepts API responses with 401 Unauthorized
   - [ ] If 401 received:
     - Check if refresh token exists and is not expired locally
     - If refresh token exists: call token refresh endpoint
     - If refresh token succeeds: retry original request with new access token
     - If refresh token fails or expired: redirect to login page
   - [ ] On successful refresh: update stored access_token and refresh_token
   - [ ] Maximum 1 refresh attempt per request (prevent infinite loops)

3. **Token Expiration Handling**
   - [ ] Access token expiration time is checked before making API requests
   - [ ] If access token will expire in <5 minutes: proactively refresh (before expiration)
   - [ ] If access token is already expired: refresh immediately
   - [ ] User is not interrupted by token refresh (happens transparently)

4. **Refresh Token Rotation**
   - [ ] On each refresh, old refresh token is invalidated
   - [ ] New refresh token is issued
   - [ ] Prevents token replay attacks (if refresh token is stolen, it can only be used once)

5. **Audit & Logging**
   - [ ] Successful token refresh is logged: `{ timestamp, user_id, action: "token_refreshed" }`
   - [ ] Failed token refresh attempts are logged: `{ timestamp, action: "token_refresh_failed", reason }`

**Technical Considerations:**
- [ASSUMPTION] Refresh token rotation is implemented (old token invalidated on each refresh)
- [ASSUMPTION] Refresh token expiration is 30 days (can be adjusted based on security policy)
- [ASSUMPTION] Access token expiration is 1 hour (can be adjusted based on security policy)
- [ASSUMPTION] Frontend proactively refreshes tokens before expiration (not reactively after 401)

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test JWT token refresh generates new access token with updated expiration
- Test refresh token rotation (old token is invalidated)
- Test token validation (expired token rejected, invalid signature rejected)

*Integration Tests:*
- Test token refresh with valid refresh token → 200 OK, new access_token and refresh_token returned
- Test token refresh with expired refresh token → 401 Unauthorized
- Test token refresh with invalid refresh token → 401 Unauthorized
- Test original refresh token is invalidated after refresh (cannot be reused)

*API Contract Tests:*
- Frontend expects response: `{ access_token, refresh_token }` on 200 OK
- Frontend expects 401 Unauthorized on expired/invalid token

*End-to-End Tests:*
- User logs in → waits for access token to expire (simulate by advancing clock) → makes API request → token is automatically refreshed → request succeeds → user is not interrupted
- User logs in → waits for refresh token to expire (simulate by advancing clock) → makes API request → token refresh fails → user is redirected to login page

*Security Tests:*
- Attempt to reuse old refresh token after refresh → request fails (token invalidated)
- Attempt to use refresh token as access token → request fails (token type mismatch)
- Verify refresh token is not leaked in logs or error messages

*Performance Tests:*
- Token refresh endpoint latency p95 <100ms
- JWT token generation and validation latency p95 <50ms

*Testability Gaps & Questions:*
- **Q1:** Should we implement token revocation (user can manually invalidate all tokens)? (Post-MVP)
- **Q2:** Should we implement device tracking (show active sessions)? (Post-MVP)

---

### STORY 1.6: User Logout & Session Termination

**Story ID:** SPLIT-1.6  
**Epic:** Epic 1  
**Story Type:** Feature  
**Story Points:** 2  
**Priority:** P0 (Critical)  
**Sprint:** Sprint 1  
**Assigned To:** Backend (Auth Service) + Frontend  
**Dependencies:** STORY 1.4 (User Login)  

**User Story:**
> As a logged-in user  
> I want to log out  
> So that I can ensure my account is not accessible from shared devices

**Description:**
Users can log out by clearing their local tokens. Optionally, the backend can maintain a token blacklist to prevent use of old tokens (e.g., if device is lost).

**Acceptance Criteria:**

1. **Frontend Logout**
   - [ ] React Native Web provides "Log Out" button in app menu/settings
   - [ ] On click:
     - Access token is cleared from local storage / secure storage
     - Refresh token is cleared from local storage / secure storage / HttpOnly cookie
     - User is redirected to login page
     - Confirmation message is displayed: "You have been logged out"

2. **Backend Logout Endpoint (Optional) (`POST /api/v1/auth/logout`)**
   - [ ] Endpoint accepts no parameters (uses access token from Authorization header)
   - [ ] On success:
     - (Optional) Current access token and refresh token are added to blacklist
     - Response returns 200 OK with message "Logged out successfully"
   - [ ] On failure:
     - No valid access token → 401 Unauthorized

3. **Token Blacklist (Optional)**
   - [ ] Tokens added to blacklist are stored in Redis with expiration matching token expiration
   - [ ] On every API request, token is checked against blacklist
   - [ ] If token is in blacklist → 401 Unauthorized, redirect to login
   - [ ] Blacklist entries are automatically expired (no manual cleanup needed)

4. **Audit & Logging**
   - [ ] Successful logout is logged: `{ timestamp, user_id, action: "logout_successful" }`

**Technical Considerations:**
- [ASSUMPTION] Frontend logout is the primary mechanism (token clearing client-side)
- [ASSUMPTION] Backend logout endpoint is optional (adds overhead for token blacklist management)
- [ASSUMPTION] Token blacklist is stored in Redis (fast, ephemeral)
- [ASSUMPTION] Token blacklist entries expire automatically (no manual cleanup)

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test token blacklist entry creation and expiration

*Integration Tests:*
- Test logout endpoint with valid access token → 200 OK, token is blacklisted
- Test logout endpoint without access token → 401 Unauthorized
- Test that blacklisted token cannot be used for subsequent API requests → 401 Unauthorized

*End-to-End Tests:*
- User logs in → clicks logout → redirected to login page → cannot access app without re-login
- User logs in → logs out → attempts to use old access token → request fails with 401 Unauthorized

*Security Tests:*
- Verify old access token cannot be used after logout (blacklist check)
- Verify old refresh token cannot be used after logout

*Testability Gaps & Questions:*
- **Q1:** Should backend logout endpoint be mandatory or optional? (Affects complexity vs. security)
- **Q2:** Should we implement "logout all devices" functionality? (Post-MVP)

---

### STORY 1.7: User Profile Management & Phone Number Collection

**Story ID:** SPLIT-1.7  
**Epic:** Epic 1  
**Story Type:** Feature  
**Story Points:** 3  
**Priority:** P0 (Critical)  
**Sprint:** Sprint 1  
**Assigned To:** Backend (Auth Service) + Frontend  
**Dependencies:** STORY 1.1 (User Registration)  

**User Story:**
> As a user  
> I want to view and edit my profile (name, phone number)  
> So that my friends see my correct name and I can receive SMS payment reminders

**Description:**
Users can view their profile information and update their name and phone number. Phone number is used for SMS payment reminders (Epic 5). Phone number validation and optional SMS verification are included.

**Acceptance Criteria:**

1. **Get User Profile Endpoint (`GET /api/v1/users/profile`)**
   - [ ] Endpoint requires valid access token (authenticated)
   - [ ] Returns user object:
     - `user_id`
     - `email`
     - `first_name`
     - `last_name`
     - `phone_number` (nullable)
     - `phone_verified` (boolean, if phone_number exists)
     - `created_at`
     - `updated_at`
   - [ ] Response returns 200 OK

2. **Update User Profile Endpoint (`PATCH /api/v1/users/profile`)**
   - [ ] Endpoint requires valid access token (authenticated)
   - [ ] Accepts JSON: `{ first_name, last_name, phone_number }` (all optional)
   - [ ] Validation:
     - `first_name`: 1-100 characters, alphanumeric + spaces
     - `last_name`: 1-100 characters, alphanumeric + spaces
     - `phone_number`: E.164 format (international, e.g., "+1-555-123-4567" or "+44-20-7946-0958")
   - [ ] On success:
     - User record is updated
     - If phone_number is new or changed: phone verification is triggered (see STORY 1.8)
     - Response returns 200 OK with updated user object
   - [ ] On failure:
     - Invalid phone_number format → 400 Bad Request with message "Invalid phone number format. Use international format (e.g., +1-555-123-4567)"
     - Invalid name format → 400 Bad Request
     - Database error → 500 Internal Server Error

3. **Frontend Profile Page**
   - [ ] React Native Web page displays at `/profile` route (requires authentication)
   - [ ] Page displays:
     - Email (read-only)
     - First name (editable text field)
     - Last name (editable text field)
     - Phone number (editable text field with placeholder "+1-555-123-4567")
     - "Save" button (disabled until changes made)
     - "Cancel" button
   - [ ] Real-time validation:
     - Phone number format validation (E.164)
     - Name field validation (1-100 characters)
   - [ ] On save:
     - Loading state displayed
     - Success message: "Profile updated"
     - If phone number changed: message "Verification code sent to your phone"
   - [ ] On error: error message displayed

4. **Audit & Logging**
   - [ ] Profile update is logged: `{ timestamp, user_id, action: "profile_updated", fields_changed: ["first_name", "phone_number"] }`

**Technical Considerations:**
- [ASSUMPTION] Phone number is stored in E.164 format (international standard)
- [ASSUMPTION] Phone number validation uses libphonenumber library
- [ASSUMPTION] Phone number verification is triggered on update (see STORY 1.8)
- [ASSUMPTION] Email cannot be changed (security consideration)

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test phone number validation (valid: "+1-555-123-4567", "+44-20-7946-0958"; invalid: "555-123-4567", "not-a-number")
- Test name validation (valid: "John", "Mary Jane"; invalid: "", "a" [too short], "a"*101 [too long])

*Integration Tests:*
- Test get profile endpoint with valid access token → 200 OK, user object returned
- Test get profile endpoint without access token → 401 Unauthorized
- Test update profile with valid phone number → 200 OK, phone_number updated, verification triggered
- Test update profile with invalid phone number → 400 Bad Request
- Test update profile with valid name → 200 OK, name updated
- Test update profile with invalid name (empty) → 400 Bad Request

*API Contract Tests:*
- Frontend expects response: `{ user_id, email, first_name, last_name, phone_number, phone_verified, created_at, updated_at }` on 200 OK

*End-to-End Tests:*
- User logs in → navigates to profile page → updates name and phone number → clicks save → profile is updated → verification code is sent to phone

*Security Tests:*
- Attempt to update profile of another user (using different user_id) → 403 Forbidden
- Verify email cannot be changed (endpoint rejects email field)
- Verify password cannot be changed via profile endpoint (separate endpoint in STORY 1.3)

*Performance Tests:*
- Profile endpoint latency p95 <100ms

*Testability Gaps & Questions:*
- **Q1:** Should we allow users to change email address? (Currently not supported)
- **Q2:** Should we implement profile picture upload? (Post-MVP)

---

### STORY 1.8: Phone Number Verification via SMS

**Story ID:** SPLIT-1.8  
**Epic:** Epic 1  
**Story Type:** Feature  
**Story Points:** 3  
**Priority:** P1 (Important)  
**Sprint:** Sprint 2  
**Assigned To:** Backend (Auth Service) + Frontend  
**Dependencies:** STORY 1.7 (User Profile Management)  

**User Story:**
> As a user who has provided a phone number  
> I want to verify my phone number via SMS  
> So that SplitPay can confirm I own the number and use it for payment reminders

**Description:**
When a user updates their phone number, an SMS verification code (6 digits) is sent. The user enters the code to verify ownership. Unverified phone numbers cannot be used for SMS reminders.

**Acceptance Criteria:**

1. **Phone Verification Trigger**
   - [ ] When phone_number is added or updated (STORY 1.7):
     - 6-digit verification code is generated (random, 0-999999)
     - Code is stored in database with phone_number, user_id, expiration_time (10 minutes), is_used flag
     - SMS is sent to phone_number with message: "Your SplitPay verification code is: 123456. Valid for 10 minutes."
     - phone_verified flag is set to false

2. **Phone Verification Endpoint (`POST /api/v1/users/verify-phone`)**
   - [ ] Endpoint requires valid access token (authenticated)
   - [ ] Accepts JSON: `{ code }`
   - [ ] Code is validated:
     - Code exists in database for user
     - Code has not expired (10-minute window)
     - Code has not been used (is_used flag is false)
   - [ ] On success:
     - Code is marked as used (is_used = true)
     - User record is updated: `phone_verified = true`, `phone_verified_at = now()`
     - Response returns 200 OK with message "Phone number verified"
   - [ ] On failure:
     - Code expired → 400 Bad Request with message "Verification code expired. Request a new one."
     - Code invalid → 400 Bad Request with message "Invalid verification code"
     - Code already used → 400 Bad Request with message "Verification code already used"

3. **Resend Verification Code (`POST /api/v1/users/resend-phone-verification`)**
   - [ ] Endpoint requires valid access token (authenticated)
   - [ ] New verification code is generated
   - [ ] Previous codes are marked as expired (is_used = true)
   - [ ] New SMS is sent to phone_number
   - [ ] Response returns 200 OK with message "Verification code sent"
   - [ ] Rate limiting: max 3 resend requests per phone_number per hour → 429 Too Many Requests

4. **Frontend Phone Verification Page**
   - [ ] React Native Web page displays after phone number is updated
   - [ ] Page displays:
     - Message: "Enter the 6-digit code sent to [phone_number]"
     - 6 input fields (one digit each, auto-advance to next field)
     - "Verify" button
     - "Resend code" link (disabled for 60 seconds after initial send)
     - "Edit phone number" link
   - [ ] On submit:
     - Loading state displayed
     - Success: redirect to profile page with message "Phone number verified"
     - Failure: error message displayed, form remains visible for retry

5. **Audit & Logging**
   - [ ] Phone verification request is logged: `{ timestamp, user_id, action: "phone_verification_requested", phone_number }`
   - [ ] Successful phone verification is logged: `{ timestamp, user_id, action: "phone_verified", phone_number }`
   - [ ] Failed phone verification attempts are logged: `{ timestamp, user_id, action: "phone_verification_failed", reason }`

**Technical Considerations:**
- [ASSUMPTION] SMS service is configured (Twilio, AWS SNS, etc.)
- [ASSUMPTION] Verification codes expire after 10 minutes (shorter than email verification)
- [ASSUMPTION] SMS delivery latency is <30 seconds (target)
- [ASSUMPTION] Phone number verification is required for SMS reminders (see Epic 5)

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test 6-digit code generation is random
- Test code expiration logic (10-minute window)
- Test code validation (valid code passes, invalid fails)

*Integration Tests:*
- Test phone verification endpoint with valid code → 200 OK, phone_verified = true
- Test phone verification with expired code → 400 Bad Request
- Test phone verification with already-used code → 400 Bad Request
- Test resend verification code → new code generated, SMS sent, 200 OK
- Test resend rate limiting: 4 requests in 1 hour → 4th returns 429

*API Contract Tests:*
- Frontend expects response: `{ message: "Phone number verified" }` on 200 OK
- Frontend expects error response with descriptive message on 400

*End-to-End Tests:*
- User updates phone number → receives SMS with verification code → enters code → phone is verified
- User updates phone number → receives SMS → does not verify immediately → clicks "Resend code" → receives new SMS → verifies successfully
- User updates phone number → verification code expires (10 minutes) → attempts to verify → error message "Code expired"

*Security Tests:*
- Attempt to verify phone number for another user (using different user_id) → 403 Forbidden
- Attempt to reuse verification code twice → second attempt fails
- Attempt to use expired code → fails
- Verify verification code is not leaked in logs or error messages
- Verify SMS delivery is reliable (test retry logic if SMS fails)

*Performance Tests:*
- Phone verification endpoint latency p95 <100ms
- SMS delivery latency p95 <30 seconds

*Testability Gaps & Questions:*
- **Q1:** Should we implement phone verification via voice call as alternative to SMS? (Post-MVP)
- **Q2:** What is the behavior if SMS delivery fails? (Retry logic needed)
- **Q3:** Should we allow users to skip phone verification initially? (Affects feature gating)

---

## EPIC 2: RECEIPT CAPTURE & OCR PROCESSING

**Epic Goal:** Enable users to photograph receipts, extract line items via OCR, and present extracted data for item claiming. Make receipt data entry <30 seconds.

**Business Value:** Receipt scanning is the core differentiator vs. competitors like Splitwise. Fast, accurate OCR enables the "30-second split" value proposition.

**Primary Personas:** Social Sarah, Trip Coordinator Tina

**Success Metrics:**
- Receipt upload success rate ≥95% (OCR extracts ≥80% of items correctly)
- Receipt processing time <5 seconds (p99)
- User satisfaction with OCR accuracy ≥4/5 stars
- Manual correction rate <20% (users need to manually fix OCR errors)

**Acceptance Criteria (Epic-Level):**
- Users can photograph a receipt using device camera or upload from gallery
- OCR extracts line items, quantities, prices from receipt image
- Extracted items are presented for user review and correction
- OCR handles various receipt formats (thermal, printed, digital)
- OCR handles multiple languages (English, Spanish, French initially)
- Fallback: users can manually enter items if OCR fails
- Receipt images are stored securely (encrypted, not logged)

---

### STORY 2.1: Receipt Upload & Image Validation

**Story ID:** SPLIT-2.1  
**Epic:** Epic 2  
**Story Type:** Feature  
**Story Points:** 5  
**Priority:** P0 (Critical)  
**Sprint:** Sprint 1  
**Assigned To:** Backend (Expense Service) + Frontend  
**Dependencies:** STORY 1.4 (User Login)  

**User Story:**
> As a user at a restaurant or on a trip  
> I want to photograph a receipt or upload an image  
> So that I can quickly create a split expense without manually entering items

**Description:**
Users can capture a receipt photo in-app (via camera) or upload from device gallery. The app validates image quality, orientation, and file size. Valid images are uploaded to backend for OCR processing.

**Acceptance Criteria:**

1. **Receipt Upload UI (Frontend)**
   - [ ] React Native Web provides camera interface (via `react-native-camera` or similar)
   - [ ] UI displays:
     - Live camera preview with receipt frame overlay (guides user to center receipt)
     - "Take Photo" button
     - "Upload from Gallery" button
     - "Cancel" button
   - [ ] After photo is taken:
     - Preview of captured image is displayed
     - "Confirm" and "Retake" buttons are shown
   - [ ] On confirm:
     - Image is validated (see below)
     - If valid: image is uploaded to backend
     - If invalid: error message displayed with guidance (e.g., "Image too small, please try again")
     - Loading state displayed during upload (progress bar showing upload %)
   - [ ] Image upload supports offline queue (if network fails, image is queued for upload when connectivity restored)

2. **Image Validation (Frontend & Backend)**
   - [ ] File size validation:
     - Minimum: 100 KB (too small = low OCR quality)
     - Maximum: 10 MB (prevent abuse)
     - If invalid → error message "Image must be between 100 KB and 10 MB"
   - [ ] Image format validation:
     - Supported: JPEG, PNG, WebP, HEIC
     - If invalid → error message "Unsupported image format. Please use JPEG, PNG, or WebP"
   - [ ] Image dimensions validation:
     - Minimum: 640x480 pixels (too small = low OCR quality)
     - If invalid → error message "Image resolution too low. Please use a higher resolution photo"
   - [ ] Image orientation:
     - Frontend auto-rotates image based on EXIF data
     - Backend detects receipt orientation (portrait/landscape) and auto-rotates if needed
   - [ ] Image quality heuristics (frontend):
     - Blur detection: reject if image is too blurry
     - Brightness detection: warn if too dark or too bright
     - Text detection: warn if no text detected (likely not a receipt)

3. **Backend Receipt Upload Endpoint (`POST /api/v1/receipts/upload`)**
   - [ ] Endpoint requires valid access token (authenticated)
   - [ ] Accepts multipart/form-data:
     - `image` (file, required)
     - `group_id` (UUID, optional - receipt can be associated with a group)
     - `expense_date` (ISO 8601 date, optional - default to today)
   - [ ] Image is validated (file size, format, dimensions)
   - [ ] Image is stored securely:
     - Stored in encrypted blob storage (AWS S3 with server-side encryption, or similar)
     - Object key: `receipts/{user_id}/{receipt_id}/{timestamp}.jpg`
     - Image is NOT stored in database (only reference/URL stored)
     - Image access is restricted to authorized users (user who uploaded or group members)
   - [ ] Receipt record is created in database:
     - `receipt_id` (UUID)
     - `user_id` (who uploaded)
     - `group_id` (optional)
     - `image_url` (encrypted reference)
     - `image_hash` (SHA-256 of image, for deduplication)
     - `status` (enum: "uploaded", "processing", "items_extracted", "error")
     - `created_at`
     - `updated_at`
   - [ ] Response returns 202 Accepted (async processing):
     - `receipt_id`
     - `status: "processing"`
     - Message: "Receipt received. Extracting items..."
   - [ ] OCR processing is triggered asynchronously (see STORY 2.2)

4. **Image Deduplication**
   - [ ] Image hash (SHA-256) is computed
   - [ ] If image hash matches existing receipt: return existing receipt instead of creating duplicate
   - [ ] Prevents accidental duplicate uploads

5. **Error Handling**
   - [ ] File size invalid → 400 Bad Request
   - [ ] File format invalid → 400 Bad Request
   - [ ] Image dimensions invalid → 400 Bad Request
   - [ ] Storage error → 500 Internal Server Error with generic message
   - [ ] Rate limiting: max 100 receipt uploads per user per day → 429 Too Many Requests

6. **Audit & Logging**
   - [ ] Receipt upload is logged: `{ timestamp, user_id, receipt_id, action: "receipt_uploaded", file_size, image_hash }`
   - [ ] Failed uploads are logged: `{ timestamp, user_id, action: "receipt_upload_failed", reason }`
   - [ ] Image content is never logged (privacy)

**Technical Considerations:**
- [ASSUMPTION] Blob storage is encrypted at rest (AWS S3 SSE-S3 or SSE-KMS)
- [ASSUMPTION] Image URLs are signed (time-limited, user-specific) to prevent unauthorized access
- [ASSUMPTION] Image deduplication is optional (can be post-MVP optimization)
- [ASSUMPTION] OCR processing is asynchronous (user does not wait for extraction)
- [ASSUMPTION] Receipt images are deleted after 30 days (data retention policy)

**Testing Strategy (QA Notes):**

*Unit Tests:*
- Test image hash computation (same image → same hash, different image → different hash)
- Test file size validation (100 KB edge case, 10 MB edge case, 50 KB [too small], 20 MB [too large])
- Test image format validation (JPEG valid, PNG valid, GIF invalid, BMP invalid)
- Test image dimension validation (640x480 valid, 320x240 [too small], 4000x3000 valid)

*Integration Tests:*
- Test receipt upload endpoint with valid image → 202 Accepted, receipt_id returned, status "processing"
- Test receipt upload with image too small → 400 Bad Request
- Test receipt upload with image too large → 400 Bad Request
- Test receipt upload with unsupported format → 400 