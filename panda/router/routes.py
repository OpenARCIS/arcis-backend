from fastapi import APIRouter

from ..core.llm.factory import LLMProvider, LLMFactory
from panda import Config

from panda.agents.graph import build_and_run_graph

router = APIRouter()

# TODO change response model
@router.get("/testmodelflash")
async def test_flash():
    await build_and_run_graph()

    return {"response": 'hi'}