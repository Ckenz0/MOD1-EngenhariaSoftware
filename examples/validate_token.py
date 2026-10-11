"""Consumidor independente: requer somente PyJWT[crypto] e a chave publica confiavel."""

import argparse
import getpass
import json
import sys
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import jwt


class ValidationError(Exception):
    pass


@lru_cache(maxsize=8)
def get_jwks_client(jwks_url: str) -> jwt.PyJWKClient:
    parsed = urlsplit(jwks_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValidationError("Configure a trusted HTTP(S) JWKS URL")
    if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise ValidationError("Use HTTPS for remote JWKS")
    return jwt.PyJWKClient(jwks_url, timeout=5, cache_jwk_set=True, lifespan=300)


def validate_token(
    token: str,
    *,
    issuer: str,
    audience: str,
    jwks_url: str | None = None,
    public_key_path: Path | None = None,
) -> dict[str, Any]:
    if bool(jwks_url) == bool(public_key_path):
        raise ValidationError("Configure exactly one trusted public key source")
    try:
        header = jwt.get_unverified_header(token)
        if (
            header.get("alg") != "RS256"
            or header.get("typ") != "JWT"
            or not isinstance(header.get("kid"), str)
            or not header["kid"]
        ):
            raise ValueError("Invalid token header")
        if jwks_url is not None:
            key = get_jwks_client(jwks_url).get_signing_key_from_jwt(token).key
        else:
            assert public_key_path is not None
            key = public_key_path.read_bytes()
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            leeway=5,
            options={"require": ["sub", "iss", "aud", "iat", "exp", "jti"], "strict_aud": True},
        )
        if (
            type(claims["iat"]) is not int
            or type(claims["exp"]) is not int
            or claims["exp"] <= claims["iat"]
        ):
            raise ValueError("Invalid timestamps")
        UUID(claims["sub"])
        UUID(claims["jti"])
        return claims
    except (jwt.PyJWTError, OSError, ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Token rejected or public key unavailable") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validar JWT sem importar o emissor")
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--audience", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--jwks-url")
    source.add_argument("--public-key-path", type=Path)
    args = parser.parse_args(argv)
    try:
        claims = validate_token(
            getpass.getpass("Token (entrada oculta): "),
            issuer=args.issuer,
            audience=args.audience,
            jwks_url=args.jwks_url,
            public_key_path=args.public_key_path,
        )
        print(json.dumps({name: claims[name] for name in ("sub", "iss", "aud", "exp")}))
        return 0
    except (ValidationError, EOFError, KeyboardInterrupt):
        print("Token recusado ou chave publica indisponivel.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
