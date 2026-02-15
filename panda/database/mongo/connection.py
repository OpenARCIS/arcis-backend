from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from panda import Config

# easy references
COLLECTIONS = {
    'users': 'users',
    'processed_emails': 'processed_emails',
    'settings': 'settings',
    'token_usage': 'token_usage',
    'user_emotions': 'user_emotions'
}

class Database:
    client: AsyncIOMotorClient
    db: AsyncIOMotorDatabase

    def __init__(self):
        self.mongodb_url = Config.DATABASE_URL
        self.database_name = Config.DATABASE_NAME
        self.client = None
        self.db = None
        
    async def connect(self):
        self.client = AsyncIOMotorClient(self.mongodb_url)
        self.db = self.client[self.database_name]
        await self._create_indexes()
        
    async def disconnect(self):
        if self.client:
            self.client.close()

    async def _create_indexes(self):
        await self.db[COLLECTIONS['users']].create_index([("user_id", 1)])
        await self.db[COLLECTIONS['processed_emails']].create_index(
            [("email_id", 1)], 
            unique=True
        )


mongo = Database()