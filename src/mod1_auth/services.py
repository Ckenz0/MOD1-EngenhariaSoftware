from datetime import UTC, datetime
from uuid import UUID, uuid4

from email_validator import validate_email

from mod1_auth.domain import InvalidCredentialsError, User
from mod1_auth.repositories import UserRepository
from mod1_auth.security import (
    TokenResponse,
    TokenService,
    TokenValidationError,
    hash_password,
    verify_password,
)

_dummy_password_hash = hash_password("dummy-password-never-used-for-login")


def normalize_email(email: str) -> str:
    return email.strip().lower()


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def create_user(self, *, email: str, display_name: str, password: str) -> User:
        email = normalize_email(email)
        validate_email(email, check_deliverability=False)
        display_name = display_name.strip()
        if not 1 <= len(display_name) <= 120:
            raise ValueError("Name must contain 1 to 120 characters")
        if not 12 <= len(password) <= 128:
            raise ValueError("Password must contain 12 to 128 characters")
        return self.repository.add(
            User(uuid4(), email, display_name, hash_password(password), True, datetime.now(UTC))
        )

    def get_user_by_email(self, email: str) -> User | None:
        return self.repository.get_by_email(normalize_email(email))

    def get_user_by_id(self, user_id: UUID) -> User | None:
        return self.repository.get_by_id(user_id)

    def set_user_active(self, user_id: UUID, active: bool) -> User:
        return self.repository.set_active(user_id, active)


class AuthService:
    def __init__(self, repository: UserRepository, tokens: TokenService) -> None:
        self.repository = repository
        self.tokens = tokens

    def authenticate(self, email: str, password: str) -> TokenResponse:
        user = self.repository.get_by_email(normalize_email(email))
        valid = verify_password(password, user.password_hash if user else _dummy_password_hash)
        if user is None or not valid or not user.is_active:
            raise InvalidCredentialsError("Invalid credentials")
        return self.tokens.issue(user.id)

    def current_user(self, token: str) -> User:
        try:
            claims = self.tokens.verify(token)
        except TokenValidationError as exc:
            raise InvalidCredentialsError("Invalid authentication credentials") from exc
        user = self.repository.get_by_id(claims.sub)
        if user is None or not user.is_active:
            raise InvalidCredentialsError("Invalid authentication credentials")
        return user
