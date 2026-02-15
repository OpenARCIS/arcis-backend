import calendar
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from bson import ObjectId
from panda.database.mongo.connection import mongo
from pydantic import BaseModel, Field

# --- Data Models (Pydantic) ---
class CalendarItem(BaseModel):
    title: str
    item_type: str = Field(..., pattern="^(event|todo|reminder)$") # strict type
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = ""
    is_completed: bool = False # Mainly for Todos
    metadata: Dict[str, Any] = {} # Extra data (e.g., color, tags)

# --- Main Wrapper Class ---
class CalendarWrapper:
    def __init__(self, collection_name: str = "calendar_events"):
        """
        Initialize with a Motor Database instance.
        """
        self.collection_name = collection_name
        self.cal = calendar.Calendar(firstweekday=6) # 6 = Sunday, 0 = Monday

    @property
    def collection(self):
        return mongo.db[self.collection_name]

    # ---------------------------
    # Core CRUD Operations
    # ---------------------------

    async def add_item(self, item: CalendarItem) -> str:
        """Adds an event, todo, or reminder to the database."""
        # Convert Pydantic model to dict
        data = item.model_dump()
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

    async def get_item(self, item_id: str) -> Optional[dict]:
        """Retrieves a single item by ID."""
        try:
            oid = ObjectId(item_id)
        except:
            return None
        return await self.collection.find_one({"_id": oid})

    async def update_item(self, item_id: str, update_data: dict) -> bool:
        """Updates fields of a specific item."""
        try:
            oid = ObjectId(item_id)
        except:
            return False
            
        result = await self.collection.update_one(
            {"_id": oid}, 
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete_item(self, item_id: str) -> bool:
        """Deletes an item permanently."""
        try:
            oid = ObjectId(item_id)
        except:
            return False
        result = await self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0

    async def toggle_todo(self, item_id: str) -> bool:
        """Toggles the completion status of a Todo."""
        item = await self.get_item(item_id)
        if item and item.get("item_type") == "todo":
            new_status = not item.get("is_completed", False)
            return await self.update_item(item_id, {"is_completed": new_status})
        return False

    # ---------------------------
    # Calendar View Logic
    # ---------------------------

    async def get_items_in_range(self, start: datetime, end: datetime) -> List[dict]:
        """
        Fetches all items that fall within a specific time range.
        Handles events that might span across days.
        """
        cursor = self.collection.find({
            "start_time": {"$gte": start, "$lt": end}
        }).sort("start_time", 1)
        
        items = await cursor.to_list(length=None)
        
        # Convert ObjectIds to strings for JSON serializability if needed
        for item in items:
            item["_id"] = str(item["_id"])
        return items

    async def get_month_view(self, year: int, month: int) -> List[List[Dict]]:
        """
        Returns a structured representation of a Month.
        Each day contains the date and a list of items for that day.
        
        Structure:
        [
            [ {day: 1, items: [...]}, {day: 2, items: [...]}, ... ], # Week 1
            ...
        ]
        """
        # 1. Calculate time range for the query
        num_days = calendar.monthrange(year, month)[1]
        start_date = datetime(year, month, 1)
        # End date is the 1st of the next month
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        # 2. Fetch all items for this month in one DB call
        month_items = await self.get_items_in_range(start_date, end_date)

        # 3. Create the calendar matrix (list of weeks)
        # monthdayscalendar returns 0 for days outside the month
        weeks_matrix = self.cal.monthdayscalendar(year, month)
        
        structured_calendar = []

        for week in weeks_matrix:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append(None) # Empty slot (padding for week)
                    continue
                
                # Filter items belonging to this specific day
                # (You can optimize this further by using a dict map instead of list comprehension)
                current_day_start = datetime(year, month, day)
                current_day_end = current_day_start + timedelta(days=1)
                
                day_items = [
                    item for item in month_items 
                    if current_day_start <= item["start_time"] < current_day_end
                ]

                week_data.append({
                    "day": day,
                    "date": current_day_start.strftime("%Y-%m-%d"),
                    "items": day_items
                })
            structured_calendar.append(week_data)

        return structured_calendar


calendar_wrapper = CalendarWrapper()