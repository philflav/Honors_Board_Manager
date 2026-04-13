import streamlit as st
import json
import os
import subprocess
import pandas as pd
import io
import zipfile
import shutil
import sys
from datetime import datetime

# Configuration
REQ_BOARDS_FILE = "req_boards.json"
CACHE_FILE = "honors_boards_cache.json"
SCRAPER_SCRIPT = "honors_scraper.py"

# Page config
st.set_page_config(page_title="FFGC Honors Board Manager", page_icon="🏆", layout="wide")

# --- Cleanup Automation ---

def cleanup_images():
    """Wipes all files from the automated_images folder."""
    folder = "automated_images"
    if os.path.exists(folder):
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

# Call cleanup on the first run of the app in this session
if "cleanup_done" not in st.session_state:
    cleanup_images()
    st.session_state.cleanup_done = True

def get_images_zip():
    """Generates an in-memory ZIP file of all images in automated_images/."""
    folder = "automated_images"
    buf = io.BytesIO()
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    files = os.listdir(folder)
    if not files:
        return None
        
    with zipfile.ZipFile(buf, "w") as zf:
        for filename in files:
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path):
                zf.write(file_path, filename)
    buf.seek(0)
    return buf

@st.cache_resource
def install_playwright_binaries():
    """Ensures Playwright browser binaries are installed on Streamlit Cloud."""
    try:
        # Check if we are running in a cloud-like environment (check for /mount/src or similar)
        # Or just run it once to be safe - it's fast if already installed
        st.info("🌐 Checking for browser binaries...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        # Note: --with-deps usually needs sudo, but Streamlit Cloud environment 
        # often requires certain packages in packages.txt if it fails here.
    except Exception as e:
        st.error(f"Error ensuring browser binaries: {e}")
        return False
    return True

# Trigger binary install
install_playwright_binaries()

def load_board_ids():
    """Loads the list of board IDs from the JSON file."""
    if os.path.exists(REQ_BOARDS_FILE):
        try:
            with open(REQ_BOARDS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def load_available_boards():
    """Loads the list of discovered boards from available_boards.json."""
    if os.path.exists("available_boards.json"):
        try:
            with open("available_boards.json", "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

def save_board_ids(board_ids):
    """Saves the list of board IDs to the JSON file."""
    try:
        with open(REQ_BOARDS_FILE, "w") as f:
            json.dump(sorted(list(set(board_ids))), f, indent=4)
        return True
    except IOError:
        return False

def run_scraper():
    """Executes the honors_scraper.py script."""
    try:
        st.info(f"🚀 Triggering {SCRAPER_SCRIPT}...")
        # Run script as subprocess to see output
        process = subprocess.Popen(
            ["python", SCRAPER_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Stream the output to the UI
        log_area = st.empty()
        full_log = ""
        
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                full_log += line
                log_area.code(full_log)
        
        returncode = process.wait()
        return returncode == 0
    except Exception as e:
        st.error(f"Error: {e}")

@st.dialog("📦 Download Images")
def download_popup():
    """Shows a modal dialog for downloading the ZIP of images."""
    st.write("Your honors board images have been generated successfully!")
    
    zip_data = get_images_zip()
    if zip_data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="💾 Download ZIP of Images",
            data=zip_data,
            file_name=f"honors_boards_{timestamp}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True
        )
        st.write("---")
        if st.button("Cleanup & Close", use_container_width=True):
            cleanup_images()
            st.rerun()
    else:
        st.warning("No images were found in the output folder. Perhaps generation was skipped for all boards?")

@st.dialog("📖 User Guide")
def show_user_guide():
    """Shows the user guide in a modal dialog."""
    st.markdown("""
    1.  **Welcome**: You can see all available honors boards in the table below.
    2.  **Credentials**: Ensure your **User ID** and **PIN** are entered in the sidebar.
    3.  **Discovery**: If the table is empty, click **'🔄 Refresh Available Boards'** in the sidebar.
    4.  **Selection**: Check the **'Select'** box for any boards you want to process.
    5.  **Scraping**: Click **'🔍 Scrape Selected'** to fetch the latest data for your checks.
    6.  **Generation**: Click **'🎨 Generate Selected'** to create images forboards marked **'✅ Scraped'**.
    7.  **Automation**: Use **'🔥 Scrape & Generate ALL Selected'** above the table to fully automate both steps for your selection.
    8.  **Downloading**: A popup will appear automatically once your images are ready.
    9.  **Cleanup**: Click **'🚪 Exit & Cleanup'** when finished to clear temporary image files.
    """)
    if st.button("Close", use_container_width=True):
        st.rerun()

def trigger_image_generation(ids, num_columns=1):
    """Runs generate_boards.py for specific IDs."""
    try:
        # Clear existing images first to prevent accumulation
        cleanup_images()
        
        with st.spinner(f"🎨 Generating {len(ids)} board images ({num_columns} col)..."):
            cmd = [sys.executable, "generate_boards.py", "--columns", str(num_columns)] + [str(i) for i in ids]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                st.success("✅ Image generation complete!")
                # Automatically open the download popup
                download_popup()
            else:
                st.error("❌ Image generation failed.")
                with st.expander("View Logs"):
                    st.code(result.stdout)
                    st.code(result.stderr)
    except Exception as e:
        st.error(f"Error: {e}")

def show_cache_stats(username_input=None, pin_input=None):
    """Displays statistics and handles board selection, scraping, and generation."""
    selected_ids = load_board_ids()
    data = []
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            st.error("Error reading cache file.")
    
    available_boards_data = load_available_boards()
    if not available_boards_data:
        st.info("👋 Welcome! Please click **'🔄 Refresh Available Boards'** in the sidebar to discover boards from the club portal.")
        return

    # Create combined list of boards
    all_available_ids = sorted([int(b['id']) for b in available_boards_data])
    
    # Initialize session state for selection if not present
    if "selected_ids" not in st.session_state:
        st.session_state.selected_ids = selected_ids

    stats = []
    boards_map = {int(b['id']): b['title'] for b in available_boards_data}

    for bid in all_available_ids:
        board_cache = next((b for b in data if b["board_id"] == bid), None)
        status = "✅ Scraped" if board_cache else "⏳ Not Scraped"
        title = board_cache.get("title") if board_cache else boards_map.get(bid, f"Board {bid}")
        winners_count = len(board_cache.get("winners", [])) if board_cache else 0
        
        stats.append({
            "Select": bid in st.session_state.selected_ids,
            "Board ID": bid,
            "Title": title,
            "Winners": winners_count,
            "Status": status
        })
    
    df = pd.DataFrame(stats)
    
    st.subheader("📊 Honors Board Management")
    
    # Action Row
    col_scrape, col_gen, col_all, col_none, _ = st.columns([1.5, 2, 1, 1, 2], vertical_alignment="bottom")
    
    # Sync selection back to file when modified
    def sync_selection(ids):
        save_board_ids(ids)

    # Process Selection Changes BEFORE buttons
    # We use the data_editor later, but we need the current selection for buttons
    
    if col_all.button("✅ Select All", use_container_width=True):
        st.session_state.selected_ids = all_available_ids
        sync_selection(all_available_ids)
        st.rerun()
    if col_none.button("❌ Clear", use_container_width=True):
        st.session_state.selected_ids = []
        sync_selection([])
        st.rerun()

    # Scrape Button
    if col_scrape.button("🔍 Scrape Selected", type="secondary", use_container_width=True):
        current_selected = st.session_state.selected_ids
        if not current_selected:
            st.warning("Select boards to scrape first.")
        elif not username_input or not pin_input:
            st.error("Provide User ID and PIN in the sidebar.")
        else:
            env = os.environ.copy()
            env["USERNAME"] = username_input
            env["PIN"] = pin_input
            
            with st.spinner(f"⏳ Scraping {len(current_selected)} boards..."):
                # Run honors_scraper.py with IDs as arguments
                cmd = [sys.executable, SCRAPER_SCRIPT] + [str(i) for i in current_selected]
                process = subprocess.run(cmd, env=env, capture_output=True, text=True)
                
                if process.returncode == 0:
                    st.success("✅ Scraping complete!")
                    st.rerun()
                else:
                    st.error("❌ Scraping failed.")
                    with st.expander("Show Error Logs"):
                        st.code(process.stdout + "\n" + process.stderr)

    # Generation Button
    if col_gen.button("🎨 Generate Selected", type="primary", use_container_width=True):
        current_selected = st.session_state.selected_ids
        # Only boards that are scraped can be generated
        scraped_selected = [bid for bid in current_selected if any(b["board_id"] == bid for b in data)]
        
        if not scraped_selected:
            st.warning("Select at least one scraped board (Status: ✅).")
        else:
            trigger_image_generation(scraped_selected, st.session_state.num_columns)
    
    # Show interactive table using data_editor
    edited_df = st.data_editor(
        df,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", default=False),
            "Board ID": st.column_config.NumberColumn(format="%d"),
            "Status": st.column_config.TextColumn("Status"),
        },
        disabled=["Board ID", "Winners", "Status"],
        hide_index=True,
        key="board_selector"
    )

    # Update session state and save to file if selection changed
    new_selection = edited_df[edited_df["Select"]]["Board ID"].tolist()
    if set(new_selection) != set(st.session_state.selected_ids):
        st.session_state.selected_ids = new_selection
        sync_selection(new_selection)

    # Save title changes back to the cache file
    title_changed = False
    for _, row in edited_df.iterrows():
        bid = row["Board ID"]
        new_title = row["Title"]
        for board in data:
            if board["board_id"] == bid and board["title"] != new_title:
                board["title"] = new_title
                title_changed = True
    
    if title_changed:
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f, indent=2)
            st.toast("✅ Titles updated!")
        except IOError as e:
            st.error(f"Failed to save titles: {e}")

# --- UI Layout ---

st.title("🏆 FFGC Honors Board Management")
st.markdown("---")

# Load current state and environment
current_ids = load_board_ids()
from dotenv import load_dotenv
load_dotenv()

# --- Sidebar Controls ---

# Exit Button (Top of sidebar for visibility)
if st.sidebar.button("🚪 Exit & Cleanup", use_container_width=True, type="secondary", help="Deletes all generated images and stops the app session."):
    cleanup_images()
    st.sidebar.success("Folder cleared. You may now close this tab.")
    st.stop()

st.sidebar.markdown("---")
st.sidebar.header("🔐 Credentials")
c1, c2 = st.sidebar.columns(2)
username_input = c1.text_input("User ID", value=os.getenv("USERNAME", ""), help="Your Intelligent Golf username")
pin_input = c2.text_input("PIN", value=os.getenv("PIN", ""), type="password", help="Your Intelligent Golf PIN")

st.sidebar.markdown("---")
st.sidebar.header("📊 Layout Settings")
num_columns = st.sidebar.radio(
    "Number of Columns",
    options=[1, 2, 3, 4],
    index=0,
    horizontal=True,
    help="Select how many columns the honors board should have.",
    key="num_columns"
)

st.sidebar.markdown("---")

if st.sidebar.button("📖 Open User Guide", use_container_width=True):
    show_user_guide()

# Refresh button
if st.sidebar.button("🔄 Refresh Available Boards", use_container_width=True, help="Scrapes the portal to find all existing honors boards."):
    if not username_input or not pin_input:
        st.sidebar.error("Provide User ID and PIN first.")
    else:
        with st.spinner("Discovering boards..."):
            env = os.environ.copy()
            env["USERNAME"] = username_input
            env["PIN"] = pin_input
            process = subprocess.run([sys.executable, "fetch_available_boards.py"], env=env, capture_output=True, text=True)
            if process.returncode == 0:
                st.sidebar.success("Updated board list!")
                st.rerun()
            else:
                st.sidebar.error("Failed to refresh.")
                with st.expander("Show Discovery Logs"):
                    st.code(process.stdout + "\n" + process.stderr)

# Main Control Panel
st.subheader("⚙️ Global Actions")
st.write(f"You have **{len(st.session_state.get('selected_ids', []))}** boards currently selected in the table below.")

if st.button("🔥 Scrape & Generate ALL Selected", type="primary", help="Scrapes and generates images for all currently selected boards in one go.", use_container_width=True):
    selected = st.session_state.get('selected_ids', [])
    if not selected:
        st.warning("Please select at least one board in the table first.")
    elif not username_input or not pin_input:
        st.error("Please provide both User ID and PIN in the sidebar.")
    else:
        # First Scrape
        env = os.environ.copy()
        env["USERNAME"] = username_input
        env["PIN"] = pin_input
        with st.spinner("⏳ Running full process for selected boards... This may take a minute."):
            cmd = [sys.executable, SCRAPER_SCRIPT] + [str(i) for i in selected]
            res = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if res.returncode == 0:
                # Then Generate
                trigger_image_generation(selected, st.session_state.num_columns)
            else:
                st.error("❌ Process failed during scraping.")
                with st.expander("Show Error Logs"):
                    st.code(res.stdout + "\n" + res.stderr)

st.markdown("---")

# Image Generation Section
show_cache_stats(username_input, pin_input)

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
