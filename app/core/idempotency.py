import hashlib
import json
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlmodel import Session, select

from app.domains.donations.models import IdempotencyKey


def compute_payload_hash(payload: Any) -> str:
    """
    Computes a deterministic SHA-256 hash of an incoming request payload.

    Supports bytes, strings, dicts, and Pydantic/SQLModel objects.
    """
    if payload is None:
        return hashlib.sha256(b"").hexdigest()

    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()

    if isinstance(payload, str):
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    dumped_json = json.dumps(
        payload,
        sort_keys=True,
        default=str,
    )

    return hashlib.sha256(
        dumped_json.encode("utf-8")
    ).hexdigest()


def check_or_reserve_idempotency_key(
    session: Session,
    key: Optional[str],
    endpoint: str,
    payload: Any,
) -> Optional[Dict[str, Any]]:
    """
    Atomically checks and reserves an Idempotency-Key.

    Returns:
        - Cached response if the key was already completed.
        - None if this request successfully reserved a new key.

    Raises:
        HTTP 409 if the same key is reused with a different payload.
    """
    if not key:
        return None

    body_hash = compute_payload_hash(payload)

    # Atomically reserve the key.
    #
    # Because IdempotencyKey.key is the PostgreSQL primary key,
    # only one concurrent request can successfully insert it.
    result = session.execute(
        text(
            """
            INSERT INTO idempotency_keys
                (key, endpoint, body_hash, response_json, created_at)
            VALUES
                (:key, :endpoint, :body_hash, NULL, NOW())
            ON CONFLICT (key) DO NOTHING
            """
        ),
        {
            "key": key,
            "endpoint": endpoint,
            "body_hash": body_hash,
        },
    )

    if result.rowcount == 1:
        # This request successfully reserved the key.
        return None

    # Another request already owns this key.
    existing = session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key
        )
    ).first()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key is currently being processed. Please retry.",
        )

    if existing.body_hash != body_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Idempotency key reused with a different request payload.",
        )

    if existing.response_json:
        return json.loads(existing.response_json)

    # The key exists but the original request has not finished yet.
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Idempotency key is currently being processed. Please retry.",
    )


def save_idempotency_response(
    session: Session,
    key: Optional[str],
    endpoint: str,
    payload: Any,
    response_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Stores the successful response against the reserved Idempotency-Key.

    The caller is responsible for committing the transaction.
    """
    if not key:
        return response_data

    body_hash = compute_payload_hash(payload)
    response_json_str = json.dumps(
        response_data,
        default=str,
    )

    existing = session.exec(
        select(IdempotencyKey).where(
            IdempotencyKey.key == key
        )
    ).first()

    if existing:
        # Only fill in the response for the request that reserved
        # this key. The body hash is kept unchanged.
        existing.response_json = response_json_str
        existing.endpoint = endpoint
        existing.body_hash = body_hash
        session.add(existing)

    else:
        # Normally unreachable because check_or_reserve_idempotency_key()
        # reserves the key before the business operation starts.
        record = IdempotencyKey(
            key=key,
            endpoint=endpoint,
            body_hash=body_hash,
            response_json=response_json_str,
        )
        session.add(record)

    return response_data
