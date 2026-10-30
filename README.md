# Marketplace backend - Architecture & Design Documentation

> A DDD-lite FastAPI backend for a course marketplace in Azerbaijan. Academies (training centers) list their
> courses; students find upcoming courses and enroll. PostgreSQL stores all data.

This document covers the architecture, the patterns and decisions behind it, how to run the service, and the
endpoint reference. The architecture follows the Python/FastAPI port of
[Rovio.Matchmaking](https://github.com/TuralSuleymani/Rovio.Matchmaking): the same layers, shared kernel and
conventions.

**Status:** the academy module and the course module are implemented end to end: domain,
application, infrastructure and API, including the public course listing. Enrollments, authentication and
migrations are next. See [Roadmap](#roadmap).

---

# Part 1: Architecture guide

## Table of Contents

- [Features](#features)
- [High-level diagram](#high-level-diagram)
- [Architecture diagram](#architecture-diagram)
- [Components diagram](#components-diagram)
- [Sequence diagrams](#sequence-diagrams)
- [Clean Architecture overview](#clean-architecture-overview)
- [Applied Domain-Driven Design patterns](#applied-domain-driven-design-patterns)
- [Applied design principles and patterns](#applied-design-principles-and-patterns)
- [Architectural decisions](#architectural-decisions)
- [Best practices applied](#best-practices-applied)
- [Technologies used](#technologies-used)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Quality checks](#quality-checks)
- [Failure model](#failure-model)
- [Roadmap](#roadmap)
- [Part 2: Endpoints reference](#part-2-endpoints-reference)

## Features

**Academies**

- Academy registration; a new academy is `Active` at once.
- Academy names (case-insensitive) and contact emails are unique across the platform.
- Academy profile update (name, contact email) with partial `PATCH`.
- Admin **verified badge**: granted after the admin checks the academy, revoked e.g. when fraud is flagged. Only
  academies with the badge can create, publish or resume courses.
- Admin suspend and reactivate; a suspended academy cannot publish.
- Academy list for admins, filterable by status, oldest first.

**Courses**

- Create a course as a draft: title, description, category, photo gallery (first photo is the cover), syllabus,
  included / excluded items, venue and class time, course dates, price per student, capacity and the academy's own
  cancellation policy (refund tiers).
- Lifecycle driven by the academy itself, no moderation: publish, pause, resume, cancel, archive (instead of delete).
- One academy cannot run two live courses with the same title on overlapping dates.
- Public listing for students: published courses that have not started yet, soonest first.

**Cross-cutting**

- Every rule lives in the domain; expected failures come back as values with a stable error `code`.
- "Today" is the Baku local date (UTC+4), so date rules match what students and academies see.
- Layer boundaries enforced automatically with import-linter.

## High-level diagram

```mermaid
flowchart LR
    student[Student web app]
    academy[Academy dashboard]
    admin[Admin panel]
    api[marketplace API<br/>FastAPI]
    db[(PostgreSQL)]

    student --> api
    academy --> api
    admin --> api
    api --> db
```

## Architecture diagram

Dependencies point inwards only. The domain knows nothing about FastAPI, SQLAlchemy, the database or `await`.

```mermaid
flowchart TD
    main[main.py<br/>composition root]
    api[api<br/>routers, request schemas, error mapping]
    infra[infrastructure<br/>SQLAlchemy models, repositories, config]
    app[application<br/>services, ports, DTOs]
    domain[domain<br/>entities, value objects, domain services, rules]
    common[common<br/>Result, Id, Entity, DomainError, local time]

    main --> api
    main --> infra
    api --> infra
    api --> app
    infra --> app
    infra --> domain
    app --> domain
    domain --> common
    app --> common
```

## Components diagram

```mermaid
flowchart LR
    subgraph api
        academy_router[academy_router]
        course_router[course_router]
        unwrap[errors.unwrap]
    end
    subgraph application
        academy_service[AcademyService]
        course_service[CourseService]
        academy_port[[IAcademyRepository]]
        course_port[[ICourseRepository]]
        dtos[AcademyDto<br/>CourseDto]
    end
    subgraph domain
        academy[Academy]
        course[Course]
        overlap[CourseOverlapPolicy]
        vo[Value objects<br/>AcademyName, ContactEmail, Money,<br/>DateRange, CancellationPolicy, ...]
    end
    subgraph infrastructure
        academy_repo[AcademyRepository]
        course_repo[CourseRepository]
        rows[AcademyRow<br/>CourseModel]
        clock[SystemTimeProvider]
    end
    db[(PostgreSQL)]

    academy_router --> academy_service
    course_router --> course_service
    academy_router --> unwrap
    course_router --> unwrap
    academy_service --> academy_port
    course_service --> academy_port
    course_service --> course_port
    course_service --> overlap
    academy_service --> academy
    course_service --> course
    academy_service --> dtos
    course_service --> dtos
    academy --> vo
    course --> vo
    academy_repo -. implements .-> academy_port
    course_repo -. implements .-> course_port
    academy_repo --> rows
    course_repo --> rows
    rows --> db
    academy_service --> clock
    course_service --> clock
```

## Sequence diagrams

### Register an academy

```mermaid
sequenceDiagram
    participant C as Client
    participant R as academy_router
    participant S as AcademyService
    participant A as Academy
    participant P as AcademyRepository
    participant D as PostgreSQL

    C->>R: POST /api/v1/academies {name, contact_email}
    R->>S: register(name, contact_email)
    S->>A: Academy.create(name, email, now)
    alt invalid input
        A-->>S: failure(DomainError)
        S-->>R: failure
        R-->>C: 400 {code, message}
    else valid
        A-->>S: success(Academy, Active, no badge)
        S->>P: exists_with_name / exists_with_contact_email
        alt name or email taken
            S-->>R: failure (409)
            R-->>C: 409 academy_name_taken / contact_email_taken
        else unique
            S->>P: add(academy)
            P->>D: INSERT + COMMIT
            S-->>R: success(AcademyDto)
            R-->>C: 201 + Location
        end
    end
```

### Academy publishes a course

```mermaid
sequenceDiagram
    participant C as Academy
    participant R as course_router
    participant S as CourseService
    participant AG as Academy
    participant P as CourseRepository
    participant O as CourseOverlapPolicy
    participant AN as Course

    C->>R: POST /api/v1/academies/{academy_id}/courses/{id}/publish
    R->>R: Id.parse(academy_id), Id.parse(id) (400 invalid_id)
    R->>S: publish(academy_id, id)
    S->>AG: ensure_can_publish()
    alt suspended, not active or no verified badge
        AG-->>S: failure (409)
    else allowed
        S->>P: get(id)
        P-->>S: Course or None / other academy's (404)
        S->>P: list_active_by_academy(academy_id)
        S->>O: ensure_no_overlap(course, others)
        alt same title on overlapping dates
            O-->>S: failure (409 course.overlap)
        else no overlap
            S->>AN: publish(now)
            alt not a draft / already started
                AN-->>S: failure (409 / 400)
            else ok
                AN-->>S: success, status = published
                S->>P: update(course)
                S-->>R: CourseDto
                R-->>C: 200
            end
        end
    end
```

## Clean Architecture overview

| Layer | Package | Responsibility |
| --- | --- | --- |
| Shared kernel | `marketplace.common` | `Result`, typed `Id`, `Entity` base, `DomainError`, `ErrorType`, `TimeProvider` port, Baku `local_today` |
| Domain | `marketplace.domain` | Entities, value objects, domain services, enums, error codes; every business rule. No I/O, no `await` |
| Application | `marketplace.application` | Use-case services, repository ports (`IAcademyRepository`, `ICourseRepository`), DTOs and commands |
| Infrastructure | `marketplace.infrastructure` | SQLAlchemy table models, repository implementations, settings, system clock |
| API | `marketplace.api` | FastAPI routers, request schemas, `Result` → HTTP mapping, dependency wiring |
| Composition root | `marketplace.main` | Builds the app: settings, engine, session factory, routers |

## Applied Domain-Driven Design patterns

1. **Entities** with identity-based equality (`Entity[T]`): two academies are equal when their ids are equal.
2. **Value objects** (`AcademyName`, `ContactEmail`, `Money`, `DateRange`, `PhotoGallery`, `Syllabus`,
   `Inclusions`, `Venue`, `CancellationPolicy`): immutable frozen dataclasses, compared by value,
   normalized on creation.
3. **Factory methods**: `create(...)` builds a new object and runs every rule; `rehydrate(...)` rebuilds an
   object loaded from storage without re-running rules.
4. **Typed ids**: `Id[Academy]` and `Id[Course]` cannot be mixed up.
5. **Behaviour on the entity**: status changes are methods (`suspend`, `grant_verification`, `publish`, `pause`,
   `cancel`, `archive`, ...) that guard their own transitions, not setters.
6. **Domain service**: `CourseOverlapPolicy` owns the rule that compares one course with the academy's
   other live ones, a rule no single entity can own. The application loads the list; the policy only decides.
7. **Cross-entity rule on the entity that owns the data**: `Academy.ensure_can_publish()` is asked by the
   course use cases before a course is created, published or resumed.
8. **Domain errors as values**: rules return `Result` with a `DomainError` that carries an `ErrorType` and a
   stable `code`.
9. **Repositories as ports**: the application owns `IAcademyRepository` and `ICourseRepository`;
   infrastructure implements them.
10. **No aggregate root (deliberate)**: `Academy` and `Course` are independent entities linked by
    `academy_id`. See [Architectural decisions](#architectural-decisions).

## Applied design principles and patterns

1. **Ports and adapters**: services depend on interfaces (`IAcademyRepository`, `ICourseRepository`,
   `TimeProvider`), not on SQLAlchemy or the system clock.
2. **Repository**: the only place that reads or writes the database and commits.
3. **Result pattern**: expected failures travel as values; exceptions are reserved for bugs and corrupted data
   (`InvariantViolationError`).
4. **Dependency injection**: FastAPI `Depends` builds one `AsyncSession` and one service per request.
5. **Composition root**: `main.py` is the only module that knows every layer.
6. **Data mapper**: `AcademyRow` and `CourseModel` describe the tables; the repositories translate them to
   and from the entities. Course lists (photos, syllabus, inclusions, refund tiers) are stored as JSON.

## Architectural decisions

| Decision | Rationale |
| --- | --- |
| DDD-lite: no aggregate roots, no domain events, no CQRS | No invariant spans `Academy` and `Course` today. A root would force loading the academy on every course change and cause needless conflicts |
| Entities linked by id only (`Course.academy_id`) | Each entity has its own repository and can change independently |
| `Result` instead of exceptions for expected failures | Every failure path is explicit in signatures and easy to follow |
| HTTP status chosen only in `api/errors.py` | The domain and application never know about HTTP; `ErrorType` decides the status |
| Domain is synchronous, never calls `now()` | `async` is contagious and the clock is hidden state; services pass `now` from `TimeProvider` |
| Repository always calls `rehydrate`, never `create` | Loading must keep the stored id, status and timestamps, and must not fail on data saved under older rules (an old course may start in the past) |
| No creation token on entities | Kept simple; "only `create` and `rehydrate` call the constructor" is a convention |
| New academies are `Active` at once; the verified badge is separate from status | Academies can sign up without waiting; the badge (granted and revoked by an admin) is what lets them publish and what students see. The older approval flow (`PendingVerification` → `verify` / `reject`) is kept in the domain and API but `create` no longer uses it |
| Uniqueness checked in the service, enforced by unique indexes | The service gives a clear `409`; the indexes on `lower(name)` and `contact_email` are the last guard against concurrent requests |
| State changes are action endpoints (`/suspend`, `/publish`, `/verified-badge`) | Each transition is a domain method with its own rule, not a status field edit |
| No moderation of courses | The academy drives the whole lifecycle; trust comes from the verified badge |
| One course = one group (cohort), one `DateRange` | A new date is a new (duplicated) course; capacity belongs to the course |
| Archive instead of delete | Old enrollments keep pointing at the course |
| Another academy's course answers `404` | Its existence is not revealed |
| `Money` as `Decimal`, at most 2 decimal places | No float rounding; amounts with more decimals are rejected, not rounded |
| Course dates as `date`, inclusive; "today" is the Baku date | Day precision is enough for course dates; the class time lives on `Venue`. Azerbaijan is UTC+4 all year, so a fixed offset is exact |
| Pydantic for DTOs and request schemas, not for the domain | The domain stays framework-free; the API returns DTOs directly |
| Layers checked by import-linter | Python has no compile-time module boundaries |

## Best practices applied

- Thin routers: parse input, call one service method, `unwrap` the result. No business conditions.
- Services hold no rules: load, call the entity or domain service, save only on success.
- Request fields are deliberately loose (optional strings); the domain validates them and returns its own codes.
- Value objects normalize input (trim, collapse spaces, lower-case emails) so equal values compare equal.
- Settings come from `.env` (or real environment variables); no credentials in code.
- `expire_on_commit=False` on the session factory to avoid lazy loads after commit in async code.
- Type hints everywhere; mypy in strict mode; ruff for lint and import order.

## Technologies used

### Runtime & language

| Technology | Version |
| --- | --- |
| Python | 3.12 |
| PostgreSQL | 17 (Docker image) |
| uv | 0.9 (package and environment manager) |

### Production packages

| Package | Version | Used in |
| --- | --- | --- |
| fastapi | 0.142.4 | api |
| pydantic | 2.13.5 | application DTOs, api schemas |
| pydantic-settings | 2.15.0 | infrastructure config |
| sqlalchemy[asyncio] | 2.1.4 | infrastructure |
| asyncpg | 0.32.0 | infrastructure (PostgreSQL driver) |
| uvicorn | 0.54.0 | ASGI server |

### Development packages

| Package | Version | Purpose |
| --- | --- | --- |
| ruff | 0.16.10 | lint and import sorting |
| mypy | 2.4.0 | static type checking (strict) |
| import-linter | 2.15 | layer contract |
| pytest, pytest-asyncio, httpx, aiosqlite | see `uv.lock` | reserved for tests |

## Project structure

```text
.
├── compose.yaml                 # local PostgreSQL
├── pyproject.toml               # dependencies, ruff, mypy, import-linter
├── .env.example                 # copy to .env
└── src/marketplace/
    ├── main.py                  # composition root: create_app()
    ├── common/                  # shared kernel
    │   ├── entity.py, identity.py, result.py, time_provider.py
    │   ├── local_time.py        # Baku time zone, local_today()
    │   └── errors/              # DomainError, ErrorType, CommonErrorCodes
    ├── domain/
    │   ├── academy/
    │   │   ├── academy.py        # Academy entity
    │   │   ├── course.py         # Course entity
    │   │   ├── enums.py         # AcademyStatus, CourseStatus
    │   │   ├── errors.py        # AcademyErrorCodes, CourseErrorCodes, MoneyErrorCodes
    │   │   └── value_objects/   # AcademyName, ContactEmail, Money, DateRange, PhotoGallery,
    │   │                        # Syllabus, Inclusions, Venue, CancellationPolicy
    │   └── course/
    │       └── services/course_overlap_policy.py   # domain service
    ├── application/
    │   └── academy/
    │       ├── abstractions/    # IAcademyRepository, ICourseRepository (ports)
    │       ├── academy_service.py, course_service.py
    │       └── dtos/            # academy_dtos.py, course_dtos.py
    ├── infrastructure/
    │   ├── config.py, database.py, system_time_provider.py
    │   └── academy/
    │       ├── academy_row.py, course_model.py              # SQLAlchemy models
    │       └── academy_repository.py, course_repository.py  # adapters
    └── api/
        ├── dependencies.py, errors.py
        └── academy/
            ├── academy_router.py         # /academies, /admin/academies
            ├── course_router.py          # /academies/{id}/courses, /public/courses
            └── schemas.py
```

## Getting started

Prerequisites: [uv](https://docs.astral.sh/uv/) and Docker.

```bash
# 1. Install dependencies into .venv
uv sync

# 2. Configure: DATABASE_URL is read from .env in the project root
cp .env.example .env

# 3. Start PostgreSQL (user, password and database are all "marketplace", port 5432)
docker compose up -d

# 4. Run the API
uv run uvicorn marketplace.main:app --reload
```

- API: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- Stop the database with `docker compose down`; add `-v` to delete its data.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | yes | none | SQLAlchemy async URL, e.g. `postgresql+asyncpg://marketplace:marketplace@localhost:5432/marketplace` |
| `DATABASE_ECHO` | no | `false` | Log every SQL statement |

### Create the tables

There are no migrations yet, so create the tables once, before the first run:

```bash
docker exec -i marketplace-postgres psql -U marketplace -d marketplace <<'SQL'
CREATE TABLE academies (
    id                   uuid         PRIMARY KEY,
    name                 varchar(200) NOT NULL,
    contact_email        varchar(254) NOT NULL,
    status               varchar(32)  NOT NULL,
    rejection_reason     varchar(500),
    is_verified          boolean      NOT NULL DEFAULT false,
    verified_at_utc      timestamptz,
    created_at_utc       timestamptz  NOT NULL,
    last_modified_at_utc timestamptz  NOT NULL
);
CREATE INDEX ix_academies_status_created_at_utc ON academies (status, created_at_utc);
CREATE UNIQUE INDEX uq_academies_contact_email ON academies (contact_email);
CREATE UNIQUE INDEX uq_academies_name_lower ON academies (lower(name));

CREATE TABLE courses (
    id                            uuid          PRIMARY KEY,
    academy_id                     uuid          NOT NULL REFERENCES academies (id),
    title                         varchar(200)  NOT NULL,
    description                   text          NOT NULL,
    category                   varchar(100)  NOT NULL,
    photos                        json          NOT NULL,
    syllabus                     json          NOT NULL,
    included                      json          NOT NULL,
    excluded                      json          NOT NULL,
    venue_address               varchar(300)  NOT NULL,
    class_time                  time          NOT NULL,
    start_date                    date          NOT NULL,
    end_date                      date          NOT NULL,
    price_amount                  numeric(12,2) NOT NULL,
    price_currency                varchar(3)    NOT NULL,
    capacity                      integer       NOT NULL,
    refund_tiers                  json          NOT NULL,
    last_cancellation_days_before integer       NOT NULL,
    status                        varchar(32)   NOT NULL,
    created_at_utc                timestamptz   NOT NULL,
    last_modified_at_utc          timestamptz   NOT NULL,
    cancelled_at_utc              timestamptz,
    archived_at_utc               timestamptz
);
CREATE INDEX ix_courses_academy_id_start_date ON courses (academy_id, start_date);
CREATE INDEX ix_courses_status_start_date ON courses (status, start_date);
SQL
```

If you created the `academies` table from an earlier version of this README, add the new columns and indexes
first, then create only the `courses` table:

```sql
ALTER TABLE academies
    ADD COLUMN is_verified boolean NOT NULL DEFAULT false,
    ADD COLUMN verified_at_utc timestamptz;
CREATE UNIQUE INDEX uq_academies_contact_email ON academies (contact_email);
CREATE UNIQUE INDEX uq_academies_name_lower ON academies (lower(name));
```

## Quality checks

```bash
uv run ruff check src     # lint
uv run mypy               # strict type check
uv run lint-imports       # layer contract: api > infrastructure > application > domain > common
```

Automated tests are not part of the repository yet.

## Failure model

| Scenario | Behavior |
| --- | --- |
| Invalid input (empty name, bad email, missing photo, end before start, ...) | `400` with the domain's error `code`; nothing is saved. Only the first failing rule is reported |
| Malformed path id | `400 invalid_id` |
| Malformed JSON, wrong field types or a missing required course field | `422`, FastAPI's default validation response |
| Unknown academy or course, or another academy's course | `404 academy_not_found` / `404 course.not_found` |
| Name or contact email already used by another academy | `409 academy_name_taken` / `409 contact_email_taken` |
| Academy suspended or without the verified badge tries to create, publish or resume | `409 academy_suspended` / `academy_not_active` / `academy_not_verified` |
| Transition not allowed from the current status | `409` with a specific code; nothing is saved |
| Live course with the same title on overlapping dates | `409 course.overlap` |
| Two concurrent registrations with the same name or email | One wins; the other hits the unique index and gets an unhandled `500` |
| Corrupted row in the database | `InvariantViolationError` from `rehydrate`; `500` |
| Database unavailable | Unhandled driver error; `500` |

## Roadmap

- Duplicate endpoint: `Course.duplicate()` and `DuplicateCourseCommand` exist; the service method and
  route do not yet.
- Public search filters (category, dates, price) on top of the current listing.
- Enrollments with a 10-minute seat hold and payment; they will supply the active enrollment count for
  `archive` (currently always 0) and refund students when a course is cancelled.
- Alembic migrations instead of the manual `CREATE TABLE`.
- Authentication and roles; admin and academy endpoints are currently **unprotected**, and any caller can act for
  any `academy_id`.
- More academy profile fields: contact person, phone, tax ID (VÖEN), logo, description, social links.
- Automated tests (pytest, httpx, aiosqlite are already listed as dev dependencies).

---

# Part 2: Endpoints reference

All endpoints are under `/api/v1`. Bodies are JSON. Interactive docs: `/docs`.

Ids are UUIDs, returned as 32 hex characters; path parameters accept them with or without dashes.

## Endpoints overview

**Academies (academy dashboard)**

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| POST | `/api/v1/academies` | 201 + `Location` | 400, 409 |
| GET | `/api/v1/academies/{academy_id}` | 200 | 400, 404 |
| PATCH | `/api/v1/academies/{academy_id}` | 200 | 400, 404, 409 |

**Admin: academies**

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| GET | `/api/v1/admin/academies` | 200 | 400 |
| POST | `/api/v1/admin/academies/{academy_id}/verified-badge` | 200 | 400, 404, 409 |
| DELETE | `/api/v1/admin/academies/{academy_id}/verified-badge` | 200 | 400, 404, 409 |
| POST | `/api/v1/admin/academies/{academy_id}/suspend` | 200 | 400, 404, 409 |
| POST | `/api/v1/admin/academies/{academy_id}/reactivate` | 200 | 400, 404, 409 |
| POST | `/api/v1/admin/academies/{academy_id}/verify` | 200 | 400, 404, 409 |
| POST | `/api/v1/admin/academies/{academy_id}/reject` | 200 | 400, 404, 409 |

**Courses (academy dashboard)**

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| POST | `/api/v1/academies/{academy_id}/courses` | 201 + `Location` | 400, 404, 409, 422 |
| GET | `/api/v1/academies/{academy_id}/courses` | 200 | 400, 404 |
| GET | `/api/v1/academies/{academy_id}/courses/{course_id}` | 200 | 400, 404 |
| POST | `/api/v1/academies/{academy_id}/courses/{course_id}/publish` | 200 | 400, 404, 409 |
| POST | `/api/v1/academies/{academy_id}/courses/{course_id}/pause` | 200 | 400, 404, 409 |
| POST | `/api/v1/academies/{academy_id}/courses/{course_id}/resume` | 200 | 400, 404, 409 |
| POST | `/api/v1/academies/{academy_id}/courses/{course_id}/cancel` | 200 | 400, 404, 409 |
| DELETE | `/api/v1/academies/{academy_id}/courses/{course_id}` | 200 | 400, 404, 409 |

**Public (students)**

| Method | Path | Success | Errors |
| --- | --- | --- | --- |
| GET | `/api/v1/public/courses` | 200 | none |
| GET | `/api/v1/public/courses/{course_id}` | 200 | 400, 404 |

### Academy status and verified badge

```mermaid
stateDiagram-v2
    [*] --> Active: register
    Active --> Suspended: suspend
    Suspended --> Active: reactivate

    state "Earlier approval flow (not reached by register)" as legacy {
        PendingVerification --> Active2: verify
        PendingVerification --> Rejected: reject (reason)
        Active2: Active
    }
```

The verified badge is independent of the status: an admin grants it (not allowed while `Suspended`) and revokes
it. An academy can create, publish and resume courses only when it is `Active` **and** has the badge.

### Course status transitions

```mermaid
stateDiagram-v2
    [*] --> draft: create
    draft --> published: publish
    published --> paused: pause
    paused --> published: resume
    published --> cancelled: cancel
    paused --> cancelled: cancel
    draft --> archived: archive
    published --> archived: archive
    paused --> archived: archive
    cancelled --> archived: archive
```

`publish` and `resume` also require that the course has not started yet (Baku date) and that the academy has no
other live (`published` or `paused`) course with the same title on overlapping dates.

## Academies

### POST Register academy

`POST /api/v1/academies`

```json
{
  "name": "Code Academy",
  "contact_email": "info@codeacademy.az"
}
```

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `name` | string | yes | trimmed, inner spaces collapsed, 1-200 characters, unique (case-insensitive) |
| `contact_email` | string | yes | trimmed, lower-cased, valid email shape, at most 254 characters, unique |

- `201 Created`: `AcademyDto` with `status = "Active"` and `is_verified = false`;
  `Location: /api/v1/academies/{id}`.
- `400`: `invalid_academy_name`, `invalid_contact_email`.
- `409`: `academy_name_taken`, `contact_email_taken`.

**AcademyDto**

```json
{
  "id": "3f2a9c1e5b7d4e8a9c217d4e5f6a8b90",
  "name": "Code Academy",
  "contact_email": "info@codeacademy.az",
  "status": "Active",
  "rejection_reason": null,
  "is_verified": false,
  "verified_at_utc": null,
  "created_at_utc": "2026-10-09T09:00:00Z",
  "last_modified_at_utc": "2026-10-09T09:00:00Z"
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | UUID as 32 hex characters |
| `name` | string | normalized |
| `contact_email` | string | lower-cased |
| `status` | string | `Active`, `Suspended` (`PendingVerification`, `Rejected` only in the earlier approval flow) |
| `rejection_reason` | string or null | set only when rejected |
| `is_verified` | boolean | verified badge |
| `verified_at_utc` | datetime or null | when the badge was granted; `null` without the badge |
| `created_at_utc` | datetime | UTC |
| `last_modified_at_utc` | datetime | UTC, changes on every successful update |

### GET Academy

`GET /api/v1/academies/{academy_id}`

- `200`: `AcademyDto`.
- `400 invalid_id`, `404 academy_not_found`.

### PATCH Update academy

`PATCH /api/v1/academies/{academy_id}`

```json
{
  "name": "Code Academy Baku"
}
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | no | omitted = unchanged; same rules as registration |
| `contact_email` | string | no | omitted = unchanged; same rules as registration |

- `200`: updated `AcademyDto`.
- `400`: `invalid_id`, `invalid_academy_name`, `invalid_contact_email`. `404 academy_not_found`.
- `409`: `academy_name_taken`, `contact_email_taken` (the academy's own current values do not conflict).

## Admin

> These endpoints have no authentication yet. Do not expose them publicly.

### GET List academies

`GET /api/v1/admin/academies?status=Active`

| Query | Type | Required | Notes |
| --- | --- | --- | --- |
| `status` | string | no | `PendingVerification`, `Active`, `Rejected`, `Suspended`; omitted = all |

- `200`: array of `AcademyDto`, oldest first.
- `400 invalid_academy_status`.

### POST Grant verified badge

`POST /api/v1/admin/academies/{academy_id}/verified-badge` (no body)

- `200`: `AcademyDto` with `is_verified = true` and `verified_at_utc` set.
- `409`: `academy_already_verified`, `academy_suspended`.

### DELETE Revoke verified badge

`DELETE /api/v1/admin/academies/{academy_id}/verified-badge` (no body)

- `200`: `AcademyDto` with `is_verified = false` and `verified_at_utc = null`.
- `409 academy_not_verified`.

### POST Suspend academy

`POST /api/v1/admin/academies/{academy_id}/suspend` (no body)

- `200`: `AcademyDto` with `status = "Suspended"`. The badge is kept but the academy cannot publish.
- `409`: `academy_already_suspended`, `academy_not_active`.

### POST Reactivate academy

`POST /api/v1/admin/academies/{academy_id}/reactivate` (no body)

- `200`: `AcademyDto` with `status = "Active"`.
- `409`: `academy_already_active`, `academy_not_suspended`.

### POST Verify academy / POST Reject academy (earlier approval flow)

`POST /api/v1/admin/academies/{academy_id}/verify` (no body) and `POST /api/v1/admin/academies/{academy_id}/reject`:

```json
{
  "reason": "VÖEN could not be verified"
}
```

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `reason` | string | yes (reject only) | trimmed, 1-500 characters |

These only apply to an academy in `PendingVerification`. Registration no longer creates such academies, so for any
academy registered through the API they return `409 academy_not_pending_verification`. `reject` returns
`400 invalid_rejection_reason` first if the reason is missing or too long.

All admin endpoints with `{academy_id}` also return `400 invalid_id` and `404 academy_not_found`.

## Courses

> These endpoints have no authentication yet: any caller can act for any `academy_id`.

A course that belongs to a different academy than the one in the path answers `404 course.not_found`.

### POST Create course

`POST /api/v1/academies/{academy_id}/courses`

Creates a **draft**. The academy must be `Active` and have the verified badge.

```json
{
  "title": "Python Backend Bootcamp",
  "description": "Twelve weeks of Python, FastAPI and PostgreSQL, ending with a portfolio project.",
  "category": "Programming",
  "photos": ["https://cdn.example.az/python/1.jpg", "https://cdn.example.az/python/2.jpg"],
  "syllabus": [
    {"order": 1, "title": "Python basics", "detail": "Types, functions, modules"},
    {"order": 2, "title": "FastAPI"}
  ],
  "included": ["Course materials", "Certificate", "Mentor support"],
  "excluded": ["Laptop"],
  "venue_address": "Nizami street 10, Baku",
  "class_time": "19:00",
  "start_date": "2026-12-01",
  "end_date": "2027-02-23",
  "price_amount": "450.00",
  "currency": "AZN",
  "capacity": 20,
  "refund_tiers": [
    {"days_before": 10, "refund_percent": 100},
    {"days_before": 5, "refund_percent": 50}
  ],
  "last_cancellation_days_before": 3
}
```

| Field | Type | Required | Rules | Error code |
| --- | --- | --- | --- | --- |
| `title` | string | yes | trimmed, inner spaces collapsed, 1-200 characters | `course.title_empty`, `course.title_too_long` |
| `description` | string | yes | trimmed, 1-5000 characters | `course.description_too_short`, `course.description_too_long` |
| `category` | string | yes | trimmed, inner spaces collapsed, 1-100 characters | `course.category_empty`, `course.category_too_long` |
| `photos` | string[] | yes | URLs or storage keys, 1-20, blanks dropped; the first is the cover | `course.gallery_empty`, `course.gallery_too_large` |
| `syllabus` | object[] | yes | at least one `{order, title, detail?}`; sorted by `order` | `course.syllabus_empty` |
| `included`, `excluded` | string[] | no | blanks dropped; may be empty | none |
| `venue_address` | string | yes | trimmed, not empty | `course.venue_empty` |
| `class_time` | time | yes | `HH:MM` or `HH:MM:SS` | `422` |
| `start_date`, `end_date` | date | yes | `YYYY-MM-DD`, inclusive; end not before start; start after today (Baku) | `course.date_range_invalid`, `course.start_in_past` |
| `price_amount` | decimal | yes | per student, not negative, at most 2 decimal places | `money.amount_invalid`, `money.amount_negative`, `money.amount_too_many_decimals` |
| `currency` | string | no (`AZN`) | 3 letters, upper-cased | `money.currency_invalid` |
| `capacity` | integer | yes | 1-10000 seats | `course.capacity_invalid` |
| `refund_tiers` | object[] | no | at most 10; `days_before` ≥ 0 and unique; `refund_percent` 0-100 and never higher closer to the course | `course.cancellation_invalid` |
| `last_cancellation_days_before` | integer | yes | ≥ 0; after this the student can no longer cancel | `course.cancellation_invalid` |

Refund example for the body above: 12 days before the course, 100%; 7 days before, 50%; 4 days before, 0%;
2 days before, cancellation is no longer possible.

- `201 Created`: `CourseDto` with `status = "draft"`;
  `Location: /api/v1/academies/{academy_id}/courses/{id}`.
- `400`: `invalid_id` or any code from the table above.
- `404 academy_not_found`.
- `409`: `academy_suspended`, `academy_not_active`, `academy_not_verified`.
- `422`: a required field (`class_time`, dates, `price_amount`, `capacity`, `last_cancellation_days_before`)
  missing or of the wrong type.

**CourseDto**

```json
{
  "id": "9b1d4c7a2e3f4a5b8c6d7e8f9a0b1c2d",
  "academy_id": "3f2a9c1e5b7d4e8a9c217d4e5f6a8b90",
  "title": "Python Backend Bootcamp",
  "description": "Twelve weeks of Python, FastAPI and PostgreSQL, ending with a portfolio project.",
  "category": "Programming",
  "photos": ["https://cdn.example.az/python/1.jpg", "https://cdn.example.az/python/2.jpg"],
  "cover_photo": "https://cdn.example.az/python/1.jpg",
  "syllabus": [
    {"order": 1, "title": "Python basics", "detail": "Types, functions, modules"},
    {"order": 2, "title": "FastAPI", "detail": ""}
  ],
  "included": ["Course materials", "Certificate", "Mentor support"],
  "excluded": ["Laptop"],
  "venue_address": "Nizami street 10, Baku",
  "class_time": "19:00:00",
  "start_date": "2026-12-01",
  "end_date": "2027-02-23",
  "duration_days": 85,
  "price_amount": "450.00",
  "currency": "AZN",
  "capacity": 20,
  "refund_tiers": [
    {"days_before": 10, "refund_percent": 100},
    {"days_before": 5, "refund_percent": 50}
  ],
  "last_cancellation_days_before": 3,
  "status": "draft",
  "created_at_utc": "2026-10-29T09:00:00Z",
  "last_modified_at_utc": "2026-10-29T09:00:00Z",
  "cancelled_at_utc": null,
  "archived_at_utc": null
}
```

| Field | Notes |
| --- | --- |
| `cover_photo` | the first photo |
| `duration_days` | inclusive: a one-day course has `start_date = end_date` and `duration_days = 1` |
| `price_amount` | decimal, serialized as a string |
| `refund_tiers` | sorted by `days_before`, highest first |
| `status` | `draft`, `published`, `paused`, `cancelled`, `archived` |
| `cancelled_at_utc`, `archived_at_utc` | set by `cancel` and `archive` |

### GET List academy courses

`GET /api/v1/academies/{academy_id}/courses`

- `200`: array of `CourseDto`, every status except `archived`, soonest start first.
- `400 invalid_id`, `404 academy_not_found`.

### GET Course

`GET /api/v1/academies/{academy_id}/courses/{course_id}`

- `200`: `CourseDto` (any status, including archived).
- `400 invalid_id`, `404 course.not_found`.

### POST Publish / POST Resume

`POST .../courses/{course_id}/publish` (draft → published) and
`POST .../courses/{course_id}/resume` (paused → published), no body.

- `200`: `CourseDto` with `status = "published"`.
- `400 course.start_in_past`: the course has already started.
- `404`: `academy_not_found`, `course.not_found`.
- `409`: `academy_suspended`, `academy_not_active`, `academy_not_verified`, `course.overlap`,
  `course.invalid_transition`.

### POST Pause

`POST .../courses/{course_id}/pause` (no body). Hides the course from the public listing; existing
enrollments stay valid.

- `200`: `CourseDto` with `status = "paused"`.
- `409 course.invalid_transition` unless `published`.

### POST Cancel

`POST .../courses/{course_id}/cancel` (no body). Allowed from `published` or `paused`.

- `200`: `CourseDto` with `status = "cancelled"` and `cancelled_at_utc` set.
- `409 course.invalid_transition`.

### DELETE Archive

`DELETE .../courses/{course_id}` (no body). Archives instead of deleting; allowed from any status
except `archived`.

- `200`: `CourseDto` with `status = "archived"` and `archived_at_utc` set.
- `409`: `course.already_archived`, `course.has_active_enrollments` (once enrollments exist).

All course endpoints also return `400 invalid_id`, and `404 course.not_found` for an unknown
course or one that belongs to another academy.

## Public

### GET Published courses

`GET /api/v1/public/courses`

- `200`: array of `CourseDto` with `status = "published"` that start after today (Baku date), soonest
  first. Paused, draft, cancelled and archived courses are not listed.

### GET Published course

`GET /api/v1/public/courses/{course_id}`

- `200`: `CourseDto`.
- `400 invalid_id`; `404 course.not_found` when it does not exist or is not `published`.

## Error responses

Every domain or application failure has the same shape:

```json
{
  "detail": {
    "code": "course.overlap",
    "message": "The academy already has a live course “Python Backend Bootcamp” on overlapping dates (2026-12-01 - 2027-02-23)."
  }
}
```

Clients should switch on `code`, never on `message`.

| Status | `ErrorType` | Codes |
| --- | --- | --- |
| 400 | `BAD_REQUEST`, `VALIDATION` | `invalid_id`, `invalid_academy_name`, `invalid_contact_email`, `invalid_rejection_reason`, `invalid_academy_status`, `course.title_empty`, `course.title_too_long`, `course.description_too_short`, `course.description_too_long`, `course.category_empty`, `course.category_too_long`, `course.gallery_empty`, `course.gallery_too_large`, `course.syllabus_empty`, `course.venue_empty`, `course.date_range_invalid`, `course.start_in_past`, `course.capacity_invalid`, `course.cancellation_invalid`, `money.amount_invalid`, `money.amount_negative`, `money.amount_too_many_decimals`, `money.currency_invalid` |
| 404 | `NOT_FOUND` | `academy_not_found`, `course.not_found` |
| 409 | `CONFLICT` | `academy_name_taken`, `contact_email_taken`, `academy_not_pending_verification`, `academy_not_active`, `academy_not_suspended`, `academy_suspended`, `academy_already_suspended`, `academy_already_active`, `academy_already_verified`, `academy_not_verified`, `course.invalid_transition`, `course.overlap`, `course.already_archived`, `course.has_active_enrollments` |
| 422 | (FastAPI) | malformed JSON, wrong field types or missing required fields |
| 429 / 503 / 500 | `TOO_MANY_REQUESTS` / `UNAVAILABLE` / `UNEXPECTED` | mapped, not used by any endpoint yet |

## Quick curl examples

```bash
BASE=http://127.0.0.1:8000/api/v1

# register an academy, then set ACADEMY to the "id" from the response
curl -s -X POST $BASE/academies -H "Content-Type: application/json" \
  -d '{"name": "Code Academy", "contact_email": "info@codeacademy.az"}'
ACADEMY=3f2a9c1e5b7d4e8a9c217d4e5f6a8b90

curl -s $BASE/academies/$ACADEMY
curl -s -X PATCH $BASE/academies/$ACADEMY -H "Content-Type: application/json" -d '{"name": "Code Academy Baku"}'

# admin: grant the verified badge so the academy can publish
curl -s "$BASE/admin/academies?status=Active"
curl -s -X POST $BASE/admin/academies/$ACADEMY/verified-badge

# create a draft, then set COURSE to the "id" from the response
curl -s -X POST $BASE/academies/$ACADEMY/courses -H "Content-Type: application/json" -d '{
  "title": "Python Backend Bootcamp", "description": "Twelve weeks of Python and FastAPI.", "category": "Programming",
  "photos": ["https://cdn.example.az/python/1.jpg"], "syllabus": [{"order": 1, "title": "Python basics"}],
  "venue_address": "Nizami street 10, Baku", "class_time": "19:00",
  "start_date": "2026-12-01", "end_date": "2027-02-23", "price_amount": "450.00", "capacity": 20,
  "refund_tiers": [{"days_before": 10, "refund_percent": 100}], "last_cancellation_days_before": 3}'
COURSE=9b1d4c7a2e3f4a5b8c6d7e8f9a0b1c2d

# lifecycle
curl -s -X POST $BASE/academies/$ACADEMY/courses/$COURSE/publish
curl -s -X POST $BASE/academies/$ACADEMY/courses/$COURSE/pause
curl -s -X POST $BASE/academies/$ACADEMY/courses/$COURSE/resume
curl -s $BASE/academies/$ACADEMY/courses

# public listing
curl -s $BASE/public/courses
curl -s $BASE/public/courses/$COURSE

# cancel and archive
curl -s -X POST $BASE/academies/$ACADEMY/courses/$COURSE/cancel
curl -s -X DELETE $BASE/academies/$ACADEMY/courses/$COURSE

# admin: suspend, reactivate, revoke the badge
curl -s -X POST $BASE/admin/academies/$ACADEMY/suspend
curl -s -X POST $BASE/admin/academies/$ACADEMY/reactivate
curl -s -X DELETE $BASE/admin/academies/$ACADEMY/verified-badge
```
