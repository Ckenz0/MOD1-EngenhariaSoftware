import pytest
import test_postgresql as pg_tests


@pytest.mark.parametrize("override", ["host=remote.invalid", "hostaddr=203.0.113.1"])
def test_disposable_postgres_rejects_address_overrides_before_connecting(monkeypatch, override):
    monkeypatch.setenv("TEST_DATABASE_URL", f"postgresql+psycopg://localhost/disposable?{override}")

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Address override reached database initialization")

    monkeypatch.setattr(pg_tests, "create_engine_for_url", unexpected_connection)
    fixture = pg_tests.pg_database.__wrapped__()
    with pytest.raises(pytest.fail.Exception, match="disposable local PostgreSQL"):
        next(fixture)
