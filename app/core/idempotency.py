"""
Idempotency Control Module.

Prevents duplicate processing of financial transactions and critical requests
by hashing request payloads, storing unique 'Idempotency-Key' headers, and
caching execution responses.
"""

import hashlib
import json
from typing import Any, Dict, Optional
from sqlmodel import Session, select

from app.domains.donations.models import IdempotencyKey


def compute_payload_hash(payload: Any) -> str:
    """
    Computes a deterministic SHA-256 hash of an incoming request payload.

    Supports bytes, strings, dicts, and Pydantic/SQLModel objects (via
    model_dump/dict).
    """
    if payload is None:
        return hashlib.sha256(b"").hexdigest()
    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()
    if isinstance(payload, str):
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()

    dumped_json = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(dumped_json.encode("utf-8")).hexdigest()


def check_or_reserve_idempotency_key(
    session: Session,
    key: Optional[str],
    endpoint: str,
    payload: Any,
) -> Optional[Dict[str, Any]]:
    """
    Looks up an Idempotency-Key.

    Returns:
        - The ORIGINAL cached response dict if this exact key + payload was
          already processed (caller should return this immediately, as-is).
        - None if this key has never been seen (caller should proceed to
          run the business logic, then call save_idempotency_response()).
    Raises:
        HTTP 409 if the same key is reused with a DIFFERENT payload — that's
        a client bug, not a legitimate retry.
    """
    if not key:
        return None

    body_hash = compute_payload_hash(payload)

    existing = session.exec(
        select(IdempotencyKey).where(IdempotencyKey.key == key)
    ).first()

    if existing:
        if existing.body_hash != body_hash:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key reused with a different request payload."
            )
        if existing.response_json:
            return json.loads(existing.response_json)

    return None


def save_idempotency_response(
    session: Session,
    key: Optional[str],
    endpoint: str,
    payload: Any,
    response_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Persists the successful response body against this Idempotency-Key so a
    future retry with the same key returns the exact same response.

    NOTE: this function does NOT commit. It only session.add()s the record.
    The caller's service function commits once, as part of its single
    business-action transaction (see donations/service.py).
    """
    if not key:
        return response_data

    body_hash = compute_payload_hash(payload)
    response_json_str = json.dumps(response_data, default=str)

    existing = session.exec(
        select(IdempotencyKey).where(IdempotencyKey.key == key)
    ).first()

    if existing:
        existing.response_json = response_json_str
        session.add(existing)
    else:
        record = IdempotencyKey(
            key=key,
            endpoint=endpoint,
            body_hash=body_hash,
            response_json=response_json_str
        )
        session.add(record)

    return response_data