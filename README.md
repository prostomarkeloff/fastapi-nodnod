<div align="center">

# fastapi-nodnod

**nodnod DI for FastAPI**

</div>

---

## What is this

[nodnod](https://github.com/timoniq/nodnod) integration with FastAPI. Use nodnod's dependency graph in FastAPI endpoints.

## Why

FastAPI with `Annotated` is clean, but dependencies are still functions:

```python
from typing import Annotated
from fastapi import Depends

def get_db(): ...
def get_user(db = Depends(get_db)): ...
def get_permissions(user = Depends(get_user)): ...

CurrentUser = Annotated[User, Depends(get_user)]
Permissions = Annotated[list[str], Depends(get_permissions)]

@app.get("/admin")
async def admin(user: CurrentUser, perms: Permissions): ...
```

nodnod — dependencies are **classes with typed composition**:

```python
from nodnod import scalar_node

@scalar_node
class CurrentUser:
    @classmethod
    def __compose__(cls, request: Request, db: DBPool) -> User: ...

@scalar_node
class Permissions:
    @classmethod
    def __compose__(cls, user: CurrentUser) -> list[str]: ...

@app.get("/admin")
@nodnod_route
async def admin(user: CurrentUser, perms: Permissions): ...
```

**When nodnod wins:**
- Complex dependency graphs (auth → permissions → rate limits → audit)
- Reusable nodes packaged as libraries
- Dependencies that need cleanup (generators)
- Multi-tenant isolation, feature flags

**When FastAPI Depends is enough:**
- Simple deps (get db connection, parse header)
- No complex graphs

## Install

```bash
uv add git+https://github.com/prostomarkeloff/fastapi-nodnod.git
```

## Simple example

```python
from fastapi import FastAPI, HTTPException
from nodnod import scalar_node
from starlette.requests import Request
from fastapi_nodnod import nodnod_route

app = FastAPI()

@scalar_node
class CurrentUser:
    @classmethod
    def __compose__(cls, request: Request) -> str:
        user = request.headers.get("x-user")
        if not user:
            raise HTTPException(401)
        return user

@scalar_node
class IsAdmin:
    @classmethod
    def __compose__(cls, user: CurrentUser) -> bool:
        return user == "alice"

@app.get("/admin")
@nodnod_route
async def admin(user: CurrentUser, is_admin: IsAdmin):
    if not is_admin:
        raise HTTPException(403)
    return {"message": f"Welcome {user}"}
```

FastAPI parses HTTP (Query, Path, Body). nodnod resolves services.

## Scopes

By default, every request creates a fresh scope. All nodes are resolved from scratch:

```
Request 1: [Scope] → resolve DBPool → resolve CurrentUser → resolve Permissions
Request 2: [Scope] → resolve DBPool → resolve CurrentUser → resolve Permissions
Request 3: [Scope] → resolve DBPool → resolve CurrentUser → resolve Permissions
```

This is fine for per-request stuff (CurrentUser, Permissions). But DBPool? Config? You don't want to recreate them every request.

**Solution: shared scope.** Put singletons there, request scopes inherit from it:

```
App Scope (lives forever):
  ├── DBPool (created once)
  ├── Config (created once)
  │
  ├── Request 1 Scope (child):
  │     └── CurrentUser (per-request)
  │
  ├── Request 2 Scope (child):
  │     └── CurrentUser (per-request)
```

### How to use

```python
from fastapi_nodnod import create_scope, nodnod_route

# Create app-level scope with singletons
scope = create_scope()
scope.set(DBPool, create_pool())      # created once
scope.set(Config, load_config())      # created once
scope.set(Redis, create_redis())      # created once

# Pass scope to routes
@app.get("/users")
@nodnod_route(scope=scope.scope)
async def list_users(
    db: DBPool,          # from app scope (singleton)
    user: CurrentUser,   # resolved per-request
):
    ...
```

### Multiple scopes

Different route groups can have different scopes:

```python
public_scope = create_scope()
public_scope.set(RateLimit, RateLimit(100))  # 100 req/min

admin_scope = create_scope()
admin_scope.set(RateLimit, RateLimit(1000))  # 1000 req/min
admin_scope.set(AdminDB, create_admin_db())

@app.get("/public/data")
@nodnod_route(scope=public_scope.scope)
async def public_data(limit: RateLimit): ...

@app.get("/admin/data")
@nodnod_route(scope=admin_scope.scope)
async def admin_data(limit: RateLimit, db: AdminDB): ...
```

### Scope API

```python
scope = create_scope("name")      # create scope
scope.set(Type, value)            # put value
scope.get(Type)                   # get value (or None)
scope.scope                       # underlying nodnod.Scope for @nodnod_route
```

## Examples

```bash
# Simple (no scope)
uv run uvicorn examples.simple:app --reload
curl localhost:8000/me -H "x-user: alice"

# Multi-tenant isolation
uv run uvicorn examples.tenant_isolation:app --reload
curl localhost:8000/projects -H "x-tenant: acme"

# Feature flags
uv run uvicorn examples.feature_flags:app --reload
curl localhost:8000/ui-config -H "x-user-id: alice"
```

---

[@prostomarkeloff](https://github.com/prostomarkeloff)
