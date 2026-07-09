"""认证：JWT + bcrypt + SHA256 遗留兼容"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt
from app.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    """双模校验：bcrypt + 遗留 SHA256（自动升级）"""
    # 遗留 SHA256: 64位纯 hex
    if len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash):
        sha = hashlib.sha256(password.encode()).hexdigest()
        return sha == stored_hash
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        return False


def is_legacy_hash(stored_hash: str) -> bool:
    return len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash)


def generate_session_token() -> str:
    return secrets.token_hex(32)


def create_jwt(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
