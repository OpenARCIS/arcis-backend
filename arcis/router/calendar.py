from fastapi import APIRouter, HTTPException, Query
from datetime import datetime

from arcis.core.external_api.calendar import calendar_wrapper

calendar_router = APIRouter()

async def _get_calendar_items_by_type(start_time: str, end_time: str, item_type: str):
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        
        items = await calendar_wrapper.get_items_in_range(start_dt, end_dt)
        filtered_items = [item for item in items if item.get('item_type') == item_type]
        return filtered_items
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO 8601.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@calendar_router.get("/calendar/events")
async def get_events(
    start_time: str = Query(..., description="ISO 8601 start time"),
    end_time: str = Query(..., description="ISO 8601 end time")
):
    """Fetch calendar items of type 'event'."""
    return await _get_calendar_items_by_type(start_time, end_time, "event")

@calendar_router.get("/calendar/todos")
async def get_todos(
    start_time: str = Query(..., description="ISO 8601 start time"),
    end_time: str = Query(..., description="ISO 8601 end time")
):
    """Fetch calendar items of type 'todo'."""
    return await _get_calendar_items_by_type(start_time, end_time, "todo")

@calendar_router.get("/calendar/reminders")
async def get_reminders(
    start_time: str = Query(..., description="ISO 8601 start time"),
    end_time: str = Query(..., description="ISO 8601 end time")
):
    """Fetch calendar items of type 'reminder'."""
    return await _get_calendar_items_by_type(start_time, end_time, "reminder")
