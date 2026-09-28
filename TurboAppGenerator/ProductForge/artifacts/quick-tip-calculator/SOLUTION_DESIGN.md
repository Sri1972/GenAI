# SOLUTION DESIGN DOCUMENT
## Tip Calculator Web App

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Owner:** Principal Solutions Architect  
**Status:** Ready for Implementation  
**Audience:** Engineering Team, Product Management, QA

---

## TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Component Design](#component-design)
4. [Data Model & Persistence](#data-model--persistence)
5. [API & Calculation Contract](#api--calculation-contract)
6. [Security Design](#security-design)
7. [Scalability & Performance](#scalability--performance)
8. [Deployment Architecture](#deployment-architecture)
9. [Monitoring & Observability](#monitoring--observability)
10. [Error Handling & Validation](#error-handling--validation)
11. [Localization & Formatting](#localization--formatting)
12. [Testing Strategy](#testing-strategy)
13. [Assumptions & Open Questions](#assumptions--open-questions)
14. [Trade-Off Analysis](#trade-off-analysis)

---

## EXECUTIVE SUMMARY

### Product Overview
The Tip Calculator is a lightweight, client-side web application that enables users to instantly calculate tip amounts and total bills across multiple currencies. The application is designed for three primary personas: frequent diners (Sarah), service industry workers (Marcus), and budget-conscious travelers (Priya).

### Architectural Approach
This solution follows a **client-side-first, zero-backend architecture**:
- All calculations execute in the browser using vanilla JavaScript
- No server-side logic, API endpoints, or database required
- User preferences (currency selection) persist via browser `localStorage`
- Single self-contained HTML file deployment to static hosting
- Fully functional offline after initial page load

### Why This Architecture?
- **Simplicity:** Eliminates operational complexity (no server to deploy, scale, or monitor)
- **Performance:** No network latency for calculations; instant results
- **Reliability:** No backend failure points; app works offline
- **Cost:** Static file hosting is cheaper than managed infrastructure
- **Scope Fit:** Calculation logic is stateless; no multi-user coordination needed

### Key Design Decisions
| Decision | Rationale | Trade-Off |
|---|---|---|
| **No backend API** | Calculations are stateless; no persistence needed | Cannot add real-time collaboration or server-side analytics without refactoring |
| **Vanilla JS + Tailwind CSS** | Minimal dependencies; single HTML file deployment | No component reusability; larger file if more features added later |
| **Browser localStorage** | Persists currency preference; works offline | Limited to ~5-10MB quota; not suitable for large datasets |
| **Banker's rounding** | Minimizes systematic bias in financial calculations | Slightly less intuitive than round-half-up for non-technical users |
| **10 major currencies** | Covers ~80% of global transaction volume | Requires maintenance if new currencies added; not all currencies supported |

### Success Criteria (Technical)
- **Performance:** Page load ≤2 seconds on 4G mobile; time-to-calculate ≤5 seconds
- **Accuracy:** 100% calculation correctness with defined rounding behavior
- **Availability:** 99.9% uptime (static hosting SLA)
- **Usability:** ≥80% first-time user completion rate
- **Reliability:** Zero external API dependencies; fully functional offline

---

## ARCHITECTURE OVERVIEW

### System Context Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        User's Browser                            │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │         Tip Calculator SPA (Single HTML File)              │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Presentation Layer (HTML + Tailwind CSS)            │ │ │
│  │  │  ┌────────────────────────────────────────────────┐  │ │ │
│  │  │  │ • Currency Selector (dropdown)                 │  │ │ │
│  │  │  │ • Bill Amount Input (text field)               │  │ │ │
│  │  │  │ • Tip Percentage Input (text field)            │  │ │ │
│  │  │  │ • Results Display (read-only)                  │  │ │ │
│  │  │  │ • Error Messages (inline validation)           │  │ │ │
│  │  │  └────────────────────────────────────────────────┘  │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                        ↓                                   │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Business Logic Layer (Vanilla JavaScript)           │ │ │
│  │  │  ┌────────────────────────────────────────────────┐  │ │ │
│  │  │  │ • Input Validation Engine                      │  │ │ │
│  │  │  │ • Calculation Engine (tip + total)             │  │ │ │
│  │  │  │ • Rounding Engine (banker's rounding)          │  │ │ │
│  │  │  │ • Currency Formatting Engine                   │  │ │ │
│  │  │  │ • State Management (local component state)     │  │ │ │
│  │  │  └────────────────────────────────────────────────┘  │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  │                        ↓                                   │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Persistence Layer (Browser APIs)                    │ │ │
│  │  │  ┌────────────────────────────────────────────────┐  │ │ │
│  │  │  │ • localStorage: { selectedCurrency: "USD" }    │  │ │ │
│  │  │  │ • No IndexedDB, no cookies, no server calls    │  │ │ │
│  │  │  └────────────────────────────────────────────────┘  │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ✓ No external API calls                                        │
│  ✓ No backend dependency                                        │
│  ✓ Fully functional offline                                     │
│  ✓ Works in any modern browser (ES6+ support)                   │
└──────────────────────────────────────────────────────────────────┘
```

### Deployment Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Static File Hosting                      │
│  (GitHub Pages / Netlify / S3 / Local HTTP Server)          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  index.html (self-contained, ~80-100KB)              │  │
│  │  • Inline CSS (Tailwind utilities)                   │  │
│  │  • Inline JavaScript (calculation engine)            │  │
│  │  • Inline SVG icons (if any)                         │  │
│  │  • No external dependencies (except Tailwind CDN)    │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  CDN (optional, for Tailwind CSS if not inlined)           │
│  • Tailwind CSS v3+ from CDN                               │
│  • Cached globally; ~50KB gzipped                          │
└─────────────────────────────────────────────────────────────┘
         ↑
         │ HTTP GET /index.html
         │
    User Browser
```

### Data Flow Diagram

```
User Input (Bill Amount, Tip %)
         ↓
    ┌────────────────────────────────┐
    │  Input Validation Engine       │
    │  • Check numeric format        │
    │  • Check range (0.01-999999.99)│
    │  • Check precision (2 decimals)│
    └────────────────────────────────┘
         ↓
    [Valid?] ──No──→ Display Error Message
         │
        Yes
         ↓
    ┌────────────────────────────────┐
    │  Calculation Engine            │
    │  • tipAmount = bill × (tip% / 100)
    │  • totalBill = bill + tipAmount│
    │  • Keep full precision in memory
    └────────────────────────────────┘
         ↓
    ┌────────────────────────────────┐
    │  Rounding Engine               │
    │  • Apply banker's rounding     │
    │  • Round to currency precision │
    │  (USD/EUR: 2 decimals,         │
    │   JPY: 0 decimals, etc.)       │
    └────────────────────────────────┘
         ↓
    ┌────────────────────────────────┐
    │  Currency Formatting Engine    │
    │  • Apply locale-specific format│
    │  • Add currency symbol         │
    │  • Add thousands separator     │
    │  • Use Intl.NumberFormat API   │
    └────────────────────────────────┘
         ↓
    Display Results (Tip Amount + Total Bill)
         ↓
    [User changes currency?] ──Yes──→ Re-format & re-display
         │
        No
         ↓
    [User changes inputs?] ──Yes──→ Recalculate (back to validation)
         │
        No
         ↓
    [Page unload?] ──Yes──→ Save currency to localStorage
         │
        No
         ↓
    Idle (waiting for user input)
```

### Component Interaction Model

```
┌─────────────────────────────────────────────────────────────┐
│                      App Container                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  CurrencySelector Component                          │  │
│  │  • Dropdown with 10 currency options                 │  │
│  │  • onChange: Update state + localStorage             │  │
│  │  • Trigger: Re-format all displayed amounts          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  BillAmountInput Component                           │  │
│  │  • Text input, type="number"                         │  │
│  │  • onChange: Validate + trigger calculation          │  │
│  │  • Display: Inline error message if invalid          │  │
│  │  • State: billAmount, validationError               │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  TipPercentageInput Component                        │  │
│  │  • Text input, type="number"                         │  │
│  │  • onChange: Validate + trigger calculation          │  │
│  │  • Display: Inline error message if invalid          │  │
│  │  • State: tipPercentage, validationError            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ResultsDisplay Component                            │  │
│  │  • Read-only display of tipAmount + totalBill        │  │
│  │  • Formatted per selected currency                   │  │
│  │  • Hidden if inputs are invalid or empty             │  │
│  │  • Props: tipAmount, totalBill, currency             │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ResetButton Component (Optional)                    │  │
│  │  • onClick: Clear all inputs + errors                │  │
│  │  • Preserve currency selection                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## COMPONENT DESIGN

### Component Inventory

#### 1. **CurrencySelector Component**

**Responsibility:** Allow user to select a currency; persist selection; trigger re-formatting of all displayed amounts.

**Interfaces:**
- **Input Props:** None (reads from state)
- **Output Events:** `onCurrencyChange(currencyCode: string)`
- **State Managed:** `selectedCurrency` (string, e.g., "USD", "EUR", "GBP")
- **Side Effects:** 
  - Write to `localStorage` on change
  - Trigger recalculation/re-formatting of results display

**Behavior:**
- Dropdown (HTML `<select>`) with 10 currency options
- Default to "USD" on first load; restore from `localStorage` if available
- Changing currency immediately re-formats all displayed amounts (no page reload)
- Currency code persists across sessions

**Data Owned:**
- `selectedCurrency: string` (one of: USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD)

**Acceptance Criteria:**
- User can select any of 10 currencies from dropdown
- Selection persists across page reloads (via localStorage)
- Changing currency re-formats tip amount and total bill immediately
- Default currency is USD if localStorage is empty or unavailable

---

#### 2. **BillAmountInput Component**

**Responsibility:** Capture bill amount from user; validate input; trigger calculation on change.

**Interfaces:**
- **Input Props:** None (reads from state)
- **Output Events:** `onBillAmountChange(amount: string, isValid: boolean)`
- **State Managed:** `billAmount` (string, raw user input), `billAmountError` (string or null)
- **Side Effects:** Trigger calculation engine on valid input

**Behavior:**
- Text input field with `type="number"` (HTML5 numeric input)
- Accept values 0.01 to 999,999.99 with up to 2 decimal places
- Validate on every keystroke (onChange event)
- Display inline error message if input is invalid
- Clear error message as soon as user corrects input
- Do NOT auto-format input (let user type freely; format only on display)

**Validation Rules:**
- Must be numeric (reject letters, special characters except decimal point)
- Must be ≥0.01 (reject zero and negative numbers)
- Must be ≤999,999.99 (reject amounts that exceed reasonable bill size)
- Must have ≤2 decimal places (reject 0.001, 0.0001, etc.)
- Empty field is valid (no calculation shown, but no error)

**Data Owned:**
- `billAmount: string` (raw user input, e.g., "47.50")
- `billAmountError: string | null` (validation error message, if any)

**Acceptance Criteria:**
- User can type numeric values with decimal point
- Invalid input (letters, negative, >999999.99) shows error message
- Error clears when user corrects input
- Valid input triggers calculation immediately
- Empty field does not show error

---

#### 3. **TipPercentageInput Component**

**Responsibility:** Capture tip percentage from user; validate input; trigger calculation on change.

**Interfaces:**
- **Input Props:** None (reads from state)
- **Output Events:** `onTipPercentageChange(percentage: string, isValid: boolean)`
- **State Managed:** `tipPercentage` (string, raw user input), `tipPercentageError` (string or null)
- **Side Effects:** Trigger calculation engine on valid input

**Behavior:**
- Text input field with `type="number"` (HTML5 numeric input)
- Accept values 0 to 100 with up to 1 decimal place
- Validate on every keystroke (onChange event)
- Display inline error message if input is invalid
- Clear error message as soon as user corrects input
- Do NOT auto-format input (let user type freely; format only on display)

**Validation Rules:**
- Must be numeric (reject letters, special characters except decimal point)
- Must be ≥0 (zero is valid; represents no tip)
- Must be ≤100 (reject percentages >100%)
- Must have ≤1 decimal place (reject 15.25%, accept 15.2%)
- Empty field is valid (no calculation shown, but no error)

**Data Owned:**
- `tipPercentage: string` (raw user input, e.g., "18")
- `tipPercentageError: string | null` (validation error message, if any)

**Acceptance Criteria:**
- User can type numeric values with decimal point
- Invalid input (letters, negative, >100) shows error message
- Error clears when user corrects input
- Valid input triggers calculation immediately
- Empty field does not show error

---

#### 4. **ResultsDisplay Component**

**Responsibility:** Display calculated tip amount and total bill in user's selected currency; format according to locale rules.

**Interfaces:**
- **Input Props:** 
  - `tipAmount: number` (calculated, full precision)
  - `totalBill: number` (calculated, full precision)
  - `currency: string` (e.g., "USD", "EUR", "JPY")
  - `isValid: boolean` (whether inputs are valid)
- **Output Events:** None (read-only display)
- **State Managed:** None (all props passed from parent)
- **Side Effects:** None

**Behavior:**
- Display tip amount and total bill side-by-side or stacked (responsive)
- Format both amounts according to currency locale rules (symbol, decimal places, thousands separator)
- Use `Intl.NumberFormat` API for locale-aware formatting
- Hide results if either input is invalid or empty
- Large, high-contrast text for readability (≥24px on mobile)
- No user interaction (read-only)

**Data Owned:** None (stateless component)

**Formatting Rules (Specified in Localization Section):**
- USD: `$47.50` (symbol prefix, 2 decimals, comma thousands separator)
- EUR: `47,50 €` (symbol suffix, comma decimal separator, period thousands separator in some locales)
- GBP: `£47.50` (symbol prefix, 2 decimals)
- JPY: `¥4,750` (symbol prefix, 0 decimals, comma thousands separator)
- INR: `₹4,750.00` (symbol prefix, 2 decimals, Indian numbering system)
- CAD: `$47.50` (symbol prefix, 2 decimals)
- AUD: `$47.50` (symbol prefix, 2 decimals)
- CHF: `CHF 47.50` (symbol prefix, 2 decimals)
- MXN: `$47.50` (symbol prefix, 2 decimals)
- SGD: `$47.50` (symbol prefix, 2 decimals)

**Acceptance Criteria:**
- Results display only when both inputs are valid and non-empty
- Tip amount and total bill are formatted per currency locale rules
- Large, readable text (≥24px on mobile)
- No calculation errors or display glitches

---

#### 5. **ResetButton Component (Optional)**

**Responsibility:** Clear all user inputs and validation errors; preserve currency selection.

**Interfaces:**
- **Input Props:** None
- **Output Events:** `onReset()`
- **State Managed:** None (triggers parent state reset)
- **Side Effects:** Clear billAmount, tipPercentage, and all validation errors

**Behavior:**
- Button labeled "Clear" or "Reset"
- onClick: Clear all input fields and error messages
- Preserve currency selection (do NOT reset to USD)
- Results display disappears (since inputs are now empty)
- Focus returns to bill amount input (for accessibility)

**Data Owned:** None

**Acceptance Criteria:**
- Clicking reset clears all inputs and errors
- Currency selection is preserved
- Focus moves to bill amount input
- Results display is hidden

---

### State Management Architecture

**Approach:** Local component state (no global state manager needed)

**State Hierarchy:**
```
App (root)
├── selectedCurrency (string) — persisted to localStorage
├── billAmount (string) — raw user input
├── billAmountError (string | null)
├── tipPercentage (string) — raw user input
├── tipPercentageError (string | null)
├── tipAmount (number) — derived, not stored
├── totalBill (number) — derived, not stored
└── isValid (boolean) — derived, not stored
```

**State Transitions:**
- **On page load:** Restore `selectedCurrency` from localStorage; initialize other state to empty
- **On bill amount input:** Validate; update `billAmount` and `billAmountError`; recalculate if valid
- **On tip percentage input:** Validate; update `tipPercentage` and `tipPercentageError`; recalculate if valid
- **On currency change:** Update `selectedCurrency`; save to localStorage; re-format results
- **On reset:** Clear all inputs and errors; preserve currency

**Derived State (Computed, Never Stored):**
- `tipAmount = billAmount × (tipPercentage / 100)` — calculated on every input change
- `totalBill = billAmount + tipAmount` — calculated on every input change
- `isValid = billAmount > 0 && tipPercentage >= 0 && no validation errors` — computed for conditional rendering

**Why No Global State Manager?**
- Only 6 state variables; no complex interdependencies
- No multi-component state sharing (each component owns its own state)
- No async operations or side effects requiring middleware
- Redux/Zustand would add unnecessary complexity and bundle size

---

## DATA MODEL & PERSISTENCE

### Data Entities

#### 1. **Currency Configuration**

**Entity:** `CurrencyConfig`

**Purpose:** Define formatting rules for each supported currency.

**Attributes:**
- `code: string` — ISO 4217 currency code (e.g., "USD", "EUR", "JPY")
- `symbol: string` — Currency symbol (e.g., "$", "€", "¥")
- `locale: string` — BCP 47 language tag for `Intl.NumberFormat` (e.g., "en-US", "de-DE", "ja-JP")
- `decimalPlaces: number` — Number of decimal places (USD/EUR: 2, JPY: 0)
- `symbolPosition: string` — "prefix" or "suffix" (USD: prefix, EUR: suffix in some locales)

**Example Entries:**
```
{
  code: "USD",
  symbol: "$",
  locale: "en-US",
  decimalPlaces: 2,
  symbolPosition: "prefix"
}

{
  code: "JPY",
  symbol: "¥",
  locale: "ja-JP",
  decimalPlaces: 0,
  symbolPosition: "prefix"
}

{
  code: "EUR",
  symbol: "€",
  locale: "de-DE",
  decimalPlaces: 2,
  symbolPosition: "suffix"
}
```

**Storage:** Hardcoded in JavaScript (no database); loaded on app initialization.

**Relationships:** None (lookup table only).

---

#### 2. **User Preference**

**Entity:** `UserPreference`

**Purpose:** Persist user's currency selection across sessions.

**Attributes:**
- `selectedCurrency: string` — ISO 4217 currency code (e.g., "USD")
- `lastUpdated: ISO8601 timestamp` — When preference was last changed

**Storage:** Browser `localStorage` under key `"tipCalculator_selectedCurrency"`

**Persistence Rules:**
- Write to localStorage whenever user changes currency
- Read from localStorage on page load
- Default to "USD" if localStorage is empty or unavailable
- No expiration; persists indefinitely until user clears browser data

**Example localStorage Entry:**
```json
{
  "tipCalculator_selectedCurrency": "GBP",
  "tipCalculator_lastUpdated": "2024-01-15T14:30:00Z"
}
```

**Why localStorage?**
- Simple key-value storage; no schema needed
- Works offline
- ~5-10MB quota per domain (tip calculator uses <1KB)
- No server-side infrastructure required

**Why Not IndexedDB?**
- Overkill for a single preference value
- localStorage is simpler and sufficient

**Why Not Cookies?**
- Unnecessary HTTP overhead
- localStorage is more appropriate for client-side-only data

---

#### 3. **Calculation Result (Ephemeral)**

**Entity:** `CalculationResult`

**Purpose:** Represent the output of a tip calculation (not persisted).

**Attributes:**
- `billAmount: number` — Original bill amount (full precision)
- `tipPercentage: number` — Tip percentage (full precision)
- `tipAmount: number` — Calculated tip (banker's rounded to currency precision)
- `totalBill: number` — Calculated total (banker's rounded to currency precision)
- `currency: string` — Currency code (e.g., "USD")
- `calculatedAt: ISO8601 timestamp` — When calculation was performed

**Storage:** Memory only (not persisted); discarded on page unload.

**Lifetime:** Created on every valid input change; destroyed when user navigates away or closes tab.

**Why Not Persisted?**
- Calculation is ephemeral; no business value in storing history
- No multi-user coordination needed
- MVP scope does not include calculation history or analytics

**Future Extension:** If bill splitting or calculation history is added in v1.1+, this entity would be persisted to a backend database.

---

### Data Relationships

**Diagram:**
```
┌─────────────────────────────────────────────────────────────┐
│  CurrencyConfig (10 entries, hardcoded)                     │
│  ├─ code: "USD"                                             │
│  ├─ symbol: "$"                                             │
│  ├─ locale: "en-US"                                         │
│  ├─ decimalPlaces: 2                                        │
│  └─ symbolPosition: "prefix"                                │
└─────────────────────────────────────────────────────────────┘
         ↑
         │ Referenced by
         │
┌─────────────────────────────────────────────────────────────┐
│  UserPreference (1 entry, persisted to localStorage)        │
│  ├─ selectedCurrency: "USD" (FK to CurrencyConfig.code)    │
│  └─ lastUpdated: ISO8601 timestamp                          │
└─────────────────────────────────────────────────────────────┘
         ↑
         │ Used by
         │
┌─────────────────────────────────────────────────────────────┐
│  CalculationResult (ephemeral, memory only)                 │
│  ├─ billAmount: 47.50                                       │
│  ├─ tipPercentage: 18                                       │
│  ├─ tipAmount: 8.55 (formatted per CurrencyConfig)         │
│  ├─ totalBill: 56.05 (formatted per CurrencyConfig)        │
│  ├─ currency: "USD" (FK to CurrencyConfig.code)            │
│  └─ calculatedAt: ISO8601 timestamp                         │
└─────────────────────────────────────────────────────────────┘
```

**Cardinality:**
- CurrencyConfig: 1 (10 entries, static)
- UserPreference: 1 (per browser/user)
- CalculationResult: 0..N (ephemeral; multiple per session)

**Constraints:**
- `UserPreference.selectedCurrency` must reference a valid `CurrencyConfig.code`
- `CalculationResult.currency` must reference a valid `CurrencyConfig.code`
- No foreign key enforcement needed (all data is in-memory or localStorage)

---

## API & CALCULATION CONTRACT

### Calculation Engine Specification

**Purpose:** Define the exact behavior of the tip calculation algorithm, including rounding and precision rules. This specification serves as the contract for testing and future backend implementation.

**Inputs:**
- `billAmount: number` — Bill amount in decimal format (e.g., 47.50)
  - Valid range: 0.01 to 999,999.99
  - Precision: Up to 2 decimal places
- `tipPercentage: number` — Tip percentage (e.g., 18 for 18%)
  - Valid range: 0 to 100
  - Precision: Up to 1 decimal place
- `currency: string` — ISO 4217 currency code (e.g., "USD", "JPY")
  - Must be one of: USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD

**Outputs:**
- `tipAmount: number` — Calculated tip amount, banker's rounded to currency precision
- `totalBill: number` — Calculated total bill, banker's rounded to currency precision
- `formattedTipAmount: string` — Tip amount formatted per currency locale (e.g., "$8.55")
- `formattedTotalBill: string` — Total bill formatted per currency locale (e.g., "$56.05")

**Algorithm:**

```
Step 1: Validate Inputs
  IF billAmount < 0.01 OR billAmount > 999,999.99
    RETURN ValidationError("Bill amount must be between 0.01 and 999,999.99")
  IF tipPercentage < 0 OR tipPercentage > 100
    RETURN ValidationError("Tip percentage must be between 0 and 100")
  IF currency NOT IN [USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD]
    RETURN ValidationError("Unsupported currency")

Step 2: Calculate Tip Amount (Full Precision)
  tipAmountExact = billAmount × (tipPercentage / 100)
  // Example: 47.50 × (18 / 100) = 8.5518 (keep full precision in memory)

Step 3: Calculate Total Bill (Full Precision)
  totalBillExact = billAmount + tipAmountExact
  // Example: 47.50 + 8.5518 = 56.0518

Step 4: Determine Currency Precision
  decimalPlaces = CurrencyConfig[currency].decimalPlaces
  // Example: USD → 2 decimals, JPY → 0 decimals

Step 5: Apply Banker's Rounding
  tipAmount = BankersRound(tipAmountExact, decimalPlaces)
  totalBill = BankersRound(totalBillExact, decimalPlaces)
  // Banker's rounding: round to nearest even if exactly halfway
  // Example: 8.5518 → 8.55 (USD), 8.5 → 8 (banker's rounding)

Step 6: Format for Display
  formattedTipAmount = FormatCurrency(tipAmount, currency)
  formattedTotalBill = FormatCurrency(totalBill, currency)
  // Example: 8.55 → "$8.55" (USD), 8550 → "¥8,550" (JPY)

Step 7: Return Results
  RETURN {
    tipAmount: tipAmount,
    totalBill: totalBill,
    formattedTipAmount: formattedTipAmount,
    formattedTotalBill: formattedTotalBill,
    currency: currency
  }
```

**Rounding Rule: Banker's Rounding (Round-Half-to-Even)**

Banker's rounding minimizes systematic bias in financial calculations. It rounds to the nearest even number when the value is exactly halfway between two integers.

**Examples:**
- 8.5 → 8 (round to even)
- 8.55 → 8.56 (round to even, but 8.56 is not exactly halfway)
- 8.545 → 8.54 (round to even)
- 8.555 → 8.56 (round to even)
- 8.5518 → 8.55 (round to nearest, not exactly halfway)

**Why Banker's Rounding?**
- Reduces systematic bias compared to round-half-up (which always rounds 0.5 up)
- Standard in financial systems and accounting software
- Minimizes cumulative rounding errors across multiple transactions

**Implementation Note:** JavaScript's `Math.round()` uses round-half-away-from-zero, NOT banker's rounding. A custom rounding function must be implemented:

```
BankersRound(value, decimalPlaces):
  multiplier = 10 ^ decimalPlaces
  scaled = value × multiplier
  floor = Math.floor(scaled)
  remainder = scaled - floor
  
  IF remainder < 0.5
    RETURN floor / multiplier
  ELSE IF remainder > 0.5
    RETURN (floor + 1) / multiplier
  ELSE  // remainder == 0.5 (exactly halfway)
    IF floor % 2 == 0
      RETURN floor / multiplier  // round to even
    ELSE
      RETURN (floor + 1) / multiplier  // round to even
```

---

### Calculation Examples

**Example 1: USD, Standard Tip**
```
Input:
  billAmount: 47.50
  tipPercentage: 18
  currency: "USD"

Calculation:
  tipAmountExact = 47.50 × 0.18 = 8.5518
  totalBillExact = 47.50 + 8.5518 = 56.0518
  decimalPlaces = 2
  tipAmount = BankersRound(8.5518, 2) = 8.55
  totalBill = BankersRound(56.0518, 2) = 56.05

Output:
  tipAmount: 8.55
  totalBill: 56.05
  formattedTipAmount: "$8.55"
  formattedTotalBill: "$56.05"
```

**Example 2: JPY, No Decimals**
```
Input:
  billAmount: 5000
  tipPercentage: 15
  currency: "JPY"

Calculation:
  tipAmountExact = 5000 × 0.15 = 750
  totalBillExact = 5000 + 750 = 5750
  decimalPlaces = 0
  tipAmount = BankersRound(750, 0) = 750
  totalBill = BankersRound(5750, 0) = 5750

Output:
  tipAmount: 750
  totalBill: 5750
  formattedTipAmount: "¥750"
  formattedTotalBill: "¥5,750"
```

**Example 3: EUR, Banker's Rounding Edge Case**
```
Input:
  billAmount: 33.33
  tipPercentage: 15
  currency: "EUR"

Calculation:
  tipAmountExact = 33.33 × 0.15 = 4.9995
  totalBillExact = 33.33 + 4.9995 = 38.3295
  decimalPlaces = 2
  tipAmount = BankersRound(4.9995, 2) = 5.00 (round to even)
  totalBill = BankersRound(38.3295, 2) = 38.33

Output:
  tipAmount: 5.00
  totalBill: 38.33
  formattedTipAmount: "5,00 €" (German locale)
  formattedTotalBill: "38,33 €" (German locale)
```

---

### Input Validation Contract

**Purpose:** Define exact validation rules for user inputs.

**Bill Amount Validation:**
- **Type:** Numeric string or number
- **Range:** 0.01 to 999,999.99 (inclusive)
- **Precision:** Up to 2 decimal places
- **Rejection Rules:**
  - Negative numbers (e.g., "-10.00")
  - Zero or near-zero (e.g., "0", "0.00")
  - Amounts < 0.01 (e.g., "0.001")
  - Amounts > 999,999.99 (e.g., "1,000,000.00")
  - Non-numeric characters (e.g., "abc", "47.50a")
  - More than 2 decimal places (e.g., "47.501")
  - Empty string (valid; no calculation shown)
- **Error Messages:**
  - "Bill amount must be at least $0.01"
  - "Bill amount cannot exceed $999,999.99"
  - "Please enter a valid number"

**Tip Percentage Validation:**
- **Type:** Numeric string or number
- **Range:** 0 to 100 (inclusive)
- **Precision:** Up to 1 decimal place
- **Rejection Rules:**
  - Negative numbers (e.g., "-5")
  - Numbers > 100 (e.g., "150")
  - Non-numeric characters (e.g., "abc", "18%")
  - More than 1 decimal place (e.g., "18.25")
  - Empty string (valid; no calculation shown)
- **Error Messages:**
  - "Tip percentage must be between 0 and 100"
  - "Please enter a valid number"

**Currency Validation:**
- **Type:** String (ISO 4217 code)
- **Valid Values:** USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD
- **Rejection Rules:**
  - Any currency code not in the valid list
- **Error Messages:**
  - "Unsupported currency"

---

### Error Handling Contract

**Validation Error Response:**
```
{
  status: "error",
  code: "VALIDATION_ERROR",
  field: "billAmount" | "tipPercentage" | "currency",
  message: "Human-readable error message",
  value: "User-provided value"
}
```

**Calculation Error Response:**
```
{
  status: "error",
  code: "CALCULATION_ERROR",
  message: "An unexpected error occurred during calculation",
  details: "Technical error details (for logging)"
}
```

**Success Response:**
```
{
  status: "success",
  data: {
    billAmount: 47.50,
    tipPercentage: 18,
    tipAmount: 8.55,
    totalBill: 56.05,
    currency: "USD",
    formattedTipAmount: "$8.55",
    formattedTotalBill: "$56.05"
  }
}
```

---

## SECURITY DESIGN

### Threat Model

**Threat 1: Input Injection (XSS)**
- **Attack Vector:** User enters malicious JavaScript in bill amount or tip percentage field (e.g., `<script>alert('xss')</script>`)
- **Impact:** Malicious code executes in user's browser; could steal localStorage data or redirect to phishing site
- **Mitigation:**
  - Use HTML5 `type="number"` input fields (browser prevents non-numeric input)
  - Validate input server-side (in this case, client-side only; no backend)
  - Use `textContent` instead of `innerHTML` when displaying user input
  - Sanitize any user-provided data before rendering (though this app doesn't display user input)

**Threat 2: localStorage Tampering**
- **Attack Vector:** Attacker modifies localStorage to inject malicious currency code (e.g., `selectedCurrency: "<script>alert('xss')</script>"`)
- **Impact:** App crashes or displays unexpected behavior
- **Mitigation:**
  - Validate currency code against whitelist before using it
  - Default to "USD" if localStorage contains invalid currency
  - Never execute or eval() localStorage data

**Threat 3: Man-in-the-Middle (MITM) Attack**
- **Attack Vector:** Attacker intercepts HTTP traffic and modifies the HTML/CSS/JS
- **Impact:** Attacker could modify calculation logic to steal tip amounts or redirect to phishing site
- **Mitigation:**
  - Deploy app over HTTPS only (enforce via HTTP Strict-Transport-Security header)
  - Use Subresource Integrity (SRI) for any external CDN resources (e.g., Tailwind CSS)
  - Host on reputable static hosting provider (GitHub Pages, Netlify, etc.) that enforces HTTPS

**Threat 4: Calculation Manipulation**
- **Attack Vector:** Attacker modifies JavaScript to calculate incorrect tips (e.g., always round down)
- **Impact:** Service workers (Persona 2) lose trust in app; users underpay tips
- **Mitigation:**
  - Implement comprehensive unit tests for calculation engine
  - Document rounding rules explicitly (so users can verify)
  - Use banker's rounding consistently (no special cases)
  - Provide calculation transparency (show intermediate steps if needed)

**Threat 5: Privacy Leakage via localStorage**
- **Attack Vector:** Attacker gains access to user's device and reads localStorage
- **Impact:** Attacker learns user's preferred currency (low-value information)
- **Mitigation:**
  - localStorage is not encrypted; only store non-sensitive data (currency preference)
  - Do NOT store bill amounts, tip percentages, or calculation history
  - Inform users that localStorage is not encrypted (in privacy policy, if added)

---

### Authentication & Authorization

**Decision:** No authentication or authorization required.

**Rationale:**
- App is public; no user accounts or login needed
- No sensitive user data to protect (currency preference is non-sensitive)
- No multi-user coordination or access control
- PRD explicitly states no login requirement

**Consequence:** Any user can access the app; no per-user data isolation needed.

---

### Data Protection

**Data at Rest (localStorage):**
- **Data Stored:** `selectedCurrency` (string, e.g., "USD")
- **Sensitivity:** Non-sensitive (public information)
- **Protection:** None required (localStorage is not encrypted by default)
- **Retention:** Indefinite (until user clears browser data)
- **Deletion:** User can clear via browser settings or by clearing site data

**Data in Transit (HTTPS):**
- **Data Transmitted:** HTML, CSS, JavaScript files (no user data)
- **Protection:** HTTPS encryption (enforced by hosting provider)
- **Requirement:** All traffic must be over HTTPS; HTTP requests must redirect to HTTPS

**Data in Memory:**
- **Data Held:** billAmount, tipPercentage, tipAmount, totalBill (ephemeral)
- **Sensitivity:** Non-sensitive (user's own financial data)
- **Protection:** None required (data is discarded on page unload)
- **Lifetime:** Duration of user session only

---

### Content Security Policy (CSP)

**Recommended CSP Header:**
```
Content-Security-Policy: 
  default-src 'self'; 
  script-src 'self' 'unsafe-inline'; 
  style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; 
  img-src 'self' data:; 
  font-src 'self'; 
  connect-src 'none'; 
  frame-ancestors 'none'; 
  base-uri 'self'; 
  form-action 'self'
```

**Rationale:**
- `default-src 'self'`: Only allow resources from same origin
- `script-src 'self' 'unsafe-inline'`: Allow inline scripts (necessary for single-file app); no external scripts
- `style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com`: Allow inline styles and Tailwind CDN
- `connect-src 'none'`: No external API calls (app is fully client-side)
- `frame-ancestors 'none'`: Prevent clickjacking (app cannot be embedded in iframe)

---

### HTTPS & Transport Security

**Requirement:** All traffic must be over HTTPS.

**Implementation:**
- Configure hosting provider to enforce HTTPS (automatic redirects from HTTP to HTTPS)
- Set `Strict-Transport-Security` header: `max-age=31536000; includeSubDomains; preload`
- Use HSTS preload list to ensure HTTPS on first visit

**Why:** Prevents MITM attacks and ensures calculation logic cannot be tampered with.

---

### Subresource Integrity (SRI)

**If Using External CDN (e.g., Tailwind CSS):**

```html
<link 
  href="https://cdn.tailwindcss.com" 
  rel="stylesheet"
  integrity="sha384-[hash-value]"
  crossorigin="anonymous"
>
```

**Purpose:** Verify that CDN-hosted resources have not been tampered with.

**Implementation:**
- Generate SRI hash for Tailwind CSS file
- Include hash in `integrity` attribute
- Browser verifies hash before loading resource; rejects if mismatch

---

### Privacy Considerations

**Data Collection:** None (app does not collect or transmit user data).

**Cookies:** None used (app uses localStorage only).

**Third-Party Services:** None (app is fully self-contained).

**Privacy Policy:** Not required for MVP (no data collection). If analytics or third-party services are added in future versions, privacy policy must be updated.

**GDPR Compliance:** Not applicable (no personal data collected or processed).

---

## SCALABILITY & PERFORMANCE

### Performance Targets

| Metric | Target | Rationale |
|---|---|---|
| **Page Load Time** | ≤2 seconds on 4G mobile | Users at restaurant table need fast access |
| **Time-to-Calculate** | ≤5 seconds from page load to result display | Persona 1 (Sarah) needs result within 30 seconds total |
| **Time-to-Interactive** | ≤1 second | User can interact with form immediately |
| **First Input Delay (FID)** | ≤100ms | Input response feels instant |
| **Cumulative Layout Shift (CLS)** | <0.1 | No visual jank during interaction |
| **Bundle Size** | ≤100KB gzipped | Fast download on slow networks |

### Performance Optimization Strategy

**1. Minimize Bundle Size**
- Single self-contained HTML file (no separate CSS/JS files)
- Inline critical CSS (Tailwind utilities only)
- Inline JavaScript (calculation engine, state management)
- No external dependencies except Tailwind CSS CDN (optional)
- Remove unused Tailwind utilities via PurgeCSS or similar

**2. Optimize Asset Delivery**
- Serve HTML with gzip compression (hosting provider handles automatically)
- Use HTTP/2 or HTTP/3 for faster multiplexing
- Set long cache headers for static assets (if using separate files)
- Use CDN for Tailwind CSS (already cached globally)

**3. Optimize JavaScript Execution**
- Use vanilla JavaScript (no framework overhead)
- Avoid unnecessary DOM manipulation (batch updates)
- Debounce input events if needed (though calculation is instant, so not necessary)
- Use `requestAnimationFrame` for animations (if any)

**4. Optimize CSS**
- Use Tailwind CSS utility classes (no custom CSS)
- Inline critical CSS in `<head>` (Tailwind utilities)
- Defer non-critical CSS (none in this app)
- Use CSS Grid or Flexbox for responsive layout (no floats)

**5. Optimize Images**
- No images required for MVP (text-only interface)
- If icons added, use SVG (scalable, small file size)
- Use `<picture>` element for responsive images (if needed)

**6. Optimize Fonts**
- Use system fonts (no custom font downloads)
- If custom fonts needed, use `font-display: swap` for fast text rendering

**7. Optimize Network Requests**
- Zero external API calls (fully client-side)
- No third-party analytics or tracking
- No ads or promotional content

---

### Scalability Approach

**Horizontal Scaling:** Not applicable (static file hosting scales automatically).

**Vertical Scaling:** Not applicable (no server-side processing).

**Database Scaling:** Not applicable (no database).

**Caching Strategy:**
- **Browser Cache:** Static HTML file cached for 1 year (long TTL)
- **CDN Cache:** Tailwind CSS cached globally (already cached by CDN provider)
- **localStorage Cache:** User's currency preference cached indefinitely

**Rate Limiting:** Not applicable (no API endpoints).

**Load Balancing:** Not applicable (static file hosting provider handles load balancing automatically).

---

### Capacity Planning

**Expected Traffic:** Unknown (no analytics in MVP).

**Assumptions:**
- Assume 10,000 daily active users (conservative estimate for a utility app)
- Each user loads page once per session (5-10 sessions per day)
- Each session includes 3-5 calculations (average)
- No persistent data storage (calculations are ephemeral)

**Capacity Requirements:**
- **Bandwidth:** ~100MB/day (10,000 users × 100KB per page load × 10 sessions/day ÷ 1000)
  - Static hosting provider (GitHub Pages, Netlify, S3) can handle this easily
- **Storage:** <1MB (only HTML file; no database)
- **Compute:** Zero (static files; no server-side processing)

**Scaling Triggers:** None (static hosting scales automatically).

---

## DEPLOYMENT ARCHITECTURE

### Deployment Topology

```
┌─────────────────────────────────────────────────────────────┐
│                    Static File Hosting                      │
│  (GitHub Pages / Netlify / Vercel / AWS S3 + CloudFront)   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  index.html (self-contained, ~80-100KB)              │  │
│  │  • Inline CSS (Tailwind utilities)                   │  │
│  │  • Inline JavaScript (calculation engine)            │  │
│  │  • Inline SVG icons (if any)                         │  │
│  │  • Git commit SHA in HTML comment                    │  │
│  │  • Build timestamp in HTML comment                   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  CDN (optional, for Tailwind CSS if not inlined)           │
│  • Tailwind CSS v3+ from https://cdn.tailwindcss.com      │
│  • Cached globally; ~50KB gzipped                          │
│  • Subresource Integrity (SRI) hash for verification       │
│                                                             │
│  HTTPS Enforcement                                          │
│  • All traffic redirected from HTTP to HTTPS               │
│  • Strict-Transport-Security header set                    │
│  • HSTS preload list enabled                               │
└─────────────────────────────────────────────────────────────┘
         ↑
         │ HTTP GET /index.html (redirects to HTTPS)
         │
    User Browser (any device, any OS)
```

### Hosting Options

**Option 1: GitHub Pages (Recommended for MVP)**
- **Cost:** Free
- **Setup:** Push HTML file to `gh-pages` branch or `/docs` folder
- **HTTPS:** Automatic (GitHub-managed certificate)
- **CDN:** GitHub's global CDN
- **Deployment:** Automatic on push (if CI/CD configured)
- **Pros:** Free, simple, no configuration, automatic HTTPS
- **Cons:** Limited customization, no server-side logic

**Option 2: Netlify**
- **Cost:** Free tier (generous limits)
- **Setup:** Connect Git repo; automatic deployments on push
- **HTTPS:** Automatic (Let's Encrypt certificate)
- **CDN:** Netlify's global CDN
- **Deployment:** Automatic on push
- **Pros:** Easy setup, automatic deployments, good DX
- **Cons:** Requires Git repo, limited free tier

**Option 3: Vercel**
- **Cost:** Free tier (generous limits)
- **Setup:** Connect Git repo; automatic deployments on push
- **HTTPS:** Automatic (Let's Encrypt certificate)
- **CDN:** Vercel's global CDN
- **Deployment:** Automatic on push
- **Pros:** Fast, easy setup, good DX
- **Cons:** Requires Git repo, limited free tier

**Option 4: AWS S3 + CloudFront**
- **Cost:** Pay-per-use (cheap for static files)
- **Setup:** Upload HTML to S3; configure CloudFront distribution
- **HTTPS:** CloudFront with AWS Certificate Manager
- **CDN:** CloudFront global CDN
- **Deployment:** Manual upload or CI/CD pipeline
- **Pros:** Scalable, reliable, integrates with AWS ecosystem
- **Cons:** More complex setup, requires AWS account

**Option 5: Local HTTP Server (Development Only)**
- **Cost:** Free
- **Setup:** Run `python -m http.server 8000` or `npx http-server`
- **HTTPS:** Not available locally (use HTTP for dev)
- **CDN:** None (local only)
- **Deployment:** Not applicable (development only)
- **Pros:** Simple, no external dependencies
- **Cons:** Not suitable for production

**Recommendation:** Use GitHub Pages for MVP (free, simple, automatic HTTPS). Migrate to Netlify or Vercel if more features are added.

---

### Deployment Pipeline

**Trigger:** Push to `main` branch (or manual trigger)

**Pipeline Stages:**

**Stage 1: Lint & Validate (5 seconds)**
- HTML validation (W3C validator or similar)
- CSS validation (Tailwind classes exist)
- JavaScript syntax check (ESLint or Node `--check-syntax`)
- Accessibility check (axe-core or similar)

**Stage 2: Unit Tests (10 seconds)**
- Calculation engine tests (Jest or Vitest)
  - Test rounding edge cases (0.005, 0.015, etc.)
  - Test currency formatting (JPY, INR, EUR)
  - Test input validation (negative, >999999.99, non-numeric)
- Input validation tests
- Currency formatting tests

**Stage 3: Build (2 seconds)**
- Bundle HTML + CSS + JS into single file (or copy assets)
- Generate git commit SHA and timestamp
- Inject into HTML comment for traceability
- Minify CSS and JavaScript (optional, for size optimization)

**Stage 4: Deploy (3 seconds)**
- Upload to static host (GitHub Pages, S3, Netlify, etc.)
- Invalidate CDN cache (if applicable)
- Verify deployment (HTTP 200, content-length matches)

**Stage 5: Smoke Test (5 seconds)**
- Load deployed URL in headless browser
- Verify page renders correctly
- Verify calculation works (test case: $47.50 @ 18% = $56.05)
- Verify currency selector works
- Verify localStorage works

**Total Pipeline Time:** ~25 seconds

---

### Rollback Strategy

**Rollback Trigger:** Deployment fails smoke test or production issue detected.

**Rollback Process:**
1. Revert to previous commit in Git
2. Re-run deployment pipeline
3. Verify smoke tests pass
4. Notify team of rollback

**Rollback Time:** ~5 minutes (including verification)

**Prevention:** Comprehensive testing before merge to `main` branch.

---

### Environment Configuration

**Development Environment:**
- Local HTTP server (Python or Node)
- No HTTPS (use HTTP for dev)
- Console logging enabled
- No minification (for debugging)

**Staging Environment (Optional):**
- Same as production (static hosting)
- Separate URL (e.g., `staging.tipCalculator.com`)
- Used for final testing before production release

**Production Environment:**
- Static file hosting (GitHub Pages, Netlify, etc.)
- HTTPS enforced
- Console logging disabled (or minimal)
- Minified CSS and JavaScript
- Long cache headers (1 year TTL)

---

## MONITORING & OBSERVABILITY

### Observability Strategy

**Approach:** Minimal observability for MVP (static file, no backend).

**Logging:**
- **Development:** Console logging enabled (for debugging)
- **Production:** Console logging disabled (or minimal)
- **What to Log:**
  - Calculation inputs and results (development only)
  - Validation errors (development only)
  - localStorage read/write operations (development only)
  - Browser compatibility issues (if any)

**Metrics:**
- **No server-side metrics** (no backend to monitor)
- **Client-side metrics** (optional, for future analytics):
  - Page load time
  - Time-to-calculate
  - Calculation accuracy (via unit tests)
  - Currency selection distribution
  - Error rates (validation errors, calculation errors)

**Tracing:**
- **No distributed tracing** (single-page app, no external services)
- **Browser DevTools:** Use for performance profiling during development

**Alerting:**
- **No alerts** (no backend to fail)
- **Deployment alerts:** Notify team if deployment fails

---

### Monitoring Checklist

**Pre-Deployment:**
- [ ] Page load time ≤2 seconds on 4G mobile (test via Lighthouse)
- [ ] Bundle size ≤100KB gzipped (test via webpack-bundle-analyzer or similar)
- [ ] All unit tests pass (calculation, validation, formatting)
- [ ] Smoke tests pass (page renders, calculation works, currency selector works)
- [ ] Accessibility tests pass (axe-core)
- [ ] HTTPS enforced (test via curl or browser)
- [ ] CSP header set correctly (test via browser DevTools)
- [ ] SRI hash correct (if using external CDN)

**Post-Deployment:**
- [ ] Verify deployment URL is accessible (HTTP 200)
- [ ] Verify HTTPS redirect works (HTTP → HTTPS)
- [ ] Verify page renders correctly (visual inspection)
- [ ] Verify calculation works (test case: $47.50 @ 18% = $56.05)
- [ ] Verify currency selector works (test all 10 currencies)
- [ ] Verify localStorage works (test currency persistence)
- [ ] Verify offline functionality (test in DevTools offline mode)
- [ ] Verify mobile responsiveness (test on multiple devices)

---

### Analytics (Future)

**Out of Scope for MVP:** No analytics or tracking.

**Future Considerations (v1.1+):**
- Page view count
- Calculation frequency
- Currency selection distribution
- Error rates
- User retention (return visits)
- Device/browser distribution

**Privacy Implications:** If analytics are added, privacy policy must be updated and user consent obtained (GDPR, CCPA).

---

## ERROR HANDLING & VALIDATION

### Input Validation Rules

**Bill Amount Validation:**

| Rule | Valid | Invalid | Error Message |
|---|---|---|---|
| **Type** | Numeric | Letters, symbols (except `.`) | "Please enter a valid number" |
| **Range** | 0.01 to 999,999.99 | <0.01 or >999,999.99 | "Bill amount must be between $0.01 and $999,999.99" |
| **Precision** | Up to 2 decimals | 3+ decimals (e.g., 47.501) | "Bill amount can have at most 2 decimal places" |
| **Sign** | Positive | Negative (e.g., -10) | "Bill amount must be positive" |
| **Empty** | Valid (no calc shown) | N/A | N/A |

**Tip Percentage Validation:**

| Rule | Valid | Invalid | Error Message |
|---|---|---|---|
| **Type** | Numeric | Letters, symbols (except `.`) | "Please enter a valid number" |
| **Range** | 0 to 100 | <0 or >100 | "Tip percentage must be between 0 and 100" |
| **Precision** | Up to 1 decimal | 2+ decimals (e.g., 18.25) | "Tip percentage can have at most 1 decimal place" |
| **Sign** | Non-negative | Negative (e.g., -5) | "Tip percentage must be non-negative" |
| **Empty** | Valid (no calc shown) | N/A | N/A |

**Currency Validation:**

| Rule | Valid | Invalid | Error Message |
|---|---|---|---|
| **Value** | USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD | Any other value | "Unsupported currency" |
| **Type** | String | N/A | N/A |

---

### Error Handling Strategy

**Validation Error Handling:**
1. User enters invalid input (e.g., "abc" in bill amount field)
2. Validation engine detects error
3. Display inline error message below input field
4. Highlight input field with red border (visual feedback)
5. Hide results display (since calculation cannot proceed)
6. Clear error message as soon as user corrects input

**Calculation Error Handling:**
1. Calculation engine encounters unexpected error (e.g., division by zero)
2. Log error to console (development only)
3. Display generic error message to user: "An unexpected error occurred. Please try again."
4. Do NOT display technical error details to user
5. Provide "Reset" button to clear all inputs and start over

**localStorage Error Handling:**
1. App attempts to read currency preference from localStorage
2. localStorage is unavailable (e.g., private browsing mode, quota exceeded)
3. Default to "USD" (no error shown)
4. App continues to function normally
5. Graceful degradation (user can still select currency manually)

**Browser Compatibility Error Handling:**
1. App detects unsupported browser (e.g., IE 11)
2. Display message: "Your browser is not supported. Please use a modern browser (Chrome, Firefox, Safari, Edge)."
3. Provide link to browser download page
4. App may not function correctly in unsupported browser

---

### Error Recovery

**User-Recoverable Errors:**
- Invalid input: User corrects input; error clears automatically
- Calculation error: User clicks "Reset" button; all inputs cleared
- localStorage unavailable: User can still use app; currency preference not persisted

**System-Level Errors:**
- Deployment fails: Rollback to previous version (automatic via CI/CD)
- Static hosting unavailable: Failover to backup hosting (if configured)
- CDN unavailable: Fallback to inline CSS (if Tailwind CSS is inlined)

---

## LOCALIZATION & FORMATTING

### Supported Currencies

| Currency | Code | Symbol | Locale | Decimals | Example |
|---|---|---|---|---|---|
| US Dollar | USD | $ | en-US | 2 | $47.50 |
| Euro | EUR | € | de-DE | 2 | 47,50 € |
| British Pound | GBP | £ | en-GB | 2 | £47.50 |
| Japanese Yen | JPY | ¥ | ja-JP | 0 | ¥4,750 |
| Canadian Dollar | CAD | $ | en-CA | 2 | $47.50 |
| Australian Dollar | AUD | $ | en-AU | 2 | $47.50 |
| Swiss Franc | CHF | CHF | de-CH | 2 | CHF 47.50 |
| Indian Rupee | INR | ₹ | en-IN | 2 | ₹47.50 |
| Mexican Peso | MXN | $ | es-MX | 2 | $47.50 |
| Singapore Dollar | SGD | $ | en-SG | 2 | $47.50 |

### Formatting Rules

**Using `Intl.NumberFormat` API:**

The app uses the browser's built-in `Intl.NumberFormat` API for locale-aware formatting. This ensures correct symbol placement, decimal separators, and thousands separators per locale.

**Example Implementation:**
```
formatter = new Intl.NumberFormat(locale, {
  style: 'currency',
  currency: currencyCode,
  minimumFractionDigits: decimalPlaces,
  maximumFractionDigits: decimalPlaces
})

formattedAmount = formatter.format(amount)
```

**Formatting Examples:**

| Currency | Amount | Formatted |
|---|---|---|
| USD | 47.50 | $47.50 |
| EUR (de-DE) | 47| EUR (de-DE) | 47.50 | 47,50 € |
| EUR (fr-FR) | 47.50 | 47,50 € |
| GBP | 47.50 | £47.50 |
| JPY | 4750 | ¥4,750 |
| INR | 47.50 | ₹47.50 |
| CHF | 47.50 | CHF 47.50 |
| MXN | 47.50 | $47.50 |
| SGD | 47.50 | $47.50 |

**Decimal Place Rules:**
- USD, EUR, GBP, CAD, AUD, CHF, INR, MXN, SGD: 2 decimal places
- JPY: 0 decimal places (no cents)

**Thousands Separator Rules:**
- USD, GBP, JPY, CAD, AUD, INR, MXN, SGD: Comma (,) as thousands separator
- EUR (de-DE, fr-FR): Period (.) or space as thousands separator (locale-dependent)
- CHF: Apostrophe (') or period (.) as thousands separator (locale-dependent)

**Why `Intl.NumberFormat`?**
- Built-in browser API (no external library needed)
- Respects user's browser locale settings
- Handles all edge cases (symbol placement, separators, decimals)
- Automatically updated when browser locale changes
- No maintenance burden (browser vendor maintains)

---

### Locale Selection

**Default Locale:** `en-US` (US English)

**Locale Mapping:**
- USD → `en-US`
- EUR → `de-DE` (German; can be overridden per user preference)
- GBP → `en-GB` (British English)
- JPY → `ja-JP` (Japanese)
- CAD → `en-CA` (Canadian English)
- AUD → `en-AU` (Australian English)
- CHF → `de-CH` (Swiss German)
- INR → `en-IN` (Indian English)
- MXN → `es-MX` (Mexican Spanish)
- SGD → `en-SG` (Singapore English)

**Rationale:** Each currency is mapped to a locale that uses that currency natively. This ensures correct formatting conventions.

**Future Enhancement:** Allow users to override locale per currency (e.g., EUR in French locale instead of German).

---

### Right-to-Left (RTL) Language Support

**Out of Scope for MVP:** No RTL language support.

**Rationale:**
- App is English-only (no translations)
- Supported currencies (USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD) are used in LTR countries
- RTL support would require UI redesign and testing

**Future Enhancement:** If app is translated to Arabic or Hebrew, RTL support must be added.

---

## TESTING STRATEGY

### Test Categories

#### 1. Unit Tests (Calculation Engine)

**Purpose:** Verify calculation accuracy and rounding behavior.

**Test Framework:** Jest or Vitest

**Test Cases:**

**Calculation Accuracy:**
- Standard tip calculation: $47.50 @ 18% = $8.55 tip, $56.05 total
- Zero tip: $47.50 @ 0% = $0.00 tip, $47.50 total
- 100% tip: $47.50 @ 100% = $47.50 tip, $95.00 total
- Small amount: $0.01 @ 50% = $0.01 tip (banker's rounding), $0.02 total
- Large amount: $999,999.99 @ 99% = $989,999.99 tip, $1,989,999.98 total
- Decimal tip percentage: $47.50 @ 18.5% = $8.78 tip, $56.28 total

**Banker's Rounding Edge Cases:**
- 8.5 → 8 (round to even)
- 8.55 → 8.56 (round to even, but 8.56 is not exactly halfway)
- 8.545 → 8.54 (round to even)
- 8.555 → 8.56 (round to even)
- 8.5518 → 8.55 (round to nearest, not exactly halfway)

**Currency Formatting:**
- USD: 8.55 → "$8.55"
- JPY: 8550 → "¥8,550"
- EUR (de-DE): 8.55 → "8,55 €"
- INR: 8.55 → "₹8.55"

**Input Validation:**
- Valid: "47.50", "0.01", "999999.99"
- Invalid: "-10", "abc", "47.501", "1000000"
- Empty: "" (valid, no calculation)

---

#### 2. Integration Tests (Component Interaction)

**Purpose:** Verify components work together correctly.

**Test Framework:** Jest with DOM testing library (e.g., `@testing-library/dom`)

**Test Cases:**

**User Input Flow:**
1. User enters bill amount "47.50"
2. User enters tip percentage "18"
3. Results display shows "$8.55" and "$56.05"
4. User changes currency to "GBP"
5. Results display shows "£8.55" and "£56.05"
6. User clicks reset button
7. All inputs cleared; results hidden

**Error Handling:**
1. User enters invalid bill amount "abc"
2. Error message displays: "Please enter a valid number"
3. Results hidden
4. User corrects input to "47.50"
5. Error message clears; results display

**localStorage Persistence:**
1. User selects currency "EUR"
2. Page reloads
3. Currency selector shows "EUR" (restored from localStorage)
4. User enters calculation; results display in EUR format

---

#### 3. End-to-End Tests (User Workflows)

**Purpose:** Verify complete user workflows from page load to result display.

**Test Framework:** Playwright or Cypress

**Test Cases:**

**Workflow 1: Quick Calculation (Persona 1 - Sarah)**
1. Load page
2. Enter bill amount "47.50"
3. Enter tip percentage "18"
4. Verify results display: "$8.55" and "$56.05"
5. Verify page load time ≤2 seconds
6. Verify time-to-calculate ≤5 seconds

**Workflow 2: Multi-Currency Calculation (Persona 3 - Priya)**
1. Load page
2. Select currency "GBP"
3. Enter bill amount "47.50"
4. Enter tip percentage "18"
5. Verify results display: "£8.55" and "£56.05"
6. Verify currency persists on page reload

**Workflow 3: Error Recovery (Persona 2 - Marcus)**
1. Load page
2. Enter invalid bill amount "abc"
3. Verify error message displays
4. Correct input to "47.50"
5. Verify error clears and results display
6. Verify calculation accuracy

**Workflow 4: Offline Functionality**
1. Load page
2. Enter calculation
3. Verify results display
4. Disable network (DevTools offline mode)
5. Reload page
6. Verify page loads and calculation works offline

---

#### 4. Performance Tests

**Purpose:** Verify performance targets are met.

**Test Framework:** Lighthouse, WebPageTest, or similar

**Test Cases:**

**Page Load Time:**
- Target: ≤2 seconds on 4G mobile
- Test: Load page on simulated 4G connection
- Measure: Time to First Contentful Paint (FCP), Largest Contentful Paint (LCP)

**Time-to-Interactive:**
- Target: ≤1 second
- Test: Load page and measure time until user can interact
- Measure: Time to Interactive (TTI)

**Bundle Size:**
- Target: ≤100KB gzipped
- Test: Measure HTML file size (gzipped)
- Measure: Total bytes transferred

**First Input Delay (FID):**
- Target: ≤100ms
- Test: Measure delay between user input and response
- Measure: FID metric via Lighthouse

**Cumulative Layout Shift (CLS):**
- Target: <0.1
- Test: Measure visual stability during interaction
- Measure: CLS metric via Lighthouse

---

#### 5. Accessibility Tests

**Purpose:** Verify app is accessible to users with disabilities.

**Test Framework:** axe-core, WAVE, or similar

**Test Cases:**

**WCAG 2.1 Level AA Compliance:**
- [ ] All form inputs have associated labels
- [ ] Color contrast ratio ≥4.5:1 for text
- [ ] Interactive elements have ≥44px touch target size
- [ ] Keyboard navigation works (Tab, Enter, Escape)
- [ ] Screen reader announces form labels and errors
- [ ] Focus indicator visible on all interactive elements
- [ ] No keyboard traps
- [ ] Page structure is semantic (headings, landmarks)

**Specific Tests:**
- [ ] Bill amount input: Label visible, error announced by screen reader
- [ ] Tip percentage input: Label visible, error announced by screen reader
- [ ] Currency selector: Dropdown accessible via keyboard
- [ ] Results display: Announced by screen reader
- [ ] Reset button: Keyboard accessible, focus visible

---

#### 6. Browser Compatibility Tests

**Purpose:** Verify app works across major browsers.

**Test Browsers:**
- Chrome (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions)
- Edge (latest 2 versions)
- Mobile Safari (iOS 14+)
- Chrome Mobile (Android 10+)

**Test Cases:**
- [ ] Page loads without errors
- [ ] Calculation works correctly
- [ ] Currency formatting works correctly
- [ ] localStorage works (or graceful fallback)
- [ ] Responsive design works on mobile
- [ ] Touch interactions work on mobile

---

#### 7. Security Tests

**Purpose:** Verify app is secure against common attacks.

**Test Cases:**

**XSS Prevention:**
- [ ] Enter `<script>alert('xss')</script>` in bill amount field
- [ ] Verify script does NOT execute
- [ ] Verify error message displays instead

**localStorage Tampering:**
- [ ] Manually set localStorage to invalid currency: `selectedCurrency: "<script>alert('xss')</script>"`
- [ ] Reload page
- [ ] Verify app defaults to USD (graceful fallback)
- [ ] Verify no error or crash

**HTTPS Enforcement:**
- [ ] Load page over HTTP
- [ ] Verify redirect to HTTPS
- [ ] Verify Strict-Transport-Security header set

**CSP Compliance:**
- [ ] Load page
- [ ] Verify no CSP violations in console
- [ ] Verify external scripts blocked (if any)

---

### Test Execution Plan

**Pre-Commit (Local):**
- Run unit tests (Jest)
- Run linter (ESLint)
- Run accessibility checks (axe-core)

**Pre-Merge (CI/CD):**
- Run all unit tests
- Run integration tests
- Run accessibility checks
- Run performance tests (Lighthouse)
- Run security tests

**Pre-Deployment (Staging):**
- Run end-to-end tests (Playwright)
- Run browser compatibility tests
- Manual smoke test (visual inspection)

**Post-Deployment (Production):**
- Run smoke tests (automated)
- Manual verification (visual inspection)
- Monitor error rates (console errors)

---

### Test Coverage Goals

| Category | Target Coverage | Rationale |
|---|---|---|
| **Calculation Engine** | 100% | Critical path; must be 100% accurate |
| **Input Validation** | 100% | All edge cases must be tested |
| **Currency Formatting** | 100% | All 10 currencies must format correctly |
| **Component Logic** | ≥90% | Most code paths covered |
| **Error Handling** | ≥90% | Most error scenarios covered |
| **Overall** | ≥85% | Reasonable coverage for MVP |

---

## ASSUMPTIONS & OPEN QUESTIONS

### Assumptions

**[ASSUMPTION 1] Browser Support**
- Assumption: App targets modern browsers (ES6+ support)
- Browsers: Chrome, Firefox, Safari, Edge (latest 2 versions)
- Excluded: Internet Explorer 11 and older
- Rationale: IE11 is end-of-life; supporting it adds complexity without benefit
- Validation: Test on target browsers before release

**[ASSUMPTION 2] Tailwind CSS Delivery**
- Assumption: Tailwind CSS delivered via CDN (https://cdn.tailwindcss.com)
- Alternative: Inline Tailwind CSS in HTML file (no CDN dependency)
- Rationale: CDN reduces HTML file size; trade-off is external dependency
- Validation: Test both approaches; choose based on performance metrics

**[ASSUMPTION 3] localStorage Availability**
- Assumption: Browser supports localStorage (ES5 feature, widely available)
- Fallback: If localStorage unavailable, default to USD; no error shown
- Rationale: Graceful degradation; app still functions without persistence
- Validation: Test in private browsing mode (localStorage disabled)

**[ASSUMPTION 4] Intl.NumberFormat Support**
- Assumption: Browser supports `Intl.NumberFormat` API (ES6 feature, widely available)
- Fallback: If unavailable, use basic formatting (e.g., "$47.50" without locale rules)
- Rationale: Graceful degradation; app still functions with basic formatting
- Validation: Test on older browsers (if supporting IE11 in future)

**[ASSUMPTION 5] No Backend Required**
- Assumption: All calculations execute client-side; no server-side logic needed
- Rationale: Calculation is stateless; no multi-user coordination needed
- Validation: Confirm with product team that bill splitting and shared calculations are NOT in MVP scope

**[ASSUMPTION 6] No Authentication Required**
- Assumption: App is public; no login or user accounts needed
- Rationale: PRD explicitly states no authentication requirement
- Validation: Confirm with product team that user accounts are NOT in MVP scope

**[ASSUMPTION 7] No Data Persistence Beyond localStorage**
- Assumption: Only currency preference persisted; no calculation history or user data stored
- Rationale: MVP scope does not include history or analytics
- Validation: Confirm with product team that calculation history is NOT in MVP scope

**[ASSUMPTION 8] 10 Currencies Sufficient**
- Assumption: Supporting 10 major currencies covers ~80% of use cases
- Rationale: Covers USD, EUR, GBP, JPY, CAD, AUD, CHF, INR, MXN, SGD
- Validation: Confirm with product team that other currencies are NOT required for MVP

**[ASSUMPTION 9] Banker's Rounding Acceptable**
- Assumption: Banker's rounding (round-half-to-even) is acceptable for financial calculations
- Rationale: Standard in accounting; minimizes systematic bias
- Validation: Confirm with product team and service workers (Persona 2) that this rounding rule is acceptable

**[ASSUMPTION 10] Static File Hosting Sufficient**
- Assumption: Static file hosting (GitHub Pages, Netlify, etc.) meets availability and performance requirements
- Rationale: 99.9% uptime SLA; global CDN; no server-side logic needed
- Validation: Confirm with DevOps team that static hosting meets requirements

---

### Open Questions

**Q1: Should the app support bill splitting (dividing total among multiple people)?**
- **Impact:** Requires additional UI component and calculation logic
- **Scope:** Out of scope for MVP; can be added in v1.1
- **Decision Needed:** Confirm with product team

**Q2: Should the app support preset tip percentages (e.g., buttons for 15%, 18%, 20%)?**
- **Impact:** Reduces user input; speeds up calculation for common scenarios
- **Scope:** Out of scope for MVP; can be added in v1.1
- **Decision Needed:** Confirm with product team; check if Persona 1 (Sarah) would benefit

**Q3: Should the app support calculation history (showing past calculations)?**
- **Impact:** Requires localStorage persistence and UI to display history
- **Scope:** Out of scope for MVP; can be added in v1.1
- **Decision Needed:** Confirm with product team; check if Persona 2 (Marcus) would benefit

**Q4: Should the app support custom tip percentages (user-defined, not just 0-100)?**
- **Impact:** Validation logic already supports 0-100; no additional work needed
- **Scope:** In scope; already supported
- **Decision Needed:** None; already implemented

**Q5: Should the app support offline-first PWA (Progressive Web App) features?**
- **Impact:** Requires service worker registration and manifest file
- **Scope:** Out of scope for MVP; app already works offline (static file)
- **Decision Needed:** Confirm with product team; check if Persona 3 (Priya) needs PWA features

**Q6: Should the app support dark mode?**
- **Impact:** Requires additional CSS and toggle UI
- **Scope:** Out of scope for MVP; can be added in v1.1
- **Decision Needed:** Confirm with product team; check if users prefer dark mode

**Q7: Should the app support multiple languages (i18n)?**
- **Impact:** Requires translation files and language selector
- **Scope:** Out of scope for MVP; English-only for now
- **Decision Needed:** Confirm with product team; check if international users need translations

**Q8: Should the app support analytics (tracking user behavior)?**
- **Impact:** Requires third-party analytics service (e.g., Google Analytics)
- **Scope:** Out of scope for MVP; can be added in v1.1
- **Privacy Implication:** Requires privacy policy update and user consent
- **Decision Needed:** Confirm with product team and legal team

**Q9: Should the app support sharing calculations (e.g., via URL or QR code)?**
- **Impact:** Requires URL encoding of calculation parameters
- **Scope:** Out of scope for MVP; can be added in v1.1
- **Decision Needed:** Confirm with product team; check if Persona 2 (Marcus) would benefit

**Q10: What is the target audience for the app (geographic region)?**
- **Impact:** Affects currency selection, language support, and localization
- **Scope:** Global audience assumed; 10 major currencies support ~80% of use cases
- **Decision Needed:** Confirm with product team; check if specific regions are prioritized

---

## TRADE-OFF ANALYSIS

### Architecture Trade-Offs

#### Trade-Off 1: Client-Side vs. Server-Side Calculation

**Option A: Client-Side (Chosen)**
- **Pros:**
  - No backend infrastructure needed
  - Instant calculation (no network latency)
  - Works offline
  - Lower operational cost
  - Simpler deployment
- **Cons:**
  - Calculation logic exposed in browser (not a security issue for this app)
  - Cannot add server-side features (analytics, history) without refactoring
  - Rounding logic must be duplicated if backend added later

**Option B: Server-Side**
- **Pros:**
  - Centralized calculation logic
  - Can add server-side features (analytics, history) easily
  - Easier to update calculation logic (no client-side deployment)
- **Cons:**
  - Requires backend infrastructure (server, database, API)
  - Network latency (slower calculation)
  - Doesn't work offline
  - Higher operational cost
  - More complex deployment

**Decision:** Client-side calculation chosen for MVP. If server-side features are needed in v1.1+, calculation logic can be moved to backend with minimal refactoring.

---

#### Trade-Off 2: Framework vs. Vanilla JavaScript

**Option A: Vanilla JavaScript (Chosen)**
- **Pros:**
  - No framework overhead (~40KB for React)
  - Single HTML file deployment
  - Faster page load
  - Simpler codebase
  - No build step required
- **Cons:**
  - No component reusability
  - Manual DOM manipulation
  - No state management library
  - Harder to scale if more features added

**Option B: React + Vite**
- **Pros:**
  - Component reusability
  - Built-in state management (hooks)
  - Easier to add features
  - Better developer experience
- **Cons:**
  - Framework overhead (~40KB gzipped)
  - Build step required (Vite)
  - More complex deployment
  - Slower page load

**Decision:** Vanilla JavaScript chosen for MVP. If app grows significantly (bill splitting, history, etc.), React can be introduced in v1.1+ with minimal refactoring.

---

#### Trade-Off 3: localStorage vs. IndexedDB

**Option A: localStorage (Chosen)**
- **Pros:**
  - Simple API (key-value store)
  - Sufficient for single preference value
  - Works in all modern browsers
  - No schema needed
- **Cons:**
  - Limited to ~5-10MB quota
  - Synchronous API (blocks main thread)
  - Not suitable for large datasets

**Option B: IndexedDB**
- **Pros:**
  - Larger quota (~50MB+)
  - Asynchronous API (non-blocking)
  - Suitable for complex data structures
- **Cons:**
  - Complex API
  - Overkill for single preference value
  - More code to maintain

**Decision:** localStorage chosen for MVP. If app needs to store calculation history or large datasets, IndexedDB can be introduced in v1.1+.

---

#### Trade-Off 4: Banker's Rounding vs. Round-Half-Up

**Option A: Banker's Rounding (Chosen)**
- **Pros:**
  - Minimizes systematic bias
  - Standard in financial systems
  - Reduces cumulative rounding errors
- **Cons:**
  - Less intuitive for non-technical users
  - Different from common "round up" expectation

**Option B: Round-Half-Up**
- **Pros:**
  - More intuitive (always round 0.5 up)
  - Matches common expectation
- **Cons:**
  - Introduces systematic bias (always rounds up)
  - Can accumulate errors across multiple transactions

**Decision:** Banker's rounding chosen for MVP. Service workers (Persona 2) will appreciate the accuracy. If users complain, can switch to round-half-up in v1.1.

---

#### Trade-Off 5: 10 Currencies vs. All Currencies

**Option A: 10 Major Currencies (Chosen)**
- **Pros:**
  - Covers ~80% of global transaction volume
  - Simpler UI (shorter dropdown)
  - Easier to maintain
  - Faster to implement
- **Cons:**
  - Some users may not find their currency
  - Requires maintenance if new currencies added

**Option B: All Currencies (180+)**
- **Pros:**
  - Covers all users globally
  - No maintenance for new currencies (if using dynamic list)
- **Cons:**
  - Cluttered UI (very long dropdown)
  - Harder to find currency
  - More complex implementation
  - Slower to implement

**Decision:** 10 major currencies chosen for MVP. If users request additional currencies, can add them in v1.1 (e.g., AED, ZAR, BRL).

---

#### Trade-Off 6: Tailwind CDN vs. Inline CSS

**Option A: Tailwind CDN (Chosen)**
- **Pros:**
  - Smaller HTML file (~30KB vs. ~80KB with inline CSS)
  - Cached globally by CDN
  - Easier to update Tailwind version
- **Cons:**
  - External dependency (CDN must be available)
  - Doesn't work offline (unless cached by browser)
  - Requires SRI hash for security

**Option B: Inline CSS**
- **Pros:**
  - No external dependencies
  - Works offline immediately
  - Single file deployment
- **Cons:**
  - Larger HTML file (~80KB)
  - Slower page load (more bytes to download)
  - Harder to update Tailwind version

**Decision:** Tailwind CDN chosen for MVP (smaller file size, faster load). If offline-first is critical, can switch to inline CSS in v1.1.

---

#### Trade-Off 7: GitHub Pages vs. Netlify vs. Vercel

**Option A: GitHub Pages (Chosen for MVP)**
- **Pros:**
  - Free
  - Simple setup (push to `gh-pages` branch)
  - Automatic HTTPS
  - No configuration needed
- **Cons:**
  - Limited customization
  - No server-side logic
  - Slower build times

**Option B: Netlify**
- **Pros:**
  - Free tier (generous limits)
  - Easy setup (connect Git repo)
  - Automatic deployments
  - Good DX
- **Cons:**
  - Requires Git repo
  - Limited free tier

**Option C: Vercel**
- **Pros:**
  - Free tier (generous limits)
  - Easy setup (connect Git repo)
  - Automatic deployments
  - Fast CDN
- **Cons:**
  - Requires Git repo
  - Limited free tier

**Decision:** GitHub Pages chosen for MVP (free, simple, no configuration). If more features are added, can migrate to Netlify or Vercel in v1.1.

---

### Feature Trade-Offs

#### Trade-Off 1: Real-Time Calculation vs. "Calculate" Button

**Option A: Real-Time Calculation (Chosen)**
- **Pros:**
  - Instant feedback (no button click needed)
  - Better UX (faster to use)
  - Matches user expectation
- **Cons:**
  - Requires JavaScript (doesn't work if JS disabled)
  - More complex event handling

**Option B: "Calculate" Button**
- **Pros:**
  - Works without JavaScript (graceful degradation)
  - Simpler event handling
- **Cons:**
  - Slower UX (requires button click)
  - Doesn't match user expectation

**Decision:** Real-Time calculation chosen for MVP. Graceful fallback (button) can be added if needed.

---

#### Trade-Off 2: Inline Error Messages vs. Modal Dialogs

**Option A: Inline Error Messages (Chosen)**
- **Pros:**
  - Non-intrusive (doesn't block interaction)
  - Faster to dismiss (no click needed)
  - Better mobile UX
  - Matches modern web standards
- **Cons:**
  - Requires more space on form
  - May be missed by users

**Option B: Modal Dialogs**
- **Pros:**
  - Attention-grabbing (forces user to acknowledge)
  - Doesn't take up form space
- **Cons:**
  - Intrusive (blocks interaction)
  - Slower to dismiss (requires click)
  - Poor mobile UX
  - Outdated pattern

**Decision:** Inline error messages chosen for MVP. Better UX and mobile-friendly.

---

#### Trade-Off 3: Dropdown vs. Radio Buttons for Currency Selection

**Option A: Dropdown (Chosen)**
- **Pros:**
  - Compact (saves vertical space on mobile)
  - Standard pattern for selection
  - Easier to add more currencies later
- **Cons:**
  - Requires click to open
  - Less discoverable (options hidden)

**Option B: Radio Buttons**
- **Pros:**
  - All options visible (more discoverable)
  - No click needed to see options
- **Cons:**
  - Takes up more vertical space (10 radio buttons = lots of space)
  - Harder to add more currencies later
  - Poor mobile UX

**Decision:** Dropdown chosen for MVP. Better mobile UX and space efficiency.

---

### Performance Trade-Offs

#### Trade-Off 1: Bundle Size vs. Features

**Option A: Minimal Bundle (Chosen)**
- **Target:** ≤100KB gzipped
- **Approach:** Vanilla JS, Tailwind CDN, no external libraries
- **Trade-Off:** Limited features (no bill splitting, history, etc.)

**Option B: Feature-Rich Bundle**
- **Target:** ~200KB gzipped
- **Approach:** React, component libraries, external libraries
- **Trade-Off:** Larger file size, slower load time

**Decision:** Minimal bundle chosen for MVP. Features can be added in v1.1 if performance allows.

---

#### Trade-Off 2: Page Load Time vs. Offline Capability

**Option A: Tailwind CDN (Chosen)**
- **Page Load Time:** ~1.5 seconds (smaller HTML file)
- **Offline Capability:** Requires browser cache (not guaranteed on first visit)
- **Trade-Off:** Faster load, but not offline-first

**Option B: Inline CSS**
- **Page Load Time:** ~2 seconds (larger HTML file)
- **Offline Capability:** Works offline immediately (single file)
- **Trade-Off:** Slower load, but offline-first

**Decision:** Tailwind CDN chosen for MVP (faster load time is priority). Offline-first can be added in v1.1 if needed.

---

## CONCLUSION

This Solution Design Document provides a comprehensive blueprint for implementing the Tip Calculator web app. The architecture is deliberately simple and pragmatic:

- **Client-side only:** No backend infrastructure, no database, no API
- **Single HTML file:** Minimal deployment complexity
- **Vanilla JavaScript:** No framework overhead
- **Browser localStorage:** Simple persistence for user preferences
- **Static file hosting:** Cheap, reliable, scalable

The design prioritizes **simplicity, performance, and reliability** over feature richness. All non-functional requirements (page load ≤2 seconds, calculation accuracy 100%, offline capability) are achievable with this architecture.

**Key Success Factors:**
1. Implement banker's rounding correctly (test edge cases thoroughly)
2. Validate all user inputs rigorously (prevent XSS and calculation errors)
3. Format currencies correctly per locale (use `Intl.NumberFormat` API)
4. Test across browsers and devices (ensure responsive design works)
5. Deploy to static hosting with HTTPS enforcement (ensure security)

**Future Extensibility:**
If the product roadmap includes features like bill splitting, calculation history, or user accounts, this architecture can be extended with a backend API and database without major refactoring. The calculation contract is already defined; a backend implementation can follow the same specification.

---

**Document Approval:**
- [ ] Product Management: Confirms feature scope and success metrics
- [ ] Engineering Lead: Confirms technical feasibility and timeline
- [ ] QA Lead: Confirms testing strategy and acceptance criteria
- [ ] DevOps Lead: Confirms deployment and hosting approach
- [ ] Security Lead: Confirms security design and threat mitigations

---

**Version History:**

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | [Current Date] | Principal Solutions Architect | Initial document |

---

**Document Distribution:**
- Engineering Team (implementation)
- Product Management (requirements validation)
- QA Team (testing strategy)
- DevOps Team (deployment)
- Security Team (security review)