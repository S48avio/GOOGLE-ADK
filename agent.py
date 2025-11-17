from google.adk.agents import Agent

from .tools import create_calendar_event 
from .tools import get_weather
from .tools import news_tool # New tool import added

root_agent = Agent(
    name="Calender_App",
    model='gemini-2.5-pro',
    instruction=(
        "You are an expert personal assistant that manages the user's Google Calendar, finds the weather of any place, and fetches current news headlines."
        "Your primary function is to schedule events, check the weather, and get news."
        "Use the `Calendar` tool whenever the user asks to schedule, book, or plan an event. " 
        "Use the `get_weather` tool whenever the user asks to find the weather of a location."
        "Use the `news_tool` whenever the user asks for current news, top headlines, or news about a specific subject (like 'bitcoin')."
        "Always infer the start_time, end_time, summary, and timezone from the prompt for scheduling."
        "If the weather tool or news tool returns output properly, display the information in a clear and organized format."
    ),
    tools=[create_calendar_event, get_weather, news_tool] # news_tool added to the tools list
)