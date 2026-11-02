"""Đăng ký / đăng nhập: mật khẩu băm PBKDF2-SHA256, phiên đăng nhập bằng JWT (HS256, hết hạn sau 7 ngày)."""
import base64
import hashlib
import hmac
import os
import secrets
import time

import jwt  # PyJWT
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db

TOKEN_TTL = 7 * 24 * 3600
PBKDF2_ITER = 600_000
MAX_FAILS, FAIL_WINDOW = 8, 15 * 60  # tối đa 8 lần sai / 15 phút cho mỗi email

_bearer = HTTPBearer(auto_error=False)
_secret_cache: str | None = None
_fails: dict[str, list[float]] = {}


# ------------------------------------------------------------------ mật khẩu
def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITER)
    return f"pbkdf2_sha256${PBKDF2_ITER}${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, dk = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iters))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:  # noqa: BLE001
        return False


DUMMY_HASH = hash_password(secrets.token_hex(8))  # để thời gian phản hồi giống nhau khi email không tồn tại


# ------------------------------------------------------------------ khóa ký token
def get_secret() -> str:
    """JWT_SECRET trong môi trường nếu có; nếu không thì tạo một khóa ngẫu nhiên và lưu trong database."""
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    env = os.environ.get("JWT_SECRET", "").strip()
    if env:
        _secret_cache = env
        return env
    with db.session() as conn:
        conn.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING",
                     ("jwt_secret", secrets.token_hex(32)))
        _secret_cache = conn.execute("SELECT value FROM app_settings WHERE key = ?", ("jwt_secret",)).fetchone()["value"]
    return _secret_cache


def make_token(user_id: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL}, get_secret(), algorithm="HS256")


# ------------------------------------------------------------------ chống dò mật khẩu
def throttle_check(key: str):
    now = time.time()
    recent = [t for t in _fails.get(key, []) if now - t < FAIL_WINDOW]
    _fails[key] = recent
    if len(recent) >= MAX_FAILS:
        raise HTTPException(429, "Đăng nhập sai quá nhiều lần. Hãy đợi khoảng 15 phút rồi thử lại.")


def throttle_fail(key: str):
    _fails.setdefault(key, []).append(time.time())


def throttle_clear(key: str):
    _fails.pop(key, None)


# ------------------------------------------------------------------ dependency cho các API cần đăng nhập
def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    unauth = {"WWW-Authenticate": "Bearer"}
    if not cred:
        raise HTTPException(401, "Bạn chưa đăng nhập.", headers=unauth)
    try:
        payload = jwt.decode(cred.credentials, get_secret(), algorithms=["HS256"])
        uid = int(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn. Hãy đăng nhập lại.", headers=unauth)
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ. Hãy đăng nhập lại.", headers=unauth)
    with db.session() as conn:
        row = conn.execute("SELECT id, email, name FROM users WHERE id = ?", (uid,)).fetchone()
    if not row:
        raise HTTPException(401, "Tài khoản không tồn tại. Hãy đăng nhập lại.", headers=unauth)
    return {"id": row["id"], "email": row["email"], "name": row["name"]}
