import pytest

from mod1_auth.database import create_session_factory
from mod1_auth.domain import InvalidCredentialsError
from mod1_auth.repositories import UserRepository
from mod1_auth.security import TokenService, load_key_material
from mod1_auth.services import AuthService


def test_authentication_without_http(engine, settings, user):
    with create_session_factory(engine)() as session:
        repository = UserRepository(session)
        service = AuthService(
            repository, TokenService(load_key_material(settings.jwt_private_key_path), settings)
        )
        token = service.authenticate(" CAUE@EXAMPLE.COM ", "  password12345  ").access_token
        assert service.current_user(token).id == user.id
        with pytest.raises(InvalidCredentialsError):
            service.authenticate(user.email, "wrong")
        with pytest.raises(InvalidCredentialsError):
            service.authenticate("absent@example.com", "wrong")
        repository.set_active(user.id, False)
        with pytest.raises(InvalidCredentialsError):
            service.authenticate(user.email, "  password12345  ")
        with pytest.raises(InvalidCredentialsError):
            service.current_user(token)
