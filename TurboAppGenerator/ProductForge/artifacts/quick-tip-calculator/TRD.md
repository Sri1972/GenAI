# TECHNICAL REQUIREMENTS DOCUMENT (TRD)
## Tip Calculator Web App

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Owner:** Engineering  
**Status:** Ready for Implementation  
**Audience:** Frontend Engineers, QA, DevOps

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Technology Stack](#technology-stack)
4. [Data Model & Persistence](#data-model--persistence)
5. [Functional Requirements (Technical)](#functional-requirements-technical)
6. [Non-Functional Requirements](#non-functional-requirements)
7. [API & Integration Points](#api--integration-points)
8. [Security & Privacy](#security--privacy)
9. [Error Handling & Validation](#error-handling--validation)
10. [Rounding & Precision Specification](#rounding--precision-specification)
11. [Localization & Formatting](#localization--formatting)
12. [Testing Strategy](#testing-strategy)
13. [Deployment & Operations](#deployment--operations)
14. [Open Questions & Assumptions](#open-questions--assumptions)
15. [Appendix: Acceptance Criteria Checklist](#appendix-acceptance-criteria-checklist)

---

## EXECUTIVE SUMMARY

**Product:** Tip Calculator Web App (MVP)  
**Deployment Model:** Static single-page application (SPA) hosted on static file hosting  
**Technology Profile:** Prototype / Lightweight (per active profile)  
**Core Scope:** Client-side calculation engine with multi-currency support and persistent user preferences  
**Out of Scope (MVP):** Backend API, database, authentication, bill splitting, offline-first PWA, analytics  

**Key Technical Decisions:**
- **No backend required:** All calculations execute in the browser; no server-side logic or persistence layer
- **Client-side storage:** Browser `localStorage` for currency preference persistence
- **Single-file deployment:** HTML + CSS + JavaScript bundled into one self-contained file or minimal asset set
- **Rounding rule:** Banker's rounding (round-half-to-even) for all monetary calculations to minimize systematic bias
- **Supported currencies:** 10 major currencies with locale-aware formatting (USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD)

**Success Criteria (Technical):**
- Page load time ≤2 seconds on 4G mobile
- Time-to-calculate ≤5 seconds from page load to result display
- 100% calculation accuracy with defined rounding behavior
- Zero external API dependencies (offline-capable)
- ≥90% user confidence in accuracy (post-use survey)

---

## ARCHITECTURE OVERVIEW

### System Context Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    User's Browser                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Tip Calculator SPA (Single HTML File)        │   │
│  │                                                      │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  UI Layer (HTML + Tailwind CSS)             │    │   │
│  │  │  - Bill amount input                        │    │   │
│  │  │  - Tip percentage input                     │    │   │
│  │  │  - Currency selector dropdown               │    │   │
│  │  │  - Results display (tip + total)            │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │                      ↓                               │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Calculation Engine (JavaScript)            │    │   │
│  │  │  - Input validation                         │    │   │
│  │  │  - Tip calculation (banker's rounding)      │    │   │
│  │  │  - Currency formatting                      │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  │                      ↓                               │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │  Browser localStorage                       │    │   │
│  │  │  - Selected currency preference             │    │   │
│  │  │  - Last updated timestamp                   │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  No external API calls, no backend dependency               │
└─────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Client-Side First:** All business logic (calculation, validation, formatting) executes in the browser. No server round-trips required for core functionality.
2. **Stateless Calculation:** Each calculation is independent; no session state or server-side context needed.
3. **Progressive Enhancement:** App works with JavaScript disabled for basic input (graceful degradation); real-time updates require JavaScript.
4. **Offline-Capable:** Once loaded, the app functions without network connectivity. Currency preferences persist locally.
5. **Single Responsibility:** The app does one thing well — calculate tips accurately and display them in multiple currencies.

### Failure Modes & Recovery

| Failure Mode | Impact | Recovery Strategy |
|---|---|---|
| Browser localStorage unavailable | Currency preference not persisted; user must re-select on each visit | Default to USD; no error shown (graceful degradation) |
| Invalid user input (non-numeric) | Calculation cannot proceed | Show inline error message; clear invalid field; focus on input |
| Rounding edge case (e.g., $47.51 @ 18%) | Potential mismatch between displayed and actual charge | Use banker's rounding consistently; document rule in UI tooltip |
| JavaScript disabled | App cannot calculate in real-time | Provide static HTML form with "Calculate" button (fallback) |
| Very large numbers (>999,999.99) | Potential display overflow or precision loss | Reject input; show validation error "Amount too large" |

---

## TECHNOLOGY STACK

### Frontend / UI

**Primary Choice:** HTML + CSS (Tailwind) + Vanilla JavaScript  
**Rationale:** 
- Single-page application with minimal interactivity (no multi-page routing, no complex component state)
- Tailwind CSS provides utility-first styling without build complexity
- Vanilla JavaScript sufficient for real-time input handling and calculation
- No framework overhead; reduces bundle size and load time
- Can be delivered as a single self-contained HTML file

**Why Not React?**
- React adds ~40KB gzipped overhead for a simple calculator
- No component reusability benefit; UI is a single form + results display
- Build step (Vite) adds deployment complexity for a prototype
- Vanilla JS + event listeners is simpler and faster for this use case

**Why Not Vue/Angular?**
- Same reasoning as React; overkill for single-page, low-interactivity app
- Prototype profile explicitly discourages framework overhead

**Specific Technologies:**
- **HTML5:** Semantic markup for form inputs, accessibility
- **CSS:** Tailwind CSS v3+ (via CDN for zero build step)
- **JavaScript:** ES6+ (modern browser support assumed; no transpilation needed)
- **No build tool required:** Single HTML file with inline CSS and JavaScript

### Backend / API

**Primary Choice:** None  
**Rationale:**
- All calculations are stateless and execute in the browser
- No data persistence beyond user's local preference (currency selection)
- No authentication, authorization, or multi-user coordination needed
- No external service integration required

**Explicit Out-of-Scope:**
- REST API, GraphQL, or gRPC endpoints
- Server-side business logic
- Database (SQL, NoSQL, or otherwise)
- Authentication/authorization layer
- Rate limiting or API gateway

**Why This Matters:**
- Eliminates operational complexity (no server to deploy, scale, or monitor)
- Reduces latency (no network round-trip for calculations)
- Improves reliability (no backend failure points)
- Simplifies deployment (static file hosting only)

### Data Persistence

**Primary Choice:** Browser `localStorage`  
**Rationale:**
- Persists user's currency preference across sessions
- No server-side storage required
- Works offline
- ~5-10MB quota per domain; tip calculator uses <1KB

**Why Not IndexedDB?**
- Overkill for a single preference value
- localStorage is simpler and sufficient

**Why Not Cookies?**
- Unnecessary HTTP overhead
- localStorage is more appropriate for client-side-only data

**Why Not Server-Side Session?**
- Requires backend infrastructure
- Adds latency and complexity
- Not needed for a stateless calculator

### Hosting & Deployment

**Primary Choice:** Static file hosting  
**Rationale:**
- Single HTML file (or minimal asset set) requires no server-side runtime
- Can be deployed to any static host: GitHub Pages, Netlify, Vercel, AWS S3, or simple HTTP server
- Zero operational overhead

**Specific Hosting Options (Not Mandated):**
- GitHub Pages (free, simple, no configuration)
- Netlify (free tier, automatic deployments from Git)
- AWS S3 + CloudFront (if organization already uses AWS)
- Local HTTP server for development (Python `http.server`, Node `http-server`, etc.)

**Why Not Docker/Kubernetes?**
- Unnecessary for a static file
- Adds deployment complexity without benefit

**Why Not Serverless (Lambda/Cloud Functions)?**
- No backend logic to execute
- Static hosting is simpler and cheaper

### Observability & Monitoring

**Primary Choice:** Browser console logging only  
**Rationale:**
- Prototype profile; no production monitoring infrastructure required
- Console logs sufficient for debugging during development
- No user data to track or analyze (no analytics service)

**Logging Strategy:**
- Log calculation inputs and results to console (development only; can be disabled in production)
- Log validation errors and edge cases
- No PII or sensitive data logged

**Why Not Google Analytics / Mixpanel?**
- Out of scope for MVP
- Can be added in v1.1 if usage metrics are needed
- Requires privacy policy update and user consent

### Testing

**Primary Choice:** Manual testing / smoke checklist  
**Rationale:**
- Prototype profile; automated testing not required for MVP
- Simple calculation logic is easy to verify manually
- QA checklist sufficient for launch

**Smoke Test Checklist (Manual):**
- [ ] Page loads in <2 seconds on 4G mobile
- [ ] Bill amount input accepts valid numbers (0.01 to 999,999.99)
- [ ] Tip percentage input accepts valid percentages (0 to 100%)
- [ ] Calculation updates in real-time as user types
- [ ] Results display with correct currency symbol and formatting
- [ ] Currency selector persists across page reload
- [ ] Invalid inputs show error messages
- [ ] Rounding behavior matches specification (banker's rounding)
- [ ] App works on Chrome, Safari, Firefox (latest versions)
- [ ] App works on mobile (iOS Safari, Chrome Android)

**Why Not Jest/Vitest?**
- Not explicitly requested in PRD
- Manual testing sufficient for MVP scope
- Can be added in v1.1 if regression risk increases

### CI/CD

**Primary Choice:** None (manual build/run)  
**Rationale:**
- Single HTML file; no build step required
- No automated testing to run
- Deployment is manual file upload to static host

**Future Enhancement (Not MVP):**
- GitHub Actions workflow to lint HTML/CSS/JS and deploy on push to `main` branch
- Can be added in v1.1 if team adopts continuous deployment

---

## DATA MODEL & PERSISTENCE

### Data Entities

#### 1. Calculation Input (Transient)
**Scope:** In-memory only; not persisted  
**Attributes:**
- `billAmount` (number): User-entered bill amount in local currency (0.01 to 999,999.99)
- `tipPercentage` (number): User-entered tip percentage (0 to 100, up to 1 decimal place)
- `selectedCurrency` (string): ISO 4217 currency code (e.g., "USD", "GBP", "EUR")

**Lifecycle:** Created on user input; cleared on page reload or currency change

#### 2. Calculation Result (Transient)
**Scope:** In-memory only; not persisted  
**Attributes:**
- `tipAmount` (number): Calculated tip (billAmount × tipPercentage / 100), rounded per specification
- `totalBill` (number): Bill + tip, rounded per specification
- `calculatedAt` (timestamp): ISO 8601 timestamp of calculation (for debugging)

**Lifecycle:** Generated on each input change; cleared on page reload

#### 3. User Preference (Persistent)
**Scope:** Browser localStorage  
**Storage Key:** `tipCalculator_preferences`  
**Schema:**
```
{
  "selectedCurrency": "GBP",
  "lastUpdated": "2024-01-15T10:30:00Z"
}
```

**Lifecycle:**
- Created on first currency selection
- Updated whenever user changes currency
- Persists across page reloads and browser sessions
- Cleared only if user manually clears browser storage

**Storage Limits:**
- localStorage quota: ~5-10MB per domain
- Tip calculator usage: <1KB
- No quota risk

### Data Flow Diagram

```
User Input (Bill, Tip %)
        ↓
   Validation
   (Check range, format)
        ↓
   [Valid?] ──No──→ Show Error Message
        │
       Yes
        ↓
   Calculation Engine
   (billAmount × tipPercentage / 100)
        ↓
   Rounding (Banker's Rounding)
        ↓
   Format for Display
   (Currency symbol, decimals, separators)
        ↓
   Display Results
   (Tip Amount + Total Bill)
        ↓
   [User changes currency?]
        │
       Yes
        ↓
   Save to localStorage
   Recalculate & reformat
```

### Persistence Strategy

**Currency Preference:**
- Saved to localStorage immediately on user selection
- Loaded from localStorage on page load
- Default to USD if no preference exists
- No server-side sync required

**Calculation History:**
- Not persisted (out of scope for MVP)
- Each calculation is independent
- User can clear inputs and start fresh

---

## FUNCTIONAL REQUIREMENTS (TECHNICAL)

### FR1: Real-Time Tip Calculation

**Requirement:** As user types bill amount and tip percentage, the app calculates and displays tip amount and total bill in real-time.

**Technical Specification:**

**Input Handling:**
- Bill amount input: Accepts numeric values with up to 2 decimal places
  - Valid range: 0.01 to 999,999.99
  - Rejects: negative numbers, letters, special characters (except decimal point)
  - Behavior: Calculation updates on each keystroke (no "Calculate" button)
- Tip percentage input: Accepts numeric values with up to 1 decimal place
  - Valid range: 0 to 100
  - Rejects: negative numbers, >100, letters, special characters (except decimal point)
  - Behavior: Calculation updates on each keystroke

**Calculation Logic:**
- Formula: `tipAmount = billAmount × (tipPercentage / 100)`
- Formula: `totalBill = billAmount + tipAmount`
- Both results rounded per rounding specification (see Section 10)
- Calculation executes synchronously in browser (no async delay)

**Output Display:**
- Tip amount: Displayed with currency symbol, correct decimal places, thousands separator
- Total bill: Displayed with currency symbol, correct decimal places, thousands separator
- Both values visible simultaneously
- Results update immediately as user types (no perceptible delay)

**Edge Cases:**
- Bill amount = 0: Display tip = 0, total = 0 (valid scenario)
- Tip percentage = 0: Display tip = 0, total = bill amount (valid scenario)
- Very small amounts (e.g., $0.01 @ 1%): Display $0.00 tip (rounded down per banker's rounding)
- Very large amounts (e.g., $999,999.99 @ 100%): Display correctly formatted result

**Acceptance Criteria:**
- [ ] Calculation updates within 100ms of user input (imperceptible delay)
- [ ] Results are mathematically accurate per rounding specification
- [ ] No calculation errors or NaN/Infinity values displayed
- [ ] Results remain visible after calculation (don't disappear)

---

### FR2: Multi-Currency Support

**Requirement:** User can select from 10 major currencies; all amounts display with correct formatting.

**Technical Specification:**

**Supported Currencies:**
| Currency | Code | Symbol | Decimal Places | Thousands Separator | Example |
|---|---|---|---|---|---|
| US Dollar | USD | $ | 2 | , | $1,234.56 |
| Euro | EUR | € | 2 | . | €1.234,56 |
| British Pound | GBP | £ | 2 | , | £1,234.56 |
| Japanese Yen | JPY | ¥ | 0 | , | ¥123,456 |
| Canadian Dollar | CAD | C$ | 2 | , | C$1,234.56 |
| Australian Dollar | AUD | A$ | 2 | , | A$1,234.56 |
| Swiss Franc | CHF | CHF | 2 | ' | CHF 1'234.56 |
| Indian Rupee | INR | ₹ | 2 | , | ₹1,23,456.78 |
| Mexican Peso | MXN | $ | 2 | , | $1,234.56 |
| Singapore Dollar | SGD | S$ | 2 | , | S$1,234.56 |

**Currency Selection:**
- Dropdown/select menu with all 10 currencies
- Default: USD on first visit
- User can change currency at any time
- Selection persists to localStorage immediately

**Formatting Rules:**
- Symbol placement: Before amount (USD, GBP, EUR, etc.) or after (JPY, CHF, INR)
- Decimal places: Per locale (JPY = 0, others = 2)
- Thousands separator: Per locale (comma, period, apostrophe, or space)
- Spacing: Per locale (e.g., "CHF 1'234.56" vs "$1,234.56")

**Recalculation on Currency Change:**
- When user changes currency, all displayed amounts reformat immediately
- Calculation values do NOT change (e.g., $100 @ 15% = £100 @ 15% in local currency)
- No currency conversion applied (user is responsible for converting bill amount if needed)

**Acceptance Criteria:**
- [ ] All 10 currencies display with correct symbol and formatting
- [ ] Decimal places match locale specification (JPY = 0, others = 2)
- [ ] Thousands separators display correctly per locale
- [ ] Currency selection persists across page reload
- [ ] Changing currency reformats all displayed amounts immediately
- [ ] No currency conversion applied (calculation values unchanged)

---

### FR3: Input Validation & Error Handling

**Requirement:** App validates user inputs and provides clear, actionable error messages.

**Technical Specification:**

**Bill Amount Validation:**
- Accepts: Numeric values 0.01 to 999,999.99 with up to 2 decimal places
- Rejects: Negative numbers, letters, special characters (except decimal point), empty field
- Error message: "Please enter a bill amount between $0.01 and $999,999.99"
- Display: Inline error below input field (red text, small font)
- Behavior: Error clears when user corrects input

**Tip Percentage Validation:**
- Accepts: Numeric values 0 to 100 with up to 1 decimal place
- Rejects: Negative numbers, >100, letters, special characters (except decimal point), empty field
- Error message: "Please enter a tip percentage between 0% and 100%"
- Display: Inline error below input field (red text, small font)
- Behavior: Error clears when user corrects input

**Empty Field Handling:**
- If bill amount is empty: No calculation; no error shown (user hasn't started)
- If tip percentage is empty: No calculation; no error shown (user hasn't started)
- If both are empty: No calculation; no error shown
- If one is filled and one is empty: No calculation; no error shown (user still entering data)
- Error only shown when user enters invalid data (e.g., negative number, >100%)

**Real-Time Validation:**
- Validation runs on each keystroke (input event)
- Error message appears immediately if input is invalid
- Error clears immediately when input becomes valid
- No "Submit" button; validation is continuous

**Acceptance Criteria:**
- [ ] Invalid inputs show clear, actionable error messages
- [ ] Error messages appear/disappear in real-time
- [ ] Valid inputs clear error messages
- [ ] Empty fields do not trigger errors (user still entering)
- [ ] Calculation does not execute if either input is invalid

---

### FR4: Currency Preference Persistence

**Requirement:** User's selected currency persists across page reloads and browser sessions.

**Technical Specification:**

**Storage Mechanism:**
- Use browser `localStorage` API
- Storage key: `tipCalculator_preferences`
- Data format: JSON object with `selectedCurrency` and `lastUpdated` fields

**Save Behavior:**
- Currency preference saved to localStorage immediately when user selects a new currency
- Timestamp (`lastUpdated`) updated on each save
- No server-side sync required

**Load Behavior:**
- On page load, app checks localStorage for saved preference
- If preference exists: Load saved currency and apply formatting
- If preference does not exist: Default to USD
- No error if localStorage is unavailable (graceful degradation)

**Edge Cases:**
- localStorage unavailable (private browsing, quota exceeded): Default to USD; no error shown
- Corrupted localStorage data: Default to USD; no error shown
- User clears browser storage: Default to USD on next visit

**Acceptance Criteria:**
- [ ] Currency preference persists across page reload
- [ ] Currency preference persists across browser sessions
- [ ] Default to USD if no preference exists
- [ ] Gracefully handle localStorage unavailability (no error shown)
- [ ] Timestamp updated on each currency change

---

## NON-FUNCTIONAL REQUIREMENTS

### NFR1: Performance

**Requirement:** App loads and responds quickly on mobile networks.

**Specification:**

**Page Load Time:**
- Target: ≤2 seconds on 4G mobile connection (measured via Lighthouse)
- Measured from: Initial request to page interactive (user can interact with inputs)
- Includes: HTML parsing, CSS rendering, JavaScript execution
- Excludes: External CDN latency (Tailwind CSS CDN)

**Time-to-Calculate:**
- Target: ≤5 seconds from page load to first calculation result displayed
- Measured from: Page load complete to results visible on screen
- Includes: User input time (not measured; user-dependent)

**Real-Time Calculation Response:**
- Target: ≤100ms from keystroke to result update
- Measured from: Input event fired to DOM updated with new result
- Ensures: No perceptible lag as user types

**Bundle Size:**
- Target: ≤100KB total (HTML + CSS + JavaScript gzipped)
- Rationale: Fits in single HTTP request; fast download on 4G

**Why These Targets?**
- 2-second page load: Industry standard for mobile web; users abandon slower sites
- 5-second time-to-calculate: Acceptable for a utility app; user expects quick feedback
- 100ms keystroke response: Imperceptible to human; feels instant
- 100KB bundle: Single HTTP request; no additional round-trips

**Measurement Tools:**
- Lighthouse (Chrome DevTools): Measure page load time and performance metrics
- WebPageTest: Measure real-world performance on 4G connection
- Browser DevTools: Measure keystroke-to-update latency

**Acceptance Criteria:**
- [ ] Page load time ≤2 seconds on 4G (Lighthouse score ≥90)
- [ ] Time-to-calculate ≤5 seconds from page load
- [ ] Keystroke-to-update latency ≤100ms
- [ ] Total bundle size ≤100KB gzipped

---

### NFR2: Reliability & Availability

**Requirement:** App functions correctly and consistently across browsers and devices.

**Specification:**

**Browser Support:**
- Chrome (latest 2 versions)
- Safari (latest 2 versions)
- Firefox (latest 2 versions)
- Edge (latest 2 versions)

**Device Support:**
- Desktop (Windows, macOS, Linux)
- Mobile (iOS 12+, Android 8+)
- Tablet (iPad, Android tablets)

**Offline Capability:**
- Once page is loaded, app functions without network connectivity
- Calculation engine works offline
- Currency preference loads from localStorage (no network call)
- No external API calls required

**Uptime Target:**
- 99.9% availability (static file hosting; no backend to fail)
- Measured: File availability on hosting provider

**Graceful Degradation:**
- If JavaScript is disabled: Form displays; user can enter data (no real-time calculation)
- If localStorage is unavailable: App works; currency defaults to USD
- If CSS fails to load: Form is still usable (unstyled but functional)

**Acceptance Criteria:**
- [ ] App works on all supported browsers (manual testing)
- [ ] App works on desktop, mobile, and tablet (responsive design)
- [ ] App functions offline after initial page load
- [ ] Graceful degradation if JavaScript or localStorage unavailable
- [ ] No console errors or warnings

---

### NFR3: Accessibility

**Requirement:** App is usable by people with disabilities.

**Specification:**

**WCAG 2.1 Level AA Compliance:**
- Semantic HTML (form labels, input types, error messages)
- Keyboard navigation: All inputs and controls accessible via Tab key
- Color contrast: Text contrast ratio ≥4.5:1 (WCAG AA standard)
- Focus indicators: Visible focus outline on all interactive elements
- Error messages: Associated with form fields via `aria-describedby`

**Form Accessibility:**
- Bill amount input: `<label>` associated with `<input type="number">`
- Tip percentage input: `<label>` associated with `<input type="number">`
- Currency selector: `<label>` associated with `<select>`
- Error messages: Displayed inline with `aria-live="polite"` for screen readers

**Screen Reader Support:**
- Form labels read aloud by screen readers
- Error messages announced when they appear
- Results announced when calculation updates
- Currency symbol included in announced amount (e.g., "Tip: $8.55")

**Acceptance Criteria:**
- [ ] All form inputs have associated labels
- [ ] Keyboard navigation works (Tab, Enter, arrow keys)
- [ ] Color contrast ≥4.5:1 for all text
- [ ] Focus indicators visible on all interactive elements
- [ ] Error messages announced by screen readers
- [ ] WAVE accessibility checker: No errors or contrast warnings

---

### NFR4: Security & Privacy

**Requirement:** App protects user data and operates securely.

**Specification:**

**Data Protection:**
- No user data collected or transmitted to server
- No PII (personally identifiable information) stored
- No cookies set (except localStorage, which is client-side only)
- No third-party tracking or analytics

**HTTPS Requirement:**
- App must be served over HTTPS (not HTTP)
- Rationale: Industry standard; protects against man-in-the-middle attacks
- Enforced by hosting provider (GitHub Pages, Netlify, etc. default to HTTPS)

**Content Security Policy (CSP):**
- Inline CSS and JavaScript allowed (single-file app)
- No external script execution
- No eval() or dynamic code execution

**Input Sanitization:**
- All user inputs validated and type-checked (numeric only)
- No HTML/JavaScript injection possible (inputs are numbers, not strings)
- No SQL injection risk (no database)

**localStorage Security:**
- localStorage is domain-scoped (only accessible from same domain)
- No sensitive data stored (only currency preference)
- User can clear localStorage manually via browser settings

**Acceptance Criteria:**
- [ ] App served over HTTPS only
- [ ] No external API calls or third-party scripts
- [ ] No user data transmitted to server
- [ ] Input validation prevents injection attacks
- [ ] No console errors related to security

---

### NFR5: Usability & User Experience

**Requirement:** App is intuitive and requires minimal learning.

**Specification:**

**First-Time User Experience:**
- Page loads with empty form and default currency (USD)
- Labels clearly indicate what each input is for ("Bill Amount", "Tip Percentage")
- Results section visible but empty until user enters data
- No onboarding or tutorial required

**Real-Time Feedback:**
- Results update as user types (no "Calculate" button)
- Error messages appear immediately if input is invalid
- Currency symbol updates immediately when user changes currency
- No loading spinners or delays (all calculations instant)

**Mobile-First Design:**
- Form inputs are large enough to tap on mobile (≥44px height)
- Keyboard appears automatically on mobile (input type="number")
- Results are readable on small screens (responsive layout)
- No horizontal scrolling required

**Visual Hierarchy:**
- Bill amount and tip percentage inputs are prominent
- Results (tip amount and total) are clearly highlighted
- Currency selector is visible but not distracting
- Error messages are red and easy to spot

**Acceptance Criteria:**
- [ ] First-time user can complete calculation without help
- [ ] Results update in real-time as user types
- [ ] Error messages are clear and actionable
- [ ] Mobile layout is responsive and readable
- [ ] No onboarding or tutorial required

---

## API & INTEGRATION POINTS

### External Dependencies

**Explicit Statement:** Tip Calculator has **zero external API dependencies** for MVP.

**Why This Matters:**
- No third-party service calls required
- App functions offline after initial page load
- No rate limiting, authentication, or SLA concerns
- No vendor lock-in or service discontinuation risk

### Internal Data Flow (No APIs)

All data flows are client-side only:

1. **User Input** → Validation → Calculation → Formatting → Display
2. **Currency Selection** → localStorage save → Recalculation → Display
3. **Page Load** → localStorage read → Apply saved currency → Display

No HTTP requests, no API endpoints, no backend communication.

### Future Integration Points (Post-MVP)

These are documented for reference but **out of scope for MVP**:

| Integration | Purpose | Status | Rationale |
|---|---|---|---|
| Analytics API (Google Analytics, Mixpanel) | Track user behavior, feature adoption | P1 (v1.1) | Requires privacy policy; not needed for MVP |
| Currency Exchange API | Convert bill amount between currencies | P2 (v2.0) | Out of scope; users responsible for conversion |
| Tip Database API | Store/retrieve common tip percentages by country | P2 (v2.0) | Out of scope; hardcoded defaults sufficient for MVP |
| Bill Splitting API | Persist split calculations | P2 (v2.0) | Out of scope; feature not in MVP |

---

## ERROR HANDLING & VALIDATION

### Input Validation Rules

#### Bill Amount Input

| Scenario | Input | Validation | Action | Error Message |
|---|---|---|---|---|
| Valid amount | "47.50" | ✓ Pass | Calculate | None |
| Valid amount (no decimals) | "100" | ✓ Pass | Calculate | None |
| Valid amount (1 decimal) | "50.5" | ✓ Pass | Calculate | None |
| Negative number | "-50" | ✗ Fail | Block | "Please enter a bill amount between $0.01 and $999,999.99" |
| Zero | "0" | ✗ Fail | Block | "Please enter a bill amount between $0.01 and $999,999.99" |
| Too large | "1000000" | ✗ Fail | Block | "Please enter a bill amount between $0.01 and $999,999.99" |
| Non-numeric | "abc" | ✗ Fail | Block | "Please enter a bill amount between $0.01 and $999,999.99" |
| Special characters | "$50" | ✗ Fail | Block | "Please enter a bill amount between $0.01 and $999,999.99" |
| Too many decimals | "50.555" | ✗ Fail | Block | "Please enter a bill amount between $0.01 and $999,999.99" |
| Empty | "" | ✓ Pass (no error) | No calculation | None (user still entering) |

#### Tip Percentage Input

| Scenario | Input | Validation | Action | Error Message |
|---|---|---|---|---|
| Valid percentage | "18" | ✓ Pass | Calculate | None |
| Valid percentage (decimal) | "18.5" | ✓ Pass | Calculate | None |
| Zero | "0" | ✓ Pass | Calculate | None |
| 100% | "100" | ✓ Pass | Calculate | None |
| Negative | "-15" | ✗ Fail | Block | "Please enter a tip percentage between 0% and 100%" |
| >100% | "150" | ✗ Fail | Block | "Please enter a tip percentage between 0% and 100%" |
| Non-numeric | "abc" | ✗ Fail | Block | "Please enter a tip percentage between 0% and 100%" |
| Special characters | "15%" | ✗ Fail | Block | "Please enter a tip percentage between 0% and 100%" |
| Too many decimals | "15.555" | ✗ Fail | Block | "Please enter a tip percentage between 0% and 100%" |
| Empty | "" | ✓ Pass (no error) | No calculation | None (user still entering) |

### Error Display Strategy

**Inline Errors:**
- Error message appears directly below the invalid input field
- Text color: Red (#EF4444 or similar)
- Font size: Small (12-14px)
- Icon: Optional warning icon (⚠️)
- Behavior: Appears on keystroke if input is invalid; disappears when input becomes valid

**Error Clearing:**
- Error automatically clears when user corrects input
- No manual dismissal required
- No error persists after user fixes the problem

**Example Error State:**
```
Bill Amount: [47.50]
Tip Percentage: [-15]
                 ⚠️ Please enter a tip percentage between 0% and 100%
```

### Calculation Edge Cases

| Bill | Tip % | Exact Tip | Displayed Tip | Rationale |
|---|---|---|---|---|
| $47.50 | 18% | $8.55 | $8.55 | Exact; no rounding needed |
| $47.51 | 18% | $8.5518 | $8.55 | Banker's rounding (round-half-to-even) |
| $33.33 | 20% | $6.666 | $6.67 | Banker's rounding (round-half-up) |
| $0.01 | 1% | $0.0001 | $0.00 | Banker's rounding (round-half-down) |
| $100.00 | 15% | $15.00 | $15.00 | Exact; no rounding needed |
| ¥1,000 | 10% | ¥100 | ¥100 | JPY has 0 decimals; exact |
| ¥1,001 | 10% | ¥100.1 | ¥100 | JPY rounded to nearest integer |

---

## ROUNDING & PRECISION SPECIFICATION

### Rounding Rule: Banker's Rounding (Round-Half-to-Even)

**Definition:** When a value is exactly halfway between two rounded values, round to the nearest even number.

**Rationale:**
- Minimizes systematic bias (alternates between rounding up and down)
- Standard in financial systems (IEEE 754, SQL, Python)
- Prevents cumulative rounding errors in repeated calculations
- Fair to both payer and payee

**Examples:**

| Value | Rounded to 2 Decimals | Explanation |
|---|---|---|
| 8.545 | 8.54 | Halfway; round to even (4) |
| 8.555 | 8.56 | Halfway; round to even (6) |
| 8.565 | 8.56 | Halfway; round to even (6) |
| 8.575 | 8.58 | Halfway; round to even (8) |
| 8.5449 | 8.54 | Not halfway; round down |
| 8.5451 | 8.55 | Not halfway; round up |

### Implementation

**JavaScript Implementation:**
- Use `Math.round()` with adjustment for banker's rounding
- Or use `Intl.NumberFormat` with `minimumFractionDigits` and `maximumFractionDigits`
- Ensure consistency across all calculations

**Precision:**
- All intermediate calculations use JavaScript's native number precision (IEEE 754 double-precision)
- Final results rounded to 2 decimal places (or 0 for JPY)
- No arbitrary precision library needed (overkill for this use case)

### Display Precision

**USD, EUR, GBP, CAD, AUD, CHF, INR, MXN, SGD:**
- Display: 2 decimal places
- Example: $8.55, €8,55, £8.55

**JPY:**
- Display: 0 decimal places (no cents)
- Example: ¥100

### Acceptance Criteria

- [ ] Rounding follows banker's rounding (round-half-to-even) consistently
- [ ] All results rounded to correct decimal places per currency
- [ ] No rounding errors or precision loss in calculations
- [ ] Rounding behavior documented in code comments

---

## LOCALIZATION & FORMATTING

### Currency Formatting Rules

**USD (US Dollar)**
- Symbol: $ (before amount)
- Decimal places: 2
- Thousands separator: , (comma)
- Example: $1,234.56

**EUR (Euro)**
- Symbol: € (before amount in some locales, after in others; use before for consistency)
- Decimal places: 2
- Thousands separator: . (period) in most EU countries; , (comma) in some
- Example: €1.234,56 (German/French style) or €1,234.56 (English style)
- **Decision:** Use €1.234,56 (European standard)

**GBP (British Pound)**
- Symbol: £ (before amount)
- Decimal places: 2
- Thousands separator: , (comma)
- Example: £1,234.56

**JPY (Japanese Yen)**
- Symbol: ¥ (before amount)
- Decimal places: 0 (no cents)
- Thousands separator: , (comma)
- Example: ¥123,456

**CAD (Canadian Dollar)**
- Symbol: C$ (before amount)
- Decimal places: 2
- Thousands separator: , (comma)
- Example: C$1,234.56

**AUD (Australian Dollar)**
- Symbol: A$ (before amount)
- Decimal places: 2
- Thousands separator: , (comma)
- Example: A$1,234.56

**CHF (Swiss Franc)**
- Symbol: CHF (before amount with space)
- Decimal places: 2
- Thousands separator: ' (apostrophe)
- Example: CHF 1'234.56

**INR (Indian Rupee)**
- Symbol: ₹ (before amount)
- Decimal places: 2
- Thousands separator: , (comma, with special grouping: 1,23,456.78)
- Example: ₹1,23,456.78

**MXN (Mexican Peso)**
- Symbol: $ (before amount; same as USD but different currency)
- Decimal places: 2
- Thousands separator: , (comma)
- Example: $1,234.56

**SGD (Singapore Dollar)**
- Symbol: S$ (before amount)
- Decimal places: 2
- Thousands separator: , (comma)
- Example: S$1,234.56

### Formatting Implementation

**Option 1: Intl.NumberFormat (Recommended)**
- Use JavaScript's built-in `Intl.NumberFormat` API
- Handles locale-specific formatting automatically
- Supported in all modern browsers
- Example: `new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(1234.56)`

**Option 2: Manual Formatting**
- Define formatting rules in a configuration object
- Apply symbol, decimals, and separators manually
- More control; more code to maintain

**Recommendation:** Use `Intl.NumberFormat` for consistency and maintainability.

### Acceptance Criteria

- [ ] All 10 currencies format correctly (symbol, decimals, separators)
- [ ] JPY displays 0 decimal places; others display 2
- [ ] Thousands separators display correctly per locale
- [ ] Currency symbol placement is consistent
- [ ] No formatting errors or display bugs

---

## TESTING STRATEGY

### Manual Testing Approach

**Rationale:** Prototype profile; automated testing not required for MVP. Manual testing sufficient for simple calculation logic.

### Test Scenarios

#### Calculation Accuracy

| Test Case | Bill | Tip % | Expected Tip | Expected Total | Status |
|---|---|---|---|---|---|
| Basic calculation | $100.00 | 15% | $15.00 | $115.00 | [ ] |
| Decimal bill | $47.50 | 18% | $8.55 | $56.05 | [ ] |
| Decimal tip % | $100.00 | 18.5% | $18.50 | $118.50 | [ ] |
| Zero tip | $100.00 | 0% | $0.00 | $100.00 | [ ] |
| High tip % | $100.00 | 50% | $50.00 | $150.00 | [ ] |
| Small amount | $0.01 | 1% | $0.00 | $0.01 | [ ] |
| Large amount | $999,999.99 | 20% | $199,999.98 | $1,199,999.97 | [ ] |
| Rounding edge case | $47.51 | 18% | $8.55 | $56.06 | [ ] |

#### Input Validation

| Test Case | Input | Expected Behavior | Status |
|---|---|---|---|
| Valid bill amount | 100 | Accept; calculate | [ ] |
| Negative bill | -50 | Reject; show error | [ ] |
| Zero bill | 0 | Reject; show error | [ ] |
| Non-numeric bill | abc | Reject; show error | [ ] |
| Valid tip % | 18 | Accept; calculate | [ ] |
| Negative tip % | -15 | Reject; show error | [ ] |
| Tip % > 100 | 150 | Reject; show error | [ ] |
| Non-numeric tip % | abc | Reject; show error | [ ] |
| Empty bill | (empty) | No error; no calculation | [ ] |
| Empty tip % | (empty) | No error; no calculation | [ ] |

#### Currency Formatting

| Test Case | Currency | Amount | Expected Display | Status |
|---|---|---|---|---|
| USD | USD | 1234.56 | $1,234.56 | [ ] |
| EUR | EUR | 1234.56 | €1.234,56 | [ ] |
| GBP | GBP | 1234.56 | £1,234.56 | [ ] |
| JPY | JPY | 123456 | ¥123,456 | [ ] |
| CAD | CAD | 1234.56 | C$1,234.56 | [ ] |
| AUD | AUD | 1234.56 | A$1,234.56 | [ ] |
| CHF | CHF | 1234.56 | CHF 1'234.56 | [ ] |
| INR | INR | 123456.78 | ₹1,23,456.78 | [ ] |
| MXN | MXN | 1234.56 | $1,234.56 | [ ] |
| SGD | SGD | 1234.56 | S$1,234.56 | [ ] |

#### Currency Persistence

| Test Case | Action | Expected Behavior | Status |
|---|---|---|---|
| Select currency | User selects GBP | GBP selected; all amounts display in GBP | [ ] |
| Reload page | User reloads page | GBP still selected (loaded from localStorage) | [ ] |
| Clear storage | User clears browser storage | Default to USD on next visit | [ ] |
| Change currency | User changes from GBP to USD | USD selected; amounts reformat | [ ] |

#### Real-Time Calculation

| Test Case | Action | Expected Behavior | Status |
|---|---|---|---|
| Type bill amount | User types "100" | Results update in real-time | [ ] |
| Type tip % | User types "15" | Results update in real-time | [ ] |
| Keystroke latency | User types quickly | No lag; results update smoothly | [ ] |
| Clear input | User clears bill amount | Results clear | [ ] |

#### Browser & Device Compatibility

| Browser | Version | Status |
|---|---|---|
| Chrome | Latest | [ ] |
| Safari | Latest | [ ] |
| Firefox | Latest | [ ] |
| Edge | Latest | [ ] |
| Chrome Mobile | Latest | [ ] |
| Safari iOS | Latest | [ ] |

#### Performance

| Metric | Target | Measured | Status |
|---|---|---|---|
| Page load time | ≤2 seconds | ___ seconds | [ ] |
| Time-to-calculate | ≤5 seconds | ___ seconds | [ ] |
| Keystroke-to-update | ≤100ms | ___ ms | [ ] |
| Bundle size | ≤100KB | ___ KB | [ ] |

#### Accessibility

| Test Case | Expected Behavior | Status |
|---|---|---|
| Keyboard navigation | Tab key navigates all inputs | [ ] |
| Focus indicators | Visible focus outline on inputs | [ ] |
| Color contrast | Text contrast ≥4.5:1 | [ ] |
| Screen reader | Labels and errors announced | [ ] |
| Error messages | Associated with form fields | [ ] |

### Test Execution

**Who:** QA engineer or developer  
**When:** Before launch and after any code changes  
**How:** Manual testing using checklist above  
**Tools:** Browser DevTools, Lighthouse, WAVE accessibility checker  
**Documentation:** Record pass/fail for each test case; document any bugs found

### Bug Reporting

**Format:**
- Test case: [Name]
- Expected: [What should happen]
- Actual: [What actually happened]
- Severity: [Critical / High / Medium / Low]
- Steps to reproduce: [Detailed steps]

**Severity Levels:**
- **Critical:** App crashes, calculation is wrong, data loss
- **High:** Feature doesn't work as specified, but app still functions
- **Medium:** Minor UI issue, formatting problem, edge case
- **Low:** Cosmetic issue, typo, nice-to-have improvement

---

## DEPLOYMENT & OPERATIONS

### Deployment Model

**Type:** Static file hosting  
**Artifact:** Single HTML file (or minimal asset set: HTML + CSS + JS)  
**Hosting Options:**
- GitHub Pages (free, simple, automatic)
- Netlify (free tier, automatic deployments)
- Vercel (free tier, automatic deployments)
- AWS S3 + CloudFront (if organization uses AWS)
- Any HTTP server (local development)

### Deployment Steps

1. **Build:** No build step required; single HTML file is ready to deploy
2. **Test:** Run manual test checklist (see Testing Strategy)
3. **Upload:** Upload HTML file to static hosting provider
4. **Verify:** Test app on live URL; confirm all features work
5. **Monitor:** Check for errors in browser console (no backend to monitor)

### Hosting Requirements

**HTTPS:** Required (all modern hosting providers default to HTTPS)  
**Domain:** Optional (can use hosting provider's default domain or custom domain)  
**CDN:** Optional (hosting providers typically include CDN for fast delivery)  
**SSL Certificate:** Automatic (provided by hosting provider)  

### Operational Burden

**Minimal:** No backend to maintain, no database to manage, no server to monitor.

**Maintenance Tasks:**
- Monitor page load time (Lighthouse)
- Check for browser compatibility issues (new browser versions)
- Update currency formatting if locale rules change (rare)
- Update supported currencies if needed (add/remove from list)

**Monitoring:**
- No backend monitoring needed
- Browser console logging for debugging (development only)
- No uptime monitoring needed (static file; 99.9%+ availability guaranteed by hosting provider)

### Rollback Strategy

**If bug is discovered post-launch:**
1. Revert to previous version of HTML file
2. Re-upload to hosting provider
3. Verify fix on live URL

**Version Control:**
- Store HTML file in Git repository
- Tag each release (v1.0, v1.0.1, etc.)
- Easy to revert to previous version if needed

### Future Scaling (Not MVP)

**If app becomes very popular:**
- Static hosting scales automatically (no backend to scale)
- CDN ensures fast delivery globally
- No database bottlenecks (no database)
- No API rate limiting (no API)

**Conclusion:** App is inherently scalable due to client-side architecture.

---

## OPEN QUESTIONS & ASSUMPTIONS

### Assumptions Made

**[ASSUMPTION 1] No Backend Required**
- Assumption: All calculations execute in the browser; no server-side logic needed
- Rationale: Tip calculation is stateless and simple; no data persistence beyond user preference
- Validation: Confirmed by PRD (no mention of server-side requirements)
- Risk: If future requirements add server-side logic (e.g., user accounts, bill history), this assumption breaks
- Mitigation: Document as MVP scope; plan for backend in v1.1 if needed

**[ASSUMPTION 2] No Authentication Required**
- Assumption: No login, no user accounts, no authentication
- Rationale: App is a utility tool; no need to identify users or protect data
- Validation: Confirmed by PRD (no mention of user accounts or login)
- Risk: If future requirements add user accounts (e.g., bill history, sharing), this assumption breaks
- Mitigation: Document as MVP scope; plan for auth in v1.1 if needed

**[ASSUMPTION 3] Banker's Rounding is Acceptable**
- Assumption: Rounding follows banker's rounding (round-half-to-even)
- Rationale: Standard in financial systems; minimizes bias
- Validation: Not explicitly stated in PRD; assumed based on "100% accuracy" requirement
- Risk: If users expect different rounding (e.g., always round up), this assumption breaks
- Mitigation: Document rounding rule in UI tooltip; gather user feedback post-launch

**[ASSUMPTION 4] No Currency Conversion**
- Assumption: App does not convert between currencies; user is responsible for converting bill amount
- Rationale: Adds complexity; currency exchange rates change constantly
- Validation: Implied by PRD (no mention of currency conversion)
- Risk: Users may expect automatic conversion (e.g., USD bill → EUR display)
- Mitigation: Document in UI that app does not convert; add to FAQ if needed

**[ASSUMPTION 5] localStorage is Sufficient for Persistence**
- Assumption: Browser localStorage is sufficient for persisting currency preference
- Rationale: Single preference value; no need for server-side storage
- Validation: Confirmed by PRD (no mention of server-side persistence)
- Risk: If users expect preferences to sync across devices, this assumption breaks
- Mitigation: Document as MVP scope; plan for cloud sync in v1.1 if needed

**[ASSUMPTION 6] Single HTML File Deployment**
- Assumption: App is deployed as a single HTML file (or minimal asset set)
- Rationale: Simplifies deployment; no build step required
- Validation: Confirmed by prototype profile (no build tool required)
- Risk: If app grows in complexity, single file may become unwieldy
- Mitigation: Plan for modular architecture in v1.1 if needed

### Open Questions for Product Team

**Q1: Rounding Behavior**
- Question: Should the app always round up (in user's favor) or use banker's rounding?
- Impact: Affects calculation accuracy and user trust
- Recommendation: Use banker's rounding (standard in finance); document in UI

**Q2: Bill Splitting**
- Question: Is bill splitting in MVP scope or P1 (post-launch)?
- Impact: Affects UI complexity and development time
- Recommendation: Keep out of MVP; add in v1.1 if usage data justifies

**Q3: Preset Tip Percentages**
- Question: Should the app include preset buttons (e.g., "15%", "18%", "20%")?
- Impact: Affects UI design and user experience
- Recommendation: Include in MVP (mentioned in PRD as "common scenarios"); add buttons for quick selection

**Q4: Tip History**
- Question: Should the app save calculation history?
- Impact: Requires server-side storage or more complex localStorage schema
- Recommendation: Keep out of MVP; add in v1.1 if users request it

**Q5: Offline PWA**
- Question: Should the app be a Progressive Web App (PWA) with offline support?
- Impact: Requires service worker; adds complexity
- Recommendation: Keep out of MVP; app already works offline after initial load; PWA can be added in v1.1

**Q6: Analytics**
- Question: Should the app track user behavior (e.g., which currencies are used most)?
- Impact: Requires analytics service; privacy policy update
- Recommendation: Keep out of MVP; add in v1.1 if business needs usage data

### Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| Rounding behavior doesn't match user expectations | Users lose trust; negative reviews | Medium | Document rounding rule in UI; gather feedback post-launch |
| localStorage unavailable (private browsing) | Currency preference not persisted | Low | Graceful degradation; default to USD; no error shown |
| Browser compatibility issues | App doesn't work on some browsers | Low | Test on all major browsers; use standard APIs only |
| Performance issues on slow networks | Users abandon app | Medium | Optimize bundle size; test on 4G; use Lighthouse |
| Calculation errors due to floating-point precision | Users lose trust | Low | Use banker's rounding; test edge cases; document precision limits |
| Scope creep (bill splitting, history, etc.) | MVP delayed; team overloaded | High | Explicitly document MVP scope; defer features to v1.1 |

---

## APPENDIX: ACCEPTANCE CRITERIA CHECKLIST

### Pre-Launch Checklist

**Functionality:**
- [ ] Bill amount input accepts valid numbers (0.01 to 999,999.99)
- [ ] Tip percentage input accepts valid percentages (0 to 100)
- [ ] Calculation updates in real-time as user types
- [ ] Tip amount displays correctly (calculated value, 2 decimals)
- [ ] Total bill displays correctly (bill + tip, 2 decimals)
- [ ] All calculations are mathematically accurate (no rounding errors)
- [ ] Invalid inputs show clear error messages
- [ ] Error messages clear when input becomes valid
- [ ] Currency selector displays all 10 supported currencies
- [ ] Currency selection persists across page reload
- [ ] All currencies format correctly (symbol, decimals, separators)
- [ ] Changing currency recalculates and reformats amounts

**Performance:**
- [ ] Page load time ≤2 seconds on 4G mobile (Lighthouse)
- [ ] Time-to-calculate ≤5 seconds from page load
- [ ] Keystroke-to-update latency ≤100ms
- [ ] Total bundle size ≤100KB gzipped

**Compatibility:**
- [ ] App works on Chrome (latest 2 versions)
- [ ] App works on Safari (latest 2 versions)
- [ ] App works on Firefox (latest 2 versions)
- [ ] App works on Edge (latest 2 versions)
- [ ] App works on mobile (iOS Safari, Chrome Android)
- [ ] App works on tablet (iPad, Android tablets)
- [ ] Responsive design (no horizontal scrolling)

**Accessibility:**
- [ ] All form inputs have associated labels
- [ ] Keyboard navigation works (Tab, Enter, arrow keys)
- [ ] Focus indicators visible on all interactive elements
- [ ] Color contrast ≥4.5:1 for all text
- [ ] Error messages announced by screen readers
- [ ] WAVE accessibility checker: No errors or contrast warnings

**Security & Privacy:**
- [ ] App served over HTTPS only
- [ ] No external API calls or third-party scripts
- [ ] No user data transmitted to server
- [ ] Input validation prevents injection attacks
- [ ] No console errors related to security

**Usability:**
- [ ] First-time user can complete calculation without help
- [ ] Results update in real-time (no "Calculate" button needed)
- [ ] Error messages are clear and actionable
- [ ] Mobile layout is responsive and readable
- [ ] No onboarding or tutorial required
- [ ] Currency preference persists across sessions

**Testing:**
- [ ] Manual test checklist completed (all scenarios pass)
- [ ] No console errors or warnings
- [ ] No calculation errors or edge case failures
- [ ] No browser compatibility issues

**Deployment:**
- [ ] HTML file uploaded to static hosting provider
- [ ] App accessible via public URL
- [ ] HTTPS enabled
- [ ] Page load time verified on live URL
- [ ] All features tested on live URL

**Documentation:**
- [ ] Rounding rule documented in code comments
- [ ] Currency formatting rules documented
- [ ] Deployment instructions documented
- [ ] Known limitations documented (no backend, no currency conversion, etc.)

---

## DOCUMENT SIGN-OFF

**Prepared By:** [Engineering Lead]  
**Reviewed By:** [Product Manager, QA Lead]  
**Approved By:** [Engineering Manager]  
**Date:** [Current Date]  
**Version:** 1.0  
**Status:** Ready for Implementation

---

**End of TRD.md**