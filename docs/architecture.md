# Architecture

## System overview

```mermaid
flowchart LR
    subgraph Clients
        C[Citizen]
        O[Officer]
        A[Admin]
        SW[Swagger UI / ReDoc]
    end

    subgraph Docker Compose
        subgraph api[api container - Gunicorn + Django REST Framework]
            MW[Middleware<br/>WhiteNoise, Security, Auth]
            JWT[JWT authentication<br/>simplejwt]
            THR[Rate limiting<br/>DRF throttles]
            PERM[Role permissions<br/>Citizen / Officer / Admin]
            VIEWS[ViewSets & APIViews]
            WF[Workflow service<br/>status transitions & assignment]
            SEL[Selectors<br/>role-scoped querysets]
            AUD[Audit recorder]
        end
        WORKER[worker container<br/>Celery]
        DB[(PostgreSQL 16)]
        REDIS[(Redis 7<br/>broker + cache)]
        MEDIA[/media volume<br/>attachments/]
    end

    SMTP[[Gmail SMTP]]
    INBOX[User inbox]

    C & O & A -->|HTTPS JSON + Bearer token| MW
    SW -->|OpenAPI schema| MW
    MW --> JWT --> THR --> PERM --> VIEWS
    THR <-->|counters| REDIS
    VIEWS --> SEL --> DB
    VIEWS --> WF --> DB
    VIEWS --> AUD --> DB
    VIEWS -->|upload / access-checked download| MEDIA
    WF -->|queue email on commit| REDIS
    REDIS -->|tasks| WORKER
    WORKER -->|SMTP + TLS| SMTP --> INBOX
```

- **api** serves HTTP. Every request passes authentication, throttling and role permissions.
- **worker** runs Celery tasks (email delivery, retried with backoff on SMTP errors), so a slow
  mail server never slows down an API response.
- **Redis** is the Celery broker/result backend and the Django cache that holds throttle counters,
  shared by all Gunicorn workers.
- Emails are queued with `transaction.on_commit`, so nothing is sent for work that rolled back.

## Request lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Citizen
    actor Admin
    actor Officer
    participant API as DRF API
    participant DB as PostgreSQL
    participant Q as Redis + Celery
    participant Mail as Gmail SMTP

    Citizen->>API: POST /auth/register/
    API->>DB: User(is_email_verified=false) + AuditLog
    API->>Q: send verification email
    Q->>Mail: email with signed link
    Citizen->>API: GET /auth/verify-email/?token=…
    Citizen->>API: POST /auth/login/
    API-->>Citizen: access + refresh JWT
    Citizen->>API: POST /requests/
    API->>DB: ServiceRequest(SUBMITTED) + StatusChange + AuditLog
    Admin->>API: POST /requests/{id}/assign/
    API->>DB: status=ASSIGNED + StatusChange + AuditLog
    API->>Q: notify officer and citizen
    Officer->>API: POST /requests/{id}/status/ IN_PROGRESS → RESOLVED
    API->>Q: notify citizen
    Citizen->>API: POST /requests/{id}/status/ CLOSED
    API->>Q: notify officer
```

## Status workflow

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED: citizen submits
    SUBMITTED --> ASSIGNED: admin assigns officer
    SUBMITTED --> CANCELLED: owner / admin
    SUBMITTED --> REJECTED: admin (note required)
    ASSIGNED --> IN_PROGRESS: assigned officer / admin
    ASSIGNED --> REJECTED: assigned officer / admin (note required)
    IN_PROGRESS --> RESOLVED: assigned officer / admin
    IN_PROGRESS --> REJECTED: assigned officer / admin (note required)
    RESOLVED --> CLOSED: owner / admin
    CLOSED --> [*]
    REJECTED --> [*]
    CANCELLED --> [*]
```

## Code layout

| Layer | Location | Responsibility |
|---|---|---|
| Settings / routing | `config/` | Env-driven settings, URL routing, OpenAPI, Celery app |
| Accounts | `apps/accounts/` | User model with roles, JWT auth, email verification, admin user management, `seed_demo` |
| Categories | `apps/categories/` | Service categories (admin-managed) |
| Service requests | `apps/service_requests/` | Requests, status history, comments, attachments, statistics |
| ↳ `selectors.py` | | Which requests a user may see (role scoping) |
| ↳ `workflow.py` | | Status transition table, officer assignment, row locking |
| ↳ `notifications.py` | | Who gets emailed about which request event |
| ↳ `statistics.py` | | Aggregations for the admin dashboard |
| Notifications | `apps/notifications/` | Celery `send_email` task, on-commit queueing |
| Audit | `apps/audit/` | Append-only `AuditLog`, recording helper, admin endpoint |
| Common | `apps/common/` | Shared base model, health check (DB + Redis) |
| Tests | `tests/` | pytest-django API tests against PostgreSQL |
