import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Twitch API Configuration
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
STREAMER_NAMES = os.getenv("TWITCH_STREAMER_NAMES", "").split(",")

# Clean up streamer names (remove whitespace)
STREAMER_NAMES = [name.strip() for name in STREAMER_NAMES if name.strip()]

# Check interval in seconds
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))

# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Colors
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    
    # Background colors
    BG_RED = '\033[101m'
    BG_GREEN = '\033[102m'
    BG_BLACK = '\033[40m'

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
        raise Exception(f"Failed to get OAuth token: {response.status_code}")

def check_multiple_streamers(streamer_names, access_token):
    """Check if multiple streamers are currently live (up to 100 at once)"""
    url = "https://api.twitch.tv/helix/streams"
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {access_token}"
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
        raise Exception(f"API request failed: {response.status_code}")

def format_viewer_count(count):
    """Format viewer count with K for thousands"""
    if count >= 1000:
        return f"{count/1000:.1f}K"
    return str(count)

def display_status(statuses, last_update, seconds_remaining):
    """Display streamers in a nice visual format"""
    clear_screen()
    
    # Header
    print(f"{Colors.BOLD}{Colors.CYAN}╔{'═' * 78}╗{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{Colors.WHITE}{'TWITCH STREAM MONITOR':^78}{Colors.CYAN}║{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚{'═' * 78}╝{Colors.RESET}")
    print()
    
    # Sort streamers: live ones first, then offline
    live_streamers = [(name, status) for name, status in statuses.items() if status["is_live"]]
    offline_streamers = [(name, status) for name, status in statuses.items() if not status["is_live"]]
    
    # Count summary
    live_count = len(live_streamers)
    total_count = len(statuses)
    print(f"{Colors.BOLD}  Status: {Colors.GREEN}{live_count} LIVE{Colors.RESET}{Colors.BOLD} / {Colors.RED}{total_count - live_count} OFFLINE{Colors.RESET}{Colors.BOLD} / {total_count} Total{Colors.RESET}")
    print(f"{Colors.GRAY}  Last Update: {last_update}{Colors.RESET}")
    print()
    
    # Display live streamers
    if live_streamers:
        print(f"{Colors.BOLD}{Colors.GREEN}  ● LIVE STREAMS{Colors.RESET}")
        print(f"{Colors.GREEN}  {'─' * 76}{Colors.RESET}")
        for name, status in live_streamers:
            viewers = format_viewer_count(status["viewer_count"])
            title = status["title"][:55] + "..." if len(status["title"]) > 55 else status["title"]
            game = status["game"][:20] + "..." if len(status["game"]) > 20 else status["game"]
            
            print(f"{Colors.BOLD}{Colors.GREEN}  ┌─ {name.upper()}{Colors.RESET}")
            print(f"{Colors.GREEN}  │{Colors.RESET}  {Colors.BOLD}Title:{Colors.RESET} {title}")
            print(f"{Colors.GREEN}  │{Colors.RESET}  {Colors.BOLD}Game:{Colors.RESET} {Colors.CYAN}{game}{Colors.RESET}")
            print(f"{Colors.GREEN}  │{Colors.RESET}  {Colors.BOLD}Viewers:{Colors.RESET} {Colors.YELLOW}{viewers}{Colors.RESET}")
            print(f"{Colors.GREEN}  └{'─' * 74}{Colors.RESET}")
            print()
    
    # Display offline streamers
    if offline_streamers:
        print(f"{Colors.BOLD}{Colors.RED}  ○ OFFLINE{Colors.RESET}")
        print(f"{Colors.RED}  {'─' * 76}{Colors.RESET}")
        
        # Display offline streamers in columns
        cols = 3
        for i in range(0, len(offline_streamers), cols):
            row = offline_streamers[i:i+cols]
            formatted_names = [f"{Colors.RED}  • {name:<22}{Colors.RESET}" for name, _ in row]
            print("".join(formatted_names))
        print()
    
    # Footer with countdown
    print(f"{Colors.GRAY}  {'─' * 76}{Colors.RESET}")
    print(f"{Colors.GRAY}  Next check in {Colors.YELLOW}{seconds_remaining}{Colors.GRAY} seconds... (Press Ctrl+C to exit){Colors.RESET}", end='\r')

def main():
    try:
        validate_config()
        
        # Initial screen
        clear_screen()
        print(f"{Colors.BOLD}{Colors.CYAN}Initializing Twitch Stream Monitor...{Colors.RESET}")
        print(f"{Colors.GRAY}Monitoring {len(STREAMER_NAMES)} streamers{Colors.RESET}")
        
        # Get OAuth token
        access_token = get_oauth_token()
        print(f"{Colors.GREEN}✓ Successfully authenticated with Twitch API{Colors.RESET}")
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
                print(f"\n{Colors.RED}[{timestamp}] Error checking status: {e}{Colors.RESET}")
                print(f"{Colors.YELLOW}Retrying in {CHECK_INTERVAL} seconds...{Colors.RESET}")
                time.sleep(CHECK_INTERVAL)
                
    except KeyboardInterrupt:
        clear_screen()
        print(f"\n{Colors.YELLOW}Stopping monitor... Goodbye!{Colors.RESET}\n")
    except ValueError as e:
        print(f"{Colors.RED}Configuration Error: {e}{Colors.RESET}")
        print(f"\n{Colors.YELLOW}Please create a .env file with the following variables:{Colors.RESET}")
        print("TWITCH_CLIENT_ID=your_client_id")
        print("TWITCH_CLIENT_SECRET=your_client_secret")
        print("TWITCH_STREAMER_NAMES=streamer1,streamer2,streamer3")
        print("CHECK_INTERVAL=60  # optional, defaults to 60 seconds")
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")

if __name__ == "__main__":
    main()
