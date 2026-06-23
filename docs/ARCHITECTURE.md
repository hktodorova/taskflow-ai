# Architecture

TaskFlow AI Enterprise uses a layered FastAPI architecture designed for clear separation of responsibilities.

```text
Client: Swagger UI / CLI / cURL
        |
FastAPI API Layer
        |
Service Layer: business rules and workflows
        |
Repository Layer: database operations
        |
SQLAlchemy ORM
        |
SQLite database
```

## Modules

- **Authentication Module** – password hashing, Bearer token validation and current user lookup.
- **Authorization Module** – role-based access control with `admin`, `member` and `viewer`.
- **Users Module** – user creation, login and profile access.
- **Teams Module** – teams and team membership.
- **Projects Module** – project management and optional team ownership.
- **Tasks Module** – CRUD, completion workflow, tags, priorities, dependencies, comments and subtasks.
- **Analytics Module** – completion rate, overdue tasks, team load and workload metrics.
- **AI Recommendations Module** – rule-based prioritization suggestions.
- **Notifications Module** – email outbox and queued message simulation.
- **Background Jobs Module** – job queue simulation for email sending and daily digest processing.
- **CLI Module** – terminal access for common workflows.

## Why this architecture is suitable

The API layer stays thin, the service layer contains business rules, and repository classes isolate database access. This makes the system easier to test, extend and debug with AI-assisted development tools.
