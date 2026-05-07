#!/usr/bin/env python3
"""Tests login credentials against the Intelligent Golf portal."""

import os
import sys
from ig_scraper import IntelligentGolfScraper
from dotenv import load_dotenv

load_dotenv()

def main():
    CLUB_URL = os.getenv("CLUB_URL")
    USERNAME = os.getenv("USERNAME")
    PIN = os.getenv("PIN")

    if not CLUB_URL:
        print("Error: CLUB_URL environment variable is not set.")
        sys.exit(1)
    if not USERNAME or not PIN:
        print("Error: USERNAME and PIN must be provided.")
        sys.exit(1)

    scraper = IntelligentGolfScraper(CLUB_URL, USERNAME, PIN)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        scraper.browser = p.chromium.launch(headless=True)
        scraper.page = scraper.browser.new_page()
        try:
            success = scraper.login()
            if success:
                print(f"Successfully logged in as {USERNAME}")
                sys.exit(0)
            else:
                print("Invalid login credentials.")
                sys.exit(1)
        finally:
            scraper.browser.close()


if __name__ == "__main__":
    main()
