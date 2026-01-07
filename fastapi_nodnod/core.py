"""nodnod + FastAPI integration."""

from __future__ import annotations

import functools
import inspect
import typing

import kungfu
from nodnod import EventLoopAgent, Node, Scope, Value
from starlette.requests import Request

T = typing.TypeVar("T")
F = typing.TypeVar("F", bound=typing.Callable[..., typing.Any])


def _is_node(ann: typing.Any) -> bool:
    try:
        return isinstance(ann, type) and issubclass(ann, Node)
    except TypeError:
        return False


async def _run_agent(agent: EventLoopAgent, scope: Scope) -> None:
    run_method: typing.Callable[..., typing.Coroutine[typing.Any, typing.Any, None]] = (
        getattr(agent, "run")
    )
    await run_method(local_scope=scope, mapped_scopes={})


async def _resolve(
    func: typing.Callable[..., typing.Any],
    agent: EventLoopAgent,
    node_params: dict[str, type[Node[typing.Any, typing.Any]]],
    request: Request,
    kwargs: dict[str, typing.Any],
    parent_scope: Scope | None,
) -> typing.Any:
    if parent_scope is not None:
        scope = parent_scope.create_child(detail=f"req:{id(request)}")
    else:
        scope = Scope(detail=f"req:{id(request)}")

    async with scope:
        scope.push(Value(Request, request))
        await _run_agent(agent, scope)

        resolved = dict(kwargs)
        for name, node_type in node_params.items():
            out_type: type[typing.Any] = getattr(node_type, "__type__", node_type)
            match scope.retrieve(out_type):
                case kungfu.Some(value):
                    resolved[name] = value.unbox()
                case kungfu.Nothing():
                    pass

        result = func(**resolved)
        if inspect.iscoroutine(result):
            return await result
        return result


@typing.overload
def nodnod_route(func: F) -> F: ...


@typing.overload
def nodnod_route(func: None = None, *, scope: Scope | None = None) -> typing.Callable[[F], F]: ...


def nodnod_route(
    func: F | None = None,
    *,
    scope: Scope | None = None,
) -> F | typing.Callable[[F], F]:
    """
    Enable nodnod DI for a route.

    @app.get("/")
    @nodnod_route
    async def handler(user: CurrentUser): ...

    @app.get("/")
    @nodnod_route(scope=app_scope.scope)
    async def handler(user: CurrentUser, config: Config): ...
    """

    def decorator(fn: F) -> F:
        sig = inspect.signature(fn)
        hints = typing.get_type_hints(fn)

        node_params: dict[str, type[Node[typing.Any, typing.Any]]] = {}
        for name, param in sig.parameters.items():
            ann = hints.get(name, param.annotation)
            if ann is not inspect.Parameter.empty and _is_node(ann):
                node_params[name] = ann

        if not node_params:
            return fn

        agent = EventLoopAgent.build(set(node_params.values()))

        new_params: list[inspect.Parameter] = []
        for name, param in sig.parameters.items():
            if name not in node_params and name != "request":
                new_params.append(param)
        new_params.append(
            inspect.Parameter("request", inspect.Parameter.KEYWORD_ONLY, annotation=Request)
        )
        new_sig = sig.replace(parameters=new_params)

        @functools.wraps(fn)
        async def wrapper(request: Request, **kwargs: typing.Any) -> typing.Any:
            return await _resolve(fn, agent, node_params, request, kwargs, scope)

        setattr(wrapper, "__signature__", new_sig)
        return typing.cast(F, wrapper)

    if func is not None:
        return decorator(func)
    return decorator


class NodnodScope:
    """Wrapper for shared scope."""

    def __init__(self, detail: str = "app") -> None:
        self._scope = Scope(detail=detail)

    @property
    def scope(self) -> Scope:
        return self._scope

    def set(self, type_: type[T], value: T) -> None:
        self._scope.push(Value(type_, value))

    def get(self, type_: type[T]) -> T | None:
        match self._scope.retrieve(type_):
            case kungfu.Some(v):
                return v.unbox()  # type: ignore[no-any-return]
            case kungfu.Nothing():
                return None


def create_scope(detail: str = "app") -> NodnodScope:
    """Create a shared scope."""
    return NodnodScope(detail=detail)


__all__ = ("nodnod_route", "create_scope", "NodnodScope")
