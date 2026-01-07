import typing

from fastapi import Depends, FastAPI, Query
from fastapi.testclient import TestClient
from nodnod import scalar_node
from starlette.requests import Request

from fastapi_nodnod import create_scope, nodnod_route


class TestBasic:
    def test_passthrough(self) -> None:
        app = FastAPI()

        @app.get("/")
        @nodnod_route
        async def handler() -> dict[str, str]:
            return {"ok": "true"}

        assert TestClient(app).get("/").json() == {"ok": "true"}

    def test_node_from_request(self) -> None:
        @scalar_node
        class Path:
            @classmethod
            def __compose__(cls, request: Request) -> str:
                return request.url.path

        app = FastAPI()

        @app.get("/test")
        @nodnod_route
        async def handler(p: Path) -> dict[str, str]:  # type: ignore[type-arg]
            return {"path": p}

        assert TestClient(app).get("/test").json() == {"path": "/test"}

    def test_node_from_header(self) -> None:
        @scalar_node
        class Token:
            @classmethod
            def __compose__(cls, request: Request) -> str:
                return request.headers.get("x-token", "none")

        app = FastAPI()

        @app.get("/")
        @nodnod_route
        async def handler(t: Token) -> dict[str, str]:  # type: ignore[type-arg]
            return {"token": t}

        client = TestClient(app)
        assert client.get("/").json() == {"token": "none"}
        assert client.get("/", headers={"x-token": "abc"}).json() == {"token": "abc"}

    def test_node_chain(self) -> None:
        @scalar_node
        class A:
            @classmethod
            def __compose__(cls) -> int:
                return 10

        @scalar_node
        class B:
            @classmethod
            def __compose__(cls, a: A) -> int:  # type: ignore[type-arg]
                return a * 2  # type: ignore[operator]

        app = FastAPI()

        @app.get("/")
        @nodnod_route
        async def handler(b: B) -> dict[str, int]:  # type: ignore[type-arg]
            return {"b": b}

        assert TestClient(app).get("/").json() == {"b": 20}


class TestMixed:
    def test_node_with_query(self) -> None:
        @scalar_node
        class Env:
            @classmethod
            def __compose__(cls) -> str:
                return "prod"

        app = FastAPI()

        @app.get("/")
        @nodnod_route
        async def handler(env: Env, page: int = Query(1)) -> dict[str, str | int]:  # type: ignore[type-arg]
            return {"env": env, "page": page}

        client = TestClient(app)
        assert client.get("/").json() == {"env": "prod", "page": 1}
        assert client.get("/?page=5").json() == {"env": "prod", "page": 5}

    def test_node_with_depends(self) -> None:
        def get_db() -> str:
            return "db"

        @scalar_node
        class Svc:
            @classmethod
            def __compose__(cls, request: Request) -> str:
                return request.url.path

        app = FastAPI()

        @app.get("/")
        @nodnod_route
        async def handler(svc: Svc, db: str = Depends(get_db)) -> dict[str, str]:  # type: ignore[type-arg]
            return {"svc": svc, "db": db}

        assert TestClient(app).get("/").json() == {"svc": "/", "db": "db"}

    def test_node_with_path(self) -> None:
        @scalar_node
        class Mult:
            @classmethod
            def __compose__(cls) -> int:
                return 3

        app = FastAPI()

        @app.get("/{n}")
        @nodnod_route
        async def handler(n: int, m: Mult) -> dict[str, int]:  # type: ignore[type-arg]
            return {"r": n * m}  # type: ignore[operator]

        assert TestClient(app).get("/7").json() == {"r": 21}


class TestScope:
    def test_isolation(self) -> None:
        counter = 0

        @scalar_node
        class Counter:
            @classmethod
            def __compose__(cls) -> int:
                nonlocal counter
                counter += 1
                return counter

        app = FastAPI()

        @app.get("/")
        @nodnod_route
        async def handler(c: Counter) -> dict[str, int]:  # type: ignore[type-arg]
            return {"c": c}

        client = TestClient(app)
        assert client.get("/").json() == {"c": 1}
        assert client.get("/").json() == {"c": 2}

    def test_shared_scope(self) -> None:
        class Cfg:
            def __init__(self, v: str) -> None:
                self.v = v

        scope = create_scope()
        scope.set(Cfg, Cfg("x"))

        @scalar_node
        class Path:
            @classmethod
            def __compose__(cls, request: Request) -> str:
                return request.url.path

        app = FastAPI()

        @app.get("/")
        @nodnod_route(scope=scope.scope)
        async def handler(p: Path) -> dict[str, str]:  # type: ignore[type-arg]
            cfg = scope.get(Cfg)
            assert cfg is not None
            return {"p": p, "cfg": cfg.v}

        assert TestClient(app).get("/").json() == {"p": "/", "cfg": "x"}

    def test_multiple_scopes(self) -> None:
        class Tag:
            def __init__(self, v: str) -> None:
                self.v = v

        s1 = create_scope()
        s1.set(Tag, Tag("A"))

        s2 = create_scope()
        s2.set(Tag, Tag("B"))

        @scalar_node
        class Msg:
            @classmethod
            def __compose__(cls) -> str:
                return "ok"

        app = FastAPI()

        @app.get("/a")
        @nodnod_route(scope=s1.scope)
        async def ha(m: Msg) -> dict[str, str]:  # type: ignore[type-arg]
            t = s1.get(Tag)
            assert t is not None
            return {"m": m, "t": t.v}

        @app.get("/b")
        @nodnod_route(scope=s2.scope)
        async def hb(m: Msg) -> dict[str, str]:  # type: ignore[type-arg]
            t = s2.get(Tag)
            assert t is not None
            return {"m": m, "t": t.v}

        client = TestClient(app)
        assert client.get("/a").json() == {"m": "ok", "t": "A"}
        assert client.get("/b").json() == {"m": "ok", "t": "B"}


class TestAsync:
    def test_async_compose(self) -> None:
        @scalar_node
        class Async:
            @classmethod
            async def __compose__(cls, request: Request) -> str:
                return request.method

        app = FastAPI()

        @app.get("/")
        @nodnod_route
        async def handler(a: Async) -> dict[str, str]:  # type: ignore[type-arg]
            return {"a": a}

        assert TestClient(app).get("/").json() == {"a": "GET"}


class TestGenerator:
    def test_cleanup(self) -> None:
        cleaned = False

        @scalar_node
        class Res:
            @classmethod
            def __compose__(cls) -> typing.Generator[str, None, None]:
                nonlocal cleaned
                yield "res"
                cleaned = True

        app = FastAPI()

        @app.get("/")
        @nodnod_route
        async def handler(r: Res) -> dict[str, str]:  # type: ignore[type-arg]
            return {"r": r}

        assert TestClient(app).get("/").json() == {"r": "res"}
        assert cleaned
