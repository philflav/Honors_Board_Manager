#!/usr/bin/env python3
"""
Honors Board Scraper Script
Runs the honors board scraping and saves to cache.
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
    
    # Load board IDs from req_boards.json, or use defaults
    board_ids_file = "req_boards.json"
    if os.path.exists(board_ids_file):
        try:
            with open(board_ids_file, "r") as f:
                board_ids = json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Error reading {board_ids_file}, using defaults.")
            board_ids = [54, 45, 19, 34, 92, 76, 70, 69, 68]
    else:
        board_ids = [54, 45, 19, 34, 92, 76, 70, 69, 68]

    # Command line override
    if len(sys.argv) > 1:
        try:
            board_ids = [int(x) for x in sys.argv[1:]]
        except ValueError:
            print("Invalid board IDs")
            sys.exit(1)
    
    cache_file = "honors_boards_cache.json"
    
    scraper = IntelligentGolfScraper(CLUB_URL, USERNAME, PIN)
    boards_data = scraper.run_honors_boards(board_ids, force_refresh=True, cache_file=cache_file)
    
    if boards_data:
        print(f"Successfully scraped {len(boards_data)} boards")
    else:
        print("Failed to scrape boards")
        sys.exit(1)

if __name__ == "__main__":
    main()