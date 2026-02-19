import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, status


class JwtError(Exception):
    pass


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_jwt(payload: dict[str, Any], secret: str, expires_in_s: int = 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    claims = {**payload, "exp": int(time.time()) + expires_in_s}

    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64url_encode(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    encoded_signature = _b64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def decode_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise JwtError("Malformed JWT") from exc

    signing_input = f"{encoded_header}.{encoded_payload}".encode()
    expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_b64url_encode(expected_sig), encoded_signature):
        raise JwtError("Invalid JWT signature")

    payload = json.loads(_b64url_decode(encoded_payload))
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise JwtError("Expired JWT")

    return payload


def jwt_http_exception(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
