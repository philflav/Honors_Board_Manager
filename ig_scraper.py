"""
Intelligent Golf Competition Results Scraper
A proof-of-concept for extracting competition results from Intelligent Golf portals

Requirements:
pip install playwright
playwright install chromium
"""

from playwright.sync_api import sync_playwright
import json
# Optional local_cache for competition results
try:
    import local_cache
except ImportError:
    local_cache = None
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

class IntelligentGolfScraper:
    def __init__(self, club_url, username, pin):
        self.club_url = club_url
        self.username = username
        self.pin = pin
        self.browser = None
        self.page = None
    
    def login(self):
        """Log in to the Intelligent Golf portal"""
        print(f"Navigating to {self.club_url}...")
        self.page.goto(self.club_url)
        
        # Accept cookies if present
        try:
            self.page.get_by_role("link", name="ACCEPT COOKIES").click(timeout=3000)
            print("Cookies accepted")
        except:
            print("No cookie banner found")
        
        # Fill in login form
        print(f"Filling login form for user: {self.username}...")
        self.page.get_by_role("textbox", name="Login:").fill(str(self.username))
        self.page.get_by_role("textbox", name="PIN Number:").fill(str(self.pin))
        
        # Click login button
        self.page.get_by_role("button", name="Login").click()
        # Wait for navigation or error message
        self.page.wait_for_timeout(2000) 
        
        if self.page.get_by_text("Invalid login").is_visible():
            print("ERROR: Invalid login credentials provided.")
            return False
            
        print("Logged in successfully!")
        return True
        
    def get_recent_competitions(self):
        """Get list of recent competitions"""
        print("Fetching competition list...")
        self.page.goto(f"{self.club_url}/competition.php")
        
        # Extract competition data
        competitions = self.page.evaluate("""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                const comps = [];
                
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 3) {
                        const link = cells[0].querySelector('a');
                        if (link) {
                            comps.push({
                                name: link.textContent.trim(),
                                date: cells[1].textContent.trim(),
                                winner: cells[2].textContent.trim(),
                                url: link.getAttribute('href')
                            });
                        }
                    }
                });
                
                return comps;
            }
        """)
        
        print(f"Found {len(competitions)} recent competitions")
        return competitions
    
    def get_competition_results(self, comp_url):
        """Get detailed results for a specific competition"""
        full_url = f"{self.club_url}/competition.php{comp_url}"
        print(f"Fetching results from {full_url}...")
        
        self.page.goto(full_url)
        
        # Extract competition details and results
        data = self.page.evaluate("""
            () => {
                const results = [];
                const rows = document.querySelectorAll('table tbody tr');
                
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 3) {
                        results.push({
                            position: cells[0].textContent.trim(),
                            player: cells[1].textContent.trim(),
                            points: cells[2].textContent.trim()
                        });
                    }
                });
                
                return {
                    competition: document.querySelector('h3')?.textContent.trim() || '',
                    date: document.querySelector('h4')?.textContent.trim() || '',
                    results: results
                };
            }
        """)
        
        return data
    
    def get_team_data(self, comp_id):
        """Get team data from startsheet"""
        print(f"Fetching team data for competition {comp_id}...")
        self.page.goto(f"{self.club_url}/competition.php?go=startsheet&compid={comp_id}")

        team_players = self.page.evaluate("""
            () => {
                const rows = document.querySelectorAll('table tbody tr');
                const players = [];
                let team_id = 1;

                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    const rowPlayers = [];

                    // Collect all players in this row (typically 3-4 players per team row)
                    for (let i = 1; i < cells.length; i++) {  // Start from i=1 to skip first cell if it's not a player
                        const cell = cells[i];
                        const playerName = cell.textContent.trim();
                        if (playerName) {
                            // Extract name without handicap
                            const match = playerName.match(/(.+?)\\((\\d+)\\)/);
                            const cleanName = match ? match[1].trim() : playerName;
                            // Skip "reserved" entries as they are not players
                            if (cleanName.toLowerCase() !== 'reserved') {
                                rowPlayers.push(cleanName);
                            }
                        }
                    }

                    // Assign the same team_id to all players in this row
                    if (rowPlayers.length > 0) {
                        rowPlayers.forEach(name => {
                            players.push({
                                name: name,
                                team_id: team_id
                            });
                        });
                        team_id++;  // Increment team_id for the next row
                    }
                });

                return players;
            }
        """)

        print(f"Found {len(team_players)} players in team data")
        return team_players
    
    def get_all_scorecards(self, comp_id):
        """Get detailed hole-by-hole scorecards for all players in a competition"""
        print(f"Fetching all scorecards for competition {comp_id}...")
        self.page.goto(f"{self.club_url}/competition.php?compid={comp_id}")

        # Extract competition date from the page
        comp_date = self.page.evaluate("""() => document.querySelector('h4')?.textContent.trim() || ''""")

        # Get team data first
        team_data = self.get_team_data(comp_id)
        team_map = {player['name'].strip().lower(): player['team_id'] for player in team_data}

        # Navigate back to results page
        self.page.goto(f"{self.club_url}/competition.php?compid={comp_id}")

        # Extract all player data with scorecard URLs
        scorecards = self.page.evaluate("""
            async () => {
                const players = [];
                const rows = document.querySelectorAll('table tbody tr');

                // Get player list with round URLs
                for (const row of rows) {
                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 3) {
                        const playerCell = cells[1];
                        const pointsCell = cells[2];
                        const playerLink = playerCell.querySelector('a');
                        const pointsLink = pointsCell.querySelector('a');

                        if (playerLink && pointsLink) {
                            const playerText = playerCell.textContent.trim();
                            const match = playerText.match(/(.+?)\\((\\d+)\\)/);
                            const name = match ? match[1].trim() : playerText;

                            // Skip "reserved" entries as they are not players
                            if (name.toLowerCase() !== 'reserved') {
                                players.push({
                                    position: cells[0].textContent.trim(),
                                    name: name,
                                    handicap: match ? match[2] : '',
                                    points: pointsCell.textContent.trim(),
                                    roundUrl: pointsLink.getAttribute('href')
                                });
                            }
                        }
                    }
                }

                // Fetch each player's scorecard
                const allScorecards = [];

                for (const player of players) {
                    try {
                        const response = await fetch(player.roundUrl);
                        const html = await response.text();
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');

                        // Extract scorecard data
                        const scoreRows = doc.querySelectorAll('table tbody tr');
                        let scoreRow, parRow, pointsRow;

                        for (const row of scoreRows) {
                            const firstCell = row.querySelector('td strong')?.textContent || '';
                            if (firstCell === 'Par') parRow = row;
                            if (firstCell === 'Score') scoreRow = row;
                            if (firstCell === 'Stableford') pointsRow = row; // Updated to 'Stableford' as per user's manual change
                        }

                        const scorecard = {
                            position: player.position,
                            name: player.name,
                            handicap: player.handicap,
                            totalPoints: player.points,
                            holes: []
                        };

                        if (scoreRow && parRow && pointsRow) {
                            const scoreCells = scoreRow.querySelectorAll('td');
                            const parCells = parRow.querySelectorAll('td');
                            const pointsCells = pointsRow.querySelectorAll('td');

                            // Get individual hole scores (cells 1-18)
                            for (let i = 1; i <= 18; i++) {
                                const cellIndex = (i <= 9) ? i : i + 1; // Adjust for the 'Out' summary column
                                scorecard.holes.push({
                                    hole: i,
                                    par: parCells[cellIndex]?.textContent || '',
                                    score: pointsCells[cellIndex]?.textContent || '' // Now extracting Stableford points as the 'score'
                                });
                            }

                            scorecard.out = pointsCells[10]?.textContent || ''; // 'Out' Stableford points
                            scorecard.in = pointsCells[20]?.textContent || ''; // 'In' Stableford points
                            scorecard.total = pointsCells[21]?.textContent || ''; // 'Total' Stableford points
                        }

                        allScorecards.push(scorecard);
                    } catch (e) {
                        console.error(`Error fetching scorecard for ${player.name}:`, e);
                    }
                }

                return allScorecards;
            }
        """)

        # Add team_id to each scorecard
        for card in scorecards:
            normalized_name = card['name'].strip().lower()
            card['team_id'] = team_map.get(normalized_name, None)
            if card['team_id'] is None:
                # Try partial matching
                for team_name, team_id in team_map.items():
                    if normalized_name in team_name or team_name in normalized_name:
                        card['team_id'] = team_id
                        break

        return scorecards, comp_date
    
    def calculate_team_scores(self, scorecards):
        """Calculate total scores for each team using the best two and worst scores per hole"""
        from collections import defaultdict

        # Group scorecards by team_id
        teams = defaultdict(list)
        for card in scorecards:
            team_id = card.get('team_id')
            if team_id is not None:
                teams[team_id].append(card)

        team_scores = []
        for team_id, cards in teams.items():
            team_total = 0
            team_back_9 = 0
            team_back_6 = 0
            team_back_3 = 0
            team_h18 = 0
            players_info = []

            # For each hole, collect scores from all players in the team
            for hole_num in range(1, 19):
                hole_scores = []
                for card in cards:
                    # Find the hole data
                    hole_data = next((h for h in card.get('holes', []) if h['hole'] == hole_num), None)
                    if hole_data and hole_data.get('score'):
                        try:
                            score = int(hole_data['score'])
                            hole_scores.append(score)
                        except (ValueError, TypeError):
                            pass  # Skip invalid scores

                if len(hole_scores) >= 2:  # Need at least 2 scores to calculate
                    hole_scores.sort(reverse=True)  # Sort descending (highest first)
                    # Take best two (highest) and worst (lowest)
                    best_scores = hole_scores[:2]  # Top 2
                    # Take the worst score ONLY if it's not already counted in the best two (i.e. more than 2 players)
                    worst_score = hole_scores[-1] if len(hole_scores) > 2 else 0
                    hole_contribution = sum(best_scores) + worst_score
                    
                    team_total += hole_contribution
                    if hole_num >= 10:
                        team_back_9 += hole_contribution
                    if hole_num >= 13:
                        team_back_6 += hole_contribution
                    if hole_num >= 16:
                        team_back_3 += hole_contribution
                    if hole_num == 18:
                        team_h18 = hole_contribution

            # Calculate individual player totals for info
            for card in cards:
                total_points = sum(int(h.get('score', 0) or 0) for h in card.get('holes', []))
                players_info.append({
                    'name': card['name'],
                    'handicap': card['handicap'],
                    'points': total_points
                })

            team_scores.append({
                'team_id': team_id,
                'total_points': team_total,
                'back_9': team_back_9,
                'back_6': team_back_6,
                'back_3': team_back_3,
                'h18': team_h18,
                'players': players_info
            })

        # Sort teams by total points descending, then back 9, back 6, back 3, then 18th hole (Full Countback)
        sorted_teams = sorted(team_scores, key=lambda x: (x['total_points'], x['back_9'], x['back_6'], x['back_3'], x['h18']), reverse=True)
        return sorted_teams

    def export_to_csv(self, scorecards, filename):
        """Export scorecards to CSV format"""
        import csv

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)

            # Write header
            header = ['Position', 'Player', 'Handicap', 'Team ID']
            for i in range(1, 19):
                header.append(f'Hole {i} Points') # Changed to only Stableford Points
            header.extend(['Out', 'In', 'Total', 'Points'])
            writer.writerow(header)

            # Write data
            for card in scorecards:
                row = [card['position'], card['name'], card['handicap'], card.get('team_id', '')]
                for hole in card['holes']:
                    row.append(hole['score']) # 'score' now contains Stableford points
                row.extend([card['out'], card['in'], card['total'], card['totalPoints']])
                writer.writerow(row)

    def export_team_scores(self, team_scores, filename):
        """Export team scores to CSV format"""
        import csv

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(['Team ID', 'Total Points', 'Players'])

            # Write data
            for team in team_scores:
                players_str = '; '.join([f"{p['name']} ({p['handicap']}) - {p['points']} pts" for p in team['players']])
                row = [team['team_id'], team['total_points'], players_str]
                writer.writerow(row)

        print(f"Team scores exported to {filename}")
    
    def get_board_data(self, board_id):
        """Get honors board data for a specific board ID"""
        print(f"Fetching honors board {board_id}...")
        
        # Try different possible URLs
        possible_urls = [
            f"{self.club_url.rstrip('/')}/boardcomps.php?board={board_id}",  # boardcomps.php
            f"{self.club_url.rstrip('/')}/?board={board_id}",  # root with board param
        ]
        
        data = None
        for board_url in possible_urls:
            try:
                
                print(f"Trying URL: {board_url}")
                self.page.goto(board_url, wait_until="domcontentloaded")
                self.page.wait_for_timeout(1500)
                
                # Check if page loaded successfully
                page_text = self.page.evaluate("() => document.body.innerText.substring(0, 200)")
                print(f"Page content preview: {page_text[:100]}")
                
                if 'Invalid' not in page_text and 'Get in touch' not in page_text.lower():
                    data = self.page.evaluate("""
                        () => {
                            // Find the board title - look for the first main heading after the "Get in touch"
                            let title = 'Honors Board';
                            
                            // Try to find from common title locations
                            const h1 = document.querySelector('h1');
                            const h2 = document.querySelector('h2');
                            const h3 = document.querySelector('h3');
                            
                            // Look for title in h3 first (often used for board titles)
                            if (h3 && h3.textContent.trim() && h3.textContent.trim() !== 'Get in touch') {
                                title = h3.textContent.trim();
                            } else if (h1 && h1.textContent.trim() && h1.textContent.trim() !== 'Get in touch') {
                                title = h1.textContent.trim();
                            } else if (h2 && h2.textContent.trim() && h2.textContent.trim() !== 'Get in touch') {
                                title = h2.textContent.trim();
                            } else {
                                // Search for any other heading with substantial text
                                const allHeadings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                                for (let heading of allHeadings) {
                                    const text = heading.textContent.trim();
                                    if (text && text.length > 3 && text !== 'Get in touch' && text !== 'HOME') {
                                        title = text;
                                        break;
                                    }
                                }
                            }
                            
                            const winners = [];
                            const tables = document.querySelectorAll('table');
                            
                            // Look through all tables to find the one with winners
                            for (const table of tables) {
                                const rows = table.querySelectorAll('tbody tr');
                                if (rows.length > 0) {
                                    rows.forEach(row => {
                                        const cells = row.querySelectorAll('td');
                                        if (cells.length >= 2) {
                                            const year = cells[0].textContent.trim();
                                            const winner = cells[1].textContent.trim();
                                            // Skip header-looking rows
                                            if (year && winner && year.length < 20 && winner.length < 100 && 
                                                year !== 'Year' && winner !== 'Winner' && year !== 'Name' && winner !== 'Result') {
                                                winners.push({
                                                    year: year,
                                                    winner: winner,
                                                    score: cells.length > 2 ? cells[2].textContent.trim() : null
                                                });
                                            }
                                        }
                                    });
                                    // If we found winners, break
                                    if (winners.length > 0) break;
                                }
                            }
                            
                            return { title, winners };
                        }
                    """)
                    if data and data.get('winners') and len(data['winners']) > 0:
                        print(f"Board {board_id} - Title: {data['title']}, Found {len(data['winners'])} winners")
                        return data
                else:
                    print(f"Page is error page or not a board page")
            except Exception as e:
                print(f"Error with URL {board_url}: {e}")
                continue
        
        # If we get here, return empty data with feedback
        print(f"Board {board_id} - No valid data found on any URL")
        return {'title': f'Board {board_id}', 'winners': []}
    
    def get_honors_boards(self, board_ids):
        """Get data for multiple honors boards with rate limiting"""
        boards_data = []
        for board_id in board_ids:
            try:
                data = self.get_board_data(board_id)
                boards_data.append({ 'board_id': board_id, **data })
                # Rate limiting to prevent IP blocking
                self.page.wait_for_timeout(1000)  # 1 second delay between requests
            except Exception as e:
                print(f"Error fetching board {board_id}: {e}")
                boards_data.append({ 'board_id': board_id, 'error': str(e) })
        return boards_data

    def get_available_boards(self):
        """Discover all available honors boards from boardcomps.php"""
        print(f"Discovering available boards from {self.club_url}/boardcomps.php...")
        self.page.goto(f"{self.club_url.rstrip('/')}/boardcomps.php")
        self.page.wait_for_timeout(2000)
        
        boards = self.page.evaluate("""
            () => {
                const results = [];
                // Look for links like boardcomps.php?board=XX
                const links = document.querySelectorAll('a[href*="board="]');
                
                links.forEach(link => {
                    const href = link.getAttribute('href');
                    const match = href.match(/board=(\\d+)/);
                    if (match) {
                        const id = match[1];
                        const title = link.textContent.trim();
                        // Only add if we have a title and it's not a common nav link
                        if (title && title.length > 2 && !results.some(b => b.id === id)) {
                            results.push({ id, title });
                        }
                    }
                });
                
                return results;
            }
        """)
        
        print(f"Found {len(boards)} available boards.")
        return boards
    
    def save_boards_cache(self, boards_data, filename="honors_boards_cache.json"):
        """Save boards data to local JSON cache"""
        import json
        try:
            with open(filename, 'w') as f:
                json.dump(boards_data, f, indent=2)
            print(f"Boards data cached to {filename}")
        except Exception as e:
            print(f"Failed to save cache: {e}")
    
    def load_boards_cache(self, filename="honors_boards_cache.json"):
        """Load boards data from local JSON cache"""
        import json
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Failed to load cache: {e}")
            return None
    
    def run_honors_boards(self, board_ids, force_refresh=False, cache_file="honors_boards_cache.json"):
        """Run honors board scraping with caching"""
        if not force_refresh:
            cached_data = self.load_boards_cache(cache_file)
            if cached_data:
                print("Loaded honors boards from cache.")
                return cached_data
        
        with sync_playwright() as p:
            self.browser = p.chromium.launch(headless=True)
            self.page = self.browser.new_page()
            
            try:
                if not self.login():
                    return None
                
                boards_data = self.get_honors_boards(board_ids)
                self.save_boards_cache(boards_data, cache_file)
                return boards_data
                
            finally:
                self.browser.close()

    def run_discovery(self, cache_file="available_boards.json"):
        """Run the discovery process and save to cache"""
        with sync_playwright() as p:
            self.browser = p.chromium.launch(headless=True)
            self.page = self.browser.new_page()
            
            try:
                if not self.login():
                    return None
                
                boards = self.get_available_boards()
                
                if boards:
                    with open(cache_file, 'w') as f:
                        json.dump(boards, f, indent=2)
                    print(f"Discovered boards saved to {cache_file}")
                
                return boards
                
            finally:
                self.browser.close()
    
    def run(self, competition_id=None, export_files=False, force_refresh=False):
        """Main execution method. Set export_files=True to output CSV and JSON files."""
        # Check database cache first if competition_id is provided
        if competition_id and not force_refresh:
            try:
                if local_cache:
                    cached_scorecards, cached_team_scores = local_cache.get_competition_data(competition_id)
                    if cached_scorecards and cached_team_scores:
                        print(f"Loaded competition {competition_id} from local database.")
                        return cached_scorecards
                else:
                    print("local_cache module not found, skipping cache check.")
            except Exception as e:
                print(f"Cache check failed: {e}")

        with sync_playwright() as p:
            # Launch browser
            self.browser = p.chromium.launch(headless=True)  # Set to True for headless
            self.page = self.browser.new_page()
            
            try:
                # Login
                self.login()
                
                if competition_id:
                    # Get specific competition scorecards
                    print(f"\n--- Fetching Competition {competition_id} ---")
                    scorecards, comp_date = self.get_all_scorecards(competition_id)

                    if scorecards is None:
                        print("No scorecards retrieved")
                        return None

                    # Calculate team scores
                    team_scores = self.calculate_team_scores(scorecards)

                    # Save to Database
                    try:
                        if local_cache:
                            local_cache.save_competition_data(competition_id, self.club_url, scorecards, team_scores, comp_date=comp_date)
                            print(f"Competition {competition_id} ({comp_date}) saved to database.")
                        else:
                            print("local_cache module not found, skipping database save.")
                    except Exception as e:
                        print(f"Failed to save to database: {e}")

                    if export_files:
                        # Save to JSON
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        json_filename = f"scorecards_{competition_id}_{timestamp}.json"

                        with open(json_filename, 'w') as f:
                            json.dump(scorecards, f, indent=2)
                        print(f"Scorecards saved to {json_filename}")

                        # Export to CSV
                        csv_filename = f"scorecards_{competition_id}_{timestamp}.csv"
                        self.export_to_csv(scorecards, csv_filename)

                        # Export team scores to CSV
                        team_csv_filename = f"team_scores_{competition_id}_{timestamp}.csv"
                        self.export_team_scores(team_scores, team_csv_filename)

                    # Print summary
                    print("\n=== PLAYER SUMMARY ===")
                    for card in scorecards:
                        print(f"{card['position']} - {card['name']} ({card['handicap']}) - Team {card.get('team_id', 'N/A')} - {card['totalPoints']} pts - Total: {card['total']}")

                    # Print team summary
                    if team_scores:
                        print("\n=== TEAM SUMMARY ===")
                        for team in team_scores:
                            print(f"Team {team['team_id']} - Total: {team['total_points']} pts")
                            for player in team['players']:
                                print(f"  - {player['name']} ({player['handicap']}) - {player['points']} pts")
                    else:
                        print("\n=== TEAM SUMMARY ===")
                        print("No team data available")

                    return scorecards
                    
                else:
                    # Get recent competitions
                    competitions = self.get_recent_competitions()
                    
                    # Get details for each competition
                    all_results = []
                    for i, comp in enumerate(competitions[:5]):  # Limit to 5 most recent
                        print(f"\n--- Processing {comp['name']} ---")
                        results = self.get_competition_results(comp['url'])
                        results['url'] = comp['url']
                        all_results.append(results)
                    
                    # Save to file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"golf_results_{timestamp}.json"
                    
                    with open(filename, 'w') as f:
                        json.dump(all_results, f, indent=2)
                    
                    print(f"\nResults saved to {filename}")
                    
                    # Print summary
                    print("\n=== SUMMARY ===")
                    for result in all_results:
                        print(f"\n{result['competition']}")
                        print(f"Date: {result['date']}")
                        if result['results']:
                            winner = result['results'][0]
                            print(f"Winner: {winner['player']} - {winner['points']} points")
                
            finally:
                self.browser.close()

# Example usage
if __name__ == "__main__":
    # Configuration - load from environment variables
    import os
    CLUB_URL = os.getenv("CLUB_URL")
    USERNAME = os.getenv("USERNAME")
    PIN = os.getenv("PIN")

    if not all([CLUB_URL, USERNAME, PIN]):
        print("Error: Missing environment variables. Please set CLUB_URL, USERNAME, and PIN in your .env file.")
        exit(1)

    # Create scraper
    scraper = IntelligentGolfScraper(CLUB_URL, USERNAME, PIN)

    # Option 1: Get all recent competitions
    # scraper.run()

    # Option 2: Get detailed scorecards for specific competition
    COMPETITION_ID = "9072"  # MidWeek Roll Up from Oct 29th
    scraper.run(competition_id=COMPETITION_ID, export_files=False)
