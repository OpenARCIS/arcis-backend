from fastapi import APIRouter

from panda.core.workflow_manual.manual_flow import run_workflow
from panda.core.external_api.gmail import gmail_api

router = APIRouter()


@router.get("/test")
async def test_flash():
    await run_workflow("Find me a mail from shany telling about assignment")
    #await gmail_api.get_n_mails(5)


    return {"response": 'hi'}