# Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ SERVICE_REQUEST : "submits (citizen)"
    USER ||--o{ SERVICE_REQUEST : "is assigned (officer)"
    CATEGORY ||--o{ SERVICE_REQUEST : classifies
    SERVICE_REQUEST ||--o{ STATUS_CHANGE : "has history"
    SERVICE_REQUEST ||--o{ COMMENT : has
    SERVICE_REQUEST ||--o{ ATTACHMENT : has
    USER ||--o{ STATUS_CHANGE : "changed by"
    USER ||--o{ COMMENT : writes
    USER ||--o{ ATTACHMENT : uploads
    USER |o--o{ AUDIT_LOG : "performs (null = anonymous)"

    USER {
        bigint id PK
        varchar email UK "login identifier, lower-cased"
        varchar password "hashed"
        varchar first_name
        varchar last_name
        varchar role "CITIZEN | OFFICER | ADMIN"
        boolean is_email_verified
        boolean is_active
        boolean is_staff
        boolean is_superuser
        timestamp date_joined
        timestamp last_login
    }

    CATEGORY {
        bigint id PK
        varchar name UK "case-insensitive unique"
        text description
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    SERVICE_REQUEST {
        bigint id PK
        bigint citizen_id FK
        bigint category_id FK
        bigint assigned_officer_id FK "nullable"
        varchar title
        text description
        varchar priority "LOW | MEDIUM | HIGH | URGENT"
        varchar status "SUBMITTED | ASSIGNED | IN_PROGRESS | RESOLVED | CLOSED | REJECTED | CANCELLED"
        timestamp assigned_at "nullable"
        timestamp resolved_at "nullable"
        timestamp created_at
        timestamp updated_at
    }

    STATUS_CHANGE {
        bigint id PK
        bigint service_request_id FK
        bigint changed_by_id FK
        varchar from_status "blank on creation"
        varchar to_status
        text note "required for REJECTED"
        timestamp created_at
    }

    COMMENT {
        bigint id PK
        bigint service_request_id FK
        bigint author_id FK
        text body
        timestamp created_at
    }

    ATTACHMENT {
        bigint id PK
        bigint service_request_id FK
        bigint uploaded_by_id FK
        varchar file "random stored name"
        varchar original_name
        varchar content_type
        bigint size "bytes"
        timestamp created_at
    }

    AUDIT_LOG {
        bigint id PK
        bigint actor_id FK "nullable"
        varchar action "LOGIN_SUCCEEDED, REQUEST_STATUS_CHANGED, ..."
        varchar target_type "model name, e.g. servicerequest"
        varchar target_id
        jsonb changes "field diffs, never passwords"
        inet ip_address
        timestamp created_at "indexed"
    }
```

## Notes

- **Deletion policy**: users, categories in use and requests are never hard-deleted (`PROTECT` foreign keys).
  Users are deactivated; categories are deactivated; requests end in `CLOSED`, `REJECTED` or `CANCELLED`.
- **Indexes**: `service_request.status` and `service_request.priority` are indexed for list filtering and statistics;
  `audit_log` is indexed on `created_at`, `action` and `(target_type, target_id)`.
- **Audit log** is a generic log: `target_type` + `target_id` point at any row (user, category,
  service request) without a hard foreign key, so entries survive and stay immutable.
- **Email verification** needs no table: tokens are signed (`django.core.signing`) and time-limited.
- JWT refresh-token blacklisting uses the `token_blacklist` tables provided by `djangorestframework-simplejwt`
  (`OutstandingToken`, `BlacklistedToken`), omitted above for clarity.
