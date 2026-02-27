from arcis import Config

from langgraph.checkpoint.mongodb import MongoDBSaver
from pymongo import MongoClient

# seperate client for mongodb cuz async motor is deprecated in langgraph
# dual client is safe for now
db_client = MongoClient(Config.DATABASE_URL)

checkpointer = MongoDBSaver(
    db_client,
    'arcis_short_memory'
)