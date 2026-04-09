#!/usr/bin/env python3
"""
Fetch Available Boards Scraper
Discovers all honors boards from the club portal and saves to available_boards.json.
"""

import os
import sys
import json
from ig_scraper import IntelligentGolfScraper
from dotenv import load_dotenv

load_dotenv()

def main():
    CLUB_URL = os.getenv("CLUB_URL")
    USERNAME = os.getenv("USERNAME")
    PIN = os.getenv("PIN")
    
    if not all([CLUB_URL, USERNAME, PIN]):
        print("Error: Missing environment variables.")
        sys.exit(1)
    
    cache_file = "available_boards.json"
    
    scraper = IntelligentGolfScraper(CLUB_URL, USERNAME, PIN)
    print("🚀 Triggering board discovery...")
    boards = scraper.run_discovery(cache_file=cache_file)
    
    if boards:
        print(f"✅ Successfully discovered {len(boards)} boards")
    else:
        print("❌ Failed to discover boards")
        sys.exit(1)

if __name__ == "__main__":
    main()
