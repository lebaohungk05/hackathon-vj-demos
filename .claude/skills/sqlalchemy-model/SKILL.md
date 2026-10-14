---
name: sqlalchemy-model
description: Use when adding or changing a database table / SQLAlchemy or SQLModel model. Enforces async session usage, parameterized queries, and safe Alembic migrations.
---

# SQLAlchemy / SQLModel

## When to use

Adding a table, adding/removing a column, changing a constraint, or writing a non-trivial query.

## Rules

1. **Async everywhere** for new code. `AsyncSession`, `async def`, `await session.execute(...)`. Mixing sync and async sessions is forbidden.
2. **No raw f-string SQL.** Use ORM expressions, or `text("... :param ...")` with `bindparams`.
3. **PK**: `id: UUID` (default `uuid4`) for new tables — not autoincrement int, which leaks volume.
4. **Timestamps**: `created_at`, `updated_at` (`server_default=func.now()`, `onupdate=func.now()`).
5. **Soft delete only when required.** Default to hard delete; if soft, add `deleted_at` and filter in a base query helper.
6. **Indexes**: every FK gets an index. Composite indexes for known query patterns (document the pattern in a comment).
7. **Tenant scoping**: if multi-tenant, every table carries `tenant_id` and every query filters by it. Build a base query helper rather than relying on memory.

## Template (SQLModel)

```python
# app/models/user.py
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, nullable=False)
    email: str = Field(index=True, unique=True, nullable=False, max_length=320)
    display_name: str = Field(nullable=False, max_length=200)
    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(sa_column_kwargs={"server_default": func.now()}, nullable=False)
    updated_at: datetime = Field(
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
        nullable=False,
    )
```

## Migrations (Alembic)

- Generate: `alembic revision --autogenerate -m "AB#1234 add users.is_active"`.
- **Read the generated file before committing.** Autogenerate misses indexes, server defaults, and CHECK constraints.
- **Non-null on existing tables**: do it in two deploys — add nullable + backfill + set non-null. Never in one migration on a hot table.
- **Drops**: separate PR, run after the code that references the column is fully removed.
- **Long migrations**: `op.execute("SET lock_timeout = '5s'")` at top; consider `CREATE INDEX CONCURRENTLY` for Postgres.
- Test with `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` against a scratch DB.

## Cosmos DB note

For Cosmos containers we do **not** use SQLAlchemy. Use the official `azure-cosmos` async client, and choose the partition key explicitly (document it in a comment on the repository class). Never query without a partition key in hot paths.

## Azure SQL note

Same models work via `aioodbc` + `mssql+aioodbc://`. Watch out for collation defaults — use `Latin1_General_100_CI_AS_SC_UTF8` for new DBs.
