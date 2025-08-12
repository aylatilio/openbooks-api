# Security helpers: password verification, JWT creation/validation, and auth dependency.

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt

from .settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# -------------------------- Password helpers --------------------------- #
def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify plaintext vs bcrypt hash (safe fallback to False)."""
    try:
        return bcrypt.verify(plain_password, password_hash)
    except Exception:
        return False

def authenticate_admin(username: str, password: str) -> bool:
    """Validate admin username + bcrypt hash from env."""
    if username != settings.ADMIN_USERNAME:
        return False
    if not settings.ADMIN_PASSWORD_HASH:
        return False
    return verify_password(password, settings.ADMIN_PASSWORD_HASH)

# ---------------------------- JWT helpers ------------------------------- #
def _create_token(subject: str, minutes: int, token_type: str) -> str:
    """Create signed JWT with iat/exp/type claims."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        "type": token_type,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_access_token(subject: str) -> str:
    """Short-lived token for API calls."""
    return _create_token(subject, settings.ACCESS_TOKEN_EXPIRE_MINUTES, "access")

def create_refresh_token(subject: str) -> str:
    """Long-lived token used to mint a new access token."""
    return _create_token(subject, settings.REFRESH_TOKEN_EXPIRE_MINUTES, "refresh")

def decode_token(token: str) -> dict:
    """Decode & validate JWT, raising 401 if invalid/expired."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

# ---------------------- Dependency for protected routes ----------------- #
def require_admin(token: str = Depends(oauth2_scheme)) -> str:
    """Validate Bearer token as an access token for the configured admin user."""
    claims = decode_token(token)
    if claims.get("type") != "access":
        raise HTTPException(status_code=401, detail="Not an access token")
    if claims.get("sub") != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Not authorized")
    return claims["sub"]
