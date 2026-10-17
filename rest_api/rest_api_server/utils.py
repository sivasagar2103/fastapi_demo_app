
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from pwdlib.hashers.argon2 import Argon2Hasher

# Retain verification for passwords saved before the bcrypt migration.
legacy_argon2 = Argon2Hasher()

def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"),
                              stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False

DUMMY_HASH = hash_password("dummy-password-never-used")

def issue_token(user, settings):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user["id"], "tenant_id": user.get("tenant_id"), "iat": now,
        "exp": now + timedelta(minutes=settings.token_minutes),
        "iss": "fastapi-demo", "aud": "management-api"}, settings.jwt_secret, algorithm="HS256")
