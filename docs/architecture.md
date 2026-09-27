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
            PERM[Role permissions<br/>Citizen / Officer / Admin]
            VIEWS[ViewSets & APIViews]
            WF[Workflow service<br/>status transitions & assignment]
            SEL[Selectors<br/>role-scoped querysets]
        end
        DB[(PostgreSQL 16)]
        MEDIA[/media volume<br/>attachments/]
    end

    C & O & A -->|HTTPS JSON + Bearer token| MW
    SW -->|OpenAPI schema| MW
    MW --> JWT --> PERM --> VIEWS
    VIEWS --> SEL --> DB
    VIEWS --> WF --> DB
    VIEWS -->|upload / access-checked download| MEDIA
```

## Request lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor Citizen
    actor Admin
    actor Officer
    participant API as DRF API
    participant DB as PostgreSQL

    Citizen->>API: POST /auth/register/ then /auth/login/
    API-->>Citizen: access + refresh JWT
    Citizen->>API: POST /requests/ (category, title, description, priority)
    API->>DB: ServiceRequest(status=SUBMITTED) + StatusChange
    Admin->>API: POST /requests/{id}/assign/ {officer}
    API->>DB: assigned_officer, status=ASSIGNED + StatusChange
    Officer->>API: POST /requests/{id}/status/ {IN_PROGRESS}
    Officer->>API: POST /requests/{id}/comments/, /attachments/
    Officer->>API: POST /requests/{id}/status/ {RESOLVED}
    Citizen->>API: POST /requests/{id}/status/ {CLOSED}
    API->>DB: every transition recorded in StatusChange
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
| Settings / routing | `config/` | Env-driven settings, URL routing, OpenAPI |
| Accounts | `apps/accounts/` | User model with roles, JWT auth, admin user management, `seed_demo` |
| Categories | `apps/categories/` | Service categories (admin-managed) |
| Service requests | `apps/service_requests/` | Requests, status history, comments, attachments, statistics |
| ↳ `selectors.py` | | Which requests a user may see (role scoping) |
| ↳ `workflow.py` | | Status transition table, officer assignment, row locking |
| ↳ `statistics.py` | | Aggregations for the admin dashboard |
| Common | `apps/common/` | Shared base model, health check |
| Tests | `tests/` | pytest-django API tests against PostgreSQL |
