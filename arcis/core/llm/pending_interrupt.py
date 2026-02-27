from datetime import datetime
from bson import ObjectId
from arcis.core.llm.short_memory import db_client

db = db_client['arcis_short_memory']
pending_col = db['pending_interrupts']


def save_pending(thread_id: str, question: str, source_context: dict = None):
    """Save a pending interrupt for user review."""
    doc = {
        "thread_id": thread_id,
        "question": question,
        "status": "pending",
        "source_context": source_context or {},
        "created_at": datetime.now().timestamp()
    }
    result = pending_col.insert_one(doc)
    return str(result.inserted_id)


def get_all_pending() -> list:
    """Get all pending interrupts for the frontend."""
    items = list(pending_col.find(
        {"status": "pending"}
    ).sort("created_at", -1))
    for item in items:
        item["_id"] = str(item["_id"])
    return items


def get_pending_by_id(interrupt_id: str) -> dict | None:
    """Get a single pending interrupt by ID."""
    doc = pending_col.find_one({"_id": ObjectId(interrupt_id)})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


def resolve_pending(interrupt_id: str):
    """Mark a pending interrupt as resolved."""
    pending_col.update_one(
        {"_id": ObjectId(interrupt_id)},
        {"$set": {"status": "resolved", "resolved_at": datetime.now().timestamp()}}
    )


def dismiss_pending(interrupt_id: str):
    """Mark a pending interrupt as dismissed (user chose to skip)."""
    pending_col.update_one(
        {"_id": ObjectId(interrupt_id)},
        {"$set": {"status": "dismissed", "dismissed_at": datetime.now().timestamp()}}
    )
