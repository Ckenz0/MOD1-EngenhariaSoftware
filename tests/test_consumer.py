import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from examples.validate_token import ValidationError, get_jwks_client, validate_token
from mod1_auth.security import build_jwks, load_key_material


@pytest.fixture
def jwks_server(key_path):
    data = json.dumps(build_jwks(load_key_material(key_path))).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/jwks", server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture
def public_path(tmp_path, key_path):
    path = tmp_path / "public.pem"
    path.write_bytes(
        load_key_material(key_path).public_key.public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    return path


def test_consumer_validates_api_token_jwks_and_offline(client, user, jwks_server, public_path):
    token = client.post(
        "/auth/token", data={"username": user.email, "password": "  password12345  "}
    ).json()["access_token"]
    url, server = jwks_server
    assert validate_token(
        token, issuer="test-issuer", audience="engenharia-software-api", jwks_url=url
    )["sub"] == str(user.id)
    server.shutdown()
    assert validate_token(
        token, issuer="test-issuer", audience="engenharia-software-api", public_key_path=public_path
    )["sub"] == str(user.id)
    assert validate_token(
        token, issuer="test-issuer", audience="engenharia-software-api", jwks_url=url
    )["sub"] == str(user.id)


@pytest.mark.parametrize(
    "kind",
    [
        "expired",
        "future",
        "wrong-key",
        "issuer",
        "audience",
        "missing",
        "iat-string",
        "exp-bool",
        "sub",
        "jti",
        "order",
        "none",
        "hmac",
        "typ",
    ],
)
def test_consumer_rejects_invalid_profile(public_path, key_path, kind):
    now = int(datetime.now(UTC).timestamp())
    claims = dict(
        sub=str(uuid4()),
        iss="test-issuer",
        aud="engenharia-software-api",
        iat=now,
        exp=now + 1800,
        jti=str(uuid4()),
    )
    keys = load_key_material(key_path)
    key, algorithm = keys.private_key, "RS256"
    headers = {"kid": keys.kid, "typ": "JWT"}
    if kind == "expired":
        claims.update(iat=now - 1800, exp=now - 30)
    elif kind == "future":
        claims.update(iat=now + 60)
    elif kind == "wrong-key":
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    elif kind == "issuer":
        claims["iss"] = "wrong"
    elif kind == "audience":
        claims["aud"] = "wrong"
    elif kind == "missing":
        del claims["jti"]
    elif kind == "iat-string":
        claims["iat"] = str(now)
    elif kind == "exp-bool":
        claims["exp"] = True
    elif kind in ("sub", "jti"):
        claims[kind] = "invalid"
    elif kind == "order":
        claims["exp"] = now
    elif kind == "none":
        key, algorithm = None, "none"
    elif kind == "hmac":
        key, algorithm = "synthetic-secret-at-least-32-bytes!", "HS256"
    elif kind == "typ":
        headers["typ"] = "other"
    token = jwt.encode(claims, key, algorithm=algorithm, headers=headers)
    with pytest.raises(ValidationError):
        validate_token(
            token,
            issuer="test-issuer",
            audience="engenharia-software-api",
            public_key_path=public_path,
        )


def test_consumer_does_not_trust_token_jku(jwks_server, key_path):
    url, _ = jwks_server
    keys = load_key_material(key_path)
    now = int(datetime.now(UTC).timestamp())
    claims = dict(
        sub=str(uuid4()),
        iss="test-issuer",
        aud="engenharia-software-api",
        iat=now,
        exp=now + 1800,
        jti=str(uuid4()),
    )
    token = jwt.encode(
        claims,
        keys.private_key,
        algorithm="RS256",
        headers={"kid": keys.kid, "jku": "http://127.0.0.1:1/untrusted"},
    )
    assert (
        validate_token(
            token, issuer="test-issuer", audience="engenharia-software-api", jwks_url=url
        )["sub"]
        == claims["sub"]
    )
    assert get_jwks_client(url) is get_jwks_client(url)


def test_unavailable_jwks_and_unknown_key_fail_closed(jwks_server, key_path):
    url, _ = jwks_server
    keys = load_key_material(key_path)
    now = int(datetime.now(UTC).timestamp())
    claims = dict(
        sub=str(uuid4()),
        iss="test-issuer",
        aud="engenharia-software-api",
        iat=now,
        exp=now + 1800,
        jti=str(uuid4()),
    )
    token = jwt.encode(claims, keys.private_key, algorithm="RS256", headers={"kid": "unknown"})
    for source in (url, "http://127.0.0.1:1/unavailable"):
        with pytest.raises(ValidationError):
            validate_token(
                token, issuer="test-issuer", audience="engenharia-software-api", jwks_url=source
            )


def test_consumer_requires_exactly_one_key_source(public_path):
    for sources in ({}, {"jwks_url": "http://127.0.0.1:1/jwks", "public_key_path": public_path}):
        with pytest.raises(ValidationError):
            validate_token(
                "invalid", issuer="test-issuer", audience="engenharia-software-api", **sources
            )
