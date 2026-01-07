"""
Feature flags per user.

uv run uvicorn examples.feature_flags:app --reload
curl localhost:8000/config -H "x-user: alice"
curl localhost:8000/config -H "x-user: bob"
"""

import hashlib
from dataclasses import dataclass

from fastapi import FastAPI
from nodnod import scalar_node
from starlette.requests import Request

from fastapi_nodnod import create_scope, nodnod_route


@dataclass
class User:
    id: str


@dataclass
class Flags:
    new_ui: bool
    dark_mode: bool


FLAGS: dict[str, float] = {
    "new_ui": 0.5,
    "dark_mode": 1.0,
}


def in_rollout(user_id: str, flag: str, pct: float) -> bool:
    h = hashlib.md5(f"{user_id}:{flag}".encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF < pct


class FlagService:
    def flags_for(self, user: User) -> Flags:
        return Flags(
            new_ui=in_rollout(user.id, "new_ui", FLAGS["new_ui"]),
            dark_mode=in_rollout(user.id, "dark_mode", FLAGS["dark_mode"]),
        )


scope = create_scope()
scope.set(FlagService, FlagService())


@scalar_node
class CurrentUser:
    @classmethod
    def __compose__(cls, request: Request) -> User:
        return User(request.headers.get("x-user", "anon"))


@scalar_node
class UserFlags:
    @classmethod
    def __compose__(cls, user: CurrentUser, svc: FlagService) -> Flags:
        return svc.flags_for(user)


app = FastAPI()


@app.get("/config")
@nodnod_route(scope=scope.scope)
async def config(user: CurrentUser, flags: UserFlags) -> dict[str, str | bool]:
    return {"user": user.id, "new_ui": flags.new_ui, "dark_mode": flags.dark_mode}
