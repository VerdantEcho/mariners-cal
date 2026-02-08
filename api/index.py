from flask import Flask, Response
import requests
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import dateutil.parser

app = Flask(__name__)

# --- CONFIGURATION ---
MLB_API_URL = "https://statsapi.mlb.com/api/v1/schedule"
TEAM_ID = 136  # 136 is the ID for Seattle Mariners

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def handler(path):
    # 1. Setup the Calendar Metadata
    cal = Calendar()
    cal.add('prodid', '-//Mariners Schedule//mxm.dk//')
    cal.add('version', '2.0')
    cal.add('X-WR-CALNAME', 'Mariners (Live)')  # Name shown in your app
    cal.add('refresh-interval;value=duration', 'PT1H') # Refresh every hour

    # 2. Calculate Dates (Get full current year)
    current_year = datetime.now().year
    start_date = f"{current_year}-01-01"
    end_date = f"{current_year}-12-31"

    # 3. Fetch Data from MLB API
    params = {
        "sportId": 1,
        "teamId": TEAM_ID,
        "startDate": start_date,
        "endDate": end_date,
        "hydrate": "team,venue" # Ask for team details and venue names
    }

    try:
        r = requests.get(MLB_API_URL, params=params)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return f"Error fetching MLB data: {str(e)}", 500

    # 4. Process Games
    if data and 'dates' in data:
        for date_info in data['dates']:
            for game in date_info['games']:
                
                # Extract basic info
                game_pk = game.get('gamePk')
                game_date_str = game.get('gameDate') # ISO format: 2024-03-28T20:10:00Z
                status = game.get('status', {}).get('detailedState', '')

                # Skip if no date
                if not game_date_str: continue

                # Identify Home vs Away
                teams = game.get('teams', {})
                away = teams.get('away', {}).get('team', {})
                home = teams.get('home', {}).get('team', {})
                
                # Get Abbreviations (defaults to first 3 letters if missing)
                away_abbr = away.get('abbreviation', away.get('name', 'UNK')[:3].upper())
                home_abbr = home.get('abbreviation', home.get('name', 'UNK')[:3].upper())
                
                # Determine "vs" or "@"
                is_home_game = (home.get('id') == TEAM_ID)
                
                if is_home_game:
                    summary = f"vs. {away_abbr}"
                    location = "T-Mobile Park"
                    desc = f"Seattle Mariners vs {away.get('name')}"
                else:
                    summary = f"@ {home_abbr}"
                    venue = teams.get('home', {}).get('venue', {}).get('name', 'Away')
                    location = f"{venue}, {home.get('name')}"
                    desc = f"Seattle Mariners @ {home.get('name')}"

                # Handle Postponements
                if status in ['Postponed', 'Cancelled']:
                    summary = f"[POSTPONED] {summary}"

                # Create the Event Object
                event = Event()
                event.add('summary', summary)
                event.add('uid', str(game_pk)) # Unique ID prevents duplicates
                event.add('location', location)
                event.add('description', desc)

                # Parse Time (MLB provides UTC)
                dt_start = dateutil.parser.isoparse(game_date_str)
                event.add('dtstart', dt_start)
                event.add('dtend', dt_start + timedelta(hours=3)) # Assume 3 hour game
                event.add('dtstamp', datetime.now())

                cal.add_component(event)

    # 5. Return the formatted Calendar file
    return Response(
        cal.to_ical(),
        mimetype="text/calendar",
        headers={"Content-Disposition": "inline; filename=mariners_live.ics"}
    )