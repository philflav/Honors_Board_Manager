# 🏆 FFGC Honors Board Manager

A streamlined management application for the **Felixstowe Ferry Golf Club** honors board scraping and display image generation. 

## 🎯 Purpose
This tool automates the tedious process of updating physical or digital honors boards. It directly logs into the Intelligent Golf portal, scrapes the latest winner histories across multiple competitions, and dynamically generates highly crafted, multi-column presentation images. These perfectly formatted images are then ready to be displayed in the club foyer or on the club website.

---

## 🚀 Key Features

- **Automated Board Discovery**: Automatically scrapes the club portal to find and list all available honors boards—no manual ID hunting required.
- **Interactive Master-Detail UI**: 
  - A clean data table to overview your boards.
  - A dedicated "Configuration Pane" (accessed via the ⚙️ icon) that loads seamlessly without resetting your scroll position.
- **Independent Board Formatting**:
  - **Dynamic Layouts**: Choose from 1, 2, 3, or 4 columns per board.
  - **"Best Fit" Mode**: Let the system automatically calculate the optimal number of columns based on how many winners a board has.
  - **Smart Fill Strategies**: Choose **Progressive** (fills column 1 first, then 2...) or **Balanced** (spreads winners evenly across all columns).
  - **Safe Truncation**: Ensures your board never overflows. If capacities are exceeded, the oldest entries are safely truncated while prioritizing the most recent winners.
- **Dual-Image Generation**: Automatically generates high-fidelity raw PNGs and optimized 8-bit quantized images for varying digital display formats.

---

## 📖 Operation / How to Use

### 1. Setup & Authenticate
1. Open the app in your browser (default: `http://localhost:8501`).
2. Look at the left **Sidebar**.
3. Under **🔐 Credentials**, enter your Intelligent Golf **User ID** and **PIN**.

### 2. Discover Boards
* If the main table is empty, click **'🔄 Refresh Available Boards'** in the sidebar. This tells the scraper to log in and index every single honors board available for the club.

### 3. Scraping Data
* Check the **Scrape** box next to any board you want to update.
* Click **'🔍 Scrape Selected'**. The system will download all the historical winners for those loaded boards and cache them safely.
* *Note: A board's status will change from "⏳ Not Scraped" to "✅ Scraped" when data is ready.*

### 4. Configuration & Formatting
* Click the gear icon (**⚙️**) in the "Edit" column for any board.
* The **Configuration Pane** will slide open on the right side of the screen.
* Here, you can:
  * **Rename the Title** of the board.
  * Adjust the **Number of Columns** (or rely on the recommended Best Fit).
  * Change the **Fill Method** (Progressive vs Balanced).

### 5. Generating Images
* Check the **Gen** box next to boards you're ready to export.
* Click **'🎨 Generate Selected'**. 
* Once finished, a popup will appear allowing you to download all files neatly packaged into a single `.zip` folder.

> **Pro Tip**: Use the **'🔥 Scrape & Generate ALL Selected'** button above the table to run the entire end-to-end pipeline in one click.

---

## 🛠️ Installation & Deployment

### Run inside Docker (Recommended)
This application utilizes Playwright, which requires specific system-level browser binaries. Docker is the absolute easiest way to ensure this runs perfectly on any machine.

1. Ensure [Docker Desktop](https://www.docker.com/products/docker-desktop/) is installed and running.
2. In the project folder, build and spin up the container:
   ```bash
   docker compose up -d --build
   ```
3. Open your browser to: `http://localhost:8501`

*(Your configuration choices are mounted to local volumes (`req_boards.json`), so you won't lose your custom setups when the container stops).*

### Run Locally (For Development)
If you prefer running natively using Python 3.10+:

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```
3. **Run Streamlit**:
   ```bash
   streamlit run app.py
   ```

*(You can also place default credentials in a `.env` file to avoid typing your PIN every time).*

---

## 🚑 Troubleshooting

### Docker 500 Internal Server Error
If you run `docker compose up -d --build` and receive an error like:
`request returned 500 Internal Server Error for API route... dockerDesktopLinuxEngine`

* **Cause**: Docker Desktop's engine service has hung in the background (common on Windows/WSL).
* **Fix**: 
  1. Fully quit Docker Desktop from your system tray.
  2. Open PowerShell and type: `wsl --shutdown`
  3. Restart Docker Desktop and wait for the engine to initialize before retrying the command.

### "Scraping Failed"
* Double check that your User ID and PIN are correct natively on Intelligent Golf.
* Ensure the club URL is correctly configured (the default assumes Felixstowe).
