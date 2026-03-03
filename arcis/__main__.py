import asyncio
import uvicorn
import warnings

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from arcis import Config
from arcis.logger import LOGGER

from arcis.router.gmail import gmail_router
from arcis.router.settings import settings_router
from arcis.router.calendar import calendar_router
from arcis.router.chat import chat_router
from arcis.router.auto_flow import auto_flow_router
from arcis.router.user_status import user_status_router
from arcis.router.token_tracker import token_tracker_router
from arcis.router.onboarding import onboarding_router

from arcis.database.mongo.connection import mongo

from arcis.core.llm.config_manager import config_manager
from arcis.core.llm.long_memory import long_memory

from arcis.core.external_api.gmail import gmail_api
from arcis.core.tts.tts_manager import tts_manager

from arcis.core.workflow_auto.auto_flow import run_autonomous_processing
from arcis.core.mcp.manager import mcp_manager

warnings.filterwarnings("ignore", message="Pydantic serializer warnings") # because of the usage of raw_response in pydantic models


async def check_emails_cron():
    try:
        while True:
            await asyncio.sleep(Config.AUTO_CHECK_INTERVAL)
            await run_autonomous_processing()
        return True
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mongo.connect()
    await config_manager.load_config()
    await gmail_api.load_creds()

    try:
        long_memory.init(mode=Config.EMBEDDING_MODE)
    except Exception as e:
        LOGGER.error(f"Long-term memory init failed (non-fatal): {e}")
        

    try:
        await mcp_manager.init(
            config_path=Config.MCP_SERVERS_CONFIG_PATH,
            tool_threshold=Config.MCP_TOOL_THRESHOLD,
        )
    except Exception as e:
        LOGGER.error(f"MCP init failed (non-fatal): {e}")

    try:
        loop = asyncio.get_event_loop() # Avoid blocking event loop for slow model loads
        await loop.run_in_executor(None, tts_manager.initialize, Config.TTS_DEFAULT_VOICE) 
    except Exception as e:
        LOGGER.error(f"TTS Manager initialization failed: {e}")
    
    from arcis.tgclient import get_tg_client
    tg_arcis = get_tg_client()
    if tg_arcis:
        try:
            await tg_arcis.start()
        except Exception as e:
            LOGGER.error(f"Failed to start Telegram Bot: {e}")

    cron_task = asyncio.create_task(check_emails_cron())
    
    yield
    
    cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass
        
    if tg_arcis:
        try:
            await tg_arcis.stop()
        except Exception as e:
            LOGGER.error(f"Failed to stop Telegram Bot: {e}")

    await mcp_manager.shutdown()
    await mongo.disconnect()


api_server = FastAPI(title="ARCIS - API", lifespan=lifespan)

api_server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_server.include_router(gmail_router)
api_server.include_router(settings_router)
api_server.include_router(calendar_router)
api_server.include_router(chat_router)
api_server.include_router(auto_flow_router)
api_server.include_router(user_status_router)
api_server.include_router(token_tracker_router)
api_server.include_router(onboarding_router)


if __name__ == '__main__':
    uvicorn.run(api_server, host="0.0.0.0", port=8501, log_level="info")