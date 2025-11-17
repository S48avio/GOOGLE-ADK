import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from pydantic import BaseModel, Field # Pydantic Field is needed for descriptions
from datetime import datetime
import requests

# --- IMPORTANT ADK/Tool Imports ---
# This line provides the decorator and the Field function used for schemas.
# Note: If this line causes an ImportError, you may need to run:

# --- IMPORTANT: Scopes and Token File ---
# Scopes define what your app can do. If you change them, delete token.json!
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
TOKEN_FILE = 'my_agent/token.json'
CREDENTIALS_FILE = 'my_agent/credentials.json'

def get_calendar_service():
    """Authenticates and returns a service object for the Google Calendar API."""
    creds = None
    
    # Check if we have valid saved credentials (token.json)
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If no valid credentials, initiate the login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Refresh token if expired
            creds.refresh(Request())
        else:
            # First-time login: uses credentials.json to open browser
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Missing {CREDENTIALS_FILE}. Please download it from Google Cloud Console.")
                
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

# --- Pydantic Schema for Calendar Tool Input ---
class CreateEventInput(BaseModel):
    """Schema for the Create Calendar Event Tool. Note that the event will use the user's primary calendar timezone."""
    summary: str = Field(description="The title or brief description of the event, e.g., 'Team Meeting'.")
    start_time: str = Field(description="Event start time in ISO 8601 format, including date and time (e.g., 2025-12-01T10:00:00).")
    end_time: str = Field(description="Event end time in ISO 8601 format, including date and time (e.g., 2025-12-01T11:00:00).")
    timezone: str = Field(default='Asia/Kolkata', description="Time Zone for the date and time setting (e.g., 'Asia/Kolkata'). Defaults to 'Asia/Kolkata' if not specified.")

# --- ADK Calendar Tool Definition ---

def create_calendar_event(input: CreateEventInput) -> str:
    """
    Creates a new event on the user's primary Google Calendar.
    Requires date-time inputs in ISO format (YYYY-MM-DDTHH:MM:SS) for start and end times.
    """
    try:
        service = get_calendar_service()
        
        # Event structure required by the Google Calendar API
        event = {
            'summary': input.summary,
            # Correctly applying timeZone to start and end objects
            'start': {'dateTime': input.start_time, 'timeZone': input.timezone},
            'end': {'dateTime': input.end_time, 'timeZone': input.timezone},
        }
        
        # Insert the event into the primary calendar
        event = service.events().insert(calendarId='primary', body=event).execute()
        
        return f"SUCCESS: Event '{event.get('summary')}' scheduled on {event.get('start').get('dateTime')}. Link: {event.get('htmlLink')}"

    except Exception as e:
        # Provide the agent with a clear error if the tool fails
        return f"ERROR: Could not create event. Details: {str(e)}"

# --- Weather API Endpoints ---
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

def get_weather(city: str) -> dict:
    """Retrieves the hourly temperature forecast for a specified city for 1 day.

    This function first converts the city name to coordinates (Geocoding) and
    then fetches the hourly temperature data from the Open-Meteo API.

    Args:
        city (str): The name of the city (e.g., "New York", "London", "Tokyo").

    Returns:
        dict: A dictionary containing the weather information or an error message.
    """
    print(f"--- Tool: get_weather called for city: {city} ---")

    try:
        # 1. Geocoding: Convert City Name to Coordinates
        geo_params = {'name': city, 'count': 1, 'language': 'en', 'format': 'json'}
        geo_response = requests.get(GEOCODING_URL, params=geo_params)
        geo_response.raise_for_status()
        geo_data = geo_response.json()

        if not geo_data.get('results'):
            return {"status": "error", "error_message": f"Sorry, could not find coordinates for '{city}'."}

        # Use the first result (usually the most popular city)
        location = geo_data['results'][0]
        latitude = location['latitude']
        longitude = location['longitude']

        found_city = location['name']
        country = location['country']

        # 2. Forecast: Get Hourly Temperature Data
        forecast_params = {
            'latitude': latitude,
            'longitude': longitude,
            'hourly': 'temperature_2m',
            'forecast_days': 1
        }
        forecast_response = requests.get(FORECAST_URL, params=forecast_params)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()

        # 3. Process and Compile Report
        times = forecast_data['hourly']['time']
        temperatures = forecast_data['hourly']['temperature_2m']

        # Find the min/max for the 24-hour period
        min_temp = min(temperatures)
        max_temp = max(temperatures)

        # Create a detailed report (you can customize the output format)
        report = (
            f"Hourly Temperature Forecast for {found_city}, {country} "
            f"(Lat: {latitude:.2f}, Lon: {longitude:.2f}) for the next 24 hours:\n"
            f"Min Temperature: {min_temp}°C\n"
            f"Max Temperature: {max_temp}°C\n"
            f"Hourly Data (Time: Temp):\n"
        )
        # Add a few key hourly points for brevity
        for i in range(0, len(times), 4): # Sample every 4 hours
            report += f"  {times[i].split('T')[1].split(':')[0]}h: {temperatures[i]}°C\n"


        return {
            "status": "success",
            "city": found_city,
            "report": report,
            "min_temperature_celsius": min_temp,
            "max_temperature_celsius": max_temp,
            "hourly_data": list(zip(times, temperatures)) # Provides all raw data
        }

    except requests.exceptions.HTTPError as e:
        return {"status": "error", "error_message": f"HTTP Error: Could not fetch data. ({e})"}

    except requests.exceptions.RequestException:
        return {"status": "error", "error_message": "Connection Error: Could not connect to the API server."}

    except Exception as e:
        return {"status": "error", "error_message": f"An unexpected error occurred: {e}"}

# ==============================================================================
# --- NEWS TOOL IMPLEMENTATION (Using newsapi.org with provided key) ---
# ==============================================================================

# --- News API Endpoint and Key (from user's request) ---
NEWS_API_BASE_URL_EVERYTHING = "https://newsapi.org/v2/everything"
NEWS_API_BASE_URL_HEADLINES = "https://newsapi.org/v2/top-headlines"
NEWS_API_KEY = "7bf6895b452a4bf2b3f84c531e36dffd" 

# --- Pydantic Schema for News Tool Input ---
class NewsToolInput(BaseModel):
    """
    Schema for the News Tool. Use 'general' for top US headlines or a specific subject.
    """
    query: str = Field(
        default='general', 
        description="The subject for the news search (e.g., 'bitcoin', 'technology'). Use 'general' for top US headlines."
    )
    max_articles: int = Field(
        default=5,
        description="Maximum number of articles to return (API limits may apply)."
    )

# --- ADK News Tool Definition ---

def news_tool(input: NewsToolInput) -> str:
    """
    Retrieves top news headlines or news about a specific subject and returns 
    a formatted list of titles and descriptions using newsapi.org.
    """
    print(f"--- Tool: news_tool called for query: {input.query} ---")

    try:
        if input.query.lower() == 'general':
            # Use top-headlines endpoint for general news (like the user's second example URL)
            api_url = NEWS_API_BASE_URL_HEADLINES
            params = {
                'apiKey': NEWS_API_KEY,
                'country': 'us', # Defaulting to 'us' as per the user's example URL
                'pageSize': input.max_articles 
            }
            query_desc = "Top US Headlines"
        else:
            # Use everything endpoint for searching a specific query (like the user's first example URL)
            api_url = NEWS_API_BASE_URL_EVERYTHING
            params = {
                'apiKey': NEWS_API_KEY,
                'q': input.query,
                'sortBy': 'publishedAt', # Sort by recency
                'pageSize': input.max_articles 
            }
            query_desc = f"News about '{input.query}'"
            
        
        response = requests.get(api_url, params=params)
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        
        articles = data.get('articles', [])
        
        if not articles:
            return f"INFO: No news articles found for {query_desc}."
            
        # Format the output to only include Title and Description
        output_list = []
        for i, article in enumerate(articles):
            output_list.append(
                f"--- Article {i+1} ---\n"
                f"Title: {article.get('title', 'N/A')}\n"
                f"Description: {article.get('description', 'N/A')}"
            )

        header = f"Top {len(articles)} Results for {query_desc}:"
        return f"{header}\n\n" + "\n\n".join(output_list)

    except requests.exceptions.HTTPError as e:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        error_message = response.text if 'response' in locals() else str(e)
        return f"ERROR: HTTP Error accessing News API. Status Code: {status_code}. Details: {error_message}"
    except requests.exceptions.RequestException:
        return "ERROR: Connection Error: Could not connect to the News API server."
    except Exception as e:
        return f"ERROR: An unexpected error occurred in news_tool: {e}"