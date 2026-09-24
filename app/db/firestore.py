
from typing import Optional
from google.cloud import firestore
from app.core.config import settings

_firestore_client: Optional[firestore.Client] = None


def get_firestore_client() -> firestore.Client:
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=settings.FIRESTORE_PROJECT_ID)
    return _firestore_client


# Best-effort only. Postgres is the source of truth for donations, not
# Firestore -- if this write fails, we log it and move on, we never let
# it break a real donation.
def write_donation_feed_entry(campaign_id: str, entry: dict) -> None:
    try:
        client = get_firestore_client()
        client.collection("donation_feed").document(str(campaign_id)) \
              .collection("entries").add(entry)
    except Exception as exc:
        print(f"[firestore] donation_feed write failed (non-fatal): {exc}")


# Same deal as above, just for the admin dashboard's activity feed.
def write_activity_feed_entry(entry: dict) -> None:
    try:
        client = get_firestore_client()
        client.collection("activity_feed").add(entry)
    except Exception as exc:
        print(f"[firestore] activity_feed write failed (non-fatal): {exc}")