# onto_platform/auth.py
import secrets
import uuid
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, AsyncGenerator, Callable
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, HTTPException, Request

_TOKEN_PREFIX = "op_"
_PH = PasswordHasher()


class Scope(IntEnum):
    read = 1
    editor = 2
    admin = 3


def generate_token() -> str:
    return _TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(plaintext: str) -> str:
    return _PH.hash(plaintext)


def verify_token(plaintext: str, hashed: str) -> bool:
    try:
        return _PH.verify(hashed, plaintext)
    except (VerifyMismatchError, InvalidHashError):
        return False


def token_prefix(plaintext: str) -> str:
    return plaintext[:8]


@dataclass
class RequestPrincipal:
    token_id: uuid.UUID
    label: str
    scope: Scope


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth[len("Bearer "):].strip() or None


def require_scope(
    min_scope: Scope,
    session_provider: Callable[[], AsyncGenerator[Any, None]],
) -> Callable[..., Any]:
    """Returns a FastAPI dependency that resolves and authorizes a bearer token."""
    from onto_platform.token_store import lookup_token

    async def dep(
        request: Request,
        session: Any = Depends(session_provider),
    ) -> RequestPrincipal:
        token = _extract_bearer(request)
        if not token:
            raise HTTPException(
                status_code=401,
                detail={"code": "UNAUTHORIZED", "message": "Missing or malformed Authorization header"},
            )
        result = await lookup_token(session, token)
        if result is None:
            raise HTTPException(
                status_code=401,
                detail={"code": "UNAUTHORIZED", "message": "Invalid or revoked token"},
            )
        if result.scope < min_scope:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORBIDDEN", "message": f"Requires scope >= {min_scope.name}"},
            )
        return RequestPrincipal(token_id=result.token_id, label=result.label, scope=result.scope)

    return dep
