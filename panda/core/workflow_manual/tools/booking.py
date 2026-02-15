from typing import Optional
from langchain_core.tools import tool

@tool
def search_flights(origin: str, destination: str, date: str) -> str:
    """Search for flights between two cities."""
    return f"""Found 3 flights from {origin} to {destination} on {date}:
    1. Flight AI-101: 08:00 AM - 10:00 AM, Price: $150
    2. Flight BA-202: 12:00 PM - 02:00 PM, Price: $180
    3. Flight CD-303: 06:00 PM - 08:00 PM, Price: $120
    """

@tool
def book_flight(flight_id: str) -> str:
    """Book a flight by ID."""
    return f"Successfully booked flight {flight_id}. Confirmation code: PRE-12345."

@tool
def search_hotels(location: str, date: str) -> str:
    """Search for hotels in a location."""
    return f"""Found 3 hotels in {location} for {date}:
    1. Grand Plaza: 5 stars, $200/night
    2. City Stay: 4 stars, $120/night
    3. Budget Inn: 3 stars, $80/night
    """

@tool
def book_hotel(hotel_id: str) -> str:
    """Book a hotel by ID."""
    return f"Successfully booked hotel {hotel_id}. Confirmation code: HTL-67890."

@tool
def search_trains(origin: str, destination: str, date: str) -> str:
    """Search for trains between two cities."""
    return f"""Found 3 trains from {origin} to {destination} on {date}:
    1. Express 101: 09:00 AM - 12:00 PM, Price: $50
    2. Intercity 202: 01:00 PM - 04:00 PM, Price: $45
    3. Night Rider 303: 10:00 PM - 06:00 AM, Price: $40
    """

@tool
def book_train(train_id: str) -> str:
    """Book a train by ID."""
    return f"Successfully booked train {train_id}. Confirmation code: TRN-54321."

booking_tools = [
    search_flights,
    book_flight,
    search_hotels,
    book_hotel,
    search_trains,
    book_train
]
