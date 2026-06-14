import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from pribilka.models.user_access_token import UserAccessToken

_TOKEN_BYTES = 32


def hash_access_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_access_token(db: Session, user_id: str) -> str:
    raw = secrets.token_urlsafe(_TOKEN_BYTES)
    db.add(
        UserAccessToken(
            token_hash=hash_access_token(raw),
            user_id=user_id,
        )
    )
    db.flush()
    return raw


def resolve_user_id(db: Session, raw_token: str) -> str | None:
    token_hash = hash_access_token(raw_token.strip())
    return db.scalar(
        select(UserAccessToken.user_id).where(UserAccessToken.token_hash == token_hash)
    )


def user_has_credentials(db: Session, user_id: str) -> bool:
    return (
        db.scalar(
            select(UserAccessToken.user_id)
            .where(UserAccessToken.user_id == user_id)
            .limit(1)
        )
        is not None
    )
