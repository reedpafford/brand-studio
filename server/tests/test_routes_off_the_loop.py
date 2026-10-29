import inspect

from fastapi.routing import APIRoute

from app.db import get_db


def _routes(routes):
    for route in routes:
        inner = getattr(route, "original_router", None)  # an included router, listed whole
        yield from _routes(inner.routes) if inner else [route]


def _uses_db(dependant) -> bool:
    return any(d.call is get_db or _uses_db(d) for d in dependant.dependencies)


def test_no_async_route_touches_the_database(app):
    """The database calls block, so a route that makes them is a plain def and runs on a worker
    thread. An async one would hold the whole server while it waits for SQLite's lock, so the
    request holding that lock could never finish (the browser tests' "database is locked")."""
    held = [
        route.path
        for route in _routes(app.routes)
        if isinstance(route, APIRoute)
        and inspect.iscoroutinefunction(route.endpoint)
        and _uses_db(route.dependant)
    ]
    assert any(isinstance(r, APIRoute) for r in _routes(app.routes))
    assert held == []
