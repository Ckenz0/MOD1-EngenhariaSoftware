from collections.abc import Iterator
from datetime import datetime
from typing import Annotated
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mod1_auth.database import database_is_ready
from mod1_auth.domain import DuplicateEmailError, InvalidCredentialsError, User
from mod1_auth.repositories import UserRepository
from mod1_auth.security import TokenResponse, build_jwks
from mod1_auth.services import AuthService, UserService, normalize_email

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    email: str = Field(max_length=320)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = normalize_email(value)
        try:
            validate_email(normalized, check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValueError("Invalid email address") from exc
        return normalized

    @field_validator("display_name", mode="before")
    @classmethod
    def trimmed_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("display_name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required")
        return value


class RegistrationResponse(BaseModel):
    message: str = "If this email is available, the account is ready. Try signing in."


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
        )


def get_auth_service(request: Request) -> Iterator[AuthService]:
    with request.app.state.sessions() as session:
        yield AuthService(UserRepository(session), request.app.state.tokens)


def get_user_service(request: Request) -> Iterator[UserService]:
    with request.app.state.sessions() as session:
        yield UserService(UserRepository(session))


def register_routes(app: FastAPI) -> None:
    @app.post("/auth/register", status_code=202, response_model=RegistrationResponse)
    def register(
        response: Response,
        registration: RegistrationRequest,
        service: Annotated[UserService, Depends(get_user_service)],
    ) -> RegistrationResponse:
        try:
            service.create_user(
                email=registration.email,
                display_name=registration.display_name,
                password=registration.password,
            )
        except DuplicateEmailError:
            # Same response for existing accounts; never overwrite or reactivate them.
            pass
        response.headers["Cache-Control"] = "no-store"
        return RegistrationResponse()

    @app.post(
        "/auth/token",
        response_model=TokenResponse,
        responses={401: {"description": "Invalid credentials"}},
    )
    def token(
        response: Response,
        form: Annotated[OAuth2PasswordRequestForm, Depends()],
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> TokenResponse:
        try:
            result = service.authenticate(form.username, form.password)
        except InvalidCredentialsError as exc:
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc
        response.headers["Cache-Control"] = "no-store"
        return result

    @app.get(
        "/auth/me",
        response_model=UserResponse,
        responses={401: {"description": "Invalid authentication credentials"}},
    )
    def me(
        token: Annotated[str | None, Depends(oauth2)],
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> UserResponse:
        try:
            if not token:
                raise InvalidCredentialsError()
            return UserResponse.from_user(service.current_user(token))
        except InvalidCredentialsError as exc:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    @app.get("/.well-known/jwks.json")
    def jwks(request: Request) -> dict[str, list[dict[str, str]]]:
        return build_jwks(request.app.state.keys)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", responses={503: {"description": "Database unavailable"}})
    def ready(request: Request, response: Response) -> dict[str, str]:
        if not database_is_ready(request.app.state.engine):
            response.status_code = 503
            return {"status": "unavailable"}
        return {"status": "ready"}
