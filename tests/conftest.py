import pytest
from fastapi.testclient import TestClient

from mod1_auth.config import Settings
from mod1_auth.database import create_engine_for_url, create_session_factory, initialize_database
from mod1_auth.repositories import UserRepository
from mod1_auth.security import generate_private_key
from mod1_auth.services import UserService


@pytest.fixture(scope="session")
def key_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("api-keys") / "auth.pem"
    generate_private_key(path)
    return path


@pytest.fixture
def settings(tmp_path, key_path):
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        jwt_private_key_path=key_path,
        jwt_issuer="test-issuer",
        _env_file=None,
    )


@pytest.fixture
def engine(settings):
    engine = create_engine_for_url(settings.database_url.get_secret_value())
    initialize_database(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def user(engine):
    with create_session_factory(engine)() as session:
        return UserService(UserRepository(session)).create_user(
            email="caue@example.com", display_name="Caue", password="  password12345  "
        )


@pytest.fixture
def app(settings, engine):
    from mod1_auth.main import create_app

    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client
