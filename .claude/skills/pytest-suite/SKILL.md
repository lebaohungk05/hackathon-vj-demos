---
name: pytest-suite
description: Use when writing or extending pytest tests for FastAPI services. Covers async clients, DB isolation, fixtures, parametrize, auth assertions.
---

# pytest

## Layout

```
tests/
  conftest.py            # app, db, client, auth fixtures
  unit/                  # pure logic, no IO
  api/                   # FastAPI integration tests
  integration/           # cross-service / DB-heavy (mark slow)
  fixtures/              # JSON / SQL fixtures, anonymized
```

## Core fixtures (drop into `conftest.py`)

```python
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.deps import get_db


@pytest_asyncio.fixture
async def db_session(monkeypatch) -> AsyncSession:
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost:5433/test")
    async with engine.begin() as conn:
        # create schema for test, or use migrations on a scratch DB
        ...
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    async def _override_db():
        yield db_session
    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token-for-fixture-user"}
```

## Rules

1. **DB tests use a disposable database.** Spin up via `docker compose -f docker-compose.test.yml` or `pytest-postgresql`. Never the staging DB.
2. **Each test rolls back** its transaction in the fixture teardown.
3. **`parametrize` over copy-paste.** If 3 tests differ only in inputs/expected outputs, parametrize.
4. **Marks**: `@pytest.mark.slow`, `@pytest.mark.integration`, `@pytest.mark.requires_azure`. Run unit tests by default; CI runs marked tests in a separate job.
5. **No real secrets** — use `monkeypatch.setenv("DB_PASSWORD", "test")`.
6. **No `time.sleep`** in tests. Use `freezegun` for time, `pytest-asyncio` for async waits, or `respx`/`msw`-style mocking.
7. **Auth tests are mandatory** on every new endpoint: 401 when missing token, 403 when token lacks permission.

## Example: API test

```python
import pytest

@pytest.mark.asyncio
async def test_create_user_requires_auth(client):
    r = await client.post("/users", json={"email": "a@b.co", "display_name": "A"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_user_happy_path(client, auth_headers):
    r = await client.post(
        "/users",
        headers=auth_headers,
        json={"email": "a@b.co", "display_name": "A"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "a@b.co"
    assert "id" in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"email": "not-an-email", "display_name": "A"}, 422),
        ({"email": "a@b.co"}, 422),  # missing display_name
    ],
)
async def test_create_user_validation(client, auth_headers, payload, expected):
    r = await client.post("/users", headers=auth_headers, json=payload)
    assert r.status_code == expected
```

## Commands

```bash
pytest -q                       # quick unit run
pytest -q -m "not slow"         # default CI scope
pytest -q --cov=app --cov-report=term-missing
pytest -q tests/api/test_users.py::test_create_user_happy_path  # single test
```
