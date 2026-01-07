"""
Multi-tenant: all queries scoped to tenant.

uv run uvicorn examples.tenant_isolation:app --reload
curl localhost:8000/projects -H "x-tenant: acme"
curl localhost:8000/projects -H "x-tenant: startup"
"""

from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from nodnod import scalar_node
from pydantic import BaseModel
from starlette.requests import Request

from fastapi_nodnod import create_scope, nodnod_route


@dataclass
class Tenant:
    id: str
    name: str


@dataclass
class Project:
    id: int
    tenant_id: str
    name: str


TENANTS = {
    "acme": Tenant("acme", "Acme Corp"),
    "startup": Tenant("startup", "Startup Inc"),
}

PROJECTS = [
    Project(1, "acme", "Website"),
    Project(2, "acme", "Mobile App"),
    Project(3, "startup", "MVP"),
]


class TenantDB:
    def __init__(self, tenant: Tenant) -> None:
        self.tenant = tenant

    def projects(self) -> list[Project]:
        return [p for p in PROJECTS if p.tenant_id == self.tenant.id]

    def create_project(self, name: str) -> Project:
        p = Project(len(PROJECTS) + 1, self.tenant.id, name)
        PROJECTS.append(p)
        return p


scope = create_scope()


@scalar_node
class CurrentTenant:
    @classmethod
    def __compose__(cls, request: Request) -> Tenant:
        tid = request.headers.get("x-tenant", "")
        tenant = TENANTS.get(tid)
        if not tenant:
            raise HTTPException(400, "unknown tenant")
        return tenant


@scalar_node
class DB:
    @classmethod
    def __compose__(cls, tenant: CurrentTenant) -> TenantDB:
        return TenantDB(tenant)


class NewProject(BaseModel):
    name: str


app = FastAPI()


@app.get("/projects")
@nodnod_route(scope=scope.scope)
async def list_projects(db: DB) -> list[dict[str, str | int]]:
    return [{"id": p.id, "name": p.name} for p in db.projects()]


@app.post("/projects")
@nodnod_route(scope=scope.scope)
async def create_project(body: NewProject, db: DB) -> dict[str, str | int]:
    p = db.create_project(body.name)
    return {"id": p.id, "name": p.name}
