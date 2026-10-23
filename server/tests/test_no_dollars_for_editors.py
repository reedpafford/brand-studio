"""Guard: any response that can carry a dollar field (`*_usd`) must be owner-only."""

from fastapi.routing import APIRoute

from app.auth import owner_only


def _dollar_schemas(openapi: dict) -> set[str]:
    return {
        name
        for name, schema in openapi["components"]["schemas"].items()
        if any(prop.endswith("_usd") for prop in schema.get("properties", {}))
    }


def _needs_owner(dependant) -> bool:
    return any(d.call is owner_only or _needs_owner(d) for d in dependant.dependencies)


def test_every_route_returning_dollars_is_owner_only(app):
    dollar = _dollar_schemas(app.openapi())
    assert dollar, "expected at least one dollar schema (UsageOut)"
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.response_model is None:
            continue
        text = str(route.response_model)
        if any(name in text for name in dollar):
            assert _needs_owner(route.dependant), f"{route.path} returns dollars to editors"
