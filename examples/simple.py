"""
Simple example.

uv run uvicorn examples.simple:app --reload
curl localhost:8000/me -H "x-user: alice"
"""

from fastapi import FastAPI, HTTPException, Query
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
class RequireAdmin:
    @classmethod
    def __compose__(cls, user: CurrentUser) -> None:
        if user not in ["alice", "admin"]:
            raise HTTPException(403)


@app.get("/me")
@nodnod_route
async def me(user: CurrentUser) -> dict[str, str]:
    return {"user": user}


@app.get("/admin")
@nodnod_route
async def admin(user: CurrentUser, _: RequireAdmin) -> dict[str, str]:
    return {"msg": f"welcome {user}"}


@app.get("/search")
@nodnod_route
async def search(user: CurrentUser, q: str = Query(...), limit: int = Query(10)) -> dict[str, str | int]:
    return {"user": user, "q": q, "limit": limit}
