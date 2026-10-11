from uuid import UUID

import pytest
from pydantic import ValidationError

from mod1_auth.config import Settings
from mod1_auth.database import create_engine_for_url, create_session_factory, initialize_database
from mod1_auth.domain import DuplicateEmailError
from mod1_auth.repositories import UserRepository
from mod1_auth.security import verify_password
from mod1_auth.services import UserService


@pytest.fixture
def session(tmp_path):
    engine = create_engine_for_url(f"sqlite:///{tmp_path / 'users.db'}")
    initialize_database(engine)
    with create_session_factory(engine)() as session:
        yield session
    engine.dispose()


def test_user_normalization_hash_and_reload(session):
    service = UserService(UserRepository(session))
    password = "  long password literal  "
    user = service.create_user(email=" Caue@Example.com ", display_name=" Caue ", password=password)
    assert user.email == "caue@example.com"
    assert user.display_name == "Caue"
    assert isinstance(user.id, UUID)
    assert user.is_active
    assert user.password_hash != password
    assert verify_password(password, user.password_hash)
    assert not verify_password(password.strip(), user.password_hash)
    session.expire_all()
    reloaded = service.get_user_by_email(" CAUE@example.com ")
    assert reloaded.id == user.id
    assert reloaded.created_at.utcoffset().total_seconds() == 0


def test_duplicate_normalized_email_is_rejected(session):
    service = UserService(UserRepository(session))
    user = service.create_user(
        email="caue@example.com", display_name="Caue", password="password12345"
    )
    with pytest.raises(DuplicateEmailError):
        service.create_user(
            email=" CAUE@EXAMPLE.COM ", display_name="Other", password="password12345"
        )
    assert service.get_user_by_id(user.id).display_name == "Caue"
    second = service.create_user(
        email="other@example.com", display_name="Other", password="password12345"
    )
    assert second.id != user.id


@pytest.mark.parametrize("length", [11, 129])
def test_invalid_password_length(session, length):
    with pytest.raises(ValueError):
        UserService(UserRepository(session)).create_user(
            email="a@example.com", display_name="A", password="x" * length
        )


@pytest.mark.parametrize("length", [12, 128])
def test_password_boundary_is_accepted(session, length):
    user = UserService(UserRepository(session)).create_user(
        email="a@example.com", display_name="A", password="x" * length
    )
    assert verify_password("x" * length, user.password_hash)


@pytest.mark.parametrize(
    "email,name", [("invalid", "A"), ("a@example.com", " "), ("a@example.com", "x" * 121)]
)
def test_invalid_user_data(session, email, name):
    with pytest.raises(ValueError):
        UserService(UserRepository(session)).create_user(
            email=email, display_name=name, password="password12345"
        )


def test_user_survives_new_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'persistent.db'}"
    first = create_engine_for_url(url)
    initialize_database(first)
    with create_session_factory(first)() as session:
        user = UserService(UserRepository(session)).create_user(
            email="a@example.com", display_name="A", password="password12345"
        )
    first.dispose()
    second = create_engine_for_url(url)
    with create_session_factory(second)() as session:
        assert UserRepository(session).get_by_id(user.id).email == "a@example.com"
    second.dispose()


def test_settings_require_database_issuer_and_key(monkeypatch):
    for name in ("DATABASE_URL", "JWT_ISSUER", "JWT_PRIVATE_KEY_PATH"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "overrides",
    [
        {"access_token_expire_minutes": 0},
        {"access_token_expire_minutes": -1},
        {"database_schema": "bad;drop"},
        {"cors_origins": ["*"]},
        {"cors_origins": ["https://example.com/path"]},
    ],
)
def test_settings_reject_invalid_configuration(tmp_path, overrides):
    values = dict(
        database_url="sqlite:///test.db",
        jwt_issuer="test",
        jwt_private_key_path=tmp_path / "key.pem",
        _env_file=None,
    )
    with pytest.raises(ValidationError):
        Settings(**(values | overrides))


def test_database_url_is_redacted(tmp_path):
    settings = Settings(
        database_url="postgresql+psycopg://user:secret-value@localhost/auth",
        jwt_issuer="test",
        jwt_private_key_path=tmp_path / "key.pem",
        _env_file=None,
    )
    assert "secret-value" not in repr(settings)
    assert "secret-value" not in settings.model_dump_json()
