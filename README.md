# 🏆 FFGC Honors Board Manager

A streamlined management application for the **Felixstowe Ferry Golf Club** honors board scraping and display image generation. This tool automates the process of fetching winner data from Intelligent Golf and creating high-quality display images for the club foyer.

---

## 🚀 Features

- **Dynamic Board Management**: Add, view, or remove Board IDs through an interactive sidebar.
- **Automated Scraping**: Fetches titles, winner lists, and entry counts using `Playwright`.
- **Title Personalization**: Edit board titles directly in the UI to ensure the display board looks exactly how you want.
- **Selective Generation**: Choose specific boards to generate images for via an interactive checkbox table.
- **Integrated Credentials**: Enter your User ID and PIN securely in the app; credentials can also be autopopulated from a `.env` file.
- **Secure Handling**:
  - **In-Memory ZIP**: Download all generated images in a single ZIP file without storing the archive on disk.
  - **Auto-Cleanup**: Temporary images are wiped on app startup and can be cleared manually via the **"Exit & Cleanup"** button.

---

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/philflav/Honors_Board_Manager.git
   cd Honors_Board_Manager
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```

4. **Configuration (Optional)**:
   Create a `.env` file in the root directory for default credentials:
   ```env
   CLUB_URL=https://felixstowe.intelligentgolf.co.uk
   USERNAME=your_id
   PIN=your_pin
   ```

---

## 🐳 Docker Deployment

### Using Docker Compose (Recommended for local)
The project includes a `docker-compose.yaml` for easy orchestration:

1. **Build and Start**:
   ```bash
   docker compose up -d --build
   ```
2. **Access**: Open your browser at `http://localhost:8501`.
3. **Persistance**: Your `honors_boards_cache.json` and `req_boards.json` are mounted as volumes to ensure your board IDs and custom titles are saved even if the container is restarted.

### Using Docker Directly
```bash
docker build -t honors-board-manager .
docker run -p 8501:8501 --env-file .env honors-board-manager
```

---

## 📁 Project Structure

- `app.py`: Main Streamlit dashboard and UI.
- `honors_scraper.py`: Scraper entry point (targets `req_boards.json`).
- `ig_scraper.py`: Core scraping engine using Playwright.
- `generate_boards.py`: Logic for creating display images from cached data.
- `req_boards.json`: Persistent storage for your targeted board IDs.
- `honors_boards_cache.json`: Local cache of scraped honors board data.

---

## 🔒 Privacy & Data
This application is designed to keep your data clean. It does not store images permanently and offers manual cleanup to ensure no sensitive or heavy media remains on your machine after the session is closed.
