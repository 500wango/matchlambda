from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from app.core.config import settings

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)
TOKEN_ISSUER = "matchlambda"

# Only HMAC algorithms may be configured. Anything else (notably "none", but
# also asymmetric algorithms whose verification key we do not hold) would let an
# attacker forge tokens, so an unsafe setting is a hard startup failure rather
# than a silent downgrade.
SAFE_JWT_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})
JWT_ALGORITHM = str(settings.JWT_ALGORITHM or "").strip().upper()
if JWT_ALGORITHM not in SAFE_JWT_ALGORITHMS:
    raise RuntimeError(
        f"Unsupported JWT_ALGORITHM '{settings.JWT_ALGORITHM}'. "
        f"Allowed algorithms: {sorted(SAFE_JWT_ALGORITHMS)}."
    )


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    try:
        return ph.check_needs_rehash(hashed_password)
    except InvalidHashError:
        return False


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> tuple[str, int]:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
        expires_in = int(expires_delta.total_seconds())
    else:
        expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": TOKEN_ISSUER,
    }
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt, expires_in


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            issuer=TOKEN_ISSUER,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
        return payload
    except jwt.PyJWTError:
        return None
