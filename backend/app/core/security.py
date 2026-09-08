"""FR-5 / M8：密碼雜湊 + JWT（HS256），全用標準函式庫（免新增依賴）。

- 密碼：PBKDF2-HMAC-SHA256 + 每用戶 salt。
- JWT：header.payload.signature（base64url），secret 由 ``JWT_SECRET`` 提供。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

_PBKDF2_ITERATIONS = 100_000


class JWTError(Exception):
    """token 無效 / 過期 / 格式錯誤。"""


# ---------- 密碼 ----------
def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
    ).hex()


def verify_password(password: str, salt: str, hashed: str) -> bool:
    return hmac.compare_digest(hash_password(password, salt), hashed)


# ---------- JWT（HS256）----------
def _secret() -> str:
    return os.getenv("JWT_SECRET", "testweaver-dev-secret-change-me")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def _now() -> int:
    return int(time.time())


def create_token(payload: dict, expires_minutes: int = 60) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    body = {**payload, "iat": _now(), "exp": _now() + expires_minutes * 60}
    segments = (
        f"{_b64url_encode(json.dumps(header, separators=(',', ':')).encode())}."
        f"{_b64url_encode(json.dumps(body, separators=(',', ':')).encode())}"
    )
    sig = hmac.new(_secret().encode(), segments.encode("ascii"), hashlib.sha256).digest()
    return f"{segments}.{_b64url_encode(sig)}"


def decode_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise JWTError("malformed token")
    segments, sig = ".".join(parts[:2]), parts[2]
    expected = hmac.new(_secret().encode(), segments.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64url_decode(sig)
    except Exception as exc:  # noqa: BLE001
        raise JWTError("bad signature encoding") from exc
    if not hmac.compare_digest(provided, expected):
        raise JWTError("bad signature")
    try:
        payload = json.loads(_b64url_decode(parts[1]))
    except Exception as exc:  # noqa: BLE001
        raise JWTError("bad payload") from exc
    if not isinstance(payload, dict):
        raise JWTError("bad payload")
    exp = payload.get("exp")
    if exp is not None and _now() > int(exp):
        raise JWTError("token expired")
    return payload
