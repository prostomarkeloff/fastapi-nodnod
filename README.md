<div align="center">

# fastapi-nodnod

**nodnod DI for FastAPI**

</div>

---

```python
from fastapi import FastAPI, HTTPException
from nodnod import scalar_node
from starlette.requests import Request

from fastapi_nodnod import nodnod_route

@scalar_node
class CurrentUser:
    @classmethod
    def __compose__(cls, request: Request) -> str:
        user = request.headers.get("x-user")
        if not user:
            raise HTTPException(401)
        return user

@scalar_node
class RequireAdmin:
    @classmethod
    def __compose__(cls, user: CurrentUser) -> None:
        if user not in ["alice", "admin"]:
            raise HTTPException(403)

app = FastAPI()

@app.get("/admin")
@nodnod_route
async def admin(user: CurrentUser, _: RequireAdmin) -> dict[str, str]:
    return {"welcome": user}
```

`CurrentUser` → `RequireAdmin` → endpoint. Graph builds itself.

---

## What is this

[nodnod](https://github.com/timoniq/nodnod) integration with FastAPI. Use nodnod's dependency graph in endpoints.

## Why

FastAPI with `Annotated`:

```python
from typing import Annotated
from fastapi import Depends

def get_user(request: Request) -> str: ...
def require_admin(user: str = Depends(get_user)) -> None: ...

CurrentUser = Annotated[str, Depends(get_user)]

@app.get("/admin")
async def admin(user: CurrentUser, _: Annotated[None, Depends(require_admin)]): ...
```

nodnod:

```python
@scalar_node
class CurrentUser:
    @classmethod
    def __compose__(cls, request: Request) -> str: ...

@scalar_node
class RequireAdmin:
    @classmethod
    def __compose__(cls, user: CurrentUser) -> None: ...

@app.get("/admin")
@nodnod_route
async def admin(user: CurrentUser, _: RequireAdmin): ...
```

**When nodnod wins:**
- Complex graphs (auth → permissions → rate limits → audit)
- Reusable nodes as libraries
- Multi-tenant isolation, feature flags

**When Depends is enough:**
- Simple deps (parse header, get db)

## Install

```bash
uv add git+https://github.com/prostomarkeloff/fastapi-nodnod.git
```

## Scopes

By default, every request creates a fresh scope. All nodes resolve from scratch.

For singletons (DBPool, Config) — create a shared scope:

```
Shared Scope (lives forever):
  ├── DBPool
  ├── Config
  │
  ├── Request 1 Scope (child):
  │     └── CurrentUser
  │
  ├── Request 2 Scope (child):
        └── CurrentUser
```

```python
from fastapi_nodnod import create_scope, nodnod_route

scope = create_scope()
scope.set(DBPool, create_pool())
scope.set(Config, load_config())

@app.get("/users")
@nodnod_route(scope=scope.scope)
async def list_users(db: DBPool, user: CurrentUser):
    ...
```

Multiple scopes for different route groups:

```python
public_scope = create_scope()
public_scope.set(RateLimit, RateLimit(100))

admin_scope = create_scope()
admin_scope.set(RateLimit, RateLimit(1000))

@app.get("/public")
@nodnod_route(scope=public_scope.scope)
async def public(): ...

@app.get("/admin")
@nodnod_route(scope=admin_scope.scope)
async def admin(): ...
```

## Examples

```bash
uv run uvicorn examples.simple:app --reload
uv run uvicorn examples.tenant_isolation:app --reload
uv run uvicorn examples.feature_flags:app --reload
```

---

[@prostomarkeloff](https://github.com/prostomarkeloff)
