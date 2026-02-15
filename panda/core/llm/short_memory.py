from panda import Config

from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient, DESCENDING

# seperate client for mongodb cuz async motor is deprecated in langgraph
# dual client is safe for now
db_client = MongoClient(Config.DATABASE_URL)

checkpointer = MongoDBSaver(
    db_client,
    'panda_short_memory'
)


def get_all_threads():
    """
    Returns a lightweight list of all conversations for the sidebar.
    Each item contains: thread_id, updated_at, and last_message (preview).
    """
    db = db_client['panda_short_memory']
    collection = db['checkpoints']

    pipeline = [
        {"$sort": {"thread_id": 1, "checkpoint_id": -1}},

        # group by thread_id to get unique conversations
        {"$group": {
            "_id": "$thread_id",
            "latest_checkpoint": {"$first": "$checkpoint"},
            "updated_at": {"$first": "$metadata.step"}
        }},

        {"$project": {
            "thread_id": "$_id",
            "_id": 0,
            "updated_at": 1,
            # Extract the very last message from the array for the preview text
            "last_message": { 
                "$let": {
                    "vars": {
                        "last_msg": { "$arrayElemAt": ["$latest_checkpoint.channel_values.messages", -1] }
                    },
                    "in": {
                        "type": "$$last_msg.type",
                        "response": "$$last_msg.content",
                        "plan": [],
                        "thread_id": "$_id"
                    }
                }
            }
        }}
    ]

    try:
        # Returns: [{'thread_id': '123', 'last_message': {...}}, ...]
        return list(collection.aggregate(pipeline))
    except Exception as e:
        print(f"Error fetching sidebar: {e}")
        return []


def get_thread_history(thread_id: str):
    """
    Returns the FULL list of messages for a specific thread_id.
    """
    db = db_client['panda_short_memory']
    collection = db['checkpoints']
    
    latest_checkpoint = collection.find_one(
        {"thread_id": thread_id},
        sort=[("checkpoint_id", DESCENDING)]
    )
    
    if latest_checkpoint:
        try:
            raw_messages = latest_checkpoint['checkpoint']['channel_values']['messages']
            formatted_messages = []
            for msg in raw_messages:
                formatted_messages.append({
                    "type": msg['type'],
                    "response": msg['content'],
                    "plan": msg.get('additional_kwargs', {}).get('plan', []),
                    "thread_id": thread_id
                })
            return formatted_messages
        except KeyError:
            return []
            
    return []