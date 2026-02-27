from datetime import datetime
from arcis.core.llm.short_memory import db_client

db = db_client['arcis_short_memory']
messages_col = db['chat_messages']


def save_message(thread_id: str, role: str, content: str, plan: list = None):
    """Save a single chat message to the collection."""
    messages_col.insert_one({
        "thread_id": thread_id,
        "role": role,
        "content": content,
        "plan": plan or [],
        "timestamp": datetime.now().timestamp()
    })


def get_thread_history(thread_id: str) -> list:
    """Return all messages for a thread, sorted chronologically."""
    return list(messages_col.find(
        {"thread_id": thread_id},
        {"_id": 0}
    ).sort("timestamp", 1))


def get_all_threads() -> list:
    """Get the latest message per thread for sidebar display."""
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$thread_id",
            "last_message": {"$first": "$content"},
            "last_role": {"$first": "$role"},
            "updated_at": {"$first": "$timestamp"}
        }},
        {"$sort": {"updated_at": -1}},
        {"$project": {
            "thread_id": "$_id",
            "_id": 0,
            "last_message": 1,
            "last_role": 1,
            "updated_at": 1
        }}
    ]
    return list(messages_col.aggregate(pipeline))
