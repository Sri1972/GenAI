# SPECS.md — FairSplit Complete Technical Specifications

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Owner:** Engineering Leadership  
**Status:** Ready for Implementation  
**Audience:** Engineering Team, QA, DevOps  

---

## TABLE OF CONTENTS

1. [Project Structure](#1-project-structure)
2. [Technology Stack & Versions](#2-technology-stack--versions)
3. [Environment Configuration](#3-environment-configuration)
4. [Data Models & Database Schema](#4-data-models--database-schema)
5. [API Contract & Service Boundaries](#5-api-contract--service-boundaries) *(Part 2)*
6. [Frontend Architecture & Component Specifications](#6-frontend-architecture--component-specifications) *(Part 2)*
7. [Backend Service Architecture & Algorithms](#7-backend-service-architecture--algorithms) *(Part 3)*
8. [Security, Compliance & Audit](#8-security-compliance--audit) *(Part 3)*
9. [Deployment, Monitoring & Operations](#9-deployment-monitoring--operations) *(Part 4)*
10. [Testing Strategy & QA Specifications](#10-testing-strategy--qa-specifications) *(Part 4)*

---

## 1. PROJECT STRUCTURE

### 1.1 Directory Tree (Complete File/Folder Layout)

```
fairsplit/
├── README.md                          # Project overview, setup instructions
├── LICENSE                            # MIT or Apache 2.0
├── .gitignore                         # Git ignore rules (Node, React, IDE, secrets)
├── .editorconfig                      # Editor formatting consistency (tabs, line endings)
├── CONTRIBUTING.md                    # Contribution guidelines, code standards
├── CODEOWNERS                         # Code review assignment by directory
│
├── docker-compose.yml                 # Local development environment (frontend, backend, postgres, redis)
├── docker-compose.prod.yml            # Production-like compose file (for staging/pre-prod testing)
│
├── frontend/                          # React SPA
│   ├── package.json                   # Dependencies, scripts, metadata
│   ├── package-lock.json              # Locked dependency versions
│   ├── tsconfig.json                  # TypeScript configuration
│   ├── vite.config.ts                 # Vite build configuration (or webpack.config.js if using webpack)
│   ├── .env.example                   # Template for environment variables (no secrets)
│   ├── .env.development               # Dev environment (git-ignored; copy from .env.example)
│   ├── .env.staging                   # Staging environment (git-ignored)
│   ├── .env.production                # Production environment (git-ignored; deployed via CI/CD secrets)
│   ├── index.html                     # HTML entry point
│   ├── public/                        # Static assets (favicon, manifest, robots.txt)
│   │   ├── favicon.ico
│   │   ├── manifest.json              # PWA manifest (optional v1)
│   │   └── robots.txt
│   │
│   ├── src/
│   │   ├── index.tsx                  # React app entry point
│   │   ├── App.tsx                    # Root component, routing setup
│   │   │
│   │   ├── types/                     # TypeScript type definitions (shared across components)
│   │   │   ├── index.ts               # Barrel export of all types
│   │   │   ├── user.ts                # User, AuthToken, Session types
│   │   │   ├── expense.ts             # Expense, LineItem, Split types
│   │   │   ├── api.ts                 # API request/response types
│   │   │   └── errors.ts              # Error types, error codes
│   │   │
│   │   ├── api/                       # HTTP client, API utilities
│   │   │   ├── client.ts              # Axios instance, interceptors, auth header setup
│   │   │   ├── endpoints.ts           # API endpoint constants (base URL, paths)
│   │   │   ├── auth.ts                # Auth API calls (signup, login, logout, refresh token)
│   │   │   ├── expenses.ts            # Expense API calls (create, list, update, delete)
│   │   │   ├── receipts.ts            # Receipt upload, OCR status polling
│   │   │   ├── splits.ts              # Split calculation, settlement queries
│   │   │   ├── recurring.ts           # Recurring split API calls
│   │   │   └── errors.ts              # API error handling, retry logic, error mapping
│   │   │
│   │   ├── store/                     # State management (Redux or Zustand; TBD during implementation)
│   │   │   ├── index.ts               # Store configuration, middleware setup
│   │   │   ├── authSlice.ts           # Auth state (user, token, login status)
│   │   │   ├── expensesSlice.ts       # Expenses state (list, selected, loading, errors)
│   │   │   ├── uiSlice.ts             # UI state (modals, notifications, theme)
│   │   │   └── thunks/                # Async action creators (API calls)
│   │   │       ├── authThunks.ts
│   │   │       ├── expenseThunks.ts
│   │   │       └── receiptThunks.ts
│   │   │
│   │   ├── components/                # Reusable UI components
│   │   │   ├── common/                # Generic, reusable components
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── LoadingSpinner.tsx
│   │   │   │   ├── ErrorBoundary.tsx
│   │   │   │   ├── Toast.tsx          # Notification toast component
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── FormInput.tsx      # Reusable form input with validation
│   │   │   │   ├── FormSelect.tsx
│   │   │   │   └── ConfirmDialog.tsx
│   │   │   │
│   │   │   ├── auth/                  # Authentication-related components
│   │   │   │   ├── LoginForm.tsx      # Email/password login
│   │   │   │   ├── SignUpForm.tsx     # Email/password signup
│   │   │   │   ├── PasswordReset.tsx  # Password reset flow
│   │   │   │   ├── ProtectedRoute.tsx # Route guard for authenticated pages
│   │   │   │   └── SessionManager.tsx # Token refresh, session lifecycle
│   │   │   │
│   │   │   ├── receipt/               # Receipt upload & OCR components
│   │   │   │   ├── ReceiptUpload.tsx  # Drag-drop file upload
│   │   │   │   ├── ReceiptPreview.tsx # Display uploaded receipt image
│   │   │   │   ├── OCRStatus.tsx      # Show OCR processing status
│   │   │   │   ├── LineItemList.tsx   # Display extracted line items
│   │   │   │   └── ReceiptCamera.tsx  # Camera capture (optional v1)
│   │   │   │
│   │   │   ├── expense/               # Expense creation & management
│   │   │   │   ├── ExpenseForm.tsx    # Create new expense
│   │   │   │   ├── ItemAssignment.tsx # Assign items to people
│   │   │   │   ├── ItemSelector.tsx   # UI for claiming items
│   │   │   │   ├── ExpenseReview.tsx  # Review before finalizing
│   │   │   │   ├── ExpenseList.tsx    # List of user's expenses
│   │   │   │   └── ExpenseDetail.tsx  # Single expense view with settlement
│   │   │   │
│   │   │   ├── split/                 # Split calculation & settlement
│   │   │   │   ├── SplitSummary.tsx   # Show who owes whom
│   │   │   │   ├── SettlementFlow.tsx # Settlement instructions
│   │   │   │   ├── PaymentLink.tsx    # Venmo/PayPal links
│   │   │   │   └── SplitHistory.tsx   # Historical splits
│   │   │   │
│   │   │   ├── recurring/             # Recurring split management
│   │   │   │   ├── RecurringForm.tsx  # Create recurring split
│   │   │   │   ├── RecurringList.tsx  # List active recurring splits
│   │   │   │   ├── RecurringEdit.tsx  # Edit/pause/cancel
│   │   │   │   └── RecurringSchedule.tsx # Show schedule & next billing date
│   │   │   │
│   │   │   ├── dashboard/             # Main dashboard/home
│   │   │   │   ├── Dashboard.tsx      # Main dashboard layout
│   │   │   │   ├── QuickStats.tsx     # Summary cards (total owed, you owe, etc.)
│   │   │   │   ├── RecentActivity.tsx # Recent splits and payments
│   │   │   │   └── ActionButtons.tsx  # Quick-action buttons (new expense, etc.)
│   │   │   │
│   │   │   ├── group/                 # Group/user management
│   │   │   │   ├── GroupForm.tsx      # Create group
│   │   │   │   ├── GroupList.tsx      # List groups
│   │   │   │   ├── GroupMembers.tsx   # Manage group members
│   │   │   │   └── InviteUsers.tsx    # Invite friends to group
│   │   │   │
│   │   │   ├── profile/               # User profile & settings
│   │   │   │   ├── Profile.tsx        # User profile view/edit
│   │   │   │   ├── AccountSettings.tsx # Email, password, preferences
│   │   │   │   └── Notifications.tsx  # Notification preferences
│   │   │   │
│   │   │   └── layout/                # Layout components
│   │   │       ├── Header.tsx         # Top navigation bar
│   │   │       ├── Sidebar.tsx        # Side navigation (optional)
│   │   │       ├── Footer.tsx         # Footer
│   │   │       └── MainLayout.tsx     # Main layout wrapper
│   │   │
│   │   ├── hooks/                     # Custom React hooks
│   │   │   ├── useAuth.ts             # Auth context/state hook
│   │   │   ├── useApi.ts              # Generic API call hook with loading/error
│   │   │   ├── useForm.ts             # Form state management hook
│   │   │   ├── useLocalStorage.ts     # LocalStorage persistence hook
│   │   │   ├── useDebounce.ts         # Debounce hook
│   │   │   └── useNotification.ts     # Toast notification hook
│   │   │
│   │   ├── utils/                     # Utility functions
│   │   │   ├── format.ts              # Number, currency, date formatting
│   │   │   ├── validation.ts          # Form validation rules
│   │   │   ├── currency.ts            # Currency conversion, rounding (USD only v1)
│   │   │   ├── math.ts                # Decimal arithmetic (avoid floating-point errors)
│   │   │   ├── retry.ts               # Exponential backoff retry logic
│   │   │   └── logger.ts              # Client-side logging (console + remote)
│   │   │
│   │   ├── styles/                    # Global styles, theme
│   │   │   ├── index.css              # Global CSS
│   │   │   ├── theme.ts               # Theme configuration (colors, fonts, breakpoints)
│   │   │   ├── variables.css          # CSS variables
│   │   │   └── responsive.css         # Media queries, responsive utilities
│   │   │
│   │   └── constants/                 # App-wide constants
│   │       ├── api.ts                 # API constants (base URL, timeout, retry config)
│   │       ├── validation.ts          # Validation rules (password requirements, etc.)
│   │       ├── messages.ts            # User-facing messages, error strings
│   │       └── config.ts              # App configuration (feature flags, etc.)
│   │
│   └── tests/                         # Frontend tests
│       ├── unit/                      # Unit tests for components, hooks, utils
│       │   ├── components/
│       │   ├── hooks/
│       │   └── utils/
│       ├── integration/               # Integration tests (component + store)
│       └── e2e/                       # End-to-end tests (Cypress or Playwright)
│           ├── auth.spec.ts
│           ├── expense.spec.ts
│           └── split.spec.ts
│
├── backend/                           # Node.js/Express API
│   ├── package.json                   # Dependencies, scripts, metadata
│   ├── package-lock.json              # Locked dependency versions
│   ├── tsconfig.json                  # TypeScript configuration
│   ├── .env.example                   # Template for environment variables (no secrets)
│   ├── .env.development               # Dev environment (git-ignored)
│   ├── .env.staging                   # Staging environment (git-ignored)
│   ├── .env.production                # Production environment (git-ignored; deployed via CI/CD)
│   │
│   ├── Dockerfile                     # Docker image for backend service
│   ├── .dockerignore                  # Files to exclude from Docker build
│   │
│   ├── src/
│   │   ├── index.ts                   # Express app entry point, middleware setup
│   │   ├── server.ts                  # HTTP server initialization, graceful shutdown
│   │   │
│   │   ├── types/                     # TypeScript type definitions
│   │   │   ├── index.ts               # Barrel export
│   │   │   ├── user.ts                # User, Session, JWT payload types
│   │   │   ├── expense.ts             # Expense, LineItem, Split, Settlement types
│   │   │   ├── api.ts                 # API request/response envelope types
│   │   │   ├── errors.ts              # Error types, error codes
│   │   │   ├── ocr.ts                 # OCR request/response types
│   │   │   └── email.ts               # Email template types
│   │   │
│   │   ├── config/                    # Configuration & environment
│   │   │   ├── index.ts               # Load and validate environment variables
│   │   │   ├── database.ts            # Database connection config
│   │   │   ├── auth.ts                # JWT secret, token expiration config
│   │   │   ├── ocr.ts                 # OCR provider config (API key, endpoint)
│   │   │   ├── email.ts               # Email service config (API key, from address)
│   │   │   └── validation.ts          # Input validation rules
│   │   │
│   │   ├── db/                        # Database & ORM
│   │   │   ├── connection.ts          # Database connection pool, initialization
│   │   │   ├── migrations/            # Database migrations (Flyway, TypeORM, or similar)
│   │   │   │   ├── 001_init_schema.sql
│   │   │   │   ├── 002_add_audit_logs.sql
│   │   │   │   └── ...
│   │   │   ├── seeds/                 # Seed data for development
│   │   │   │   └── seed.ts
│   │   │   └── models/                # ORM model definitions (if using TypeORM)
│   │   │       ├── User.ts
│   │   │       ├── Expense.ts
│   │   │       ├── LineItem.ts
│   │   │       ├── Split.ts
│   │   │       ├── Group.ts
│   │   │       ├── RecurringSchedule.ts
│   │   │       └── AuditLog.ts
│   │   │
│   │   ├── middleware/                # Express middleware
│   │   │   ├── auth.ts                # JWT verification, authentication guard
│   │   │   ├── errorHandler.ts        # Global error handling middleware
│   │   │   ├── requestLogger.ts       # Request/response logging with request ID
│   │   │   ├── validation.ts          # Input validation middleware
│   │   │   ├── rateLimit.ts           # Rate limiting middleware
│   │   │   ├── cors.ts                # CORS configuration
│   │   │   └── requestId.ts           # Request ID generation and propagation
│   │   │
│   │   ├── routes/                    # API route handlers
│   │   │   ├── index.ts               # Route registration
│   │   │   ├── auth.ts                # POST /auth/signup, /auth/login, /auth/logout, /auth/refresh
│   │   │   ├── users.ts               # GET /users/:id, PUT /users/:id, DELETE /users/:id
│   │   │   ├── expenses.ts            # GET /expenses, POST /expenses, GET /expenses/:id, PUT /expenses/:id
│   │   │   ├── receipts.ts            # POST /receipts/upload, GET /receipts/:id/ocr-status
│   │   │   ├── splits.ts              # GET /splits, POST /splits/calculate, GET /splits/:id
│   │   │   ├── recurring.ts           # GET /recurring, POST /recurring, PUT /recurring/:id, DELETE /recurring/:id
│   │   │   ├── groups.ts              # GET /groups, POST /groups, GET /groups/:id
│   │   │   ├── health.ts              # GET /health (liveness/readiness probe)
│   │   │   └── admin.ts               # Admin endpoints (audit logs, system stats)
│   │   │
│   │   ├── controllers/               # Request handlers (business logic)
│   │   │   ├── authController.ts      # Auth logic (signup, login, token refresh)
│   │   │   ├── userController.ts      # User profile, account management
│   │   │   ├── expenseController.ts   # Expense CRUD operations
│   │   │   ├── receiptController.ts   # Receipt upload, OCR orchestration
│   │   │   ├── splitController.ts     # Split calculation, settlement logic
│   │   │   ├── recurringController.ts # Recurring split management
│   │   │   └── groupController.ts     # Group management
│   │   │
│   │   ├── services/                  # Business logic & domain operations
│   │   │   ├── authService.ts         # User signup, login, token generation
│   │   │   ├── userService.ts         # User profile operations
│   │   │   ├── expenseService.ts      # Expense creation, validation, persistence
│   │   │   ├── receiptService.ts      # Receipt storage, OCR orchestration
│   │   │   ├── ocrService.ts          # OCR provider integration (Google Vision or AWS Textract)
│   │   │   ├── splitService.ts        # Split calculation, payment optimization algorithm
│   │   │   ├── settlementService.ts   # Settlement calculation, transaction minimization
│   │   │   ├── recurringService.ts    # Recurring split scheduling, triggering
│   │   │   ├── emailService.ts        # Email template rendering, dispatch
│   │   │   ├── groupService.ts        # Group operations
│   │   │   └── auditService.ts        # Audit logging
│   │   │
│   │   ├── repositories/              # Data access layer (abstraction over ORM/queries)
│   │   │   ├── userRepository.ts      # User queries
│   │   │   ├── expenseRepository.ts   # Expense queries
│   │   │   ├── splitRepository.ts     # Split queries
│   │   │   ├── recurringRepository.ts # Recurring split queries
│   │   │   ├── groupRepository.ts     # Group queries
│   │   │   └── auditLogRepository.ts  # Audit log queries
│   │   │
│   │   ├── queue/                     # Async task queue (Bull, RabbitMQ wrapper, or SQS)
│   │   │   ├── index.ts               # Queue initialization
│   │   │   ├── jobs/                  # Job definitions
│   │   │   │   ├── ocrProcessJob.ts   # Process receipt OCR
│   │   │   │   ├── emailJob.ts        # Send email reminder/confirmation
│   │   │   │   ├── recurringTriggerJob.ts # Trigger recurring splits on schedule
│   │   │   │   └── settlementJob.ts   # Calculate and finalize settlement
│   │   │   └── workers/               # Job processors
│   │   │       ├── ocrWorker.ts
│   │   │       ├── emailWorker.ts
│   │   │       ├── recurringWorker.ts
│   │   │       └── settlementWorker.ts
│   │   │
│   │   ├── algorithms/                # Business logic algorithms
│   │   │   ├── paymentOptimization.ts # Payment optimization algorithm (minimize transactions)
│   │   │   ├── taxTipDistribution.ts  # Proportional tax/tip calculation
│   │   │   └── settlement.ts          # Settlement calculation logic
│   │   │
│   │   ├── utils/                     # Utility functions
│   │   │   ├── logger.ts              # Structured logging (Winston, Pino)
│   │   │   ├── errors.ts              # Custom error classes, error mapping
│   │   │   ├── jwt.ts                 # JWT token generation, verification
│   │   │   ├── crypto.ts              # Password hashing, encryption utilities
│   │   │   ├── currency.ts            # Currency formatting, decimal arithmetic
│   │   │   ├── validation.ts          # Input validation helpers
│   │   │   ├── retry.ts               # Exponential backoff for external service calls
│   │   │   └── email.ts               # Email template rendering
│   │   │
│   │   ├── constants/                 # App-wide constants
│   │   │   ├── api.ts                 # HTTP status codes, error codes
│   │   │   ├── validation.ts          # Validation rules (min/max lengths, etc.)
│   │   │   ├── messages.ts            # Error messages, email templates
│   │   │   └── limits.ts              # Rate limits, quota limits
│   │   │
│   │   └── email/                     # Email templates
│   │       ├── templates/
│   │       │   ├── paymentReminder.hbs
│   │       │   ├── paymentConfirmation.hbs
│   │       │   ├── expenseCreated.hbs
│   │       │   ├── recurringScheduled.hbs
│   │       │   └── passwordReset.hbs
│   │       └── index.ts               # Email template registry
│   │
│   ├── tests/                         # Backend tests
│   │   ├── unit/                      # Unit tests for services, utils, algorithms
│   │   │   ├── services/
│   │   │   ├── algorithms/
│   │   │   └── utils/
│   │   ├── integration/               # Integration tests (service + database)
│   │   │   ├── expenseFlow.test.ts
│   │   │   ├── splitCalculation.test.ts
│   │   │   └── recurringTrigger.test.ts
│   │   ├── e2e/                       # End-to-end tests (API + database)
│   │   │   ├── auth.test.ts
│   │   │   ├── expense.test.ts
│   │   │   └── settlement.test.ts
│   │   ├── fixtures/                  # Test data fixtures
│   │   │   ├── users.json
│   │   │   ├── expenses.json
│   │   │   └── receipts.json
│   │   └── setup.ts                   # Test database setup, teardown
│   │
│   └── scripts/                       # Utility scripts
│       ├── migrate.ts                 # Run database migrations
│       ├── seed.ts                    # Seed development data
│       ├── resetDb.ts                 # Drop and recreate database (dev only)
│       └── generateTypes.ts           # Generate TypeScript types from schema
│
├── infrastructure/                    # Infrastructure-as-Code, DevOps
│   ├── docker/
│   │   ├── Dockerfile.backend         # Backend Dockerfile (alternative location)
│   │   ├── Dockerfile.frontend        # Frontend Dockerfile (alternative location)
│   │   └── nginx.conf                 # Nginx reverse proxy config (if used)
│   │
│   ├── kubernetes/                    # Kubernetes manifests (if deploying to K8s)
│   │   ├── namespace.yaml
│   │   ├── backend-deployment.yaml
│   │   ├── frontend-deployment.yaml
│   │   ├── postgres-statefulset.yaml
│   │   ├── redis-deployment.yaml
│   │   ├── service.yaml
│   │   ├── ingress.yaml
│   │   ├── configmap.yaml
│   │   └── secrets.yaml
│   │
│   ├── terraform/                     # Terraform IaC (AWS, DigitalOcean, etc.)
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   ├── rds.tf                     # RDS database configuration
│   │   ├── ecr.tf                     # ECR container registry
│   │   ├── ecs.tf                     # ECS cluster (if using ECS)
│   │   ├── alb.tf                     # Application Load Balancer
│   │   ├── security_groups.tf
│   │   ├── vpc.tf
│   │   └── dev.tfvars                 # Dev environment variables
│   │
│   ├── scripts/
│   │   ├── deploy.sh                  # Deployment script
│   │   ├── rollback.sh                # Rollback script
│   │   ├── health-check.sh            # Health check script
│   │   └── backup-database.sh         # Database backup script
│   │
│   └── monitoring/
│       ├── prometheus.yml             # Prometheus scrape config
│       ├── grafana-dashboards/        # Grafana dashboard definitions
│       │   ├── api-metrics.json
│       │   ├── database-metrics.json
│       │   └── error-tracking.json
│       └── alerts.yml                 # Alerting rules
│
├── docs/                              # Documentation
│   ├── API.md                         # API documentation (OpenAPI/Swagger)
│   ├── ARCHITECTURE.md                # Architecture overview
│   ├── DEPLOYMENT.md                  # Deployment guide
│   ├── DEVELOPMENT.md                 # Local development setup
│   ├── DATABASE.md                    # Database schema documentation
│   ├── SECURITY.md                    # Security guidelines
│   ├── TESTING.md                     # Testing strategy
│   ├── TROUBLESHOOTING.md             # Common issues and solutions
│   └── GLOSSARY.md                    # Term definitions
│
├── .github/                           # GitHub-specific files
│   ├── workflows/
│   │   ├── ci.yml                     # CI pipeline (lint, test, build)
│   │   ├── deploy-staging.yml         # Deploy to staging on push to main
│   │   ├── deploy-production.yml      # Deploy to production (manual trigger)
│   │   └── security-scan.yml          # Security scanning (SAST, dependency check)
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   ├── feature_request.md
│   │   └── documentation.md
│   └── PULL_REQUEST_TEMPLATE.md
│
├── .gitlab-ci.yml                     # GitLab CI (if using GitLab instead of GitHub)
├── Makefile                           # Common development commands (make dev, make test, make deploy)
└── CHANGELOG.md                       # Release notes and version history
```

---

### 1.2 Key Directory Purposes

| Directory | Purpose | Owner |
|-----------|---------|-------|
| `frontend/` | React SPA source code, tests, assets | Frontend Team |
| `backend/` | Node.js/Express API source code, tests, migrations | Backend Team |
| `infrastructure/` | Docker, Kubernetes, Terraform, deployment scripts | DevOps Team |
| `docs/` | Architecture, API, deployment, security documentation | Engineering Leadership / Tech Writer |
| `.github/` | GitHub Actions CI/CD workflows, issue templates | DevOps / Engineering Leadership |

---

### 1.3 File Naming Conventions

- **TypeScript files:** `camelCase.ts` (e.g., `authService.ts`, `expenseController.ts`)
- **React components:** `PascalCase.tsx` (e.g., `LoginForm.tsx`, `ExpenseList.tsx`)
- **Database migrations:** `YYYYMMDD_HH_description.sql` (e.g., `20240115_01_init_schema.sql`)
- **Test files:** `*.test.ts` or `*.spec.ts` (e.g., `authService.test.ts`)
- **Configuration files:** `camelCase.ts` or `.env.environment` (e.g., `database.ts`, `.env.development`)
- **CSS/SCSS:** `camelCase.css` or `PascalCase.module.css` (e.g., `theme.css`, `Button.module.css`)

---

## 2. TECHNOLOGY STACK & VERSIONS

### 2.1 Frontend Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| **Runtime** | Node.js | 18.x LTS | Long-term support, stable, widely used in production |
| **Package Manager** | npm | 9.x | Bundled with Node.js; adequate for this scale (monorepo not needed v1) |
| **Framework** | React | 18.x | Industry standard, large ecosystem, component-based, proven at scale |
| **Language** | TypeScript | 5.x | Type safety, IDE support, catches errors at compile time, reduces runtime bugs |
| **Build Tool** | Vite | 4.x | Fast HMR, optimized production builds, modern ES modules, faster than webpack |
| **State Management** | Zustand or Redux Toolkit | Latest | Zustand for simplicity; Redux Toolkit if complex state needed. Decision: **Zustand (simpler, smaller bundle)** |
| **HTTP Client** | Axios | 1.x | Promise-based, interceptors, request/response transformation, better than fetch for this use case |
| **Routing** | React Router | 6.x | Industry standard, nested routes, lazy code-splitting, outlet pattern |
| **UI Component Library** | Material-UI (MUI) or Tailwind CSS | 5.x (MUI) / 3.x (Tailwind) | Decision: **Tailwind CSS** (smaller bundle, faster, more customizable for responsive design) |
| **Form Validation** | Zod or Yup | Latest (Zod) | Zod for TypeScript-first schema validation; smaller bundle than Yup |
| **HTTP Status Codes** |

---

# 5. API CONTRACT & SERVICE BOUNDARIES

## 5.1 API Overview & Design Principles

### Base URL
```
Development:  http://localhost:3000/api/v1
Staging:      https://staging-api.fairsplit.dev/api/v1
Production:   https://api.fairsplit.dev/api/v1
```

### Authentication
- **Scheme:** Bearer Token (JWT)
- **Header:** `Authorization: Bearer <access_token>`
- **Token Lifetime:** 1 hour (access token); 7 days (refresh token)
- **Refresh Endpoint:** `POST /auth/refresh` (exchanges refresh token for new access token)
- **Unauthenticated Endpoints:** `/auth/signup`, `/auth/login`, `/health`

### Request/Response Format
- **Content-Type:** `application/json` (all requests and responses)
- **Request ID:** All responses include `X-Request-ID` header for traceability
- **Pagination:** Offset/limit pattern for list endpoints (default limit: 20, max limit: 100)
- **Timestamps:** ISO 8601 format with timezone (e.g., `2024-01-15T14:30:00Z`)
- **Monetary Values:** Represented as integers in cents (e.g., $10.50 = 1050) to avoid floating-point precision issues

### Error Response Format
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more validation errors occurred",
    "details": [
      {
        "field": "email",
        "message": "Email is already registered"
      }
    ],
    "requestId": "req_abc123xyz"
  }
}
```

### HTTP Status Codes
- **200 OK:** Successful GET, successful state query
- **201 Created:** Successful POST that creates a resource
- **202 Accepted:** Asynchronous operation accepted (OCR processing, email dispatch)
- **204 No Content:** Successful DELETE or operation with no response body
- **400 Bad Request:** Validation error, malformed request
- **401 Unauthorized:** Missing or invalid authentication token
- **403 Forbidden:** Authenticated but lacks permission (e.g., accessing another user's expense)
- **404 Not Found:** Resource does not exist
- **409 Conflict:** State conflict (e.g., expense already settled, duplicate email)
- **422 Unprocessable Entity:** Semantic error (e.g., invalid business logic, cannot split expense with 0 items)
- **429 Too Many Requests:** Rate limit exceeded
- **500 Internal Server Error:** Unexpected server error (logged, user sees generic message)
- **503 Service Unavailable:** External service (OCR, email) temporarily unavailable

### Rate Limiting
- **Public Endpoints** (signup, login): 5 requests per minute per IP
- **Authenticated Endpoints** (general): 100 requests per minute per user
- **Receipt Upload:** 10 uploads per minute per user (prevent abuse)
- **Headers:** `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## 5.2 Authentication & Authorization Endpoints

### POST /auth/signup
**Purpose:** Create a new user account  
**Authentication:** None (public endpoint)  
**Rate Limit:** 5 req/min per IP

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "passwordConfirm": "SecurePass123!",
  "fullName": "John Doe"
}
```

**Request Validation:**
- `email`: Required, valid email format (RFC 5322), max 254 characters, must not already exist
- `password`: Required, min 8 characters, must contain uppercase, lowercase, digit, special character
- `passwordConfirm`: Required, must match `password` exactly
- `fullName`: Required, min 2 characters, max 100 characters, no special characters except spaces/hyphens

**Response (201 Created):**
```json
{
  "user": {
    "id": "usr_abc123xyz",
    "email": "user@example.com",
    "fullName": "John Doe",
    "createdAt": "2024-01-15T14:30:00Z"
  },
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refreshToken": "ref_xyz789abc"
}
```

**Response Headers:**
```
Set-Cookie: refreshToken=ref_xyz789abc; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=604800
X-Request-ID: req_abc123xyz
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `VALIDATION_ERROR` | Email is already registered / Password does not meet requirements / Passwords do not match |
| 400 | `INVALID_EMAIL` | Please enter a valid email address |
| 500 | `INTERNAL_ERROR` | An error occurred. Please try again. |

**Business Rules:**
- Password must be hashed with bcrypt (cost factor ≥12) before storage
- User status defaults to "active"
- Audit log entry created: `action: "user_signup"`, `user_id`, `timestamp`, `ip_address`
- Email confirmation optional (v1 allows immediate login without verification)

**Notes:**
- Refresh token stored in HttpOnly cookie to prevent XSS access
- Access token returned in response body for SPA storage (memory only, not localStorage)
- No confirmation email sent (deferred to post-MVP)

---

### POST /auth/login
**Purpose:** Authenticate user and obtain access/refresh tokens  
**Authentication:** None (public endpoint)  
**Rate Limit:** 5 req/min per IP

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Request Validation:**
- `email`: Required, valid email format
- `password`: Required, non-empty

**Response (200 OK):**
```json
{
  "user": {
    "id": "usr_abc123xyz",
    "email": "user@example.com",
    "fullName": "John Doe"
  },
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refreshToken": "ref_xyz789abc"
}
```

**Response Headers:**
```
Set-Cookie: refreshToken=ref_xyz789abc; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=604800
X-Request-ID: req_abc123xyz
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `AUTH_FAILED` | Email or password incorrect |
| 403 | `ACCOUNT_SUSPENDED` | Your account has been suspended. Contact support. |
| 404 | `USER_NOT_FOUND` | Email or password incorrect |
| 500 | `INTERNAL_ERROR` | An error occurred. Please try again. |

**Business Rules:**
- Verify email exists in database
- Use bcrypt.compare() to verify password against stored hash
- Check user status is "active" (reject if suspended or deleted)
- Generate JWT access token (exp: now + 1 hour)
- Generate refresh token (exp: now + 7 days); store in secure cookie
- Audit log entry: `action: "user_login"`, `user_id`, `timestamp`, `ip_address`
- On failed login attempt: log attempt; no email sent (prevent enumeration attacks)

**Notes:**
- Generic error message "Email or password incorrect" prevents email enumeration
- Implement exponential backoff or temporary lockout after N failed attempts (e.g., 5 failures = 15 min lockout)

---

### POST /auth/refresh
**Purpose:** Obtain new access token using refresh token  
**Authentication:** None (uses refresh token from cookie)  
**Rate Limit:** 10 req/min per user

**Request Body:**
```json
{
  "refreshToken": "ref_xyz789abc"
}
```

**Alternative:** Refresh token sent in HttpOnly cookie; request body may be empty if cookie is used.

**Request Validation:**
- `refreshToken`: Required if not in cookie, valid JWT format, not expired

**Response (200 OK):**
```json
{
  "accessToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refreshToken": "ref_new789abc"
}
```

**Response Headers:**
```
Set-Cookie: refreshToken=ref_new789abc; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=604800
X-Request-ID: req_abc123xyz
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `INVALID_TOKEN` | Refresh token is invalid or expired |
| 400 | `MISSING_TOKEN` | Refresh token is required |

**Business Rules:**
- Verify refresh token is valid JWT with correct signature
- Verify refresh token has not expired
- Verify refresh token has not been revoked (optional: maintain revocation list)
- Generate new access token (exp: now + 1 hour)
- Optionally rotate refresh token (generate new one, invalidate old one)
- Audit log entry: `action: "token_refresh"`, `user_id`, `timestamp`

**Notes:**
- Refresh token rotation improves security; old token becomes invalid after new one issued
- If refresh token expired, user must re-authenticate via login

---

### POST /auth/logout
**Purpose:** Invalidate user session and tokens  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Request Body:**
```json
{}
```

**Response (204 No Content):**
```
(empty body)
```

**Response Headers:**
```
Set-Cookie: refreshToken=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0
X-Request-ID: req_abc123xyz
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |

**Business Rules:**
- Clear refresh token cookie (set Max-Age=0)
- Optionally add access token to revocation list (if maintaining token blacklist)
- Audit log entry: `action: "user_logout"`, `user_id`, `timestamp`

**Notes:**
- Frontend should also clear access token from memory
- Revocation list is optional; depends on implementation approach

---

### POST /auth/password-reset-request
**Purpose:** Request password reset link via email  
**Authentication:** None (public endpoint)  
**Rate Limit:** 3 req/min per IP

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Request Validation:**
- `email`: Required, valid email format

**Response (202 Accepted):**
```json
{
  "message": "If an account exists with this email, a password reset link has been sent."
}
```

**Error Responses:**
- Always return 202 even if email not found (prevents email enumeration)

**Business Rules:**
- Query database for user by email
- If user found:
  - Generate reset token (secure random, 32+ bytes)
  - Store reset token with expiration (1 hour) in database
  - Send email with reset link: `https://fairsplit.dev/reset-password?token=<reset_token>`
  - Audit log: `action: "password_reset_requested"`, `user_id`, `timestamp`
- If user not found: do nothing (return success to prevent enumeration)
- Email should include reset link, expiration time, and "If you didn't request this, ignore this email"

**Notes:**
- Reset token must be cryptographically secure (use crypto.randomBytes or similar)
- Reset link should include token as query parameter; frontend sends token to reset endpoint
- Token should be single-use and expire after 1 hour

---

### POST /auth/password-reset
**Purpose:** Reset password using reset token  
**Authentication:** None (uses reset token)  
**Rate Limit:** 5 req/min per IP

**Request Body:**
```json
{
  "resetToken": "abc123xyz789...",
  "newPassword": "NewSecurePass123!",
  "newPasswordConfirm": "NewSecurePass123!"
}
```

**Request Validation:**
- `resetToken`: Required, valid format
- `newPassword`: Required, min 8 characters, uppercase, lowercase, digit, special character
- `newPasswordConfirm`: Required, must match `newPassword`

**Response (200 OK):**
```json
{
  "message": "Password reset successfully. You can now log in with your new password."
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `INVALID_TOKEN` | Reset token is invalid or expired |
| 400 | `VALIDATION_ERROR` | New password does not meet requirements / Passwords do not match |
| 404 | `TOKEN_NOT_FOUND` | Reset token not found |

**Business Rules:**
- Query database for reset token record
- Verify token exists and has not expired
- Verify token has not been used (single-use)
- Hash new password with bcrypt (cost ≥12)
- Update user password in database
- Mark reset token as used (or delete it)
- Clear any active refresh tokens (force user to log in)
- Audit log: `action: "password_reset"`, `user_id`, `timestamp`
- Send confirmation email: "Your password has been reset. If you didn't do this, contact support."

**Notes:**
- Invalidate all existing refresh tokens to force re-login
- Reset token should be single-use to prevent replay attacks

---

### GET /auth/me
**Purpose:** Get current authenticated user's profile  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Request Body:**
```
(empty)
```

**Response (200 OK):**
```json
{
  "user": {
    "id": "usr_abc123xyz",
    "email": "user@example.com",
    "fullName": "John Doe",
    "createdAt": "2024-01-15T14:30:00Z",
    "updatedAt": "2024-01-15T14:30:00Z"
  }
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 404 | `USER_NOT_FOUND` | User not found |

**Business Rules:**
- Extract user ID from JWT token
- Query database for user record
- Return user profile (exclude password hash)

**Notes:**
- Used by frontend to verify authentication status and populate user context

---

### PATCH /auth/me
**Purpose:** Update current user's profile (email, full name)  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Request Body:**
```json
{
  "email": "newemail@example.com",
  "fullName": "Jane Doe"
}
```

**Request Validation:**
- `email`: Optional, valid email format, max 254 characters, must not already exist (if changed)
- `fullName`: Optional, min 2 characters, max 100 characters

**Response (200 OK):**
```json
{
  "user": {
    "id": "usr_abc123xyz",
    "email": "newemail@example.com",
    "fullName": "Jane Doe",
    "updatedAt": "2024-01-15T15:00:00Z"
  }
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `VALIDATION_ERROR` | Email is already registered / Invalid email format |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 409 | `CONFLICT` | Email is already in use by another account |

**Business Rules:**
- Extract user ID from JWT token
- Validate new email (if provided) is not already registered
- Update user record with new values
- Audit log: `action: "user_profile_updated"`, `user_id`, `fields_changed`, `timestamp`

**Notes:**
- If email changed, optionally send confirmation email (v1 may skip this)

---

### DELETE /auth/me
**Purpose:** Delete user account and all associated data  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 1 req/min per user

**Request Body:**
```json
{
  "password": "SecurePass123!"
}
```

**Request Validation:**
- `password`: Required, must match user's current password (confirm identity)

**Response (204 No Content):**
```
(empty body)
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 403 | `INVALID_PASSWORD` | Password is incorrect |
| 409 | `ACCOUNT_HAS_ACTIVE_SPLITS` | Cannot delete account with unsettled expenses. Please settle all splits first. |

**Business Rules:**
- Extract user ID from JWT token
- Verify password against stored hash
- Check if user has any unsettled expenses (active splits with pending payments)
  - If yes: reject deletion with 409 error
- If user can be deleted:
  - Mark user account as "deleted" (soft delete; retain record for audit trail)
  - Anonymize user data (email, full name replaced with placeholder)
  - Retain all transaction history and audit logs (for compliance)
  - Clear refresh tokens
- Audit log: `action: "user_deleted"`, `user_id`, `timestamp`
- Send confirmation email: "Your account has been deleted. All your data has been removed."

**Notes:**
- Soft delete (mark as deleted) rather than hard delete to maintain referential integrity and audit trail
- Unsettled expenses prevent deletion to avoid orphaned financial records
- All user's expenses/splits remain visible to other group members (for settlement purposes)

---

## 5.3 Group Management Endpoints

### POST /groups
**Purpose:** Create a new expense group (e.g., "Weekend Trip", "House Rent")  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Request Body:**
```json
{
  "name": "Weekend Trip to Vegas",
  "description": "May 10-12, 2024",
  "members": ["usr_xyz789", "usr_abc123"]
}
```

**Request Validation:**
- `name`: Required, min 2 characters, max 100 characters
- `description`: Optional, max 500 characters
- `members`: Optional, array of user IDs, max 20 members

**Response (201 Created):**
```json
{
  "group": {
    "id": "grp_abc123xyz",
    "name": "Weekend Trip to Vegas",
    "description": "May 10-12, 2024",
    "createdBy": "usr_abc123xyz",
    "createdAt": "2024-01-15T14:30:00Z",
    "members": [
      {
        "userId": "usr_abc123xyz",
        "email": "creator@example.com",
        "fullName": "John Doe",
        "role": "owner",
        "joinedAt": "2024-01-15T14:30:00Z"
      },
      {
        "userId": "usr_xyz789",
        "email": "member@example.com",
        "fullName": "Jane Smith",
        "role": "member",
        "joinedAt": "2024-01-15T14:30:00Z"
      }
    ]
  }
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `VALIDATION_ERROR` | Group name is required / Group name must be 2-100 characters |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 404 | `USER_NOT_FOUND` | One or more members not found |

**Business Rules:**
- Creator automatically added as group owner
- Specified members invited to group (if provided)
- Members can be added/removed later via separate endpoints
- Group ID generated (UUID or snowflake ID)
- Audit log: `action: "group_created"`, `user_id`, `group_id`, `timestamp`

**Notes:**
- Members can be invited by user ID (if already registered) or email (for future members)
- Invitation flow deferred to post-MVP if email-based invitations needed

---

### GET /groups
**Purpose:** List all groups for authenticated user  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Query Parameters:**
```
?limit=20&offset=0&sort=createdAt&order=desc
```

**Response (200 OK):**
```json
{
  "groups": [
    {
      "id": "grp_abc123xyz",
      "name": "Weekend Trip to Vegas",
      "description": "May 10-12, 2024",
      "createdBy": "usr_abc123xyz",
      "createdAt": "2024-01-15T14:30:00Z",
      "memberCount": 4,
      "activeExpenseCount": 2,
      "settledExpenseCount": 5
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 8
  }
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |

**Business Rules:**
- Return only groups where authenticated user is a member
- Sort by creation date (descending) by default
- Include member count and expense counts for quick overview

---

### GET /groups/:groupId
**Purpose:** Get details of a specific group  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Path Parameters:**
- `groupId`: Group ID (e.g., `grp_abc123xyz`)

**Response (200 OK):**
```json
{
  "group": {
    "id": "grp_abc123xyz",
    "name": "Weekend Trip to Vegas",
    "description": "May 10-12, 2024",
    "createdBy": "usr_abc123xyz",
    "createdAt": "2024-01-15T14:30:00Z",
    "updatedAt": "2024-01-15T14:30:00Z",
    "members": [
      {
        "userId": "usr_abc123xyz",
        "email": "creator@example.com",
        "fullName": "John Doe",
        "role": "owner",
        "joinedAt": "2024-01-15T14:30:00Z"
      },
      {
        "userId": "usr_xyz789",
        "email": "member@example.com",
        "fullName": "Jane Smith",
        "role": "member",
        "joinedAt": "2024-01-15T14:30:00Z"
      }
    ],
    "expenses": [
      {
        "id": "exp_abc123xyz",
        "description": "Dinner at The Venetian",
        "amount": 24500,
        "currency": "USD",
        "createdAt": "2024-01-15T14:30:00Z",
        "status": "settled"
      }
    ]
  }
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 403 | `FORBIDDEN` | You do not have access to this group |
| 404 | `GROUP_NOT_FOUND` | Group not found |

**Business Rules:**
- Only group members can view group details
- Return full member list and recent expenses

---

### PATCH /groups/:groupId
**Purpose:** Update group details (name, description)  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Path Parameters:**
- `groupId`: Group ID

**Request Body:**
```json
{
  "name": "Updated Trip Name",
  "description": "Updated description"
}
```

**Request Validation:**
- `name`: Optional, min 2 characters, max 100 characters
- `description`: Optional, max 500 characters

**Response (200 OK):**
```json
{
  "group": {
    "id": "grp_abc123xyz",
    "name": "Updated Trip Name",
    "description": "Updated description",
    "updatedAt": "2024-01-15T15:00:00Z"
  }
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 403 | `FORBIDDEN` | Only group owner can update group details |
| 404 | `GROUP_NOT_FOUND` | Group not found |

**Business Rules:**
- Only group owner can update group
- Audit log: `action: "group_updated"`, `user_id`, `group_id`, `fields_changed`, `timestamp`

---

### DELETE /groups/:groupId
**Purpose:** Delete a group (soft delete; retain for audit trail)  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Path Parameters:**
- `groupId`: Group ID

**Request Body:**
```json
{}
```

**Response (204 No Content):**
```
(empty body)
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 403 | `FORBIDDEN` | Only group owner can delete group |
| 404 | `GROUP_NOT_FOUND` | Group not found |
| 409 | `CONFLICT` | Cannot delete group with unsettled expenses |

**Business Rules:**
- Only group owner can delete group
- Cannot delete if group has unsettled expenses
- Soft delete: mark group as "deleted"; retain for audit trail
- Audit log: `action: "group_deleted"`, `user_id`, `group_id`, `timestamp`

---

### POST /groups/:groupId/members
**Purpose:** Add a member to a group  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Path Parameters:**
- `groupId`: Group ID

**Request Body:**
```json
{
  "userId": "usr_xyz789"
}
```

**Request Validation:**
- `userId`: Required, must be valid user ID, must not already be member

**Response (201 Created):**
```json
{
  "member": {
    "userId": "usr_xyz789",
    "email": "newmember@example.com",
    "fullName": "New Member",
    "role": "member",
    "joinedAt": "2024-01-15T15:00:00Z"
  }
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 403 | `FORBIDDEN` | Only group owner can add members |
| 404 | `GROUP_NOT_FOUND` / `USER_NOT_FOUND` | Group or user not found |
| 409 | `CONFLICT` | User is already a member of this group |

**Business Rules:**
- Only group owner can add members
- New member added with role "member" (not owner)
- Audit log: `action: "group_member_added"`, `user_id`, `group_id`, `new_member_id`, `timestamp`

---

### DELETE /groups/:groupId/members/:userId
**Purpose:** Remove a member from a group  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Path Parameters:**
- `groupId`: Group ID
- `userId`: User ID to remove

**Request Body:**
```json
{}
```

**Response (204 No Content):**
```
(empty body)
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 403 | `FORBIDDEN` | Only group owner can remove members |
| 404 | `GROUP_NOT_FOUND` / `USER_NOT_FOUND` | Group or user not found |
| 409 | `CONFLICT` | Cannot remove member with unsettled expenses in this group |

**Business Rules:**
- Only group owner can remove members
- Cannot remove member if they have unsettled expenses in group
- Audit log: `action: "group_member_removed"`, `user_id`, `group_id`, `removed_member_id`, `timestamp`

---

## 5.4 Receipt & OCR Processing Endpoints

### POST /receipts/upload
**Purpose:** Upload receipt image and trigger OCR processing  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 10 req/min per user

**Request:**
- **Content-Type:** `multipart/form-data`
- **Form Fields:**
  - `receipt`: Binary image file (JPEG, PNG, PDF; max 10 MB)
  - `groupId`: Group ID (optional; can be added later during expense creation)

**Response (202 Accepted):**
```json
{
  "receipt": {
    "id": "rcpt_abc123xyz",
    "status": "processing",
    "createdAt": "2024-01-15T14:30:00Z",
    "imageUrl": "https://s3.amazonaws.com/fairsplit-receipts/rcpt_abc123xyz.jpg",
    "ocrStatus": "pending"
  }
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `INVALID_FILE` | File is not a valid image (JPEG, PNG, PDF) |
| 400 | `FILE_TOO_LARGE` | File size exceeds 10 MB |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication token |
| 413 | `PAYLOAD_TOO_LARGE` | Request body exceeds size limit |

**Business Rules:**
- Store receipt image in cloud storage (AWS S3, GCS, or similar)
- Generate unique receipt ID
- Queue OCR processing job asynchronously (do not block request)
- Return receipt ID immediately; OCR processing happens in background
- OCR status initially "pending"; transitions to "completed" or "failed"
- Audit log: `action: "receipt_uploaded"`, `user_id`, `receipt_id`, `timestamp`

**Notes:**
- Image stored with server-side encryption
- Presigned URL returned for frontend to display image preview
- Frontend polls GET /receipts/:receiptId to check OCR status

---

### GET /receipts/:receiptId
**Purpose:** Get receipt details and OCR processing status  
**Authentication:** Required (Bearer token)  
**Rate Limit:** 100 req/min per user

**Path Parameters:**
- `receiptId`: Receipt ID (e.g., `rcpt_abc123xyz`)

**Response (200 OK):**
```json
{
  "receipt": {
    "id": "rcpt_abc123xyz",
    "status": "completed",
    "createdAt": "2024-01-15T14:30:00Z",
    "imageUrl": "https://s3.amazonaws.com/fairsplit-receipts/rcpt_abc123xyz.jpg",
    "ocrStatus": "completed",
    "lineItems": [
      {
        "id": "item_abc123",
        "description": "Grilled Salmon",
        "quantity": 1,
        "unitPrice": 2800,
        "totalPrice": 2800,
        "confidence": 0.98
      },
      {
        "id": "item_xyz789",
        "description": "Caesar Salad",
        "quantity": 1,
        "unitPrice": 1200,
        "totalPrice": 1200,
        "confidence": 0.95
      },
      {
        "id": "item_def456",
        "description": "House Wine (glass)",
        "quantity": 2,
        "unitPrice": 900,
        "totalPrice": 1800,
        "confidence": 0.92
      

> **Guardrail Warning**: Design missing critical sections: ['scalab', 'monitor', 'deploy']

---

# 6. FRONTEND ARCHITECTURE & COMPONENT SPECIFICATIONS

## 6.1 Frontend Project Structure

```
frontend/
├── public/
│   ├── index.html                     # Main HTML entry point
│   ├── favicon.ico
│   └── manifest.json                  # PWA manifest (optional v1)
│
├── src/
│   ├── index.tsx                      # React DOM render entry point
│   ├── App.tsx                        # Root component, routing setup
│   ├── App.css                        # Global styles
│   │
│   ├── config/
│   │   ├── api.ts                     # API base URL, client configuration
│   │   ├── constants.ts               # App-wide constants (limits, timeouts, error codes)
│   │   └── env.ts                     # Environment variable loader with validation
│   │
│   ├── types/
│   │   ├── index.ts                   # Shared TypeScript types and interfaces
│   │   ├── api.ts                     # API request/response types
│   │   ├── domain.ts                  # Domain models (User, Expense, Split, etc.)
│   │   └── ui.ts                      # UI state types (form state, modal state, etc.)
│   │
│   ├── store/
│   │   ├── index.ts                   # Store initialization (Redux or Zustand)
│   │   ├── authSlice.ts               # Auth state (user, token, login status)
│   │   ├── expenseSlice.ts            # Expense state (active splits, history)
│   │   ├── uiSlice.ts                 # UI state (modals, notifications, loading)
│   │   └── hooks.ts                   # Custom hooks for store access (useAppDispatch, useAppSelector, etc.)
│   │
│   ├── services/
│   │   ├── api/
│   │   │   ├── client.ts              # Axios/Fetch client with interceptors, error handling
│   │   │   ├── auth.ts                # Auth API calls (signup, login, logout, refresh)
│   │   │   ├── expenses.ts            # Expense API calls (create, list, update, delete)
│   │   │   ├── receipts.ts            # Receipt upload and OCR status API calls
│   │   │   ├── splits.ts              # Split calculation and settlement API calls
│   │   │   ├── recurring.ts           # Recurring split API calls
│   │   │   └── users.ts               # User profile API calls
│   │   │
│   │   ├── auth/
│   │   │   ├── tokenManager.ts        # Token storage, refresh, validation
│   │   │   └── sessionManager.ts      # Session lifecycle management
│   │   │
│   │   └── utils/
│   │       ├── formatters.ts          # Format currency, dates, phone numbers
│   │       ├── validators.ts          # Client-side validation rules
│   │       ├── errorHandlers.ts       # Error message mapping and user-friendly messages
│   │       └── retry.ts               # Exponential backoff retry logic
│   │
│   ├── components/
│   │   ├── common/
│   │   │   ├── Header.tsx             # Top navigation bar (logo, user menu, logout)
│   │   │   ├── Sidebar.tsx            # Left sidebar (navigation, links)
│   │   │   ├── Footer.tsx             # Footer (copyright, links)
│   │   │   ├── Button.tsx             # Reusable button component (primary, secondary, danger)
│   │   │   ├── Input.tsx              # Reusable text input with validation feedback
│   │   │   ├── Modal.tsx              # Reusable modal/dialog component
│   │   │   ├── Spinner.tsx            # Loading spinner component
│   │   │   ├── Alert.tsx              # Alert/notification component (success, error, warning, info)
│   │   │   ├── ErrorBoundary.tsx      # Error boundary for graceful error handling
│   │   │   ├── ProtectedRoute.tsx     # Route guard for authenticated pages
│   │   │   └── styles/
│   │   │       └── common.module.css  # Shared component styles
│   │   │
│   │   ├── auth/
│   │   │   ├── LoginPage.tsx          # Login form page
│   │   │   ├── SignupPage.tsx         # Signup form page
│   │   │   ├── PasswordResetPage.tsx  # Password reset form
│   │   │   ├── LoginForm.tsx          # Login form component (email, password)
│   │   │   ├── SignupForm.tsx         # Signup form component (email, password, name)
│   │   │   ├── PasswordResetForm.tsx  # Password reset form
│   │   │   └── styles/
│   │   │       └── auth.module.css
│   │   │
│   │   ├── receipt/
│   │   │   ├── ReceiptUploadPage.tsx  # Receipt upload page (drag-drop, file input)
│   │   │   ├── ReceiptUploadForm.tsx  # Receipt upload form with preview
│   │   │   ├── ReceiptPreview.tsx     # Display uploaded receipt image with OCR status
│   │   │   ├── ReceiptOCRStatus.tsx   # Show OCR processing status (pending, success, error)
│   │   │   ├── LineItemList.tsx       # Display extracted line items from OCR
│   │   │   ├── LineItemEditor.tsx     # Edit line item name, price, quantity (if OCR fails)
│   │   │   └── styles/
│   │   │       └── receipt.module.css
│   │   │
│   │   ├── expense/
│   │   │   ├── ExpenseCreatePage.tsx  # Main expense creation flow (receipt → items → assignment → review)
│   │   │   ├── ExpenseDetailPage.tsx  # View expense details, settlement status
│   │   │   ├── ExpenseListPage.tsx    # List all expenses (active, settled, archived)
│   │   │   ├── ItemAssignmentForm.tsx # Assign line items to users (checkboxes, multi-select)
│   │   │   ├── ItemAssignmentReview.tsx # Review assignments before finalizing
│   │   │   ├── TaxTipForm.tsx         # Enter tax and tip amounts, select distribution method
│   │   │   ├── SettlementCalculation.tsx # Display calculated settlement (who owes whom)
│   │   │   ├── ExpenseCard.tsx        # Compact expense card for list view
│   │   │   ├── ParticipantList.tsx    # List participants in expense with amounts owed
│   │   │   └── styles/
│   │   │       └── expense.module.css
│   │   │
│   │   ├── recurring/
│   │   │   ├── RecurringListPage.tsx  # List recurring splits (active, paused, completed)
│   │   │   ├── RecurringCreatePage.tsx # Create new recurring split
│   │   │   ├── RecurringDetailPage.tsx # View recurring split details, edit, pause, cancel
│   │   │   ├── RecurringForm.tsx      # Form to create/edit recurring split (amount, frequency, participants)
│   │   │   ├── RecurringSchedulePreview.tsx # Show next 3 occurrences of recurring split
│   │   │   └── styles/
│   │   │       └── recurring.module.css
│   │   │
│   │   ├── dashboard/
│   │   │   ├── DashboardPage.tsx      # Main dashboard (active splits, due payments, summary)
│   │   │   ├── DuePaymentsWidget.tsx  # Widget showing payments due to current user
│   │   │   ├── OwedPaymentsWidget.tsx # Widget showing payments owed by current user
│   │   │   ├── RecentActivityWidget.tsx # Recent expense activity (last 5 items)
│   │   │   ├── SummaryStatsWidget.tsx # Summary stats (total owed, total due, number of active splits)
│   │   │   └── styles/
│   │   │       └── dashboard.module.css
│   │   │
│   │   ├── user/
│   │   │   ├── ProfilePage.tsx        # User profile page (name, email, settings)
│   │   │   ├── ProfileForm.tsx        # Edit profile form
│   │   │   ├── AccountSettingsPage.tsx # Account settings (password change, email preferences)
│   │   │   ├── PasswordChangeForm.tsx # Change password form
│   │   │   └── styles/
│   │   │       └── user.module.css
│   │   │
│   │   └── settlement/
│   │       ├── PaymentStatusPage.tsx  # View payment status for a split
│   │       ├── PaymentReminder.tsx    # Display payment reminder with payment link options
│   │       ├── PaymentLinkGenerator.tsx # Generate Venmo/PayPal payment links
│   │       ├── SettlementSummary.tsx  # Summary of all transactions needed to settle
│   │       └── styles/
│   │           └── settlement.module.css
│   │
│   ├── hooks/
│   │   ├── useAuth.ts                 # Hook for auth state and operations (login, logout, signup)
│   │   ├── useExpense.ts              # Hook for expense operations (create, list, update)
│   │   ├── useReceipt.ts              # Hook for receipt upload and OCR status
│   │   ├── useSplit.ts                # Hook for split calculation and settlement
│   │   ├── useRecurring.ts            # Hook for recurring split operations
│   │   ├── useForm.ts                 # Generic form state management hook
│   │   ├── useFetch.ts                # Generic data fetching hook with error/loading states
│   │   ├── useNotification.ts         # Hook for displaying notifications
│   │   └── useLocalStorage.ts         # Hook for local storage access with cleanup
│   │
│   ├── middleware/
│   │   ├── authMiddleware.ts          # Intercept API responses, handle 401 unauthorized
│   │   ├── errorMiddleware.ts         # Map API errors to user-friendly messages
│   │   └── retryMiddleware.ts         # Retry logic for transient failures
│   │
│   └── styles/
│       ├── index.css                  # Global styles, CSS variables (colors, fonts, spacing)
│       ├── responsive.css             # Responsive design breakpoints
│       └── animations.css             # Reusable animations (fade, slide, spin)
│
├── .env.example                       # Example environment variables
├── .eslintrc.js                       # ESLint configuration
├── .prettierrc                        # Prettier code formatting config
├── tsconfig.json                      # TypeScript configuration
├── package.json                       # Dependencies, scripts
└── vite.config.ts                     # Vite build configuration (or webpack.config.js if using CRA)
```

## 6.2 TypeScript Type Definitions

### 6.2.1 Domain Types (src/types/domain.ts)

```typescript
// User & Authentication
export interface User {
  id: string;
  email: string;
  fullName: string;
  createdAt: string;          // ISO 8601 timestamp
  updatedAt: string;
  status: 'active' | 'suspended' | 'deleted';
}

export interface AuthTokens {
  accessToken: string;        // JWT, expires in 1 hour
  refreshToken: string;       // JWT, expires in 7 days
  expiresIn: number;          // Seconds until access token expiration
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// Expense & Line Items
export interface LineItem {
  id: string;
  expenseId: string;
  name: string;                       // e.g., "Grilled Salmon"
  price: number;                      // In cents (e.g., 2500 = $25.00)
  quantity: number;                   // Default 1
  assignedToUserIds: string[];        // Users who ordered this item
  createdAt: string;
  updatedAt: string;
}

export interface Expense {
  id: string;
  createdByUserId: string;            // User who uploaded receipt
  groupId: string;                    // Group this expense belongs to
  description: string;                // e.g., "Dinner at Luigi's" or "Rent - January 2024"
  receiptImageUrl?: string;           // URL to uploaded receipt image (nullable)
  receiptOCRStatus: 'pending' | 'success' | 'failed';  // OCR processing status
  lineItems: LineItem[];
  subtotal: number;                   // Sum of all line items (cents)
  tax: number;                        // Tax amount (cents)
  tip: number;                        // Tip amount (cents)
  taxDistributionMethod: 'proportional' | 'equal' | 'manual';  // How to split tax
  tipDistributionMethod: 'proportional' | 'equal' | 'manual';  // How to split tip
  total: number;                      // subtotal + tax + tip (cents)
  settlementStatus: 'open' | 'settled' | 'partially_settled';
  createdAt: string;
  updatedAt: string;
}

export interface Split {
  id: string;
  expenseId: string;
  fromUserId: string;                 // User who owes money
  toUserId: string;                   // User to receive money
  amount: number;                     // Amount owed (cents)
  paymentStatus: 'pending' | 'completed' | 'cancelled';
  paymentMethod?: 'venmo' | 'paypal' | 'cash' | 'bank_transfer';  // How payment was made
  paidAt?: string;                    // When payment was completed
  createdAt: string;
  updatedAt: string;
}

export interface RecurringSplit {
  id: string;
  groupId: string;
  createdByUserId: string;
  description: string;                // e.g., "Rent - Apt 4B" or "Internet Bill"
  amount: number;                     // Amount per occurrence (cents)
  frequency: 'weekly' | 'biweekly' | 'monthly';
  startDate: string;                  // ISO 8601 date (YYYY-MM-DD)
  endDate?: string;                   // Optional; if null, recurring indefinitely
  participants: RecurringSplitParticipant[];  // Users involved in this recurring split
  status: 'active' | 'paused' | 'completed';
  createdAt: string;
  updatedAt: string;
}

export interface RecurringSplitParticipant {
  userId: string;
  role: 'payer' | 'recipient';        // Payer = owes money; Recipient = receives money
}

export interface Group {
  id: string;
  name: string;                       // e.g., "Apartment Mates" or "Vegas Trip 2024"
  createdByUserId: string;
  members: GroupMember[];
  createdAt: string;
  updatedAt: string;
}

export interface GroupMember {
  userId: string;
  user: User;                         // Full user object (name, email)
  joinedAt: string;
}

// Receipt OCR
export interface ReceiptOCRResult {
  receiptId: string;
  status: 'pending' | 'success' | 'failed';
  lineItems?: Array<{
    name: string;
    price: number;                    // In cents
    quantity: number;
  }>;
  subtotal?: number;                  // In cents
  tax?: number;                       // In cents
  tip?: number;                       // In cents
  total?: number;                     // In cents
  confidence?: number;                // 0-100, OCR accuracy percentage
  errorMessage?: string;              // If status = 'failed'
  processedAt?: string;
}

// Settlement Calculation
export interface SettlementCalculation {
  expenseId: string;
  transactions: SettlementTransaction[];  // Minimal set of transactions to settle all debts
  totalAmount: number;                // Total amount involved (cents)
}

export interface SettlementTransaction {
  fromUserId: string;
  fromUserName: string;
  toUserId: string;
  toUserName: string;
  amount: number;                     // In cents
  reason: string;                     // e.g., "Share of Dinner at Luigi's"
}

// Notification/Email
export interface EmailNotification {
  id: string;
  recipientUserId: string;
  recipientEmail: string;
  type: 'payment_due' | 'payment_reminder' | 'payment_received' | 'expense_settled' | 'recurring_split_created';
  subject: string;
  body: string;
  relatedExpenseId?: string;
  relatedSplitId?: string;
  sentAt: string;
  deliveryStatus: 'pending' | 'sent' | 'bounced' | 'failed';
  deliveryAttempts: number;
  lastAttemptAt?: string;
}
```

### 6.2.2 API Request/Response Types (src/types/api.ts)

```typescript
// Auth Endpoints
export interface SignupRequest {
  email: string;
  password: string;
  fullName: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RefreshTokenRequest {
  refreshToken: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirmRequest {
  token: string;
  newPassword: string;
}

// Expense Endpoints
export interface CreateExpenseRequest {
  groupId: string;
  description: string;
  receiptImageUrl?: string;           // Optional; can be added after line items
  lineItems: CreateLineItemRequest[];
  tax: number;                        // In cents
  tip: number;                        // In cents
  taxDistributionMethod: 'proportional' | 'equal' | 'manual';
  tipDistributionMethod: 'proportional' | 'equal' | 'manual';
}

export interface CreateLineItemRequest {
  name: string;
  price: number;                      // In cents
  quantity: number;
  assignedToUserIds: string[];
}

export interface UpdateExpenseRequest {
  description?: string;
  tax?: number;
  tip?: number;
  taxDistributionMethod?: 'proportional' | 'equal' | 'manual';
  tipDistributionMethod?: 'proportional' | 'equal' | 'manual';
}

export interface UpdateLineItemRequest {
  name?: string;
  price?: number;
  quantity?: number;
  assignedToUserIds?: string[];
}

export interface ListExpensesRequest {
  groupId: string;
  status?: 'open' | 'settled' | 'all';
  limit?: number;                     // Default 20, max 100
  offset?: number;                    // Default 0
}

// Receipt Upload
export interface UploadReceiptRequest {
  expenseId: string;
  imageFile: File;                    // Multipart form data
}

export interface UploadReceiptResponse {
  receiptId: string;
  imageUrl: string;
  ocrStatus: 'pending' | 'success' | 'failed';
  ocrResult?: ReceiptOCRResult;
}

export interface GetReceiptOCRStatusResponse {
  receiptId: string;
  status: 'pending' | 'success' | 'failed';
  ocrResult?: ReceiptOCRResult;
}

// Split Endpoints
export interface CalculateSettlementRequest {
  expenseId: string;
}

export interface CalculateSettlementResponse {
  settlement: SettlementCalculation;
  splits: Split[];
}

export interface MarkSplitPaidRequest {
  splitId: string;
  paymentMethod: 'venmo' | 'paypal' | 'cash' | 'bank_transfer';
  transactionId?: string;             // Optional reference ID from payment provider
}

// Recurring Split Endpoints
export interface CreateRecurringSplitRequest {
  groupId: string;
  description: string;
  amount: number;                     // In cents
  frequency: 'weekly' | 'biweekly' | 'monthly';
  startDate: string;                  // ISO 8601 date (YYYY-MM-DD)
  endDate?: string;                   // Optional
  participants: CreateRecurringSplitParticipantRequest[];
}

export interface CreateRecurringSplitParticipantRequest {
  userId: string;
  role: 'payer' | 'recipient';
}

export interface UpdateRecurringSplitRequest {
  description?: string;
  amount?: number;
  frequency?: 'weekly' | 'biweekly' | 'monthly';
  endDate?: string;
  status?: 'active' | 'paused' | 'completed';
}

export interface ListRecurringSplitsRequest {
  groupId: string;
  status?: 'active' | 'paused' | 'completed' | 'all';
  limit?: number;
  offset?: number;
}

// Group Endpoints
export interface CreateGroupRequest {
  name: string;
  memberEmails: string[];             // Emails of users to invite
}

export interface AddGroupMemberRequest {
  email: string;
}

export interface ListGroupsRequest {
  limit?: number;
  offset?: number;
}

// Generic Responses
export interface ApiResponse<T> {
  data: T;
  meta?: {
    pagination?: {
      total: number;
      limit: number;
      offset: number;
    };
  };
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Array<{
      field: string;
      message: string;
    }>;
    requestId: string;
  };
}

export interface ListResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
```

### 6.2.3 UI State Types (src/types/ui.ts)

```typescript
export interface FormState {
  values: Record<string, any>;
  errors: Record<string, string>;
  touched: Record<string, boolean>;
  isSubmitting: boolean;
  isValid: boolean;
}

export interface LoadingState {
  isLoading: boolean;
  error?: string;
  errorCode?: string;
}

export interface PaginationState {
  limit: number;
  offset: number;
  total: number;
}

export interface NotificationState {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;                  // Auto-dismiss after N ms (null = manual dismiss)
}

export interface ModalState {
  isOpen: boolean;
  title?: string;
  content?: React.ReactNode;
  actions?: ModalAction[];
}

export interface ModalAction {
  label: string;
  onClick: () => void;
  variant: 'primary' | 'secondary' | 'danger';
}

export interface AuthState {
  user: User | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error?: string;
}

export interface ExpenseState {
  expenses: Expense[];
  selectedExpense: Expense | null;
  isLoading: boolean;
  error?: string;
  pagination: PaginationState;
}

export interface ReceiptState {
  receiptId?: string;
  imageUrl?: string;
  ocrStatus: 'idle' | 'pending' | 'success' | 'failed';
  ocrResult?: ReceiptOCRResult;
  error?: string;
  uploadProgress: number;             // 0-100
}

export interface RecurringState {
  recurring: RecurringSplit[];
  selectedRecurring: RecurringSplit | null;
  isLoading: boolean;
  error?: string;
  pagination: PaginationState;
}

export interface SettlementState {
  calculation?: SettlementCalculation;
  splits: Split[];
  isCalculating: boolean;
  error?: string;
}
```

## 6.3 Component Specifications

### 6.3.1 Common Components

#### Button Component (src/components/common/Button.tsx)

```typescript
interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit' | 'reset';
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'small' | 'medium' | 'large';
  disabled?: boolean;
  isLoading?: boolean;
  fullWidth?: boolean;
  className?: string;
  ariaLabel?: string;
}

/**
 * Reusable button component with multiple variants and states.
 * 
 * Variants:
 * - primary: Blue background, white text, main action button
 * - secondary: Gray background, dark text, secondary action
 * - danger: Red background, white text, destructive action (delete, cancel)
 * - ghost: No background, colored text, minimal style
 * 
 * States:
 * - disabled: Grayed out, not clickable
 * - isLoading: Shows spinner, disables click, maintains width
 * 
 * Responsive: Full width on mobile, auto width on desktop
 * Accessibility: ARIA labels, keyboard navigation support
 */
export const Button: React.FC<ButtonProps> = ({
  children,
  onClick,
  type = 'button',
  variant = 'primary',
  size = 'medium',
  disabled = false,
  isLoading = false,
  fullWidth = false,
  className,
  ariaLabel,
}) => {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || isLoading}
      className={`button button--${variant} button--${size} ${fullWidth ? 'button--full-width' : ''} ${className}`}
      aria-label={ariaLabel}
      aria-busy={isLoading}
    >
      {isLoading ? <Spinner size="small" /> : children}
    </button>
  );
};
```

#### Input Component (src/components/common/Input.tsx)

```typescript
interface InputProps {
  label?: string;
  name: string;
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'date';
  placeholder?: string;
  value: string | number;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
  error?: string;
  touched?: boolean;
  disabled?: boolean;
  required?: boolean;
  autoComplete?: string;
  maxLength?: number;
  pattern?: string;
  step?: string | number;                 // For number inputs
  min?: string | number;
  max?: string | number;
  className?: string;
  helperText?: string;
}

/**
 * Reusable text input component with validation feedback.
 * 
 * Features:
 * - Label, placeholder, helper text
 * - Error display (red border, error message)
 * - Touched state (error only shows after blur)
 * - Disabled state
 * - Support for multiple input types (text, email, password, number, date, etc.)
 * - Accessibility: aria-invalid, aria-describedby
 * 
 * Validation feedback:
 * - Red border when error && touched
 * - Error message below input
 * - Helper text for guidance
 */
export const Input: React.FC<InputProps> = ({
  label,
  name,
  type = 'text',
  placeholder,
  value,
  onChange,
  onBlur,
  error,
  touched,
  disabled,
  required,
  autoComplete,
  maxLength,
  pattern,
  step,
  min,
  max,
  className,
  helperText,
}) => {
  const hasError = error && touched;
  const inputId = `input-${name}`;
  const errorId = `error-${name}`;
  const helperId = `helper-${name}`;

  return (
    <div className={`input-wrapper ${className}`}>
      {label && (
        <label htmlFor={inputId} className="input-label">
          {label}
          {required && <span className="required-indicator">*</span>}
        </label>
      )}
      <input
        id={inputId}
        name={name}
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        disabled={disabled}
        maxLength={maxLength}
        pattern={pattern}
        step={step}
        min={min}
        max={max}
        autoComplete={autoComplete}
        className={`input ${hasError ? 'input--error' : ''}`}
        aria-invalid={hasError}
        aria-describedby={hasError ? errorId : helperText ? helperId : undefined}
      />
      {hasError && (
        <span id={errorId} className="input-error">
          {error}
        </span>
      )}
      {helperText && !hasError && (
        <span id={helperId} className="input-helper">
          {helperText}
        </span>
      )}
    </div>
  );
};
```

#### Modal Component (src/components/common/Modal.tsx)

```typescript
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  actions?: Array<{
    label: string;
    onClick: () => void;
    variant: 'primary' | 'secondary' | 'danger';
    disabled?: boolean;
  }>;
  size?: 'small' | 'medium' | 'large';
  closeOnBackdropClick?: boolean;
  closeOnEscapeKey?: boolean;
}

/**
 * Reusable modal/dialog component.
 * 
 * Features:
 * - Backdrop overlay (semi-transparent)
 * - Close button (X icon)
 * - Title and content
 * - Action buttons (OK, Cancel, Delete, etc.)
 * - Keyboard handling (Escape to close)
 * - Backdrop click handling
 * - Focus trap (focus stays within modal)
 * - ARIA attributes (role="dialog", aria-modal="true")
 * 
 * Accessibility:
 * - Focus trap on modal
 * - Escape key closes modal
 * - Backdrop click closes modal (configurable)
 * - ARIA live region for announcements
 */
export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  actions,
  size = 'medium',
  closeOnBackdropClick = true,
  closeOnEscapeKey = true,
}) => {
  React.useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (closeOnEscapeKey && e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose, closeOnEscapeKey]);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={closeOnBackdropClick ? onClose : undefined}>
      <div className={`modal modal--${size}`} onClick={(e)

> **Guardrail Warning**: Design missing critical sections: ['security', 'scalab', 'monitor', 'deploy']

---

# 7. BACKEND SERVICE ARCHITECTURE & ALGORITHMS

## 7.1 Service Layer Organization

```
backend/
├── src/
│   ├── index.ts                       # Express app initialization, middleware setup
│   ├── server.ts                      # HTTP server startup, graceful shutdown
│   │
│   ├── config/
│   │   ├── database.ts                # PostgreSQL connection pool, ORM setup
│   │   ├── env.ts                     # Environment variable loader with validation
│   │   ├── logger.ts                  # Winston/Pino structured logging configuration
│   │   ├── queue.ts                   # Bull/RabbitMQ task queue initialization
│   │   └── constants.ts               # App-wide constants (limits, timeouts, error codes)
│   │
│   ├── middleware/
│   │   ├── auth.ts                    # JWT verification, token extraction
│   │   ├── authorization.ts           # Permission checks (resource ownership, role-based)
│   │   ├── errorHandler.ts            # Global error handler (catches all errors, formats response)
│   │   ├── requestLogger.ts           # HTTP request/response logging with request ID
│   │   ├── rateLimiter.ts             # Rate limiting (IP-based, user-based)
│   │   ├── cors.ts                    # CORS configuration for frontend origin
│   │   ├── helmet.ts                  # Security headers (CSP, X-Frame-Options, etc.)
│   │   └── requestValidator.ts        # Request body/query validation (Joi/Zod schemas)
│   │
│   ├── routes/
│   │   ├── index.ts                   # Route aggregation, version prefix (/api/v1)
│   │   ├── auth.ts                    # POST /auth/signup, /auth/login, /auth/logout, /auth/refresh
│   │   ├── users.ts                   # GET /users/me, PATCH /users/me, DELETE /users/me
│   │   ├── expenses.ts                # POST /expenses, GET /expenses, GET /expenses/:id, PATCH /expenses/:id, DELETE /expenses/:id
│   │   ├── receipts.ts                # POST /receipts/upload, GET /receipts/:id/status, GET /receipts/:id/items
│   │   ├── splits.ts                  # POST /splits/calculate, GET /splits, GET /splits/:id, PATCH /splits/:id/settle
│   │   ├── groups.ts                  # POST /groups, GET /groups, GET /groups/:id, PATCH /groups/:id, DELETE /groups/:id
│   │   ├── recurringSpits.ts          # POST /recurring-splits, GET /recurring-splits, PATCH /recurring-splits/:id, DELETE /recurring-splits/:id
│   │   └── health.ts                  # GET /health (liveness probe), GET /health/ready (readiness probe)
│   │
│   ├── controllers/
│   │   ├── authController.ts          # Request handling for auth routes
│   │   ├── userController.ts          # Request handling for user routes
│   │   ├── expenseController.ts       # Request handling for expense routes
│   │   ├── receiptController.ts       # Request handling for receipt routes
│   │   ├── splitController.ts         # Request handling for split routes
│   │   ├── groupController.ts         # Request handling for group routes
│   │   └── recurringSpitController.ts # Request handling for recurring split routes
│   │
│   ├── services/
│   │   ├── authService.ts             # Password hashing, JWT generation, token validation
│   │   ├── userService.ts             # User CRUD, profile management
│   │   ├── expenseService.ts          # Expense creation, item management, state transitions
│   │   ├── receiptService.ts          # Receipt upload orchestration, OCR provider integration
│   │   ├── splitService.ts            # Split calculation, payment optimization algorithm
│   │   ├── groupService.ts            # Group management, member invitation
│   │   ├── recurringSpitService.ts    # Recurring split scheduling, trigger logic
│   │   ├── notificationService.ts     # Email dispatch, reminder scheduling
│   │   ├── ocrService.ts              # OCR provider abstraction (Google Vision / AWS Textract)
│   │   └── emailService.ts            # Email template rendering, SendGrid/SES integration
│   │
│   ├── repositories/
│   │   ├── userRepository.ts          # User table queries
│   │   ├── expenseRepository.ts       # Expense + line item queries
│   │   ├── splitRepository.ts         # Split + settlement queries
│   │   ├── groupRepository.ts         # Group + membership queries
│   │   ├── recurringSpitRepository.ts # Recurring split queries
│   │   ├── receiptRepository.ts       # Receipt metadata queries
│   │   ├── auditLogRepository.ts      # Audit log queries (immutable)
│   │   └── baseRepository.ts          # Base class with common CRUD operations
│   │
│   ├── models/
│   │   ├── User.ts                    # User entity (ORM model)
│   │   ├── Group.ts                   # Group entity
│   │   ├── Expense.ts                 # Expense entity
│   │   ├── LineItem.ts                # Line item entity
│   │   ├── Split.ts                   # Split (settlement) entity
│   │   ├── Payment.ts                 # Payment record entity
│   │   ├── RecurringSpitTemplate.ts   # Recurring split template entity
│   │   ├── Receipt.ts                 # Receipt metadata entity
│   │   └── AuditLog.ts                # Audit log entity (immutable)
│   │
│   ├── jobs/
│   │   ├── ocrProcessingJob.ts        # Async OCR processing (queue worker)
│   │   ├── emailReminderJob.ts        # Async email reminder dispatch
│   │   ├── recurringSpitTriggerJob.ts # Scheduled job to trigger recurring splits
│   │   └── settlementCleanupJob.ts    # Scheduled job to archive old settlements
│   │
│   ├── utils/
│   │   ├── logger.ts                  # Logging utilities
│   │   ├── errors.ts                  # Custom error classes
│   │   ├── validators.ts              # Validation utilities (email, phone, etc.)
│   │   ├── crypto.ts                  # Cryptographic utilities (token generation, hashing)
│   │   ├── math.ts                    # Financial math utilities (tax/tip calculation, rounding)
│   │   └── helpers.ts                 # General helper functions
│   │
│   └── types/
│       ├── index.ts                   # Shared TypeScript types
│       ├── database.ts                # ORM model types
│       ├── api.ts                     # API request/response types
│       └── errors.ts                  # Error type definitions
│
├── migrations/
│   ├── 20240101_000000_init_schema.sql # Initial schema (users, groups, expenses, etc.)
│   ├── 20240115_000000_add_receipts.sql
│   └── [YYYYMMDD_HHMMSS_description.sql] # Timestamp-based versioning
│
├── seeds/
│   ├── dev.seed.ts                    # Development data (test users, sample expenses)
│   └── test.seed.ts                   # Test data (fixtures for unit/integration tests)
│
├── tests/
│   ├── unit/
│   │   ├── services/
│   │   │   ├── authService.test.ts
│   │   │   ├── splitService.test.ts
│   │   │   └── ...
│   │   ├── utils/
│   │   │   ├── validators.test.ts
│   │   │   └── math.test.ts
│   │   └── models/
│   │       └── ...
│   ├── integration/
│   │   ├── auth.integration.test.ts   # Full auth flow (signup, login, token refresh)
│   │   ├── expenses.integration.test.ts # Expense creation, item assignment, settlement
│   │   ├── receipts.integration.test.ts # Receipt upload, OCR processing, item extraction
│   │   └── ...
│   └── e2e/
│       ├── happyPath.e2e.test.ts      # Complete user journey (signup → expense → settlement)
│       └── errorScenarios.e2e.test.ts # Error handling, edge cases, race conditions
│
├── .env.example                       # Environment variable template (no secrets)
├── .env.test                          # Test environment configuration
├── jest.config.js                     # Jest test runner configuration
├── tsconfig.json                      # TypeScript configuration
├── package.json                       # Dependencies, scripts, metadata
└── README.md                          # Backend setup and development instructions
```

## 7.2 Core Service Interfaces & Contracts

### 7.2.1 Authentication Service

```typescript
// services/authService.ts

interface IAuthService {
  /**
   * Hash password using bcrypt (cost factor 12)
   * @param password Plain-text password
   * @returns Bcrypt hash ($2b$12$...)
   * @throws Error if hashing fails
   */
  hashPassword(password: string): Promise<string>;

  /**
   * Compare plain-text password against bcrypt hash
   * @param password Plain-text password
   * @param hash Bcrypt hash to compare against
   * @returns true if match, false otherwise
   */
  comparePassword(password: string, hash: string): Promise<boolean>;

  /**
   * Generate JWT access token (1 hour expiration)
   * @param userId User ID to encode in token
   * @returns JWT token string
   */
  generateAccessToken(userId: string): string;

  /**
   * Generate JWT refresh token (7 day expiration)
   * @param userId User ID to encode in token
   * @returns JWT token string
   */
  generateRefreshToken(userId: string): string;

  /**
   * Verify and decode JWT token
   * @param token JWT token to verify
   * @returns Decoded token payload { userId, exp, iat }
   * @throws Error if token is invalid or expired
   */
  verifyToken(token: string): Promise<{ userId: string; exp: number; iat: number }>;

  /**
   * Extract user ID from JWT token (without verification)
   * @param token JWT token to decode
   * @returns User ID from token payload
   * @throws Error if token is malformed
   */
  extractUserIdFromToken(token: string): string;
}

// Implementation
class AuthService implements IAuthService {
  private readonly JWT_SECRET = process.env.JWT_SECRET || 'dev-secret';
  private readonly JWT_ACCESS_EXPIRY = '1h';
  private readonly JWT_REFRESH_EXPIRY = '7d';
  private readonly BCRYPT_COST = 12;

  async hashPassword(password: string): Promise<string> {
    return bcrypt.hash(password, this.BCRYPT_COST);
  }

  async comparePassword(password: string, hash: string): Promise<boolean> {
    return bcrypt.compare(password, hash);
  }

  generateAccessToken(userId: string): string {
    return jwt.sign({ userId }, this.JWT_SECRET, { expiresIn: this.JWT_ACCESS_EXPIRY });
  }

  generateRefreshToken(userId: string): string {
    return jwt.sign({ userId }, this.JWT_SECRET, { expiresIn: this.JWT_REFRESH_EXPIRY });
  }

  async verifyToken(token: string): Promise<{ userId: string; exp: number; iat: number }> {
    try {
      return jwt.verify(token, this.JWT_SECRET) as { userId: string; exp: number; iat: number };
    } catch (error) {
      throw new AuthenticationError('Invalid or expired token');
    }
  }

  extractUserIdFromToken(token: string): string {
    const decoded = jwt.decode(token) as any;
    if (!decoded?.userId) throw new AuthenticationError('Malformed token');
    return decoded.userId;
  }
}
```

### 7.2.2 Expense Service

```typescript
// services/expenseService.ts

interface IExpenseService {
  /**
   * Create a new expense with line items
   * @param input Expense creation payload
   * @returns Created expense with line items
   */
  createExpense(input: CreateExpenseInput): Promise<ExpenseDTO>;

  /**
   * Claim a line item for a user
   * @param expenseId Expense ID
   * @param lineItemId Line item ID
   * @param userId User ID claiming the item
   * @returns Updated expense with line item assigned
   */
  claimLineItem(expenseId: string, lineItemId: string, userId: string): Promise<ExpenseDTO>;

  /**
   * Unclaim a line item (remove user assignment)
   * @param expenseId Expense ID
   * @param lineItemId Line item ID
   * @returns Updated expense with line item unassigned
   */
  unclaimLineItem(expenseId: string, lineItemId: string): Promise<ExpenseDTO>;

  /**
   * Finalize expense (lock it; prevent further changes)
   * @param expenseId Expense ID
   * @returns Finalized expense
   */
  finalizeExpense(expenseId: string): Promise<ExpenseDTO>;

  /**
   * Get expense by ID with all line items and assignments
   * @param expenseId Expense ID
   * @param userId User ID requesting (for authorization)
   * @returns Expense with line items and assignments
   */
  getExpense(expenseId: string, userId: string): Promise<ExpenseDTO>;

  /**
   * List all expenses for a user or group
   * @param filters Filter criteria (userId, groupId, status, dateRange)
   * @param pagination Offset and limit
   * @returns Paginated list of expenses
   */
  listExpenses(
    filters: ExpenseFilters,
    pagination: PaginationParams
  ): Promise<PaginatedResponse<ExpenseDTO>>;

  /**
   * Delete expense (only if not finalized)
   * @param expenseId Expense ID
   * @param userId User ID requesting (for authorization)
   * @returns Deleted expense
   */
  deleteExpense(expenseId: string, userId: string): Promise<ExpenseDTO>;
}

interface CreateExpenseInput {
  groupId: string;                      // Group this expense belongs to
  description: string;                  // e.g., "Dinner at Joe's Pizza"
  totalAmount: number;                  // Amount in cents (e.g., 2500 for $25.00)
  paidByUserId: string;                 // User who paid the bill
  lineItems: LineItemInput[];           // Items ordered
  taxAmount?: number;                   // Tax in cents (optional; calculated if not provided)
  tipAmount?: number;                   // Tip in cents (optional; calculated if not provided)
  currency: 'USD';                      // v1 supports USD only
  receiptImageUrl?: string;             // URL to uploaded receipt image (optional)
  date: Date;                           // When expense occurred
}

interface LineItemInput {
  description: string;                  // Item name (e.g., "Margherita Pizza")
  amount: number;                       // Item price in cents (before tax/tip)
  quantity?: number;                    // Quantity ordered (default 1)
}

interface ExpenseDTO {
  id: string;
  groupId: string;
  description: string;
  totalAmount: number;                  // Total including tax/tip
  subtotal: number;                     // Amount before tax/tip
  taxAmount: number;
  tipAmount: number;
  paidByUserId: string;
  paidByUser: UserDTO;
  lineItems: LineItemDTO[];
  status: 'draft' | 'finalized' | 'settled';
  createdAt: Date;
  updatedAt: Date;
}

interface LineItemDTO {
  id: string;
  description: string;
  amount: number;
  quantity: number;
  claimedByUserId?: string;             // User who claimed this item (null if unclaimed)
  claimedByUser?: UserDTO;
}
```

### 7.2.3 Split Service (Payment Optimization Algorithm)

```typescript
// services/splitService.ts

interface ISplitService {
  /**
   * Calculate optimized payment settlements for an expense
   * Minimizes number of P2P transactions needed to settle all debts
   * @param expenseId Expense ID
   * @returns Split settlement with optimized payment flows
   */
  calculateSplit(expenseId: string): Promise<SplitDTO>;

  /**
   * Get split calculation for an expense
   * @param expenseId Expense ID
   * @returns Split settlement details
   */
  getSplit(expenseId: string): Promise<SplitDTO>;

  /**
   * Mark a payment as completed
   * @param splitId Split ID
   * @param paymentId Payment ID
   * @param completedAt Timestamp when payment was made
   * @returns Updated split with payment marked complete
   */
  markPaymentComplete(splitId: string, paymentId: string, completedAt: Date): Promise<SplitDTO>;

  /**
   * Settle entire split (mark all payments as complete)
   * @param splitId Split ID
   * @returns Settled split
   */
  settleSplit(splitId: string): Promise<SplitDTO>;
}

interface SplitDTO {
  id: string;
  expenseId: string;
  expense: ExpenseDTO;
  payments: PaymentFlowDTO[];           // Optimized payment flows
  status: 'pending' | 'partial' | 'settled';
  createdAt: Date;
  updatedAt: Date;
}

interface PaymentFlowDTO {
  id: string;
  fromUserId: string;
  fromUser: UserDTO;
  toUserId: string;
  toUser: UserDTO;
  amount: number;                       // Amount owed in cents
  status: 'pending' | 'completed';
  completedAt?: Date;
  paymentMethod?: string;               // 'venmo', 'paypal', 'cash', etc.
}
```

#### 7.2.3.1 Payment Optimization Algorithm

**Problem:** Given an expense with multiple people owing money to the person who paid, minimize the number of P2P transactions needed to settle all debts.

**Example:**
- Expense: $100 dinner, paid by Alice
- Line items claimed: Bob ($30), Charlie ($40), Diana ($30)
- Naive settlement: Bob → Alice ($30), Charlie → Alice ($40), Diana → Alice ($30) = 3 transactions
- Optimized: Same as naive in this case (all owe Alice), but algorithm should handle complex cases

**Complex example:**
- Expense: $100, paid by Alice
- Claims: Bob ($30), Charlie ($40), Diana ($30)
- But Bob also paid for something Charlie owes him $20
- Naive: Bob → Alice ($30), Charlie → Alice ($40), Diana → Alice ($30) = 3 transactions
- Optimized: Bob → Alice ($10), Charlie → Alice ($20), Diana → Alice ($30) = 3 transactions (or use net settlement)

**Algorithm Specification:**

```typescript
/**
 * Payment Optimization Algorithm: Minimize P2P Transactions
 * 
 * Approach: Graph-based debt settlement
 * 1. Build debt graph: nodes = users, edges = who owes whom
 * 2. Calculate net balance for each user (total owed - total owed to them)
 * 3. Separate users into debtors (negative balance) and creditors (positive balance)
 * 4. Greedily match largest debtor with largest creditor until all settled
 * 
 * Time Complexity: O(n log n) where n = number of users
 * Space Complexity: O(n)
 * 
 * Result: Minimizes transaction count to at most n-1 (where n = number of users with non-zero balance)
 */

interface DebtNode {
  userId: string;
  balance: number;                      // Positive = creditor, negative = debtor
}

function optimizePaymentSettlement(expense: Expense): PaymentFlow[] {
  // Step 1: Calculate net balance per user
  const balances = new Map<string, number>();
  
  // Add paid amount (payer gets credit)
  balances.set(expense.paidByUserId, expense.totalAmount);
  
  // Subtract claimed amounts per user
  for (const item of expense.lineItems) {
    if (item.claimedByUserId) {
      const current = balances.get(item.claimedByUserId) || 0;
      balances.set(item.claimedByUserId, current - item.amount);
    }
  }
  
  // Step 2: Separate debtors and creditors
  const debtors: DebtNode[] = [];
  const creditors: DebtNode[] = [];
  
  for (const [userId, balance] of balances.entries()) {
    if (balance < 0) {
      debtors.push({ userId, balance });
    } else if (balance > 0) {
      creditors.push({ userId, balance });
    }
  }
  
  // Step 3: Sort by absolute balance (largest first) for greedy matching
  debtors.sort((a, b) => a.balance - b.balance); // Most negative first
  creditors.sort((a, b) => b.balance - a.balance); // Most positive first
  
  // Step 4: Greedily match debtors to creditors
  const payments: PaymentFlow[] = [];
  let debtorIdx = 0;
  let creditorIdx = 0;
  
  while (debtorIdx < debtors.length && creditorIdx < creditors.length) {
    const debtor = debtors[debtorIdx];
    const creditor = creditors[creditorIdx];
    
    const amountToPay = Math.min(Math.abs(debtor.balance), creditor.balance);
    
    payments.push({
      fromUserId: debtor.userId,
      toUserId: creditor.userId,
      amount: amountToPay,
    });
    
    debtor.balance += amountToPay;
    creditor.balance -= amountToPay;
    
    if (Math.abs(debtor.balance) < 0.01) debtorIdx++;
    if (creditor.balance < 0.01) creditorIdx++;
  }
  
  return payments;
}
```

### 7.2.4 Receipt Service (OCR Integration)

```typescript
// services/receiptService.ts

interface IReceiptService {
  /**
   * Upload receipt image and queue OCR processing
   * @param input Upload payload with image file
   * @returns Receipt metadata with processing status
   */
  uploadReceipt(input: UploadReceiptInput): Promise<ReceiptDTO>;

  /**
   * Get receipt metadata and processing status
   * @param receiptId Receipt ID
   * @returns Receipt with current OCR status
   */
  getReceipt(receiptId: string): Promise<ReceiptDTO>;

  /**
   * Get extracted line items from receipt (once OCR completes)
   * @param receiptId Receipt ID
   * @returns List of extracted line items
   * @throws Error if OCR not yet complete or failed
   */
  getExtractedItems(receiptId: string): Promise<ExtractedLineItemDTO[]>;

  /**
   * Manually correct extracted line items (if OCR accuracy is low)
   * @param receiptId Receipt ID
   * @param corrections Corrected items to replace extracted items
   * @returns Updated receipt with corrected items
   */
  correctExtractedItems(
    receiptId: string,
    corrections: CorrectedLineItemInput[]
  ): Promise<ReceiptDTO>;
}

interface UploadReceiptInput {
  file: Express.Multer.File;            // Image file (JPEG, PNG, PDF)
  expenseId?: string;                   // Optional: link to expense
}

interface ReceiptDTO {
  id: string;
  fileName: string;
  fileSize: number;                     // Bytes
  mimeType: string;                     // 'image/jpeg', 'image/png', 'application/pdf'
  uploadedAt: Date;
  imageUrl: string;                     // URL to stored image (S3, GCS, etc.)
  ocrStatus: 'pending' | 'processing' | 'completed' | 'failed';
  ocrError?: string;                    // Error message if OCR failed
  extractedItems?: ExtractedLineItemDTO[];
  extractedAt?: Date;
  confidence: number;                   // OCR confidence score (0-1)
}

interface ExtractedLineItemDTO {
  description: string;                  // Item name
  amount: number;                       // Item price in cents
  quantity?: number;
  confidence: number;                   // OCR confidence for this item (0-1)
}

interface CorrectedLineItemInput {
  description: string;
  amount: number;
  quantity?: number;
}
```

### 7.2.5 Recurring Split Service

```typescript
// services/recurringSpitService.ts

interface IRecurringSpitService {
  /**
   * Create a recurring split template (e.g., monthly rent split)
   * @param input Recurring split configuration
   * @returns Created recurring split template
   */
  createRecurringSplit(input: CreateRecurringSpitInput): Promise<RecurringSpitDTO>;

  /**
   * Get recurring split template by ID
   * @param recurringSpitId Recurring split ID
   * @param userId User ID requesting (for authorization)
   * @returns Recurring split template
   */
  getRecurringSplit(recurringSpitId: string, userId: string): Promise<RecurringSpitDTO>;

  /**
   * List all recurring splits for a user or group
   * @param filters Filter criteria (userId, groupId, status)
   * @param pagination Offset and limit
   * @returns Paginated list of recurring splits
   */
  listRecurringSplits(
    filters: RecurringSpitFilters,
    pagination: PaginationParams
  ): Promise<PaginatedResponse<RecurringSpitDTO>>;

  /**
   * Update recurring split template (e.g., change amount or participants)
   * @param recurringSpitId Recurring split ID
   * @param input Updated configuration
   * @returns Updated recurring split template
   */
  updateRecurringSplit(
    recurringSpitId: string,
    input: UpdateRecurringSpitInput
  ): Promise<RecurringSpitDTO>;

  /**
   * Pause recurring split (stop generating new expenses)
   * @param recurringSpitId Recurring split ID
   * @returns Paused recurring split
   */
  pauseRecurringSplit(recurringSpitId: string): Promise<RecurringSpitDTO>;

  /**
   * Resume paused recurring split
   * @param recurringSpitId Recurring split ID
   * @returns Resumed recurring split
   */
  resumeRecurringSplit(recurringSpitId: string): Promise<RecurringSpitDTO>;

  /**
   * Delete recurring split template
   * @param recurringSpitId Recurring split ID
   * @returns Deleted recurring split
   */
  deleteRecurringSplit(recurringSpitId: string): Promise<RecurringSpitDTO>;

  /**
   * Trigger recurring split (create expense from template)
   * Called by scheduled job on specified cadence
   * @param recurringSpitId Recurring split ID
   * @returns Created expense from template
   */
  triggerRecurringSplit(recurringSpitId: string): Promise<ExpenseDTO>;
}

interface CreateRecurringSpitInput {
  groupId: string;
  description: string;                  // e.g., "Monthly Rent"
  totalAmount: number;                  // Total amount in cents
  paidByUserId: string;                 // User who pays the bill
  participants: RecurringSpitParticipant[]; // Users and their shares
  schedule: RecurringSchedule;
  startDate: Date;                      // When recurring split begins
  endDate?: Date;                       // Optional: when recurring split ends
}

interface RecurringSpitParticipant {
  userId: string;
  sharePercentage: number;              // e.g., 33.33 for 1/3 split
  // OR
  fixedAmount?: number;                 // Fixed amount this user owes (in cents)
}

interface RecurringSchedule {
  frequency: 'weekly' | 'biweekly' | 'monthly' | 'quarterly' | 'annual';
  dayOfWeek?: number;                   // 0-6 (0=Sunday) for weekly/biweekly
  dayOfMonth?: number;                  // 1-31 for monthly/quarterly/annual
  time: string;                         // HH:MM format (e.g., "09:00" for 9 AM)
  timezone: string;                     // IANA timezone (e.g., "America/New_York")
}

interface RecurringSpitDTO {
  id: string;
  groupId: string;
  description: string;
  totalAmount: number;
  paidByUserId: string;
  paidByUser: UserDTO;
  participants: RecurringSpitParticipantDTO[];
  schedule: RecurringSchedule;
  status: 'active' | 'paused' | 'completed';
  startDate: Date;
  endDate?: Date;
  lastTriggeredAt?: Date;
  nextTriggerAt: Date;
  createdAt: Date;
  updatedAt: Date;
}

interface RecurringSpitParticipantDTO {
  userId: string;
  user: UserDTO;
  sharePercentage: number;
  fixedAmount?: number;
}
```

### 7.2.6 Notification Service

```typescript
// services/notificationService.ts

interface INotificationService {
  /**
   * Send payment reminder email to user
   * @param input Reminder payload with split details
   * @returns Email send status
   */
  sendPaymentReminder(input: PaymentReminderInput): Promise<EmailSendResult>;

  /**
   * Send payment confirmation email to user
   * @param input Confirmation payload with payment details
   * @returns Email send status
   */
  sendPaymentConfirmation(input: PaymentConfirmationInput): Promise<EmailSendResult>;

  /**
   * Send expense settled notification to all participants
   * @param input Expense settled payload
   * @returns Email send status for all recipients
   */
  sendExpenseSettledNotification(
    input: ExpenseSettledNotificationInput
  ): Promise<EmailSendResult[]>;

  /**
   * Send group invitation email
   * @param input Invitation payload with join link
   * @returns Email send status
   */
  sendGroupInvitation(input: GroupInvitationInput): Promise<EmailSendResult>;
}

interface PaymentReminderInput {
  toUserId: string;
  toUserEmail: string;
  toUserName: string;
  fromUserName: string;
  amount: number;                       // Amount owed in cents
  expenseDescription: string;
  dueDate: Date;
  paymentLink?: string;                 // Link to Venmo/PayPal (optional)
}

interface PaymentConfirmationInput {
  toUserId: string;
  toUserEmail: string;
  toUserName: string;
  fromUserName: string;
  amount: number;                       // Amount paid in cents
  expenseDescription: string;
  paymentMethod: string;                // 'venmo', 'paypal', 'cash', etc.
}

interface ExpenseSettledNotificationInput {
  expenseId: string;
  expenseDescription: string;
  recipients: EmailRecipient[];
  settlementDetails: PaymentFlowDTO[];
}

interface EmailRecipient {
  userId: string;
  email: string;
  name: string;
}

interface GroupInvitationInput {
  toEmail: string;
  toName: string;
  fromUserName: string;
  groupName: string;
  joinLink: string;                     //

> **Guardrail Warning**: Design missing critical sections: ['scalab', 'monitor', 'deploy']