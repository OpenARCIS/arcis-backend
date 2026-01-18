from fastapi import APIRouter

from panda.core.workflow_manual.manual_flow import run_workflow
from panda.core.external_api.gmail import gmail_api
from panda.core.workflow_auto.auto_flow import run_autonomous_processing


router = APIRouter()


@router.get("/test")
async def test_flash():
    #await gmail_api.get_n_mails(5)
    await run_autonomous_processing()
    


    return {"response": 'hi'}