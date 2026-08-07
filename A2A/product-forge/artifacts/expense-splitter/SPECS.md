# TECHNICAL SPECIFICATION: SplitPay MVP

**Version:** 1.0  
**Date:** [Current Date]  
**Status:** Ready for Implementation  
**Audience:** Backend Engineers, Frontend Engineers, AI Code Generators  

**Purpose:** This document specifies every data model, API contract, component, business logic rule, and configuration value needed to implement SplitPay MVP. Developers and AI code generators should implement features directly from this spec without ambiguity or assumptions.

---

## TABLE OF CONTENTS

1. [Project Structure](#1-project-structure)
2. [Technology Stack & Versions](#2-technology-stack--versions)
3. [Environment Configuration](#3-environment-configuration)
4. [Data Models & Database Schema](#4-data-models--database-schema)
5. [API Specifications](#5-api-specifications)
6. [Frontend Component Specifications](#6-frontend-component-specifications)
7. [Business Logic & Algorithms](#7-business-logic--algorithms)
8. [Service Boundaries & Internal APIs](#8-service-boundaries--internal-apis)
9. [Error Handling & Status Codes](#9-error-handling--status-codes)
10. [Authentication & Authorization](#10-authentication--authorization)
11. [Validation Rules](#11-validation-rules)
12. [Third-Party Integration Specifications](#12-third-party-integration-specifications)
13. [State Machines & Workflows](#13-state-machines--workflows)
14. [Testing Specifications](#14-testing-specifications)
15. [Deployment & Runtime Configuration](#15-deployment--runtime-configuration)

---

## 1. PROJECT STRUCTURE

```
splitpay/
├── backend/
│   ├── src/
│   │   ├── index.ts                          # Express app entry point
│   │   ├── config/
│   │   │   ├── database.ts                   # Sequelize ORM config & connection pool
│   │   │   ├── env.ts                        # Environment variable validation & schema
│   │   │   ├── secrets.ts                    # AWS Secrets Manager client (prod) or .env (dev)
│   │   │   └── constants.ts                  # App-wide constants (limits, defaults, enums)
│   │   ├── middleware/
│   │   │   ├── auth.ts                       # JWT validation, request context injection
│   │   │   ├── errorHandler.ts               # Global error handler, response formatting
│   │   │   ├── requestLogger.ts              # Request/response logging with correlation IDs
│   │   │   ├── rateLimiter.ts                # Rate limiting per IP/user
│   │   │   └── validation.ts                 # Request body/query validation (Joi/Zod)
│   │   ├── routes/
│   │   │   ├── index.ts                      # Route aggregator
│   │   │   ├── auth.ts                       # POST /api/v1/auth/* endpoints
│   │   │   ├── users.ts                      # GET/PUT /api/v1/users/* endpoints
│   │   │   ├── receipts.ts                   # POST/GET /api/v1/receipts/* endpoints
│   │   │   ├── expenses.ts                   # GET/POST /api/v1/expenses/* endpoints
│   │   │   ├── groups.ts                     # GET/POST /api/v1/groups/* endpoints
│   │   │   ├── settlements.ts                # GET /api/v1/settlements/* endpoints
│   │   │   └── health.ts                     # GET /health, /ready (liveness/readiness probes)
│   │   ├── models/
│   │   │   ├── User.ts                       # Sequelize model definition
│   │   │   ├── Group.ts                      # Sequelize model definition
│   │   │   ├── GroupMember.ts                # Sequelize model definition
│   │   │   ├── Receipt.ts                    # Sequelize model definition
│   │   │   ├── ReceiptLineItem.ts            # Sequelize model definition
│   │   │   ├── Expense.ts                    # Sequelize model definition
│   │   │   ├── ExpenseParticipant.ts         # Sequelize model definition
│   │   │   ├── Settlement.ts                 # Sequelize model definition
│   │   │   ├── AuditLog.ts                   # Sequelize model definition
│   │   │   └── index.ts                      # Model exports and associations
│   │   ├── services/
│   │   │   ├── auth/
│   │   │   │   ├── AuthService.ts            # Register, login, token refresh, password reset
│   │   │   │   └── JwtService.ts             # Token generation, validation, refresh logic
│   │   │   ├── users/
│   │   │   │   └── UserService.ts            # Profile management, phone number updates
│   │   │   ├── receipts/
│   │   │   │   ├── ReceiptService.ts         # Receipt CRUD, status transitions
│   │   │   │   ├── OcrService.ts             # OCR provider integration, caching
│   │   │   │   └── ReceiptParser.ts          # Parse OCR response, extract line items
│   │   │   ├── expenses/
│   │   │   │   ├── ExpenseService.ts         # Expense creation, item claiming
│   │   │   │   ├── CalculationService.ts     # Tax/tip allocation, per-person amounts
│   │   │   │   └── SettlementService.ts      # Transaction minimization algorithm
│   │   │   ├── groups/
│   │   │   │   └── GroupService.ts           # Group CRUD, member management, invitations
│   │   │   ├── notifications/
│   │   │   │   ├── NotificationService.ts    # Queue SMS/push reminders
│   │   │   │   ├── SmsService.ts             # Twilio SMS delivery
│   │   │   │   └── PushService.ts            # Firebase push delivery
│   │   │   └── audit/
│   │   │       └── AuditService.ts           # Log all financial state changes
│   │   ├── controllers/
│   │   │   ├── AuthController.ts             # Route handlers for /auth/*
│   │   │   ├── UserController.ts             # Route handlers for /users/*
│   │   │   ├── ReceiptController.ts          # Route handlers for /receipts/*
│   │   │   ├── ExpenseController.ts          # Route handlers for /expenses/*
│   │   │   ├── GroupController.ts            # Route handlers for /groups/*
│   │   │   └── SettlementController.ts       # Route handlers for /settlements/*
│   │   ├── types/
│   │   │   ├── index.ts                      # TypeScript interfaces & types (request/response schemas)
│   │   │   ├── models.ts                     # Model type definitions (mirrors Sequelize models)
│   │   │   ├── api.ts                        # API request/response types
│   │   │   └── errors.ts                     # Custom error types
│   │   ├── utils/
│   │   │   ├── logger.ts                     # Structured logging (Winston)
│   │   │   ├── errors.ts                     # Custom error classes
│   │   │   ├── validation.ts                 # Validation schemas (Joi/Zod)
│   │   │   ├── crypto.ts                     # Password hashing, token signing utilities
│   │   │   ├── calculations.ts               # Tax/tip allocation, settlement math
│   │   │   └── formatters.ts                 # Response formatting, data transformation
│   │   ├── migrations/
│   │   │   ├── 001_initial_schema.ts         # Create all tables with constraints
│   │   │   ├── 002_add_indexes.ts            # Add performance indexes
│   │   │   └── ...                           # Future migrations
│   │   └── seeds/
│   │       ├── dev-data.ts                   # Development seed data (test users, groups)
│   │       └── test-data.ts                  # Test seed data (fixtures)
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── services/
│   │   │   │   ├── CalculationService.test.ts
│   │   │   │   ├── SettlementService.test.ts
│   │   │   │   └── ...
│   │   │   └── utils/
│   │   │       └── calculations.test.ts
│   │   ├── integration/
│   │   │   ├── auth.test.ts
│   │   │   ├── receipts.test.ts
│   │   │   ├── expenses.test.ts
│   │   │   └── settlements.test.ts
│   │   └── fixtures/
│   │       ├── users.ts
│   │       ├── groups.ts
│   │       ├── receipts.ts
│   │       └── expenses.ts
│   ├── .env.example                          # Example environment variables
│   ├── .env.test                             # Test environment variables
│   ├── package.json
│   ├── tsconfig.json
│   ├── jest.config.js
│   ├── Dockerfile
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── index.tsx                         # React Native Web entry point
│   │   ├── config/
│   │   │   ├── env.ts                        # Environment configuration
│   │   │   ├── api.ts                        # API client base config
│   │   │   └── constants.ts                  # App-wide constants
│   │   ├── types/
│   │   │   ├── index.ts                      # TypeScript interfaces
│   │   │   ├── api.ts                        # API response types
│   │   │   └── models.ts                     # Data model types
│   │   ├── screens/
│   │   │   ├── Auth/
│   │   │   │   ├── SignUpScreen.tsx
│   │   │   │   ├── LoginScreen.tsx
│   │   │   │   ├── PasswordResetScreen.tsx
│   │   │   │   └── EmailVerificationScreen.tsx
│   │   │   ├── Home/
│   │   │   │   └── HomeScreen.tsx            # Dashboard, recent expenses, groups
│   │   │   ├── Receipt/
│   │   │   │   ├── ReceiptCameraScreen.tsx   # Camera/photo upload
│   │   │   │   ├── ReceiptReviewScreen.tsx   # OCR results review
│   │   │   │   └── ItemClaimingScreen.tsx    # Claim items, assign to users
│   │   │   ├── Expense/
│   │   │   │   ├── ExpenseDetailScreen.tsx   # View expense, settlement details
│   │   │   │   └── SettlementScreen.tsx      # Show who owes whom
│   │   │   ├── Group/
│   │   │   │   ├── GroupListScreen.tsx
│   │   │   │   ├── GroupDetailScreen.tsx
│   │   │   │   ├── CreateGroupScreen.tsx
│   │   │   │   └── InviteScreen.tsx
│   │   │   ├── Profile/
│   │   │   │   └── ProfileScreen.tsx         # User profile, phone number, settings
│   │   │   └── Settings/
│   │   │       └── SettingsScreen.tsx        # Notification preferences, logout
│   │   ├── components/
│   │   │   ├── common/
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   ├── Loading.tsx
│   │   │   │   ├── ErrorBoundary.tsx
│   │   │   │   └── Toast.tsx
│   │   │   ├── auth/
│   │   │   │   ├── EmailInput.tsx
│   │   │   │   ├── PasswordInput.tsx
│   │   │   │   └── AuthForm.tsx
│   │   │   ├── receipt/
│   │   │   │   ├── ReceiptImage.tsx          # Display receipt photo
│   │   │   │   ├── LineItemList.tsx          # Display OCR line items
│   │   │   │   ├── LineItemClaim.tsx         # Claim UI for single item
│   │   │   │   └── TaxTipSummary.tsx         # Show tax/tip allocation
│   │   │   ├── expense/
│   │   │   │   ├── ExpenseSummary.tsx        # Show per-person amounts
│   │   │   │   ├── SettlementFlow.tsx        # Display settlement transactions
│   │   │   │   └── ParticipantList.tsx       # List expense participants
│   │   │   ├── group/
│   │   │   │   ├── GroupHeader.tsx
│   │   │   │   ├── MemberList.tsx
│   │   │   │   └── InviteButton.tsx
│   │   │   └── navigation/
│   │   │       ├── BottomTabNavigator.tsx    # Tab bar: Home, Receipts, Groups, Profile
│   │   │       ├── StackNavigator.tsx        # Stack navigation per tab
│   │   │       └── RootNavigator.tsx         # Root navigator (Auth vs App stacks)
│   │   ├── hooks/
│   │   │   ├── useAuth.ts                    # Auth context hook
│   │   │   ├── useApi.ts                     # API client hook with error handling
│   │   │   ├── useForm.ts                    # Form state management
│   │   │   ├── useCamera.ts                  # Camera permission & capture
│   │   │   └── useNotifications.ts           # Push notification permission & handling
│   │   ├── context/
│   │   │   ├── AuthContext.tsx               # Auth state (user, token, login/logout)
│   │   │   ├── GroupContext.tsx              # Current group context
│   │   │   └── NotificationContext.tsx       # Notification state (toasts, alerts)
│   │   ├── services/
│   │   │   ├── api.ts                        # Axios API client with auth interceptors
│   │   │   ├── storage.ts                    # AsyncStorage wrapper (persist auth token)
│   │   │   ├── camera.ts                     # Camera utilities
│   │   │   ├── imageProcessing.ts            # Image compression, orientation
│   │   │   └── notifications.ts              # Firebase Cloud Messaging setup
│   │   ├── utils/
│   │   │   ├── formatters.ts                 # Currency, date, number formatting
│   │   │   ├── validation.ts                 # Email, phone, password validation
│   │   │   ├── errors.ts                     # Error message mapping
│   │   │   └── calculations.ts               # Client-side calculation verification
│   │   ├── styles/
│   │   │   ├── theme.ts                      # Colors, typography, spacing
│   │   │   ├── global.ts                     # Global styles
│   │   │   └── components.ts                 # Component-specific styles
│   │   └── App.tsx                           # Root component with navigator
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── components/
│   │   │   └── utils/
│   │   ├── integration/
│   │   │   └── screens/
│   │   └── fixtures/
│   ├── .env.example
│   ├── package.json
│   ├── tsconfig.json
│   ├── jest.config.js
│   ├── app.json                              # React Native Web config
│   └── README.md
├── infrastructure/
│   ├── terraform/
│   │   ├── main.tf                           # VPC, subnets, security groups
│   │   ├── rds.tf                            # RDS PostgreSQL configuration
│   │   ├── ecs.tf                            # ECS cluster, services, task definitions
│   │   ├── alb.tf                            # Application Load Balancer
│   │   ├── ecr.tf                            # ECR repositories
│   │   ├── cloudwatch.tf                     # CloudWatch log groups, alarms
│   │   ├── variables.tf                      # Variable definitions
│   │   ├── outputs.tf                        # Output definitions
│   │   └── environments/
│   │       ├── dev.tfvars
│   │       ├── staging.tfvars
│   │       └── prod.tfvars
│   ├── kubernetes/
│   │   ├── backend-deployment.yaml
│   │   ├── backend-service.yaml
│   │   ├── frontend-deployment.yaml
│   │   ├── frontend-service.yaml
│   │   ├── postgres-statefulset.yaml
│   │   ├── redis-deployment.yaml
│   │   ├── ingress.yaml
│   │   └── configmap.yaml
│   ├── docker/
│   │   ├── backend.Dockerfile
│   │   ├── frontend.Dockerfile
│   │   └── nginx.conf                        # Nginx reverse proxy config
│   └── monitoring/
│       ├── prometheus.yml
│       ├── grafana-dashboard.json
│       └── alerting-rules.yml
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                            # Lint, test, build, security scan
│   │   ├── deploy-staging.yml                # Deploy to staging on merge to main
│   │   ├── deploy-prod.yml                   # Manual approval, deploy to production
│   │   └── infrastructure.yml                # Terraform plan/apply workflow
│   └── CODEOWNERS                            # Code ownership rules
├── docs/
│   ├── ARCHITECTURE.md                       # System design, service boundaries
│   ├── API.md                                # API documentation (OpenAPI spec)
│   ├── DATABASE.md                           # Schema documentation, indexes
│   ├── DEPLOYMENT.md                         # Deployment procedures, runbooks
│   ├── OPERATIONS.md                         # Monitoring, alerting, incident response
│   └── DEVELOPMENT.md                        # Local setup, debugging, testing
├── .gitignore
├── .env.example
├── docker-compose.yml                        # Local development environment
├── package.json                              # Root package.json (monorepo scripts)
└── README.md
```

---

## 2. TECHNOLOGY STACK & VERSIONS

### Backend

```json
{
  "runtime": "Node.js 18.x (LTS)",
  "language": "TypeScript 5.x",
  "framework": "Express.js 4.18.x",
  "orm": "Sequelize 6.35.x",
  "database": "PostgreSQL 14.x",
  "cache": "Redis 7.x",
  "authentication": "jsonwebtoken 9.x (JWT)",
  "passwordHashing": "bcrypt 5.x",
  "validation": "joi 17.x",
  "logging": "winston 3.x",
  "http": "axios 1.x",
  "testing": {
    "framework": "jest 29.x",
    "supertest": "6.x"
  },
  "ocr": "aws-sdk 2.x (Textract) or google-cloud-vision 3.x",
  "sms": "twilio 4.x",
  "push": "firebase-admin 12.x",
  "environment": "dotenv 16.x",
  "cors": "cors 2.x",
  "helmet": "helmet 7.x",
  "compression": "compression 1.x",
  "uuid": "uuid 9.x"
}
```

### Frontend

```json
{
  "runtime": "React Native 0.72.x with Expo 49.x",
  "language": "TypeScript 5.x",
  "ui": "react-native 0.72.x + React Native Web 0.18.x",
  "navigation": "react-navigation 6.x + react-native-screens 3.x",
  "http": "axios 1.x",
  "storage": "react-native-async-storage 1.x",
  "camera": "react-native-camera 4.x or expo-camera 13.x",
  "imageProcessing": "react-native-image-crop-picker 0.x or expo-image-manipulator 11.x",
  "notifications": "firebase-messaging 9.x + react-native-firebase 18.x",
  "forms": "react-hook-form 7.x",
  "validation": "zod 3.x",
  "state": "zustand 4.x or React Context API",
  "styling": "react-native-paper 5.x or styled-components 6.x",
  "testing": {
    "framework": "jest 29.x",
    "testing-library": "@testing-library/react-native 12.x"
  },
  "environment": "dotenv 16.x",
  "formatting": "date-fns 2.x",
  "uuid": "uuid 9.x"
}
```

### Infrastructure & DevOps

```json
{
  "containerization": "Docker 24.x",
  "orchestration": "Kubernetes 1.27.x (optional) or AWS ECS",
  "infrastructure": "Terraform 1.5.x",
  "cicd": "GitHub Actions",
  "monitoring": "Prometheus 2.x + Grafana 10.x",
  "logging": "CloudWatch or ELK Stack",
  "reverseProxy": "Nginx 1.25.x",
  "ssl": "Let's Encrypt / AWS Certificate Manager",
  "secretsManagement": "AWS Secrets Manager or HashiCorp Vault"
}
```

---

## 3. ENVIRONMENT CONFIGURATION

### Backend Environment Variables

```bash
# Application
NODE_ENV=development|staging|production
PORT=3000
LOG_LEVEL=debug|info|warn|error
CORS_ORIGIN=http://localhost:3000,https://app.splitpay.com

# Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=splitpay_dev
DATABASE_USER=splitpay_user
DATABASE_PASSWORD=<secure-password>
DATABASE_POOL_MIN=2
DATABASE_POOL_MAX=10
DATABASE_SSL=false|true

# Redis (caching, session store)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<optional>

# JWT
JWT_SECRET=<long-random-secret-key>
JWT_EXPIRATION=1h
JWT_REFRESH_SECRET=<long-random-secret-key>
JWT_REFRESH_EXPIRATION=30d

# OCR Provider (AWS Textract)
OCR_PROVIDER=aws_textract|google_vision
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<credentials>
AWS_SECRET_ACCESS_KEY=<credentials>
OCR_CACHE_TTL=86400  # seconds

# SMS Provider (Twilio)
TWILIO_ACCOUNT_SID=<credentials>
TWILIO_AUTH_TOKEN=<credentials>
TWILIO_PHONE_NUMBER=+1234567890

# Push Notifications (Firebase)
FIREBASE_PROJECT_ID=<credentials>
FIREBASE_PRIVATE_KEY=<credentials>
FIREBASE_CLIENT_EMAIL=<credentials>

# Email (for password resets, verification)
SENDGRID_API_KEY=<credentials>
EMAIL_FROM=noreply@splitpay.com

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000  # 15 minutes
RATE_LIMIT_MAX_REQUESTS=100

# Feature Flags
FEATURE_RECURRING_EXPENSES=false
FEATURE_PAYMENT_INTEGRATION=false

# Monitoring & Observability
SENTRY_DSN=<optional>
DATADOG_API_KEY=<optional>
```

### Frontend Environment Variables

```bash
# Application
REACT_APP_ENV=development|staging|production
REACT_APP_API_URL=http://localhost:3000|https://api.splitpay.com
REACT_APP_LOG_LEVEL=debug|info|warn|error

# Firebase Cloud Messaging
REACT_APP_FIREBASE_API_KEY=<credentials>
REACT_APP_FIREBASE_AUTH_DOMAIN=<credentials>
REACT_APP_FIREBASE_PROJECT_ID=<credentials>
REACT_APP_FIREBASE_STORAGE_BUCKET=<credentials>
REACT_APP_FIREBASE_MESSAGING_SENDER_ID=<credentials>
REACT_APP_FIREBASE_APP_ID=<credentials>

# Feature Flags
REACT_APP_FEATURE_RECURRING_EXPENSES=false
REACT_APP_FEATURE_PAYMENT_INTEGRATION=false

# Monitoring
REACT_APP_SENTRY_DSN=<optional>
```

---

## 4. DATA MODELS & DATABASE SCHEMA

### 4.1 Core Entity Models

#### User

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  email_verified BOOLEAN DEFAULT FALSE,
  email_verified_at TIMESTAMP NULL,
  password_hash VARCHAR(255) NOT NULL,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  phone_number VARCHAR(20) NULL,
  phone_verified BOOLEAN DEFAULT FALSE,
  phone_verified_at TIMESTAMP NULL,
  avatar_url TEXT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  last_login_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL,
  CONSTRAINT email_not_empty CHECK (email != ''),
  CONSTRAINT phone_format CHECK (phone_number IS NULL OR phone_number ~ '^\+?1?\d{9,15}$')
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_deleted_at ON users(deleted_at);
```

**TypeScript Type:**

```typescript
interface User {
  id: string; // UUID
  email: string;
  emailVerified: boolean;
  emailVerifiedAt: Date | null;
  passwordHash: string; // Never exposed in API responses
  firstName: string;
  lastName: string;
  phoneNumber: string | null;
  phoneVerified: boolean;
  phoneVerifiedAt: Date | null;
  avatarUrl: string | null;
  isActive: boolean;
  lastLoginAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
}

// API Response (excludes sensitive fields)
interface UserResponse {
  id: string;
  email: string;
  emailVerified: boolean;
  firstName: string;
  lastName: string;
  phoneNumber: string | null;
  phoneVerified: boolean;
  avatarUrl: string | null;
  createdAt: Date;
  updatedAt: Date;
}
```

---

#### Group

```sql
CREATE TABLE groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  name VARCHAR(255) NOT NULL,
  description TEXT NULL,
  avatar_url TEXT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL,
  CONSTRAINT name_not_empty CHECK (name != '')
);

CREATE INDEX idx_groups_owner_id ON groups(owner_id);
CREATE INDEX idx_groups_is_active ON groups(is_active);
CREATE INDEX idx_groups_deleted_at ON groups(deleted_at);
```

**TypeScript Type:**

```typescript
interface Group {
  id: string; // UUID
  ownerId: string; // UUID
  name: string;
  description: string | null;
  avatarUrl: string | null;
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
}

interface GroupResponse extends Group {
  owner: UserResponse;
  memberCount: number;
  totalExpenses: number; // Aggregated
}
```

---

#### GroupMember

```sql
CREATE TABLE group_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role VARCHAR(50) DEFAULT 'member', -- 'owner', 'member'
  joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(group_id, user_id),
  CONSTRAINT valid_role CHECK (role IN ('owner', 'member'))
);

CREATE INDEX idx_group_members_group_id ON group_members(group_id);
CREATE INDEX idx_group_members_user_id ON group_members(user_id);
```

**TypeScript Type:**

```typescript
interface GroupMember {
  id: string; // UUID
  groupId: string; // UUID
  userId: string; // UUID
  role: 'owner' | 'member';
  joinedAt: Date;
  createdAt: Date;
  updatedAt: Date;
}

interface GroupMemberResponse extends GroupMember {
  user: UserResponse;
}
```

---

#### Receipt

```sql
CREATE TABLE receipts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  uploaded_by_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  image_url TEXT NOT NULL,
  image_hash VARCHAR(64) NULL, -- SHA-256 for deduplication
  ocr_status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'success', 'failed'
  ocr_provider VARCHAR(50) NULL, -- 'aws_textract', 'google_vision'
  ocr_result JSONB NULL, -- Raw OCR response
  extracted_at TIMESTAMP NULL,
  merchant_name VARCHAR(255) NULL,
  receipt_date DATE NULL,
  subtotal_cents INTEGER NULL, -- Stored as cents to avoid float precision issues
  tax_cents INTEGER NULL,
  tip_cents INTEGER NULL,
  total_cents INTEGER NULL,
  currency_code VARCHAR(3) DEFAULT 'USD',
  notes TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL,
  CONSTRAINT positive_amounts CHECK (subtotal_cents >= 0 AND tax_cents >= 0 AND tip_cents >= 0 AND total_cents >= 0)
);

CREATE INDEX idx_receipts_group_id ON receipts(group_id);
CREATE INDEX idx_receipts_uploaded_by_id ON receipts(uploaded_by_id);
CREATE INDEX idx_receipts_ocr_status ON receipts(ocr_status);
CREATE INDEX idx_receipts_image_hash ON receipts(image_hash);
```

**TypeScript Type:**

```typescript
interface Receipt {
  id: string; // UUID
  groupId: string; // UUID
  uploadedById: string; // UUID
  imageUrl: string;
  imageHash: string | null;
  ocrStatus: 'pending' | 'processing' | 'success' | 'failed';
  ocrProvider: string | null;
  ocrResult: Record<string, any> | null;
  extractedAt: Date | null;
  merchantName: string | null;
  receiptDate: Date | null;
  subtotalCents: number | null;
  taxCents: number | null;
  tipCents: number | null;
  totalCents: number | null;
  currencyCode: string;
  notes: string | null;
  createdAt: Date;
  updatedAt: Date;
  deletedAt: Date | null;
}

interface ReceiptResponse extends Receipt {
  uploadedBy: UserResponse;
  lineItems: ReceiptLineItemResponse[];
  expense?: ExpenseResponse; // If receipt is associated with expense
}
```

---

#### ReceiptLineItem

```sql
CREATE TABLE receipt_line_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_id UUID NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
  description VARCHAR(255) NOT NULL,
  quantity DECIMAL(10, 2) NOT NULL DEFAULT 1,
  unit_price_cents INTEGER NOT NULL,
  total_price_cents INTEGER NOT NULL,
  category VARCHAR(100) NULL, -- 'food', 'beverage', 'tax', 'tip', 'other'
  is_claimed BOOLEAN DEFAULT FALSE,
  claimed_by_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  claimed_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT positive_prices CHECK (unit_price_cents > 0 AND total_price_cents > 0),
  CONSTRAINT valid_category CHECK (category IS NULL OR category IN ('food', 'beverage', 'tax', 'tip', 'other'))
);

CREATE INDEX idx_receipt_line_items_receipt_id ON receipt_line_items(receipt_id);
CREATE INDEX idx_receipt_line_items_claimed_by_id ON receipt_line_items(claimed_by_id);
CREATE INDEX idx_receipt_line_items_is_claimed ON receipt_line_items(is_claimed);
```

**TypeScript Type:**

```typescript
interface ReceiptLineItem {
  id: string; // UUID
  receiptId: string; // UUID
  description: string;
  quantity: number;
  unitPriceCents: number;
  totalPriceCents: number;
  category: 'food' | 'beverage' | 'tax' | 'tip' | 'other' | null;
  isClaimed: boolean;
  claimedById: string | null; // UUID
  claimedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
}

interface ReceiptLineItemResponse extends ReceiptLineItem {
  claimedBy?: UserResponse | null;
}
```

---

#### Expense

```sql
CREATE TABLE expenses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  receipt_id UUID NULL REFERENCES receipts(id) ON DELETE SET NULL,
  payer_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'ready', 'calculated', 'settled'
  merchant_name VARCHAR(255) NULL,
  expense_date DATE NOT NULL,
  subtotal_cents INTEGER NOT NULL,
  tax_cents INTEGER NOT NULL DEFAULT 0,
  tip_cents INTEGER NOT NULL DEFAULT 0,
  total_cents INTEGER NOT NULL,
  currency_code VARCHAR(3) DEFAULT 'USD',
  notes TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  settled_at TIMESTAMP NULL,
  deleted_at TIMESTAMP NULL,
  CONSTRAINT positive_amounts CHECK (subtotal_cents > 0 AND tax_cents >= 0 AND tip_cents >= 0 AND total_cents > 0)
);

CREATE INDEX idx_expenses_group_id ON expenses(group_id);
CREATE INDEX idx_expenses_payer_id ON expenses(payer_id);
CREATE INDEX idx_expenses_receipt_id ON expenses(receipt_id);
CREATE INDEX idx_expenses_status ON expenses(status);
```

**TypeScript Type:**

```typescript
interface Expense {
  id: string; // UUID
  groupId: string; // UUID
  receiptId: string | null; // UUID
  payerId: string; // UUID
  status: 'pending' | 'ready' | 'calculated' | 'settled';
  merchantName: string | null;
  expenseDate: Date;
  subtotalCents: number;
  taxCents: number;
  tipCents: number;
  totalCents: number;
  currencyCode: string;
  notes: string | null;
  createdAt: Date;
  updatedAt: Date;
  settledAt: Date | null;
  deletedAt: Date | null;
}

interface ExpenseResponse extends Expense {
  payer: UserResponse;
  receipt?: ReceiptResponse | null;
  participants: ExpenseParticipantResponse[];
  settlements?: SettlementResponse[];
}
```

---

#### ExpenseParticipant

```sql
CREATE TABLE expense_participants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  expense_id UUID NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  amount_owed_cents INTEGER NOT NULL,
  amount_paid_cents INTEGER NOT NULL DEFAULT 0,
  status VARCHAR(50) DEFAULT 'unpaid', -- 'unpaid', 'partial', 'paid'
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(expense_id, user_id),
  CONSTRAINT non_negative CHECK (amount_owed_cents >= 0 AND amount_paid_cents >= 0)
);

CREATE INDEX idx_expense_participants_expense_id ON expense_participants(expense_id);
CREATE INDEX idx_expense_participants_user_id ON expense_participants(user_id);
CREATE INDEX idx_expense_participants_status ON expense_participants(status);
```

**TypeScript Type:**

```typescript
interface ExpenseParticipant {
  id: string; // UUID
  expenseId: string; // UUID
  userId: string; // UUID
  amountOwedCents: number;
  amountPaidCents: number;
  status: 'unpaid' | 'partial' | 'paid';
  createdAt: Date;
  updatedAt: Date;
}

interface ExpenseParticipantResponse extends ExpenseParticipant {
  user: UserResponse;
}
```

---

#### Settlement

```sql
CREATE TABLE settlements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  expense_id UUID NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
  from_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  to_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  amount_cents INTEGER NOT NULL,
  status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'completed', 'cancelled'
  payment_method VARCHAR(50) NULL, -- 'manual', 'venmo', 'paypal', etc. (future)
  payment_reference VARCHAR(255) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TIMESTAMP NULL,
  CONSTRAINT positive_amount CHECK (amount_cents > 0),
  CONSTRAINT different_users CHECK (from_user_id != to_user_id)
);

CREATE INDEX idx_settlements_expense_id ON settlements(expense_id);
CREATE INDEX idx_settlements_from_user_id ON settlements(from_user_id);
CREATE INDEX idx_settlements_to_user_id ON settlements(to_user_id);
CREATE INDEX idx_settlements_status ON settlements(status);
```

**TypeScript Type:**

```typescript
interface Settlement {
  id: string; // UUID
  expenseId: string; // UUID
  fromUserId: string; // UUID
  toUserId: string; // UUID
  amountCents: number;
  status: 'pending' | 'completed' | 'cancelled';
  paymentMethod: string | null;
  paymentReference: string | null;
  createdAt: Date;
  updatedAt: Date;
  completedAt: Date | null;
}

interface SettlementResponse extends Settlement {
  fromUser: UserResponse;
  toUser: UserResponse;
  expense: ExpenseResponse;
}
```

---

#### AuditLog

```sql
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
  entity_type VARCHAR(50) NOT NULL, -- 'user', 'group', 'expense', 'settlement', 'receipt'
  entity_id UUID NOT NULL,
  action VARCHAR(50) NOT NULL, -- 'created', 'updated', 'deleted', 'claimed', 'calculated', 'settled'
  changes JSONB NULL, -- {field: {old: value, new: value}}
  ip_address INET NULL,
  user_agent TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_entity_type_id ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

**TypeScript Type:**

```typescript
interface AuditLog {
  id: string; // UUID
  userId: string | null; // UUID
  entityType: string;
  entityId: string; // UUID
  action: string;
  changes: Record<string, { old: any; new: any }> | null;
  ipAddress: string | null;
  userAgent: string | null;
  createdAt: Date;
}
```

---

### 4.2 Database Constraints & Relationships

```
Users (1) ──────────────── (N) Groups (owner)
Users (N) ──────────────── (N) Groups (members via GroupMember)
Groups (1) ──────────────── (N) Receipts
Groups (1) ──────────────── (N) Expenses
Receipts (1) ──────────────── (N) ReceiptLineItems
Receipts (1) ──────────────── (1) Expense (optional)
Users (1) ──────────────── (N) Expenses (payer)
Expenses (1) ──────────────── (N) ExpenseParticipants
Expenses (1) ──────────────── (N) Settlements
Users (N) ──────────────── (N) Settlements (from/to)
Users (1) ──────────────── (N) AuditLogs
```

---

### 4.3 Indexes for Performance

```sql
-- Query: Find user's groups
CREATE INDEX idx_group_members_user_id_joined ON group_members(user_id, joined_at DESC);

-- Query: Find expenses in a group
CREATE INDEX idx_expenses_group_id_created ON expenses(group_id, created_at DESC);

-- Query: Find unsettled expenses
CREATE INDEX idx_expenses_status_group_id ON expenses(status, group_id);

-- Query: Find who owes whom in a group
CREATE INDEX idx_expense_participants_user_id_status ON expense_participants(user_id, status);

-- Query: Find pending settlements for a user
CREATE INDEX idx_settlements_from_user_status ON settlements(from_user_id, status);
CREATE INDEX idx_settlements_to_user_status ON settlements(to_user_id, status);

-- Query: Find receipts by OCR status
CREATE INDEX idx_receipts_group_id_status ON receipts(group_id, ocr_status);

-- Query: Audit trail queries
CREATE INDEX idx_audit_logs_entity_type_created ON audit_logs(entity_type, created_at DESC);
```

---

## 5. API SPECIFICATIONS

### 5.1 Authentication Endpoints

#### POST /api/v1/auth/register

**Purpose:** Create a new user account

**Request:**

```typescript
{
  email: string;           // Required, valid email format, unique
  password: string;        // Required, min 8 chars, 1 uppercase, 1 number, 1 special char
  firstName: string;       // Required, 1-100 chars
  lastName: string;        // Required, 1-100 chars
}
```

**Response (201 Created):**

```typescript
{
  user: {
    id: string;
    email: string;
    emailVerified: boolean;
    firstName: string;
    lastName: string;
    createdAt: string; // ISO 8601
  };
  accessToken: string;     // JWT, expires in 1 hour
  refreshToken: string;    // JWT, expires in 30 days
  expiresIn: number;       // Seconds (3600)
}
```

**Error Responses:**

```typescript
// 400 Bad Request
{
  code: "VALIDATION_ERROR";
  message: "Validation failed";
  errors: [
    { field: "email", message: "Invalid email format" },
    { field: "password", message: "Password must contain uppercase letter, number, and special character" }
  ];
}

// 409 Conflict
{
  code: "EMAIL_ALREADY_EXISTS";
  message: "Email already registered";
}

// 429 Too Many Requests
{
  code: "RATE_LIMIT_EXCEEDED";
  message: "Too many registration attempts. Try again later.";
}
```

**Security:**
- HTTPS only
- Password hashed with bcrypt (12+ rounds) before storage
- Email verification required before accessing core features (async, see POST /api/v1/auth/verify-email)
- Rate limited: 5 attempts per IP per hour

---

#### POST /api/v1/auth/login

**Purpose:** Authenticate user and issue tokens

**Request:**

```typescript
{
  email: string;           // Required
  password: string;        // Required
}
```

**Response (200 OK):**

```typescript
{
  user: {
    id: string;
    email: string;
    emailVerified: boolean;
    firstName: string;
    lastName: string;
    phoneNumber: string | null;
    phoneVerified: boolean;
    createdAt: string; // ISO 8601
  };
  accessToken: string;     // JWT, expires in 1 hour
  refreshToken: string;    // JWT, expires in 30 days
  expiresIn: number;       // Seconds (3600)
}
```

**Error Responses:**

```typescript
// 401 Unauthorized
{
  code: "INVALID_CREDENTIALS";
  message: "Invalid email or password";
}

// 403 Forbidden
{
  code: "EMAIL_NOT_VERIFIED";
  message: "Email not verified. Check your inbox for verification link.";
}

// 429 Too Many Requests
{
  code: "RATE_LIMIT_EXCEEDED";
  message: "Too many login attempts. Try again later.";
}
```

**Security:**
- HTTPS only
- Rate limited: 10 failed attempts per IP per 15 minutes → 429
- Timing-constant comparison (prevent email enumeration)
- Last login timestamp updated

---

#### POST /api/v1/auth/refresh-token

**Purpose:** Issue new access token using refresh token

**Request:**

```typescript
{
  refreshToken: string;    // Required, valid refresh token from login/register
}
```

**Response (200 OK):**

```typescript
{
  accessToken: string;     // New JWT, expires in 1 hour
  expiresIn: number;       // Seconds (3600)
}
```

**Error Responses:**

```typescript
// 401 Unauthorized
{
  code: "INVALID_REFRESH_TOKEN";
  message: "Refresh token invalid or expired";
}
```

**Security:**
- HTTPS only
- Refresh token must be valid and not expired
- Old access token can still be used briefly (grace period)

---

#### POST /api/v1/auth/logout

**Purpose:** Invalidate user session (optional; tokens are stateless)

**Request:**

```typescript
{
  refreshToken: string;    // Optional, for cleanup
}
```

**Response (204 No Content):**

```
(empty body)
```

**Security:**
- Requires valid access token (JWT in Authorization header)
- Stateless: logout is client-side (delete token from storage)
- Refresh token can be blacklisted server-side (optional, for strict logout)

---

#### POST /api/v1/auth/password-reset-request

**Purpose:** Request password reset link via email

**Request:**

```typescript
{
  email: string;           // Required, email of account
}
```

**Response (200 OK):**

```typescript
{
  message: "If an account exists with this email, a password reset link has been sent.";
}
```

**Notes:**
- Always returns 200 OK (do not reveal whether email exists)
- Email sent with reset link (token valid for 1 hour, single-use)
- User must verify email before resetting password (if not already verified)

---

#### POST /api/v1/auth/password-reset

**Purpose:** Reset password using reset token

**Request:**

```typescript
{
  token: string;           // Required, from email reset link
  newPassword: string;     // Required, same rules as registration
}
```

**Response (200 OK):**

```typescript
{
  message: "Password reset successful. Please log in with your new password.";
}
```

**Error Responses:**

```typescript
// 400 Bad Request
{
  code: "INVALID_RESET_TOKEN";
  message: "Reset token invalid or expired";
}

// 400 Bad Request
{
  code: "VALIDATION_ERROR";
  message: "Password does not meet requirements";
}
```

**Security:**
- Token valid for 1 hour, single-use (invalidated after use)
- New password must meet same requirements as registration
- Audit logged

---

#### POST /api/v1/auth/verify-email

**Purpose:** Verify email address using verification token

**Request:**

```typescript
{
  token: string;           // Required, from email verification link
}
```

**Response (200 OK):**

```typescript
{
  user: {
    id: string;
    email: string;
    emailVerified: true;
    firstName: string;
    lastName: string;
  };
  message: "Email verified successfully";
}
```

**Error Responses:**

```typescript
// 400 Bad Request
{
  code: "INVALID_VERIFICATION_TOKEN";
  message: "Verification token invalid or expired";
}
```

**Security:**
- Token valid for 24 hours, single-use
- User can request new verification email if token expires

---

### 5.2 User Endpoints

#### GET /api/v1/users/me

**Purpose:** Get current authenticated user profile

**Request:**
- Headers: `Authorization: Bearer <access_token>`

**Response (200 OK):**

```typescript
{
  id: string;
  email: string;
  emailVerified: boolean;
  firstName: string;
  lastName: string;
  phoneNumber: string | null;
  phoneVerified: boolean;
  avatarUrl: string | null;
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}
```

**Error Responses:**

```typescript
// 401 Unauthorized
{
  code: "INVALID_TOKEN";
  message: "Access token invalid or expired";
}
```

**Security:**
- Requires valid access token
- Returns only current user's data

---

#### PUT /api/v1/users/me

**Purpose:** Update current user profile

**Request:**

```typescript
{
  firstName?: string;      // Optional, 1-100 chars
  lastName?: string;       // Optional, 1-100 chars
  phoneNumber?: string;    // Optional, E.164 format (+1234567890)
}
```

**Response (200 OK):**

```typescript
{
  id: string;
  email: string;
  emailVerified: boolean;
  firstName: string;
  lastName: string;
  phoneNumber: string | null;
  phoneVerified: boolean;
  avatarUrl: string | null;
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}
```

**Error Responses:**

```typescript
// 400 Bad Request
{
  code: "VALIDATION_ERROR";
  message: "Validation failed";
  errors: [
    { field: "phoneNumber", message: "Invalid phone number format" }
  ];
}
```

**Security:**
- Requires valid access token
- Phone number update triggers verification SMS (async)
- Audit logged

---

#### PUT /api/v1/users/me/password

**Purpose:** Change password for authenticated user

**Request:**

```typescript
{
  currentPassword: string; // Required, current password
  newPassword: string;     // Required, same rules as registration
}
```

**Response (200 OK):**

```typescript
{
  message: "Password changed successfully";
}
```

**Error Responses:**

```typescript
// 401 Unauthorized
{
  code: "INVALID_PASSWORD";
  message: "Current password is incorrect";
}

// 400 Bad Request
{
  code: "VALIDATION_ERROR";
  message: "New password does not meet requirements";
}
```

**Security:**
- Requires valid access token
- Current password verified before change
- Audit logged
- All active refresh tokens invalidated (user must re-login on other devices)

---

### 5.3 Receipt Endpoints

#### POST /api/v1/receipts/upload

**Purpose:** Upload receipt image and trigger OCR processing

**Request:**
- Headers: `Authorization: Bearer <access_token>`, `Content-Type: multipart/form-data`
- Body:
  - `file`: Image file (JPEG, PNG, WebP; max 10 MB)
  - `groupId`: UUID of group
  - `notes`: Optional string (max 500 chars)

**Response (202 Accepted):**

```typescript
{
  id: string;              // Receipt ID (UUID)
  groupId: string;
  uploadedById: string;
  imageUrl: string;        // Signed S3 URL (expires in 7 days)
  ocrStatus: "processing";
  merchantName: null;
  receiptDate: null;
  subtotalCents: null;
  taxCents: null;
  tipCents: null;
  totalCents: null;
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}
```

**Processing Flow:**
1. Immediately return 202 with receipt ID (async processing)
2. Enqueue OCR job (SQS/job queue)
3. OCR worker processes image, extracts line items
4. Update receipt with OCR results (WebSocket notification to client)
5. Client polls GET /api/v1/receipts/{id} or listens for WebSocket event

**Error Responses:**

```typescript
// 400 Bad Request
{
  code: "INVALID_FILE";
  message: "File must be JPEG, PNG, or WebP";
}

// 400 Bad Request
{
  code: "FILE_TOO_LARGE";
  message: "File must be less than 10 MB";
}

// 404 Not Found
{
  code: "GROUP_NOT_FOUND";
  message: "Group not found or user not a member";
}

// 429 Too Many Requests
{
  code: "RATE_LIMIT_EXCEEDED";
  message: "Too many uploads. Try again later.";
}
```

**Security:**
- Requires valid access token
- User must be member of group
- File uploaded to private S3 bucket (signed URLs)
- Image hash computed (SHA-256) for deduplication
- Rate limited: 50 uploads per user per day

---

#### GET /api/v1/receipts/{id}

**Purpose:** Get receipt details including OCR results and line items

**Request:**
- Headers: `Authorization: Bearer <access_token>`
- Path: `/api/v1/receipts/{id}` where `id` is receipt UUID

**Response (200 OK):**

```typescript
{
  id: string;
  groupId: string;
  uploadedById: string;
  uploadedBy: {
    id: string;
    email: string;
    firstName: string;
    lastName: string;
  };
  imageUrl: string;        // Signed S3 URL (expires in 7 days)
  ocrStatus: "success" | "failed" | "processing";
  ocrProvider: "aws_textract" | "google_vision";
  merchantName: string | null;
  receiptDate: string | null; // ISO 8601 date
  subtotalCents: number | null;
  taxCents: number | null;
  tipCents: number | null;
  totalCents: number | null;
  currencyCode: string;
  notes: string | null;
  lineItems: [
    {
      id: string;
      description: string;
      quantity: number;
      unitPriceCents: number;
      totalPriceCents: number;
      category: "food" | "beverage" | "tax" | "tip" | "other" | null;
      isClaimed: boolean;
      claimedById: string | null;
      claimedBy: {
        id: string;
        firstName: string;
        lastName: string;
      } | null;
      claimedAt: string | null; // ISO 8601
    }
  ];
  expense: {
    id: string;
    status: string;
  } | null;                // If receipt is linked to expense
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}
```

**Error Responses:**

```typescript
// 404 Not Found
{
  code: "RECEIPT_NOT_FOUND";
  message: "Receipt not found";
}

// 403 Forbidden
{
  code: "UNAUTHORIZED";
  message: "You do not have access to this receipt";
}
```

**Security:**
- Requires valid access token
- User must be member of receipt's group
- Image URL is signed and expires after 7 days

---

#### POST /api/v1/receipts/{id}/line-items/{lineItemId}/claim

**Purpose:** Claim a receipt line item (user says "I ordered this")

**Request:**
- Headers: `Authorization: Bearer <access_token>`
- Path: `/api/v1/receipts/{id}/line-items/{lineItemId}/claim`
- Body: `{}` (empty, user ID comes from token)

**Response (200 OK):**

```typescript
{
  id: string;
  description: string;
  quantity: number;
  unitPriceCents: number;
  totalPriceCents: number;
  category: string | null;
  isClaimed: true;
  claimedById: string;
  claimedBy: {
    id: string;
    firstName: string;
    lastName: string;
  };
  claimedAt: string; // ISO 8601
}
```

**Error Responses:**

```typescript
// 400 Bad Request
{
  code: "ITEM_ALREADY_CLAIMED";
  message: "This item is already claimed by another user";
}

// 404 Not Found
{
  code: "LINE_ITEM_NOT_FOUND";
  message: "Line item not found";
}

// 403 Forbidden
{
  code: "UNAUTHORIZED";
  message: "You are not a member of this group";
}
```

**Business Rules:**
- Each line item can only be claimed by one user
- User must be member of group
- Cannot claim tax/tip items directly (allocated proportionally)
- Audit logged

---

#### POST /api/v1/receipts/{id}/line-items/{lineItemId}/unclaim

**Purpose:** Unclaim a receipt line item

**Request:**
- Headers: `Authorization: Bearer <access_token>`
- Path: `/api/v1/receipts/{id}/line-items/{lineItemId}/unclaim`
- Body: `{}` (empty)

**Response (200 OK):**

```typescript
{
  id: string;
  description: string;
  quantity: number;
  unitPriceCents: number;
  totalPriceCents: number;
  category: string | null;
  isClaimed: false;
  claimedById: null;
  claimedBy: null;
  claimedAt: null;
}
```

**Security:**
- Requires valid access token
- Only the user who claimed the item can unclaim it (or group owner)
- Audit logged

---

#### GET /api/v1/receipts

**Purpose:** List receipts in a group (paginated)

**Request:**
- Headers: `Authorization: Bearer <access_token>`
- Query Parameters:
  - `groupId`: UUID (required)
  - `page`: number (optional, default 1)
  - `limit`: number (optional, default 20, max 100)
  - `status`: "pending" | "processing" | "success" | "failed" (optional, filter)

**Response (200 OK):**

```typescript
{
  data: [
    {
      id: string;
      groupId: string;
      uploadedById: string;
      imageUrl: string;
      ocrStatus: string;
      merchantName: string | null;
      receiptDate: string | null;
      subtotalCents: number | null;
      totalCents: number | null;
      createdAt: string; // ISO 8601
      updatedAt: string; // ISO 8601
    }
  ];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
  };
}
```

**Security:**
- Requires valid access token
- User must be member of group
- Returns only receipts from that group

---

### 5.4 Expense Endpoints

#### POST /api/v1/expenses

**Purpose:** Create expense from receipt and finalize item claims

**Request:**
- Headers: `Authorization: Bearer <access_token>`
- Body:

```typescript
{
  groupId: string;         // UUID of group
  receiptId: string | null;// UUID of receipt (optional, for OCR-based expenses)
  payerId: string;         // UUID of user who paid (typically current user)
  merchantName?: string;   // Optional, override receipt merchant name
  expenseDate?: string;    // ISO 8601 date (optional, default today)
  subtotalCents: number;   // Required, in cents
  taxCents?: number;       // Optional, default 0
  tipCents?: number;       // Optional, default 0
  currencyCode?: string;   // Optional, default "USD"
  notes?: string;          // Optional, max 500 chars
}
```

**Response (201 Created):**

```typescript
{
  id: string;
  groupId: string;
  receiptId: string | null;
  payerId: string;
  payer: {
    id: string;
    firstName: string;
    lastName: string;
  };
  status: "ready";         // Expense created, ready for calculation
  merchantName: string | null;
  expenseDate: string; // ISO 8601
  subtotalCents: number;
  taxCents: number;
  tipCents: number;
  totalCents: number;
  currencyCode: string;
  notes: string | null;
  participants: [
    {
      id: string;
      userId: string;
      user: {
        id: string;
        firstName: string;
        lastName: string;
      };
      amountOwedCents: number;
      amountPaidCents: 0;
      status: "unpaid";
    }
  ];
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}
```

**Processing:**
1. Create Expense record
2. Extract participants from receipt line item claims (if receiptId provided)
3. Calculate tax/tip allocation (see §7 Business Logic)
4. Create ExpenseParticipant records with calculated amounts
5. Trigger settlement calculation (async)
6. Return expense with calculated participants

**Error Responses:**

```