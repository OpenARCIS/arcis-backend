import signal
import asyncio
import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .router.routes import router
from .database.mongo.connection import mongo

api_server = FastAPI(title="PANDA - API")

api_server.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api_server.include_router(router)

shutdown_event = asyncio.Event()

def _signal_handler():
    shutdown_event.set()

async def some_cron_jobs():
    pass


async def run_fastapi():
    config = uvicorn.Config(app=api_server, host="0.0.0.0", port=8501, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    #await mongo.connect()

    await asyncio.gather(
        run_fastapi(),
        some_cron_jobs(),
        shutdown_event.wait()
    )

    #await mongo.disconnect()

if __name__ == '__main__':
    asyncio.run(main())