def test_health_reports_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_postgres_driver_is_installed():
    """Production uses Postgres (deploy/docker-compose.yml); the engine must load its driver."""
    from app.db import make_sessionmaker

    engine = make_sessionmaker("postgresql+psycopg://u:p@db/brand").kw["bind"]
    assert engine.dialect.driver == "psycopg"
