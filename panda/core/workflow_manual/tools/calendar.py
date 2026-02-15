from typing import Optional, List
from datetime import datetime
from langchain.tools import tool
from panda.core.external_api.calendar import calendar_wrapper, CalendarItem

@tool
async def calendar_add_item(title: str, item_type: str, start_time: str, end_time: str = None, description: str = "") -> str:
    """
    Adds a new event, todo, or reminder to the calendar.

    Args:
        title: The title/summary of the item.
        item_type: One of 'event', 'todo', 'reminder'.
        start_time: ISO 8601 formatted datetime string (e.g., '2023-10-27T10:00:00').
        end_time: Optional ISO 8601 formatted datetime string.
        description: Optional description or notes.
    """
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time) if end_time else None
        
        item = CalendarItem(
            title=title,
            item_type=item_type,
            start_time=start_dt,
            end_time=end_dt,
            description=description
        )
        
        item_id = await calendar_wrapper.add_item(item)
        return f"✅ Calendar item added successfully. ID: {item_id}"
    except ValueError as e:
        return f"❌ Error parsing date: {e}. Please use ISO 8601 format (YYYY-MM-DDTHH:MM:SS)."
    except Exception as e:
        return f"❌ Error adding item: {e}"

@tool
async def calendar_get_items(start_time: str, end_time: str) -> str:
    """
    Retrieves calendar items between two dates.

    Args:
        start_time: ISO 8601 formatted start datetime string.
        end_time: ISO 8601 formatted end datetime string.
    """
    try:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        
        items = await calendar_wrapper.get_items_in_range(start_dt, end_dt)
        if not items:
            return "No items found in this range."
            
        result = [f"- [{item['item_type'].upper()}] {item['title']} ({item['start_time']})" for item in items]
        return "\n".join(result)
    except Exception as e:
        return f"❌ Error retrieving items: {e}"

@tool
async def calendar_delete_item(item_id: str) -> str:
    """
    Deletes a calendar item by its ID.

    Args:
        item_id: The unique ID of the item to delete.
    """
    success = await calendar_wrapper.delete_item(item_id)
    if success:
        return f"✅ Item {item_id} deleted."
    return f"❌ Failed to delete item {item_id}. It may not exist."

@tool
async def calendar_toggle_todo(item_id: str) -> str:
    """
    Toggles the completion status of a 'todo' item.

    Args:
        item_id: The unique ID of the todo item.
    """
    success = await calendar_wrapper.toggle_todo(item_id)
    if success:
        return f"✅ Todo {item_id} status toggled."
    return f"❌ Failed to toggle todo {item_id}. ensure it exists and is a todo."

calendar_tools = [calendar_add_item, calendar_get_items, calendar_delete_item, calendar_toggle_todo]
