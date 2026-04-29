import streamlit as st
import json
import os
import subprocess
import pandas as pd
import io
import zipfile
import shutil
import sys
import math
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

def get_board_capacities():
    """Calculates total capacity for each column count from board_configs.json."""
    if not os.path.exists("board_configs.json"):
        return {1: 16, 2: 36, 3: 44, 4: 58} # Fallback defaults
    
    try:
        with open("board_configs.json", "r") as f:
            configs = json.load(f)
        
        caps = {}
        for col_str, config in configs.items():
            cols = int(col_str)
            max_rows = config["max_rows"]
            total = 0
            for i in range(cols):
                if cols >= 3 and 0 < i < cols - 1:
                    total += (max_rows - 1)
                else:
                    total += max_rows
            caps[cols] = total
        return caps
    except Exception:
        return {1: 16, 2: 36, 3: 44, 4: 58}

def calculate_best_fit(winners_count, caps):
    """Suggests the best column count for a given number of winners."""
    for cols in sorted(caps.keys()):
        if winners_count <= caps[cols]:
            return cols
    return max(caps.keys()) if caps else 1

def load_board_configs():
    """Loads the per-board configurations from req_boards.json."""
    if os.path.exists(REQ_BOARDS_FILE):
        try:
            with open(REQ_BOARDS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    # Migration: convert old list format to new dict format
                    return {str(bid): {"columns": "1", "fill": "Progressive"} for bid in data}
                return data
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_board_configs(configs):
    """Saves the per-board configurations to req_boards.json."""
    try:
        with open(REQ_BOARDS_FILE, "w") as f:
            json.dump(configs, f, indent=4)
        return True
    except IOError:
        return False

def load_available_boards():
    """Loads the list of discovered boards from available_boards.json."""
    if os.path.exists("available_boards.json"):
        try:
            with open("available_boards.json", "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []

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
    
    folder = "automated_images"
    image_files = []
    if os.path.exists(folder):
        # Filter out the 8-bit quantized versions for the preview count
        image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg')) and "_8bit" not in f]
    
    # Show a preview and selectbox if images are generated
    if len(image_files) > 0:
        if len(image_files) == 1:
            selected_image = image_files[0]
        else:
            selected_image = st.selectbox("Select board to preview:", sorted(image_files))
            
        img_path = os.path.join(folder, selected_image)
        st.image(img_path, caption=f"Preview: {selected_image}", use_container_width=True)
        
        # Also provide a direct download for the selected image
        with open(img_path, "rb") as f:
            st.download_button(
                label=f"💾 Download {selected_image}",
                data=f,
                file_name=selected_image,
                mime="image/png",
                type="secondary" if len(image_files) > 1 else "primary",
                use_container_width=True
            )
        st.write("---")
        if len(image_files) > 1:
            st.caption("Download all generated images as a ZIP archive below:")
        else:
            st.caption("Or download as a ZIP archive below:")

    zip_data = get_images_zip()
    if zip_data:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            label="💾 Download ZIP of Images",
            data=zip_data,
            file_name=f"honors_boards_{timestamp}.zip",
            mime="application/zip",
            type="secondary" if len(image_files) == 1 else "primary",
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
    4.  **Filtering**: Use the search bar above the table to filter boards by ID or Title.
    5.  **Selection**: Check the **'Gen'** or **'Scrape'** boxes for any boards you want to process.
    6.  **Configuration**: Click the gear icon (**⚙️**) in the table to edit a board's title, adjust columns, or change the fill method. Note that using multiple single-column boards is optimal when there are a lot of winners. For the fill method, **Progressive** fills column by column sequentially, while **Balanced** attempts to distribute names evenly across all columns.
    7.  **Scraping**: Click **'🔍 Scrape Selected'** to fetch the latest data for your checks.
    8.  **Generation**: Click **'🎨 Generate Selected'** to create images for boards marked **'✅ Scraped'**.
    9.  **Automation**: Use **'🔥 Scrape & Generate ALL Selected'** above the table to fully automate both steps for your selection.
    10. **Downloading**: A popup will appear automatically once your images are ready.
    11. **Cleanup**: Click **'🚪 Exit & Cleanup'** when finished to clear temporary image files.
    """)
    if st.button("Close", use_container_width=True):
        st.rerun()

def trigger_image_generation(ids, board_configs):
    """Runs generate_boards.py for specific IDs using per-board configs."""
    try:
        # Clear existing images first to prevent accumulation
        cleanup_images()
        
        # Prepare the config JSON for the CLI
        # Only include selected IDs in the config sent to CLI
        active_configs = {str(bid): board_configs[str(bid)] for bid in ids if str(bid) in board_configs}
        config_json = json.dumps(active_configs)
        
        with st.spinner(f"🎨 Generating {len(ids)} board images..."):
            cmd = [sys.executable, "generate_boards.py", "--config", config_json] + [str(i) for i in ids]
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

@st.fragment
def render_management_panel(data, available_boards_data, caps, username_input, pin_input):
    """Encapsulates the interactive section to prevent full-page resets."""
    board_configs = load_board_configs()
    all_available_ids = sorted([int(b['id']) for b in available_boards_data])
    boards_map = {int(b['id']): b['title'] for b in available_boards_data}
    
    # Initialize session state for selection if not present
    if "selected_ids" not in st.session_state:
        st.session_state.selected_ids = list(board_configs.keys())
    if "scrape_ids" not in st.session_state:
        st.session_state.scrape_ids = []
    if "edit_focus" not in st.session_state:
        st.session_state.edit_focus = None

    stats = []
    for bid in all_available_ids:
        bid_str = str(bid)
        board_cache = next((b for b in data if b["board_id"] == bid), None)
        status = "✅ Scraped" if board_cache else "⏳ Not Scraped"
        title = board_cache.get("title") if board_cache else boards_map.get(bid, f"Board {bid}")
        winners_count = len(board_cache.get("winners", [])) if board_cache else 0
        
        config = board_configs.get(bid_str, {})
        selected_cols = config.get("columns", "1")
        
        if selected_cols == "Best Fit":
            eff_cols = calculate_best_fit(winners_count, caps)
        else:
            eff_cols = int(selected_cols)
            
        capacity = caps.get(eff_cols, 1)
        if capacity == 0:
            capacity = 1
        
        boards_req = math.ceil(winners_count / capacity)
        if boards_req == 0:
            boards_req = 1
        
        stats.append({
            "Scrape": bid_str in st.session_state.scrape_ids,
            "Edit": st.session_state.edit_focus == bid_str,
            "Gen": bid_str in st.session_state.selected_ids,
            "Board ID": bid,
            "Title": title,
            "Winners": winners_count,
            "Boards": boards_req,
            "Status": status
        })
    
    df = pd.DataFrame(stats)
    
    main_col, side_col = st.columns([2.3, 1], gap="large")

    with main_col:
        # Action Row with even button sizes
        col_scrape, col_gen, col_all, col_none, _ = st.columns([1, 1, 1, 1, 1], vertical_alignment="bottom")
        
        if col_all.button("✅ All (Gen)", use_container_width=True, help="Select all boards for generation"):
            st.session_state.selected_ids = [str(bid) for bid in all_available_ids]
            # Ensure they have a config
            for bid in st.session_state.selected_ids:
                if bid not in board_configs:
                    board_configs[bid] = {"columns": "1", "fill": "Progressive"}
            save_board_configs(board_configs)


        if col_none.button("❌ Clear (Gen)", use_container_width=True, help="Unselect all boards for generation"):
            st.session_state.selected_ids = []


        if col_scrape.button("🔍 Scrape Selected", type="secondary", use_container_width=True, help="Scrapes checked boards"):
            current_selected = st.session_state.scrape_ids
            if not current_selected:
                st.warning("Select boards to scrape first.")
            elif not username_input or not pin_input:
                st.error("Provide User ID and PIN in the sidebar.")
            else:
                env = os.environ.copy()
                env["USERNAME"] = username_input
                env["PIN"] = pin_input
                with st.spinner(f"⏳ Scraping {len(current_selected)} boards..."):
                    cmd = [sys.executable, SCRAPER_SCRIPT] + [str(i) for i in current_selected]
                    process = subprocess.run(cmd, env=env, capture_output=True, text=True)
                    if process.returncode == 0:
                        st.success("✅ Scraping complete!")
                        st.rerun(scope="app") 
                    else:
                        st.error("❌ Scraping failed.")

        if col_gen.button("🎨 Generate Selected", type="primary", use_container_width=True):
            current_selected = st.session_state.selected_ids
            scraped_selected = [bid for bid in current_selected if any(str(b["board_id"]) == bid for b in data)]
            if not scraped_selected:
                st.warning("Select at least one scraped board.")
            else:
                final_configs = {}
                for bid in scraped_selected:
                    config = board_configs.get(bid, {"columns": "1", "fill": "Progressive"})
                    cols = config["columns"]
                    if cols == "Best Fit":
                        board_cache = next((b for b in data if str(b["board_id"]) == bid), None)
                        w_count = len(board_cache["winners"]) if board_cache else 0
                        cols = calculate_best_fit(w_count, caps)
                    final_configs[bid] = {"columns": cols, "fill": config.get("fill", "Progressive").lower()}
                trigger_image_generation(scraped_selected, final_configs)

        # --- Filter Logic ---
        filter_text = st.text_input("🔍 Filter Boards", value="", placeholder="Search by ID or Title...", help="Type to narrow down the list").lower()
        
        if filter_text:
            display_df = df[
                df["Board ID"].astype(str).str.contains(filter_text) | 
                df["Title"].str.lower().str.contains(filter_text)
            ]
        else:
            display_df = df

        # Show interactive table
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Scrape": st.column_config.CheckboxColumn("Scrape", help="Select for scraping", width="small"),
                "Edit": st.column_config.CheckboxColumn("⚙️", help="Click to configure", width="small"),
                "Gen": st.column_config.CheckboxColumn("Gen", help="Select for generation", width="small"),
                "Board ID": st.column_config.NumberColumn(format="%d"),
                "Boards": st.column_config.NumberColumn("Boards", width="small", help="Number of boards required based on template and winners"),
                "Status": st.column_config.TextColumn("Status"),
            },
            disabled=["Board ID", "Winners", "Status", "Boards"],
            hide_index=True,
            key="board_selector",
            use_container_width=True
        )

    # RIGHT COLUMN: Configuration Pane
    with side_col:
        focused_bid = None
        for _, row in edited_df.iterrows():
            if row["Edit"]:
                focused_bid = str(row["Board ID"])
                st.session_state.edit_focus = focused_bid
                break
        
        if not focused_bid:
             st.session_state.edit_focus = None

        if st.session_state.edit_focus:
            bid = st.session_state.edit_focus
            board_cache = next((b for b in data if str(b["board_id"]) == bid), None)
            config = board_configs.get(bid, {"columns": "1", "fill": "Progressive"})
            
            st.markdown(f"### ⚙️ Board Settings: {bid}")
            title_input = st.text_input("Board Title", value=board_cache.get("title", f"Board {bid}") if board_cache else boards_map.get(int(bid)), key=f"title_{bid}")
            
            w_count = len(board_cache["winners"]) if board_cache else 0
            st.info(f"**Winners:** {w_count}  \n**Recommended Layout:** Multiple single column boards")
            
            current_fmt = str(config.get("columns", "1"))
            if current_fmt == "Best Fit":
                current_fmt = "1"
            new_fmt = st.selectbox("Columns", options=["1", "2", "3", "4"], index=["1", "2", "3", "4"].index(current_fmt), key=f"fmt_{bid}")
            new_fill = st.selectbox("Fill Method", options=["Progressive", "Balanced"], index=["Progressive", "Balanced"].index(config.get("fill", "Progressive")), key=f"fill_{bid}")
            
            if new_fmt != str(config.get("columns")) or new_fill != config.get("fill") or (board_cache and title_input != board_cache["title"]):
                board_configs[bid] = {"columns": new_fmt, "fill": new_fill}
                save_board_configs(board_configs)
                if board_cache and title_input != board_cache["title"]:
                    board_cache["title"] = title_input
                    with open(CACHE_FILE, "w") as f:
                        json.dump(data, f, indent=2)
                st.rerun(scope="fragment") 
        else:
            st.markdown("### ⚙️ Board Settings")
            st.info("👈 Click the gear icon (**⚙️**) in the table to configure a board.")
 
    # Update selection logic (merging filtered edits with full session state)
    visible_ids = display_df["Board ID"].astype(str).tolist()
    current_gen_visible = edited_df[edited_df["Gen"]]["Board ID"].astype(str).tolist()
    current_scrape_visible = edited_df[edited_df["Scrape"]]["Board ID"].astype(str).tolist()

    new_gen = [bid for bid in st.session_state.selected_ids if bid not in visible_ids] + current_gen_visible
    new_scrape = [bid for bid in st.session_state.scrape_ids if bid not in visible_ids] + current_scrape_visible

    if set(new_gen) != set(st.session_state.selected_ids) or set(new_scrape) != set(st.session_state.scrape_ids):
        st.session_state.selected_ids = new_gen
        st.session_state.scrape_ids = new_scrape

    # --- Global Actions moved inside fragment for instant updates ---
    st.markdown("---")
    st.subheader("⚙️ Global Actions")
    st.write(f"You have **{len(st.session_state.get('selected_ids', []))}** boards currently selected in the table.")

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
                    # Then Generate with correct configs
                    board_configs = load_board_configs()
                    caps = get_board_capacities()
                    # Load cache again to get winner counts
                    with open(CACHE_FILE, "r") as f:
                        cache_data = json.load(f)
                    
                    final_configs = {}
                    for bid in selected:
                        config = board_configs.get(bid, {"columns": "1", "fill": "Progressive"})
                        cols = config["columns"]
                        if cols == "Best Fit":
                            board_cache = next((b for b in cache_data if str(b["board_id"]) == bid), None)
                            w_count = len(board_cache["winners"]) if board_cache else 0
                            cols = calculate_best_fit(w_count, caps)
                        
                        final_configs[bid] = {
                            "columns": cols,
                            "fill": config.get("fill", "Progressive").lower()
                        }
                    
                    trigger_image_generation(selected, final_configs)
                else:
                    st.error("❌ Process failed during scraping.")
                    with st.expander("Show Error Logs"):
                        st.code(res.stdout + "\n" + res.stderr)


def show_cache_stats(username_input=None, pin_input=None):
    """Displays statistics and handles board selection, scraping, and generation."""
    if not os.path.exists(CACHE_FILE):
        st.info("No scraped data found yet. Please run scraping first.")
        data = []
    else:
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            st.error("Error reading cache file.")
            data = []
    
    # Load available boards list
    if not os.path.exists("available_boards.json"):
        st.info("👋 Welcome! Please click **'🔄 Refresh Available Boards'** in the sidebar.")
        return

    with open("available_boards.json", "r") as f:
        available_boards_data = json.load(f)

    caps = get_board_capacities()
    render_management_panel(data, available_boards_data, caps, username_input, pin_input)

# --- UI Layout ---

st.markdown("""
<style>
    div[st-vertical-alignment="bottom"] button {
        height: 45px !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏆 FFGC Honors Board Management")
st.markdown("---")

# Load current state and environment
board_configs = load_board_configs()
current_ids = list(board_configs.keys())
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

# Main Control Panel removed from here (moved inside management fragment)

st.markdown("---")

# Image Generation Section
show_cache_stats(username_input, pin_input)

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
