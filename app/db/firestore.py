
from typing import Optional
from google.cloud import firestore
from app.core.config import settings

_firestore_client: Optional[firestore.Client] = None


def get_firestore_client() -> firestore.Client:
  
    global _firestore_client
    if _firestore_client is None:
        _firestore_client = firestore.Client(project=settings.FIRESTORE_PROJECT_ID)
    return _firestore_client