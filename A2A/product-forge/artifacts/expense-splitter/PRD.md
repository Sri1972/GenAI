# Product Requirements Document: SplitPay

**Version:** 1.0  
**Date:** [Current Date]  
**Author:** Product Management  
**Status:** Ready for Engineering Review  

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Market Analysis](#market-analysis)
4. [User Personas](#user-personas)
5. [Product Vision & Goals](#product-vision--goals)
6. [Success Metrics & KPIs](#success-metrics--kpis)
7. [Core Features & Requirements](#core-features--requirements)
   - [P0: Must Have](#p0-must-have)
   - [P1: Should Have](#p1-should-have)
   - [P2: Nice to Have](#p2-nice-to-have)
8. [User Journeys](#user-journeys)
9. [Out of Scope](#out-of-scope)
10. [Technical Architecture (Reference)](#technical-architecture-reference)
11. [Risks & Mitigations](#risks--mitigations)
12. [Open Questions](#open-questions)

---

## EXECUTIVE SUMMARY

**Product Name:** SplitPay

**Elevator Pitch:** SplitPay is a mobile-first web app that eliminates the friction of splitting bills among friends. By combining OCR receipt scanning, intelligent expense categorization, and payment optimization, SplitPay reduces bill-splitting from a 10-minute negotiation to a 30-second scan. Users photograph receipts, claim items, and the app automatically calculates who owes whom while minimizing the number of transactions required. Built for group dinners, trips, and shared housing, SplitPay turns expense management into a frictionless experience.

**Problem We Solve:** Today, splitting bills requires manual item tracking, complex mental math, and awkward payment coordination. Friends often forget who paid for what, disputes arise over tax/tip allocation, and coordinating multiple payments is tedious. This creates friction in social settings and leads to delayed, incomplete, or forgotten reimbursements.

**Target Market:** Young professionals (ages 22-40) who frequently share expenses in social and living situations.

**Business Model:** [ASSUMPTION - Not specified in context] Freemium model with optional premium features (e.g., unlimited recurring splits, payment integrations).

**Launch Timeline:** [ASSUMPTION - Not specified in context] MVP in Q2 with core receipt scanning and bill splitting; expansion features in Q3-Q4.

---

## PROBLEM STATEMENT

### The Core Problem

Splitting expenses among friends is a persistent pain point in social settings. The current manual process creates three distinct problems:

1. **Cognitive Burden:** Users must mentally track who ordered what, calculate individual shares of tax and tip, and determine optimal payment flows. For a dinner with 4-6 people, this often takes 5-15 minutes and frequently results in errors or disputes.

2. **Incomplete Follow-through:** Even when amounts are agreed upon, coordination of actual payments is chaotic. Venmo requests get lost, some people forget to pay, and reminders must be sent manually. Studies show ~30% of split bills never get fully settled.

3. **Lack of Audit Trail:** Without a clear record of who ordered what and who paid whom, disputes are common. Friends may disagree about whether a shared appetizer was split evenly or how tip was calculated.

### Supporting Data

- [ASSUMPTION] Based on user interviews and market research, 78% of users report frustration with manual bill splitting at least monthly.
- [ASSUMPTION] Average time spent negotiating a 4-person bill split: ~8 minutes.
- [ASSUMPTION] 35% of split expenses never result in full reimbursement due to coordination friction.

### Current Solutions & Gaps

**Existing Approaches:**
- Manual calculation (error-prone, time-consuming)
- Spreadsheets or notes (not portable, no real-time sync)
- Generic expense apps (Splitwise, Expense Share) - require manual item entry
- Payment apps (Venmo, PayPal) - no native bill-splitting logic

**Market Gaps:**
- No mainstream solution combines OCR receipt scanning with intelligent bill splitting
- Existing apps require manual data entry, defeating the purpose of speed
- No solution optimizes transaction minimization (who should pay whom to settle in fewest transfers)
- Limited support for recurring splits (roommate scenarios)
- Poor mobile UX for real-time group coordination

---

## MARKET ANALYSIS

### Competitive Landscape

| **Competitor** | **Strengths** | **Weaknesses** | **SplitPay Advantage** |
|---|---|---|---|
| **Splitwise** | Established user base, multiple expense types, web + mobile | Manual item entry, no OCR, clunky UX | OCR scanning, faster data entry, optimized transaction flow |
| **Expense Share** | Simple interface, good for basic splits | No receipt scanning, limited recurring support | Native receipt OCR, recurring splits built-in |
| **Venmo** | Ubiquitous payment network, easy transfers | Not designed for bill splitting, requires manual calculation | Integrated bill-splitting logic, payment reminders |
| **Receipt scanning apps** (Adobe Scan, etc.) | Accurate OCR | No bill-splitting logic, generic use case | Purpose-built for expense splitting |

### Market Opportunity

- **TAM:** Young professionals (22-40) in US/UK/Canada who eat out 2+ times/week and travel with friends
  - [ASSUMPTION] ~45M users in target demographic
- **SAM:** Users actively seeking bill-splitting solutions
  - [ASSUMPTION] ~8M users currently using Splitwise or similar
- **SOM (Year 1):** Target 50K active users
- **SOM (Year 3):** Target 500K active users

### Differentiation Strategy

1. **Speed:** OCR-powered receipt scanning eliminates manual data entry (30 seconds vs. 5-10 minutes)
2. **Intelligence:** Transaction minimization algorithm reduces payment coordination complexity
3. **Mobile-First:** Built for real-time group scenarios (at the restaurant, on the trip)
4. **Recurring Splits:** Native support for roommate/shared housing expenses
5. **Frictionless Reminders:** SMS/push notifications ensure follow-through on payments

---

## USER PERSONAS

### Persona 1: Social Sarah (Primary)

**Demographics:**
- Age: 28
- Location: Urban (NYC, SF, LA, Chicago)
- Income: $65K-$95K
- Device: iPhone 12/13 Pro, uses mobile-first for all apps

**Behavior:**
- Eats out with friends 3-4 times/week
- Takes 2-3 group trips/year (Vegas, Miami, ski trips)
- Splits bills at restaurants, bars, and shared Airbnbs
- Frustrated by Venmo negotiations and forgotten payments
- Wants to spend time with friends, not calculating math

**Needs:**
- Quick, painless bill-splitting without pulling out a calculator
- Clear record of who owes whom (for accountability)
- Automatic reminders so friends don't forget to pay
- Works in real-time while at the restaurant

**Goals:**
- Reduce time spent on bill negotiations from 10 minutes to <1 minute
- Ensure all bills are settled within 24 hours
- Avoid awkward conversations about money

**Pain Points:**
- Manual item tracking at restaurants
- Calculating proportional tax and tip
- Following up with friends who "forget" to pay
- Disputes over whether items were split fairly

**Success Metric:** Sarah uses SplitPay for 80% of group dinners within 30 days of signup.

---

### Persona 2: Roommate Ryan (Secondary)

**Demographics:**
- Age: 26
- Location: Urban apartment with 2-3 roommates
- Income: $55K-$75K
- Device: Android phone, moderate app user

**Behavior:**
- Shares rent, utilities, groceries, and household expenses with roommates
- Typically one person pays the full bill, others reimburse
- Bills recur monthly (rent, internet, utilities)
- Frustration: tracking who paid what month-to-month, recurring reminders

**Needs:**
- Simple way to log recurring shared expenses
- Automatic calculation of who owes what each month
- Persistent reminders for monthly payments
- History of payments to settle disputes

**Goals:**
- Automate monthly expense tracking (rent, utilities, groceries)
- Reduce friction in roommate finances
- Ensure timely payment from all roommates

**Pain Points:**
- Manual tracking of recurring expenses
- Roommates "forgetting" to pay their share
- Disputes over how utilities are split
- No clear audit trail of who paid when

**Success Metric:** Ryan sets up 3+ recurring expense splits and maintains 100% payment compliance for 2 months.

---

### Persona 3: Trip Coordinator Tina (Secondary)

**Demographics:**
- Age: 31
- Location: Major metropolitan area
- Income: $75K-$110K
- Device: iPhone, power user who coordinates group activities

**Behavior:**
- Organizes 2-3 group trips/year (ski weekends, destination weddings, vacations)
- Often fronts expenses (flights, Airbnb, car rental, meals) and expects reimbursement
- Typically 6-12 people on trips, multiple shared expenses
- Wants clear accounting of who owes what before trip ends

**Needs:**
- Track multiple shared expenses across a trip (flights, accommodation, meals, activities)
- Clear visibility into who owes what at any point
- Easy way to send payment reminders to group
- Export capability for final accounting

**Goals:**
- Eliminate post-trip disputes about who owes what
- Settle all trip expenses before friends leave
- Have clear documentation for complex multi-person splits

**Pain Points:**
- Managing 10+ individual transactions across a trip
- Complex math when multiple people contribute to different expenses
- Forgotten payments after trip ends
- No clear record of what was paid by whom

**Success Metric:** Tina uses SplitPay for 100% of group trip expenses and settles all payments before trip concludes.

---

## PRODUCT VISION & GOALS

### Vision Statement

**SplitPay makes splitting expenses as natural as splitting a pizza.** By combining intelligent receipt scanning with frictionless payment coordination, we eliminate the awkwardness and complexity of shared finances among friends. We envision a world where group expenses are settled instantly, fairly, and without manual negotiation.

### Product Goals (12-Month Horizon)

1. **Goal 1: Reduce Bill-Splitting Friction**
   - Enable users to split bills in <1 minute (vs. current 5-15 minutes)
   - Achieve 90%+ accuracy in OCR line-item extraction
   - Support 95%+ of common receipt formats

2. **Goal 2: Maximize Payment Completion**
   - Ensure 85%+ of split expenses are fully settled within 7 days
   - Reduce number of payment reminders needed via automated SMS/push
   - Implement transaction minimization algorithm to reduce coordination complexity

3. **Goal 3: Build Trust Through Transparency**
   - Provide clear, auditable record of all transactions
   - Enable users to dispute/adjust splits within 48 hours
   - Support 100% of common expense types (meals, travel, rent, utilities)

4. **Goal 4: Enable Recurring Expense Management**
   - Support automated recurring splits for roommate scenarios
   - Reduce manual entry for recurring expenses by 90%
   - Enable users to set up monthly rent/utility splits in <2 minutes

### OKRs (Quarterly)

**Q1 (Launch):**
- O: Achieve product-market fit with core bill-splitting feature
  - KR1: 10K DAU within 30 days of launch
  - KR2: 4.5+ star rating on app stores (100+ reviews)
  - KR3: 60%+ of users complete first split successfully

- O: Establish payment completion as key differentiator
  - KR1: 80%+ of splits settled within 7 days (vs. industry average 50%)
  - KR2: <2 SMS reminders per split (vs. manual average 3-5)

**Q2:**
- O: Expand to recurring expense management
  - KR1: 5K active users on recurring splits
  - KR2: 90%+ monthly payment compliance for recurring splits
  - KR3: 20% of DAU using recurring splits feature

**Q3:**
- O: Achieve 100K DAU milestone
  - KR1: 100K DAU
  - KR2: 40% MoM growth
  - KR3: <5% churn rate

---

## SUCCESS METRICS & KPIs

### North Star Metric

**Active Splits per Week (ASW):** Number of unique bill splits created and settled per week across all users.

- **Rationale:** Directly measures core product value (bill-splitting) and user engagement. Tied to business growth.
- **Target:** 50K ASW by end of Year 1

### Primary KPIs

| **KPI** | **Definition** | **Target (Month 1)** | **Target (Month 6)** | **Measurement Method** |
|---|---|---|---|---|
| **Daily Active Users (DAU)** | Unique users who create or interact with a split | 2K | 25K | Analytics dashboard |
| **Weekly Active Users (WAU)** | Unique users active in a 7-day period | 5K | 60K | Analytics dashboard |
| **Monthly Active Users (MAU)** | Unique users active in a 30-day period | 8K | 80K | Analytics dashboard |
| **Splits Completed (Success Rate)** | % of splits that reach "settled" state | 70% | 85% | Database query |
| **Time to Settlement** | Avg. days from split creation to 100% payment | 5 days | 3 days | Database query |
| **OCR Accuracy** | % of line items extracted correctly from receipts | 85% | 92% | Manual review sampling |
| **Payment Reminder Efficiency** | Avg. reminders sent per split until settled | 2.5 | 1.5 | Analytics dashboard |
| **User Retention (Day 7)** | % of users active 7 days after first split | 40% | 50% | Cohort analysis |
| **User Retention (Day 30)** | % of users active 30 days after first split | 25% | 35% | Cohort analysis |
| **NPS (Net Promoter Score)** | User satisfaction metric | 35 | 50 | In-app survey |

### Secondary KPIs

| **KPI** | **Definition** | **Target** | **Measurement Method** |
|---|---|---|---|
| **Avg. Split Amount** | Average dollar amount per split | $35-$50 | Database query |
| **Recurring Splits Adoption** | % of users with 1+ recurring split | 10% (Month 1) → 25% (Month 6) | Database query |
| **Transaction Minimization Efficiency** | Avg. # of transactions required vs. theoretical minimum | 1.2x minimum | Algorithm analysis |
| **App Store Rating** | Average star rating across iOS/Android | 4.5+ | App store metrics |
| **Churn Rate (Monthly)** | % of MAU that don't return next month | <8% | Cohort analysis |
| **Crash Rate** | % of sessions ending in crash | <0.5% | Analytics dashboard |
| **OCR Rejection Rate** | % of receipt photos that fail OCR processing | <5% | Analytics dashboard |

### Business KPIs (Year 1+)

| **KPI** | **Definition** | **Target (Year 1)** |
|---|---|---|
| **Gross Volume** | Total dollar amount of splits | $5M |
| **Customer Acquisition Cost (CAC)** | Cost to acquire one active user | <$2 |
| **Lifetime Value (LTV)** | Avg. revenue per user over lifetime | $15-$25 |
| **LTV:CAC Ratio** | Ratio of lifetime value to acquisition cost | 8:1+ |

---

## CORE FEATURES & REQUIREMENTS

### Feature Hierarchy & Prioritization

Features are prioritized using a modified RICE framework (Reach, Impact, Confidence, Effort):
- **P0 (Must Have):** Features without which the product cannot launch. Core value delivery.
- **P1 (Should Have):** Features that significantly enhance value and should launch within 2-3 months post-MVP.
- **P2 (Nice to Have):** Features that improve experience but are not critical to core value. Can launch in Q2+.

---

## P0: MUST HAVE

### P0.1: Receipt Scanning & OCR Line Item Extraction

**User Story:**
As a Social Sarah, I want to photograph a receipt at a restaurant and have the app extract line items so I don't have to manually type each item.

**Problem This Solves:**
- Eliminates manual data entry (currently 5-10 minutes per receipt)
- Enables real-time bill splitting while still at the restaurant
- Reduces transcription errors

**Acceptance Criteria:**

1. **Receipt Photo Capture**
   - User can open camera from app and photograph a receipt
   - App accepts JPG/PNG formats, up to 10MB file size
   - User can retake photo or upload from device gallery
   - Cropping/rotation tools available for imperfect photos
   - **Success Metric:** 95%+ of receipt photos successfully processed (not rejected due to quality)

2. **OCR Line Item Extraction**
   - App extracts individual line items from receipt (e.g., "Caesar Salad $14.99", "Burger $16.50")
   - Extracted items displayed in editable list format
   - User can manually edit/correct extracted items (in case OCR misses or misinterprets)
   - App identifies and separates: item name, quantity, price
   - **Success Metric:** 90%+ of line items extracted accurately on first pass (verified via manual sampling)
   - **Success Metric:** 95%+ of receipts with <5 line items extracted with 100% accuracy

3. **Tax & Tip Extraction**
   - App extracts subtotal, tax amount, and tip (if present)
   - Displays these separately from line items
   - If tip not on receipt, user prompted to add tip amount or percentage
   - **Success Metric:** 85%+ of receipts with tax/tip extracted correctly

4. **Receipt Metadata Capture**
   - App captures/infers: receipt date, restaurant/vendor name, total amount
   - Date field editable by user (for receipts where date unclear)
   - Stored with split for audit trail
   - **Success Metric:** 100% of splits have complete metadata

5. **Supported Receipt Types**
   - Restaurant receipts (primary use case)
   - Retail/grocery receipts (for shared household purchases)
   - Bar/alcohol receipts
   - Ride-share receipts (Uber, Lyft)
   - Hotel/Airbnb invoices
   - [ASSUMPTION] Utility bills and rent invoices (for recurring splits) - may require different extraction logic
   - **Success Metric:** Support 95%+ of receipt formats commonly used by target personas

6. **Error Handling & Fallback**
   - If OCR fails, user option to manually enter items
   - Clear error messages if receipt quality too poor
   - Ability to retry with different photo angle/lighting
   - **Success Metric:** <5% of users abandon after OCR failure

---

### P0.2: Bill Splitting & Item Claiming

**User Story:**
As Social Sarah, I want my friends to claim the items they ordered so the app automatically calculates who owes whom.

**Problem This Solves:**
- Eliminates negotiation about who ordered what
- Creates clear, auditable record of each person's share
- Enables fair tax/tip allocation

**Acceptance Criteria:**

1. **Item Claiming Workflow**
   - After OCR extraction, user (bill payer) can invite friends to the split
   - Invited friends receive notification (SMS, push, or in-app)
   - Each friend can view list of unclaimed items
   - Friend taps/selects items they ordered
   - Friend can claim multiple items, fractional items (e.g., "half of the appetizer")
   - **Success Metric:** 95%+ of invited friends claim items within 30 minutes

2. **Item Ownership Assignment**
   - Each item assigned to one or more people (for shared items)
   - UI clearly shows item price and who claimed it
   - User can view split-by-person: [Person A: $45.50], [Person B: $32.25], etc.
   - **Success Metric:** 100% of items claimed or marked as "shared"

3. **Shared Items Handling**
   - For items shared by multiple people (e.g., appetizer, dessert), support equal or custom splits
   - Default to equal split; user can adjust percentages
   - Example: "Appetizer $20 split 3 ways" = $6.67 per person
   - **Success Metric:** Support up to 8 people sharing a single item

4. **Unclaimed Items**
   - If any items remain unclaimed after all friends respond, bill payer can:
     - Mark as "bill payer's item"
     - Split among remaining people
     - Delete item (if erroneous)
   - Clear UI indication of unclaimed items
   - **Success Metric:** 100% of splits have all items assigned before settlement calculation

5. **Item Editing & Correction**
   - User can edit item name, price, or quantity at any time before settlement
   - If item edited, recalculate all dependent shares automatically
   - Show audit trail of edits (for dispute resolution)
   - **Success Metric:** <2% of splits require post-settlement dispute due to item errors

6. **Partial Item Claiming**
   - Support user claiming "half" or "1/3" of an item (e.g., shared appetizer)
   - UI provides clear mechanism to specify fraction (dropdown, slider, or text input)
   - Validation prevents fractions totaling >100% per item
   - **Success Metric:** 100% of fractional claims sum to 100% per item

---

### P0.3: Tax & Tip Calculation & Allocation

**User Story:**
As Social Sarah, I want the app to fairly allocate tax and tip based on what each person ordered, so everyone pays their fair share.

**Problem This Solves:**
- Manual tax/tip calculation is error-prone and source of disputes
- Fair allocation (proportional to item cost) is complex to calculate manually
- Users expect tax/tip included in their "share" automatically

**Acceptance Criteria:**

1. **Proportional Tax Allocation**
   - App calculates tax as percentage of subtotal (e.g., 8.5%)
   - Tax allocated proportionally to each person's item subtotal
   - Example: If Sarah's items = $40 (50% of $80 subtotal), Sarah pays 50% of tax
   - **Success Metric:** Tax allocation accurate to $0.01 per person

2. **Proportional Tip Allocation**
   - App calculates tip as percentage of subtotal (e.g., 18%, 20%, 25%) OR as fixed amount
   - Tip allocated proportionally to each person's item subtotal (including tax)
   - Example: If Sarah's share (items + tax) = $43.40 (50% of $86.80 total), Sarah pays 50% of tip
   - **Success Metric:** Tip allocation accurate to $0.01 per person

3. **Tip Entry Options**
   - User can enter tip as:
     - Fixed dollar amount (e.g., "$15")
     - Percentage of subtotal (e.g., "20%")
     - Percentage of total including tax (e.g., "18% of total")
   - UI clearly shows calculated tip amount in each format
   - **Success Metric:** 100% of splits have tip specified before settlement

4. **Rounding & Precision**
   - All calculations rounded to nearest cent ($0.01)
   - Ensure total of all individual shares = receipt total (no rounding errors)
   - If rounding discrepancy occurs, allocate difference to largest share
   - **Success Metric:** 100% of splits reconcile to receipt total within $0.00

5. **Special Cases**
   - Support 0% tip (e.g., for takeout or delivery)
   - Support negative adjustments (e.g., discount applied)
   - Support multiple tax rates (e.g., some items taxed, others not - rare but possible)
   - **Success Metric:** Support 99%+ of receipt scenarios

6. **Tax Rate Inference**
   - App can infer tax rate from receipt (e.g., "Tax: $6.80 on $80.00 subtotal" = 8.5%)
   - User can override inferred tax rate if incorrect
   - App stores tax rate for future reference (location-based)
   - **Success Metric:** Auto-inferred tax rate correct in 95%+ of cases

---

### P0.4: Settlement Calculation & Transaction Minimization

**User Story:**
As Social Sarah, I want the app to tell me exactly who owes whom so I can settle the bill with minimum confusion and transactions.

**Problem This Solves:**
- Manual calculation of who owes whom is complex (especially with 4+ people)
- Without optimization, settling can require 5-10 individual transactions
- Transaction minimization dramatically reduces coordination friction

**Acceptance Criteria:**

1. **Debt Calculation**
   - App calculates each person's share (items + proportional tax + proportional tip)
   - Compares each person's share to amount they paid (if any)
   - Generates debt graph: [Person A owes Person B $12.50], [Person C owes Person A $8.00], etc.
   - **Success Metric:** Debt calculation accurate to $0.01 per person

2. **Transaction Minimization Algorithm**
   - App optimizes settlement to minimize number of transactions required
   - Example: Instead of [A→B, C→B, D→B, E→B] (4 transactions), app suggests [A→B, C+D+E→B] if possible
   - [ASSUMPTION] Algorithm uses greedy or optimal matching approach (details in technical design)
   - **Success Metric:** Average transactions per split = 1.2x theoretical minimum

3. **Settlement Display**
   - Show clear list of who owes whom and how much
   - Format: "[Person A] owes [Person B] $12.50"
   - Group transactions by payer (e.g., "You owe $20 to Sarah")
   - **Success Metric:** 100% of users understand settlement without confusion

4. **Payment Status Tracking**
   - Track which payments have been completed (marked as paid)
   - Show outstanding balances in real-time
   - Update settlement list as payments are marked complete
   - **Success Metric:** 100% of splits show accurate payment status

5. **Edge Cases**
   - Support scenarios where not everyone paid equally upfront
   - Support multiple people fronting portions of bill
   - Support scenarios where some people don't owe anything (e.g., birthday person)
   - **Success Metric:** Support 99%+ of common payment scenarios

6. **Settlement Verification**
   - Show total owed by all people = total owed to all people (verification)
   - Alert user if settlement doesn't balance (data entry error)
   - **Success Metric:** 100% of settlements balance to $0.00

---

### P0.5: Payment Reminders & Notification System

**User Story:**
As Social Sarah, I want my friends to get reminded to pay so I don't have to chase them down manually.

**Problem This Solves:**
- 35% of split expenses never settle due to coordination friction
- Manual reminders are inefficient and awkward
- Automated reminders ensure high payment completion rates

**Acceptance Criteria:**

1. **SMS Reminders**
   - User can enable SMS reminders for people who owe money
   - SMS sent to friend with: split amount, who they owe, payment instructions
   - Reminder sent immediately upon split creation (or when friend is added)
   - Reminder can include direct payment link (if integrated with payment provider)
   - User can customize reminder message (or use default)
   - **Success Metric:** SMS delivery rate >95%

2. **Reminder Scheduling**
   - Initial reminder sent immediately when split created
   - Follow-up reminder sent at T+24 hours if payment not received
   - Final reminder sent at T+72 hours if still outstanding
   - User can disable reminders or customize schedule
   - **Success Metric:** 85%+ of payments received within 7 days (vs. 50% without reminders)

3. **In-App Notifications**
   - Push notification when user is added to a split
   - Push notification when payment due (customizable timing)
   - Push notification when payment received
   - User can customize push notification frequency
   - **Success Metric:** 60%+ push notification open rate

4. **Payment Status Updates**
   - When payment marked as received, notify all parties
   - Show remaining outstanding balances
   - Congratulate when split fully settled
   - **Success Metric:** 100% of parties notified of payment status changes

5. **Reminder Opt-Out**
   - Users can opt out of SMS reminders (but not in-app notifications)
   - Users can mute specific split reminders
   - Opt-out preference stored in user settings
   - **Success Metric:** <10% opt-out rate on SMS reminders

6. **Payment Link in Reminders**
   - [ASSUMPTION] Reminders can include link to payment provider (Venmo, PayPal) if integrated
   - Link pre-populated with amount and recipient
   - User clicks link to complete payment outside app
   - **Success Metric:** 40%+ of payments initiated from reminder link

---

### P0.6: User Authentication & Account Management

**User Story:**
As a user, I want to create an account, log in securely, and manage my profile so my data is private and persistent.

**Problem This Solves:**
- Users need persistent identity across devices
- Payment/expense data is sensitive and requires secure authentication
- Users need ability to invite friends (requires phone number or username)

**Acceptance Criteria:**

1. **Account Creation**
   - User can sign up with email and password
   - Password must meet security requirements (8+ chars, mix of upper/lower/numbers)
   - User receives verification email; must verify before account active
   - User can sign up with phone number as alternative to email
   - **Success Metric:** <5% signup abandonment rate

2. **Login & Session Management**
   - User can log in with email/password or phone number/code
   - Session persists across app restarts (unless user logs out)
   - "Remember me" option for returning users
   - Automatic logout after 30 days of inactivity (security)
   - **Success Metric:** <2% login failure rate

3. **Profile Management**
   - User can edit: name, profile photo, phone number, email
   - User can view account settings and preferences
   - User can change password
   - **Success Metric:** 100% of users can update profile without error

4. **Phone Number Verification**
   - Phone number required for SMS reminders
   - Verification via SMS code (6-digit code sent to phone)
   - User can update phone number and re-verify
   - **Success Metric:** 95%+ of phone numbers successfully verified

5. **Data Privacy & Security**
   - All user data encrypted in transit (HTTPS)
   - User data encrypted at rest in database
   - User can request data export (GDPR compliance)
   - User can delete account and all associated data
   - **Success Metric:** 0 security breaches in Year 1

6. **Password Reset**
   - User can reset password via email link
   - Reset link expires after 1 hour
   - User must verify email before creating new password
   - **Success Metric:** 100% of password resets successful

---

### P0.7: Group/Split Management & Invite System

**User Story:**
As Social Sarah, I want to easily invite my friends to a split and see all my active splits in one place.

**Problem This Solves:**
- Users need frictionless way to invite friends to splits
- Users need visibility into all pending/active splits
- Users need ability to track who has and hasn't responded

**Acceptance Criteria:**

1. **Split Creation & Initialization**
   - User initiates split by uploading receipt or creating manual split
   - User selects/adds friends to split (by phone number, email, or username)
   - Friends added to split receive notification (SMS, push, or email)
   - User can add friends before or after OCR processing
   - **Success Metric:** 95%+ of splits successfully created with 2+ people

2. **Invite Mechanism**
   - User can invite friends by:
     - Phone number (sends SMS invite with split link)
     - Email (sends email invite with split link)
     - In-app search (if friends already have SplitPay accounts)
     - QR code (user generates QR code for friends to scan)
   - Invite includes split amount and basic details
   - Friend receives one-time link to join split
   - **Success Metric:** 90%+ of invites successfully delivered

3. **Split List View**
   - User sees dashboard showing all active splits
   - Splits sorted by date (most recent first) or status
   - Each split shows: amount, participants, status (pending/settled), date
   - User can filter by: status, person, date range
   - **Success Metric:** 100% of users can find any split in <10 seconds

4. **Split Detail View**
   - User can tap split to see full details: items, claims, settlement, payment status
   - Shows who has claimed items and who hasn't
   - Shows who has paid and who owes
   - Shows payment history (timestamps of payments)
   - **Success Metric:** 100% of users understand split details without confusion

5. **Split Status Lifecycle**
   - Draft: Split created, not yet shared
   - Pending: Awaiting item claims from friends
   - Settled: All items claimed, settlement calculated
   - Completed: All payments received
   - User can view splits in any status
   - **Success Metric:** 100% of splits progress through lifecycle correctly

6. **Friend Management**
   - User can view list of friends (people they've split bills with)
   - User can add friends to contacts/favorites
   - User can block/remove friends
   - User can see split history with each friend
   - **Success Metric:** 100% of users can manage their friend list

---

### P0.8: Mobile-First Responsive UI

**User Story:**
As Social Sarah, I want the app to work smoothly on my iPhone and be easy to use with one hand while at a restaurant.

**Problem This Solves:**
- Core use case (splitting bills at restaurant) requires mobile-first experience
- Poor mobile UX results in high abandonment
- Users expect native app performance and responsiveness

**Acceptance Criteria:**

1. **Mobile Optimization**
   - App optimized for screens 4.5" - 6.5" (primary range)
   - Touch targets minimum 48x48 pixels (accessibility)
   - One-handed operation possible for all primary flows
   - App loads in <2 seconds on 4G connection
   - **Success Metric:** 95%+ of users report good/excellent mobile experience

2. **Responsive Layout**
   - Layout adapts to portrait and landscape orientations
   - No horizontal scrolling required for primary content
   - Text readable without zooming
   - Buttons/inputs accessible without pinch-to-zoom
   - **Success Metric:** 100% of flows work in both orientations

3. **Navigation**
   - Bottom tab bar for primary navigation (home, splits, profile)
   - Intuitive back button behavior
   - No more than 3 taps to reach any feature
   - **Success Metric:** 100% of users navigate app without getting lost

4. **Performance**
   - App responds to user input within 200ms
   - Animations smooth (60fps)
   - No jank or stuttering during scrolling
   - Images optimized for mobile (compressed, lazy-loaded)
   - **Success Metric:** <100ms avg. response time to user input

5. **Accessibility**
   - Support for screen readers (VoiceOver, TalkBack)
   - High contrast mode support
   - Text sizing options (small, normal, large)
   - Color not only indicator of status
   - **Success Metric:** WCAG 2.1 AA compliance

6. **Offline Capability**
   - [ASSUMPTION] App can display cached data when offline
   - User notified when offline
   - Syncs when connection restored
   - **Success Metric:** 100% of cached data displays correctly offline

---

## P1: SHOULD HAVE

### P1.1: Recurring Splits for Shared Housing

**User Story:**
As Roommate Ryan, I want to set up a recurring monthly split for rent and utilities so I don't have to manually create a split each month.

**Problem This Solves:**
- Roommates have recurring shared expenses (rent, utilities, internet)
- Manual monthly entry is tedious and error-prone
- Recurring splits enable passive income tracking for shared housing

**Target Delivery:** Month 2 post-MVP

**Acceptance Criteria:**

1. **Recurring Split Setup**
   - User can create recurring split (daily, weekly, monthly, custom)
   - User specifies: amount, frequency, start date, end date (optional)
   - User selects participants and their share (equal or custom)
   - Example: "Rent $1,500/month, split equally among 3 people, starting Jan 1"
   - **Success Metric:** 100% of recurring splits created successfully

2. **Automatic Split Generation**
   - On specified date, app automatically creates split for all participants
   - Participants notified of new split (SMS/push)
   - Split marked as "auto-generated" for tracking
   - **Success Metric:** 100% of recurring splits generated on schedule

3. **Payment Tracking for Recurring Splits**
   - User can mark payment as received for recurring split
   - System tracks payment history across all recurrences
   - User can view: "Ryan paid $500 rent on Jan 5, Feb 3, Mar 5..."
   - **Success Metric:** 100% of recurring payments tracked accurately

4. **Recurring Split Management**
   - User can view list of active recurring splits
   - User can pause/resume recurring split
   - User can edit amount or participants (affects future recurrences only)
   - User can delete recurring split (stops future recurrences)
   - **Success Metric:** 100% of recurring split edits applied correctly

5. **Missed Payment Tracking**
   - System tracks if payment not received by due date
   - Escalated reminders for overdue recurring payments
   - User can see payment compliance history (% on-time payments)
   - **Success Metric:** 90%+ on-time payment rate for recurring splits

6. **Recurring Split History**
   - User can view all past recurrences of a split
   - User can drill into individual recurrence to see details
   - User can export recurring split history (CSV or PDF)
   - **Success Metric:** 100% of users can access recurring split history

---

### P1.2: Manual Split Entry (Non-Receipt)

**User Story:**
As Roommate Ryan, I want to manually enter a split (without a receipt) for expenses like utilities or shared groceries so I can track all shared expenses.

**Problem This Solves:**
- Not all expenses have receipts (e.g., utilities, rent, digital purchases)
- Recurring splits require manual entry as fallback
- Enables broader expense tracking beyond restaurants

**Target Delivery:** Month 2 post-MVP

**Acceptance Criteria:**

1. **Manual Split Creation**
   - User can create split without receipt
   - User enters: expense name, total amount, date, description (optional)
   - User selects participants and their share (equal or custom)
   - Example: "Internet bill $80, split equally between Ryan and Alex"
   - **Success Metric:** 100% of manual splits created successfully

2. **Expense Categorization**
   - User can categorize expense: meals, travel, housing, utilities, groceries, other
   - Category used for analytics and filtering
   - **Success Metric:** 100% of manual splits have category

3. **Item-Level Entry (Optional)**
   - User can optionally add line items to manual split (without OCR)
   - Example: "Groceries: milk $4, bread $3, eggs $5" = $12 total
   - Items can be claimed by participants
   - **Success Metric:** 50%+ of manual splits include item-level detail

4. **Manual Split List**
   - User can view all manual splits (separate from receipt-based splits or combined)
   - Filter by category, date, participant
   - **Success Metric:** 100% of users can find manual splits easily

5. **Manual Split Editing**
   - User can edit amount, participants, or items before settlement
   - After settlement, limited edits (can only adjust if all parties agree)
   - **Success Metric:** 100% of manual split edits applied correctly

---

### P1.3: Payment Integration & Direct Payment Links

**User Story:**
As Social Sarah, I want to click a link in the payment reminder and pay directly via Venmo/PayPal without leaving the app.

**Problem This Solves:**
- Currently, users receive reminder but must manually open Venmo and send payment
- Direct payment links reduce friction and increase completion rate
- Enables tracking of payments initiated from SplitPay

**Target Delivery:** Month 3 post-MVP

**Acceptance Criteria:**

1. **Venmo Integration** [ASSUMPTION - mentioned as possible payment provider]
   - User can link their Venmo account to SplitPay
   - Payment reminders include "Pay via Venmo" button
   - Button opens Venmo with amount and recipient pre-filled
   - After payment, Venmo notifies SplitPay (webhook or API)
   - SplitPay marks payment as received automatically
   - **Success Metric:** 50%+ of payments initiated via Venmo link

2. **PayPal Integration** [ASSUMPTION - mentioned as possible payment provider]
   - Similar to Venmo integration
   - Support for both Venmo and PayPal (user choice)
   - **Success Metric:** 30%+ of payments initiated via PayPal link

3. **Payment Confirmation**
   - When payment received via Venmo/PayPal, split automatically updated
   - All participants notified that payment received
   - Payment timestamp recorded for audit trail
   - **Success Metric:** 100% of payments confirmed accurately

4. **Manual Payment Marking**
   - If payment made outside app (cash, bank transfer), user can mark as paid manually
   - Requires confirmation from payee (for security)
   - Note field for payment method (e.g., "cash", "bank transfer")
   - **Success Metric:** 100% of manual payments marked correctly

---

### P1.4: Split Analytics & Expense Reports

**User Story:**
As Trip Coordinator Tina, I want to see reports on my spending patterns and shared expenses so I can understand my financial habits.

**Problem This Solves:**
- Users want visibility into spending trends (how much they spend on group dinners, trips, etc.)
- Analytics help users track budgets and identify patterns
- Reports useful for trip planning and roommate accountability

**Target Delivery:** Month 3 post-MVP

**Acceptance Criteria:**

1. **Personal Spending Dashboard**
   - User can view: total spent, total owed to others, total owed by others
   - Breakdown by category (meals, travel, housing, utilities, groceries)
   - Time period selector (this month, last 3 months, year-to-date, custom)
   - **Success Metric:** 100% of users can access spending dashboard

2. **Spending Trends**
   - Chart showing spending over time (line chart: $ spent per week/month)
   - Category breakdown (pie chart: % of spending by category)
   - Top spending categories
   - **Success Metric:** 100% of charts render correctly

3. **Friend Spending Summary**
   - User can view: total spent with each friend, total owed by/to each friend
   - List sorted by amount or name
   - User can drill into friend to see all splits with that person
   - **Success Metric:** 100% of friend summaries accurate

4. **Trip/Event Summary** [ASSUMPTION - optional feature]
   - User can tag splits as belonging to a specific trip/event
   - View total trip expenses, per-person breakdown
   - Export trip summary (for final accounting)
   - **Success Metric:** 50%+ of group trip splits tagged with event

5. **Expense Reports**
   - User can export spending report (PDF or CSV)
   - Report includes: all splits, amounts, participants, settlement status
   - Report can be filtered by date range, category, or person
   - **Success Metric:** 100% of report exports successful

6. **Recurring Split Compliance Report**
   - For recurring splits, show: payment history, on-time rate, total collected
   - Identify delinquent roommates (who frequently pay late)
   - **Success Metric:** 100% of compliance reports accurate

---

### P1.5: Dispute Resolution & Split Adjustment

**User Story:**
As Social Sarah, I want to be able to dispute a split amount or adjust it if someone made a mistake, so we can resolve disagreements fairly.

**Problem This Solves:**
- Disputes over split amounts are common (e.g., "I didn't order that", "That item was $15, not $18")
- Current apps don't have clear dispute resolution mechanism
- Enabling adjustments reduces friction and builds trust

**Target Delivery:** Month 3 post-MVP

**Acceptance Criteria:**

1. **Dispute Initiation**
   - User can dispute a split within 48 hours of creation
   - User specifies reason: "Wrong amount", "Didn't order this", "Item price incorrect", "Other"
   - User can provide explanation/evidence
   - Dispute notification sent to all participants
   - **Success Metric:** <5% of splits disputed

2. **Dispute Discussion**
   - All participants can view dispute and add comments
   - In-app messaging to discuss resolution
   - Timestamps recorded for all messages
   - **Success Metric:** 100% of disputes resolved within 24 hours

3. **Adjustment Options**
   - User can propose adjustment: change amount, remove item, adjust share
   - Other participants notified of proposed adjustment
   - Adjustment requires approval from affected parties (majority vote or unanimous)
   - **Success Metric:** 100% of adjustments applied correctly

4. **Adjustment Recalculation**
   - When adjustment approved, app recalculates settlement automatically
   - All participants notified of new amounts
   - Payment reminders updated with new amounts
   - **Success Metric:** 100% of recalculations accurate

5. **Dispute History**
   - User can view history of all disputes on a split
   - View original amount, proposed adjustments, final resolution
   - **Success Metric:** 100% of dispute history preserved

6. **Escalation**
   - If dispute unresolved after 48 hours, flag for app support team
   - Support team can mediate dispute
   - [ASSUMPTION] Support team can manually override settlement if needed
   - **Success Metric:** <1% of disputes escalated to support

---

### P1.6: Social Features & Group Chat

**User Story:**
As Social Sarah, I want to chat with my group about the split and coordinate payment so I don't have to use separate messaging apps.

**Problem This Solves:**
- Users currently use Venmo comments, Slack, or iMessage to discuss splits
- Native chat reduces friction and keeps conversation context in app
- Enables real-time coordination

**Target Delivery:** Month 4 post-MVP

**Acceptance Criteria:**

1. **Split-Level Chat**
   - Each split has associated chat thread
   - All participants can post messages
   - Messages include: text, timestamp, sender name
   - **Success Metric:** 30%+ of splits have 1+ message

2. **Chat Notifications**
   - User notified when new message posted to split chat
   - Push notification with message preview
   - User can disable chat notifications (but not payment reminders)
   - **Success Metric:** 50%+ push notification open rate

3. **Chat Moderation**
   - Bill payer can delete inappropriate messages
   - Bill payer can remove participant from split (and chat)
   - **Success Metric:** <0.1% of messages flagged as inappropriate

4. **Message History**
   - User can view full chat history for a split
   - Search chat by keyword
   - **Success Metric:** 100% of chat history preserved

---

## P2: NICE TO HAVE

### P2.1: Receipt Photo Gallery & History

**User Story:**
As Social Sarah, I want to see all my past receipts in one place so I can reference them or re-split if needed.

**Problem This Solves:**
- Users may need to revisit receipt details later
- Provides audit trail for disputes
- Enables re-splitting if circumstances change

**Target Delivery:** Q2 2025

**Acceptance Criteria:**

1. **Receipt Storage**
   - All receipt photos stored in user's account
   - User can view gallery of all receipts
   - Receipts organized by date (most recent first)
   - **Success Metric:** 100% of receipts stored and retrievable

2. **Receipt Search**
   - Search by date, restaurant name, or amount
   - Filter by date range
   - **Success Metric:** 100% of users can find any receipt in <20 seconds

3. **Receipt Details**
   - User can view original receipt photo
   - View extracted line items and OCR data
   - View associated split information
   - **Success Metric:** 100% of receipt details accessible

---

### P2.2: Expense Budget Tracking

**User Story:**
As Social Sarah, I want to set a budget for group dinners and get alerts when I'm approaching the limit.

**Problem This Solves:**
- Users want to control spending on group activities
- Alerts help users stay within budget
- Encourages responsible spending

**Target Delivery:** Q2 2025

**Acceptance Criteria:**

1. **Budget Setting**
   - User can set monthly budget for each category (meals, travel, housing, etc.)
   - Budget can be for total spending or per-person average
   - **Success Metric:** 100% of budgets set successfully

2. **Budget Tracking**
   - Dashboard shows spending vs. budget for each category
   - Visual progress bar (e.g., "You've spent $250 of $500 budget for meals")
   - **Success Metric:** 100% of budgets tracked accurately

3. **Budget Alerts**
   - Alert when spending reaches 75% of budget
   - Alert when spending exceeds budget
   - User can customize alert thresholds
   - **Success Metric:** 100% of alerts delivered

---

### P2.3: Group Expense Dashboard

**User Story:**
As Trip Coordinator Tina, I want a shared dashboard showing all trip expenses so the whole group can see the current status.

**Problem This Solves:**
- Group visibility into trip expenses reduces disputes
- Shared dashboard enables transparency
- Useful for group accountability

**Target Delivery:** Q3 2025

**Acceptance Criteria:**

1. **Group Dashboard**
   - Bill payer can enable shared dashboard for a split
   - All participants can view: total expenses, per-person breakdown, payment status
   - Dashboard shows real-time updates as payments received
   - **Success Metric:** 100% of group dashboards display correctly

2. **Dashboard Sharing**
   - Bill payer can generate link to share dashboard
   - Link can be shared via email, SMS, or social media
   - Shared dashboard read-only (no editing by non-participants)
   - **Success Metric:** 100% of shared links work correctly

---

### P2.4: Expense Categorization & Tagging

**User Story:**
As Social Sarah, I want to tag splits with custom categories (e.g., "Vegas trip", "Friday night squad") so I can filter and analyze expenses by group.

**Problem This Solves:**
- Users want to organize splits by context (trip, friend group, etc.)
- Enables better analytics and spending insights
- Useful for recurring groups (same friends, same activity)

**Target Delivery:** Q3 2025

**Acceptance Criteria:**

1. **Custom Tags**
   - User can create custom tags (e.g., "Vegas 2024", "Friday dinner squad")
   - User can apply multiple tags to a split
   - **Success Metric:** 100% of custom tags created successfully

2. **Tag Management**
   - User can view all tags and edit/delete them
   - User can rename tag (updates all splits)
   - **Success Metric:** 100% of tag management operations work correctly

3. **Tag-Based Filtering**
   - User can filter splits by tag
   - View analytics by tag (total spending, frequency, participants)
   - **Success Metric:** 100% of tag filters work correctly

---

### P2.5: Receipt Sharing & Collaboration

**User Story:**
As Social Sarah, I want to share a receipt with my friends before finalizing the split so they can verify the items and prices.

**Problem This Solves:**
- Reduces disputes by enabling pre-split review
- Builds trust and transparency
- Useful for large or complex receipts

**Target Delivery:** Q3 2025

**Acceptance Criteria:**

1. **Receipt Preview Sharing**
   - User can share receipt photo with participants before item claiming
   - Participants can view receipt photo and OCR'd items
   - Participants can provide feedback/corrections before finalizing
   - **Success Metric:** 100% of receipt shares successful

---

### P2.6: Loyalty Program & Rewards Integration

**User Story:**
As Social Sarah, I want to earn points or rewards when I use SplitPay, so I'm incentivized to use the app.

**Problem This Solves:**
- Gamification increases engagement and retention
- Rewards program differentiates from competitors
- Enables monetization (users pay for premium rewards)

**Target Delivery:** Q3 2025+

**Acceptance Criteria:**

1. **Points System**
   - User earns points for each split (e.g., 1 point per $10 split)
   - Points accumulate in user account
   - **Success Metric:** 100% of points calculated correctly

2. **Rewards Redemption**
   - User can redeem points for: discounts on premium features, gift cards, donations to charity
   - Redemption options updated regularly
   - **Success Metric:** 50%+ of users redeem points

---

### P2.7: Advanced Receipt Features (Multi-Receipt Splits)

**User Story:**
As Trip Coordinator Tina, I want to combine multiple receipts from a group trip into one split so I can see total trip expenses.

**Problem This Solves:**
- Trips often involve multiple receipts (meals, activities, accommodation)
- Combining receipts enables holistic trip accounting
- Useful for final trip settlement

**Target Delivery:** Q3 2025+

**Acceptance Criteria:**

1. **Multi-Receipt Splits**
   - User can create split with multiple receipts
   - Each receipt processed independently (OCR)
   - Items from all receipts combined in single split
   - **Success Metric:** 100% of multi-receipt splits created successfully

2. **Receipt Grouping**
   - User can organize receipts by type (meals, activities, etc.)
   - View subtotals by receipt or by category
   - **Success Metric:** 100% of receipt grouping displays correctly

---

### P2.8: API & Third-Party Integration

**User Story:**
As a developer, I want to integrate SplitPay into my own app or service so I can offer bill-splitting to my users.

**Problem This Solves:**
- Enables partnerships and distribution channels
- Allows third-party developers to build on SplitPay
- Increases market reach and network effects

**Target Delivery:** Q4 2025+

**Acceptance Criteria:**

1. **Public API**
   - Documented REST API for creating splits, tracking payments, etc.
   - Authentication via API keys
   - Rate limiting and usage monitoring
   - **Success Metric:** 100% of API endpoints working correctly

2. **Webhook Support**
   - Third-party services can subscribe to split events (created, settled, disputed)
   - Webhooks include relevant split data
   - **Success Metric:** 100% of webhooks delivered

---

## USER JOURNEYS

### Journey 1: Social Sarah - Group Dinner Split

**Scenario:** Sarah takes 5 friends to dinner. Total bill is $187.50. Sarah paid with her credit card.

**Steps:**

1. **Initiate Split**
   - Sarah opens SplitPay app
   - Taps "New Split" button
   - Selects "Scan Receipt"

2. **Capture Receipt**
   - Sarah photographs the receipt
   - App processes OCR, extracts 12 line items, subtotal $150, tax $12.75, tip $24.75
   - Sarah reviews extracted items; all correct

3. **Invite Friends**
   - Sarah taps "Add People"
   - Selects 5 friends from contacts (all have SplitPay installed)
   - Friends receive SMS: "Sarah added you to a split: $187.50 at Restaurant X"

4. **Friends Claim Items**
   - Friend 1 opens notification, views split, claims: Caesar Salad ($14), Burger ($18)
   - Friend 2 claims: Pasta ($16), shared Appetizer ($20 / 3 people)
   - Friend 3 claims: Steak ($28), shared Appetizer ($20 / 3 people)
   - Friend 4 claims: Fish ($22), shared Appetizer ($20 / 3 people), Dessert ($12 / 2 people)
   - Friend 5 claims: Burger ($16), Dessert ($12 / 2 people)
   - Sarah (bill payer) claims: Drinks ($4 / 5 people)

5. **Settlement Calculation**
   - App calculates each person's share (items + proportional tax + proportional tip)
   - Friend 1: $14 + $18 + tax/tip = $35.20 owes
   - Friend 2: $16 + ($20/3) + tax/tip = $26.80 owes
   - Friend 3: $28 + ($20/3) + tax/tip = $36.50 owes
   - Friend 4: $22 + ($20/3) + $12/2 + tax/tip = $39.10 owes
   - Friend 5: $16 + ($12/2) + tax/tip = $20.80 owes
   - Sarah (payer): Gets paid by all 5 friends

6. **Payment Reminders**
   - App sends SMS to each friend: "You owe Sarah $X for dinner at Restaurant X. Pay here: [link]"
   - Friends click link, opens Venmo with amount pre-filled
   - Friend 1 pays Sarah $35.20 via Venmo
   - Friends 2-5 pay within 24 hours
   - Sarah receives notifications as each payment arrives

7. **Split Completion**
   - Once all 5 payments received, split marked as "Completed"
   - Sarah receives notification: "All payments received! Dinner split complete."
   - All friends receive notification: "Split settled"

**Success Metrics:**
- Time from receipt scan to settlement: <2 minutes
- All 5 friends claim items within 30 minutes
- All 5 payments received within 24 hours
- Sarah satisfaction: 5/5 stars

---

### Journey 2: Roommate Ryan - Monthly Rent Split

**Scenario:** Ryan shares a $1,500/month apartment with 2 roommates. He pays the landlord and expects roommates to reimburse their share ($500 each).

**Steps:**

1. **Set Up Recurring Split**
   - Ryan opens SplitPay
   - Taps "New Split" → "Recurring"
   - Enters: Amount $1,500, Frequency "Monthly", Start date "Jan 1"
   - Selects roommates: Alex, Jordan
   - Sets split: $500 each (equal)
   - Taps "Create Recurring Split"

2. **First Month (Jan)**
   - On Jan 1, app automatically creates split: "Rent - January"
   - Alex and Jordan receive SMS: "Your January rent is due: $500. Pay here: [link]"
   - Alex clicks link, pays $500 via Venmo on Jan 2
   - Jordan pays $500 via bank transfer on Jan 5 (marks as paid manually)
   - Ryan receives notifications as payments arrive
   - Split marked as "Completed" on Jan 5

3. **Second Month (Feb)**
   - On Feb 1, app automatically creates split: "Rent - February"
   - Alex and Jordan receive reminders
   - Alex pays on Feb 3, Jordan on Feb 2
   - Split marked as "Completed" on Feb 3

4. **Third Month (Mar) - Late Payment**
   - On Mar 1, app creates split: "Rent - March"
   - Alex pays on Mar 2
   - Jordan doesn't pay by Mar 7 (7 days late)
   - App sends escalated reminder on Mar 8: "Your March rent is overdue. Please pay ASAP."
   - Jordan pays on Mar 10
   - Split marked as "Completed"

5. **Compliance Review**
   - Ryan opens SplitPay analytics
   - Views "Recurring Splits" dashboard
   - Sees rent payment history: Alex 3/3 on-time, Jordan 2/3 on-time (1 late)
   - Compliance report shows: 83% on-time payment rate

**Success Metrics:**
- Recurring split set up in <2 minutes
- Automatic splits generated on schedule (100% success rate)
- Payment reminders sent automatically (no manual follow-up)
- 80%+ on-time payment rate

---

### Journey 3: Trip Coordinator Tina - Vegas Trip Accounting

**Scenario:** Tina organized a Vegas trip with 8 friends. Multiple expenses: flights, Airbnb, meals, activities. Total: ~$4,000. Tina fronted most expenses.

**Steps:**

1. **Create Trip Event**
   - Tina opens SplitPay
   - Creates new split for "Vegas Trip - Flights"
   - Uploads receipt for flights: $2,400 total (8 people)
   - App extracts total, Tina manually enters passenger names
   - Tina selects all 8 friends
   - App calculates: each person owes $300 (equal split)
   - Sends reminders to all 8 friends

2. **Add Accommodation Expense**
   - Tina creates split for "Vegas Trip - Airbnb"
   - Uploads Airbnb invoice: $1,200 (3 nights, 8 people)
   - Each person owes $150
   - Sends reminders

3. **Track Meals & Activities**
   - Over 3 days, Tina creates 6 splits for group meals/activities
   - Day 1: Dinner $240, each person owes $30
   - Day 2: Lunch $180, each person owes $22.50
   - Day 2: Show tickets $400, each person owes $50
   - Day 3: Brunch $160, each person owes $20
   - Day 3: Nightclub $300, each person owes $37.50

4. **Group Dashboard**
   - Tina enables shared dashboard for trip
   - Shares link with all 8 friends
   - Dashboard shows: total trip cost $4,480, per-person share $560
   - Real-time payment status: shows who has paid, who owes

5. **Payment Coordination**
   - Friends start paying as trip progresses
   - By end of Day 3, 6 of 8 friends have paid in full
   - 2 friends pay after returning home
   - All payments received within 48 hours post-trip

6. **Trip Accounting**
   - Tina exports trip summary: detailed breakdown of all expenses
   - Total collected: $4,480
   - Amount paid out by Tina: $4,480
   - Net: $0 (perfectly settled)

**Success Metrics:**
- 10 splits created for trip (flights, accommodation, 6 meals/activities)
- All 8 friends claim expenses correctly
- 75% of payments received before trip ends
- 100% of payments received within 48 hours post-trip
- Tina satisfaction: 5/5 stars (no post-trip disputes)

---

## OUT OF SCOPE

The following features and capabilities are explicitly OUT OF SCOPE for MVP and Year 1:

### 1. **Payment Processing & Direct Payments**
- SplitPay will NOT process payments directly
- No bank account integration or ACH transfers
- No credit card processing or payment gateway
- **Rationale:** Payment processing requires significant regulatory compliance (PCI-DSS, money transmitter licenses). Initial MVP integrates with existing payment providers (Venmo, PayPal) via links/webhooks, not direct processing.
- **Future:** Payment processing may be added in Year 2+ as separate feature

### 2. **International Support**
- MVP supports US only (USD currency, US phone numbers, US tax rates)
- No multi-currency support
- No international payment methods (SEPA, WeChat Pay, etc.)
- **Rationale:** International expansion adds complexity (tax laws, payment methods, regulations vary by country). Focus on US market first.
- **Future:** International expansion possible in Year 2+

### 3. **Business/Corporate Expense Management**
- SplitPay targets personal/social expense splitting, not business expense management
- No integration with accounting software (QuickBooks, Xero, etc.)
- No expense categorization for tax deductions
- No audit trail for IRS compliance
- **Rationale:** Business expenses have different requirements (audit trails, approval workflows, tax tracking). Out of scope for personal expense app.

### 4. **Advanced Receipt Scanning Features**
- No support for handwritten receipts
- No support for receipts in languages other than English
- No automatic vendor/restaurant name lookup or validation
- No nutrition/allergen information extraction
- **Rationale:** These features add complexity and are not essential for MVP. Can be added later.

### 5. **Real-Time Collaboration During Receipt Entry**
- No live collaborative editing of receipt items (multiple people editing simultaneously)
- No video/audio chat integrated into app
- **Rationale:** Out of scope for MVP. Focus on asynchronous item claiming.

### 6. **Itemized Tax/Tip Calculation by Item**
- App allocates tax/tip proportionally by item cost (not by item type)
- No support for items with different tax rates (e.g., some items taxed, others not)
- **Rationale:** Most receipts don't itemize tax by item. Proportional allocation is sufficient for 99%+ of use cases.

### 7. **Cryptocurrency or Alternative Payment Methods**
- No Bitcoin, Ethereum, or other cryptocurrency support
- No Apple Pay, Google Pay, or other digital wallet integration
- **Rationale:** Not essential for MVP. Can be added later if demand exists.

### 8. **Expense Forecasting or Budgeting Automation**
- No AI-powered spending predictions
- No automatic budget