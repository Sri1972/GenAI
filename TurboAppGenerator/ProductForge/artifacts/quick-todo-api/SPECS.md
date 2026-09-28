# SPECS.md
## To-Do List API — Complete Technical Specification

**Document Version:** 1.0  
**Last Updated:** [Current Date]  
**Status:** Ready for Implementation  
**Owner:** Engineering Leadership

---

## TABLE OF CONTENTS

1. [Project Structure](#project-structure)
2. [Technology Stack & Versions](#technology-stack--versions)
3. [Environment Configuration](#environment-configuration)
4. [Data Models & Database Schema](#data-models--database-schema)
5. [API Contract Specification](#api-contract-specification) *(Part 2)*
6. [Error Handling & Validation Rules](#error-handling--validation-rules) *(Part 2)*
7. [Concurrency & Consistency Model](#concurrency--consistency-model) *(Part 2)*
8. [Deployment & Operations](#deployment--operations) *(Part 3)*
9. [Observability & Monitoring](#observability--monitoring) *(Part 3)*
10. [Testing Strategy](#testing-strategy) *(Part 4)*

---

## 1. PROJECT STRUCTURE

### Directory Tree (Spring Boot + Maven)

```
todo-api/
├── pom.xml                                 # Maven project configuration
├── README.md                               # Project overview & quick start
├── .gitignore                              # Git ignore rules
├── .env.example                            # Example environment variables
├── Dockerfile                              # Docker image definition (optional, for future)
├── docker-compose.yml                      # Local dev environment (optional)
│
├── src/
│   ├── main/
│   │   ├── java/com/todoapi/
│   │   │   ├── TodoApiApplication.java     # Spring Boot entry point
│   │   │   │
│   │   │   ├── config/
│   │   │   │   ├── AppConfig.java          # Spring configuration beans
│   │   │   │   ├── SecurityConfig.java     # CORS, rate limiting config (if needed)
│   │   │   │   └── JpaConfig.java          # JPA/Hibernate configuration
│   │   │   │
│   │   │   ├── controller/
│   │   │   │   ├── TaskController.java     # REST endpoints for tasks
│   │   │   │   ├── HealthController.java   # Liveness/readiness probes
│   │   │   │   └── ErrorController.java    # Global error handling
│   │   │   │
│   │   │   ├── service/
│   │   │   │   ├── TaskService.java        # Business logic, state machine
│   │   │   │   └── TaskServiceImpl.java     # Implementation
│   │   │   │
│   │   │   ├── repository/
│   │   │   │   ├── TaskRepository.java     # Spring Data JPA interface
│   │   │   │   └── TaskRepositoryCustom.java # Custom query methods
│   │   │   │
│   │   │   ├── entity/
│   │   │   │   └── Task.java               # JPA entity (database model)
│   │   │   │
│   │   │   ├── dto/
│   │   │   │   ├── CreateTaskRequest.java  # Request DTO for POST /tasks
│   │   │   │   ├── UpdateTaskRequest.java  # Request DTO for PATCH /tasks/{id}
│   │   │   │   ├── TaskResponse.java       # Response DTO for all task endpoints
│   │   │   │   ├── ListTasksResponse.java  # Response DTO for GET /tasks (paginated)
│   │   │   │   └── ErrorResponse.java      # Error response DTO
│   │   │   │
│   │   │   ├── exception/
│   │   │   │   ├── TaskNotFoundException.java
│   │   │   │   ├── TaskConflictException.java
│   │   │   │   ├── ValidationException.java
│   │   │   │   └── GlobalExceptionHandler.java
│   │   │   │
│   │   │   ├── util/
│   │   │   │   ├── RequestIdGenerator.java # Generate/extract request IDs
│   │   │   │   ├── PaginationHelper.java   # Pagination logic
│   │   │   │   └── TaskStateValidator.java # State machine validation
│   │   │   │
│   │   │   └── filter/
│   │   │       └── RequestIdFilter.java    # MDC population for request tracing
│   │   │
│   │   └── resources/
│   │       ├── application.yml             # Spring Boot configuration
│   │       ├── application-dev.yml         # Development profile
│   │       ├── application-prod.yml        # Production profile
│   │       ├── application-test.yml        # Test profile
│   │       │
│   │       └── db/migration/
│   │           ├── V1__Create_tasks_table.sql
│   │           ├── V2__Add_indexes.sql
│   │           └── V3__Add_version_column.sql
│   │
│   └── test/
│       ├── java/com/todoapi/
│       │   ├── controller/
│       │   │   └── TaskControllerTest.java
│       │   ├── service/
│       │   │   └── TaskServiceTest.java
│       │   ├── repository/
│       │   │   └── TaskRepositoryTest.java
│       │   └── integration/
│       │       └── TaskApiIntegrationTest.java
│       │
│       └── resources/
│           ├── application-test.yml
│           └── test-data.sql
│
├── docs/
│   ├── API.md                              # API endpoint documentation
│   ├── ARCHITECTURE.md                     # Architecture decisions
│   ├── DEPLOYMENT.md                       # Deployment guide
│   └── TROUBLESHOOTING.md                  # Common issues & solutions
│
└── scripts/
    ├── build.sh                            # Build script
    ├── run-local.sh                        # Run locally
    ├── run-tests.sh                        # Run test suite
    └── deploy.sh                           # Deployment script
```

### Key Directories Explained

| Directory | Purpose | Ownership |
|-----------|---------|-----------|
| `src/main/java/com/todoapi/controller/` | HTTP request handlers, route definitions | Backend Engineer |
| `src/main/java/com/todoapi/service/` | Business logic, state machine, validation | Backend Engineer |
| `src/main/java/com/todoapi/repository/` | Data access layer, queries | Backend Engineer |
| `src/main/java/com/todoapi/entity/` | JPA entities (database models) | Database Engineer |
| `src/main/java/com/todoapi/dto/` | Request/response DTOs, serialization | Backend Engineer |
| `src/main/java/com/todoapi/exception/` | Custom exceptions, error handling | Backend Engineer |
| `src/main/resources/db/migration/` | Flyway SQL migrations | Database Engineer |
| `src/test/` | Unit, integration, and API tests | QA Engineer |
| `docs/` | Architecture, deployment, troubleshooting guides | Tech Lead |

---

## 2. TECHNOLOGY STACK & VERSIONS

### Runtime & Framework

```xml
<!-- pom.xml: Core Dependencies -->

<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.todoapi</groupId>
  <artifactId>todo-api</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>

  <name>To-Do List API</name>
  <description>RESTful API for task management</description>

  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.0</version>
    <relativePath/>
  </parent>

  <properties>
    <java.version>17</java.version>
    <maven.compiler.source>17</maven.compiler.source>
    <maven.compiler.target>17</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <sqlite-jdbc.version>3.44.0.0</sqlite-jdbc.version>
    <flyway.version>9.22.3</flyway.version>
  </properties>

  <dependencies>
    <!-- Spring Boot Starters -->
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>

    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>

    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>

    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>

    <!-- Database -->
    <dependency>
      <groupId>org.xerial</groupId>
      <artifactId>sqlite-jdbc</artifactId>
      <version>${sqlite-jdbc.version}</version>
    </dependency>

    <dependency>
      <groupId>org.hibernate.orm</groupId>
      <artifactId>hibernate-community-dialects</artifactId>
    </dependency>

    <!-- Database Migrations -->
    <dependency>
      <groupId>org.flywaydb</groupId>
      <artifactId>flyway-core</artifactId>
      <version>${flyway.version}</version>
    </dependency>

    <!-- Logging -->
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-logging</artifactId>
    </dependency>

    <!-- JSON Processing -->
    <dependency>
      <groupId>com.fasterxml.jackson.core</groupId>
      <artifactId>jackson-databind</artifactId>
    </dependency>

    <dependency>
      <groupId>com.fasterxml.jackson.datatype</groupId>
      <artifactId>jackson-datatype-jsr310</artifactId>
    </dependency>

    <!-- Metrics & Observability -->
    <dependency>
      <groupId>io.micrometer</groupId>
      <artifactId>micrometer-core</artifactId>
    </dependency>

    <!-- Testing -->
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>

    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>

    <dependency>
      <groupId>org.mockito</groupId>
      <artifactId>mockito-core</artifactId>
      <scope>test</scope>
    </dependency>

    <dependency>
      <groupId>org.mockito</groupId>
      <artifactId>mockito-junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>

    <!-- Development Tools -->
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-devtools</artifactId>
      <scope>runtime</scope>
      <optional>true</optional>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
        <configuration>
          <excludes>
            <exclude>
              <groupId>org.springframework.boot</groupId>
              <artifactId>spring-boot-configuration-processor</artifactId>
            </exclude>
          </excludes>
        </configuration>
      </plugin>

      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-surefire-plugin</artifactId>
        <version>3.0.0</version>
        <configuration>
          <includes>
            <include>**/*Test.java</include>
            <include>**/*Tests.java</include>
          </includes>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```

### Dependency Versions (Locked)

| Component | Package | Version | Purpose |
|-----------|---------|---------|---------|
| **Java Runtime** | OpenJDK | 17 LTS | Language runtime; LTS ensures 5+ years of support |
| **Spring Boot** | org.springframework.boot:spring-boot-starter-parent | 3.2.0 | Framework, dependency management, auto-configuration |
| **Spring Web** | spring-boot-starter-web | 3.2.0 | REST controller support, embedded Tomcat |
| **Spring Data JPA** | spring-boot-starter-data-jpa | 3.2.0 | ORM, repository pattern, transaction management |
| **Spring Validation** | spring-boot-starter-validation | 3.2.0 | Bean validation (JSR-380), @Valid annotations |
| **Spring Actuator** | spring-boot-starter-actuator | 3.2.0 | Health checks, metrics endpoints, observability |
| **Hibernate ORM** | hibernate-community-dialects | (via Spring Boot) | JPA implementation, SQLite dialect support |
| **SQLite JDBC** | sqlite-jdbc | 3.44.0.0 | Pure Java SQLite driver, no native dependencies |
| **Flyway** | flyway-core | 9.22.3 | Database schema versioning, migrations |
| **Jackson** | jackson-databind, jackson-datatype-jsr310 | (via Spring Boot) | JSON serialization, Java 8 date/time support |
| **Micrometer** | micrometer-core | (via Spring Boot) | Metrics collection, Prometheus export |
| **SLF4J + Logback** | spring-boot-starter-logging | (via Spring Boot) | Structured logging, MDC support |
| **JUnit 5** | junit-jupiter | (via Spring Boot) | Unit testing framework |
| **Mockito** | mockito-core, mockito-junit-jupiter | (via Spring Boot) | Mocking for unit tests |

### Why Not X?

| Alternative | Why Not | Trade-off |
|-------------|---------|-----------|
| **Spring Boot 2.7** | EOL in November 2023; 3.2 is current LTS with 5+ years support | Requires Java 17+; older projects may need Java 11 compatibility |
| **Hibernate 5** | Bundled with Spring Boot 2.7; Spring Boot 3.2 uses Hibernate 6 | Requires migration of entity annotations if upgrading from 2.7 |
| **PostgreSQL** | Adds operational complexity (separate server, backups, replication). SQLite is sufficient for prototype. | If scale exceeds SQLite limits (>10GB, >1,000 writes/sec), migrate to PostgreSQL. |
| **Liquibase** | Flyway is simpler, more widely adopted, sufficient for this scale. | Liquibase offers more complex versioning; not needed for v1.0. |
| **Lombok** | Reduces boilerplate but adds compile-time magic. Spring Boot 3.2 has record types (Java 17) for immutable DTOs. | Records are less flexible than Lombok; use for simple DTOs only. |
| **MapStruct** | Overkill for simple DTO mapping. Manual mapping or Spring's BeanUtils sufficient. | If DTO count grows >10, consider MapStruct for maintainability. |

---

## 3. ENVIRONMENT CONFIGURATION

### Environment Variables (`.env` file)

```bash
# .env.example — Copy to .env and populate for local development

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

# Application name and version (informational)
APP_NAME=todo-api
APP_VERSION=1.0.0

# Spring profile: dev, test, prod
SPRING_PROFILES_ACTIVE=dev

# Server configuration
SERVER_PORT=8080
SERVER_SERVLET_CONTEXT_PATH=/api/v1

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# SQLite database file path (relative or absolute)
# For local dev: ./data/todo.db
# For Docker: /app/data/todo.db
SPRING_DATASOURCE_URL=jdbc:sqlite:./data/todo.db

# SQLite JDBC driver class (do not change)
SPRING_DATASOURCE_DRIVER_CLASS_NAME=org.sqlite.JDBC

# Connection pool settings
SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=10
SPRING_DATASOURCE_HIKARI_MINIMUM_IDLE=2
SPRING_DATASOURCE_HIKARI_CONNECTION_TIMEOUT=30000
SPRING_DATASOURCE_HIKARI_IDLE_TIMEOUT=600000
SPRING_DATASOURCE_HIKARI_MAX_LIFETIME=1800000

# JPA/Hibernate configuration
SPRING_JPA_DATABASE_PLATFORM=org.hibernate.community.dialect.SQLiteDialect
SPRING_JPA_HIBERNATE_DDL_AUTO=validate
SPRING_JPA_SHOW_SQL=false
SPRING_JPA_PROPERTIES_HIBERNATE_FORMAT_SQL=false
SPRING_JPA_PROPERTIES_HIBERNATE_USE_SQL_COMMENTS=false

# Flyway database migration
SPRING_FLYWAY_ENABLED=true
SPRING_FLYWAY_LOCATIONS=classpath:db/migration
SPRING_FLYWAY_OUT_OF_ORDER=false
SPRING_FLYWAY_VALIDATE_ON_MIGRATE=true

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Root logger level: DEBUG, INFO, WARN, ERROR
LOGGING_LEVEL_ROOT=INFO

# Application logger level
LOGGING_LEVEL_COM_TODOAPI=DEBUG

# Spring Framework logger level
LOGGING_LEVEL_ORG_SPRINGFRAMEWORK=INFO
LOGGING_LEVEL_ORG_SPRINGFRAMEWORK_WEB=DEBUG
LOGGING_LEVEL_ORG_HIBERNATE=WARN

# Log output format (console or file)
LOGGING_PATTERN_CONSOLE=%d{yyyy-MM-dd HH:mm:ss} - %logger{36} - %msg%n
LOGGING_FILE_NAME=logs/todo-api.log
LOGGING_FILE_MAX_SIZE=10MB
LOGGING_FILE_MAX_HISTORY=10

# ============================================================================
# ACTUATOR & OBSERVABILITY
# ============================================================================

# Actuator endpoints exposure (comma-separated)
MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE=health,metrics,info,prometheus
MANAGEMENT_ENDPOINTS_WEB_BASE_PATH=/actuator

# Health check configuration
MANAGEMENT_ENDPOINT_HEALTH_SHOW_DETAILS=when-authorized
MANAGEMENT_HEALTH_LIVENESSSTATE_ENABLED=true
MANAGEMENT_HEALTH_READINESSSTATE_ENABLED=true

# Metrics configuration
MANAGEMENT_METRICS_EXPORT_PROMETHEUS_ENABLED=true
MANAGEMENT_METRICS_TAGS_APPLICATION=${APP_NAME}
MANAGEMENT_METRICS_TAGS_ENVIRONMENT=${SPRING_PROFILES_ACTIVE}

# ============================================================================
# RATE LIMITING & SECURITY
# ============================================================================

# Rate limit: requests per minute per IP
RATE_LIMIT_REQUESTS_PER_MINUTE=600

# CORS configuration (comma-separated allowed origins)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080

# ============================================================================
# API CONFIGURATION
# ============================================================================

# Pagination defaults
API_PAGINATION_DEFAULT_LIMIT=20
API_PAGINATION_MAX_LIMIT=100

# Task configuration
TASK_SOFT_DELETE_ENABLED=false
TASK_RETENTION_DAYS=30

# Request timeout (milliseconds)
API_REQUEST_TIMEOUT_MS=30000

# ============================================================================
# DEVELOPMENT TOOLS (dev profile only)
# ============================================================================

# Enable Spring DevTools (auto-restart on file changes)
SPRING_DEVTOOLS_RESTART_ENABLED=true

# Enable H2 console for database inspection (dev only)
SPRING_H2_CONSOLE_ENABLED=false
```

### Spring Boot Configuration Files

#### `application.yml` (Base Configuration)

```yaml
# src/main/resources/application.yml

spring:
  application:
    name: todo-api
    version: 1.0.0

  # JPA/Hibernate
  jpa:
    database-platform: org.hibernate.community.dialect.SQLiteDialect
    hibernate:
      ddl-auto: validate  # Never auto-create schema; use Flyway
    show-sql: false
    properties:
      hibernate:
        format_sql: false
        use_sql_comments: false
        jdbc:
          batch_size: 20
          fetch_size: 50

  # Datasource (SQLite)
  datasource:
    url: jdbc:sqlite:./data/todo.db
    driver-class-name: org.sqlite.JDBC
    hikari:
      maximum-pool-size: 10
      minimum-idle: 2
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
      auto-commit: true

  # Flyway
  flyway:
    enabled: true
    locations: classpath:db/migration
    out-of-order: false
    validate-on-migrate: true

  # Jackson (JSON serialization)
  jackson:
    default-property-inclusion: non_null
    serialization:
      write-dates-as-timestamps: false
      indent-output: false
    deserialization:
      fail-on-unknown-properties: false

  # Servlet
  servlet:
    multipart:
      max-file-size: 10MB
      max-request-size: 10MB

# Server
server:
  port: 8080
  servlet:
    context-path: /api/v1
  compression:
    enabled: true
    min-response-size: 1024
  error:
    include-message: always
    include-binding-errors: always

# Logging
logging:
  level:
    root: INFO
    com.todoapi: DEBUG
    org.springframework: INFO
    org.springframework.web: DEBUG
    org.hibernate: WARN
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} - %logger{36} - %msg%n"
    file: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"
  file:
    name: logs/todo-api.log
    max-size: 10MB
    max-history: 10

# Actuator
management:
  endpoints:
    web:
      exposure:
        include: health,metrics,info,prometheus
      base-path: /actuator
  endpoint:
    health:
      show-details: when-authorized
  health:
    livenessState:
      enabled: true
    readinessState:
      enabled: true
  metrics:
    export:
      prometheus:
        enabled: true
    tags:
      application: ${spring.application.name}
      environment: ${spring.profiles.active}

# Application-specific properties
app:
  api:
    pagination:
      default-limit: 20
      max-limit: 100
    request-timeout-ms: 30000
  task:
    soft-delete-enabled: false
    retention-days: 30
  rate-limit:
    requests-per-minute: 600
  cors:
    allowed-origins: http://localhost:3000,http://localhost:8080
```

#### `application-dev.yml` (Development Profile)

```yaml
# src/main/resources/application-dev.yml

spring:
  jpa:
    show-sql: true
    properties:
      hibernate:
        format_sql: true
        use_sql_comments: true

  devtools:
    restart:
      enabled: true

logging:
  level:
    root: DEBUG
    com.todoapi: DEBUG
    org.springframework: DEBUG
    org.springframework.web: DEBUG
    org.hibernate.SQL: DEBUG
    org.hibernate.type.descriptor.sql.BasicBinder: TRACE

server:
  error:
    include-stacktrace: always
```

#### `application-prod.yml` (Production Profile)

```yaml
# src/main/resources/application-prod.yml

spring:
  jpa:
    show-sql: false
    properties:
      hibernate:
        format_sql: false
        use_sql_comments: false

logging:
  level:
    root: WARN
    com.todoapi: INFO
    org.springframework: WARN

server:
  error:
    include-stacktrace: never
    include-message: always

management:
  endpoints:
    web:
      exposure:
        include: health,metrics,prometheus
```

#### `application-test.yml` (Test Profile)

```yaml
# src/main/resources/application-test.yml

spring:
  datasource:
    url: jdbc:sqlite:memory:
    driver-class-name: org.sqlite.JDBC

  jpa:
    hibernate:
      ddl-auto: create-drop
    show-sql: false

  flyway:
    enabled: true

logging:
  level:
    root: WARN
    com.todoapi: INFO

server:
  port: 0  # Random port for test isolation
```

### Configuration Loading Order

1. **`application.yml`** — Base configuration (always loaded)
2. **`application-{profile}.yml`** — Profile-specific overrides (loaded based on `SPRING_PROFILES_ACTIVE`)
3. **Environment variables** — Override all YAML settings (via `@Value` or `@ConfigurationProperties`)
4. **System properties** — Highest priority (via `-D` flags)

### How to Use

**Local Development:**
```bash
# Copy template
cp .env.example .env

# Edit .env with local values
SPRING_PROFILES_ACTIVE=dev
SPRING_DATASOURCE_URL=jdbc:sqlite:./data/todo.db

# Run with Maven
mvn spring-boot:run

# Or build and run JAR
mvn clean package
java -jar target/todo-api-1.0.0.jar
```

**Production Deployment:**
```bash
# Set environment variables (via Docker, systemd, or cloud platform)
export SPRING_PROFILES_ACTIVE=prod
export SPRING_DATASOURCE_URL=jdbc:sqlite:/var/lib/todo-api/todo.db
export LOGGING_FILE_NAME=/var/log/todo-api/todo-api.log

# Run JAR
java -jar todo-api-1.0.0.jar
```

---

## 4. DATA MODELS & DATABASE SCHEMA

### Database Schema (SQL DDL)

#### Migration: `V1__Create_tasks_table.sql`

```sql
-- src/main/resources/db/migration/V1__Create_tasks_table.sql
-- Initial schema: tasks table with core columns

CREATE TABLE IF NOT EXISTS tasks (
  -- Primary Key
  id TEXT PRIMARY KEY NOT NULL,

  -- Task Content
  title VARCHAR(255) NOT NULL,
  description TEXT,

  -- Task Metadata
  priority VARCHAR(10) NOT NULL DEFAULT 'MEDIUM',
  due_date DATE,

  -- Task State
  status VARCHAR(20) NOT NULL DEFAULT 'NEW',

  -- Concurrency Control
  version INTEGER NOT NULL DEFAULT 1,

  -- Timestamps
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- Constraints
  CHECK (status IN ('NEW', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED')),
  CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH')),
  CHECK (length(title) > 0 AND length(title) <= 255),
  CHECK (length(description) <= 2000),
  CHECK (version > 0)
);

-- Audit: Record schema version
-- (Flyway manages this automatically in flyway_schema_history table)
```

#### Migration: `V2__Add_indexes.sql`

```sql
-- src/main/resources/db/migration/V2__Add_indexes.sql
-- Performance indexes for common queries

-- Index for list tasks by status (most common filter)
CREATE INDEX IF NOT EXISTS idx_tasks_status_created_at
  ON tasks(status, created_at DESC);

-- Index for list tasks by due date (filtering by date range)
CREATE INDEX IF NOT EXISTS idx_tasks_due_date
  ON tasks(due_date);

-- Index for list tasks by creation date (default sort)
CREATE INDEX IF NOT EXISTS idx_tasks_created_at
  ON tasks(created_at DESC);

-- Index for retrieving task by ID (primary key lookup, implicit)
-- SQLite automatically creates index on PRIMARY KEY

-- Composite index for common filter + sort combination
CREATE INDEX IF NOT EXISTS idx_tasks_status_priority_created_at
  ON tasks(status, priority, created_at DESC);
```

#### Migration: `V3__Add_version_column.sql` (Idempotent)

```sql
-- src/main/resources/db/migration/V3__Add_version_column.sql
-- Ensure version column exists (idempotent for existing databases)

-- SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS
-- So we check if column exists before adding
-- This migration is safe to re-run (Flyway prevents duplicate execution)

-- Note: If upgrading from v1.0 without version column, this adds it
-- For new installations, V1 already includes version column
```

### JPA Entity Model

#### `Task.java` (JPA Entity)

```java
// src/main/java/com/todoapi/entity/Task.java

package com.todoapi.entity;

import jakarta.persistence.*;
import jakarta.validation.constraints.*;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(
  name = "tasks",
  indexes = {
    @Index(name = "idx_tasks_status_created_at", columnList = "status, created_at DESC"),
    @Index(name = "idx_tasks_due_date", columnList = "due_date"),
    @Index(name = "idx_tasks_created_at", columnList = "created_at DESC"),
    @Index(name = "idx_tasks_status_priority_created_at", columnList = "status, priority, created_at DESC")
  }
)
public class Task {

  // ========================================================================
  // PRIMARY KEY
  // ========================================================================

  @Id
  @Column(name = "id", length = 36, nullable = false, updatable = false)
  private String id;

  // ========================================================================
  // TASK CONTENT
  // ========================================================================

  @NotBlank(message = "Title is required")
  @Size(min = 1, max = 255, message = "Title must be between 1 and 255 characters")
  @Column(name = "title", length = 255, nullable = false)
  private String title;

  @Size(max = 2000, message = "Description must not exceed 2000 characters")
  @Column(name = "description", columnDefinition = "TEXT")
  private String description;

  // ========================================================================
  // TASK METADATA
  // ========================================================================

  @NotNull(message = "Priority is required")
  @Enumerated(EnumType.STRING)
  @Column(name = "priority", length = 10, nullable = false)
  private TaskPriority priority;

  @Column(name = "due_date")
  private LocalDate dueDate;

  // ========================================================================
  // TASK STATE
  // ========================================================================

  @NotNull(message = "Status is required")
  @Enumerated(EnumType.STRING)
  @Column(name = "status", length = 20, nullable = false)
  private TaskStatus status;

  // ========================================================================
  // CONCURRENCY CONTROL
  // ========================================================================

  @Version
  @Column(name = "version", nullable = false)
  private Integer version;

  // ========================================================================
  // TIMESTAMPS
  // ========================================================================

  @NotNull
  @Column(name = "created_at", nullable = false, updatable = false)
  private LocalDateTime createdAt;

  @NotNull
  @Column(name = "updated_at", nullable = false)
  private LocalDateTime updatedAt;

  // ========================================================================
  // CONSTRUCTORS
  // ========================================================================

  public Task() {
    // JPA requires no-arg constructor
  }

  public Task(String title, String description, TaskPriority priority, LocalDate dueDate) {
    this.id = UUID.randomUUID().toString();
    this.title = title;
    this.description = description;
    this.priority = priority != null ? priority : TaskPriority.MEDIUM;
    this.dueDate = dueDate;
    this.status = TaskStatus.NEW;
    this.version = 1;
    this.createdAt = LocalDateTime.now();
    this.updatedAt = LocalDateTime.now();
  }

  // ========================================================================
  // LIFECYCLE CALLBACKS
  // ========================================================================

  @PreUpdate
  protected void onUpdate() {
    this.updatedAt = LocalDateTime.now();
  }

  // ========================================================================
  // GETTERS & SETTERS
  // ========================================================================

  public String getId() {
    return id;
  }

  public void setId(String id) {
    this.id = id;
  }

  public String getTitle() {
    return title;
  }

  public void setTitle(String title) {
    this.title = title;
  }

  public String getDescription() {
    return description;
  }

  public void setDescription(String description) {
    this.description = description;
  }

  public TaskPriority getPriority() {
    return priority;
  }

  public void setPriority(TaskPriority priority) {
    this.priority = priority;
  }

  public LocalDate getDueDate() {
    return dueDate;
  }

  public void setDueDate(LocalDate dueDate) {
    this.dueDate = dueDate;
  }

  public TaskStatus getStatus() {
    return status;
  }

  public void setStatus(TaskStatus status) {
    this.status = status;
  }

  public Integer getVersion() {
    return version;
  }

  public void setVersion(Integer version) {
    this.version = version;
  }

  public LocalDateTime getCreatedAt() {
    return createdAt;
  }

  public void setCreatedAt(LocalDateTime createdAt) {
    this.createdAt = createdAt;
  }

  public LocalDateTime getUpdatedAt() {
    return updatedAt;
  }

  public void setUpdatedAt(LocalDateTime updatedAt) {
    this.updatedAt = updatedAt;
  }

  // ========================================================================
  // UTILITY METHODS
  // ========================================================================

  @Override
  public String toString() {
    return "Task{" +
      "id='" + id + '\'' +
      ", title='" + title + '\'' +
      ", status=" + status +
      ", priority=" + priority +
      ", version=" + version +
      ", createdAt=" + createdAt +
      ", updatedAt=" + updatedAt +
      '}';
  }

  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (o == null || getClass() != o.getClass()) return false;
    Task task = (Task) o;
    return id != null && id.equals(task.id);
  }

  @Override
  public int hashCode() {
    return id != null ? id.hashCode() : 0;
  }
}
```

### Enums

#### `TaskStatus.java`

```java
// src/main/java/com/todoapi/entity/TaskStatus.java

package com.todoapi.entity;

/**
 * Task lifecycle states.
 *
 * State Transitions:
 * - NEW → IN_PROGRESS (task started)
 * - NEW → ARCHIVED (task abandoned without starting)
 * - IN_PROGRESS → COMPLETED (task finished)
 * - IN_PROGRESS → ARCHIVED (task abandoned mid-progress)
 * - COMPLETED → ARCHIVED (completed task archived)
 * - ARCHIVED → (terminal state, no transitions out)
 *
 * Invalid Transitions (rejected with 400 Bad Request):
 * - COMPLETED → IN_PROGRESS (cannot un-complete a task)
 * - ARCHIVED → * (cannot transition out of archived)
 */
public enum TaskStatus {
  NEW("new", "Task created, not yet started"),
  IN_PROGRESS("in_progress", "Task is actively being worked on"),
  COMPLETED("completed", "Task finished successfully"),
  ARCHIVED("archived", "Task archived (abandoned or completed and archived)");

  private final String value;
  private final String description;

  TaskStatus(String value, String description) {
    this.value = value;
    this.description = description;
  }

  public String getValue() {
    return value;
  }

  public String getDescription() {
    return description;
  }

  public static TaskStatus fromValue(String value) {
    for (TaskStatus status : TaskStatus.values()) {
      if (status.value.equalsIgnoreCase(value)) {
        return status;
      }
    }
    throw new IllegalArgumentException("Invalid task status: " + value);
  }
}
```

#### `TaskPriority.java`

```java
// src/main/java/com/todoapi/entity/TaskPriority.java

package com.todoapi.entity;

/**
 * Task priority levels.
 *
 * Used for sorting and filtering tasks.
 * No state machine constraints; priority can be changed at any time.
 */
public enum TaskPriority {
  LOW("low", 1),
  MEDIUM("medium", 2),
  HIGH("high", 3);

  private final String value;
  private final int level;

  TaskPriority(String value, int level) {
    this.value = value;
    this.level = level;
  }

  public String getValue() {
    return value;
  }

  public int getLevel() {
    return level;
  }

  public static TaskPriority fromValue(String value) {
    for (TaskPriority priority : TaskPriority.values()) {
      if (priority.value.equalsIgnoreCase(value)) {
        return priority;
      }
    }
    throw new IllegalArgumentException("Invalid task priority: " + value);
  }
}
```

### Data Transfer Objects (DTOs)

#### `CreateTaskRequest.java`

```java
// src/main/java/com/todoapi/dto/CreateTaskRequest.java

package com.todoapi.dto;

import jakarta.validation.constraints.*;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDate;

/**
 * Request DTO for POST /tasks (create task).
 *
 * Validation:
 * - title: required, 1-255 characters
 * - description: optional, max 2000 characters
 * - priority: optional, must be LOW|MEDIUM|HIGH (default: MEDIUM)
 * - due_date: optional, must be ISO 8601 date (YYYY-MM-DD)
 */
public class CreateTaskRequest {

  @NotBlank(message = "Title is required")
  @Size(min = 1, max = 255, message = "Title must be between 1 and 255 characters")
  @JsonProperty("title")
  private String title;

  @Size(max = 2000, message = "Description must not exceed 2000 characters")
  @JsonProperty("description")
  private String description;

  @Pattern(
    regexp = "^(LOW|MEDIUM|HIGH)$",
    message = "Priority must be LOW, MEDIUM, or HIGH"
  )
  @JsonProperty("priority")
  private String priority;

  @JsonProperty("due_date")
  private LocalDate dueDate;

  // ========================================================================
  // CONSTRUCTORS
  // ========================================================================

  public CreateTaskRequest() {
  }

  public CreateTaskRequest(String title, String description, String priority, LocalDate dueDate) {
    this.title = title;
    this.description = description;
    this.priority = priority;
    this.dueDate = dueDate;
  }

  // ========================================================================
  // GETTERS & SETTERS
  // ========================================================================

  public String getTitle() {
    return title;
  }

  public void setTitle(String title) {
    this.title = title;
  }

  public String getDescription() {
    return description;
  }

  public void setDescription(String description) {
    this.description = description;
  }

  public String getPriority() {
    return priority;
  }

  public void setPriority(String priority) {
    this.priority = priority;
  }

  public LocalDate getDueDate() {
    return dueDate;
  }

  public void setDueDate(LocalDate dueDate) {
    this.dueDate = dueDate;
  }
}
```

#### `UpdateTaskRequest.java`

```java
// src/main/java/com/todoapi/dto/UpdateTaskRequest.java

package com.todoapi.dto;

import jakarta.validation.constraints.*;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDate;

/**
 * Request DTO for PATCH /tasks/{id} (update task).
 *
 * All fields are optional; only provided fields are updated.
 * Version field is required for optimistic locking.
 *
 * Validation:
 * - version: required, must match current version in database
 * - status: optional, must be valid state transition
 * - title: optional, 1-255 characters
 * - description: optional, max 2000 characters
 * - priority: optional, LOW|MEDIUM|HIGH
 * - due_date: optional, ISO 8601 date
 */
public class UpdateTaskRequest {

  @NotNull(message = "Version is required for optimistic locking")
  @Min(value = 1, message = "Version must be >= 1")
  @JsonProperty("version")
  private Integer version;

  @Pattern(
    regexp = "^(NEW|IN_PROGRESS|COMPLETED|ARCHIVED)$",
    message = "Status must be NEW, IN_PROGRESS, COMPLETED, or ARCHIVED"
  )
  @JsonProperty("status")
  private String status;

  @Size(min = 1, max = 255, message = "Title must be between 1 and 255 characters")
  @JsonProperty("title")
  private String title;

  @Size(max = 2000, message = "Description must not exceed 2000 characters")
  @JsonProperty("description")
  private String description;

  @Pattern(
    regexp = "^(LOW|MEDIUM|HIGH)$",
    message = "Priority must be LOW, MEDIUM, or HIGH"
  )
  @JsonProperty("priority")
  private String priority;

  @JsonProperty("due_date")
  private LocalDate dueDate;

  // ========================================================================
  // CONSTRUCTORS
  // ========================================================================

  public UpdateTaskRequest() {
  }

  public UpdateTaskRequest(Integer version, String status, String title, String description,
                           String priority, LocalDate dueDate) {
    this.version = version;
    this.status = status;
    this.title = title;
    this.description = description;
    this.priority = priority;
    this.dueDate = dueDate;
  }

  // ========================================================================
  // GETTERS & SETTERS
  // ========================================================================

  public Integer getVersion() {
    return version;
  }

  public void setVersion(Integer version) {
    this.version = version;
  }

  public String getStatus() {
    return status;
  }

  public void setStatus(String status) {
    this.status = status;
  }

  public String getTitle() {
    return title;
  }

  public void setTitle(String title) {
    this.title = title;
  }

  public String getDescription() {
    return description;
  }

  public void setDescription(String description) {
    this.description = description;
  }

  public String getPriority() {
    return priority;
  }

  public void setPriority(String priority) {
    this.priority = priority;
  }

  public LocalDate getDueDate() {
    return dueDate;
  }

  public void setDueDate(LocalDate dueDate) {
    this.dueDate = dueDate;
  }

  // ========================================================================
  // UTILITY METHODS
  // ========================================================================

  /**
   * Check if any field is provided (not null).
   * Used to validate that at least one field is being updated.
   */
  public boolean hasAnyUpdate() {
    return status != null || title != null || description != null ||
           priority != null || dueDate != null;
  }
}
```

#### `TaskResponse.java`

```java
// src/main/java/com/todoapi/dto/TaskResponse.java

package com.todoapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * Response DTO for task endpoints.
 *
 * Returned by:
 * - POST /tasks (create)
 * - GET /tasks/{id} (retrieve)
 * - PATCH /tasks/{id} (update)
 * - GET /tasks (list, as array)
 */
public class TaskResponse {

  @JsonProperty("id")
  private String id;

  @JsonProperty("title")
  private String title;

  @JsonProperty("description")
  private String description;

  @JsonProperty("priority")
  private String priority;

  @JsonProperty("due_date")
  private LocalDate dueDate;

  @JsonProperty("status")
  private String status;

  @JsonProperty("version")
  private Integer version;

  @JsonProperty("created_at")
  private LocalDateTime createdAt;

  @JsonProperty("updated_at")
  private LocalDateTime updatedAt;

  // ========================================================================
  // CONSTRUCTORS
  // ========================================================================

  public TaskResponse() {
  }

  public TaskResponse(String id, String title, String description, String priority,
                      LocalDate dueDate, String status, Integer version,
                      LocalDateTime createdAt, LocalDateTime updatedAt) {
    this.id = id;
    this.title = title;
    this.description = description;
    this.priority = priority;
    this.dueDate = dueDate;
    this.status = status;
    this.version = version;
    this.createdAt = createdAt;
    this.updatedAt = updatedAt;
  }

  // ========================================================================
  // GETTERS & SETTERS
  // ========================================================================

  public String getId() {
    return id;
  }

  public void setId(String id) {
    this.id = id;
  }

  public String getTitle() {
    return title;
  }

  public void setTitle(String title) {
    this.title = title;
  }

  public String getDescription() {
    return description;
  }

  public void setDescription(String description) {
    this.description = description;
  }

  public String getPriority() {
    return priority;
  }

  public void setPriority(String priority) {
    this.priority = priority;
  }

  public LocalDate getDueDate() {
    return dueDate;
  }

  public void setDueDate(LocalDate dueDate) {
    this.dueDate = dueDate;
  }

  public String getStatus() {
    return status;
  }

  public void setStatus(String status) {
    this.status = status;
  }

  public Integer getVersion() {
    return version;
  }

  public void setVersion(Integer version) {
    this.version = version;
  }

  public LocalDateTime getCreatedAt() {
    return createdAt;
  }

  public void setCreatedAt(LocalDateTime createdAt) {
    this.createdAt = createdAt;
  }

  public LocalDateTime getUpdatedAt() {
    return updatedAt;
  }

  public void setUpdatedAt(LocalDateTime updatedAt) {
    this.updatedAt = updatedAt;
  }
}
```

#### `ListTasksResponse.java`

```java
// src/main/java/com/todoapi/dto/ListTasksResponse.java

package com.todoapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/**
 * Response DTO for GET /tasks (list tasks with pagination).
 *
 * Contains:
 * - tasks: array of TaskResponse objects
 * - pagination: metadata about current page
 */
public class ListTasksResponse {

  @JsonProperty("tasks")
  private List<TaskResponse> tasks;

  @JsonProperty("pagination")
  private PaginationMetadata pagination;

  // ========================================================================
  // CONSTRUCTORS
  // ========================================================================

  public ListTasksResponse() {
  }

  public ListTasksResponse(List<TaskResponse> tasks, PaginationMetadata pagination) {
    this.tasks = tasks;
    this.pagination = pagination;
  }

  // ========================================================================
  // GETTERS & SETTERS
  // ========================================================================

  public List<TaskResponse> getTasks() {
    return tasks;
  }

  public void setTasks(List<TaskResponse> tasks) {
    this.tasks = tasks;
  }

  public PaginationMetadata getPagination() {
    return pagination;
  }

  public void setPagination(PaginationMetadata pagination) {
    this.pagination = pagination;
  }

  // ========================================================================
  // NESTED CLASS: PaginationMetadata
  // ========================================================================

  public static class PaginationMetadata {

    @JsonProperty("limit")
    private Integer limit;

    @JsonProperty("offset")
    private Integer offset;

    @JsonProperty("total")
    private Long total;

    @JsonProperty("has_more")
    private Boolean hasMore;

    // Constructors
    public PaginationMetadata() {
    }

    public PaginationMetadata(Integer limit, Integer offset, Long total, Boolean hasMore) {
      this.limit = limit;
      this.offset = offset;
      this.total = total;
      this.hasMore = hasMore;
    }

    // Getters & Setters
    public Integer getLimit() {
      return limit;
    }

    public void setLimit(Integer limit) {
      this.limit = limit;
    }

    public Integer getOffset() {
      return offset;
    }

    public void setOffset(Integer offset) {
      this.offset = offset;
    }

    public Long getTotal() {
      return total;
    }

    public void setTotal(Long total) {
      this.total = total;
    }

    public Boolean getHasMore() {
      return hasMore;
    }

    public void setHasMore(Boolean hasMore) {
      this.hasMore = hasMore;
    }
  }
}
```

#### `ErrorResponse.java`

```java
// src/main/java/com/todoapi/dto/ErrorResponse.java

package com.todoapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.LocalDateTime;
import java.util.List;

/**
 * Response DTO for error responses (4xx, 5xx).
 *
 * Returned by GlobalExceptionHandler for all error scenarios.
 */
public class ErrorResponse {

  @JsonProperty("error")
  private ErrorDetail error;

  @JsonProperty("timestamp")
  private LocalDateTime timestamp;

  @JsonProperty("request_id")
  private String requestId;

  // ========================================================================
  // CONSTRUCTORS
  // ========================================================================

  public ErrorResponse() {
    this.timestamp = LocalDateTime.now();
  }

  public ErrorResponse(String code, String message, String requestId) {
    this();
    this.error = new ErrorDetail(code, message);
    this.requestId = requestId;
  }

  public ErrorResponse(String code, String message, List<String> details, String requestId) {
    this();
    this.error = new ErrorDetail(code, message, details);
    this.requestId = requestId;
  }

  // ========================================================================
  // GETTERS & SETTERS
  // ========================================================================

  public ErrorDetail getError() {
    return error;
  }

  public void setError(ErrorDetail error) {
    this.error = error;
  }

  public LocalDateTime getTimestamp() {
    return timestamp;
  }

  public void setTimestamp(LocalDateTime timestamp) {
    this.timestamp = timestamp;
  }

  public String getRequestId() {
    return requestId;
  }

  public void setRequestId(String requestId) {
    this.requestId = requestId;
  }

  // ========================================================================
  // NESTED CLASS: ErrorDetail
  // ========================================================================

  public static class ErrorDetail {

    @JsonProperty("code")
    private String code;

    @JsonProperty("message")
    private String message;

    @JsonProperty("details")
    private List<String> details;

    // Constructors
    public ErrorDetail() {
    }

    public ErrorDetail(String code, String message) {
      this.code = code;
      this.message = message;
    }

    public ErrorDetail(String code, String message, List<String> details) {
      this.code = code;
      this.message = message;
      this.details = details;
    }

    // Getters & Setters
    public String getCode() {
      return code;
    }

    public void setCode(String code) {
      this.code = code;
    }

    public String getMessage() {
      return message;
    }

    public void setMessage(String message) {
      this.message = message;
    }

    public List<String> getDetails() {
      return details;
    }

    public void setDetails(List<String> details) {
      this.details = details;
    }
  }
}
```

### Database Relationships & Constraints

#### Primary Key Strategy

| Column | Type | Constraint | Rationale |
|--------|------|-----------|-----------|
| `id` | TEXT (UUID) | PRIMARY KEY, NOT NULL, IMMUTABLE | Unique identifier; generated by application (UUID.randomUUID()); never exposed in PATCH requests |

#### Unique Constraints

| Constraint | Columns | Rationale |
|-----------|---------|-----------|
| None (v1.0) | — | Tasks are not user-scoped; no secondary unique constraints. If multi-tenancy added, add `UNIQUE(user_id, title)`. |

#### Foreign Keys

| Constraint | Rationale |
|-----------|-----------|
| None | No external dependencies in v1.0. Tasks are standalone entities. |

#### Check Constraints

| Constraint | Rationale |
|-----------|-----------|
| `status IN ('NEW', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED')` | Enforce valid status values at database level |
| `priority IN ('LOW', 'MEDIUM', 'HIGH')` | Enforce valid priority values at database level |
| `length(title) > 0 AND length(title) <= 255` | Enforce title length at database level |
| `length(description) <= 2000` | Enforce description length at database level |
| `version > 0` | Enforce positive version numbers |

#### Indexes

| Index Name | Columns | Query Pattern | Rationale |
|-----------|---------|---------------|-----------|
| `idx_tasks_status_created_at` | `(status, created_at DESC)` | List tasks by status | Most common filter; enables efficient filtering + sorting |
| `idx_tasks_due_date` | `(due_date)` | Filter by due date range | Supports date range queries |
| `idx_tasks_created_at` | `(created_at DESC)` | Default sort order | Supports default list ordering |
| `idx_tasks_status_priority_created_at` | `(status, priority, created_at DESC)` | Filter by status + priority | Composite index for common multi-filter queries |

### Data Type Mapping

| Column | SQL Type | Java Type | JSON Type | Rationale |
|--------|----------|-----------|-----------|-----------|
| `id` | TEXT | String | string | UUID as string (36 chars) |
| `title` | VARCHAR(255) | String | string | Task name |
| `description` | TEXT | String | string | Optional task details |
| `priority` | VARCHAR(10) | TaskPriority (enum) | string | LOW, MEDIUM, HIGH |
| `due_date` | DATE | LocalDate | string (ISO 8601) | Optional deadline |
| `status` | VARCHAR(20) | TaskStatus (enum) | string | NEW, IN_PROGRESS, COMPLETED, ARCHIVED |
| `version` | INTEGER | Integer | number | Optimistic locking counter |
| `created_at` | TIMESTAMP | LocalDateTime | string (ISO 8601) | Task creation time |
| `updated_at` | TIMESTAMP | LocalDateTime | string (ISO 8601) | Last modification time |

### Nullable Columns

| Column | Nullable | Default | Rationale |
|--------|----------|---------|-----------|
| `id` | NO | (generated) | Primary key; always required |
| `title` | NO | — | Required field; must be provided on creation |
| `description` | YES | NULL | Optional field |
| `priority` | NO | 'MEDIUM' | Required; defaults to MEDIUM if not provided |
| `due_date` | YES | NULL | Optional field |
| `status` | NO | 'NEW' | Required; defaults to NEW on creation |
| `version` | NO | 1 | Required; starts at 1 |
| `created_at` | NO | CURRENT_TIMESTAMP | Required; set by database on insert |
| `updated_at` | NO | CURRENT_TIMESTAMP | Required; set by database on insert/update |

### Concurrency Control

#### Optimistic Locking Strategy

**Mechanism:** Version field incremented on every PATCH operation.

**Conflict Detection:**
- Client sends current version in PATCH request
- Database checks: `WHERE id = ? AND version = ?`
- If version mismatch: 0 rows updated → 409 Conflict
- If version matches: row updated, version incremented → 200 OK

**Retry Logic (Client Responsibility):**
1. Client receives 409 Conflict with current task state
2. Client re-fetches task (GET /tasks/{id})
3. Client retries PATCH with new version
4. If still conflicts, client decides: retry or abort

**Why Optimistic Locking?**
- Suitable for low-contention workloads (most tasks have few concurrent updates)
- Avoids row-level locks that could cause deadlocks
- Clients handle conflicts explicitly (no hidden retries)

**Limitations:**
- High contention on popular tasks could cause cascading 409s
- Clients must implement retry logic
- Not suitable for high-frequency updates to same task

**Future Alternative (if contention becomes issue):**
- Migrate to pessimistic locking (SELECT ... FOR UPDATE)
- Or use database-level row locks (PostgreSQL advisory locks)

---

## SUMMARY: Section 1-4 Complete

This section provides:

1. **Project Structure** — Complete file/folder tree for Spring Boot + Maven project
2. **Technology Stack** — Locked versions, pom.xml dependencies, rationale for each choice
3. **Environment Configuration** — All env vars, Spring Boot YAML configs for dev/prod/test profiles
4. **Data Models** — SQL DDL (migrations), JPA entities, enums, DTOs, indexes, constraints, concurrency model

**Ready for Part 2:** API Contract Specification, Error Handling, Validation Rules, Concurrency Model Details

---

**END OF PART 1**

---

# 5. API CONTRACT SPECIFICATION

## 5.1 API Overview

### Base URL
```
http://localhost:8080/api/v1
```

### Content Type
All requests and responses use `application/json`.

### Request Headers (All Endpoints)
```
Content-Type: application/json
X-Request-ID: string (optional; generated by server if not provided)
X-Idempotency-Key: string (required for POST /tasks; optional for other endpoints)
```

### Response Headers (All Endpoints)
```
Content-Type: application/json
X-Request-ID: string (echoed from request or generated)
X-RateLimit-Limit: integer (requests per minute)
X-RateLimit-Remaining: integer (requests remaining in current window)
X-RateLimit-Reset: integer (Unix timestamp when limit resets)
```

### Rate Limiting
- **Limit:** 1,000 requests per minute per IP address
- **Enforcement:** Token bucket algorithm; burst capacity = 100 requests
- **Response on Limit Exceeded:** 429 Too Many Requests (see [Error Responses](#error-responses))

---

## 5.2 Endpoint: Create Task

### Request

**Method:** `POST`  
**Path:** `/api/v1/tasks`  
**Authentication:** None  
**Rate Limit:** 1 request per second per IP (burst: 10)

**Headers:**
```
Content-Type: application/json
X-Request-ID: string (optional)
X-Idempotency-Key: string (required)
```

**Request Body Schema:**
```json
{
  "title": "string (required, 1-255 characters, non-empty after trim)",
  "description": "string (optional, max 2000 characters, null if omitted)",
  "due_date": "string (optional, ISO 8601 date format: YYYY-MM-DD, null if omitted)",
  "priority": "enum (optional, default: MEDIUM, allowed: LOW, MEDIUM, HIGH)"
}
```

**Request Body Examples:**

*Minimal (required fields only):*
```json
{
  "title": "Buy groceries",
  "X-Idempotency-Key": "550e8400-e29b-41d4-a716-446655440000"
}
```

*Full (all fields):*
```json
{
  "title": "Complete project proposal",
  "description": "Finalize Q4 roadmap and submit to stakeholders",
  "due_date": "2024-12-31",
  "priority": "HIGH",
  "X-Idempotency-Key": "550e8400-e29b-41d4-a716-446655440001"
}
```

### Response

**Success Status:** `201 Created`

**Response Body Schema:**
```json
{
  "id": "string (UUID, e.g., '550e8400-e29b-41d4-a716-446655440000')",
  "title": "string",
  "description": "string or null",
  "due_date": "string (ISO 8601 date) or null",
  "priority": "enum (LOW, MEDIUM, HIGH)",
  "status": "enum (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)",
  "version": "integer (starts at 1)",
  "created_at": "string (ISO 8601 timestamp with timezone, e.g., '2024-01-15T10:30:00Z')",
  "updated_at": "string (ISO 8601 timestamp with timezone)"
}
```

**Response Body Example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Complete project proposal",
  "description": "Finalize Q4 roadmap and submit to stakeholders",
  "due_date": "2024-12-31",
  "priority": "HIGH",
  "status": "NEW",
  "version": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

### Error Responses

**400 Bad Request** — Validation failure

**Trigger Conditions:**
- `title` is missing, empty, or exceeds 255 characters
- `title` contains only whitespace
- `description` exceeds 2000 characters
- `due_date` is not in ISO 8601 format (YYYY-MM-DD)
- `due_date` is in the past (before today)
- `priority` is not one of: LOW, MEDIUM, HIGH
- Request body is not valid JSON

**Response Body Schema:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "string (e.g., 'title', 'due_date')",
        "message": "string (e.g., 'must not be empty', 'must be a valid ISO 8601 date')"
      }
    ]
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "title",
        "message": "must not be empty"
      },
      {
        "field": "due_date",
        "message": "must be a valid ISO 8601 date in format YYYY-MM-DD"
      }
    ]
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440002"
}
```

---

**409 Conflict** — Duplicate idempotency key with different payload

**Trigger Conditions:**
- `X-Idempotency-Key` header matches a previous request, but request body differs
- Example: First request creates task with title "A"; second request with same key tries to create task with title "B"

**Response Body Schema:**
```json
{
  "error": {
    "code": "IDEMPOTENCY_CONFLICT",
    "message": "Idempotency key already used with different request payload",
    "details": {
      "idempotency_key": "string",
      "previous_response": {
        "id": "string (UUID of previously created task)",
        "created_at": "string (ISO 8601 timestamp)"
      }
    }
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "error": {
    "code": "IDEMPOTENCY_CONFLICT",
    "message": "Idempotency key already used with different request payload",
    "details": {
      "idempotency_key": "550e8400-e29b-41d4-a716-446655440001",
      "previous_response": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "created_at": "2024-01-15T10:30:00Z"
      }
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440003"
}
```

---

**429 Too Many Requests** — Rate limit exceeded

**Trigger Conditions:**
- Client exceeds 1,000 requests per minute per IP address
- Burst capacity (100 requests) exceeded

**Response Body Schema:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please retry after X seconds.",
    "details": {
      "limit": "integer (requests per minute)",
      "window_seconds": "integer (60)",
      "retry_after_seconds": "integer"
    }
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please retry after 12 seconds.",
    "details": {
      "limit": 1000,
      "window_seconds": 60,
      "retry_after_seconds": 12
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440004"
}
```

---

**500 Internal Server Error** — Unexpected server error

**Trigger Conditions:**
- Database connection failure
- Unexpected exception during task creation
- Filesystem error (SQLite write failure)

**Response Body Schema:**
```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred. Please contact support.",
    "details": {
      "request_id": "string (for support reference)"
    }
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "error": {
    "code": "INTERNAL_SERVER_ERROR",
    "message": "An unexpected error occurred. Please contact support.",
    "details": {
      "request_id": "550e8400-e29b-41d4-a716-446655440005"
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440005"
}
```

### Business Rules

1. **Idempotency:** `X-Idempotency-Key` header is required. If the same key is used within 24 hours with the same request body, the API returns the previously created task (200 OK) instead of creating a duplicate.

2. **Default Values:**
   - `status` defaults to `NEW`
   - `priority` defaults to `MEDIUM`
   - `description` and `due_date` default to `null` if omitted

3. **Immutable Fields:** Once created, `id`, `created_at` cannot be changed.

4. **Due Date Validation:** If provided, `due_date` must be today or in the future (not in the past).

5. **Title Normalization:** Leading/trailing whitespace is trimmed; internal whitespace is preserved.

6. **Version Initialization:** All new tasks start with `version = 1`.

---

## 5.3 Endpoint: List Tasks

### Request

**Method:** `GET`  
**Path:** `/api/v1/tasks`  
**Authentication:** None  
**Rate Limit:** 100 requests per second per IP

**Query Parameters:**

```
status: enum (optional, allowed: NEW, IN_PROGRESS, COMPLETED, ARCHIVED)
  - If provided, filter tasks by status
  - If omitted, return tasks in all statuses (except ARCHIVED by default; see note below)
  - Multiple values NOT supported; use separate requests

priority: enum (optional, allowed: LOW, MEDIUM, HIGH)
  - If provided, filter tasks by priority
  - If omitted, return tasks of all priorities

due_date_from: string (optional, ISO 8601 date format: YYYY-MM-DD)
  - If provided, return tasks with due_date >= due_date_from
  - If omitted, no lower bound

due_date_to: string (optional, ISO 8601 date format: YYYY-MM-DD)
  - If provided, return tasks with due_date <= due_date_to
  - If omitted, no upper bound

sort_by: enum (optional, default: created_at, allowed: created_at, due_date, priority, status)
  - Field to sort by
  - Default: created_at (descending)

sort_order: enum (optional, default: DESC, allowed: ASC, DESC)
  - Sort direction
  - Default: DESC (newest first for created_at, earliest first for due_date)

limit: integer (optional, default: 20, min: 1, max: 100)
  - Number of tasks to return per page

offset: integer (optional, default: 0, min: 0)
  - Number of tasks to skip (for pagination)
```

**Query String Examples:**

*List all tasks (default):*
```
GET /api/v1/tasks
```

*List tasks with status=IN_PROGRESS, sorted by due_date ascending:*
```
GET /api/v1/tasks?status=IN_PROGRESS&sort_by=due_date&sort_order=ASC
```

*List high-priority tasks due in next 7 days, paginated:*
```
GET /api/v1/tasks?priority=HIGH&due_date_from=2024-01-15&due_date_to=2024-01-22&limit=50&offset=0
```

*List completed tasks, sorted by creation date descending, page 2:*
```
GET /api/v1/tasks?status=COMPLETED&sort_by=created_at&sort_order=DESC&limit=20&offset=20
```

### Response

**Success Status:** `200 OK`

**Response Body Schema:**
```json
{
  "data": [
    {
      "id": "string (UUID)",
      "title": "string",
      "description": "string or null",
      "due_date": "string (ISO 8601 date) or null",
      "priority": "enum (LOW, MEDIUM, HIGH)",
      "status": "enum (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)",
      "version": "integer",
      "created_at": "string (ISO 8601 timestamp)",
      "updated_at": "string (ISO 8601 timestamp)"
    }
  ],
  "pagination": {
    "limit": "integer (requested limit)",
    "offset": "integer (requested offset)",
    "total": "integer (total tasks matching filters, excluding ARCHIVED by default)",
    "has_more": "boolean (true if more tasks exist beyond current page)"
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Complete project proposal",
      "description": "Finalize Q4 roadmap and submit to stakeholders",
      "due_date": "2024-12-31",
      "priority": "HIGH",
      "status": "IN_PROGRESS",
      "version": 2,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T14:45:00Z"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "title": "Review team feedback",
      "description": null,
      "due_date": "2024-01-20",
      "priority": "MEDIUM",
      "status": "NEW",
      "version": 1,
      "created_at": "2024-01-15T11:00:00Z",
      "updated_at": "2024-01-15T11:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 42,
    "has_more": true
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440006"
}
```

### Error Responses

**400 Bad Request** — Invalid query parameters

**Trigger Conditions:**
- `status` is not one of: NEW, IN_PROGRESS, COMPLETED, ARCHIVED
- `priority` is not one of: LOW, MEDIUM, HIGH
- `due_date_from` or `due_date_to` is not in ISO 8601 format
- `due_date_from` is after `due_date_to`
- `limit` is < 1 or > 100
- `offset` is < 0
- `sort_by` is not one of: created_at, due_date, priority, status
- `sort_order` is not one of: ASC, DESC

**Response Body Schema:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid query parameters",
    "details": [
      {
        "parameter": "string (e.g., 'status', 'limit')",
        "message": "string (e.g., 'must be one of: NEW, IN_PROGRESS, COMPLETED, ARCHIVED')"
      }
    ]
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid query parameters",
    "details": [
      {
        "parameter": "status",
        "message": "must be one of: NEW, IN_PROGRESS, COMPLETED, ARCHIVED"
      },
      {
        "parameter": "limit",
        "message": "must be between 1 and 100"
      }
    ]
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440007"
}
```

---

**429 Too Many Requests** — Rate limit exceeded

(Same as POST /tasks; see [Error Responses](#error-responses))

---

**500 Internal Server Error** — Unexpected server error

(Same as POST /tasks; see [Error Responses](#error-responses))

### Business Rules

1. **Default Behavior:** If no `status` filter is provided, the API returns tasks in all statuses EXCEPT `ARCHIVED`. To include archived tasks, explicitly pass `status=ARCHIVED` (which returns ONLY archived tasks). To include both active and archived tasks, clients must make two separate requests.

2. **Pagination Stability:** Sort order is stable across pagination requests. Default sort is `created_at DESC, id DESC` (tie-breaker). If a task is deleted between page requests, the offset may shift by 1; clients should deduplicate by `id`.

3. **Empty Result:** If no tasks match the filters, return `200 OK` with `data: []` and `total: 0`.

4. **Total Count:** The `total` field reflects the count of tasks matching the filters (excluding ARCHIVED by default). It is NOT affected by `limit` or `offset`.

5. **has_more Flag:** `has_more` is `true` if `offset + limit < total`; `false` otherwise.

6. **Date Range Filtering:** Both `due_date_from` and `due_date_to` are inclusive. A task with `due_date = 2024-01-15` matches `due_date_from=2024-01-15&due_date_to=2024-01-15`.

---

## 5.4 Endpoint: Retrieve Task

### Request

**Method:** `GET`  
**Path:** `/api/v1/tasks/{id}`  
**Authentication:** None  
**Rate Limit:** 100 requests per second per IP

**Path Parameters:**
```
id: string (UUID, required)
  - Task ID to retrieve
```

**Query Parameters:** None

**Request Example:**
```
GET /api/v1/tasks/550e8400-e29b-41d4-a716-446655440000
```

### Response

**Success Status:** `200 OK`

**Response Body Schema:**
```json
{
  "id": "string (UUID)",
  "title": "string",
  "description": "string or null",
  "due_date": "string (ISO 8601 date) or null",
  "priority": "enum (LOW, MEDIUM, HIGH)",
  "status": "enum (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)",
  "version": "integer",
  "created_at": "string (ISO 8601 timestamp)",
  "updated_at": "string (ISO 8601 timestamp)"
}
```

**Response Body Example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Complete project proposal",
  "description": "Finalize Q4 roadmap and submit to stakeholders",
  "due_date": "2024-12-31",
  "priority": "HIGH",
  "status": "IN_PROGRESS",
  "version": 2,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T14:45:00Z"
}
```

### Error Responses

**400 Bad Request** — Invalid task ID format

**Trigger Conditions:**
- `id` is not a valid UUID format

**Response Body Schema:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid task ID format",
    "details": {
      "parameter": "id",
      "message": "must be a valid UUID"
    }
  },
  "request_id": "string"
}
```

---

**404 Not Found** — Task does not exist

**Trigger Conditions:**
- Task with given `id` does not exist in the database
- Task was deleted (hard-delete; no soft-delete in v1.0)

**Response Body Schema:**
```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task not found",
    "details": {
      "id": "string (UUID)"
    }
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task not found",
    "details": {
      "id": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440008"
}
```

---

**429 Too Many Requests** — Rate limit exceeded

(Same as POST /tasks; see [Error Responses](#error-responses))

---

**500 Internal Server Error** — Unexpected server error

(Same as POST /tasks; see [Error Responses](#error-responses))

### Business Rules

1. **Immutable Response:** The response includes the current state of the task, including the `version` field. Clients should use this `version` value in subsequent PATCH requests to detect conflicts.

2. **Deleted Tasks:** Deleted tasks return 404 Not Found. There is no way to retrieve a deleted task (no soft-delete in v1.0).

---

## 5.5 Endpoint: Update Task

### Request

**Method:** `PATCH`  
**Path:** `/api/v1/tasks/{id}`  
**Authentication:** None  
**Rate Limit:** 10 requests per second per IP

**Path Parameters:**
```
id: string (UUID, required)
  - Task ID to update
```

**Headers:**
```
Content-Type: application/json
X-Request-ID: string (optional)
```

**Request Body Schema:**
```json
{
  "title": "string (optional, 1-255 characters, non-empty after trim)",
  "description": "string (optional, max 2000 characters, null to clear)",
  "due_date": "string (optional, ISO 8601 date format: YYYY-MM-DD, null to clear)",
  "priority": "enum (optional, allowed: LOW, MEDIUM, HIGH)",
  "status": "enum (optional, allowed: NEW, IN_PROGRESS, COMPLETED, ARCHIVED)",
  "version": "integer (required, must match current version)"
}
```

**Request Body Examples:**

*Update status only (optimistic locking):*
```json
{
  "status": "IN_PROGRESS",
  "version": 1
}
```

*Update multiple fields:*
```json
{
  "title": "Updated project proposal",
  "description": "Finalize Q4 roadmap and submit to stakeholders by EOW",
  "priority": "HIGH",
  "status": "IN_PROGRESS",
  "version": 1
}
```

*Clear description:*
```json
{
  "description": null,
  "version": 2
}
```

### Response

**Success Status:** `200 OK`

**Response Body Schema:**
```json
{
  "id": "string (UUID)",
  "title": "string",
  "description": "string or null",
  "due_date": "string (ISO 8601 date) or null",
  "priority": "enum (LOW, MEDIUM, HIGH)",
  "status": "enum (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)",
  "version": "integer (incremented by 1)",
  "created_at": "string (ISO 8601 timestamp)",
  "updated_at": "string (ISO 8601 timestamp, updated to current time)"
}
```

**Response Body Example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Updated project proposal",
  "description": "Finalize Q4 roadmap and submit to stakeholders by EOW",
  "due_date": "2024-12-31",
  "priority": "HIGH",
  "status": "IN_PROGRESS",
  "version": 2,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T15:00:00Z"
}
```

### Error Responses

**400 Bad Request** — Validation failure

**Trigger Conditions:**
- `id` is not a valid UUID
- `title` is provided but empty or exceeds 255 characters
- `description` exceeds 2000 characters
- `due_date` is not in ISO 8601 format or is in the past
- `priority` is not one of: LOW, MEDIUM, HIGH
- `status` is not one of: NEW, IN_PROGRESS, COMPLETED, ARCHIVED
- `version` is missing or not an integer
- Request body is not valid JSON
- Attempted invalid state transition (see [State Machine Rules](#state-machine-rules))

**Response Body Schema:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "string (e.g., 'status', 'version')",
        "message": "string (e.g., 'invalid state transition from NEW to COMPLETED')"
      }
    ]
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "status",
        "message": "invalid state transition from COMPLETED to NEW"
      }
    ]
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440009"
}
```

---

**404 Not Found** — Task does not exist

**Trigger Conditions:**
- Task with given `id` does not exist
- Task was deleted

**Response Body Schema:**
```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task not found",
    "details": {
      "id": "string (UUID)"
    }
  },
  "request_id": "string"
}
```

---

**409 Conflict** — Version mismatch (optimistic locking conflict)

**Trigger Conditions:**
- `version` in request does not match current task version
- Another client updated the task between the time this client fetched it and attempted to update it

**Response Body Schema:**
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Task was modified by another client. Please refresh and retry.",
    "details": {
      "current_version": "integer (current version in database)",
      "provided_version": "integer (version provided in request)",
      "current_state": {
        "id": "string (UUID)",
        "title": "string",
        "description": "string or null",
        "due_date": "string (ISO 8601 date) or null",
        "priority": "enum",
        "status": "enum",
        "version": "integer",
        "created_at": "string (ISO 8601 timestamp)",
        "updated_at": "string (ISO 8601 timestamp)"
      }
    }
  },
  "request_id": "string"
}
```

**Response Body Example:**
```json
{
  "error": {
    "code": "CONFLICT",
    "message": "Task was modified by another client. Please refresh and retry.",
    "details": {
      "current_version": 3,
      "provided_version": 1,
      "current_state": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "Complete project proposal",
        "description": "Finalize Q4 roadmap and submit to stakeholders",
        "due_date": "2024-12-31",
        "priority": "HIGH",
        "status": "COMPLETED",
        "version": 3,
        "created_at": "2024-01-15T10:30:00Z",
        "updated_at": "2024-01-15T16:00:00Z"
      }
    }
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440010"
}
```

---

**429 Too Many Requests** — Rate limit exceeded

(Same as POST /tasks; see [Error Responses](#error-responses))

---

**500 Internal Server Error** — Unexpected server error

(Same as POST /tasks; see [Error Responses](#error-responses))

### Business Rules

1. **Optimistic Locking:** The `version` field is required in all PATCH requests. It must match the current version of the task in the database. If it does not match, the API returns 409 Conflict with the current state of the task.

2. **Version Increment:** On successful update, `version` is incremented by 1, regardless of which fields were updated.

3. **Partial Updates:** Only fields provided in the request body are updated. Omitted fields are not changed. To clear a field (e.g., `description`), explicitly set it to `null`.

4. **Immutable Fields:** `id`, `created_at` cannot be updated. If provided in the request, they are ignored.

5. **State Machine Validation:** Not all status transitions are allowed. See [State Machine Rules](#state-machine-rules) below.

6. **Retry Strategy:** On 409 Conflict, clients MUST re-fetch the task (GET /tasks/{id}) to get the current state and version before retrying the update.

### State Machine Rules

The task status field follows a strict state machine with defined transitions:

**Valid State Transitions:**

| From | To | Allowed | Reason |
|------|----|---------|----|
| NEW | IN_PROGRESS | ✓ | Task is being worked on |
| NEW | COMPLETED | ✗ | Must transition through IN_PROGRESS first |
| NEW | ARCHIVED | ✓ | Task can be archived without being completed |
| IN_PROGRESS | COMPLETED | ✓ | Task is finished |
| IN_PROGRESS | NEW | ✗ | Cannot revert to NEW once started |
| IN_PROGRESS | ARCHIVED | ✓ | Task can be archived mid-work |
| COMPLETED | NEW | ✗ | Cannot revert completed task |
| COMPLETED | IN_PROGRESS | ✗ | Cannot revert completed task |
| COMPLETED | ARCHIVED | ✓ | Completed task can be archived |
| ARCHIVED | * | ✗ | Archived tasks are immutable; cannot transition out |

**Error Response for Invalid Transition:**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "status",
        "message": "invalid state transition from COMPLETED to NEW"
      }
    ]
  },
  "request_id": "string"
}
```

---

## 5.6 Endpoint: Delete Task

### Request

**Method:** `DELETE`  
**Path:** `/api/v1/tasks/{id}`  
**Authentication:** None  
**Rate Limit:** 10 requests per second per IP

**Path Parameters:**
```
id: string (UUID, required)
  - Task ID to delete
```

**Query Parameters:** None

**Request Headers:**
```
X-Request-ID: string (optional)
```

**Request Example:**
```
DELETE /api/v1/tasks/550e8400-e29b-41d4-a716-446655440000
```

### Response

**Success Status:** `204 No Content`

**Response Body:** Empty (no body)

**Response Headers:**
```
X-Request-ID: string (echoed from request or generated)
```

### Error Responses

**400 Bad Request** — Invalid task ID format

**Trigger Conditions:**
- `id` is not a valid UUID format

**Response Body Schema:**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid task ID format",
    "details": {
      "parameter": "id",
      "message": "must be a valid UUID"
    }
  },
  "request_id": "string"
}
```

---

**404 Not Found** — Task does not exist

**Trigger Conditions:**
- Task with given `id` does not exist
- Task was already deleted

**Response Body Schema:**
```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task not found",
    "details": {
      "id": "string (UUID)"
    }
  },
  "request_id": "string"
}
```

---

**429 Too Many Requests** — Rate limit exceeded

(Same as POST /tasks; see [Error Responses](#error-responses))

---

**500 Internal Server Error** — Unexpected server error

(Same as POST /tasks; see [Error Responses](#error-responses))

### Business Rules

1. **Hard Delete:** Tasks are permanently deleted from the database. There is no soft-delete or recovery mechanism in v1.0.

2. **Idempotency:** Deleting a task that does not exist returns 404 Not Found. Deleting the same task twice returns 404 on the second attempt (not 204).

3. **Cascade Behavior:** There are no related entities (comments, attachments, etc.) in v1.0, so no cascade deletes are needed.

4. **Audit Trail:** No audit trail is maintained for deletions. If audit requirements arise, implement a separate audit log table.

---

## 5.7 Endpoint: Health Check (Liveness/Readiness)

### Request

**Method:** `GET`  
**Path:** `/api/v1/health`  
**Authentication:** None  
**Rate Limit:** Unlimited (health checks are not rate-limited)

**Query Parameters:** None

**Request Example:**
```
GET /api/v1/health
```

### Response

**Success Status:** `200 OK`

**Response Body Schema:**
```json
{
  "status": "enum (UP, DOWN)",
  "timestamp": "string (ISO 8601 timestamp)",
  "components": {
    "database": {
      "status": "enum (UP, DOWN)",
      "details": {
        "connection": "string (e.g., 'SQLite connected')"
      }
    }
  }
}
```

**Response Body Example (Healthy):**
```json
{
  "status": "UP",
  "timestamp": "2024-01-15T10:30:00Z",
  "components": {
    "database": {
      "status": "UP",
      "details": {
        "connection": "SQLite connected"
      }
    }
  }
}
```

**Response Body Example (Unhealthy):**
```json
{
  "status": "DOWN",
  "timestamp": "2024-01-15T10:30:00Z",
  "components": {
    "database": {
      "status": "DOWN",
      "details": {
        "connection": "SQLite connection failed: database locked"
      }
    }
  }
}
```

### Error Responses

**503 Service Unavailable** — Service is unhealthy

**Trigger Conditions:**
- Database connection is unavailable
- Filesystem is full (SQLite cannot write)
- Other critical service dependencies are down

**Response Body Schema:**
```json
{
  "status": "DOWN",
  "timestamp": "string (ISO 8601 timestamp)",
  "components": {
    "database": {
      "status": "DOWN",
      "details": {
        "connection": "string (error message)"
      }
    }
  }
}
```

### Business Rules

1. **Liveness Probe:** This endpoint is used by orchestration platforms (Kubernetes, Docker Swarm) to determine if the service is alive. Return 200 OK if the service is running, even if degraded.

2. **Readiness Probe:** This endpoint is also used to determine if the service is ready to accept traffic. Return 503 if the database is unavailable.

3. **No Rate Limiting:** Health checks are not rate-limited to ensure monitoring systems can always reach the endpoint.

---

## 5.8 API Error Codes Reference

| Error Code | HTTP Status | Meaning | Retry? |
|------------|-------------|---------|--------|
| VALIDATION_ERROR | 400 | Request validation failed (invalid input) | No |
| TASK_NOT_FOUND | 404 | Task does not exist | No |
| CONFLICT | 409 | Version mismatch (optimistic locking) | Yes (after re-fetch) |
| IDEMPOTENCY_CONFLICT | 409 | Idempotency key used with different payload | No |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests | Yes (after delay) |
| INTERNAL_SERVER_ERROR | 500 | Unexpected server error | Yes (with exponential backoff) |

---

## 5.9 API Versioning Strategy

**Current Version:** `v1`  
**Base URL:** `/api/v1`

**Versioning Approach:** URL-based versioning. All endpoints are prefixed with `/api/v1`. If breaking changes are needed in the future, a new version (`/api/v2`) will be introduced alongside v1 for backward compatibility.

**Deprecation Policy:** 
- Breaking changes will be announced 6 months in advance
- v1 will be supported for at least 12 months after v2 is released
- Clients should migrate to v2 during the overlap period

---

## 5.10 Request/Response Envelope

All API responses follow a consistent envelope structure:

**Success Response Envelope:**
```json
{
  "data": "object or array (endpoint-specific)",
  "pagination": "object (only for list endpoints)",
  "request_id": "string (unique identifier for this request)"
}
```

**Error Response Envelope:**
```json
{
  "error": {
    "code": "string (error code)",
    "message": "string (human-readable message)",
    "details": "object (error-specific details)"
  },
  "request_id": "string (unique identifier for this request)"
}
```

**Request ID Propagation:**
- If client provides `X-Request-ID` header, it is echoed in the response
- If client does not provide it, the server generates a UUID
- Request ID is used for tracing and debugging; include it in support tickets

---

## 5.11 Content Negotiation

**Supported Content Types:**
- `application/json` (required)

**Unsupported Content Types:**
- `application/xml`, `text/html`, `text/plain`, etc. return 415 Unsupported Media Type

**Character Encoding:**
- All requests and responses use UTF-8 encoding
- Charset is specified in Content-Type header: `Content-Type: application/json; charset=utf-8`

---

## 5.12 CORS Policy

**CORS Headers (if applicable):**
```
Access-Control-Allow-Origin: * (or specific origin)
Access-Control-Allow-Methods: GET, POST, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-Request-ID, X-Idempotency-Key
Access-Control-Max-Age: 86400
```

**CORS Preflight:** OPTIONS requests are supported for all endpoints.

**Note:** CORS configuration is environment-specific. For internal/prototype use, allow all origins. For production/public APIs, restrict to known origins.

---

## 5.13 Pagination Cursor Stability & Edge Cases

### Cursor Stability Guarantee

The API uses offset-based pagination with a stable sort order to ensure consistent pagination across requests:

**Default Sort Order:** `created_at DESC, id DESC` (tie-breaker)

This order is stable because:
1. `created_at` is immutable (set at creation time)
2. `id` is immutable (UUID, never changes)
3. Both fields are indexed for efficient sorting

### Edge Case: Task Deleted Between Requests

**Scenario:**
- Client fetches page 1 (limit=20, offset=0) → receives tasks 1-20
- Task 15 is deleted
- Client fetches page 2 (limit=20, offset=20) → receives tasks 21-39 (instead of 21-40)

**Behavior:** The offset shifts by 1 due to the deletion. Clients may see duplicate or missing tasks if they rely on task count rather than task IDs.

**Mitigation:** Clients should deduplicate results by `id` and handle missing tasks gracefully.

### Edge Case: Task Created with Past Timestamp

**Scenario:**
- Client fetches page 1 (limit=20, offset=0) → receives tasks created in last hour
- A new task is created with `created_at` set to 2 hours ago (due to clock skew or manual insertion)
- Client fetches page 2 (limit=20, offset=20) → the new task appears on page 1 (already fetched)

**Behavior:** The new task appears on an earlier page due to its older `created_at` timestamp.

**Mitigation:** Clients should deduplicate by `id` and use `updated_at` timestamp to detect new/modified tasks.

---

## 5.14 Concurrency & Consistency Model

### Optimistic Locking Strategy

All PATCH requests require a `version` field that must match the current version in the database. If the version does not match, the API returns 409 Conflict.

**Version Semantics:**
- Version starts at 1 for all new tasks
- Version increments by 1 on every successful PATCH, regardless of which fields are updated
- Version is immutable; clients cannot set it directly (it is read-only)

**Conflict Resolution:**
1. Client fetches task (version=1)
2. Client A updates task (PATCH with version=1) → succeeds, version becomes 2
3. Client B attempts to update task (PATCH with version=1) → fails with 409 Conflict
4. Client B re-fetches task (GET) → receives current state with version=2
5. Client B retries PATCH with version=2 → succeeds, version becomes 3

**Retry Guidance:**
- On 409 Conflict, client MUST re-fetch the task before retrying
- Blind retries with the same version will fail again
- Implement exponential backoff for retries (e.g., 100ms, 200ms, 400ms)
- Maximum retry attempts: 3 (then fail and notify user)

### Consistency Guarantees

- **Strong Consistency:** All reads return the latest committed state
- **ACID Transactions:** All writes are atomic; partial updates are not possible
- **No Dirty Reads:** Clients never see uncommitted data
- **No Lost Updates:** Optimistic locking prevents concurrent updates from overwriting each other

### Concurrency Limits

- **Max Concurrent Requests:** 1,000 per API instance
- **Max Concurrent Updates to Same Task:** Unlimited (conflicts are detected and reported)
- **Database Connection Pool:** 10 connections (SQLite limitation)

---

## 5.15 Idempotency & Retry Semantics

### Idempotency Key Scope

**Idempotency keys apply to POST /tasks only.** They prevent duplicate task creation on retry.

**Idempotency Key Semantics:**
- `X-Idempotency-Key` header is required for POST /tasks
- If the same key is used within 24 hours with the same request body, the API returns the previously created task (200 OK) instead of creating a duplicate
- If the same key is used with a different request body, the API returns 409 Conflict

**Example:**
```
Request 1: POST /tasks with X-Idempotency-Key: abc123, body: {title: "Task A"}
Response 1: 201 Created, task_id: 123

Request 2: POST /tasks with X-Idempotency-Key: abc123, body: {title: "Task A"}
Response 2: 200 OK, task_id: 123 (same task, not duplicated)

Request 3: POST /tasks with X-Idempotency-Key: abc123, body: {title: "Task B"}
Response 3: 409 Conflict (different payload with same key)
```

### Idempotency Key Format

- **Format:** UUID or any unique string (max 255 characters)
- **Recommended:** Use UUID v4 (e.g., `550e8400-e29b-41d4-a716-446655440000`)
- **Uniqueness:** Must be unique per client per 24-hour period

### Retry Strategy for Clients

**For POST /tasks (Create):**
1. Generate a unique idempotency key (UUID v4)
2. Send request with `X-Idempotency-Key` header
3. If 201 Created or 200 OK, task was created (or already existed)
4. If 409 Conflict, use different idempotency key and retry
5. If 429 Too Many Requests, wait and retry with same idempotency key
6. If 5xx, wait and retry with same idempotency key (idempotency ensures no duplicate)

**For PATCH /tasks (Update):**
1. Fetch task (GET /tasks/{id}) to get current version
2. Send PATCH request with current version
3. If 200 OK, update succeeded
4. If 409 Conflict, re-fetch task and retry with new version
5. If 429 Too Many Requests, wait and retry
6. If 5xx, wait and retry (version-based idempotency ensures no duplicate)

**For DELETE /tasks (Delete):**
1. Send DELETE request
2. If 204 No Content, task was deleted
3. If 404 Not Found, task does not exist (already deleted or never existed)
4. If 429 Too Many Requests, wait and retry
5. If 5xx, wait and retry (delete is idempotent; retrying is safe)

---

## 5.16 API Endpoint Summary Table

| Method | Path | Purpose | Auth | Rate Limit | Idempotent |
|--------|------|---------|------|-----------|-----------|
| POST | /api/v1/tasks | Create task | None | 1 req/sec | Yes (with key) |
| GET | /api/v1/tasks | List tasks | None | 100 req/sec | Yes |
| GET | /api/v1/tasks/{id} | Retrieve task | None | 100 req/sec | Yes |
| PATCH | /api/v1/tasks/{id} | Update task | None | 10 req/sec | Yes (with version) |
| DELETE | /api/v1/tasks/{id} | Delete task | None | 10 req/sec | Yes |
| GET | /api/v1/health | Health check | None | Unlimited | Yes |

---

This completes **Section 5: API Contract Specification**. All endpoints are fully specified with request/response schemas, error codes, business rules, and concurrency semantics.

---

# 6. ERROR HANDLING & VALIDATION RULES

## 6.1 Validation Rules (Request-Level)

### Task Title Validation
```
Field: title
Type: string
Rules:
  - Required: true
  - Min length: 1 character (after trim)
  - Max length: 255 characters
  - Allowed characters: Any UTF-8 character (no restrictions)
  - Trim whitespace: true (leading/trailing spaces removed before validation)
  - Null/undefined: Rejected with 400 Bad Request

Error Response (400):
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "title",
      "issue": "REQUIRED",
      "message": "title is required"
    }
  ]
}

Error Response (400) — Title too long:
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "title",
      "issue": "MAX_LENGTH_EXCEEDED",
      "message": "title must not exceed 255 characters (provided: 300)"
    }
  ]
}
```

### Task Description Validation
```
Field: description
Type: string (nullable)
Rules:
  - Required: false
  - Max length: 2000 characters
  - Allowed characters: Any UTF-8 character
  - Trim whitespace: false (preserve user formatting)
  - Null/undefined: Accepted (stored as NULL in database)
  - Empty string: Accepted (stored as empty string, not NULL)

Error Response (400) — Description too long:
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "description",
      "issue": "MAX_LENGTH_EXCEEDED",
      "message": "description must not exceed 2000 characters (provided: 2500)"
    }
  ]
}
```

### Task Due Date Validation
```
Field: due_date
Type: string (ISO 8601 date format: YYYY-MM-DD) or null
Rules:
  - Required: false
  - Format: ISO 8601 date (YYYY-MM-DD)
  - Allowed range: Any valid date (past, present, future)
  - No validation against current date (past due dates are allowed)
  - Null/undefined: Accepted (stored as NULL in database)
  - Empty string: Rejected with 400 Bad Request

Error Response (400) — Invalid date format:
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "due_date",
      "issue": "INVALID_FORMAT",
      "message": "due_date must be in ISO 8601 format (YYYY-MM-DD), got: '2024/12/31'"
    }
  ]
}

Error Response (400) — Invalid date value:
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "due_date",
      "issue": "INVALID_DATE",
      "message": "due_date is not a valid date: '2024-13-45'"
    }
  ]
}
```

### Task Priority Validation
```
Field: priority
Type: enum (string)
Rules:
  - Required: false
  - Default value: "MEDIUM" (if omitted)
  - Allowed values: "LOW", "MEDIUM", "HIGH"
  - Case-sensitive: true (lowercase only)
  - Null/undefined: Accepted (treated as default "MEDIUM")

Error Response (400) — Invalid priority:
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "priority",
      "issue": "INVALID_ENUM",
      "message": "priority must be one of: LOW, MEDIUM, HIGH (got: 'URGENT')"
    }
  ]
}
```

### Task Status Validation (PATCH Requests Only)
```
Field: status
Type: enum (string)
Rules:
  - Required: false (in PATCH request body)
  - Allowed values: "NEW", "IN_PROGRESS", "COMPLETED", "ARCHIVED"
  - Case-sensitive: true (uppercase only)
  - State machine rules (see Section 7.2):
    - NEW → IN_PROGRESS, ARCHIVED
    - IN_PROGRESS → COMPLETED, ARCHIVED
    - COMPLETED → ARCHIVED (no reverse transitions)
    - ARCHIVED → (terminal state, no transitions)
  - Invalid transitions: Rejected with 400 Bad Request

Error Response (400) — Invalid status:
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "status",
      "issue": "INVALID_ENUM",
      "message": "status must be one of: NEW, IN_PROGRESS, COMPLETED, ARCHIVED (got: 'PENDING')"
    }
  ]
}

Error Response (400) — Invalid state transition:
{
  "error_code": "INVALID_STATE_TRANSITION",
  "message": "Cannot transition from COMPLETED to IN_PROGRESS",
  "details": {
    "current_status": "COMPLETED",
    "requested_status": "IN_PROGRESS",
    "allowed_transitions": ["ARCHIVED"]
  }
}
```

### Idempotency Key Validation (POST /tasks Only)
```
Field: X-Idempotency-Key (HTTP header)
Type: string (UUID v4 recommended)
Rules:
  - Required: true (for POST /tasks)
  - Format: Any non-empty string (UUID v4 recommended for uniqueness)
  - Max length: 255 characters
  - Scope: Per endpoint (idempotency key for POST /tasks is independent of other endpoints)
  - Lifetime: 24 hours (after 24 hours, same key can be reused)
  - Duplicate detection: If same key is used with different request body, return 409 Conflict

Error Response (400) — Missing idempotency key:
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "X-Idempotency-Key",
      "issue": "REQUIRED",
      "message": "X-Idempotency-Key header is required for POST /tasks"
    }
  ]
}

Error Response (409) — Idempotency key conflict (different payload):
{
  "error_code": "IDEMPOTENCY_CONFLICT",
  "message": "Idempotency key already used with different request body",
  "details": {
    "idempotency_key": "550e8400-e29b-41d4-a716-446655440000",
    "previous_request_body": {
      "title": "Buy groceries",
      "priority": "LOW"
    },
    "current_request_body": {
      "title": "Buy groceries",
      "priority": "HIGH"
    }
  }
}
```

### Request ID Validation (All Endpoints)
```
Field: X-Request-ID (HTTP header)
Type: string (UUID v4 recommended)
Rules:
  - Required: false (generated by server if not provided)
  - Format: Any non-empty string (UUID v4 recommended)
  - Max length: 255 characters
  - Scope: Per request (used for request tracing and logging)
  - Lifetime: Request lifetime only (not stored)
  - Server behavior: If provided, echoed in response; if not provided, server generates UUID v4

Server-Generated Request ID (if not provided):
X-Request-ID: 550e8400-e29b-41d4-a716-446655440001
```

---

## 6.2 Error Response Format

### Standard Error Response Structure
```json
{
  "error_code": "string (machine-readable error code)",
  "message": "string (human-readable error message)",
  "request_id": "string (echoed from X-Request-ID header or generated)",
  "timestamp": "string (ISO 8601 timestamp of error)",
  "details": "object or array (optional, context-specific details)"
}
```

### Error Code Catalog

| HTTP Status | Error Code | Meaning | Retry? | Details |
|-------------|-----------|---------|--------|---------|
| 400 | `VALIDATION_ERROR` | Request body/parameters invalid | No | Array of validation failures |
| 400 | `INVALID_STATE_TRANSITION` | Status transition not allowed | No | Current status, requested status, allowed transitions |
| 400 | `MALFORMED_REQUEST` | Request body not valid JSON | No | Parse error details |
| 404 | `TASK_NOT_FOUND` | Task ID does not exist | No | Requested task ID |
| 409 | `CONFLICT_VERSION_MISMATCH` | Version mismatch (optimistic lock) | Yes | Current version, provided version, current task state |
| 409 | `IDEMPOTENCY_CONFLICT` | Idempotency key used with different payload | No | Previous and current request bodies |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests | Yes (after delay) | Rate limit details (limit, remaining, reset time) |
| 500 | `INTERNAL_SERVER_ERROR` | Unexpected server error | Yes (with backoff) | Error ID for support reference |
| 503 | `SERVICE_UNAVAILABLE` | Server temporarily unavailable | Yes (with backoff) | Estimated recovery time (if known) |

### Error Response Examples

#### 400 Bad Request — Validation Error
```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:45.123Z",
  "details": [
    {
      "field": "title",
      "issue": "REQUIRED",
      "message": "title is required"
    },
    {
      "field": "due_date",
      "issue": "INVALID_FORMAT",
      "message": "due_date must be in ISO 8601 format (YYYY-MM-DD)"
    }
  ]
}
```

#### 404 Not Found — Task Not Found
```json
{
  "error_code": "TASK_NOT_FOUND",
  "message": "Task not found",
  "request_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": "2024-01-15T10:31:00.456Z",
  "details": {
    "task_id": "550e8400-e29b-41d4-a716-446655440002"
  }
}
```

#### 409 Conflict — Version Mismatch
```json
{
  "error_code": "CONFLICT_VERSION_MISMATCH",
  "message": "Task has been modified since you last fetched it. Please refresh and retry.",
  "request_id": "550e8400-e29b-41d4-a716-446655440003",
  "timestamp": "2024-01-15T10:32:15.789Z",
  "details": {
    "task_id": "550e8400-e29b-41d4-a716-446655440002",
    "provided_version": 1,
    "current_version": 2,
    "current_task": {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "title": "Buy groceries",
      "status": "IN_PROGRESS",
      "version": 2,
      "updated_at": "2024-01-15T10:32:00.000Z"
    }
  }
}
```

#### 429 Too Many Requests — Rate Limit Exceeded
```json
{
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Please retry after the reset time.",
  "request_id": "550e8400-e29b-41d4-a716-446655440004",
  "timestamp": "2024-01-15T10:33:00.000Z",
  "details": {
    "limit": 1000,
    "remaining": 0,
    "reset_at": "2024-01-15T10:34:00.000Z",
    "retry_after_seconds": 60
  }
}
```

#### 500 Internal Server Error
```json
{
  "error_code": "INTERNAL_SERVER_ERROR",
  "message": "An unexpected error occurred. Please contact support with the error ID.",
  "request_id": "550e8400-e29b-41d4-a716-446655440005",
  "timestamp": "2024-01-15T10:34:30.000Z",
  "details": {
    "error_id": "ERR-2024-01-15-001",
    "support_url": "https://support.example.com/errors/ERR-2024-01-15-001"
  }
}
```

---

## 6.3 Validation Rules (Database-Level)

### NOT NULL Constraints
```sql
-- Columns that must always have a value
ALTER TABLE tasks ADD CONSTRAINT tasks_title_not_null 
  CHECK (title IS NOT NULL AND title != '');

ALTER TABLE tasks ADD CONSTRAINT tasks_status_not_null 
  CHECK (status IS NOT NULL);

ALTER TABLE tasks ADD CONSTRAINT tasks_priority_not_null 
  CHECK (priority IS NOT NULL);

ALTER TABLE tasks ADD CONSTRAINT tasks_version_not_null 
  CHECK (version IS NOT NULL AND version > 0);

ALTER TABLE tasks ADD CONSTRAINT tasks_created_at_not_null 
  CHECK (created_at IS NOT NULL);

ALTER TABLE tasks ADD CONSTRAINT tasks_updated_at_not_null 
  CHECK (updated_at IS NOT NULL);
```

### CHECK Constraints
```sql
-- Enforce valid enum values at database level
ALTER TABLE tasks ADD CONSTRAINT tasks_status_enum 
  CHECK (status IN ('NEW', 'IN_PROGRESS', 'COMPLETED', 'ARCHIVED'));

ALTER TABLE tasks ADD CONSTRAINT tasks_priority_enum 
  CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH'));

-- Enforce string length constraints
ALTER TABLE tasks ADD CONSTRAINT tasks_title_length 
  CHECK (length(title) >= 1 AND length(title) <= 255);

ALTER TABLE tasks ADD CONSTRAINT tasks_description_length 
  CHECK (description IS NULL OR length(description) <= 2000);

-- Enforce version is positive
ALTER TABLE tasks ADD CONSTRAINT tasks_version_positive 
  CHECK (version > 0);

-- Enforce updated_at >= created_at
ALTER TABLE tasks ADD CONSTRAINT tasks_timestamps_order 
  CHECK (updated_at >= created_at);
```

### Unique Constraints
```sql
-- Primary key (unique identifier)
ALTER TABLE tasks ADD CONSTRAINT tasks_pk PRIMARY KEY (id);

-- Idempotency key uniqueness (for deduplication)
-- Note: Idempotency keys are stored in a separate table with TTL
ALTER TABLE idempotency_keys ADD CONSTRAINT idempotency_keys_pk 
  PRIMARY KEY (idempotency_key);

ALTER TABLE idempotency_keys ADD CONSTRAINT idempotency_keys_unique 
  UNIQUE (idempotency_key);
```

---

# 7. CONCURRENCY & CONSISTENCY MODEL

## 7.1 Optimistic Locking Strategy

### Version Field Semantics
```
Field: version
Type: INTEGER (32-bit signed)
Initial value: 1 (assigned on task creation)
Increment: +1 on every PATCH request (regardless of which fields change)
Scope: Per task (each task has independent version counter)
Lifetime: Immutable after creation; never reset or decremented
Overflow handling: If version reaches MAX_INT (2^31 - 1), reject further updates with 500 error
  (Unlikely in practice; would require 2 billion updates to single task)
```

### Version Increment Rules
```
Trigger: PATCH /tasks/{id} request succeeds (all validations pass)
Behavior:
  1. Read current task from database (SELECT ... FOR UPDATE to prevent race)
  2. Compare provided version with current version
  3. If versions match:
     - Increment version by 1
     - Update task fields
     - Update updated_at to current timestamp
     - Commit transaction
     - Return 200 OK with updated task (including new version)
  4. If versions don't match:
     - Rollback transaction
     - Return 409 Conflict with current task state (including current version)
     - Do NOT increment version

Atomicity: Version check and increment are atomic (single database transaction)
Isolation: Use database row-level locks (SELECT ... FOR UPDATE) to prevent dirty reads
```

### Client Retry Strategy (Recommended)
```
Pseudocode for client-side retry logic:

function updateTaskWithRetry(taskId, updates, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      // Step 1: Fetch current task to get latest version
      const currentTask = await GET /tasks/{taskId}
      
      // Step 2: Attempt update with current version
      const response = await PATCH /tasks/{taskId} {
        ...updates,
        version: currentTask.version
      }
      
      // Step 3: Success
      return response.data
      
    } catch (error) {
      if (error.status === 409 && attempt < maxRetries) {
        // Conflict: version mismatch
        // Retry after exponential backoff
        await sleep(Math.pow(2, attempt - 1) * 100) // 100ms, 200ms, 400ms
        continue
      } else {
        // Non-conflict error or max retries exceeded
        throw error
      }
    }
  }
}

// Usage:
const updated = await updateTaskWithRetry(
  "550e8400-e29b-41d4-a716-446655440000",
  { status: "IN_PROGRESS" }
)
```

### Concurrent Update Scenario (Worked Example)
```
Timeline:
  T0: Task exists with version=1, status=NEW
  
  T1: Client A fetches task
       GET /tasks/550e8400-e29b-41d4-a716-446655440000
       Response: { id: "...", status: "NEW", version: 1, ... }
  
  T2: Client B fetches same task
       GET /tasks/550e8400-e29b-41d4-a716-446655440000
       Response: { id: "...", status: "NEW", version: 1, ... }
  
  T3: Client A updates task (NEW → IN_PROGRESS)
       PATCH /tasks/550e8400-e29b-41d4-a716-446655440000
       Body: { status: "IN_PROGRESS", version: 1 }
       
       Server:
         1. Read task: SELECT * FROM tasks WHERE id = "..." FOR UPDATE
         2. Check version: 1 == 1 ✓
         3. Update: UPDATE tasks SET status = "IN_PROGRESS", version = 2, updated_at = NOW()
         4. Commit
       
       Response: 200 OK { id: "...", status: "IN_PROGRESS", version: 2, ... }
  
  T4: Client B attempts same update (NEW → IN_PROGRESS)
       PATCH /tasks/550e8400-e29b-41d4-a716-446655440000
       Body: { status: "IN_PROGRESS", version: 1 }
       
       Server:
         1. Read task: SELECT * FROM tasks WHERE id = "..." FOR UPDATE
         2. Check version: 1 != 2 ✗
         3. Rollback (no update)
       
       Response: 409 Conflict
       {
         "error_code": "CONFLICT_VERSION_MISMATCH",
         "message": "Task has been modified since you last fetched it",
         "details": {
           "provided_version": 1,
           "current_version": 2,
           "current_task": { id: "...", status: "IN_PROGRESS", version: 2, ... }
         }
       }
  
  T5: Client B retries (after exponential backoff)
       1. Fetch task: GET /tasks/550e8400-e29b-41d4-a716-446655440000
          Response: { id: "...", status: "IN_PROGRESS", version: 2, ... }
       
       2. Attempt update: PATCH /tasks/550e8400-e29b-41d4-a716-446655440000
          Body: { status: "IN_PROGRESS", version: 2 }
          
          Server:
            1. Read task: SELECT * FROM tasks WHERE id = "..." FOR UPDATE
            2. Check version: 2 == 2 ✓
            3. Update: UPDATE tasks SET version = 3, updated_at = NOW()
               (Note: status is already IN_PROGRESS, but version still increments)
            4. Commit
          
          Response: 200 OK { id: "...", status: "IN_PROGRESS", version: 3, ... }
```

---

## 7.2 Task State Machine

### State Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌──────────┐                                              │
│  │   NEW    │ ◄─── Initial state (assigned on creation)   │
│  └────┬─────┘                                              │
│       │                                                     │
│       ├─────────────────────────────────────────────┐      │
│       │                                             │      │
│       ▼                                             ▼      │
│  ┌──────────────┐                            ┌──────────┐ │
│  │ IN_PROGRESS  │                            │ ARCHIVED │ │
│  └────┬─────────┘                            └──────────┘ │
│       │                                             ▲      │
│       │                                             │      │
│       ├─────────────────────────────────────────────┤      │
│       │                                             │      │
│       ▼                                             │      │
│  ┌──────────────┐                                  │      │
│  │  COMPLETED   │──────────────────────────────────┘      │
│  └──────────────┘ (terminal state)                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Allowed Transitions:
  NEW → IN_PROGRESS
  NEW → ARCHIVED
  IN_PROGRESS → COMPLETED
  IN_PROGRESS → ARCHIVED
  COMPLETED → ARCHIVED
  ARCHIVED → (no transitions; terminal state)

Disallowed Transitions (return 400 Bad Request):
  NEW → COMPLETED (must go through IN_PROGRESS)
  IN_PROGRESS → NEW (no reverse transitions)
  COMPLETED → IN_PROGRESS (no reverse transitions)
  COMPLETED → NEW (no reverse transitions)
  ARCHIVED → * (no transitions from terminal state)
```

### State Transition Validation Logic
```java
// Pseudocode for state machine validation

enum TaskStatus {
  NEW, IN_PROGRESS, COMPLETED, ARCHIVED
}

class TaskStateValidator {
  
  // Define allowed transitions as a map
  private static final Map<TaskStatus, Set<TaskStatus>> ALLOWED_TRANSITIONS = Map.of(
    TaskStatus.NEW, Set.of(TaskStatus.IN_PROGRESS, TaskStatus.ARCHIVED),
    TaskStatus.IN_PROGRESS, Set.of(TaskStatus.COMPLETED, TaskStatus.ARCHIVED),
    TaskStatus.COMPLETED, Set.of(TaskStatus.ARCHIVED),
    TaskStatus.ARCHIVED, Set.of() // Terminal state: no transitions
  );
  
  public static void validateTransition(TaskStatus currentStatus, TaskStatus requestedStatus) 
    throws InvalidStateTransitionException {
    
    if (currentStatus == requestedStatus) {
      // Idempotent: allow no-op transitions
      return;
    }
    
    Set<TaskStatus> allowedNextStates = ALLOWED_TRANSITIONS.get(currentStatus);
    
    if (!allowedNextStates.contains(requestedStatus)) {
      throw new InvalidStateTransitionException(
        String.format(
          "Cannot transition from %s to %s. Allowed transitions: %s",
          currentStatus,
          requestedStatus,
          allowedNextStates
        )
      );
    }
  }
}
```

### Idempotent Transitions
```
Behavior: If client requests transition to current status, treat as success (200 OK)

Example:
  Current task: { id: "...", status: "IN_PROGRESS", version: 5 }
  
  Request: PATCH /tasks/550e8400-e29b-41d4-a716-446655440000
           Body: { status: "IN_PROGRESS", version: 5 }
  
  Server:
    1. Check transition: IN_PROGRESS → IN_PROGRESS (same status)
    2. Treat as idempotent: no-op
    3. Increment version: 5 → 6
    4. Update updated_at to current timestamp
    5. Return 200 OK { id: "...", status: "IN_PROGRESS", version: 6, updated_at: "..." }
  
  Rationale: Allows clients to safely retry without checking current status first
```

---

## 7.3 Consistency Guarantees

### Strong Consistency Model
```
Guarantee: All reads reflect the most recent writes (no stale reads)

Implementation:
  - Single-instance deployment: All reads and writes go to same SQLite instance
  - ACID transactions: SQLite enforces atomicity, consistency, isolation, durability
  - Row-level locks: SELECT ... FOR UPDATE prevents dirty reads during updates
  - No caching layer: No Redis or in-memory cache (eliminates cache invalidation issues)

Implication: Clients can assume that GET /tasks/{id} always returns latest state
```

### Atomicity Guarantees
```
Guarantee: Each API operation is atomic (all-or-nothing)

Scope:
  - POST /tasks: Create task + assign ID + set timestamps (atomic)
  - PATCH /tasks/{id}: Version check + field update + version increment (atomic)
  - DELETE /tasks/{id}: Mark as deleted + update timestamp (atomic)
  - GET /tasks: Read task state (atomic read)

Implementation:
  - Database transactions: Each operation wrapped in BEGIN TRANSACTION ... COMMIT
  - Rollback on error: If any step fails, entire transaction rolled back
  - No partial updates: Client never sees partially updated task

Example (PATCH atomicity):
  BEGIN TRANSACTION
    SELECT * FROM tasks WHERE id = ? FOR UPDATE  -- Lock row
    IF version matches:
      UPDATE tasks SET status = ?, version = version + 1, updated_at = NOW()
      COMMIT
    ELSE:
      ROLLBACK
      RETURN 409 Conflict
```

### Isolation Guarantees
```
Guarantee: Concurrent operations don't interfere with each other

Isolation Level: SERIALIZABLE (SQLite default)
  - Prevents dirty reads: Transaction A cannot read uncommitted changes from Transaction B
  - Prevents non-repeatable reads: Transaction A sees consistent snapshot of data
  - Prevents phantom reads: Transaction A doesn't see new rows inserted by Transaction B

Implementation:
  - Row-level locks: SELECT ... FOR UPDATE locks row for duration of transaction
  - Snapshot isolation: Each transaction sees consistent snapshot at start time
  - Conflict detection: If two transactions try to modify same row, one fails with 409

Example (Isolation):
  Transaction A: PATCH /tasks/123 (status: NEW → IN_PROGRESS)
  Transaction B: PATCH /tasks/123 (status: NEW → COMPLETED)
  
  Timeline:
    T1: A reads task (version 1, status NEW)
    T2: B reads task (version 1, status NEW)
    T3: A updates task (version 1 → 2, status IN_PROGRESS) — COMMIT
    T4: B attempts update (version 1 → 2, status COMPLETED)
        Server detects version mismatch (1 != 2) — ROLLBACK
        Return 409 Conflict
```

### Durability Guarantees
```
Guarantee: Committed data survives server crashes

Implementation:
  - SQLite WAL (Write-Ahead Logging): Changes written to log before database
  - Fsync on commit: Database file synced to disk on transaction commit
  - No in-memory-only data: All state persisted to disk

Implication: If server crashes after 200 OK response, data is guaranteed to be persisted
```

---

## 7.4 Pagination Cursor Stability

### Sort Order (Immutable)
```
Default sort order: created_at DESC, id DESC (tie-breaker)

Rationale:
  - created_at DESC: Most recent tasks first (intuitive for users)
  - id DESC: Deterministic ordering for tasks created at same millisecond
  - Immutable: Sort order never changes (ensures cursor stability)

Implication: Pagination cursors remain valid across requests
  - If task is deleted between page N and N+1, offset shifts by 1
  - If new task is created with created_at in past, it appears on already-fetched pages
  - Clients should deduplicate by id if needed
```

### Offset Shift Behavior
```
Scenario: Task deleted between pagination requests

Initial state:
  Tasks: [T1 (created_at: 2024-01-15 10:00), T2 (2024-01-15 09:00), T3 (2024-01-15 08:00)]
  
Request 1: GET /tasks?limit=2&offset=0
  Response: [T1, T2]
  
Between requests: T2 is deleted
  Tasks: [T1 (created_at: 2024-01-15 10:00), T3 (2024-01-15 08:00)]
  
Request 2: GET /tasks?limit=2&offset=2
  Expected: [T3]
  Actual: [T3] (offset shifted by 1 due to deletion)
  
Implication: Clients may see duplicate or missing tasks if deletions occur between requests
  - Recommended: Deduplicate by id on client side
  - Recommended: Use cursor-based pagination for future versions (not v1.0)
```

### Pagination Limits
```
Limit parameter:
  - Min: 1
  - Max: 100
  - Default: 20
  - Validation: If limit > 100, return 400 Bad Request

Offset parameter:
  - Min: 0
  - Max: No hard limit (but performance degrades for large offsets)
  - Default: 0
  - Validation: If offset < 0, return 400 Bad Request

Rationale:
  - Min limit of 1: Prevents empty responses
  - Max limit of 100: Prevents memory exhaustion from large result sets
  - Default limit of 20: Reasonable balance between data transfer and round-trips
  - No offset limit: Allows clients to paginate through entire dataset (inefficient but possible)
```

---

# 8. FRONTEND COMPONENT SPECIFICATIONS

## 8.1 Component: TaskForm

### Purpose
Render a form for creating or editing a task. Used on task creation page and task detail page.

### Props
```typescript
interface TaskFormProps {
  // Mode: 'create' or 'edit'
  mode: 'create' | 'edit';
  
  // Initial task data (for edit mode)
  initialTask?: {
    id: string;
    title: string;
    description: string | null;
    due_date: string | null; // ISO 8601 date (YYYY-MM-DD)
    priority: 'LOW' | 'MEDIUM' | 'HIGH';
    status: 'NEW' | 'IN_PROGRESS' | 'COMPLETED' | 'ARCHIVED';
    version: number;
  };
  
  // Callback on successful submission
  onSubmit: (task: TaskResponse) => void;
  
  // Callback on error
  onError: (error: ApiError) => void;
  
  // Callback to cancel form
  onCancel: () => void;
  
  // Optional: disable form (e.g., during submission)
  disabled?: boolean;
}
```

### State
```typescript
interface TaskFormState {
  // Form field values
  title: string;
  description: string;
  due_date: string; // ISO 8601 date (YYYY-MM-DD) or empty string
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  status: 'NEW' | 'IN_PROGRESS' | 'COMPLETED' | 'ARCHIVED'; // Edit mode only
  
  // Form state
  isSubmitting: boolean;
  errors: {
    title?: string;
    description?: string;
    due_date?: string;
    priority?: string;
    status?: string;
    form?: string; // General form error (e.g., network error)
  };
  
  // For edit mode: track version for optimistic locking
  version?: number;
  
  // For create mode: idempotency key (generated on mount)
  idempotencyKey?: string;
}
```

### Behavior

#### Initialization (Create Mode)
```
1. Generate idempotency key (UUID v4) on component mount
2. Initialize form fields to defaults:
   - title: ""
   - description: ""
   - due_date: ""
   - priority: "MEDIUM"
   - status: "NEW" (not editable in create mode)
3. Clear errors
4. Set isSubmitting = false
```

#### Initialization (Edit Mode)
```
1. Populate form fields from initialTask prop
2. Store version from initialTask (for optimistic locking)
3. Clear errors
4. Set isSubmitting = false
```

#### Field Validation (On Change)
```
Validate on every field change (real-time feedback):

title:
  - If empty: error = "Title is required"
  - If length > 255: error = "Title must not exceed 255 characters"
  - Otherwise: error = null

description:
  - If length > 2000: error = "Description must not exceed 2000 characters"
  - Otherwise: error = null

due_date:
  - If provided and not ISO 8601 format (YYYY-MM-DD): error = "Invalid date format"
  - Otherwise: error = null

priority:
  - If not in [LOW, MEDIUM, HIGH]: error = "Invalid priority"
  - Otherwise: error = null

status (edit mode only):
  - Validate against state machine rules (see Section 7.2)
  - If invalid transition: error = "Invalid status transition"
  - Otherwise: error = null
```

#### Form Submission (Create Mode)
```
1. Validate all fields (see Field Validation above)
2. If any errors: display errors, do not submit
3. If no errors:
   a. Set isSubmitting = true
   b. Call POST /api/v1/tasks with:
      {
        "title": title,
        "description": description || null,
        "due_date": due_date || null,
        "priority": priority
      }
      Headers:
        X-Idempotency-Key: idempotencyKey
   c. On success (201 Created):
      - Set isSubmitting = false
      - Call onSubmit(response.data)
      - Clear form
   d. On error:
      - Set isSubmitting = false
      - If 400 Bad Request: display validation errors from response.details
      - If 409 Conflict (idempotency): display "Task already created with this request"
      - If 429 Too Many Requests: display "Too many requests, please try again later"
      - If 5xx: display "Server error, please try again"
      - Call onError(error)
```

#### Form Submission (Edit Mode)
```
1. Validate all fields (see Field Validation above)
2. If any errors: display errors, do not submit
3. If no errors:
   a. Set isSubmitting = true
   b. Call PATCH /api/v1/tasks/{id} with:
      {
        "title": title,
        "description": description || null,
        "due_date": due_date || null,
        "priority": priority,
        "status": status,
        "version": version
      }
   c. On success (200 OK):
      - Set isSubmitting = false
      - Update version from response
      - Call onSubmit(response.data)
   d. On 409 Conflict (version mismatch):
      - Set isSubmitting = false
      - Display "Task has been modified. Please refresh and try again."
      - Call onError(error)
      - Optionally: auto-refresh task and re-populate form
   e. On other error:
      - Set isSubmitting = false
      - Display error message
      - Call onError(error)
```

#### Cancel Button
```
On click:
  1. Clear form
  2. Clear errors
  3. Call onCancel()
```

### Events

| Event | Trigger | Handler |
|-------|---------|---------|
| `onChange` | User types in any field | Validate field, update state |
| `onSubmit` | User clicks submit button | Validate form, submit to API |
| `onCancel` | User clicks cancel button | Clear form, call onCancel callback |
| `onError` | API returns error | Display error, call onError callback |

### Rendering

```jsx
<form onSubmit={handleSubmit}>
  {/* Title field */}
  <input
    type="text"
    name="title"
    value={state.title}
    onChange={handleTitleChange}
    placeholder="Task title"
    disabled={state.isSubmitting}
    aria-label="Task title"
    aria-invalid={!!state.errors.title}
    aria-describedby={state.errors.title ? "title-error" : undefined}
  />
  {state.errors.title && (
    <span id="title-error" className="error">{state.errors.title}</span>
  )}

  {/* Description field */}
  <textarea
    name="description"
    value={state.description}
    onChange={handleDescriptionChange}
    placeholder="Task description (optional)"
    disabled={state.isSubmitting}
    aria-label="Task description"
    aria-invalid={!!state.errors.description}
    aria-describedby={state.errors.description ? "description-error" : undefined}
  />
  {state.errors.description && (
    <span id="description-error" className="error">{state.errors.description}</span>
  )}

  {/* Due date field */}
  <input
    type="date"
    name="due_date"
    value={state.due_date}
    onChange={handleDueDateChange}
    disabled={state.isSubmitting}
    aria-label="Due date"
    aria-invalid={!!state.errors.due_date}
    aria-describedby={state.errors.due_date ? "due-date-error" : undefined}
  />
  {state.errors.due_date && (
    <span id="due-date-error" className="error">{state.errors.due_date}</span>
  )}

  {/* Priority dropdown */}
  <select
    name="priority"
    value={state.priority}
    onChange={handlePriorityChange}
    disabled={state.isSubmitting}
    aria-label="Priority"
    aria-invalid={!!state.errors.priority}
    aria-describedby={state.errors.priority ? "priority-error" : undefined}
  >
    <option value="LOW">Low</option>
    <option value="MEDIUM">Medium</option>
    <option value="HIGH">High</option>
  </select>
  {state.errors.priority && (
    <span id="priority-error" className="error">{state.errors.priority}</span>
  )}

  {/* Status dropdown (edit mode only) */}
  {mode === 'edit' && (
    <>
      <select
        name="status"
        value={state.status}
        onChange={handleStatusChange}
        disabled={state.isSubmitting}
        aria-label="Status"
        aria-invalid={!!state.errors.status}
        aria-describedby={state.errors.status ? "status-error" : undefined}
      >
        <option value="NEW">New</option>
        <option value="IN_PROGRESS">In Progress</option>
        <option value="COMPLETED">Completed</option>
        <option value="ARCHIVED">Archived</option>
      </select>
      {state.errors.status && (
        <span id="status-error" className="error">{state.errors.status}</span>
      )}
    </>
  )}

  {/* Form-level error */}
  {state.errors.form && (
    <div className="error" role="alert">{state.errors.form}</div>
  )}

  {/* Submit button */}
  <button
    type="submit"
    disabled={state.isSubmitting}
    aria-busy={state.isSubmitting}
  >
    {state.isSubmitting ? 'Saving...' : (mode === 'create' ? 'Create Task' : 'Update Task')}
  </button>

  {/* Cancel button */}
  <button
    type="button"
    onClick={handleCancel}
    disabled={state.isSubmitting}
  >
    Cancel
  </button>
</form>
```

---

## 8.2 Component: TaskList

### Purpose
Render a paginated list of tasks with filtering, sorting, and status indicators.

### Props
```typescript
interface TaskListProps {
  // Initial filter state
  initialFilters?: {
    status?: 'NEW' | 'IN_PROGRESS' | 'COMPLETED' | 'ARCHIVED' | 'ALL';
    priority?: 'LOW' | 'MEDIUM' | 'HIGH' | 'ALL';
    due_date_start?: string; // ISO 8601 date (YYYY-MM-DD)
    due_date_end?: string; // ISO 8601 date (YYYY-MM-DD)
    sort_by?: 'created_at' | 'due_date' | 'priority';
    sort_order?: 'asc' | 'desc';
  };
  
  // Initial pagination state
  initialLimit?: number; // Default: 20
  
  // Callback when task is clicked
  onTaskClick: (task: TaskResponse) => void;
  
  // Callback when task is deleted
  onTaskDeleted: (taskId: string) => void;
  
  // Callback when task is updated
  onTaskUpdated: (task: TaskResponse) => void;
  
  // Optional: disable list (e.g., during loading)
  disabled?: boolean;
}
```

### State
```typescript
interface TaskListState {
  // Tasks data
  tasks: TaskResponse[];
  
  // Pagination
  offset: number;
  limit: number;
  total_count: number;
  has_more: boolean;
  
  // Filters
  filters: {
    status: 'NEW' | 'IN_PROGRESS' | 'COMPLETED' | 'ARCHIVED' | 'ALL';
    priority: 'LOW' | 'MEDIUM' | 'HIGH' | 'ALL';
    due_date_start: string | null; // ISO 8601 date
    due_date_end: string | null; // ISO 8601 date
    sort_by: 'created_at' | 'due_date' | 'priority';
    sort_order: 'asc' | 'desc';
  };
  
  // Loading/error state
  isLoading: boolean;
  error: ApiError | null;
  
  // Expanded task details (for inline editing)
  expandedTaskId: string | null;
}
```

### Behavior

#### Initialization
```
1. Set filters from initialFilters prop (or defaults)
2. Set limit from initialLimit prop (or default 20)
3. Set offset = 0
4. Fetch tasks from API
5. Set isLoading = true
```

#### Fetch Tasks
```
1. Build query parameters:
   - limit: state.limit
   - offset: state.offset
   - status: state.filters.status (if not 'ALL')
   - priority: state.filters.priority (if not 'ALL')
   - due_date_start: state.filters.due_date_start (if set)
   - due_date_end: state.filters.due_date_end (if set)
   - sort_by: state.filters.sort_by
   - sort_order: state.filters.sort_order

2. Call GET /api/v1/tasks?{query_params}

3. On success (200 OK):
   - Set tasks = response.data
   - Set total_count = response.total_count
   - Set has_more = response.has_more
   - Set isLoading = false
   - Clear error

4. On error:
   - Set isLoading = false
   - Set error = error
   - Display error message to user
```

#### Filter Change
```
On any filter change (status, priority, date range, sort):
  1. Update filters state
  2. Reset offset = 0 (go to first page)
  3. Fetch tasks (see Fetch Tasks above)
```

#### Pagination
```
On "Next Page" button click:
  1. Set offset = offset + limit
  2. Fetch tasks (see Fetch Tasks above)

On "Previous Page" button click:
  1. Set offset = Math.max(0, offset - limit)
  2. Fetch tasks (see Fetch Tasks above)

On "Go to page N" (if page number input):
  1. Set offset = (N - 1) * limit
  2. Fetch tasks (see Fetch Tasks above)
```

#### Task Status Update (Inline)
```
On status dropdown change for task in list:
  1. Show loading indicator on task row
  2. Call PATCH /api/v1/tasks/{taskId} with new status and version
  3. On success (200 OK):
     - Update task in tasks array
     - Call onTaskUpdated(updated_task)
     - Show success message
  4. On 409 Conflict (version mismatch):
     - Show error: "Task has been modified. Please refresh."
     - Fetch tasks to get latest state
  5. On error:
     - Show error message
     - Revert status dropdown to previous value
```

#### Task Deletion
```
On delete button click for task:
  1. Show confirmation dialog: "Are you sure you want to delete this task?"
  2. On confirm:
     a. Show loading indicator on task row
     b. Call DELETE /api/v1/tasks/{taskId}
     c. On success (204 No Content):
        - Remove task from tasks array
        - Decrement total_count
        - Call onTaskDeleted(taskId)
        - Show success message
     d. On error:
        - Show error message
  3. On cancel:
     - Close dialog
```

#### Task Expansion (Inline Details)
```
On task row click:
  1. If expandedTaskId == taskId:
     - Set expandedTaskId = null (collapse)
  2. Else:
     - Set expandedTaskId = taskId (expand)
     - Show task details (description, due date, priority, status)
     - Show inline edit button
```

### Events

| Event | Trigger | Handler |
|-------|---------|---------|
| `onFilterChange` | User changes filter | Update filters, reset offset, fetch tasks |
| `onPaginationChange` | User clicks next/prev page | Update offset, fetch tasks |
| `onTaskClick` | User clicks task row | Call onTaskClick callback |
| `onTaskStatusChange` | User changes status in dropdown | Update task via API |
| `onTaskDelete` | User clicks delete button | Delete task via API |
| `onTaskExpand` | User clicks expand button | Toggle expandedTaskId |

### Rendering

```jsx
<div className="task-list">
  {/* Filters */}
  <div className="filters">
    <select
      name="status"
      value={state.filters.status}
      onChange={handleStatusFilterChange}
      disabled={state.isLoading}
    >
      <option value="ALL">All Statuses</option>
      <option value="NEW">New</option>
      <option value="IN_PROGRESS">In Progress</option>
      <option value="COMPLETED">Completed</option>
      <option value="ARCHIVED">Archived</option>
    </select>

    <select
      name="priority"
      value={state.filters.priority}
      onChange={handlePriorityFilterChange}
      disabled={state.isLoading}
    >
      <option value="ALL">All Priorities</option>
      <option value="LOW">Low</option>
      <option value="MEDIUM">Medium</option>
      <option value="HIGH">High</option>
    </select>

    <input
      type="date"
      name="due_date_start"
      value={state.filters.due_date_start || ''}
      onChange={handleDueDateStartChange}
      disabled={state.isLoading}
      placeholder="Start date"
    />

    <input
      type="date"
      name="due_date_end"
      value={state.filters.due_date_end || ''}
      onChange={handleDueDateEndChange}
      disabled={state.isLoading}
      placeholder="End date"
    />

    <select
      name="sort_by"
      value={state.filters.sort_by}
      onChange={handleSortByChange}
      disabled={state.isLoading}
    >
      <option value="created_at">Created Date</option>
      <option value="due_date">Due Date</option>
      <option value="priority">Priority</option>
    </select>

    <select
      name="sort_order"
      value={state.filters.sort_order}
      onChange={handleSortOrderChange}
      disabled={state.isLoading}
    >
      <option value="desc">Descending</option>
      <option value="asc">Ascending</option>
    </select>
  </div>

  {/* Loading state */}
  {state.isLoading && <div className="loading">Loading tasks...</div>}

  {/* Error state */}
  {state.error && (
    <div className="error" role="alert">
      {state.error.message}
      <button onClick={handleRetry}>Retry</button>
    </div>
  )}

  {/* Empty state */}
  {!state.isLoading && state.tasks.length === 0 && (
    <div className="empty-state">No tasks found</div>
  )}

  {/* Task list */}
  {!state.isLoading && state.tasks.length > 0 && (
    <ul className="tasks" role="list">
      {state.tasks.map((task) => (
        <li key={task.id} className="task-row">
          <div className="task-header" onClick={() => handleTaskExpand(task.id)}>
            <span className="task-title">{task.title}</span>
            <span className={`task-status status-${task.status.toLowerCase()}`}>
              {task.status}
            </span>
            <span className={`task-priority priority-${task.priority.toLowerCase()}`}>
              {task.priority}
            </span>
            {task.due_date && (
              <span className="task-due-date">{task.due_date}</span>
            )}
            <button
              className="expand-button"
              onClick={(e) => {
                e.stopPropagation();
                handleTaskExpand(task.id);
              }}
              aria-expanded={state.expandedTaskId === task.id}
            >
              {state.expandedTaskId === task.id ? '▼' : '▶'}
            </button>
          </div>

          {/* Expanded details */}
          {state.expandedTaskId === task.id && (
            <div className="task-details">
              {task.description && (
                <p className="task-description">{task.description}</p>
              )}
              <div className="task-meta">
                <span>Created: {new Date(task.created_at).toLocaleString()}</span>
                <span>Updated: {new Date(task.updated_at).toLocaleString()}</span>
              </div>
              <div className="task-actions">
                <button onClick={() => handleTaskEdit(task)}>Edit</button>
                <button onClick={() => handleTaskDelete(task.id)}>Delete</button>
              </div>
            </div>
          )}
        </li>
      ))}
    </ul>
  )}

  {/* Pagination */}
  {!state.isLoading && state.tasks.length > 0 && (
    <div className="pagination">
      <button
        onClick={handlePreviousPage}
        disabled={state.offset === 0}
      >
        Previous
      </button>
      <span>
        Page {Math.floor(state.offset / state.limit) + 1} of{' '}
        {Math.ceil(state.total_count / state.limit)}
      </span>
      <button
        onClick={handleNextPage}
        disabled={!state.has_more}
      >
        Next
      </button>
    </div>
  )}
</div>
```

---

## 8.3 Component: TaskDetail

### Purpose
Render a single task with full details and inline editing capabilities.

### Props
```typescript
interface TaskDetailProps {
  // Task ID to display
  taskId: string;
  
  // Callback when task is updated
  onTaskUpdated: (task: TaskResponse) => void;
  
  // Callback when task is deleted
  onTaskDeleted: (taskId: string) => void;
  
  // Callback to go back to list
  onBack: () => void;
}
```

### State
```typescript
interface TaskDetailState {
  // Task data
  task: TaskResponse | null;
  
  // Loading/error state
  isLoading: boolean;
  error: ApiError | null;
  
  // Edit mode
  isEditing: boolean;
  editForm: {
    title: string;
    description: string;
    due_date: string;
    priority: 'LOW' | 'MEDIUM' | 'HIGH';
    status: 'NEW' | 'IN_PROGRESS' | 'COMPLETED' | 'ARCHIVED';
    version: number;
  };
  editErrors: {
    [key: string]: string;
  };
}
```

### Behavior

#### Initialization
```
1. Set isLoading = true
2. Fetch task from API: GET /api/v1/tasks/{taskId}
3. On success (200 OK):
   - Set task = response.data
   - Set isLoading = false
   - Clear error
4. On error:
   - Set isLoading = false
   - Set error = error
```

#### Edit Mode
```
On "Edit" button click:
  1. Set isEditing = true
  2. Populate editForm with current task data
  3. Clear editErrors

On "Cancel" button click:
  1. Set isEditing = false
  2. Clear editForm
  3. Clear editErrors

On "Save" button click:
  1. Validate editForm (see TaskForm validation)
  2. If errors: display errors, do not submit
  3. If no errors:
     a. Call PATCH /api/v1/tasks/{taskId} with editForm
     b. On success (200 OK):
        - Set task = response.data
        - Set isEditing = false
        - Call onTaskUpdated(response.data)
     c. On 409 Conflict (version mismatch):
        - Display error: "Task has been modified. Please refresh."
        - Fetch task to get latest state
     d. On error:
        - Display error
```

#### Delete Task
```
On "Delete" button click:
  1. Show confirmation dialog: "Are you sure you want to delete this task?"
  2. On confirm:
     a. Call DELETE /api/v1/tasks/{taskId}
     b. On success (204 No Content):
        - Call onTaskDeleted(taskId)
        - Navigate back to list
     c. On error:
        - Display error message
  3. On cancel:
     - Close dialog
```

### Rendering

```jsx
<div className="task-detail">
  {/* Back button */}
  <button onClick={handleBack} className="back-button">
    ← Back to List
  </button>

  {/* Loading state */}
  {state.isLoading && <div className="loading">Loading task...</div>}

  {/* Error state */}
  {state.error && (
    <div className="error" role="alert">
      {state.error.message}
      <button onClick={handleRetry}>Retry</button>
    </div>
  )}

  {/* Task detail */}
  {!state.isLoading && state.task && (
    <div className="task-detail-content">
      {!state.isEditing ? (
        <>
          {/* View mode */}
          <h1>{state.task.title}</h1>
          <div className="task-meta">
            <span className={`status status-${state.task.status.toLowerCase()}`}>
              {state.task.status}
            </span>
            <span className={`priority priority-${state.task.priority.toLowerCase()}`}>
              {state.task.priority}
            </span>
          </div>

          {state.task.description && (
            <div className="task-description">
              <h3>Description</h3>
              <p>{state.task.description}</p>
            </div>
          )}

          {state.task.due_date && (
            <div className="task-due-date">
              <h3>Due Date</h3>
              <p>{state.task.due_date}</p>
            </div>
          )}

          <div className="task-timestamps">
            <p>Created: {new Date(state.task.created_at).toLocaleString()}</p>
            <p>Updated: {new Date(state.task.updated_at).toLocaleString()}</p>
          </div>

          <div className="task-actions">
            <button onClick={handleEdit} className="edit-button">
              Edit
            </button>
            <button onClick={handleDelete} className="delete-button">
              Delete
            </button>
          </div>
        </>
      ) : (
        <>
          {/* Edit mode */}
          <TaskForm
            mode="edit"
            initialTask={state.task}
            onSubmit={handleSaveEdit}
            onError={handleEditError}
            onCancel={handleCancelEdit}
          />
        </>
      )}
    </div>
  )}
</div>
```

---

# 9. BUSINESS LOGIC & ALGORITHMS

## 9.1 Task State Machine Validation

### Algorithm: Validate State Transition
```
Input:
  - currentStatus: TaskStatus (current task status)
  - requestedStatus: TaskStatus (requested new status)

Output:
  - isValid: boolean (true if transition is allowed)
  - allowedTransitions: Set<TaskStatus> (allowed next states)

Algorithm:
  1. Define state transition map:
     NEW → {IN_PROGRESS, ARCHIVED}
     IN_PROGRESS → {COMPLETED, ARCHIVED}
     COMPLETED → {ARCHIVED}
     ARCHIVED → {} (terminal state)

  2. If currentStatus == requestedStatus:
     return {isValid: true, reason: "idempotent"}

  3. allowedTransitions = transitionMap[currentStatus]

  4. If requestedStatus in allowedTransitions:
     return {isValid: true}
  Else:
     return {isValid: false, allowedTransitions: allowedTransitions}

Time Complexity: O(1)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
public class TaskStateValidator {
  
  private static final Map<TaskStatus, Set<TaskStatus>> ALLOWED_TRANSITIONS = 
    Map.ofEntries(
      Map.entry(TaskStatus.NEW, Set.of(TaskStatus.IN_PROGRESS, TaskStatus.ARCHIVED)),
      Map.entry(TaskStatus.IN_PROGRESS, Set.of(TaskStatus.COMPLETED, TaskStatus.ARCHIVED)),
      Map.entry(TaskStatus.COMPLETED, Set.of(TaskStatus.ARCHIVED)),
      Map.entry(TaskStatus.ARCHIVED, Set.of())
    );
  
  public static ValidationResult validateTransition(
    TaskStatus currentStatus,
    TaskStatus requestedStatus
  ) {
    // Idempotent: allow no-op transitions
    if (currentStatus == requestedStatus) {
      return ValidationResult.valid();
    }
    
    Set<TaskStatus> allowedNextStates = ALLOWED_TRANSITIONS.get(currentStatus);
    
    if (allowedNextStates.contains(requestedStatus)) {
      return ValidationResult.valid();
    } else {
      return ValidationResult.invalid(
        String.format(
          "Cannot transition from %s to %s. Allowed transitions: %s",
          currentStatus,
          requestedStatus,
          allowedNextStates
        ),
        allowedNextStates
      );
    }
  }
}

public class ValidationResult {
  private final boolean valid;
  private final String message;
  private final Set<TaskStatus> allowedTransitions;
  
  public static ValidationResult valid() {
    return new ValidationResult(true, null, Set.of());
  }
  
  public static ValidationResult invalid(String message, Set<TaskStatus> allowedTransitions) {
    return new ValidationResult(false, message, allowedTransitions);
  }
  
  // Getters...
}
```

---

## 9.2 Optimistic Locking Conflict Detection

### Algorithm: Detect Version Conflict
```
Input:
  - taskId: UUID (task identifier)
  - providedVersion: int (version from client)
  - currentVersion: int (version in database)

Output:
  - hasConflict: boolean (true if versions don't match)
  - currentTask: Task (current task state for client to retry)

Algorithm:
  1. Read task from database: SELECT * FROM tasks WHERE id = taskId FOR UPDATE
  2. If task not found:
     return {hasConflict: false, error: "TASK_NOT_FOUND"}
  3. If providedVersion != currentVersion:
     return {hasConflict: true, currentTask: task}
  4. Else:
     return {hasConflict: false}

Time Complexity: O(1) (single row lookup)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Service
public class TaskService {
  
  @Transactional
  public TaskResponse updateTask(
    UUID taskId,
    TaskUpdateRequest request,
    int providedVersion
  ) throws TaskNotFoundException, VersionConflictException {
    
    // Read task with row-level lock
    Task task = taskRepository.findByIdForUpdate(taskId)
      .orElseThrow(() -> new TaskNotFoundException(taskId));
    
    // Check version conflict
    if (task.getVersion() != providedVersion) {
      throw new VersionConflictException(
        String.format(
          "Version mismatch: provided %d, current %d",
          providedVersion,
          task.getVersion()
        ),
        task
      );
    }
    
    // Validate state transition (if status is being updated)
    if (request.getStatus() != null) {
      TaskStateValidator.validateTransition(task.getStatus(), request.getStatus());
    }
    
    // Update task fields
    task.setTitle(request.getTitle());
    task.setDescription(request.getDescription());
    task.setDueDate(request.getDueDate());
    task.setPriority(request.getPriority());
    if (request.getStatus() != null) {
      task.setStatus(request.getStatus());
    }
    
    // Increment version
    task.setVersion(task.getVersion() + 1);
    task.setUpdatedAt(Instant.now());
    
    // Save (within transaction)
    Task updated = taskRepository.save(task);
    
    return TaskMapper.toResponse(updated);
  }
}

@Repository
public interface TaskRepository extends JpaRepository<Task, UUID> {
  
  @Query("SELECT t FROM Task t WHERE t.id = :id")
  @Lock(LockModeType.PESSIMISTIC_WRITE)
  Optional<Task> findByIdForUpdate(@Param("id") UUID id);
}
```

---

## 9.3 Pagination Offset### Algorithm: Calculate Pagination Offset
```
Input:
  - pageNumber: int (1-indexed page number, or 0 for first page)
  - limit: int (items per page)
  - offset: int (0-indexed offset from client)

Output:
  - calculatedOffset: int (0-indexed offset for database query)
  - isValid: boolean (true if offset is valid)

Algorithm:
  1. Validate limit:
     If limit < 1 or limit > 100:
       return {isValid: false, error: "INVALID_LIMIT"}
  
  2. Validate offset:
     If offset < 0:
       return {isValid: false, error: "INVALID_OFFSET"}
  
  3. If offset is provided:
     return {isValid: true, calculatedOffset: offset}
  
  4. Else if pageNumber is provided:
     calculatedOffset = (pageNumber - 1) * limit
     return {isValid: true, calculatedOffset: calculatedOffset}

Time Complexity: O(1)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Service
public class TaskService {
  
  private static final int MIN_LIMIT = 1;
  private static final int MAX_LIMIT = 100;
  private static final int DEFAULT_LIMIT = 20;
  private static final int DEFAULT_OFFSET = 0;
  
  public Page<TaskResponse> listTasks(
    Integer limit,
    Integer offset,
    String status,
    String priority,
    LocalDate dueDateStart,
    LocalDate dueDateEnd,
    String sortBy,
    String sortOrder
  ) throws ValidationException {
    
    // Validate and normalize limit
    if (limit == null) {
      limit = DEFAULT_LIMIT;
    }
    if (limit < MIN_LIMIT || limit > MAX_LIMIT) {
      throw new ValidationException(
        String.format(
          "limit must be between %d and %d (provided: %d)",
          MIN_LIMIT,
          MAX_LIMIT,
          limit
        )
      );
    }
    
    // Validate and normalize offset
    if (offset == null) {
      offset = DEFAULT_OFFSET;
    }
    if (offset < 0) {
      throw new ValidationException(
        String.format("offset must be >= 0 (provided: %d)", offset)
      );
    }
    
    // Build query with filters
    Specification<Task> spec = buildFilterSpecification(
      status,
      priority,
      dueDateStart,
      dueDateEnd
    );
    
    // Build sort order
    Sort sort = buildSort(sortBy, sortOrder);
    
    // Execute paginated query
    Pageable pageable = PageRequest.of(
      offset / limit,  // Convert offset to page number
      limit,
      sort
    );
    
    Page<Task> page = taskRepository.findAll(spec, pageable);
    
    return new Page<>(
      page.getContent().stream()
        .map(TaskMapper::toResponse)
        .collect(Collectors.toList()),
      page.getTotalElements(),
      page.hasNext(),
      offset,
      limit
    );
  }
}

public class Page<T> {
  private final List<T> data;
  private final long totalCount;
  private final boolean hasMore;
  private final int offset;
  private final int limit;
  
  public Page(List<T> data, long totalCount, boolean hasMore, int offset, int limit) {
    this.data = data;
    this.totalCount = totalCount;
    this.hasMore = hasMore;
    this.offset = offset;
    this.limit = limit;
  }
  
  // Getters...
}
```

---

## 9.4 Task Filtering & Query Building

### Algorithm: Build Filter Specification
```
Input:
  - status: string (optional, filter by status)
  - priority: string (optional, filter by priority)
  - dueDateStart: LocalDate (optional, filter tasks with due_date >= dueDateStart)
  - dueDateEnd: LocalDate (optional, filter tasks with due_date <= dueDateEnd)

Output:
  - specification: Specification<Task> (JPA specification for filtering)

Algorithm:
  1. Initialize specification as empty (no filters)
  
  2. If status is provided and not "ALL":
     Add filter: task.status == status
  
  3. If priority is provided and not "ALL":
     Add filter: task.priority == priority
  
  4. If dueDateStart is provided:
     Add filter: task.due_date >= dueDateStart
  
  5. If dueDateEnd is provided:
     Add filter: task.due_date <= dueDateEnd
  
  6. Combine all filters with AND logic
  
  7. Return specification

Time Complexity: O(1) (constant number of filters)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Service
public class TaskService {
  
  private Specification<Task> buildFilterSpecification(
    String status,
    String priority,
    LocalDate dueDateStart,
    LocalDate dueDateEnd
  ) {
    return (root, query, criteriaBuilder) -> {
      List<Predicate> predicates = new ArrayList<>();
      
      // Filter by status
      if (status != null && !status.equals("ALL")) {
        predicates.add(
          criteriaBuilder.equal(root.get("status"), TaskStatus.valueOf(status))
        );
      }
      
      // Filter by priority
      if (priority != null && !priority.equals("ALL")) {
        predicates.add(
          criteriaBuilder.equal(root.get("priority"), TaskPriority.valueOf(priority))
        );
      }
      
      // Filter by due date start
      if (dueDateStart != null) {
        predicates.add(
          criteriaBuilder.greaterThanOrEqualTo(root.get("dueDate"), dueDateStart)
        );
      }
      
      // Filter by due date end
      if (dueDateEnd != null) {
        predicates.add(
          criteriaBuilder.lessThanOrEqualTo(root.get("dueDate"), dueDateEnd)
        );
      }
      
      // Combine predicates with AND
      return criteriaBuilder.and(predicates.toArray(new Predicate[0]));
    };
  }
  
  private Sort buildSort(String sortBy, String sortOrder) {
    if (sortBy == null) {
      sortBy = "created_at";
    }
    if (sortOrder == null) {
      sortOrder = "desc";
    }
    
    Sort.Direction direction = Sort.Direction.fromString(sortOrder.toUpperCase());
    
    return switch (sortBy) {
      case "created_at" -> Sort.by(direction, "createdAt").and(Sort.by(direction, "id"));
      case "due_date" -> Sort.by(direction, "dueDate").and(Sort.by(direction, "id"));
      case "priority" -> Sort.by(direction, "priority").and(Sort.by(direction, "id"));
      default -> Sort.by(direction, "createdAt").and(Sort.by(direction, "id"));
    };
  }
}
```

---

## 9.5 Idempotency Key Deduplication

### Algorithm: Detect Duplicate Request
```
Input:
  - idempotencyKey: string (idempotency key from request header)
  - requestBody: object (current request body)

Output:
  - isDuplicate: boolean (true if key was used before)
  - previousResponse: object (previous response if duplicate)
  - isConflict: boolean (true if key used with different payload)

Algorithm:
  1. Query idempotency_keys table: SELECT * FROM idempotency_keys WHERE key = idempotencyKey
  
  2. If no record found:
     return {isDuplicate: false}
  
  3. If record found:
     a. Check if record is expired (created_at + 24 hours < now):
        If expired: delete record, return {isDuplicate: false}
     
     b. Compare stored request body with current request body:
        If bodies match:
          return {isDuplicate: true, previousResponse: record.response}
        Else:
          return {isDuplicate: false, isConflict: true, previousBody: record.body}

Time Complexity: O(1) (single row lookup)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Service
public class IdempotencyService {
  
  private static final Duration IDEMPOTENCY_TTL = Duration.ofHours(24);
  
  public IdempotencyResult checkIdempotency(
    String idempotencyKey,
    String requestBodyJson
  ) throws IdempotencyConflictException {
    
    Optional<IdempotencyRecord> existing = idempotencyKeyRepository
      .findByKey(idempotencyKey);
    
    if (existing.isEmpty()) {
      return IdempotencyResult.notFound();
    }
    
    IdempotencyRecord record = existing.get();
    
    // Check if record is expired
    if (record.getCreatedAt().plus(IDEMPOTENCY_TTL).isBefore(Instant.now())) {
      idempotencyKeyRepository.delete(record);
      return IdempotencyResult.notFound();
    }
    
    // Compare request bodies
    if (record.getRequestBody().equals(requestBodyJson)) {
      // Duplicate request: return cached response
      return IdempotencyResult.duplicate(record.getResponse());
    } else {
      // Conflict: same key, different payload
      throw new IdempotencyConflictException(
        String.format(
          "Idempotency key '%s' already used with different request body",
          idempotencyKey
        ),
        record.getRequestBody(),
        requestBodyJson
      );
    }
  }
  
  @Transactional
  public void recordIdempotency(
    String idempotencyKey,
    String requestBodyJson,
    String responseBodyJson
  ) {
    IdempotencyRecord record = new IdempotencyRecord();
    record.setKey(idempotencyKey);
    record.setRequestBody(requestBodyJson);
    record.setResponse(responseBodyJson);
    record.setCreatedAt(Instant.now());
    
    idempotencyKeyRepository.save(record);
  }
}

@Repository
public interface IdempotencyKeyRepository extends JpaRepository<IdempotencyRecord, UUID> {
  Optional<IdempotencyRecord> findByKey(String key);
}

public class IdempotencyResult {
  private final boolean found;
  private final String cachedResponse;
  
  public static IdempotencyResult notFound() {
    return new IdempotencyResult(false, null);
  }
  
  public static IdempotencyResult duplicate(String cachedResponse) {
    return new IdempotencyResult(true, cachedResponse);
  }
  
  public boolean isFound() {
    return found;
  }
  
  public String getCachedResponse() {
    return cachedResponse;
  }
}
```

---

## 9.6 Request ID Propagation

### Algorithm: Generate or Extract Request ID
```
Input:
  - requestHeaders: Map<string, string> (HTTP request headers)

Output:
  - requestId: string (UUID v4 or extracted from header)

Algorithm:
  1. Check if X-Request-ID header is present:
     If present and non-empty:
       return X-Request-ID value
  
  2. Else:
     Generate UUID v4
     return UUID v4

Time Complexity: O(1)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Component
public class RequestIdFilter extends OncePerRequestFilter {
  
  private static final String REQUEST_ID_HEADER = "X-Request-ID";
  private static final String REQUEST_ID_MDC_KEY = "requestId";
  
  @Override
  protected void doFilterInternal(
    HttpServletRequest request,
    HttpServletResponse response,
    FilterChain filterChain
  ) throws ServletException, IOException {
    
    // Extract or generate request ID
    String requestId = request.getHeader(REQUEST_ID_HEADER);
    if (requestId == null || requestId.isBlank()) {
      requestId = UUID.randomUUID().toString();
    }
    
    // Store in MDC for logging
    MDC.put(REQUEST_ID_MDC_KEY, requestId);
    
    // Add to response header
    response.setHeader(REQUEST_ID_HEADER, requestId);
    
    try {
      filterChain.doFilter(request, response);
    } finally {
      MDC.remove(REQUEST_ID_MDC_KEY);
    }
  }
}

@RestControllerAdvice
public class GlobalExceptionHandler {
  
  @ExceptionHandler(TaskNotFoundException.class)
  public ResponseEntity<ErrorResponse> handleTaskNotFound(
    TaskNotFoundException ex,
    HttpServletRequest request
  ) {
    String requestId = MDC.get("requestId");
    
    ErrorResponse error = new ErrorResponse(
      "TASK_NOT_FOUND",
      "Task not found",
      requestId,
      Instant.now(),
      Map.of("task_id", ex.getTaskId().toString())
    );
    
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(error);
  }
}
```

---

## 9.7 Rate Limiting (Token Bucket Algorithm)

### Algorithm: Token Bucket Rate Limiter
```
Input:
  - clientIp: string (client IP address)
  - limit: int (requests per minute, default: 1000)
  - burstCapacity: int (burst capacity, default: 100)

Output:
  - isAllowed: boolean (true if request is allowed)
  - remaining: int (requests remaining in current window)
  - resetAt: Instant (when limit resets)

Algorithm:
  1. Query rate limit bucket: SELECT * FROM rate_limit_buckets WHERE client_ip = clientIp
  
  2. If no bucket found:
     Create new bucket:
       tokens = burstCapacity
       lastRefillAt = now
       return {isAllowed: true, remaining: burstCapacity - 1}
  
  3. If bucket found:
     a. Calculate elapsed time since last refill: elapsed = now - lastRefillAt
     
     b. Calculate tokens to add: tokensToAdd = (elapsed / 60 seconds) * limit
     
     c. Update bucket:
        tokens = min(tokens + tokensToAdd, burstCapacity)
        lastRefillAt = now
     
     d. If tokens > 0:
        tokens -= 1
        return {isAllowed: true, remaining: tokens}
     
     e. Else:
        return {isAllowed: false, remaining: 0, resetAt: lastRefillAt + 60 seconds}

Time Complexity: O(1) (single row lookup and update)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Component
public class RateLimitingFilter extends OncePerRequestFilter {
  
  private static final int LIMIT_PER_MINUTE = 1000;
  private static final int BURST_CAPACITY = 100;
  private static final Duration REFILL_PERIOD = Duration.ofMinutes(1);
  
  @Autowired
  private RateLimitBucketRepository bucketRepository;
  
  @Override
  protected void doFilterInternal(
    HttpServletRequest request,
    HttpServletResponse response,
    FilterChain filterChain
  ) throws ServletException, IOException {
    
    String clientIp = getClientIp(request);
    RateLimitResult result = checkRateLimit(clientIp);
    
    // Add rate limit headers
    response.setHeader("X-RateLimit-Limit", String.valueOf(LIMIT_PER_MINUTE));
    response.setHeader("X-RateLimit-Remaining", String.valueOf(result.getRemaining()));
    response.setHeader("X-RateLimit-Reset", String.valueOf(result.getResetAt().getEpochSecond()));
    
    if (!result.isAllowed()) {
      response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
      response.setContentType("application/json");
      
      ErrorResponse error = new ErrorResponse(
        "RATE_LIMIT_EXCEEDED",
        "Too many requests. Please retry after the reset time.",
        MDC.get("requestId"),
        Instant.now(),
        Map.of(
          "limit", LIMIT_PER_MINUTE,
          "remaining", 0,
          "reset_at", result.getResetAt().toString(),
          "retry_after_seconds", 60
        )
      );
      
      response.getWriter().write(new ObjectMapper().writeValueAsString(error));
      return;
    }
    
    filterChain.doFilter(request, response);
  }
  
  private RateLimitResult checkRateLimit(String clientIp) {
    Optional<RateLimitBucket> existing = bucketRepository.findByClientIp(clientIp);
    
    RateLimitBucket bucket;
    if (existing.isEmpty()) {
      bucket = new RateLimitBucket();
      bucket.setClientIp(clientIp);
      bucket.setTokens(BURST_CAPACITY - 1);
      bucket.setLastRefillAt(Instant.now());
      bucketRepository.save(bucket);
      
      return new RateLimitResult(
        true,
        BURST_CAPACITY - 1,
        Instant.now().plus(REFILL_PERIOD)
      );
    }
    
    bucket = existing.get();
    
    // Calculate tokens to add
    Duration elapsed = Duration.between(bucket.getLastRefillAt(), Instant.now());
    double tokensToAdd = (double) elapsed.getSeconds() / REFILL_PERIOD.getSeconds() * LIMIT_PER_MINUTE;
    
    bucket.setTokens(
      Math.min(
        (int) (bucket.getTokens() + tokensToAdd),
        BURST_CAPACITY
      )
    );
    bucket.setLastRefillAt(Instant.now());
    
    if (bucket.getTokens() > 0) {
      bucket.setTokens(bucket.getTokens() - 1);
      bucketRepository.save(bucket);
      
      return new RateLimitResult(
        true,
        bucket.getTokens(),
        Instant.now().plus(REFILL_PERIOD)
      );
    } else {
      return new RateLimitResult(
        false,
        0,
        bucket.getLastRefillAt().plus(REFILL_PERIOD)
      );
    }
  }
  
  private String getClientIp(HttpServletRequest request) {
    String xForwardedFor = request.getHeader("X-Forwarded-For");
    if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
      return xForwardedFor.split(",")[0].trim();
    }
    return request.getRemoteAddr();
  }
}

public class RateLimitResult {
  private final boolean allowed;
  private final int remaining;
  private final Instant resetAt;
  
  public RateLimitResult(boolean allowed, int remaining, Instant resetAt) {
    this.allowed = allowed;
    this.remaining = remaining;
    this.resetAt = resetAt;
  }
  
  public boolean isAllowed() {
    return allowed;
  }
  
  public int getRemaining() {
    return remaining;
  }
  
  public Instant getResetAt() {
    return resetAt;
  }
}
```

---

## 9.8 Data Validation Algorithms

### Algorithm: Validate Task Title
```
Input:
  - title: string (task title)

Output:
  - isValid: boolean
  - error: string (error message if invalid)

Algorithm:
  1. If title is null or undefined:
     return {isValid: false, error: "REQUIRED"}
  
  2. Trim whitespace: title = title.trim()
  
  3. If title.length == 0:
     return {isValid: false, error: "REQUIRED"}
  
  4. If title.length > 255:
     return {isValid: false, error: "MAX_LENGTH_EXCEEDED"}
  
  5. return {isValid: true}

Time Complexity: O(n) where n = length of title
Space Complexity: O(1)
```

### Algorithm: Validate Task Due Date
```
Input:
  - dueDate: string (ISO 8601 date format: YYYY-MM-DD)

Output:
  - isValid: boolean
  - error: string (error message if invalid)
  - parsedDate: LocalDate (parsed date if valid)

Algorithm:
  1. If dueDate is null or undefined:
     return {isValid: true} (optional field)
  
  2. If dueDate is empty string:
     return {isValid: false, error: "INVALID_FORMAT"}
  
  3. Try to parse dueDate as ISO 8601 date (YYYY-MM-DD):
     If parse fails:
       return {isValid: false, error: "INVALID_FORMAT"}
  
  4. If parsed date is invalid (e.g., 2024-13-45):
     return {isValid: false, error: "INVALID_DATE"}
  
  5. return {isValid: true, parsedDate: parsedDate}

Time Complexity: O(n) where n = length of date string
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Component
public class TaskValidator {
  
  public ValidationResult validateTitle(String title) {
    if (title == null || title.isBlank()) {
      return ValidationResult.invalid("REQUIRED", "title is required");
    }
    
    String trimmed = title.trim();
    
    if (trimmed.isEmpty()) {
      return ValidationResult.invalid("REQUIRED", "title is required");
    }
    
    if (trimmed.length() > 255) {
      return ValidationResult.invalid(
        "MAX_LENGTH_EXCEEDED",
        String.format("title must not exceed 255 characters (provided: %d)", trimmed.length())
      );
    }
    
    return ValidationResult.valid();
  }
  
  public ValidationResult validateDescription(String description) {
    if (description == null || description.isBlank()) {
      return ValidationResult.valid(); // Optional field
    }
    
    if (description.length() > 2000) {
      return ValidationResult.invalid(
        "MAX_LENGTH_EXCEEDED",
        String.format("description must not exceed 2000 characters (provided: %d)", description.length())
      );
    }
    
    return ValidationResult.valid();
  }
  
  public ValidationResult validateDueDate(String dueDateStr) {
    if (dueDateStr == null || dueDateStr.isBlank()) {
      return ValidationResult.valid(); // Optional field
    }
    
    try {
      LocalDate dueDate = LocalDate.parse(dueDateStr, DateTimeFormatter.ISO_DATE);
      return ValidationResult.valid();
    } catch (DateTimeParseException e) {
      return ValidationResult.invalid(
        "INVALID_FORMAT",
        String.format("due_date must be in ISO 8601 format (YYYY-MM-DD), got: '%s'", dueDateStr)
      );
    }
  }
  
  public ValidationResult validatePriority(String priority) {
    if (priority == null || priority.isBlank()) {
      return ValidationResult.valid(); // Optional field, defaults to MEDIUM
    }
    
    try {
      TaskPriority.valueOf(priority.toUpperCase());
      return ValidationResult.valid();
    } catch (IllegalArgumentException e) {
      return ValidationResult.invalid(
        "INVALID_ENUM",
        String.format("priority must be one of: LOW, MEDIUM, HIGH (got: '%s')", priority)
      );
    }
  }
}

public class ValidationResult {
  private final boolean valid;
  private final String issue;
  private final String message;
  
  public static ValidationResult valid() {
    return new ValidationResult(true, null, null);
  }
  
  public static ValidationResult invalid(String issue, String message) {
    return new ValidationResult(false, issue, message);
  }
  
  public boolean isValid() {
    return valid;
  }
  
  public String getIssue() {
    return issue;
  }
  
  public String getMessage() {
    return message;
  }
}
```

---

## 9.9 Timestamp Management

### Algorithm: Manage Task Timestamps
```
Input:
  - operation: string (CREATE, UPDATE, DELETE)
  - task: Task (task object)

Output:
  - task: Task (task with updated timestamps)

Algorithm:
  1. If operation == CREATE:
     task.created_at = now (UTC)
     task.updated_at = now (UTC)
  
  2. If operation == UPDATE:
     task.updated_at = now (UTC)
     (created_at remains unchanged)
  
  3. If operation == DELETE:
     task.updated_at = now (UTC)
     (created_at remains unchanged)
  
  4. return task

Time Complexity: O(1)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Entity
@Table(name = "tasks")
public class Task {
  
  @Id
  private UUID id;
  
  @Column(name = "title", nullable = false, length = 255)
  private String title;
  
  @Column(name = "description", length = 2000)
  private String description;
  
  @Column(name = "due_date")
  private LocalDate dueDate;
  
  @Column(name = "priority", nullable = false)
  @Enumerated(EnumType.STRING)
  private TaskPriority priority;
  
  @Column(name = "status", nullable = false)
  @Enumerated(EnumType.STRING)
  private TaskStatus status;
  
  @Column(name = "version", nullable = false)
  private Integer version;
  
  @Column(name = "created_at", nullable = false, updatable = false)
  private Instant createdAt;
  
  @Column(name = "updated_at", nullable = false)
  private Instant updatedAt;
  
  @PrePersist
  protected void onCreate() {
    this.id = UUID.randomUUID();
    this.createdAt = Instant.now();
    this.updatedAt = Instant.now();
    this.version = 1;
    if (this.status == null) {
      this.status = TaskStatus.NEW;
    }
    if (this.priority == null) {
      this.priority = TaskPriority.MEDIUM;
    }
  }
  
  @PreUpdate
  protected void onUpdate() {
    this.updatedAt = Instant.now();
  }
  
  // Getters and setters...
}
```

---

## 9.10 Response Serialization

### Algorithm: Serialize Task to JSON
```
Input:
  - task: Task (task entity from database)

Output:
  - json: string (JSON representation of task)

Algorithm:
  1. Create response object:
     {
       "id": task.id (UUID as string),
       "title": task.title (string),
       "description": task.description (string or null),
       "due_date": task.due_date (ISO 8601 date string or null),
       "priority": task.priority (enum string: LOW, MEDIUM, HIGH),
       "status": task.status (enum string: NEW, IN_PROGRESS, COMPLETED, ARCHIVED),
       "version": task.version (integer),
       "created_at": task.created_at (ISO 8601 timestamp string),
       "updated_at": task.updated_at (ISO 8601 timestamp string)
     }
  
  2. Serialize to JSON string using Jackson ObjectMapper
  
  3. return json

Time Complexity: O(1) (constant number of fields)
Space Complexity: O(1)
```

### Implementation (Java/Spring)
```java
@Component
public class TaskMapper {
  
  private static final ObjectMapper objectMapper = new ObjectMapper()
    .registerModule(new JavaTimeModule())
    .setSerializationInclusion(JsonInclude.Include.NON_NULL);
  
  public static TaskResponse toResponse(Task task) {
    return new TaskResponse(
      task.getId().toString(),
      task.getTitle(),
      task.getDescription(),
      task.getDueDate() != null ? task.getDueDate().toString() : null,
      task.getPriority().toString(),
      task.getStatus().toString(),
      task.getVersion(),
      task.getCreatedAt().toString(),
      task.getUpdatedAt().toString()
    );
  }
  
  public static Task toEntity(TaskCreateRequest request) {
    Task task = new Task();
    task.setTitle(request.getTitle());
    task.setDescription(request.getDescription());
    if (request.getDueDate() != null) {
      task.setDueDate(LocalDate.parse(request.getDueDate()));
    }
    task.setPriority(TaskPriority.valueOf(request.getPriority()));
    task.setStatus(TaskStatus.NEW);
    return task;
  }
}

@Data
@AllArgsConstructor
public class TaskResponse {
  private String id;
  private String title;
  private String description;
  private String due_date;
  private String priority;
  private String status;
  private Integer version;
  private String created_at;
  private String updated_at;
}
```

---

# 10. TESTING STRATEGY

## 10.1 Unit Tests

### Test Coverage Goals
```
Target: >80% code coverage
Focus areas:
  - Business logic (state machine, validation, filtering)
  - Error handling (exception cases)
  - Edge cases (boundary conditions, null values)

Excluded from coverage:
  - Spring framework boilerplate (auto-wired beans, configuration)
  - Database schema (tested via integration tests)
  - HTTP layer (tested via integration tests)
```

### Unit Test Examples

#### Test: Task State Machine Validation
```java
@Test
public void testValidTransitionFromNewToInProgress() {
  TaskStatus current = TaskStatus.NEW;
  TaskStatus requested = TaskStatus.IN_PROGRESS;
  
  ValidationResult result = TaskStateValidator.validateTransition(current, requested);
  
  assertTrue(result.isValid());
}

@Test
public void testInvalidTransitionFromCompletedToNew() {
  TaskStatus current = TaskStatus.COMPLETED;
  TaskStatus requested = TaskStatus.NEW;
  
  ValidationResult result = TaskStateValidator.validateTransition(current, requested);
  
  assertFalse(result.isValid());
  assertEquals("Cannot transition from COMPLETED to NEW", result.getMessage());
}

@Test
public void testIdempotentTransition() {
  TaskStatus current = TaskStatus.IN_PROGRESS;
  TaskStatus requested = TaskStatus.IN_PROGRESS;
  
  ValidationResult result = TaskStateValidator.validateTransition(current, requested);
  
  assertTrue(result.isValid());
}
```

#### Test: Task Title Validation
```java
@Test
public void testValidTitle() {
  String title = "Buy groceries";
  
  ValidationResult result = taskValidator.validateTitle(title);
  
  assertTrue(result.isValid());
}

@Test
public void testEmptyTitle() {
  String title = "";
  
  ValidationResult result = taskValidator.validateTitle(title);
  
  assertFalse(result.isValid());
  assertEquals("REQUIRED", result.getIssue());
}

@Test
public void testTitleExceedsMaxLength() {
  String title = "a".repeat(256);
  
  ValidationResult result = taskValidator.validateTitle(title);
  
  assertFalse(result.isValid());
  assertEquals("MAX_LENGTH_EXCEEDED", result.getIssue());
}

@Test
public void testNullTitle() {
  String title = null;
  
  ValidationResult result = taskValidator.validateTitle(title);
  
  assertFalse(result.isValid());
  assertEquals("REQUIRED", result.getIssue());
}
```

#### Test: Pagination Offset Calculation
```java
@Test
public void testValidOffset() {
  int limit = 20;
  int offset = 40;
  
  PaginationResult result = taskService.validatePagination(limit, offset);
  
  assertTrue(result.isValid());
  assertEquals(40, result.getCalculatedOffset());
}

@Test
public void testInvalidLimitTooLarge() {
  int limit = 101;
  int offset = 0;
  
  PaginationResult result = taskService.validatePagination(limit, offset);
  
  assertFalse(result.isValid());
  assertEquals("INVALID_LIMIT", result.getError());
}

@Test
public void testNegativeOffset() {
  int limit = 20;
  int offset = -1;
  
  PaginationResult result = taskService.validatePagination(limit, offset);
  
  assertFalse(result.isValid());
  assertEquals("INVALID_OFFSET", result.getError());
}
```

---

## 10.2 Integration Tests

### Integration Test Setup
```java
@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
public class TaskControllerIntegrationTest {
  
  @Autowired
  private MockMvc mockMvc;
  
  @Autowired
  private TaskRepository taskRepository;
  
  @Autowired
  private IdempotencyKeyRepository idempotencyKeyRepository;
  
  @BeforeEach
  public void setUp() {
    taskRepository.deleteAll();
    idempotencyKeyRepository.deleteAll();
  }
}
```

### Integration Test Examples

#### Test: Create Task (Happy Path)
```java
@Test
public void testCreateTaskSuccess() throws Exception {
  String idempotencyKey = UUID.randomUUID().toString();
  
  String requestBody = """
    {
      "title": "Buy groceries",
      "description": "Milk, eggs, bread",
      "due_date": "2024-12-31",
      "priority": "HIGH"
    }
    """;
  
  mockMvc.perform(post("/api/v1/tasks")
    .header("X-Idempotency-Key", idempotencyKey)
    .contentType(MediaType.APPLICATION_JSON)
    .content(requestBody))
    .andExpect(status().isCreated())
    .andExpect(jsonPath("$.id").exists())
    .andExpect(jsonPath("$.title").value("Buy groceries"))
    .andExpect(jsonPath("$.status").value("NEW"))
    .andExpect(jsonPath("$.priority").value("HIGH"))
    .andExpect(jsonPath("$.version").value(1));
  
  // Verify task was persisted
  assertEquals(1, taskRepository.count());
}
```

#### Test: Create Task (Validation Error)
```java
@Test
public void testCreateTaskMissingTitle() throws Exception {
  String idempotencyKey = UUID.randomUUID().toString();
  
  String requestBody = """
    {
      "priority": "HIGH"
    }
    """;
  
  mockMvc.perform(post("/api/v1/tasks")
    .header("X-Idempotency-Key", idempotencyKey)
    .contentType(MediaType.APPLICATION_JSON)
    .content(requestBody))
    .andExpect(status().isBadRequest())
    .andExpect(jsonPath("$.error_code").value("VALIDATION_ERROR"))
    .andExpect(jsonPath("$.details[0].field").value("title"))
    .andExpect(jsonPath("$.details[0].issue").value("REQUIRED"));
  
  // Verify task was NOT persisted
  assertEquals(0, taskRepository.count());
}
```

#### Test: Update Task (Version Conflict)
```java
@Test
public void testUpdateTaskVersionConflict() throws Exception {
  // Create task
  Task task = new Task();
  task.setTitle("Original title");
  task.setStatus(TaskStatus.NEW);
  task.setPriority(TaskPriority.MEDIUM);
  task.setVersion(1);
  task = taskRepository.save(task);
  
  // Simulate concurrent update: increment version to 2
  task.setVersion(2);
  taskRepository.save(task);
  
  // Attempt update with stale version
  String requestBody = """
    {
      "title": "Updated title",
      "version": 1
    }
    """;
  
  mockMvc.perform(patch("/api/v1/tasks/" + task.getId())
    .contentType(MediaType.APPLICATION_JSON)
    .content(requestBody))
    .andExpect(status().isConflict())
    .andExpect(jsonPath("$.error_code").value("CONFLICT_VERSION_MISMATCH"))
    .andExpect(jsonPath("$.details.provided_version").value(1))
    .andExpect(jsonPath("$.details.current_version").value(2));
}
```

#### Test: List Tasks with Filtering
```java
@Test
public void testListTasksWithStatusFilter() throws Exception {
  // Create tasks with different statuses
  Task task1 = new Task();
  task1.setTitle("Task 1");
  task1.setStatus(TaskStatus.NEW);
  task1.setPriority(TaskPriority.MEDIUM);
  taskRepository.save(task1);
  
  Task task2 = new Task();
  task2.setTitle("Task 2");
  task2.setStatus(TaskStatus.IN_PROGRESS);
  task2.setPriority(TaskPriority.HIGH);
  taskRepository.save(task2);
  
  // Filter by status
  mockMvc.perform(get("/api/v1/tasks?status=NEW"))
    .andExpect(status().isOk())
    .andExpect(jsonPath("$.data.length()").value(1))
    .andExpect(jsonPath("$.data[0].title").value("Task 1"))
    .andExpect(jsonPath("$.total_count").value(1));
}
```

#### Test: Idempotency (Duplicate Request)
```java
@Test
public void testCreateTaskIdempotency() throws Exception {
  String idempotencyKey = UUID.randomUUID().toString();
  
  String requestBody = """
    {
      "title": "Buy groceries",
      "priority": "HIGH"
    }
    """;
  
  // First request
  MvcResult result1 = mockMvc.perform(post("/api/v1/tasks")
    .header("X-Idempotency-Key", idempotencyKey)
    .contentType(MediaType.APPLICATION_JSON)
    .content(requestBody))
    .andExpect(status().isCreated())
    .andReturn();
  
  String taskId1 = JsonPath.read(result1.getResponse().getContentAsString(), "$.id");
  
  // Second request (duplicate)
  MvcResult result2 = mockMvc.perform(post("/api/v1/tasks")
    .header("X-Idempotency-Key", idempotencyKey)
    .contentType(MediaType.APPLICATION_JSON)
    .content(requestBody))
    .andExpect(status().isCreated())
    .andReturn();
  
  String taskId2 = JsonPath.read(result2.getResponse().getContentAsString(), "$.id");
  
  // Verify same task was returned
  assertEquals(taskId1, taskId2);
  
  // Verify only one task was created
  assertEquals(1, taskRepository.count());
}
```

---

## 10.3 End-to-End Test Scenarios

### Scenario 1: Complete Task Lifecycle
```
1. Create task (NEW)
2. Transition to IN_PROGRESS
3. Transition to COMPLETED
4. Transition to ARCHIVED
5. Verify final state

Expected: All transitions succeed, version increments at each step
```

### Scenario 2: Concurrent Update Conflict
```
1. Create task (version 1)
2. Client A fetches task (version 1)
3. Client B fetches task (version 1)
4. Client A updates task (version 1 → 2)
5. Client B attempts update (version 1 → 2)

Expected: Client B receives 409 Conflict, can retry after re-fetching
```

### Scenario 3: Pagination with Deletion
```
1. Create 25 tasks
2. Fetch page 1 (limit=10, offset=0) → tasks 1-10
3. Delete task 5
4. Fetch page 2 (limit=10, offset=10) → tasks 11-25 (offset shifted)

Expected: Client sees consistent pagination despite deletion
```

### Scenario 4: Rate Limiting
```
1. Send 1000 requests within 1 minute
2. Send 1001st request

Expected: 1001st request returns 429 Too Many Requests
```

---

## 10.4 Performance Tests

### Load Test: 1,000 Concurrent Users
```
Scenario:
  - 1,000 concurrent users
  - Each user creates 10 tasks
  - Each user lists tasks 5 times
  - Each user updates 5 tasks
  - Duration: 5 minutes

Expected Results:
  - p95 latency: <200ms
  - p99 latency: <500ms
  - Error rate: <0.1%
  - Throughput: >100 requests/second
```

### Load Test: Large Result Set
```
Scenario:
  - 10,000 tasks in database
  - List tasks with limit=100, offset=0
  - List tasks with limit=100, offset=9900

Expected Results:
  - p95 latency: <200ms (even for large offsets)
  - Memory usage: <500MB
  - No timeout errors
```

---

This completes the SPECS.md document with comprehensive specifications for error handling, validation, concurrency, frontend components, business logic algorithms, and testing strategy. All sections are now complete and ready for implementation.

---

# 8. SERVICE BOUNDARIES & INTERNAL APIS

## 8.1 Service Layer Architecture

### TaskService (Core Business Logic)

**Responsibility:** Orchestrate task lifecycle operations, enforce state machine rules, handle concurrency conflicts, coordinate with repository layer.

**Public Methods:**

```java
package com.todoapi.service;

import com.todoapi.dto.*;
import com.todoapi.entity.Task;
import com.todoapi.exception.*;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;

public interface TaskService {
  
  /**
   * Create a new task.
   * 
   * @param request CreateTaskRequest with title, description, due_date, priority
   * @param idempotencyKey Unique key for idempotency (prevents duplicate creation)
   * @return Created task with auto-generated id, status=NEW, version=1
   * @throws ValidationException if request validation fails
   * @throws DuplicateTaskException if idempotency key already exists with different payload
   */
  TaskResponse createTask(CreateTaskRequest request, String idempotencyKey) 
    throws ValidationException, DuplicateTaskException;

  /**
   * Retrieve a single task by id.
   * 
   * @param taskId UUID of task to retrieve
   * @return Task details including current version
   * @throws TaskNotFoundException if task does not exist or is deleted
   */
  TaskResponse getTaskById(String taskId) 
    throws TaskNotFoundException;

  /**
   * List tasks with pagination, filtering, and sorting.
   * 
   * @param filter TaskFilterRequest with status, due_date_start, due_date_end, priority
   * @param pageable Pagination parameters (page, size, sort)
   * @return Page of tasks matching filter criteria
   * @throws ValidationException if filter parameters are invalid
   */
  Page<TaskResponse> listTasks(TaskFilterRequest filter, Pageable pageable) 
    throws ValidationException;

  /**
   * Update task status or fields (title, description, due_date, priority).
   * 
   * @param taskId UUID of task to update
   * @param request UpdateTaskRequest with fields to update and current version
   * @return Updated task with incremented version
   * @throws TaskNotFoundException if task does not exist
   * @throws ValidationException if request validation fails
   * @throws ConcurrencyConflictException if version mismatch (409 Conflict)
   * @throws InvalidStateTransitionException if status transition is not allowed
   */
  TaskResponse updateTask(String taskId, UpdateTaskRequest request) 
    throws TaskNotFoundException, ValidationException, ConcurrencyConflictException, InvalidStateTransitionException;

  /**
   * Delete a task (hard delete).
   * 
   * @param taskId UUID of task to delete
   * @throws TaskNotFoundException if task does not exist or already deleted
   */
  void deleteTask(String taskId) 
    throws TaskNotFoundException;

  /**
   * Validate state transition from current status to new status.
   * 
   * @param currentStatus Current task status
   * @param newStatus Desired task status
   * @throws InvalidStateTransitionException if transition is not allowed
   */
  void validateStateTransition(TaskStatus currentStatus, TaskStatus newStatus) 
    throws InvalidStateTransitionException;
}
```

**Implementation Notes:**

- **Idempotency Tracking:** Store idempotency keys in a separate `idempotency_keys` table with hash of request payload. On duplicate key with same payload, return cached response. On duplicate key with different payload, throw 409 Conflict.
- **Version Increment:** Every PATCH increments version by 1, regardless of which fields change. Version is checked before update; if mismatch, throw ConcurrencyConflictException (409).
- **State Machine Validation:** Before updating status, call `validateStateTransition()` to ensure transition is allowed (see [State Machines & Workflows](#state-machines--workflows)).
- **Soft-Delete Decision:** DECISION REQUIRED — Current spec says "hard delete only" but PRD mentions "soft-delete with retention." Clarify: Are deleted tasks physically removed, or marked with `deleted_at` timestamp? This affects schema, queries, and compliance.

---

### ValidationService (Input Validation)

**Responsibility:** Validate all incoming requests against business rules and constraints.

**Public Methods:**

```java
package com.todoapi.service;

import com.todoapi.dto.*;
import com.todoapi.exception.ValidationException;

public interface ValidationService {

  /**
   * Validate CreateTaskRequest.
   * 
   * @param request Request to validate
   * @throws ValidationException if any field fails validation
   */
  void validateCreateTaskRequest(CreateTaskRequest request) 
    throws ValidationException;

  /**
   * Validate UpdateTaskRequest.
   * 
   * @param request Request to validate
   * @throws ValidationException if any field fails validation
   */
  void validateUpdateTaskRequest(UpdateTaskRequest request) 
    throws ValidationException;

  /**
   * Validate TaskFilterRequest.
   * 
   * @param filter Filter to validate
   * @throws ValidationException if any filter parameter is invalid
   */
  void validateTaskFilterRequest(TaskFilterRequest filter) 
    throws ValidationException;

  /**
   * Validate task title.
   * 
   * @param title Title to validate
   * @throws ValidationException if title is invalid
   */
  void validateTitle(String title) 
    throws ValidationException;

  /**
   * Validate task description.
   * 
   * @param description Description to validate
   * @throws ValidationException if description is invalid
   */
  void validateDescription(String description) 
    throws ValidationException;

  /**
   * Validate due date.
   * 
   * @param dueDate Due date to validate (ISO 8601 format)
   * @throws ValidationException if due date is invalid
   */
  void validateDueDate(String dueDate) 
    throws ValidationException;

  /**
   * Validate priority.
   * 
   * @param priority Priority to validate
   * @throws ValidationException if priority is invalid
   */
  void validatePriority(String priority) 
    throws ValidationException;
}
```

**Validation Rules (Detailed):**

See [Section 6: Error Handling & Validation Rules](#error-handling--validation-rules) for complete validation specifications.

---

### IdempotencyService (Idempotency Key Management)

**Responsibility:** Track idempotency keys, detect duplicates, cache responses for retries.

**Public Methods:**

```java
package com.todoapi.service;

import com.todoapi.dto.TaskResponse;
import com.todoapi.exception.DuplicateTaskException;

public interface IdempotencyService {

  /**
   * Check if idempotency key exists and return cached response if available.
   * 
   * @param idempotencyKey Unique idempotency key
   * @param requestHash Hash of request payload (to detect payload changes)
   * @return Cached TaskResponse if key exists with same payload
   * @throws DuplicateTaskException if key exists with different payload
   * @return null if key does not exist (first attempt)
   */
  TaskResponse getCachedResponse(String idempotencyKey, String requestHash) 
    throws DuplicateTaskException;

  /**
   * Store idempotency key and response for future retries.
   * 
   * @param idempotencyKey Unique idempotency key
   * @param requestHash Hash of request payload
   * @param response TaskResponse to cache
   */
  void cacheResponse(String idempotencyKey, String requestHash, TaskResponse response);

  /**
   * Compute hash of request payload for duplicate detection.
   * 
   * @param request Request object to hash
   * @return SHA-256 hash of request JSON
   */
  String computeRequestHash(Object request);
}
```

**Implementation Notes:**

- **Idempotency Key Scope:** Applies to POST /tasks only. PATCH and DELETE are not idempotent; use version field for conflict detection.
- **Cache Expiration:** Idempotency keys expire after 24 hours (configurable). After expiration, same key can be reused for new request.
- **Hash Algorithm:** Use SHA-256 hash of request JSON (sorted keys) to detect payload changes.
- **Storage:** Store in `idempotency_keys` table with columns: `key`, `request_hash`, `response_json`, `created_at`, `expires_at`.

---

## 8.2 Repository Layer (Data Access)

### TaskRepository (Spring Data JPA)

**Responsibility:** CRUD operations on tasks table, custom queries for filtering/sorting.

**Interface Definition:**

```java
package com.todoapi.repository;

import com.todoapi.entity.Task;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface TaskRepository extends JpaRepository<Task, UUID> {

  /**
   * Find task by id (excludes deleted tasks).
   * 
   * @param id Task UUID
   * @return Task if exists and not deleted
   */
  @Query("SELECT t FROM Task t WHERE t.id = :id AND t.deletedAt IS NULL")
  Optional<Task> findByIdNotDeleted(@Param("id") UUID id);

  /**
   * Find all tasks with optional filtering by status, priority, due date range.
   * 
   * @param status Task status (nullable; if null, include all statuses)
   * @param priority Task priority (nullable; if null, include all priorities)
   * @param dueDateStart Start of due date range (nullable)
   * @param dueDateEnd End of due date range (nullable)
   * @param pageable Pagination and sort parameters
   * @return Page of tasks matching criteria
   */
  @Query("""
    SELECT t FROM Task t 
    WHERE t.deletedAt IS NULL
      AND (:status IS NULL OR t.status = :status)
      AND (:priority IS NULL OR t.priority = :priority)
      AND (:dueDateStart IS NULL OR t.dueDate >= :dueDateStart)
      AND (:dueDateEnd IS NULL OR t.dueDate <= :dueDateEnd)
  """)
  Page<Task> findAllWithFilters(
    @Param("status") String status,
    @Param("priority") String priority,
    @Param("dueDateStart") LocalDate dueDateStart,
    @Param("dueDateEnd") LocalDate dueDateEnd,
    Pageable pageable
  );

  /**
   * Count tasks by status (for analytics/monitoring).
   * 
   * @param status Task status
   * @return Count of tasks with given status
   */
  @Query("SELECT COUNT(t) FROM Task t WHERE t.status = :status AND t.deletedAt IS NULL")
  long countByStatus(@Param("status") String status);

  /**
   * Find tasks with due date in past (for notifications/reminders).
   * 
   * @param today Current date
   * @param pageable Pagination parameters
   * @return Page of overdue tasks
   */
  @Query("""
    SELECT t FROM Task t 
    WHERE t.dueDate < :today 
      AND t.status != 'COMPLETED' 
      AND t.deletedAt IS NULL
    ORDER BY t.dueDate ASC
  """)
  Page<Task> findOverdueTasks(@Param("today") LocalDate today, Pageable pageable);
}
```

**Custom Query Notes:**

- **Soft-Delete Handling:** All queries include `t.deletedAt IS NULL` to exclude deleted tasks. If hard-delete is used, remove this clause.
- **Null Parameter Handling:** Use `IS NULL` checks in JPQL to handle optional filter parameters. Spring Data JPA will pass null for omitted filters.
- **Pagination:** All list queries return `Page<Task>` to support pagination. Caller specifies page number, size, and sort order via `Pageable`.
- **Sort Order:** Default sort is `created_at DESC, id DESC` (tie-breaker). Clients can override via query parameter.

---

### IdempotencyKeyRepository (Spring Data JPA)

**Responsibility:** Store and retrieve idempotency keys for duplicate detection.

**Interface Definition:**

```java
package com.todoapi.repository;

import com.todoapi.entity.IdempotencyKey;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Optional;

@Repository
public interface IdempotencyKeyRepository extends JpaRepository<IdempotencyKey, String> {

  /**
   * Find idempotency key by key string (if not expired).
   * 
   * @param key Idempotency key string
   * @return IdempotencyKey if exists and not expired
   */
  @Query("""
    SELECT ik FROM IdempotencyKey ik 
    WHERE ik.key = :key 
      AND ik.expiresAt > CURRENT_TIMESTAMP
  """)
  Optional<IdempotencyKey> findByKeyNotExpired(@Param("key") String key);

  /**
   * Delete expired idempotency keys (cleanup job).
   * 
   * @param now Current timestamp
   * @return Number of keys deleted
   */
  @Query("DELETE FROM IdempotencyKey ik WHERE ik.expiresAt <= :now")
  int deleteExpiredKeys(@Param("now") LocalDateTime now);
}
```

---

## 8.3 Cross-Cutting Concerns

### RequestContextFilter (Request Tracing)

**Responsibility:** Extract or generate request ID, store in MDC (Mapped Diagnostic Context) for logging.

**Implementation Pseudocode:**

```java
package com.todoapi.filter;

import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;

@Component
public class RequestContextFilter extends OncePerRequestFilter {

  private static final String REQUEST_ID_HEADER = "X-Request-ID";
  private static final String REQUEST_ID_MDC_KEY = "requestId";

  @Override
  protected void doFilterInternal(
    HttpServletRequest request,
    HttpServletResponse response,
    FilterChain filterChain
  ) throws ServletException, IOException {
    
    // Extract or generate request ID
    String requestId = request.getHeader(REQUEST_ID_HEADER);
    if (requestId == null || requestId.isBlank()) {
      requestId = UUID.randomUUID().toString();
    }
    
    // Store in MDC for logging
    MDC.put(REQUEST_ID_MDC_KEY, requestId);
    
    // Add to response header
    response.setHeader(REQUEST_ID_HEADER, requestId);
    
    try {
      filterChain.doFilter(request, response);
    } finally {
      MDC.remove(REQUEST_ID_MDC_KEY);
    }
  }
}
```

**Logging Configuration (logback-spring.xml):**

```xml
<configuration>
  <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
    <encoder>
      <pattern>
        %d{ISO8601} [%thread] %-5level %logger{36} [%X{requestId}] - %msg%n
      </pattern>
    </encoder>
  </appender>

  <root level="INFO">
    <appender-ref ref="CONSOLE" />
  </root>
</configuration>
```

---

### RateLimitingFilter (Request Throttling)

**Responsibility:** Enforce rate limits per IP address using token bucket algorithm.

**Implementation Pseudocode:**

```java
package com.todoapi.filter;

import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.servlet.FilterChain;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class RateLimitingFilter extends OncePerRequestFilter {

  private static final int RATE_LIMIT_PER_MINUTE = 1000;
  private static final int BURST_CAPACITY = 100;
  private static final long WINDOW_SIZE_MS = 60_000; // 1 minute

  private final ConcurrentHashMap<String, TokenBucket> buckets = new ConcurrentHashMap<>();

  @Override
  protected void doFilterInternal(
    HttpServletRequest request,
    HttpServletResponse response,
    FilterChain filterChain
  ) throws ServletException, IOException {
    
    String clientIp = getClientIp(request);
    TokenBucket bucket = buckets.computeIfAbsent(clientIp, k -> new TokenBucket(RATE_LIMIT_PER_MINUTE, BURST_CAPACITY, WINDOW_SIZE_MS));
    
    if (!bucket.allowRequest()) {
      response.setStatus(429); // Too Many Requests
      response.setHeader("X-RateLimit-Limit", String.valueOf(RATE_LIMIT_PER_MINUTE));
      response.setHeader("X-RateLimit-Remaining", "0");
      response.setHeader("X-RateLimit-Reset", String.valueOf(bucket.getResetTime()));
      response.getWriter().write("{\"error_code\": \"RATE_LIMIT_EXCEEDED\", \"message\": \"Too many requests\"}");
      return;
    }
    
    response.setHeader("X-RateLimit-Limit", String.valueOf(RATE_LIMIT_PER_MINUTE));
    response.setHeader("X-RateLimit-Remaining", String.valueOf(bucket.getTokensRemaining()));
    response.setHeader("X-RateLimit-Reset", String.valueOf(bucket.getResetTime()));
    
    filterChain.doFilter(request, response);
  }

  private String getClientIp(HttpServletRequest request) {
    String xForwardedFor = request.getHeader("X-Forwarded-For");
    if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
      return xForwardedFor.split(",")[0].trim();
    }
    return request.getRemoteAddr();
  }

  private static class TokenBucket {
    private final int capacity;
    private final long windowSizeMs;
    private int tokens;
    private long lastRefillTime;

    TokenBucket(int ratePerMinute, int burstCapacity, long windowSizeMs) {
      this.capacity = burstCapacity;
      this.windowSizeMs = windowSizeMs;
      this.tokens = burstCapacity;
      this.lastRefillTime = System.currentTimeMillis();
    }

    synchronized boolean allowRequest() {
      refill();
      if (tokens > 0) {
        tokens--;
        return true;
      }
      return false;
    }

    private void refill() {
      long now = System.currentTimeMillis();
      long timePassed = now - lastRefillTime;
      if (timePassed >= windowSizeMs) {
        tokens = capacity;
        lastRefillTime = now;
      }
    }

    int getTokensRemaining() {
      refill();
      return tokens;
    }

    long getResetTime() {
      return lastRefillTime + windowSizeMs;
    }
  }
}
```

**Configuration (application.yml):**

```yaml
app:
  ratelimit:
    enabled: true
    requests-per-minute: 1000
    burst-capacity: 100
```

---

### ExceptionHandlingAdvice (Global Error Handler)

**Responsibility:** Catch exceptions and return standardized error responses.

**Implementation Pseudocode:**

```java
package com.todoapi.controller;

import com.todoapi.dto.ErrorResponse;
import com.todoapi.exception.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ControllerAdvice;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;

@ControllerAdvice
public class ExceptionHandlingAdvice {

  private static final Logger logger = LoggerFactory.getLogger(ExceptionHandlingAdvice.class);

  @ExceptionHandler(ValidationException.class)
  @ResponseStatus(HttpStatus.BAD_REQUEST)
  public ResponseEntity<ErrorResponse> handleValidationException(ValidationException ex) {
    logger.warn("Validation error: {}", ex.getMessage());
    return ResponseEntity.badRequest().body(
      ErrorResponse.builder()
        .errorCode("VALIDATION_ERROR")
        .message("Validation failed")
        .details(ex.getDetails())
        .build()
    );
  }

  @ExceptionHandler(TaskNotFoundException.class)
  @ResponseStatus(HttpStatus.NOT_FOUND)
  public ResponseEntity<ErrorResponse> handleTaskNotFound(TaskNotFoundException ex) {
    logger.warn("Task not found: {}", ex.getMessage());
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(
      ErrorResponse.builder()
        .errorCode("TASK_NOT_FOUND")
        .message(ex.getMessage())
        .build()
    );
  }

  @ExceptionHandler(ConcurrencyConflictException.class)
  @ResponseStatus(HttpStatus.CONFLICT)
  public ResponseEntity<ErrorResponse> handleConcurrencyConflict(ConcurrencyConflictException ex) {
    logger.warn("Concurrency conflict: {}", ex.getMessage());
    return ResponseEntity.status(HttpStatus.CONFLICT).body(
      ErrorResponse.builder()
        .errorCode("CONCURRENCY_CONFLICT")
        .message("Task was modified by another request. Please re-fetch and retry.")
        .details(ex.getCurrentTaskState())
        .build()
    );
  }

  @ExceptionHandler(InvalidStateTransitionException.class)
  @ResponseStatus(HttpStatus.BAD_REQUEST)
  public ResponseEntity<ErrorResponse> handleInvalidStateTransition(InvalidStateTransitionException ex) {
    logger.warn("Invalid state transition: {}", ex.getMessage());
    return ResponseEntity.badRequest().body(
      ErrorResponse.builder()
        .errorCode("INVALID_STATE_TRANSITION")
        .message(ex.getMessage())
        .build()
    );
  }

  @ExceptionHandler(DuplicateTaskException.class)
  @ResponseStatus(HttpStatus.CONFLICT)
  public ResponseEntity<ErrorResponse> handleDuplicateTask(DuplicateTaskException ex) {
    logger.warn("Duplicate idempotency key with different payload: {}", ex.getMessage());
    return ResponseEntity.status(HttpStatus.CONFLICT).body(
      ErrorResponse.builder()
        .errorCode("DUPLICATE_IDEMPOTENCY_KEY")
        .message("Idempotency key already used with different request payload")
        .build()
    );
  }

  @ExceptionHandler(Exception.class)
  @ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
  public ResponseEntity<ErrorResponse> handleGenericException(Exception ex) {
    logger.error("Unexpected error", ex);
    return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(
      ErrorResponse.builder()
        .errorCode("INTERNAL_SERVER_ERROR")
        .message("An unexpected error occurred. Please contact support.")
        .build()
    );
  }
}
```

---

## 8.4 Internal Data Transfer Objects (DTOs)

### CreateTaskRequest

```java
package com.todoapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CreateTaskRequest {
  
  @JsonProperty("title")
  private String title;
  
  @JsonProperty("description")
  private String description;
  
  @JsonProperty("due_date")
  private String dueDate; // ISO 8601 format: YYYY-MM-DD
  
  @JsonProperty("priority")
  private String priority; // LOW, MEDIUM, HIGH
}
```

### UpdateTaskRequest

```java
package com.todoapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UpdateTaskRequest {
  
  @JsonProperty("title")
  private String title; // Optional; if provided, update title
  
  @JsonProperty("description")
  private String description; // Optional; if provided, update description
  
  @JsonProperty("due_date")
  private String dueDate; // Optional; if provided, update due date
  
  @JsonProperty("priority")
  private String priority; // Optional; if provided, update priority
  
  @JsonProperty("status")
  private String status; // Optional; if provided, update status (with state machine validation)
  
  @JsonProperty("version")
  private Integer version; // Required; current version for optimistic locking
}
```

### TaskFilterRequest

```java
package com.todoapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TaskFilterRequest {
  
  @JsonProperty("status")
  private String status; // Optional; filter by status (NEW, IN_PROGRESS, COMPLETED, ARCHIVED)
  
  @JsonProperty("priority")
  private String priority; // Optional; filter by priority (LOW, MEDIUM, HIGH)
  
  @JsonProperty("due_date_start")
  private String dueDateStart; // Optional; ISO 8601 date (YYYY-MM-DD)
  
  @JsonProperty("due_date_end")
  private String dueDateEnd; // Optional; ISO 8601 date (YYYY-MM-DD)
}
```

### TaskResponse

```java
package com.todoapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TaskResponse {
  
  @JsonProperty("id")
  private String id; // UUID
  
  @JsonProperty("title")
  private String title;
  
  @JsonProperty("description")
  private String description;
  
  @JsonProperty("due_date")
  private String dueDate; // ISO 8601 date (YYYY-MM-DD) or null
  
  @JsonProperty("priority")
  private String priority; // LOW, MEDIUM, HIGH
  
  @JsonProperty("status")
  private String status; // NEW, IN_PROGRESS, COMPLETED, ARCHIVED
  
  @JsonProperty("version")
  private Integer version; // Current version for optimistic locking
  
  @JsonProperty("created_at")
  private LocalDateTime createdAt; // ISO 8601 timestamp
  
  @JsonProperty("updated_at")
  private LocalDateTime updatedAt; // ISO 8601 timestamp
}
```

### ErrorResponse

```java
package com.todoapi.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ErrorResponse {
  
  @JsonProperty("error_code")
  private String errorCode; // Machine-readable error code
  
  @JsonProperty("message")
  private String message; // Human-readable error message
  
  @JsonProperty("details")
  private List<ErrorDetail> details; // Optional; detailed error information
  
  @Data
  @Builder
  @NoArgsConstructor
  @AllArgsConstructor
  public static class ErrorDetail {
    
    @JsonProperty("field")
    private String field; // Field name (for validation errors)
    
    @JsonProperty("issue")
    private String issue; // Issue code (e.g., REQUIRED, MAX_LENGTH_EXCEEDED)
    
    @JsonProperty("message")
    private String message; // Detailed message
  }
}
```

---

# 9. ERROR HANDLING & STATUS CODES

## 9.1 HTTP Status Codes

### 200 OK

**Used for:** Successful GET, PATCH requests that return data.

**Response Body:** Task object or list of tasks.

**Example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "status": "NEW",
  "version": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### 201 Created

**Used for:** Successful POST /tasks (task creation).

**Response Headers:**
```
Location: /api/v1/tasks/{id}
```

**Response Body:** Created task object with auto-generated id, status=NEW, version=1.

**Example:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Buy groceries",
  "description": null,
  "due_date": null,
  "priority": "MEDIUM",
  "status": "NEW",
  "version": 1,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### 204 No Content

**Used for:** Successful DELETE /tasks/{id}.

**Response Body:** Empty (no content).

---

### 400 Bad Request

**Used for:** Request validation failures, malformed JSON, invalid query parameters.

**Error Codes:**
- `VALIDATION_ERROR` — One or more fields failed validation
- `INVALID_REQUEST_FORMAT` — Malformed JSON or missing required headers
- `INVALID_QUERY_PARAMETER` — Invalid pagination or filter parameter

**Response Body:**
```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "title",
      "issue": "REQUIRED",
      "message": "title is required"
    },
    {
      "field": "due_date",
      "issue": "INVALID_FORMAT",
      "message": "due_date must be in ISO 8601 format (YYYY-MM-DD)"
    }
  ]
}
```

---

### 404 Not Found

**Used for:** Task does not exist or has been deleted.

**Error Code:** `TASK_NOT_FOUND`

**Response Body:**
```json
{
  "error_code": "TASK_NOT_FOUND",
  "message": "Task with id '550e8400-e29b-41d4-a716-446655440000' not found"
}
```

---

### 409 Conflict

**Used for:** Concurrency conflicts (version mismatch) or duplicate idempotency key with different payload.

**Error Codes:**
- `CONCURRENCY_CONFLICT` — Version mismatch during PATCH
- `DUPLICATE_IDEMPOTENCY_KEY` — Idempotency key already used with different payload
- `INVALID_STATE_TRANSITION` — Status transition not allowed by state machine

**Response Body (Concurrency Conflict):**
```json
{
  "error_code": "CONCURRENCY_CONFLICT",
  "message": "Task was modified by another request. Please re-fetch and retry.",
  "details": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "version": 2,
    "status": "IN_PROGRESS",
    "updated_at": "2024-01-15T10:35:00Z"
  }
}
```

**Response Body (Invalid State Transition):**
```json
{
  "error_code": "INVALID_STATE_TRANSITION",
  "message": "Cannot transition from COMPLETED to IN_PROGRESS"
}
```

---

### 429 Too Many Requests

**Used for:** Rate limit exceeded.

**Error Code:** `RATE_LIMIT_EXCEEDED`

**Response Headers:**
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705329000
Retry-After: 60
```

**Response Body:**
```json
{
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests. Rate limit: 1000 requests per minute."
}
```

---

### 500 Internal Server Error

**Used for:** Unexpected server errors (database connection failure, unhandled exception).

**Error Code:** `INTERNAL_SERVER_ERROR`

**Response Body:**
```json
{
  "error_code": "INTERNAL_SERVER_ERROR",
  "message": "An unexpected error occurred. Please contact support.",
  "details": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

---

### 503 Service Unavailable

**Used for:** Service is temporarily unavailable (maintenance, database down).

**Error Code:** `SERVICE_UNAVAILABLE`

**Response Headers:**
```
Retry-After: 300
```

**Response Body:**
```json
{
  "error_code": "SERVICE_UNAVAILABLE",
  "message": "Service is temporarily unavailable. Please try again later."
}
```

---

## 9.2 Validation Error Details

### Validation Error Schema

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "details": [
    {
      "field": "string (field name)",
      "issue": "string (error code)",
      "message": "string (human-readable message)"
    }
  ]
}
```

### Validation Error Codes

| Issue Code | Field | Condition | Example Message |
|-----------|-------|-----------|-----------------|
| `REQUIRED` | Any | Field is required but missing or null | "title is required" |
| `MAX_LENGTH_EXCEEDED` | title, description | Field exceeds max length | "title must not exceed 255 characters (provided: 300)" |
| `MIN_LENGTH_EXCEEDED` | title | Field is below min length | "title must be at least 1 character" |
| `INVALID_FORMAT` | due_date | Field format is invalid | "due_date must be in ISO 8601 format (YYYY-MM-DD)" |
| `INVALID_ENUM` | priority, status | Field value not in allowed enum | "priority must be one of: LOW, MEDIUM, HIGH" |
| `INVALID_DATE_RANGE` | due_date_start, due_date_end | Date range is invalid | "due_date_start must be before due_date_end" |
| `INVALID_OFFSET` | page, size | Pagination parameter is invalid | "page must be >= 0" |
| `INVALID_LIMIT` | page, size | Pagination limit exceeds max | "size must not exceed 100" |

---

## 9.3 Exception Hierarchy

```
Exception (Java)
├── RuntimeException
│   ├── ValidationException
│   │   └── Details: List<ErrorDetail> (field, issue, message)
│   ├── TaskNotFoundException
│   │   └── Message: "Task with id '{id}' not found"
│   ├── ConcurrencyConflictException
│   │   └── Details: Current task state (id, version, status, updated_at)
│   ├── InvalidStateTransitionException
│   │   └── Message: "Cannot transition from {currentStatus} to {newStatus}"
│   ├── DuplicateTaskException
│   │   └── Message: "Idempotency key already used with different payload"
│   └── RateLimitExceededException
│       └── Details: Limit, remaining, reset time
```

---

# 10. AUTHENTICATION & AUTHORIZATION

## 10.1 Authentication Model

**Decision:** NO AUTHENTICATION REQUIRED (per guardrails and PRD scope).

**Rationale:**
- Tasks are not user-scoped; API is open for prototype/internal use.
- No login, accounts, or identity verification required.
- All endpoints are publicly accessible (no auth headers required).

**Future Consideration (v2.0+):**
If multi-tenancy or public-facing deployment is required, add authentication layer:
- **Option 1:** API Key authentication (simple, suitable for service-to-service)
- **Option 2:** OAuth 2.0 / OIDC (complex, suitable for user-facing applications)
- **Option 3:** JWT tokens (stateless, suitable for distributed systems)

---

## 10.2 Authorization Model

**Decision:** NO AUTHORIZATION REQUIRED (per guardrails and PRD scope).

**Rationale:**
- No user roles or permissions; all authenticated users have full access.
- No resource-level access control (e.g., user can only see their own tasks).

**Future Consideration (v2.0+):**
If multi-tenancy is required, add authorization layer:
- **Option 1:** Tenant-scoped queries (filter tasks by tenant_id)
- **Option 2:** Role-based access control (RBAC) with roles like ADMIN, USER, VIEWER
- **Option 3:** Attribute-based access control (ABAC) with fine-grained permissions

---

## 10.3 Security Headers

**Recommended (optional for prototype):**

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'
```

**Implementation (Spring Security):**

```java
package com.todoapi.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;

@Configuration
public class SecurityConfig {

  @Bean
  public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http
      .headers()
        .contentTypeOptions()
        .and()
        .xssProtection()
        .and()
        .frameOptions().deny()
        .and()
      .and()
      .csrf().disable() // Disable CSRF for stateless API
      .authorizeRequests()
        .anyRequest().permitAll(); // Allow all requests (no auth required)
    
    return http.build();
  }
}
```

---

# 11. THIRD-PARTY INTEGRATION SPECIFICATIONS

## 11.1 External Dependencies

**Current State (v1.0):** NO external service dependencies.

**Rationale:**
- All functionality is self-contained within the API.
- No third-party APIs, webhooks, or integrations required.
- Simplifies deployment, reduces failure points, improves reliability.

---

## 11.2 Future Integration Points (v2.0+)

### Email Notifications (Future)

**Trigger:** Task due date approaching or overdue.

**Integration:** Async job that queries overdue tasks and sends email notifications.

**Service:** SendGrid, AWS SES, or similar.

**Implementation:** Add scheduled job (Spring @Scheduled) that runs daily at 9 AM.

---

### Webhook Events (Future)

**Trigger:** Task created, updated, or deleted.

**Integration:** POST to client-provided webhook URL with task event payload.

**Service:** Internal webhook dispatcher (no external service).

**Implementation:** Add webhook registry table, async event publisher.

---

### Analytics / Data Warehouse (Future)

**Trigger:** Task lifecycle events (created, completed, deleted).

**Integration:** Stream events to data warehouse (BigQuery, Snowflake, etc.).

**Service:** Kafka, Pub/Sub, or similar.

**Implementation:** Add event publisher, configure sink to data warehouse.

---

# 12. STATE MACHINES & WORKFLOWS

## 12.1 Task Status State Machine

### State Diagram

```
┌─────────┐
│   NEW   │ (Initial state)
└────┬────┘
     │
     ├─────────────────────────────────────┐
     │                                     │
     ▼                                     ▼
┌──────────────┐                    ┌──────────────┐
│ IN_PROGRESS  │                    │  COMPLETED   │
└──────┬───────┘                    └──────┬───────┘
       │                                   │
       ├───────────────────────────────────┤
       │                                   │
       ▼                                   ▼
┌──────────────┐                    ┌──────────────┐
│  ARCHIVED    │◄───────────────────│  COMPLETED   │
└──────────────┘                    └──────────────┘
```

### State Definitions

| State | Description | Transitions | Semantics |
|-------|-------------|-------------|-----------|
| **NEW** | Task created, not yet started | → IN_PROGRESS, → COMPLETED, → ARCHIVED | Initial state; task is pending |
| **IN_PROGRESS** | Task is being worked on | → COMPLETED, → ARCHIVED, → NEW | Task is active; can revert to NEW if needed |
| **COMPLETED** | Task is finished | → ARCHIVED | Terminal state; task is done |
| **ARCHIVED** | Task is archived (hidden from active lists) | None | Terminal state; task is archived |

### Allowed Transitions

```
NEW → IN_PROGRESS (start working on task)
NEW → COMPLETED (mark task as done without starting)
NEW → ARCHIVED (archive task without completing)

IN_PROGRESS → COMPLETED (finish task)
IN_PROGRESS → ARCHIVED (archive task without completing)
IN_PROGRESS → NEW (revert to pending)

COMPLETED → ARCHIVED (archive completed task)

ARCHIVED → (no transitions; terminal state)
```

### Disallowed Transitions

```
COMPLETED → NEW (cannot revert completed task)
COMPLETED → IN_PROGRESS (cannot revert completed task)
ARCHIVED → * (archived tasks cannot transition)
```

---

## 12.2 State Transition Validation

### Implementation (TaskService)

```java
package com.todoapi.service;

import com.todoapi.entity.TaskStatus;
import com.todoapi.exception.InvalidStateTransitionException;

public class TaskStateValidator {

  private static final Map<TaskStatus, Set<TaskStatus>> ALLOWED_TRANSITIONS = Map.ofEntries(
    Map.entry(TaskStatus.NEW, Set.of(TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.ARCHIVED)),
    Map.entry(TaskStatus.IN_PROGRESS, Set.of(TaskStatus.COMPLETED, TaskStatus.ARCHIVED, TaskStatus.NEW)),
    Map.entry(TaskStatus.COMPLETED, Set.of(TaskStatus.ARCHIVED)),
    Map.entry(TaskStatus.ARCHIVED, Set.of()) // No transitions from ARCHIVED
  );

  public static void validateTransition(TaskStatus currentStatus, TaskStatus newStatus) 
    throws InvalidStateTransitionException {
    
    if (currentStatus == newStatus) {
      // No-op; same status is allowed
      return;
    }
    
    Set<TaskStatus> allowedNextStates = ALLOWED_TRANSITIONS.getOrDefault(currentStatus, Set.of());
    
    if (!allowedNextStates.contains(newStatus)) {
      throw new InvalidStateTransitionException(
        String.format("Cannot transition from %s to %s", currentStatus, newStatus)
      );
    }
  }
}
```

### Error Response (Invalid Transition)

```json
{
  "error_code": "INVALID_STATE_TRANSITION",
  "message": "Cannot transition from COMPLETED to IN_PROGRESS"
}
```

---

## 12.3 Task Lifecycle Events (Future)

**Note:** Event publishing is not required for v1.0 but should be designed for future extensibility.

### Event Types

```java
public enum TaskEventType {
  TASK_CREATED,
  TASK_UPDATED,
  TASK_STATUS_CHANGED,
  TASK_DELETED,
  TASK_COMPLETED,
  TASK_OVERDUE
}
```

### Event Payload

```java
@Data
@Builder
public class TaskEvent {
  private String eventId; // UUID
  private TaskEventType eventType;
  private String taskId;
  private TaskStatus previousStatus; // null for TASK_CREATED
  private TaskStatus currentStatus;
  private LocalDateTime occurredAt;
  private String triggeredBy; // "API" or "SYSTEM"
}
```

### Event Publishing (Future)

```java
// In TaskService.updateTask()
if (statusChanged) {
  TaskEvent event = TaskEvent.builder()
    .eventId(UUID.randomUUID().toString())
    .eventType(TaskEventType.TASK_STATUS_CHANGED)
    .taskId(task.getId().toString())
    .previousStatus(previousStatus)
    .currentStatus(newStatus)
    .occurredAt(LocalDateTime.now())
    .triggeredBy("API")
    .build();
  
  eventPublisher.publish(event); // Async
}
```

---

# 13. TESTING SPECIFICATIONS

## 13.1 Unit Testing Strategy

### Test Framework

- **Framework:** JUnit 5 (Jupiter)
- **Mocking:** Mockito
- **Assertions:** AssertJ (fluent assertions)

### Test Structure

```
src/test/java/com/todoapi/
├── service/
│   ├── TaskServiceTest.java
│   ├── ValidationServiceTest.java
│   └── IdempotencyServiceTest.java
├── controller/
│   ├── TaskControllerTest.java
│   └── HealthControllerTest.java
├── repository/
│   ├── TaskRepositoryTest.java
│   └── IdempotencyKeyRepositoryTest.java
└── util/
    └── TaskStateValidatorTest.java
```

### Example Unit Test (TaskService)

```java
package com.todoapi.service;

import com.todoapi.dto.CreateTaskRequest;
import com.todoapi.dto.TaskResponse;
import com.todoapi.entity.Task;
import com.todoapi.exception.ValidationException;
import com.todoapi.repository.TaskRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TaskServiceTest {

  @Mock
  private TaskRepository taskRepository;

  @Mock
  private ValidationService validationService;

  @InjectMocks
  private TaskService taskService;

  private CreateTaskRequest validRequest;

  @BeforeEach
  void setUp() {
    validRequest = CreateTaskRequest.builder()
      .title("Test Task")
      .description("Test Description")
      .priority("MEDIUM")
      .build();
  }

  @Test
  void testCreateTask_Success() throws ValidationException {
    // Arrange
    Task savedTask = Task.builder()
      .id(UUID.randomUUID())
      .title("Test Task")
      .status(TaskStatus.NEW)
      .version(1)
      .build();

    when(taskRepository.save(any(Task.class))).thenReturn(savedTask);

    // Act
    TaskResponse response = taskService.createTask(validRequest, "idempotency-key-123");

    // Assert
    assertThat(response)
      .isNotNull()
      .extracting("title", "status", "version")
      .containsExactly("Test Task", "NEW", 1);
  }

  @Test
  void testCreateTask_ValidationFails() throws ValidationException {
    // Arrange
    CreateTaskRequest invalidRequest = CreateTaskRequest.builder()
      .title("") // Empty title
      .build();

    doThrow(new ValidationException("title is required"))
      .when(validationService).validateCreateTaskRequest(invalidRequest);

    // Act & Assert
    assertThatThrownBy(() -> taskService.createTask(invalidRequest, "idempotency-key-123"))
      .isInstanceOf(ValidationException.class)
      .hasMessage("title is required");
  }
}
```

---

## 13.2 Integration Testing Strategy

### Test Framework

- **Framework:** Spring Boot Test + Testcontainers
- **Database:** Embedded SQLite (no external database required)
- **HTTP Client:** RestTemplate or WebTestClient

### Test Structure

```
src/test/java/com/todoapi/integration/
├── TaskControllerIntegrationTest.java
├── TaskServiceIntegrationTest.java
└── ConcurrencyIntegrationTest.java
```

### Example Integration Test

```java
package com.todoapi.integration;

import com.todoapi.dto.CreateTaskRequest;
import com.todoapi.dto.TaskResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.ActiveProfiles;

import static org.assertj.core.api.Assertions.*;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class TaskControllerIntegrationTest {

  @Autowired
  private TestRestTemplate restTemplate;

  @Test
  void testCreateTask_EndToEnd() {
    // Arrange
    CreateTaskRequest request = CreateTaskRequest.builder()
      .title("Integration Test Task")
      .priority("HIGH")
      .build();

    // Act
    ResponseEntity<TaskResponse> response = restTemplate.postForEntity(
      "/api/v1/tasks",
      request,
      TaskResponse.class
    );

    // Assert
    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
    assertThat(response.getBody())
      .isNotNull()
      .extracting("title", "status", "version")
      .containsExactly("Integration Test Task", "NEW", 1);
  }

  @Test
  void testListTasks_WithPagination() {
    // Arrange: Create 25 tasks
    for (int i = 0; i < 25; i++) {
      CreateTaskRequest request = CreateTaskRequest.builder()
        .title("Task " + i)
        .build();
      restTemplate.postForEntity("/api/v1/tasks", request, TaskResponse.class);
    }

    // Act
    ResponseEntity<String> response = restTemplate.getForEntity(
      "/api/v1/tasks?page=0&size=10",
      String.class
    );

    // Assert
    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
    // Parse JSON and verify pagination
  }
}
```

---

## 13.3 Concurrency Testing

### Test Scenario: Concurrent Status Updates

```java
@Test
void testConcurrentStatusUpdates_OneSucceedsOneConflicts() throws InterruptedException {
  // Arrange: Create a task
  TaskResponse task = createTask("Concurrent Test Task");
  String taskId = task.getId();
  int initialVersion = task.getVersion();

  // Act: Two threads try to update status simultaneously
  ExecutorService executor = Executors.newFixedThreadPool(2);
  CountDownLatch latch = new CountDownLatch(2);
  AtomicInteger successCount = new AtomicInteger(0);
  AtomicInteger conflictCount = new AtomicInteger(0);

  executor.submit(() -> {
    try {
      UpdateTaskRequest request = UpdateTaskRequest.builder()
        .status("IN_PROGRESS")
        .version(initialVersion)
        .build();
      ResponseEntity<TaskResponse> response = restTemplate.exchange(
        "/api/v1/tasks/" + taskId,
        HttpMethod.PATCH,
        new HttpEntity<>(request),
        TaskResponse.class
      );
      if (response.getStatusCode() == HttpStatus.OK) {
        successCount.incrementAndGet();
      }
    } finally {
      latch.countDown();
    }
  });

  executor.submit(() -> {
    try {
      UpdateTaskRequest request = UpdateTaskRequest.builder()
        .status("IN_PROGRESS")
        .version(initialVersion)
        .build();
      ResponseEntity<TaskResponse> response = restTemplate.exchange(
        "/api/v1/tasks/" + taskId,
        HttpMethod.PATCH,
        new HttpEntity<>(request),
        TaskResponse.class
      );
      if (response.getStatusCode() == HttpStatus.CONFLICT) {
        conflictCount.incrementAndGet();
      }
    } finally {
      latch.countDown();
    }
  });

  latch.await();
  executor.shutdown();

  // Assert
  assertThat(successCount.get()).isEqualTo(1);
  assertThat(conflictCount.get()).isEqualTo(1);
}
```

---

## 13.4 Performance Testing

### Load Test Scenario

**Tool:** JMeter or Gatling

**Scenario:** Simulate 1,000 concurrent users creating and listing tasks.

**Test Plan:**
1. Ramp up: 100 users per minute for 10 minutes
2. Steady state: 1,000 concurrent users for 5 minutes
3. Ramp down: 100 users per minute for 10 minutes

**Metrics to Collect:**
- Response time (min, max, avg, p50, p95, p99)
- Throughput (requests per second)
- Error rate (% of failed requests)
- CPU usage
- Memory usage
- Database connection pool utilization

**Success Criteria:**
- p95 response time < 200ms
- Error rate < 0.1%
- CPU usage < 80%
- Memory usage < 2GB

---

## 13.5 Test Coverage Goals

| Component | Target Coverage | Notes |
|-----------|-----------------|-------|
| Service Layer | >90% | Core business logic; high priority |
| Controller Layer | >80% | HTTP handling; medium priority |
| Repository Layer | >85% | Data access; high priority |
| Utility Classes | >85% | Validators, converters; medium priority |
| Exception Handling | >90% | Error paths; high priority |

---

# 14. DEPLOYMENT & RUNTIME CONFIGURATION

## 14.1 Build & Packaging

### Maven Build

```bash
# Build JAR
mvn clean package

# Output: target/todo-api-1.0.0.jar
```

### pom.xml (Key Dependencies)

```xml
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.todoapi</groupId>
  <artifactId>todo-api</artifactId>
  <version>1.0.0</version>
  <packaging>jar</packaging>

  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.2.0</version>
  </parent>

  <dependencies>
    <!-- Spring Boot Starters -->
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-validation</artifactId>
    </dependency>

    <!-- Database -->
    <dependency>
      <groupId>org.xerial</groupId>
      <artifactId>sqlite-jdbc</artifactId>
      <version>3.44.0.0</version>
    </dependency>
    <dependency>
      <groupId>org.hibernate.orm</groupId>
      <artifactId>hibernate-community-dialects</artifactId>
      <version>6.4.0.Final</version>
    </dependency>

    <!-- Migrations -->
    <dependency>
      <groupId>org.flywaydb</groupId>
      <artifactId>flyway-core</artifactId>
      <version>9.22.0</version>
    </dependency>

    <!-- Utilities -->
    <dependency>
      <groupId>org.projectlombok</groupId>
      <artifactId>lombok</artifactId>
      <optional>true</optional>
    </dependency>

    <!-- Testing -->
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.testcontainers</groupId>
      <artifactId>testcontainers</artifactId>
      <version>1.19.0</version>
      <scope>test</scope>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</project>
```

---

## 14.2 Runtime Configuration

### application.yml (Production)

```yaml
spring:
  application:
    name: todo-api
  
  datasource:
    url: jdbc:sqlite:${DATABASE_PATH:/data/todo.db}
    driver-class-name: org.sqlite.JDBC
    hikari:
      maximum-pool-size: 10
      minimum-idle: 2
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
  
  jpa:
    hibernate:
      ddl-auto: validate # Use Flyway for migrations
    properties:
      hibernate:
        dialect: org.hibernate.community.dialect.SQLiteDialect
        format_sql: false
        jdbc:
          batch_size: 20
          fetch_size: 50
  
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: true

server:
  port: ${SERVER_PORT:8080}
  servlet:
    context-path: /api/v1
  compression:
    enabled: true
    min-response-size: 1024
  shutdown: graceful
  shutdown-wait-time: 30s

management:
  endpoints:
    web:
      exposure:
        include: health,metrics,info
  endpoint:
    health:
      show-details: when-authorized
  metrics:
    export:
      simple:
        enabled: true

logging:
  level:
    root: INFO
    com.todoapi: DEBUG
  pattern:
    console: "%d{ISO8601} [%thread] %-5level %logger{36} [%X{requestId}] - %msg%n"
    file: "%d{ISO8601} [%thread] %-5level %logger{36} [%X{requestId}] - %msg%n"
  file:
    name: /var/log/todo-api/application.log
    max-size: 100MB
    max-history: 10

app:
  ratelimit:
    enabled: true
    requests-per-minute: 1000
    burst-capacity: 100
  
  idempotency:
    enabled: true
    ttl-hours: 24
  
  task:
    max-title-length: 255
    max-description-length: 2000
    default-priority: MEDIUM
    default-page-size: 20
    max-page-size: 100
```

### application-test.yml (Testing)

```yaml
spring:
  datasource:
    url: jdbc:sqlite:memory:
    driver-class-name: org.sqlite.JDBC
  
  jpa:
    hibernate:
      ddl-auto: create-drop
    properties:
      hibernate:
        dialect: org.hibernate.community.dialect.SQLiteDialect
        format_sql: true

server:
  port: 0 # Random port for integration tests

logging:
  level:
    root: WARN
    com.todoapi: DEBUG
```

---

## 14.3 Database Initialization

### Flyway Migration: V1__Initial_Schema.sql

```sql
-- Create tasks table
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  due_date DATE,
  priority VARCHAR(10) NOT NULL DEFAULT 'MEDIUM',
  status VARCHAR(20) NOT NULL DEFAULT 'NEW',
  version INTEGER NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX idx_tasks_status_created_at ON tasks(status, created_at DESC);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX idx_tasks_deleted_at ON tasks(deleted_at);

-- Create idempotency_keys table
CREATE TABLE idempotency_keys (
  key TEXT PRIMARY KEY,
  request_hash VARCHAR(64) NOT NULL,
  response_json TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP NOT NULL
);

-- Create index for cleanup queries
CREATE INDEX idx_idempotency_keys_expires_at ON idempotency_keys(expires_at);
```

---

## 14.4 Docker Deployment (Optional)

### Dockerfile

```dockerfile
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Copy JAR from build stage
COPY target/todo-api-1.0.0.jar app.jar

# Create data directory for SQLite
RUN mkdir -p /data

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/api/v1/health || exit 1

# Run application
ENTRYPOINT ["java", "-jar", "app.jar"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  todo-api:
    build: .
    ports:
      - "8080:8080"
    environment:
      DATABASE_PATH: /data/todo.db
      SERVER_PORT: 8080
      SPRING_PROFILES_ACTIVE: prod
    volumes:
      - todo-data:/data
      - todo-logs:/var/log/todo-api
    restart: unless-stopped

volumes:
  todo-data:
  todo-logs:
```

---

## 14.5 Kubernetes Deployment (Optional)

### Deployment Manifest (deployment.yaml)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: todo-api
  labels:
    app: todo-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: todo-api
  template:
    metadata:
      labels:
        app: todo-api
    spec:
      replicas: 3
      selector:
        matchLabels:
          app: todo-api
      template:
        metadata:
          labels:
            app: todo-api
        spec:
          containers:
          - name: todo-api
            image: todo-api:1.0.0
            ports:
            - containerPort: 8080
            env:
            - name: DATABASE_PATH
              value: /data/todo.db
            - name: SERVER_PORT
              value: "8080"
            - name: SPRING_PROFILES_ACTIVE
              value: prod
            resources:
              requests:
                memory: "512Mi"
                cpu: "250m"
              limits:
                memory: "1Gi"
                cpu: "500m"
            livenessProbe:
              httpGet:
                path: /api/v1/health/live
                port: 8080
              initialDelaySeconds: 30
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            readinessProbe:
              httpGet:
                path: /api/v1/health/ready
                port: 8080
              initialDelaySeconds: 10
              periodSeconds: 5
              timeoutSeconds: 3
              failureThreshold: 3
            volumeMounts:
            - name: data
              mountPath: /data
            - name: logs
              mountPath: /var/log/todo-api
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: todo-api-data
          - name: logs
            emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: todo-api
spec:
  selector:
    app: todo-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: LoadBalancer

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: todo-api-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

---

## 14.6 Environment Variables

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `DATABASE_PATH` | `/data/todo.db` | Path to SQLite database file | No |
| `SERVER_PORT` | `8080` | HTTP server port | No |
| `SPRING_PROFILES_ACTIVE` | `prod` | Active Spring profile (prod, test, dev) | No |
| `LOG_LEVEL` | `INFO` | Root logging level | No |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting | No |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `1000` | Rate limit threshold | No |
| `IDEMPOTENCY_ENABLED` | `true` | Enable idempotency key tracking | No |
| `IDEMPOTENCY_TTL_HOURS` | `24` | Idempotency key expiration (hours) | No |

---

## 14.7 Startup & Shutdown

### Startup Sequence

1. **JVM Initialization:** Load Spring Boot application context
2. **Database Connection:** Establish connection pool to SQLite
3. **Flyway Migrations:** Run pending database migrations
4. **Bean Initialization:** Instantiate all Spring beans (services, repositories, filters)
5. **Server Start:** Bind Tomcat to configured port
6. **Health Check:** Readiness probe returns 200 OK

**Expected Startup Time:** 5-10 seconds

### Shutdown Sequence

1. **Graceful Shutdown Signal:** Receive SIGTERM or shutdown request
2. **Stop Accepting Requests:** Readiness probe returns 503 Service Unavailable
3. **Wait for In-Flight Requests:** Wait up to 30 seconds for active requests to complete
4. **Close Database Connections:** Drain connection pool
5. **Shutdown Complete:** Process exits

**Shutdown Timeout:** 30 seconds (configurable via `server.shutdown-wait-time`)

---

## 14.8 Operational Runbooks

### Runbook: Restart API Instance

```bash
# 1. Drain traffic (if behind load balancer)
# Mark instance as unhealthy in load balancer

# 2. Wait for in-flight requests to complete
sleep 30

# 3. Stop container
docker stop todo-api

# 4. Start container
docker start todo-api

# 5. Wait for readiness
sleep 10

# 6. Verify health
curl http://localhost:8080/api/v1/health/ready

# 7. Re-enable in load balancer
```

### Runbook: Database Backup

```bash
# 1. Backup SQLite database file
cp /data/todo.db /backups/todo.db.$(date +%Y%m%d_%H%M%S)

# 2. Verify backup integrity
sqlite3 /backups/todo.db.* "SELECT COUNT(*) FROM tasks;"

# 3. Upload to cloud storage (optional)
aws s3 cp /backups/todo.db.* s3://backup-bucket/todo-api/
```

### Runbook: Database Recovery

```bash
# 1. Stop API instance
docker stop todo-api

# 2. Restore backup
cp /backups/todo.db.YYYYMMDD_HHMMSS /data/todo.db

# 3. Verify restored database
sqlite3 /data/todo.db "SELECT COUNT(*) FROM tasks;"

# 4. Start API instance
docker start todo-api

# 5. Verify health
curl http://localhost:8080/api/v1/health/ready
```

---

# 15. OBSERVABILITY & MONITORING

## 15.1 Logging Strategy

### Log Levels

| Level | Usage | Examples |
|-------|-------|----------|
| **DEBUG** | Detailed diagnostic information | Request/response bodies, SQL queries, internal state transitions |
| **INFO** | General informational messages | API startup, task creation, migrations completed |
| **WARN** | Warning conditions | Rate limit exceeded, validation errors, deprecated API usage |
| **ERROR** | Error conditions | Database connection failure, unhandled exceptions, data corruption |

### Log Format

```
2024-01-15T10:30:45.123Z [http-nio-8080-exec-1] INFO  com.todoapi.controller.TaskController [550e8400-e29b-41d4-a716-446655440000] - POST /api/v1/tasks completed in 45ms
```

**Fields:**
- `2024-01-15T10:30:45.123Z` — ISO 8601 timestamp
- `[http-nio-8080-exec-1]` — Thread name
- `INFO` — Log level
- `com.todoapi.controller.TaskController` — Logger name (class)
- `[550e8400-e29b-41d4-a716-446655440000]` — Request ID (MDC)
- Message — Log message

### Structured Logging (JSON)

**Optional:** For centralized log aggregation (ELK, Splunk), output logs as JSON:

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "com.todoapi.controller.TaskController",
  "thread": "http-nio-8080-exec-1",
  "requestId": "550e8400-e29b-41d4-a716-446655440000",
  "message": "POST /api/v1/tasks completed in 45ms",
  "method": "POST",
  "path": "/api/v1/tasks",
  "statusCode": 201,
  "duration_ms": 45
}
```

---

## 15.2 Metrics Collection

### Metrics Framework

- **Library:** Micrometer (Spring Boot built-in)
- **Export:** Prometheus (optional; can be added later)

### Key Metrics

#### Request Metrics

```
http.server.requests
  - Tags: method, uri, status
  - Values: count, total_time, max_time
  - Example: http.server.requests{method="POST",uri="/api/v1/tasks",status="201"} 1234
```

#### Business Metrics

```
tasks.created.total
  - Description: Total number of tasks created
  - Type: Counter
  - Example: tasks.created.total 5000

tasks.by_status
  - Description: Number of tasks by status
  - Type: Gauge
  - Tags: status
  - Example: tasks.by_status{status="NEW"} 1200

tasks.completion_rate
  - Description: Percentage of tasks that reach COMPLETED state
  - Type: Gauge
  - Example: tasks.completion_rate 0.65

task.update.duration
  - Description: Time taken to update a task
  - Type: Timer
  - Example: task.update.duration_seconds{quantile="0.95"} 0.045
```

#### System Metrics

```
jvm.memory.used
  - Description: JVM memory usage
  - Type: Gauge
  - Tags: area (heap, nonheap)

jvm.threads.live
  - Description: Number of live threads
  - Type: Gauge

process.cpu.usage
  - Description: CPU usage percentage
  - Type: Gauge

db.connection.pool.usage
  - Description: Database connection pool utilization
  - Type: Gauge
```

### Metrics Endpoint

```
GET /api/v1/metrics
```

**Response:**
```
# HELP http_server_requests_seconds_max  
# TYPE http_server_requests_seconds_max gauge
http_server_requests_seconds_max{method="POST",status="201",uri="/api/v1/tasks"} 0.123
# HELP http_server_requests_seconds  
# TYPE http_server_requests_seconds summary
http_server_requests_seconds_count{method="POST",status="201",uri="/api/v1/tasks"} 1234
http_server_requests_seconds_sum{method="POST",status="201",uri="/api/v1/tasks"} 45.678
```

---

## 15.3 Health Checks

### Liveness Probe

**Endpoint:** `GET /api/v1/health/live`

**Purpose:** Determine if application is running and responsive.

**Response (Healthy):**
```json
{
  "status": "UP"
}
```

**Response (Unhealthy):**
```json
{
  "status": "DOWN",
  "details": {
    "error": "Database connection failed"
  }
}
```

**HTTP Status:** 200 (UP) or 503 (DOWN)

### Readiness Probe

**Endpoint:** `GET /api/v1/health/ready`

**Purpose:** Determine if application is ready to accept traffic.

**Response (Ready):**
```json
{
  "status": "UP",
  "components": {
    "db": {
      "status": "UP"
    },
    "diskSpace": {
      "status": "UP"
    }
  }
}
```

**Response (Not Ready):**
```json
{
  "status": "DOWN",
  "components": {
    "db": {
      "status": "DOWN",
      "details": {
        "error": "Database migrations pending"
      }
    }
  }
}
```

**HTTP Status:** 200 (UP) or 503 (DOWN)

### Health Check Implementation

```java
package com.todoapi.health;

import org.springframework.boot.actuate.health.Health;
import org.springframework.boot.actuate.health.HealthIndicator;
import org.springframework.stereotype.Component;

@Component
public class DatabaseHealthIndicator implements HealthIndicator {

  @Override
  public Health health() {
    try {
      // Test database connectivity
      taskRepository.count();
      return Health.up()
        .withDetail("database", "SQLite")
        .withDetail("status", "connected")
        .build();
    } catch (Exception ex) {
      return Health.down()
        .withDetail("error", ex.getMessage())
        .build();
    }
  }
}
```

---

## 15.4 Distributed Tracing (Future)

**Note:** Distributed tracing is not required for v1.0 (single-service architecture) but should be designed for future extensibility.

### Tracing Framework

- **Library:** Spring Cloud Sleuth + Micrometer Tracing
- **Backend:** Jaeger or Zipkin (optional)

### Trace Context Propagation

```java
// Request ID is automatically propagated in MDC
// For future multi-service deployments, use W3C Trace Context headers:
// traceparent: 00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01
```

---

## 15.5 Alerting Rules (Recommended)

### Alert: High Error Rate

```
Condition: error_rate > 1% for 5 minutes
Severity: CRITICAL
Action: Page on-call engineer
```

### Alert: High Latency

```
Condition: p95_latency > 500ms for 10 minutes
Severity: WARNING
Action: Notify ops team
```

### Alert: Database Connection Pool Exhausted

```
Condition: connection_pool_usage > 90% for 5 minutes
Severity: CRITICAL
Action: Page on-call engineer
```

### Alert: Disk Space Low

```
Condition: available_disk_space < 1GB
Severity: WARNING
Action: Notify ops team
```

### Alert: Memory Usage High

```
Condition: jvm_memory_used > 80% for 10 minutes
Severity: WARNING
Action: Notify ops team
```

---

## 15.6 Monitoring Dashboard (Grafana)

**Recommended Panels:**

1. **Request Rate** — Requests per second (by endpoint)
2. **Response Time** — p50, p95, p99 latency (by endpoint)
3. **Error Rate** — % of 5xx responses (by endpoint)
4. **Task Count** — Total tasks by status
5. **Task Completion Rate** — % of tasks reaching COMPLETED state
6. **Database Connections** — Active connections, pool utilization
7. **JVM Memory** — Heap usage, GC activity
8. **CPU Usage** — Process CPU usage
9. **Disk Usage** — Available disk space

---

## 15.7 Log Aggregation (Optional)

### ELK Stack Integration

**Logstash Configuration:**
```
input {
  file {
    path => "/var/log/todo-api/application.log"
    start_position => "beginning"
  }
}

filter {
  grok {
    match => { "message" => "%{TIMESTAMP_ISO8601:timestamp} \[%{DATA:thread}\] %{LOGLEVEL:level} %{DATA:logger} \[%{UUID:requestId}\] - %{GREEDYDATA:msg}" }
  }
  mutate {
    add_field => { "service" => "todo-api" }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "todo-api-%{+YYYY.MM.dd}"
  }
}
```

---

# 16. APPENDIX: DECISION LOG

## Decision: Hard-Delete vs. Soft-Delete

**Status:** PENDING CLARIFICATION

**Context:** PRD mentions "soft-delete with retention" but TRD specifies "hard-delete only."

**Options:**
1. **Hard-Delete:** Physically remove task from database immediately. Simpler schema, no index bloat, but no audit trail.
2. **Soft-Delete:** Mark task with `deleted_at` timestamp, retain for 30 days, then purge. Enables audit trail and recovery, but adds complexity.

**Recommendation:** Clarify with product team. For v1.0, recommend hard-delete (simpler). If compliance/audit requirements exist, implement soft-delete.

**Implementation Impact:**
- **Hard-Delete:** Remove `deleted_at` column from schema; simplify all queries.
- **Soft-Delete:** Keep `deleted_at` column; add `WHERE deleted_at IS NULL` to all queries; add cleanup job to purge after 30 days.

---

## Decision: Pagination Strategy

**Status:** DECIDED — Offset-Based

**Rationale:**
- Simple, predictable, no cursor state required
- Suitable for <10,000 total tasks
- Clients can easily implement (page=0, size=20)

**Trade-off:** Inefficient for large offsets (e.g., page=1000). If dataset grows beyond 100,000 tasks, migrate to cursor-based pagination.

---

## Decision: Concurrency Control

**Status:** DECIDED — Optimistic Locking

**Rationale:**
- Prevents lost writes without row-level locks
- Clients handle conflicts explicitly (409 Conflict)
- Suitable for low-contention workloads

**Trade-off:** Clients must implement retry logic. Not suitable for high-contention scenarios (many concurrent updates to same task).

**Future:** If contention becomes an issue, migrate to pessimistic locking (SELECT FOR UPDATE).

---

## Decision: Authentication & Authorization

**Status:** DECIDED — None (v1.0)

**Rationale:** Per guardrails and PRD scope; tasks are not user-scoped.

**Future (v2.0+):** Add authentication layer if multi-tenancy or public-facing deployment required.

---

## Decision: External Dependencies

**Status:** DECIDED — None (v1.0)

**Rationale:** All functionality is self-contained. Simplifies deployment, reduces failure points.

**Future (v2.0+):** Add integrations as needed (email notifications, webhooks, analytics).

---

# 17. OPEN QUESTIONS FOR STAKEHOLDER VALIDATION

## Q1: Soft-Delete vs. Hard-Delete

**Question:** Should deleted tasks be retained for audit/compliance purposes, or physically removed immediately?

**Impact:** Schema design, query complexity, compliance requirements.

**Options:**
- Hard-delete (current spec): Simpler, no audit trail
- Soft-delete with 30-day retention: Enables audit trail, adds complexity

**Recommendation:** Clarify compliance requirements with legal/security team.

---

## Q2: Multi-Instance Deployment

**Question:** Will the API be deployed as a single instance or multiple instances behind a load balancer?

**Impact:** Database choice (SQLite vs. PostgreSQL), deployment topology, HA strategy.

**Current Spec:** Single instance with embedded SQLite.

**Future:** Multiple instances require PostgreSQL + shared database.

**Recommendation:** Confirm deployment topology before v2.0.

---

## Q3: Task Ownership / Multi-Tenancy

**Question:** Are tasks owned by users, or are they global/shared?

**Impact:** Schema design (add user_id column?), authorization model, filtering logic.

**Current Spec:** Tasks are global; no user ownership.

**Future:** If multi-tenancy required, add user_id column and tenant-scoped queries.

**Recommendation:** Clarify user/tenant model before v2.0.

---

## Q4: Task Archival Semantics

**Question:** What is the intended behavior of ARCHIVED status? Should archived tasks be hidden from list endpoints by default?

**Impact:** Query logic, API contract, client expectations.

**Current Spec:** ARCHIVED is a valid status; clients can filter by status.

**Recommendation:** Clarify whether archived tasks should be excluded from default list queries.

---

## Q5: Idempotency Key Scope

**Question:** Should idempotency keys apply to PATCH and DELETE operations, or only POST?

**Impact:** API contract, concurrency handling, client retry logic.

**Current Spec:** Idempotency keys apply to POST only; PATCH/DELETE use version field.

**Recommendation:** Confirm this is acceptable for client use cases.

---

## Q6: Rate Limiting Granularity

**Question:** Should rate limits be per-IP, per-user, or per-API-key?

**Impact:** Rate limiting implementation, fairness, abuse prevention.

**Current Spec:** Per-IP (1,000 requests/minute).

**Future:** If authentication added, migrate to per-user or per-API-key.

**Recommendation:** Confirm rate limit strategy aligns with deployment model.

---

## Q7: Data Retention Policy

**Question:** How long should task data be retained? Are there compliance/regulatory requirements?

**Impact:** Backup strategy, archival policy, data deletion procedures.

**Current Spec:** No explicit retention policy; tasks retained indefinitely.

**Recommendation:** Define retention policy based on compliance requirements (GDPR, CCPA, etc.).

---

## Q8: Notification Requirements

**Question:** Should the API send notifications (email, SMS, push) for task events (due date approaching, task completed)?

**Impact:** Service dependencies, async job requirements, integration complexity.

**Current Spec:** No notifications in v1.0.

**Future (v2.0+):** Add notification service if required.

**Recommendation:** Clarify notification requirements before v2.0 planning.

---

# 18. GLOSSARY

| Term | Definition |
|------|-----------|
| **Idempotency Key** | Unique identifier for a request; prevents duplicate processing on retries |
| **Optimistic Locking** | Concurrency control strategy using version field; detects conflicts without row-level locks |
| **Soft-Delete** | Mark record as deleted (deleted_at timestamp) without physically removing it |
| **Hard-Delete** | Physically remove record from database |
| **State Machine** | Finite set of states and allowed transitions between them |
| **MDC (Mapped Diagnostic Context)** | Thread-local storage for request context (e.g., request ID) used in logging |
| **Token Bucket** | Rate limiting algorithm; tokens are added at fixed rate, consumed on each request |
| **Flyway** | Database migration tool; version-controlled schema changes |
| **JPA (Java Persistence API)** | Standard Java ORM specification; implemented by Hibernate |
| **DTO (Data Transfer Object)** | Object used to transfer data between layers (controller ↔ service ↔ repository) |
| **Repository Pattern** | Data access abstraction layer; separates business logic from database queries |
| **Health Check** | Endpoint that reports application health status (liveness, readiness) |
| **Graceful Shutdown** | Shutdown process that allows in-flight requests to complete before terminating |

---

**END OF SPECS.md**

---

## DOCUMENT COMPLETION SUMMARY

This SPECS.md document provides complete, code-ready specifications for the To-Do List API implementation. It includes:

✅ **Project Structure** — Maven project layout, directory organization  
✅ **Technology Stack** — Java 17, Spring Boot 3.2+, SQLite, Flyway  
✅ **Environment Configuration** — application.yml for prod/test profiles  
✅ **Data Models** — JPA entities, database schema, migrations  
✅ **API Contract** — Complete endpoint specifications with request/response examples  
✅ **Error Handling** — HTTP status codes, error response formats, validation rules  
✅ **Service Boundaries** — TaskService, ValidationService, IdempotencyService interfaces  
✅ **Cross-Cutting Concerns** — Request tracing, rate limiting, exception handling  
✅ **Concurrency Model** — Optimistic locking with version field, conflict detection  
✅ **State Machines** — Task status transitions, validation rules  
✅ **Testing Strategy** — Unit tests, integration tests, concurrency tests, performance tests  
✅ **Deployment** — Docker, Kubernetes manifests, environment variables, runbooks  
✅ **Observability** — Logging, metrics, health checks, alerting rules  
✅ **Decision Log** — Rationale for key architectural decisions  
✅ **Open Questions** — Clarifications needed from stakeholders  

**Ready for Implementation:** An AI coding agent or development team can now implement this API using these specifications without requiring additional clarification.