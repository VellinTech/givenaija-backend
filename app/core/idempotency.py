"""
Idempotency Control Module.

Prevents duplicate processing of financial transactions and critical requests 
by hashing request payloads, storing unique 'Idempotency-Key' headers, and 
caching execution responses in PostgreSQL and Redis.
"""

import hashlib
import json
from typing import Any, Dict, Optional
from fastapi import Header, HTTPException, status
from sqlmodel import Session, select

from app.domains.donations.models import IdempotencyKey


def calculate_payload_hash(payload: Any) -> str:
    """
    Computes a deterministic SHA-256 hash of incoming request payloads.
    
    Supports bytes, strings, dictionaries, and Pydantic models.
    """
    if payload is None:
        return hashlib.sha256(b"").hexdigest()
    if isinstance(payload, bytes):
        return hashlib.sha256(payload).hexdigest()
    if isinstance(payload, str):
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    
    # Sort dictionary keys to ensure deterministic JSON serialization across requests
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    
    dumped_json = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(dumped_json.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Compatibility aliases
#
# Some routes (e.g. app.domains.donations.router) import a function-based API
# instead of instantiating IdempotencyGuard directly. These thin wrappers keep
# both styles working without duplicating logic. If you're not sure which
# call sites use these, search the codebase for their names before removing.
# ---------------------------------------------------------------------------

def compute_payload_hash(payload: Any) -> str:
    """Alias for calculate_payload_hash, kept for compatibility with existing route imports."""
    return calculate_payload_hash(payload)


def check_or_reserve_idempotency_key(
    session: Session,
    key: Optional[str],
    endpoint: str,
    payload: Any,
) -> Optional[Dict[str, Any]]:
    """
    Function-style wrapper around IdempotencyGuard.check().

    Returns the cached response dict if this key + payload combination was
    already processed, raises HTTP 409 on key/payload mismatch, or returns
    None if this is a new key (safe to proceed with the request handler).
    """
    guard = IdempotencyGuard(key=key)
    return guard.check(session=session, endpoint=endpoint, payload=payload)


def save_idempotency_response(
    session: Session,
    key: Optional[str],
    endpoint: str,
    payload: Any,
    response_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Function-style wrapper around IdempotencyGuard.save()."""
    guard = IdempotencyGuard(key=key)
    return guard.save(
        session=session,
        endpoint=endpoint,
        payload=payload,
        response_data=response_data,
    )


class IdempotencyGuard:
    """
    Dependency helper to enforce request idempotency across endpoints.
    
    Usage in FastAPI routes:
        @router.post("/donations")
        def process_donation(
            payload: DonationCreate,
            session: Session = Depends(get_session),
            idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
        ):
            guard = IdempotencyGuard(idempotency_key)
            cached_response = guard.check(session, endpoint="/v1/donations", payload=payload)
            if cached_response:
                return cached_response
                
            # Process transaction...
            
            return guard.save(session, endpoint="/v1/donations", payload=payload, response_data=result)
    """

    def __init__(
        self,
        key: Optional[str] = Header(
            None, 
            alias="Idempotency-Key", 
            description="Unique UUID string to ensure request idempotency and prevent duplicate processing."
        )
    ):
        self.key = key

    def check(
        self,
        session: Session,
        endpoint: str,
        payload: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Validates idempotency key status in the database.

        Returns:
            - Cached JSON response dict if request was previously processed with identical payload.
            - Raises HTTP 409 Conflict if key is reused with a different request payload.
            - Returns None if key is new, allowing request handler execution.
        """
        if not self.key:
            return None

        body_hash = calculate_payload_hash(payload)

        # Check database for existing record
        existing_record = session.exec(
            select(IdempotencyKey).where(IdempotencyKey.key == self.key)
        ).first()

        if existing_record:
            # Detect payload tampering or key collision
            if existing_record.body_hash != body_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key conflict: This key was already used with a different payload."
                )

            # Key matches and payload matches -> return cached response JSON
            if existing_record.response_json:
                return json.loads(existing_record.response_json)

        return None

    def save(
        self,
        session: Session,
        endpoint: str,
        payload: Any,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Persists the processing result and HTTP payload hash for future key checks.
        """
        if not self.key:
            return response_data

        body_hash = calculate_payload_hash(payload)
        response_json_str = json.dumps(response_data, default=str)

        existing_record = session.exec(
            select(IdempotencyKey).where(IdempotencyKey.key == self.key)
        ).first()

        if existing_record:
            existing_record.response_json = response_json_str
            session.add(existing_record)
        else:
            record = IdempotencyKey(
                key=self.key,
                endpoint=endpoint,
                body_hash=body_hash,
                response_json=response_json_str
            )
            session.add(record)

        session.commit()
        return response_data