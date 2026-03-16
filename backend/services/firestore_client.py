import os
from datetime import datetime, timezone
from google.cloud import firestore

from models import CompetitorCard, MarketPatterns


def _get_db() -> firestore.AsyncClient:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    database = os.environ.get("FIRESTORE_DATABASE", "(default)")
    return firestore.AsyncClient(project=project, database=database)


async def load_session(session_id: str) -> dict | None:
    """Load persisted session state from Firestore. Returns None if not found."""
    db = _get_db()
    doc_ref = db.collection("sessions").document(session_id)
    doc = await doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None


async def save_competitor(session_id: str, competitor: CompetitorCard) -> None:
    """Upsert a single competitor into the session's competitor list."""
    db = _get_db()
    doc_ref = db.collection("sessions").document(session_id)

    competitor_data = competitor.model_dump()

    await doc_ref.set(
        {
            f"competitors.{competitor.id}": competitor_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        merge=True,
    )


async def save_synthesis(
    session_id: str,
    patterns: MarketPatterns,
    gaps: list[str],
) -> None:
    """Persist market patterns and positioning gaps for a session."""
    db = _get_db()
    doc_ref = db.collection("sessions").document(session_id)

    await doc_ref.set(
        {
            "patterns": patterns.model_dump(),
            "gaps": gaps,
            "research_complete": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        merge=True,
    )


async def init_session(session_id: str) -> None:
    """Create a new session document with a created_at timestamp."""
    db = _get_db()
    doc_ref = db.collection("sessions").document(session_id)
    doc = await doc_ref.get()
    if not doc.exists:
        await doc_ref.set(
            {
                "session_id": session_id,
                "competitors": {},
                "patterns": None,
                "gaps": [],
                "research_complete": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
