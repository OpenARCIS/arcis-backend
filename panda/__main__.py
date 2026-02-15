import asyncio
import uvicorn

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from .router.routes import router
from panda.router.gmail import gmail_router
from panda.router.settings import settings_router
from panda.router.calendar import calendar_router
from panda.router.chat import chat_router
from panda.router.auto_flow import auto_flow_router
from panda.router.user_status import user_status_router
from panda.router.token_tracker import token_tracker_router
from .database.mongo.connection import mongo
from panda.core.llm.config_manager import config_manager
from panda.core.external_api.gmail import gmail_api
from panda.core.workflow_auto.auto_flow import run_autonomous_processing

async def some_cron_jobs():
    try:
        return True
    except asyncio.CancelledError:
        pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    await config_manager.load_config()
    await gmail_api.load_creds()
    
    cron_task = asyncio.create_task(some_cron_jobs())

    #asyncio.create_task(run_autonomous_processing())
    
    yield
    
    cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass
        
    await mongo.disconnect()


api_server = FastAPI(title="PANDA - API", lifespan=lifespan)

api_server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_server.include_router(router)
api_server.include_router(gmail_router)
api_server.include_router(settings_router)
api_server.include_router(calendar_router)
api_server.include_router(chat_router)
api_server.include_router(auto_flow_router)
api_server.include_router(user_status_router)
api_server.include_router(token_tracker_router)


if __name__ == '__main__':
    uvicorn.run(api_server, host="0.0.0.0", port=8501, log_level="info")