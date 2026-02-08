from http.server import BaseHTTPRequestHandler
from datetime import datetime, timedelta
import requests
from icalendar import Calendar, Event
import dateutil.parser

# --- CONFIGURATION ---
MLB_API_URL = "https://statsapi.mlb.com/api/v1/schedule"
TEAM_ID = 136  # Seattle Mariners

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 1. Setup Calendar
            cal = Calendar()
            cal.add('prodid', '-//Mariners Schedule//mxm.dk//')
            cal.add('version', '2.0')
            cal.add('X-WR-CALNAME', 'Mariners (Live)')
            cal.add('refresh-interval;value=duration', 'PT1H')

            # 2. Fetch Data
            current_year = datetime.now().year
            params = {
                "sportId": 1,
                "teamId": TEAM_ID,
                "startDate": f"{current_year}-01-01",
                "endDate": f"{current_year}-12-31",
                "hydrate": "team,venue"
            }

            r = requests.get(MLB_API_URL, params=params)
            data = r.json()

            # 3. Process Games
            if data and 'dates' in data:
                for date_info in data['dates']:
                    for game in date_info['games']:
                        
                        # Basic Info
                        game_pk = game.get('gamePk')
                        game_date_str = game.get('gameDate')
                        status = game.get('status', {}).get('detailedState', '')
                        
                        if not game_date_str: continue

                        # Teams
                        teams = game.get('teams', {})
                        away = teams.get('away', {}).get('team', {})
                        home = teams.get('home', {}).get('team', {})
                        
                        away_name = away.get('name', 'Unknown')
                        home_name = home.get('name', 'Unknown')
                        away_abbr = away.get('abbreviation', away_name[:3].upper())
                        home_abbr = home.get('abbreviation', home_name[:3].upper())

                        # Logic
                        is_home = (home.get('id') == TEAM_ID)
                        
                        if is_home:
                            summary = f"⚾️ vs. {away_abbr}"
                            venue = teams.get('home', {}).get('venue', {}).get('name', 'Home')
                            location = f"{venue}, {home_name}"
                            desc = f"Mariners vs {away_name}"
                        else:
                            summary = f"⚾️ @ {home_abbr}"
                            venue = teams.get('home', {}).get('venue', {}).get('name', 'Away')
                            location = f"{venue}, {home_name}"
                            desc = f"Mariners @ {home_name}"

                        if status in ['Postponed', 'Cancelled']:
                            summary = f"[POSTPONED] {summary}"

                        # Create Event
                        event = Event()
                        event.add('summary', summary)
                        event.add('uid', str(game_pk))
                        event.add('location', location)
                        event.add('description', desc)
                        
                        # Time
                        dt_start = dateutil.parser.isoparse(game_date_str)
                        event.add('dtstart', dt_start)
                        event.add('dtend', dt_start + timedelta(hours=3))
                        event.add('dtstamp', datetime.now())
                        
                        cal.add_component(event)

            # 4. Send Response (Success)
            self.send_response(200)
            self.send_header('Content-type', 'text/calendar')
            self.send_header('Content-Disposition', 'inline; filename=mariners.ics')
            self.end_headers()
            self.wfile.write(cal.to_ical())

        except Exception as e:
            # 5. Send Error Response (If it crashes, tell us why)
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            error_message = f"Script Error: {str(e)}"
            self.wfile.write(error_message.encode('utf-8'))
            print(error_message)
