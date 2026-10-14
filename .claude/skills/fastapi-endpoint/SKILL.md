---
name: fastapi-endpoint
description: Use when adding or modifying a FastAPI route. Enforces the company layered layout (api/schemas/services/models), auth dependency, Pydantic boundaries, and parameterized DB access.
---

# FastAPI endpoint

## When to use

The user is adding a new HTTP endpoint, or extending an existing one, in a FastAPI service in this repo.

## Layout (mandatory)

```
app/
  api/<resource>.py        # APIRouter — thin: parse, call service, return
  schemas/<resource>.py    # Pydantic request/response models
  services/<resource>.py   # business logic, no FastAPI imports
  models/<resource>.py     # SQLAlchemy / SQLModel tables
  deps.py                  # shared dependencies (get_db, current_user, …)
```

## Required checklist for every new route

1. **Router** declared with a `prefix` and `tags`, mounted in `app/main.py`.
2. **Pydantic schemas** for request body and response — never return raw ORM objects.
3. **Auth dependency**: `current_user = Depends(get_current_user)` unless the route is explicitly public (document that in the docstring).
4. **Authorization check** inside the service layer, not the router (tenant scoping, RBAC).
5. **DB session** injected via `Depends(get_db)` — do not create a session inside the handler.
6. **SQL via ORM or `text()` with bound params**. No f-strings into SQL. Ever.
7. **Status codes**: 201 for create, 204 for delete, 404 for missing, 409 for conflicts, 422 is automatic from Pydantic.
8. **Pagination** for list endpoints: `limit`, `offset` or cursor — never return unbounded results.
9. **Logging**: structured (`logger.info("user.exported", extra={"user_id": ...})`) — never log full request bodies, tokens, or PII.
10. **OpenAPI**: descriptive `summary`, `response_model`, and `responses={401: ..., 404: ...}`.

## Template

```python
# app/api/users.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserOut, UserCreate
from app.services import users as users_svc

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Email already exists"}},
)
async def create_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> UserOut:
    """Create a user. Requires `users:write` permission."""
    user = await users_svc.create(db, payload=payload, actor=actor)
    return UserOut.model_validate(user)
```

## Tests required

- happy-path 201
- 401 when unauthenticated
- 403 when authenticated but lacking permission
- 409 (or domain-specific) for conflict
- 422 boundary (Pydantic validation)

Hand off to the **tester** subagent to write these.
