import requests
import time
import os
import subprocess
from datetime import datetime

def load_env_file(filepath='.env'):
    """Simple .env file parser that doesn't require external dependencies"""
    env_vars = {}
    if not os.path.exists(filepath):
        return env_vars
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                env_vars[key] = value
    
    return env_vars

# Load environment variables from .env file
env_vars = load_env_file()

# Twitch API Configuration
CLIENT_ID = env_vars.get("TWITCH_CLIENT_ID") or os.environ.get("TWITCH_CLIENT_ID")
CLIENT_SECRET = env_vars.get("TWITCH_CLIENT_SECRET") or os.environ.get("TWITCH_CLIENT_SECRET")
STREAMER_NAMES = (env_vars.get("TWITCH_STREAMER_NAMES") or os.environ.get("TWITCH_STREAMER_NAMES", "")).split(",")

# Clean up streamer names (remove whitespace)
STREAMER_NAMES = [name.strip() for name in STREAMER_NAMES if name.strip()]

# Check interval in seconds
CHECK_INTERVAL = int(env_vars.get("CHECK_INTERVAL") or os.environ.get("CHECK_INTERVAL", "60"))

# Color functions using tput
def tput(command):
    """Execute tput command and return the result"""
    try:
        result = subprocess.check_output(['tput'] + command.split())
        return result.decode('utf-8')
    except:
        return ''

# Initialize colors using tput
class Colors:
    RESET = tput('sgr0')
    BOLD = tput('bold')
    
    # Colors using setaf (set ANSI foreground)
    RED = tput('setaf 1')
    GREEN = tput('setaf 2')
    YELLOW = tput('setaf 3')
    BLUE = tput('setaf 4')
    MAGENTA = tput('setaf 5')
    CYAN = tput('setaf 6')
    WHITE = tput('setaf 7')

def clear_screen():
    """Clear the terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def validate_config():
    """Validate that all required environment variables are set"""
    if not CLIENT_ID:
        raise ValueError("TWITCH_CLIENT_ID environment variable is not set")
    if not CLIENT_SECRET:
        raise ValueError("TWITCH_CLIENT_SECRET environment variable is not set")
    if not STREAMER_NAMES:
        raise ValueError("TWITCH_STREAMER_NAMES environment variable is not set or empty")

def get_oauth_token():
    """Get OAuth token for Twitch API"""
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    
    response = requests.post(url, params=params)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        raise Exception("Failed to get OAuth token: {0}".format(response.status_code))

def check_multiple_streamers(streamer_names, access_token):
    """Check if multiple streamers are currently live (up to 100 at once)"""
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": "Bearer {0}".format(access_token)
    }
    
    # API allows up to 100 user_login parameters
    params = [("user_login", name) for name in streamer_names]
    
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        
        # Create a dictionary of live streamers
        live_streamers = {}
        for stream_info in data["data"]:
            live_streamers[stream_info["user_login"].lower()] = {
                "is_live": True,
                "title": stream_info["title"],
                "game": stream_info["game_name"],
                "viewer_count": stream_info["viewer_count"],
                "started_at": stream_info["started_at"]
            }
        
        # Add offline status for streamers not in the response
        result = {}
        for name in streamer_names:
            name_lower = name.lower()
            if name_lower in live_streamers:
                result[name] = live_streamers[name_lower]
            else:
                result[name] = {"is_live": False}
        
        return result
    else:
        raise Exception("API request failed: {0}".format(response.status_code))

def format_viewer_count(count):
    """Format viewer count with K for thousands"""
    if count >= 1000:
        return "{0:.1f}K".format(count/1000)
    return str(count)

def display_status(statuses, last_update, seconds_remaining):
    """Display streamers in a nice visual format"""
    clear_screen()
    
    # Header
    print("{0}{1}={'=' * 78}{2}".format(Colors.BOLD, Colors.CYAN, Colors.RESET))
    print("{0}{1}{2:^78}{3}".format(Colors.BOLD, Colors.CYAN, 'TWITCH STREAM MONITOR', Colors.RESET))
    print("{0}{1}={'=' * 78}{2}".format(Colors.BOLD, Colors.CYAN, Colors.RESET))
    print()
    
    # Sort streamers: live ones first, then offline
    live_streamers = [(name, status) for name, status in statuses.items() if status["is_live"]]
    offline_streamers = [(name, status) for name, status in statuses.items() if not status["is_live"]]
    
    # Count summary
    live_count = len(live_streamers)
    total_count = len(statuses)
    print("{0}  Status: {1}{2} LIVE{3}{0} / {4}{5} OFFLINE{3}{0} / {6} Total{3}".format(
        Colors.BOLD, Colors.GREEN, live_count, Colors.RESET, Colors.RED, total_count - live_count, total_count))
    print("  Last Update: {0}".format(last_update))
    print()
    
    # Display live streamers
    if live_streamers:
        print("{0}{1}  * LIVE STREAMS{2}".format(Colors.BOLD, Colors.GREEN, Colors.RESET))
        print("{0}  {1}{2}".format(Colors.GREEN, '-' * 76, Colors.RESET))
        for name, status in live_streamers:
            viewers = format_viewer_count(status["viewer_count"])
            title = status["title"][:55] + "..." if len(status["title"]) > 55 else status["title"]
            game = status["game"][:20] + "..." if len(status["game"]) > 20 else status["game"]
            
            print("{0}{1}  +-- {2}{3}".format(Colors.BOLD, Colors.GREEN, name.upper(), Colors.RESET))
            print("{0}  |{1}   {2}Title:{1} {3}".format(Colors.GREEN, Colors.RESET, Colors.BOLD, title))
            print("{0}  |{1}   {2}Game:{1} {3}{4}{1}".format(Colors.GREEN, Colors.RESET, Colors.BOLD, Colors.CYAN, game))
            print("{0}  |{1}   {2}Viewers:{1} {3}{4}{1}".format(Colors.GREEN, Colors.RESET, Colors.BOLD, Colors.YELLOW, viewers))
            print("{0}  {1}{2}".format(Colors.GREEN, '-' * 76, Colors.RESET))
            print()
    
    # Display offline streamers
    if offline_streamers:
        print("{0}{1}  o OFFLINE{2}".format(Colors.BOLD, Colors.RED, Colors.RESET))
        print("{0}  {1}{2}".format(Colors.RED, '-' * 76, Colors.RESET))
        
        # Display offline streamers in columns
        cols = 3
        for i in range(0, len(offline_streamers), cols):
            row = offline_streamers[i:i+cols]
            formatted_names = ["{0}  - {1:<22}{2}".format(Colors.RED, name, Colors.RESET) for name, _ in row]
            print("".join(formatted_names))
        print()
    
    # Footer with countdown
    print("  {0}".format('-' * 76))
    print("  Next check in {0}{1}{2} seconds... (Press Ctrl+C to exit){2}".format(
        Colors.YELLOW, seconds_remaining, Colors.RESET), end='\r')

def main():
    try:
        validate_config()
        
        # Initial screen
        clear_screen()
        print("{0}{1}Initializing Twitch Stream Monitor...{2}".format(Colors.BOLD, Colors.CYAN, Colors.RESET))
        print("Monitoring {0} streamers".format(len(STREAMER_NAMES)))
        
        # Get OAuth token
        access_token = get_oauth_token()
        print("{0}Successfully authenticated with Twitch API{1}".format(Colors.GREEN, Colors.RESET))
        time.sleep(2)
        
        while True:
            try:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                statuses = check_multiple_streamers(STREAMER_NAMES, access_token)
                
                # Countdown loop
                for seconds_remaining in range(CHECK_INTERVAL, 0, -1):
                    display_status(statuses, timestamp, seconds_remaining)
                    time.sleep(1)
                
            except Exception as e:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                clear_screen()
                print("\n{0}[{1}] Error checking status: {2}{3}".format(Colors.RED, timestamp, e, Colors.RESET))
                print("{0}Retrying in {1} seconds...{2}".format(Colors.YELLOW, CHECK_INTERVAL, Colors.RESET))
                time.sleep(CHECK_INTERVAL)
                
    except KeyboardInterrupt:
        clear_screen()
        print("\n{0}Stopping monitor... Goodbye!{1}\n".format(Colors.YELLOW, Colors.RESET))
    except ValueError as e:
        print("{0}Configuration Error: {1}{2}".format(Colors.RED, e, Colors.RESET))
        print("\n{0}Please create a .env file with the following variables:{1}".format(Colors.YELLOW, Colors.RESET))
        print("TWITCH_CLIENT_ID=your_client_id")
        print("TWITCH_CLIENT_SECRET=your_client_secret")
        print("TWITCH_STREAMER_NAMES=streamer1,streamer2,streamer3")
        print("CHECK_INTERVAL=60  # optional, defaults to 60 seconds")
    except Exception as e:
        print("{0}Error: {1}{2}".format(Colors.RED, e, Colors.RESET))

if __name__ == "__main__":
    main()
