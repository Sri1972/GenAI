# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## Tip Calculator Web App

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Owner:** Product Management  
**Status:** Ready for Engineering Review

---

## TABLE OF CONTENTS
1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [User Personas](#user-personas)
4. [Goals & Success Metrics](#goals--success-metrics)
5. [Feature Requirements](#feature-requirements)
6. [Out of Scope](#out-of-scope)
7. [Business Rules & Constraints](#business-rules--constraints)
8. [Risks & Mitigations](#risks--mitigations)
9. [Open Questions](#open-questions)
10. [Appendix: Acceptance Criteria](#appendix-acceptance-criteria)

---

## EXECUTIVE SUMMARY

**Product Name:** Tip Calculator  
**Product Type:** Web Application (MVP)  
**Target Users:** Diners, service industry workers, and anyone calculating gratuity in real-time  
**Core Value Proposition:** Instantly calculate tip amounts and total bill with a simple, distraction-free interface that handles multiple currencies and common tip scenarios.

**Why Now?**
- Existing tip calculators are cluttered with ads, require app downloads, or lack multi-currency support
- Mobile-first web app removes friction (no installation, works on any device)
- Recurring use case (every dining occasion) creates habit-forming potential

**Success Definition:** Users can calculate a tip and see the total in <5 seconds with zero errors, across multiple currencies and tip scenarios.

---

## PROBLEM STATEMENT

### The Core Problem
When dining out or receiving service, users need to quickly calculate the appropriate tip amount and total bill. Current solutions suffer from:

1. **Friction**: Require app downloads, have slow load times, or are buried in phone calculators
2. **Complexity**: Cluttered UIs with ads, unnecessary features, or confusing layouts
3. **Localization Gaps**: Don't support non-USD currencies or use incorrect formatting (e.g., showing $ for GBP)
4. **Precision Issues**: Rounding errors or unclear rounding behavior that creates discrepancies between displayed and actual amounts
5. **Inflexibility**: Don't support common scenarios like preset tip percentages or bill splitting

### User Pain Points
- **Scenario 1 (Diner):** At a restaurant, needs to calculate 18% tip on £47.50 bill in under 30 seconds; current phone calculator requires manual math
- **Scenario 2 (Service Worker):** Wants to quickly verify tip calculations from customers; needs confidence in accuracy
- **Scenario 3 (Group Dining):** Multiple people splitting a bill need to know individual per-person cost including tip; manual splitting is error-prone
- **Scenario 4 (International Travel):** Visiting UK, unfamiliar with tipping norms; needs quick reference for common tip percentages in local currency

### Market Opportunity
- Tip calculators are among the top 100 most-downloaded utility apps globally
- Multi-currency support is a key differentiator; most free calculators lack this
- Web-based solution avoids app store friction and reaches users immediately

---

## USER PERSONAS

### Persona 1: **Sarah, the Frequent Diner**
- **Age/Background:** 32, urban professional, dines out 2-3x per week
- **Goals:** 
  - Calculate tips quickly without pulling out phone calculator
  - Ensure she tips fairly and consistently
  - Impress dates/colleagues by handling the bill smoothly
- **Pain Points:**
  - Phone calculator requires multiple steps; easy to make mental math errors
  - Unsure if 15%, 18%, or 20% is appropriate in different contexts
  - Traveling internationally; unfamiliar with local tipping norms and currency
- **Behavior:**
  - Uses mobile phone at table; needs fast, one-handed interface
  - Prefers preset options over manual entry when possible
  - Values accuracy over features
- **Success Metric:** Completes calculation in <10 seconds, 100% accuracy

### Persona 2: **Marcus, the Service Industry Worker**
- **Age/Background:** 28, bartender/server, handles cash tips daily
- **Goals:**
  - Quickly verify customer tip calculations to catch errors
  - Calculate expected earnings for shift planning
  - Educate customers on fair tipping norms
- **Pain Points:**
  - Customers sometimes undercalculate; needs fast verification tool
  - Works in multiple venues with different currencies (travels for seasonal work)
  - Needs to explain tipping to international tourists
- **Behavior:**
  - Uses tool multiple times per shift (5-10+ times)
  - Needs reliability and speed; no tolerance for errors
  - May share tool with colleagues or customers
- **Success Metric:** Verifies 10 calculations per shift with 100% accuracy; tool loads in <2 seconds

### Persona 3: **Priya, the Budget-Conscious Traveler**
- **Age/Background:** 26, student/backpacker, traveling through Europe for 3 months
- **Goals:**
  - Understand local tipping customs quickly
  - Calculate tips in unfamiliar currencies without confusion
  - Avoid overpaying or underpaying due to currency misunderstanding
- **Pain Points:**
  - Tipping norms vary by country; doesn't know if 10% is standard or offensive
  - Currency conversion adds cognitive load
  - Wants a tool that works offline or with minimal data usage
- **Behavior:**
  - Uses tool 1-2x per day while traveling
  - May not have reliable internet; needs fast load times
  - Prefers visual clarity (currency symbols, clear formatting)
- **Success Metric:** Calculates tip in correct local currency with confidence; no second-guessing

---

## GOALS & SUCCESS METRICS

### Primary Goals

**Goal 1: Enable Fast, Accurate Tip Calculations**
- **Metric 1a:** Time-to-Calculate: Users complete a tip calculation in ≤5 seconds (measured from page load to result display)
- **Metric 1b:** Calculation Accuracy: 100% of calculations match expected mathematical result (no rounding errors or display bugs)
- **Metric 1c:** User Confidence: ≥90% of users report "high confidence" in calculation accuracy (post-use survey)

**Goal 2: Support Multi-Currency Transactions**
- **Metric 2a:** Currency Coverage: Support ≥10 major currencies (USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD)
- **Metric 2b:** Correct Formatting: 100% of displayed amounts use correct currency symbol and decimal places per locale
- **Metric 2c:** Currency Adoption: ≥30% of users select non-USD currency in first session

**Goal 3: Reduce Friction & Increase Adoption**
- **Metric 3a:** Page Load Time: ≤2 seconds on 4G mobile connection (measured via Lighthouse)
- **Metric 3b:** First-Time User Completion: ≥80% of first-time users complete at least one calculation without help
- **Metric 3c:** Return Usage: ≥40% of users return within 7 days for a second calculation

**Goal 4: Support Common Tipping Scenarios**
- **Metric 4a:** Feature Adoption: ≥50% of users interact with preset tip percentages in first session
- **Metric 4b:** Bill Splitting Adoption: ≥25% of users attempt bill splitting (if included in MVP)
- **Metric 4c:** Error Recovery: ≥95% of users who encounter an input error successfully correct and recalculate

### Secondary Goals
- **Goal 5:** Build habit-forming behavior (users bookmark or return regularly)
  - **Metric 5a:** Bookmarks: ≥20% of users bookmark the app within first session
  - **Metric 5b:** Repeat Usage: ≥50% of users return within 30 days

---

## FEATURE REQUIREMENTS

### P0 Features (Must-Have for MVP Launch)
**These features are non-negotiable. We do not ship without them.**

#### P0.1: Basic Tip Calculation
**Description:** Users enter a bill amount and tip percentage; the app displays the tip amount and total bill.

**User Story:**
> As a diner, I want to enter a bill amount and tip percentage so that I can instantly see the tip amount and total bill without manual calculation.

**Acceptance Criteria:**
- [ ] User can input bill amount (numeric, up to 2 decimal places)
- [ ] User can input tip percentage (numeric, 0-100%, up to 1 decimal place)
- [ ] App displays tip amount (calculated value, formatted to 2 decimal places)
- [ ] App displays total bill (bill + tip, formatted to 2 decimal places)
- [ ] Results update in real-time as user types (no "Calculate" button required)
- [ ] All calculations are mathematically accurate with no rounding errors
- [ ] Results remain visible and don't disappear after calculation

**Rationale:** This is the core value proposition. Without it, the product has no purpose.

---

#### P0.2: Multi-Currency Support
**Description:** Users can select a currency, and all amounts display with correct formatting (symbol, decimal places, thousands separator).

**User Story:**
> As an international traveler, I want to select my local currency so that I see amounts in familiar format and avoid confusion.

**Acceptance Criteria:**
- [ ] User can select from ≥10 major currencies (USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD)
- [ ] Currency selection persists across sessions (stored locally)
- [ ] All displayed amounts use correct currency symbol (e.g., £ for GBP, € for EUR, ¥ for JPY)
- [ ] Decimal places follow locale rules (USD/EUR = 2 decimals, JPY = 0 decimals)
- [ ] Thousands separators display correctly (e.g., 1,000.00 for USD, 1.000,00 for EUR)
- [ ] Currency selector is visible and easy to change
- [ ] Changing currency recalculates and reformats all displayed amounts

**Rationale:** Multi-currency is a key differentiator vs. existing calculators. Incorrect formatting erodes user trust.

---

#### P0.3: Input Validation & Error Handling
**Description:** App validates user inputs and provides clear error messages for invalid entries.

**User Story:**
> As a user, I want clear feedback when I enter invalid data so that I can correct mistakes quickly.

**Acceptance Criteria:**
- [ ] Bill amount: Accepts 0.01 to 999,999.99; rejects negative numbers, letters, empty fields
- [ ] Tip percentage: Accepts 0 to 100%; rejects negative numbers, >100%, empty fields
- [ ] Invalid input displays inline error message (e.g., "Please enter a valid amount")
- [ ] Error message clears when user corrects input
- [ ] Calculate button (if present) is disabled until both fields are valid
- [ ] Error messages are clear, non-technical, and actionable
- [ ] Edge case: $0 bill with 0% tip is valid (displays $0 total)

**Rationale:** Poor error handling frustrates users and creates distrust. Clear validation prevents calculation errors.

---

#### P0.4: Preset Tip Percentages
**Description:** Users can quickly select common tip percentages (e.g., 15%, 18%, 20%) instead of typing manually.

**User Story:**
> As a diner in a hurry, I want to tap a preset tip percentage so that I don't have to type and can calculate instantly.

**Acceptance Criteria:**
- [ ] App displays ≥3 preset tip percentage buttons (15%, 18%, 20% recommended)
- [ ] Tapping a preset button auto-fills the tip percentage field
- [ ] User can still manually override the percentage after selecting a preset
- [ ] Presets are clearly labeled and easy to tap on mobile
- [ ] Presets are context-aware (e.g., show 10%, 15%, 20% for restaurants; 15%, 18%, 20% for bars)
- [ ] Results update immediately after preset selection

**Rationale:** Presets reduce friction and support the "fast calculation" goal. Most users tip within a narrow range.

---

#### P0.5: Responsive Mobile Design
**Description:** App is fully functional and optimized for mobile devices (phones and tablets).

**User Story:**
> As a mobile user, I want the app to work smoothly on my phone so that I can calculate tips at the table without frustration.

**Acceptance Criteria:**
- [ ] App is fully functional on iOS Safari and Android Chrome
- [ ] All inputs and buttons are easily tappable (minimum 44x44px touch targets)
- [ ] Layout adapts to portrait and landscape orientations
- [ ] Text is readable without zooming (minimum 16px font size)
- [ ] No horizontal scrolling required
- [ ] Page load time ≤2 seconds on 4G connection
- [ ] All features accessible without pinch-to-zoom

**Rationale:** Primary use case is at the table on mobile. Poor mobile experience defeats the purpose.

---

### P1 Features (High Priority, Target for MVP+1)
**These features significantly enhance value but are not blockers for launch.**

#### P1.1: Bill Splitting (Equal Split)
**Description:** Users can split a bill equally among multiple people and see per-person cost including tip.

**User Story:**
> As someone in a group, I want to split the bill equally among N people so that I know exactly what each person owes.

**Acceptance Criteria:**
- [ ] User can input number of people (2-20)
- [ ] App calculates per-person share of bill (before tip)
- [ ] App calculates per-person share of tip
- [ ] App displays per-person total (bill share + tip share)
- [ ] Rounding rule is clearly documented (e.g., "Tip rounded to nearest cent, then split equally")
- [ ] Example: $100 bill, 20% tip, 3 people = $40.00 per person (or documented rounding behavior)
- [ ] User can toggle between "total view" and "per-person view"

**Rationale:** Common scenario (group dining). Reduces manual math and errors. Increases perceived value.

---

#### P1.2: Custom Tip Percentages
**Description:** Users can add custom preset buttons for tip percentages they use frequently.

**User Story:**
> As a service worker, I want to save my preferred tip percentages so that I can access them faster on repeat visits.

**Acceptance Criteria:**
- [ ] User can add up to 5 custom preset percentages
- [ ] Custom presets are stored locally and persist across sessions
- [ ] Custom presets appear alongside default presets
- [ ] User can delete custom presets
- [ ] Custom presets are clearly labeled as "custom" or user-defined
- [ ] Invalid percentages (negative, >100%) are rejected

**Rationale:** Supports power users (service workers, frequent diners). Increases repeat usage and habit formation.

---

#### P1.3: Calculation History
**Description:** App displays a log of recent calculations so users can reference past tips or verify accuracy.

**User Story:**
> As a service worker, I want to see my recent calculations so that I can verify tips from earlier in my shift.

**Acceptance Criteria:**
- [ ] App stores last 10 calculations (bill amount, tip %, tip amount, total, currency, timestamp)
- [ ] History is displayed in reverse chronological order (most recent first)
- [ ] User can tap a history entry to reload that calculation
- [ ] User can clear history with one action
- [ ] History persists across sessions (stored locally)
- [ ] History is optional; users can disable it if desired
- [ ] Each history entry shows: bill, tip %, tip amount, total, currency, time

**Rationale:** Supports verification use case. Builds confidence in accuracy. Encourages repeat usage.

---

#### P1.4: Tip Percentage Slider
**Description:** Users can adjust tip percentage using a slider for fine-grained control.

**User Story:**
> As a user, I want to adjust the tip percentage smoothly so that I can find the exact percentage I want without typing.

**Acceptance Criteria:**
- [ ] Slider ranges from 0% to 100%
- [ ] Slider updates tip amount in real-time as user drags
- [ ] Slider displays current percentage value
- [ ] User can still type percentage manually (slider and input field are in sync)
- [ ] Slider is easy to use on mobile (large touch target)
- [ ] Slider increments by 1% (or smaller if needed for precision)

**Rationale:** Improves UX for users who want to experiment with different percentages. Reduces typing.

---

### P2 Features (Nice-to-Have, Future Consideration)
**These features add polish but are not required for MVP or MVP+1.**

#### P2.1: Tip Percentage Recommendations by Region
**Description:** App suggests appropriate tip percentages based on selected currency or region.

**User Story:**
> As a traveler, I want to know what's considered a fair tip in this country so that I don't accidentally offend or overpay.

**Acceptance Criteria:**
- [ ] When user selects a currency, app displays recommended tip range (e.g., "Typical: 15-20%")
- [ ] Recommendations are based on regional norms (e.g., 10-15% for UK, 15-20% for USA)
- [ ] Recommendations are displayed as informational text, not enforced
- [ ] User can dismiss or ignore recommendations
- [ ] Recommendations are accurate and culturally appropriate

**Rationale:** Supports international travelers. Adds educational value. Differentiates from competitors.

---

#### P2.2: Dark Mode
**Description:** App supports dark mode for low-light environments (e.g., dimly lit restaurants).

**User Story:**
> As a user in a dark restaurant, I want dark mode so that I don't blind myself with a bright screen.

**Acceptance Criteria:**
- [ ] Dark mode is available as a toggle in settings
- [ ] Dark mode preference persists across sessions
- [ ] All text is readable in dark mode (sufficient contrast)
- [ ] Dark mode respects system preference (if available)
- [ ] All features work identically in dark and light modes

**Rationale:** Improves usability in real-world dining scenarios. Low effort, high perceived value.

---

#### P2.3: Offline Functionality
**Description:** App works without internet connection (all features cached locally).

**User Story:**
> As a traveler with spotty internet, I want the app to work offline so that I can calculate tips anywhere.

**Acceptance Criteria:**
- [ ] App loads and functions without internet connection
- [ ] All features (calculation, history, presets) work offline
- [ ] App syncs when connection is restored (if applicable)
- [ ] User is informed when offline (optional status indicator)

**Rationale:** Supports use case in areas with poor connectivity. Increases reliability perception.

---

#### P2.4: Keyboard Shortcuts
**Description:** Power users can use keyboard shortcuts to speed up calculations.

**User Story:**
> As a power user, I want keyboard shortcuts so that I can calculate tips faster without using the mouse.

**Acceptance Criteria:**
- [ ] Keyboard shortcuts for preset percentages (e.g., 1=15%, 2=18%, 3=20%)
- [ ] Enter key submits calculation
- [ ] Tab key navigates between fields
- [ ] Shortcuts are documented in help or settings
- [ ] Shortcuts don't conflict with browser defaults

**Rationale:** Supports power users and accessibility. Low effort to implement.

---

#### P2.5: Share Calculation
**Description:** Users can share a calculation result via link or social media.

**User Story:**
> As a user, I want to share a calculation with friends so that we can verify the tip together.

**Acceptance Criteria:**
- [ ] User can generate a shareable link with calculation details
- [ ] Link includes bill amount, tip %, tip amount, total, currency
- [ ] Recipient can view calculation without entering data
- [ ] Share button supports common platforms (email, SMS, messaging apps)
- [ ] Shared links are short and don't expose sensitive data

**Rationale:** Increases engagement and viral potential. Supports group scenarios.

---

## OUT OF SCOPE

The following features and scenarios are explicitly **NOT** included in this product:

### Explicitly Out of Scope

1. **Item-Level Splitting**
   - Tracking individual items per person (e.g., "Alice ordered the steak, Bob ordered the salad")
   - Rationale: Adds significant complexity; users can use separate calculators or manual tracking for this scenario
   - Future: Could be a premium feature or separate product

2. **Tip Pooling & Distribution**
   - Splitting tips among multiple staff members (e.g., server, bartender, busser)
   - Rationale: Out of scope for MVP; primarily used by service industry, not general diners
   - Future: Could be a separate tool for restaurant management

3. **Tax Calculation**
   - Calculating sales tax or including tax in tip calculation
   - Rationale: Tax rates vary by jurisdiction and item type; adds complexity without clear user demand
   - Future: Could be added if users request it

4. **Expense Tracking & Analytics**
   - Tracking spending over time, generating reports, or analyzing tipping habits
   - Rationale: Out of scope for MVP; would require backend infrastructure and user accounts
   - Future: Could be a premium feature

5. **Integration with Payment Apps**
   - Syncing with Venmo, PayPal, or other payment platforms
   - Rationale: Requires third-party APIs and user authentication; adds complexity
   - Future: Could be explored after MVP validation

6. **Multi-Language Support**
   - Translating UI into languages other than English
   - Rationale: MVP targets English-speaking users; can be added later
   - Future: Localization for major markets (Spanish, French, German, etc.)

7. **User Accounts & Cloud Sync**
   - Logging in, syncing data across devices, or cloud backup
   - Rationale: Adds backend complexity; local storage is sufficient for MVP
   - Future: Could be added if users request cross-device sync

8. **Advanced Rounding Options**
   - Allowing users to choose rounding behavior (round up, down, nearest)
   - Rationale: Single rounding rule is simpler; can be revisited if users request flexibility
   - Future: Could be added as a settings option

9. **Accessibility Features Beyond WCAG AA**
   - Screen reader optimization, voice input, or other advanced accessibility
   - Rationale: MVP will meet WCAG AA standards; advanced features can be added later
   - Future: Continuous improvement based on user feedback

10. **Mobile App (iOS/Android Native)**
    - Native mobile applications
    - Rationale: Web app is cross-platform and requires no installation; native apps are lower priority
    - Future: Could be considered after web app validation

---

## BUSINESS RULES & CONSTRAINTS

### Rounding Rules (CRITICAL)

**Rule 1: Tip Amount Rounding**
- Tip amounts are **rounded to the nearest cent** (2 decimal places for most currencies)
- Rounding method: **Round half up** (standard mathematical rounding)
  - Example: $5.995 → $6.00; $5.994 → $5.99
- **Exception for JPY and other zero-decimal currencies:** Tip amounts are rounded to the nearest whole unit (0 decimal places)

**Rule 2: Total Bill Rounding**
- Total bill = Bill Amount + Rounded Tip Amount
- Total is always displayed to the correct decimal places for the currency

**Rule 3: Per-Person Rounding (if Bill Splitting is implemented)**
- Per-person tip is calculated as: (Bill Amount × Tip %) ÷ Number of People
- Per-person tip is rounded to the nearest cent
- Per-person total = (Bill Amount ÷ Number of People) + Per-Person Tip
- **Note:** This may result in slight discrepancies (e.g., $0.01 difference) when splitting among 3+ people; this is acceptable and documented

**Rationale:** Rounding rules must be explicit and consistent to avoid user confusion and calculation errors.

---

### Input Constraints

| Field | Minimum | Maximum | Decimals | Notes |
|-------|---------|---------|----------|-------|
| Bill Amount | 0.01 | 999,999.99 | 2 | Negative values rejected; $0 is invalid |
| Tip Percentage | 0 | 100 | 1 | 0% is valid; >100% rejected |
| Number of People (Splitting) | 2 | 20 | 0 | Whole numbers only |

**Rationale:** Constraints prevent nonsensical inputs while supporting realistic use cases.

---

### Currency Decimal Rules

| Currency | Symbol | Decimals | Example |
|----------|--------|----------|---------|
| USD | $ | 2 | $10.50 |
| EUR | € | 2 | €10,50 |
| GBP | £ | 2 | £10.50 |
| JPY | ¥ | 0 | ¥1050 |
| CAD | C$ | 2 | C$10.50 |
| AUD | A$ | 2 | A$10.50 |
| CHF | CHF | 2 | CHF 10.50 |
| INR | ₹ | 2 | ₹10.50 |
| MXN | $ | 2 | $10.50 |
| SGD | S$ | 2 | S$10.50 |

**Rationale:** Correct formatting builds user trust and prevents confusion in international scenarios.

---

### Performance Constraints

- **Page Load Time:** ≤2 seconds on 4G mobile connection (Lighthouse metric)
- **Calculation Response Time:** <100ms (real-time updates as user types)
- **Currency Switching:** <500ms (no noticeable lag)

**Rationale:** Fast performance is critical for mobile use case; users expect instant feedback.

---

### Data Storage & Privacy

- **Local Storage Only:** All user data (currency preference, custom presets, history) stored locally in browser
- **No Backend:** MVP has no backend server or user accounts
- **No Tracking:** No analytics, cookies, or user tracking (except optional, privacy-respecting analytics)
- **Data Retention:** User data persists until browser cache is cleared; no automatic deletion

**Rationale:** Simplifies MVP; protects user privacy; reduces infrastructure costs.

---

## RISKS & MITIGATIONS

### Risk 1: Rounding Errors Erode User Trust
**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** Users distrust calculations; negative reviews; low repeat usage

**Mitigation:**
- [ ] Define rounding rules explicitly in this PRD (see Business Rules section)
- [ ] Implement comprehensive unit tests for all rounding scenarios
- [ ] Display rounding rule in app (e.g., "Tip rounded to nearest cent")
- [ ] Test edge cases: $33.33 + 18%, $100 ÷ 3 people, JPY amounts
- [ ] Provide clear documentation for support team

---

### Risk 2: Currency Formatting Errors
**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** International users confused; incorrect amounts displayed; loss of trust

**Mitigation:**
- [ ] Use established currency formatting library (not custom code)
- [ ] Test all 10+ supported currencies with real-world amounts
- [ ] Verify decimal places, symbols, and thousands separators for each currency
- [ ] Include currency formatting in acceptance criteria
- [ ] Create test matrix for all currency combinations

---

### Risk 3: Poor Mobile UX Limits Adoption
**Severity:** HIGH  
**Probability:** MEDIUM  
**Impact:** Primary use case fails; low adoption; negative reviews

**Mitigation:**
- [ ] Design mobile-first (not responsive retrofit)
- [ ] Test on real devices (iOS and Android) during development
- [ ] Ensure all touch targets ≥44x44px
- [ ] Test in low-light environments (restaurant scenario)
- [ ] Conduct usability testing with target personas before launch

---

### Risk 4: Scope Creep (Bill Splitting Complexity)
**Severity:** MEDIUM  
**Probability:** HIGH  
**Impact:** MVP delayed; engineering overload; feature bloat

**Mitigation:**
- [ ] Bill splitting is P1, not P0 (not required for MVP)
- [ ] Define splitting scope clearly: equal split only (no item-level tracking)
- [ ] Document rounding behavior for splitting upfront
- [ ] Use MoSCoW prioritization to enforce scope discipline
- [ ] Revisit after MVP launch based on user demand

---

### Risk 5: Browser Compatibility Issues
**Severity:** MEDIUM  
**Probability:** LOW  
**Impact:** Some users unable to use app; support burden; negative reviews

**Mitigation:**
- [ ] Test on iOS Safari, Android Chrome, Firefox, Edge
- [ ] Use progressive enhancement (core features work everywhere)
- [ ] Avoid bleeding-edge browser features
- [ ] Test on older devices (2-3 year old phones)
- [ ] Provide fallback for unsupported browsers

---

### Risk 6: Offline Functionality Not Implemented
**Severity:** LOW  
**Probability:** MEDIUM  
**Impact:** Users in areas with poor connectivity frustrated; missed use case

**Mitigation:**
- [ ] Offline functionality is P2 (not required for MVP)
- [ ] Prioritize based on user feedback post-launch
- [ ] If implemented, use service workers (standard approach)
- [ ] Test offline scenarios during development

---

### Risk 7: Preset Tip Percentages Don't Match User Expectations
**Severity:** LOW  
**Probability:** MEDIUM  
**Impact:** Users ignore presets; reduced perceived value; low adoption

**Mitigation:**
- [ ] Research regional tipping norms (15%, 18%, 20% for USA; 10-15% for UK)
- [ ] Conduct user research with target personas
- [ ] Make presets customizable (P1 feature)
- [ ] Allow users to override presets easily
- [ ] Gather feedback post-launch; adjust if needed

---

### Risk 8: Calculation Errors Due to Floating-Point Precision
**Severity:** MEDIUM  
**Probability:** LOW  
**Impact:** Incorrect calculations; user distrust; negative reviews

**Mitigation:**
- [ ] Use fixed-point arithmetic (not floating-point) for currency calculations
- [ ] Implement comprehensive unit tests for all calculation scenarios
- [ ] Test edge cases: very large bills, very small percentages, JPY amounts
- [ ] Code review all calculation logic before launch
- [ ] Monitor for calculation errors post-launch

---

## OPEN QUESTIONS

The following questions must be answered before engineering begins:

### Q1: Bill Splitting Scope
**Question:** Should bill splitting be included in MVP, or deferred to MVP+1?  
**Options:**
- A) Include equal-split only in MVP (P0)
- B) Defer to MVP+1 (P1)
- C) Include with advanced features (item-level tracking)

**Recommendation:** Option B (defer to MVP+1). Equal splitting adds complexity; MVP should focus on core calculation.

**Owner:** Product Manager  
**Timeline:** Decide before engineering kickoff

---

### Q2: Preset Tip Percentages
**Question:** What are the default preset percentages? Should they vary by currency/region?  
**Options:**
- A) Fixed: 15%, 18%, 20% for all users
- B) Dynamic: Vary by selected currency (e.g., 10%, 15%, 20% for GBP; 15%, 18%, 20% for USD)
- C) User-configurable: Let users set their own presets

**Recommendation:** Option A (fixed presets) for MVP; add dynamic/configurable in P1.

**Owner:** Product Manager  
**Timeline:** Decide before design phase

---

### Q3: Calculation Trigger
**Question:** Should calculations update in real-time as user types, or require a "Calculate" button?  
**Options:**
- A) Real-time (no button; updates as user types)
- B) Button-based (user clicks "Calculate" to see results)
- C) Hybrid (real-time for valid inputs; button for confirmation)

**Recommendation:** Option A (real-time). Faster, more intuitive, matches user expectations.

**Owner:** Product Manager  
**Timeline:** Decide before design phase

---

### Q4: Currency Selection Default
**Question:** What should be the default currency on first load?  
**Options:**
- A) USD (most common)
- B) Browser locale (detect from device settings)
- C) GBP (if targeting UK market)
- D) User's last selection (if returning user)

**Recommendation:** Option B (browser locale) for MVP; fall back to USD if locale not recognized.

**Owner:** Product Manager  
**Timeline:** Decide before engineering kickoff

---

### Q5: History Storage Limit
**Question:** How many calculations should be stored in history?  
**Options:**
- A) Last 5 calculations
- B) Last 10 calculations
- C) Last 50 calculations
- D) Unlimited (until browser cache cleared)

**Recommendation:** Option B (last 10). Balances usefulness with storage constraints.

**Owner:** Product Manager  
**Timeline:** Decide before engineering kickoff

---

### Q6: Analytics & Privacy
**Question:** Should the app include analytics (e.g., page views, feature usage)?  
**Options:**
- A) No analytics (privacy-first)
- B) Privacy-respecting analytics (no user tracking, no cookies)
- C) Full analytics (Google Analytics, etc.)

**Recommendation:** Option B (privacy-respecting analytics). Allows us to measure success metrics without compromising privacy.

**Owner:** Product Manager + Legal  
**Timeline:** Decide before engineering kickoff

---

### Q7: Accessibility Standards
**Question:** What accessibility standard should the app meet?  
**Options:**
- A) WCAG 2.0 Level A
- B) WCAG 2.0 Level AA (recommended)
- C) WCAG 2.1 Level AAA

**Recommendation:** Option B (WCAG 2.0 Level AA). Industry standard; balances accessibility with effort.

**Owner:** Product Manager + Design  
**Timeline:** Decide before design phase

---

### Q8: Supported Browsers
**Question:** What browsers and versions should be supported?  
**Options:**
- A) Latest versions only (Chrome, Safari, Firefox, Edge)
- B) Last 2 versions of each browser
- C) Last 3 versions of each browser

**Recommendation:** Option B (last 2 versions). Covers ~95% of users; balances compatibility with development effort.

**Owner:** Engineering Lead  
**Timeline:** Decide before engineering kickoff

---

## APPENDIX: ACCEPTANCE CRITERIA

### Feature Acceptance Checklist

#### P0.1: Basic Tip Calculation
- [ ] Bill amount input accepts numeric values up to 2 decimal places
- [ ] Tip percentage input accepts numeric values 0-100% up to 1 decimal place
- [ ] Tip amount displays correctly (bill × tip % / 100, rounded to 2 decimals)
- [ ] Total bill displays correctly (bill + tip, rounded to 2 decimals)
- [ ] Results update in real-time as user types
- [ ] All calculations are mathematically accurate (verified against manual calculations)
- [ ] Results remain visible after calculation (don't disappear)
- [ ] Works on mobile (iOS Safari, Android Chrome)
- [ ] Works on desktop (Chrome, Firefox, Safari, Edge)

#### P0.2: Multi-Currency Support
- [ ] User can select from ≥10 currencies (USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD)
- [ ] Currency selection persists across sessions
- [ ] All amounts display with correct currency symbol
- [ ] Decimal places follow locale rules (USD/EUR = 2, JPY = 0)
- [ ] Thousands separators display correctly
- [ ] Currency selector is visible and easy to access
- [ ] Changing currency recalculates and reformats all amounts
- [ ] No calculation errors when switching currencies

#### P0.3: Input Validation & Error Handling
- [ ] Bill amount: Rejects negative numbers, letters, empty fields
- [ ] Bill amount: Accepts 0.01 to 999,999.99
- [ ] Tip percentage: Rejects negative numbers, >100%, empty fields
- [ ] Tip percentage: Accepts 0 to 100%
- [ ] Invalid input displays inline error message
- [ ] Error message clears when user corrects input
- [ ] Calculate button disabled until both fields valid (if button exists)
- [ ] Error messages are clear and actionable
- [ ] Edge case: $0 bill with 0% tip is valid

#### P0.4: Preset Tip Percentages
- [ ] App displays ≥3 preset buttons (15%, 18%, 20%)
- [ ] Tapping preset auto-fills tip percentage field
- [ ] User can override preset after selection
- [ ] Presets are easy to tap on mobile (≥44x44px)
- [ ] Results update immediately after preset selection
- [ ] Presets are clearly labeled

#### P0.5: Responsive Mobile Design
- [ ] App fully functional on iOS Safari
- [ ] App fully functional on Android Chrome
- [ ] All inputs and buttons are tappable (≥44x44px)
- [ ] Layout adapts to portrait and landscape
- [ ] Text readable without zooming (≥16px)
- [ ] No horizontal scrolling required
- [ ] Page load time ≤2 seconds on 4G
- [ ] All features accessible without pinch-to-zoom

---

### Test Scenarios

#### Scenario 1: Basic Calculation (USD)
- Input: Bill $50.00, Tip 18%
- Expected: Tip $9.00, Total $59.00
- Status: [ ] Pass / [ ] Fail

#### Scenario 2: Rounding Edge Case (USD)
- Input: Bill $33.33, Tip 18%
- Expected: Tip $6.00 (rounded from $5.9994), Total $39.33
- Status: [ ] Pass / [ ] Fail

#### Scenario 3: Currency Formatting (GBP)
- Input: Bill £50.00, Tip 20%
- Expected: Tip £10.00, Total £60.00 (with £ symbol)
- Status: [ ] Pass / [ ] Fail

#### Scenario 4: JPY Formatting
- Input: Bill ¥5000, Tip 15%
- Expected: Tip ¥750, Total ¥5750 (no decimals)
- Status: [ ] Pass / [ ] Fail

#### Scenario 5: Zero Tip
- Input: Bill $25.00, Tip 0%
- Expected: Tip $0.00, Total $25.00
- Status: [ ] Pass / [ ] Fail

#### Scenario 6: Invalid Input (Negative)
- Input: Bill -$50.00
- Expected: Error message displayed, calculation blocked
- Status: [ ] Pass / [ ] Fail

#### Scenario 7: Invalid Input (Letters)
- Input: Bill "fifty dollars"
- Expected: Error message displayed, calculation blocked
- Status: [ ] Pass / [ ] Fail

#### Scenario 8: Preset Selection
- Input: Bill $75.00, Tap "18%" preset
- Expected: Tip percentage auto-filled to 18%, Tip $13.50, Total $88.50
- Status: [ ] Pass / [ ] Fail

#### Scenario 9: Mobile Portrait
- Device: iPhone 12
- Expected: All elements visible, no horizontal scroll, tappable buttons
- Status: [ ] Pass / [ ] Fail

#### Scenario 10: Mobile Landscape
- Device: iPhone 12 (landscape)
- Expected: Layout adapts, all elements visible, no horizontal scroll
- Status: [ ] Pass / [ ] Fail

---

### Success Metrics Measurement Plan

| Metric | Measurement Method | Target | Timeline |
|--------|-------------------|--------|----------|
| Time-to-Calculate | User testing (stopwatch) | ≤5 seconds | Week 1 post-launch |
| Calculation Accuracy | Automated tests + manual verification | 100% | Before launch |
| User Confidence | Post-use survey | ≥90% | Week 2 post-launch |
| Currency Coverage | Feature audit | ≥10 currencies | Before launch |
| Correct Formatting | Automated tests | 100% | Before launch |
| Currency Adoption | Analytics | ≥30% non-USD | Week 4 post-launch |
| Page Load Time | Lighthouse audit | ≤2 seconds | Before launch |
| First-Time Completion | User testing | ≥80% | Week 1 post-launch |
| Return Usage | Analytics | ≥40% within 7 days | Week 2 post-launch |
| Preset Adoption | Analytics | ≥50% | Week 2 post-launch |

---

## DOCUMENT SIGN-OFF

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Manager | [Name] | [Date] | [ ] |
| Engineering Lead | [Name] | [Date] | [ ] |
| Design Lead | [Name] | [Date] | [ ] |
| Business Stakeholder | [Name] | [Date] | [ ] |

---

## REVISION HISTORY

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | [Current Date] | Product Manager | Initial PRD; P0/P1/P2 features defined; business rules documented |

---

## RELATED DOCUMENTS

- **Technical Requirements Document (TRD):** [Link] - Technology stack, architecture, API design
- **Solution Design Document:** [Link] - Implementation details, database schema, UI mockups
- **User Research Summary:** [Link] - Persona research, user interviews, competitive analysis
- **Go-to-Market Plan:** [Link] - Launch strategy, marketing messaging, success metrics

---

**END OF DOCUMENT**