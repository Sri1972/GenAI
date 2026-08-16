# FairSplit — Product Requirements Document

**Document Version:** 1.0  
**Last Updated:** [DATE]  
**Owner:** Product Management  
**Status:** Ready for Engineering Review

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Market Analysis](#market-analysis)
4. [User Personas](#user-personas)
5. [Product Vision & Goals](#product-vision--goals)
6. [Success Metrics & KPIs](#success-metrics--kpis)
7. [Feature Requirements](#feature-requirements)
8. [User Journey & Workflows](#user-journey--workflows)
9. [Out of Scope](#out-of-scope)
10. [Technical Architecture Overview](#technical-architecture-overview)
11. [Risks & Mitigations](#risks--mitigations)
12. [Open Questions](#open-questions)

---

## EXECUTIVE SUMMARY

**Product Name:** FairSplit

**One-Liner:** FairSplit is a responsive web application that simplifies splitting bills among groups by using OCR to extract receipt line items, automatically assigning items to individuals, and calculating optimized payment flows with minimal transactions.

**Target Market:** Social groups (friends, colleagues, roommates) who frequently share expenses and want to eliminate friction from bill settlement.

**Launch Scope:** MVP supporting one-time group dinners/trips and recurring splits for shared housing.

**Key Differentiator:** Receipt OCR automation eliminates manual line-item entry; transaction optimization reduces settlement complexity.

**Success Criteria:** Users reduce bill-splitting friction by 70% compared to manual tracking; adoption reaches 1,000 active monthly users within 6 months of launch.

---

## PROBLEM STATEMENT

### The Core Problem

When groups of people share expenses (dinners, trips, rent, utilities), settling up is tedious and error-prone:

- **Manual entry burden:** Manually typing out who ordered what is time-consuming and error-prone.
- **Calculation complexity:** Figuring out who owes whom, especially with tax and tip proportional distribution, requires mental math or external tools.
- **Settlement friction:** Without a clear record and reminder system, payments are delayed or forgotten.
- **Recurring expenses:** Roommates splitting rent or utilities must repeat the process monthly with no automation.

### Current Workarounds (Pain Points)

- **Spreadsheets:** Require manual updates, version control issues, no centralized record.
- **Cash settlement:** Loses audit trail, difficult to track over time.
- **Venmo/PayPal:** No receipt context; users manually calculate amounts.
- **Existing apps (e.g., Splitwise):** Require manual line-item entry; no OCR; not optimized for one-time social splits.

### Why This Matters

- **Time cost:** Average group of 4 spends 10-15 minutes manually splitting a bill.
- **Money loss:** Calculation errors lead to over/underpayment.
- **Relationship friction:** Ambiguous splits damage trust; forgotten reminders create awkwardness.

---

## MARKET ANALYSIS

### Competitive Landscape

| Product | Strengths | Weaknesses | FairSplit Advantage |
|---------|-----------|-----------|-------------------|
| **Splitwise** | Established, mobile app, community features | Manual entry required, no OCR, designed for long-term tracking | Receipt OCR speeds up entry; optimized for one-time events |
| **Venmo** | Simple P2P payments, social network | No expense tracking, no splitting logic | Integrates bill logic; Venmo handles payment execution |
| **Receipt apps (e.g., Expensify)** | Strong OCR, expense categorization | Designed for business, not social splits | Focused on social context; optimized UX for groups |
| **Manual spreadsheets** | Flexible, free | Error-prone, no automation, no reminders | Eliminates manual work, adds automation |
| **Group chat + calculator** | Familiar interface | No record, easily lost, poor UX | Centralized, auditable, professional |

### Market Opportunity

- **Addressable Market:** ~150M adults in developed countries who dine/travel in groups monthly.
- **TAM Segment:** 20-30M who actively use expense-splitting tools (Splitwise: ~50M users, but many inactive).
- **Differentiation:** Receipt OCR is a high-friction pain point in existing solutions; first-mover advantage in social + OCR space.

### Market Trends

- OCR technology has matured (Google Vision, AWS Textract); cost is <$0.01 per image.
- Post-pandemic: Increased group travel and social dining (pent-up demand).
- Gen Z & Millennials: Prefer digital-first, frictionless tools; willing to adopt new apps if UX is superior.

---

## USER PERSONAS

### Persona 1: **Sarah (The Social Organizer)**

**Demographics:**
- Age: 28, urban, college-educated
- Occupation: Marketing manager
- Income: $65K-$85K

**Behaviors:**
- Organizes 2-3 group dinners or trips per month
- Typically covers the bill and needs to collect from others
- Uses Venmo/PayPal frequently
- Comfortable with technology; expects mobile-friendly interfaces
- Values speed and clarity

**Pain Points:**
- Manually typing out who ordered what takes 5+ minutes
- Calculating tax/tip splits is tedious
- Follows up with friends via text; some don't pay promptly
- Frustrated by ambiguity ("Did I pay you back for that dinner?")

**Goals:**
- Quickly settle bills without friction
- Have a clear record for future reference
- Send automated reminders to non-payers
- Minimize time spent on admin work

**Success Metric:** Sarah uses FairSplit for 80% of group dinners she organizes; time to settle a bill drops from 15 min to <3 min.

---

### Persona 2: **Marcus (The Roommate)**

**Demographics:**
- Age: 25, urban, student/early career
- Occupation: Software engineer (early career)
- Income: $50K-$70K

**Behaviors:**
- Shares apartment with 2 other roommates
- Splits rent, utilities, groceries, internet monthly
- Prefers digital payment; uses banking app regularly
- Wants a single source of truth for recurring expenses
- Dislikes ambiguity or repeated conversations about money

**Pain Points:**
- Manually recalculating rent/utilities splits each month is tedious
- Roommates forget to pay on time
- No clear record of who paid for shared groceries
- Switching roommates creates settlement chaos

**Goals:**
- Automate recurring splits for rent and utilities
- Set up one-time splits for shared groceries
- Receive automated reminders for due payments
- Export settlement records for tax/audit purposes

**Success Metric:** Marcus sets up recurring splits once and doesn't need to manually re-enter data; payment reminders reduce late payments from 30% to <5%.

---

### Persona 3: **Priya (The Budget-Conscious Traveler)**

**Demographics:**
- Age: 31, suburban, college-educated
- Occupation: Consultant (frequent travel)
- Income: $80K-$120K

**Behaviors:**
- Takes 2-3 group trips annually (weekends, vacations)
- Often covers shared hotel/car/food costs upfront
- Meticulous about tracking expenses
- Uses spreadsheets to track trip costs
- Wants detailed breakdowns and receipts

**Pain Points:**
- Manually tracking multi-day trip expenses across many transactions is error-prone
- Tax/tip calculations differ by location; hard to standardize
- Roommates dispute amounts without receipts
- Spreadsheets don't send reminders; payments are slow

**Goals:**
- Upload receipts throughout trip; auto-categorize by person
- Calculate final settlement with clear itemization
- Share receipt images as proof
- Receive payment within 1 week of trip end

**Success Metric:** Priya settles trip expenses 5x faster than spreadsheet method; zero disputes due to receipt transparency.

---

## PRODUCT VISION & GOALS

### Vision Statement

FairSplit makes splitting shared expenses frictionless by automating receipt processing, optimizing payment flows, and ensuring timely settlement with minimal back-and-forth.

### Product Goals (12-Month Horizon)

1. **Adoption:** Reach 1,000 monthly active users (MAU) by end of Q2; 5,000 MAU by end of Q4.
2. **Engagement:** 60% of users return within 30 days; average user creates 3+ splits per month.
3. **Retention:** 40% monthly retention rate (typical for social tools in early stage).
4. **NPS:** Achieve NPS of 40+ (good for B2C).
5. **Revenue:** (Future) Freemium model; 10% conversion to paid tier by Q4.

### Strategic Priorities

1. **Nail the core MVP:** Receipt OCR + item assignment + payment optimization must work flawlessly.
2. **Frictionless onboarding:** Users create first split in <3 minutes with no tutorial.
3. **Social proof:** Encourage sharing of splits; build network effects.
4. **Reliability:** Email reminders must have 99%+ delivery rate.

---

## SUCCESS METRICS & KPIs

### Primary Metrics (North Star)

| Metric | Target | Measurement | Owner |
|--------|--------|-------------|-------|
| **Monthly Active Users (MAU)** | 1,000 by Q2; 5,000 by Q4 | Unique users creating ≥1 split per month | Analytics |
| **Splits Created (Volume)** | 500 splits/week by Q2 | Count of splits created (one-time + recurring) | Analytics |
| **OCR Accuracy Rate** | ≥95% | % of line items correctly extracted vs. manual audit | QA/Analytics |
| **Payment Settlement Rate** | ≥80% within 7 days | % of splits where all payments received within 7 days | Analytics |
| **User Retention (30-day)** | ≥40% | % of users active in month N who return in month N+1 | Analytics |

### Secondary Metrics (Diagnostic)

| Metric | Target | Measurement | Owner |
|--------|--------|-------------|-------|
| **Time to First Split** | <3 min | Time from sign-up to first split creation | Analytics |
| **Receipt Upload Success Rate** | ≥98% | % of receipt uploads processed without error | QA/Analytics |
| **Email Delivery Rate** | ≥99% | % of reminder emails delivered (not bounced) | Analytics |
| **Churn Rate (30-day)** | ≤60% | % of users inactive after 30 days | Analytics |
| **NPS (Net Promoter Score)** | ≥40 | Survey: "How likely to recommend?" (0-10 scale) | Product/Analytics |
| **Average Splits per User** | ≥3/month | Mean splits created per active user | Analytics |
| **Disputed Items Rate** | ≤5% | % of line items flagged as incorrect by users | Analytics |

### Business Metrics (Future)

- **Conversion Rate (Freemium):** % of free users converting to paid tier.
- **ARPU (Average Revenue Per User):** Revenue per active user.
- **LTV:CAC Ratio:** Lifetime value vs. customer acquisition cost.

### Success Thresholds for MVP Launch

- ✅ OCR accuracy ≥95% on sample receipts (100+ diverse receipts tested).
- ✅ Email delivery rate ≥99% (verified via email service provider).
- ✅ Zero critical bugs in core flows (receipt upload, item assignment, payment calculation).
- ✅ Time to first split <3 min for 90% of new users.
- ✅ NPS ≥30 from beta users.

---

## FEATURE REQUIREMENTS

### Feature Prioritization Framework

**P0 (Must-Have for MVP):** Core functionality; product cannot launch without.  
**P1 (Should-Have for MVP):** High-value; strong user demand; feasible in timeline.  
**P2 (Nice-to-Have):** Valuable but can be deferred; lower priority or higher effort.

---

## P0 FEATURES (MVP Must-Haves)

### P0.1: Receipt Upload & OCR Processing

**User Story:**  
As Sarah, I want to take a photo of a receipt or upload an image file so that the app automatically extracts line items without me typing them manually.

**Acceptance Criteria:**

- [ ] User can upload a receipt image (JPG, PNG, PDF) via web interface.
- [ ] App displays uploaded image prominently for reference.
- [ ] OCR engine (AWS Textract or Google Vision API [ASSUMPTION: specific provider TBD]) extracts line items, quantities, prices, and tax/tip.
- [ ] Extracted data is displayed in editable table format (line item, price, quantity).
- [ ] User can manually edit extracted items if OCR made errors.
- [ ] OCR accuracy is ≥95% on test set of 100 diverse receipts (restaurants, stores, etc.).
- [ ] Processing time is <5 seconds for typical receipt (average ~30 items).
- [ ] Error handling: If OCR fails, user receives clear error message with option to manually enter items.
- [ ] Extracted data is stored in database linked to split record.

**Success Metric:**  
- 95%+ of users successfully upload receipt on first attempt.
- Average OCR accuracy ≥95%.

**Out of Scope:**  
- Handwritten receipts (only printed/digital receipts).
- Non-English receipts (MVP: English only).
- Complex receipts with coupons, discounts, or loyalty program deductions (handled as line items, not calculated).

---

### P0.2: Item Assignment (Claim Items)

**User Story:**  
As Marcus, I want to assign extracted line items to specific group members so that the app knows who ordered what.

**Acceptance Criteria:**

- [ ] After OCR extraction, app displays a list of line items with unclaimed status.
- [ ] User can select a line item and assign it to a group member from a dropdown list.
- [ ] User can assign multiple items to the same person in bulk (e.g., "select all appetizers").
- [ ] UI shows visual indication of claimed vs. unclaimed items (e.g., color coding, checkmarks).
- [ ] User can reassign an item if they made a mistake.
- [ ] All items must be claimed before proceeding to payment calculation.
- [ ] User receives warning if items remain unclaimed.
- [ ] Assignment data is stored and displayed for audit/confirmation.

**Success Metric:**  
- 100% of splits have all items claimed before settlement.
- Time to assign items on 30-item receipt <2 min.

**Out of Scope:**  
- Automatic assignment based on ML prediction (future enhancement).
- Shared items (e.g., "appetizer platter for group") — treated as separate line items or manual split.

---

### P0.3: Group Member Management

**User Story:**  
As Priya, I want to add group members to a split so that I can assign expenses to them and track who owes what.

**Acceptance Criteria:**

- [ ] User can create a split and add group members by email address or phone number.
- [ ] App displays list of added members with their assigned items and amounts.
- [ ] User can add/remove members before settlement is finalized.
- [ ] Each member has a unique identifier within the split (email or phone).
- [ ] Duplicate member entries are prevented (validation).
- [ ] User can optionally set a member as "organizer" (person who paid the bill).
- [ ] Group member data is stored with the split record.

**Success Metric:**  
- 100% of splits have ≥2 members added.
- Time to add 4 members <1 min.

**Out of Scope:**  
- Saved group templates (future enhancement).
- Inviting members via link (P1 feature).

---

### P0.4: Payment Calculation & Optimization

**User Story:**  
As Sarah, I want the app to calculate who owes whom, including tax and tip, and minimize the number of transactions needed to settle up.

**Acceptance Criteria:**

- [ ] App calculates total amount owed by each person (sum of claimed items + proportional tax + proportional tip).
- [ ] Tax is distributed proportionally based on each person's item subtotal.
- [ ] Tip is distributed proportionally based on each person's item subtotal (or total, configurable by user [ASSUMPTION: clarify default]).
- [ ] App calculates net flows (who owes whom) using transaction optimization algorithm (e.g., minimize number of transactions).
- [ ] Settlement summary shows:
  - Each person's subtotal (items + tax + tip).
  - Net amount owed by each person.
  - Optimized payment instructions (e.g., "Alice pays Bob $25.50").
- [ ] Calculation is displayed clearly with itemized breakdown.
- [ ] User can review and confirm calculation before finalizing.
- [ ] Calculation is stored with split record for audit.
- [ ] Rounding errors (cents) are handled consistently (e.g., round to nearest cent; allocate remainder to organizer).

**Success Metric:**  
- 100% of calculations are mathematically correct (verified via automated tests).
- Settlement summary is understood by 95%+ of users without additional explanation.

**Out of Scope:**  
- Tipping algorithm optimization (e.g., "tip on pre-tax vs. post-tax") — user configurable [ASSUMPTION].
- Splitting shared items (e.g., "3 people share a $30 appetizer") — handled as manual split in P1.
- Discounts or coupons applied to specific items (MVP: not supported; treated as separate line items).

---

### P0.5: Settlement Summary & Confirmation

**User Story:**  
As Marcus, I want to review the final settlement before confirming so that I can verify amounts are correct.

**Acceptance Criteria:**

- [ ] Settlement page displays:
  - Receipt image (reference).
  - Itemized list of who ordered what.
  - Each person's subtotal (items + tax + tip).
  - Optimized payment instructions (who pays whom, amount).
  - Total split amount vs. receipt total (must match).
- [ ] User can edit/reassign items before confirming.
- [ ] User confirms settlement by clicking "Finalize" button.
- [ ] Confirmation creates immutable split record.
- [ ] User receives confirmation message (on-screen).

**Success Metric:**  
- 100% of splits reach confirmation stage.
- 90%+ of users confirm settlement without reassigning items (indicates clarity).

**Out of Scope:**  
- Undo after confirmation (future feature; may require policy).
- Partial payment tracking (MVP: all-or-nothing settlement).

---

### P0.6: Email Notifications & Reminders

**User Story:**  
As Priya, I want group members to receive an email notification so they know they owe money and can pay promptly.

**Acceptance Criteria:**

- [ ] When organizer finalizes split, app sends email to each person who owes money.
- [ ] Email includes:
  - Split summary (what they ordered, amount owed).
  - Payment instructions (who to pay, amount, payment method [ASSUMPTION: Venmo/PayPal links?]).
  - Link to view full split details in app.
  - Due date (configurable by organizer; default: 7 days).
- [ ] Email is sent within 1 minute of split finalization.
- [ ] Email delivery rate ≥99% (verified via email service provider).
- [ ] User can opt-out of email reminders (settings page).
- [ ] Reminder emails are sent automatically:
  - 3 days before due date (if not yet paid).
  - On due date (if not yet paid).
  - 3 days after due date (overdue reminder).
- [ ] Reminders stop once payment is marked as received.

**Success Metric:**  
- Email delivery rate ≥99%.
- 80%+ of users receive and open first notification email.
- Payment settlement rate ≥80% within 7 days.

**Out of Scope:**  
- SMS reminders (future enhancement).
- In-app push notifications (web app; not applicable).
- Payment processing via app (users pay via Venmo/PayPal externally).

---

### P0.7: Recurring Splits (Roommates)

**User Story:**  
As Marcus, I want to set up a recurring split for rent and utilities so that I don't have to manually recreate the split each month.

**Acceptance Criteria:**

- [ ] User can create a "recurring split" with:
  - Split name (e.g., "Apartment Rent - March 2024").
  - Members and their share (fixed amount or percentage).
  - Frequency (monthly, weekly, bi-weekly [ASSUMPTION: confirm frequencies]).
  - Start date and end date (or "ongoing").
  - Due date within each cycle (e.g., "1st of month").
- [ ] App automatically generates a new split instance on the specified frequency.
- [ ] Each recurring instance has the same members and amounts (unless manually edited).
- [ ] User can edit a recurring split (affects future instances only, not past).
- [ ] User can pause or cancel a recurring split.
- [ ] Recurring split dashboard shows:
  - List of active recurring splits.
  - Next due date for each.
  - Payment status for current cycle.
- [ ] Email reminders are sent for each recurring instance (same as P0.6).
- [ ] Recurring split data is stored in database.

**Success Metric:**  
- 50%+ of users with roommates set up ≥1 recurring split.
- 95%+ of recurring splits generate instances on schedule without error.
- Payment settlement rate for recurring splits ≥75% by due date.

**Out of Scope:**  
- Automatic adjustment of shares based on occupancy changes (future feature).
- Pro-rata calculation for partial months (MVP: fixed amounts only).
- Integration with rent payment systems (users pay externally).

---

## P1 FEATURES (Should-Have for MVP)

### P1.1: User Authentication & Accounts

**User Story:**  
As Sarah, I want to create an account and log in so that my splits and history are saved and accessible across sessions.

**Acceptance Criteria:**

- [ ] User can sign up with email and password (or OAuth [ASSUMPTION: Google/Facebook TBD]).
- [ ] Password must meet security requirements (≥8 chars, mix of upper/lower/numbers/symbols [ASSUMPTION: confirm policy]).
- [ ] User can log in with email/password.
- [ ] Session persists across browser sessions (auth token stored securely).
- [ ] User can reset password via email link.
- [ ] User profile page displays:
  - Email, name, phone (optional).
  - List of splits created by user.
  - List of splits where user is a member.
  - Settings (email preferences, payment methods [future]).
- [ ] Account data is stored securely in database.
- [ ] Password is hashed using industry standard (bcrypt or similar [ASSUMPTION]).

**Success Metric:**  
- 90%+ of users complete sign-up within 2 minutes.
- Zero unauthorized access incidents.

**Out of Scope:**  
- Two-factor authentication (future enhancement).
- Social login (future enhancement).
- Account deletion (future feature; data retention policy TBD).

---

### P1.2: Split History & Dashboard

**User Story:**  
As Priya, I want to view all my past splits and their settlement status so that I can track who paid and when.

**Acceptance Criteria:**

- [ ] Dashboard displays:
  - List of recent splits (created by user or where user is a member).
  - For each split: date, members, total amount, settlement status.
  - Filter/sort options (by date, by member, by status).
- [ ] User can click on a split to view full details:
  - Receipt image, itemized breakdown, payment instructions.
  - Payment status for each member (paid/unpaid).
  - Date paid (if applicable).
- [ ] Dashboard shows summary stats:
  - Total amount split (all time).
  - Total amount owed to user.
  - Total amount user owes.
- [ ] Split history is searchable by member name or split name.
- [ ] User can export split history as CSV (future enhancement [ASSUMPTION]).

**Success Metric:**  
- 80%+ of users view their split history within first week.
- Dashboard loads in <2 seconds.

**Out of Scope:**  
- Analytics/insights (e.g., "most frequent splitting partner") — P2 feature.
- Export to accounting software (future enhancement).

---

### P1.3: Invite Members & Sharing

**User Story:**  
As Sarah, I want to invite group members to a split via email link so that they can view details and confirm their items.

**Acceptance Criteria:**

- [ ] When creating a split, user can generate a shareable link (unique token).
- [ ] User can send link via email (app sends on user's behalf) or copy/paste manually.
- [ ] Non-registered users can view split details via link without logging in (read-only).
- [ ] Link expires after 30 days or split is marked as settled [ASSUMPTION: confirm policy].
- [ ] Member can confirm their items and amount via link.
- [ ] Member can request changes to their assignment (flag for organizer review).
- [ ] Organizer receives notification if member disputes their assignment.
- [ ] Link includes payment instructions and due date.

**Success Metric:**  
- 70%+ of members access split via link.
- 95%+ of links work without error.

**Out of Scope:**  
- Group invitations (save group and reuse for future splits) — P2 feature.
- In-app messaging between members — future enhancement.

---

### P1.4: Payment Status Tracking

**User Story:**  
As Marcus, I want to mark payments as received so that I can track who has settled and send follow-up reminders to non-payers.

**Acceptance Criteria:**

- [ ] Organizer can mark individual payments as "paid" after receiving money externally (Venmo, etc.).
- [ ] When organizer marks payment as paid:
  - Status updates on split summary.
  - Member is notified (optional email).
  - Reminder emails stop for that member.
- [ ] Split shows progress bar or status indicator (e.g., "3 of 4 members paid").
- [ ] Organizer can add notes when marking payment (e.g., "received via Venmo").
- [ ] Payment data is timestamped and stored for audit.
- [ ] User can view payment history (who paid when).

**Success Metric:**  
- 100% of payments can be marked as received.
- Organizer receives confirmation when marking payment.

**Out of Scope:**  
- Direct payment processing (users pay externally).
- Automatic payment verification (future enhancement).

---

### P1.5: Error Handling & Validation

**User Story:**  
As Priya, I want clear error messages when something goes wrong so that I can fix the issue quickly.

**Acceptance Criteria:**

- [ ] All user inputs are validated (email format, numeric amounts, required fields).
- [ ] Error messages are clear, specific, and actionable (not generic "Error 500").
- [ ] Examples of handled errors:
  - Invalid email address → "Please enter a valid email (e.g., user@example.com)".
  - Receipt upload fails → "Failed to process image. Please try a clearer photo or enter items manually."
  - Duplicate member → "This person is already in the split."
  - Items not fully assigned → "Please assign all items before confirming."
- [ ] Form fields are marked as required.
- [ ] User is warned before destructive actions (e.g., "Finalizing split cannot be undone").
- [ ] Error logs are captured for debugging (backend).

**Success Metric:**  
- 90%+ of validation errors are resolved by users on first attempt.
- Zero unhandled exceptions in production.

**Out of Scope:**  
- Automatic error recovery (e.g., retry logic) — P2 feature.
- Error analytics dashboard — future tool.

---

### P1.6: Responsive Web Design

**User Story:**  
As Sarah, I want the app to work seamlessly on my phone, tablet, and desktop so that I can split bills on the go.

**Acceptance Criteria:**

- [ ] App is fully responsive (mobile-first design).
- [ ] Breakpoints: mobile (<600px), tablet (600-1024px), desktop (>1024px).
- [ ] All features work on mobile (receipt upload, item assignment, payment tracking).
- [ ] Touch-friendly UI (buttons ≥48px, spacing for finger taps).
- [ ] Images scale appropriately on all screen sizes.
- [ ] No horizontal scrolling required on mobile.
- [ ] Performance is optimized for mobile networks (lazy loading, compression).
- [ ] Tested on common devices (iPhone, Android, iPad, desktop browsers).

**Success Metric:**  
- 60%+ of users access app on mobile.
- Mobile page load time <3 seconds on 4G.
- Zero layout issues on tested devices.

**Out of Scope:**  
- Native mobile apps (iOS/Android) — web-only for MVP.
- Progressive Web App (PWA) features (offline support, install to home screen) — P2 feature.

---

## P2 FEATURES (Nice-to-Have, Deferred)

### P2.1: Shared Items (Split Costs)

**Feature:** Allow users to split a single item among multiple people (e.g., "appetizer platter: $30 split 3 ways").

**Rationale:** Lower priority; most receipts have individual items. Can be handled via manual adjustment in P0 or added later based on user demand.

---

### P2.2: Saved Groups & Templates

**Feature:** Save a group of recurring members and reuse for future splits without re-entering.

**Rationale:** Convenience feature; not essential for MVP. Useful for frequent groups (e.g., "weekly poker night").

---

### P2.3: In-App Messaging

**Feature:** Allow members to message each other within the split to discuss assignments or payment issues.

**Rationale:** Out of scope for MVP; users can communicate via email or external channels. Adds complexity; deferred to future.

---

### P2.4: Payment Method Integration

**Feature:** Integrate with Venmo, PayPal, or Stripe to process payments directly within app.

**Rationale:** Significant compliance, security, and integration complexity. MVP focuses on calculation and tracking; payment execution remains external. Deferred to future based on user demand.

---

### P2.5: Analytics & Insights

**Feature:** Provide insights (e.g., "most frequent splitting partner", "average split amount", spending trends).

**Rationale:** Nice-to-have; not essential for core MVP. Can be added in future release based on user engagement.

---

### P2.6: Advanced OCR Features

**Feature:** Support handwritten receipts, non-English text, or complex receipts with discounts/coupons.

**Rationale:** Lower priority; MVP targets printed/digital receipts in English. Can expand OCR capabilities based on user feedback.

---

### P2.7: Recurring Split Adjustments

**Feature:** Automatically adjust recurring split amounts based on occupancy changes or shared expenses.

**Rationale:** Adds complexity; MVP assumes fixed amounts. Pro-rata calculations for partial months deferred.

---

### P2.8: Export & Reporting

**Feature:** Export split history as CSV, PDF, or integrate with accounting software.

**Rationale:** Useful for detailed tracking; not essential for MVP. Can be added based on user demand.

---

### P2.9: Notification Preferences

**Feature:** Allow users to customize reminder frequency, timing, and channels (email, SMS, in-app).

**Rationale:** MVP uses email reminders on fixed schedule. Advanced customization deferred.

---

### P2.10: Progressive Web App (PWA)

**Feature:** Enable offline access, install to home screen, and push notifications.

**Rationale:** Web app focus for MVP. PWA features (offline, install) deferred to future based on usage patterns.

---

## USER JOURNEY & WORKFLOWS

### Workflow 1: One-Time Group Dinner Split

**Scenario:** Sarah organizes a dinner with 3 friends. She pays the bill and wants to split it.

**Steps:**

1. **Sign Up / Log In:** Sarah signs up or logs into FairSplit.
2. **Create Split:** Clicks "New Split" → selects "One-Time Split" → names it "Dinner at Mario's - March 15".
3. **Add Members:** Adds 3 friends by email (Alice, Bob, Carol).
4. **Upload Receipt:** Takes photo of receipt or uploads file → app processes via OCR → displays extracted items.
5. **Review OCR:** Sarah reviews extracted items; manually corrects 1 item (OCR misread "$12.50" as "$125.0").
6. **Assign Items:** Sarah assigns each item to the person who ordered it:
   - Alice: Pasta ($18), Water ($2.50) → Subtotal: $20.50
   - Bob: Burger ($16), Beer ($5) → Subtotal: $21
   - Carol: Salad ($14), Wine ($8) → Subtotal: $22
   - Sarah: Appetizer ($15) → Subtotal: $15
   - **Subtotal:** $78.50
   - **Tax (8%):** $6.28 → distributed proportionally
   - **Tip (20%):** $15.70 → distributed proportionally
   - **Total:** $100.48
7. **Review Settlement:** App displays: