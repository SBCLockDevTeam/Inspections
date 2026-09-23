from __future__ import annotations

import hashlib
import hmac
import secrets

SESSION_COOKIE = "inspection_session"
DEFAULT_PASSWORD_FALLBACK = "password"
DEFAULT_PASSWORD_SETTING_KEY = "auth.default_password"
PASSWORD_ITERATIONS = 240_000


def hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return digest.hex()


def password_record(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{salt}${hash_password(password, salt)}"


def verify_password(password: str, record: str) -> bool:
    if "$" not in record:
        return False
    salt, expected_hash = record.split("$", 1)
    actual_hash = hash_password(password, salt)
    return hmac.compare_digest(actual_hash, expected_hash)
