from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from mod1_auth.config import Settings
from mod1_auth.security import (
    TokenService,
    TokenValidationError,
    build_jwks,
    generate_private_key,
    load_key_material,
)


@pytest.fixture(scope="module")
def material(tmp_path_factory):
    path = tmp_path_factory.mktemp("keys") / "auth.pem"
    generate_private_key(path)
    return load_key_material(path)


@pytest.fixture
def tokens(material, tmp_path):
    settings = Settings(
        database_url="sqlite:///unused.db",
        jwt_private_key_path=tmp_path / "key.pem",
        jwt_issuer="test-issuer",
        _env_file=None,
    )
    return TokenService(material, settings)


def test_issue_token_is_independently_verifiable(tokens, material):
    user_id = uuid4()
    response = tokens.issue(user_id)
    header = jwt.get_unverified_header(response.access_token)
    assert header == {"alg": "RS256", "kid": material.kid, "typ": "JWT"}
    claims = jwt.decode(
        response.access_token,
        material.public_key,
        algorithms=["RS256"],
        issuer="test-issuer",
        audience="engenharia-software-api",
        options={"require": ["sub", "iss", "aud", "iat", "exp", "jti"]},
    )
    assert claims["sub"] == str(user_id)
    assert claims["exp"] - claims["iat"] == 1800
    assert UUID(claims["jti"])
    assert set(claims) == {"sub", "iss", "aud", "iat", "exp", "jti"}
    assert response.token_type == "bearer"
    assert response.expires_in == 1800
    assert tokens.verify(response.access_token).sub == user_id
    assert tokens.issue(user_id).access_token != response.access_token


def claims_now():
    now = int(datetime.now(UTC).timestamp())
    return dict(
        sub=str(uuid4()),
        iss="test-issuer",
        aud="engenharia-software-api",
        iat=now,
        exp=now + 1800,
        jti=str(uuid4()),
    )


INVALID_CLAIMS = [
    {"iss": "wrong"},
    {"aud": "wrong"},
    {"aud": ["engenharia-software-api"]},
    {"sub": "bad"},
    {"jti": "bad"},
    {"iat": True},
    {"exp": True},
    {"iat": "100"},
    {"exp": "200"},
]


@pytest.mark.parametrize("override", INVALID_CLAIMS)
def test_verify_rejects_invalid_claims(tokens, material, override):
    token = jwt.encode(
        claims_now() | override,
        material.private_key,
        algorithm="RS256",
        headers={"kid": material.kid},
    )
    with pytest.raises(TokenValidationError):
        tokens.verify(token)


@pytest.mark.parametrize("missing", ["sub", "iss", "aud", "iat", "exp", "jti"])
def test_verify_requires_each_claim(tokens, material, missing):
    claims = claims_now()
    del claims[missing]
    token = jwt.encode(
        claims, material.private_key, algorithm="RS256", headers={"kid": material.kid}
    )
    with pytest.raises(TokenValidationError):
        tokens.verify(token)


@pytest.mark.parametrize(
    "kind",
    [
        "expired",
        "future",
        "order",
        "none",
        "hmac",
        "wrong-key",
        "tampered",
        "unknown-kid",
        "wrong-typ",
    ],
)
def test_verify_rejects_invalid_tokens(tokens, material, kind):
    claims = claims_now()
    key = material.private_key
    algorithm = "RS256"
    header = {"kid": material.kid, "typ": "JWT"}
    if kind == "expired":
        claims.update(iat=claims["iat"] - 1800, exp=claims["iat"] - 30)
    elif kind == "future":
        claims.update(iat=claims["iat"] + 60, exp=claims["exp"] + 60)
    elif kind == "order":
        claims["exp"] = claims["iat"]
    elif kind == "none":
        algorithm, key = "none", None
    elif kind == "hmac":
        algorithm, key = "HS256", "synthetic-secret-at-least-32-bytes!"
    elif kind == "wrong-key":
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    elif kind == "unknown-kid":
        header["kid"] = "unknown"
    elif kind == "wrong-typ":
        header["typ"] = "other"
    token = jwt.encode(claims, key, algorithm=algorithm, headers=header)
    if kind == "tampered":
        pieces = token.split(".")
        pieces[1] = ("A" if pieces[1][0] != "A" else "B") + pieces[1][1:]
        token = ".".join(pieces)
    with pytest.raises(TokenValidationError):
        tokens.verify(token)


def test_jwks_contains_only_public_rsa_fields(tokens, material):
    jwks = build_jwks(material)
    assert len(jwks["keys"]) == 1
    key = jwks["keys"][0]
    assert set(key) == {"kty", "use", "alg", "kid", "n", "e"}
    assert key["e"] == "AQAB"
    assert "=" not in key["n"]
    public = jwt.PyJWK.from_dict(key).key
    assert (
        jwt.decode(
            tokens.issue(uuid4()).access_token,
            public,
            algorithms=["RS256"],
            issuer="test-issuer",
            audience="engenharia-software-api",
        )["iss"]
        == "test-issuer"
    )


def test_key_generation_never_overwrites_existing_file(tmp_path):
    path = tmp_path / "key.pem"
    generate_private_key(path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        generate_private_key(path)
    assert path.read_bytes() == before
    assert load_key_material(path).kid == load_key_material(path).kid


@pytest.mark.parametrize("kind", ["invalid", "short"])
def test_load_rejects_invalid_key(tmp_path, kind):
    path = tmp_path / "key.pem"
    value = b"invalid PEM"
    if kind == "short":
        value = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    path.write_bytes(value)
    with pytest.raises(ValueError):
        load_key_material(path)
