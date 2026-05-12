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
import carousel_builder

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

if "ig_logged_in" not in st.session_state:
    st.session_state.ig_logged_in = None
if "ig_logged_in_user" not in st.session_state:
    st.session_state.ig_logged_in_user = ""
if "ig_last_username" not in st.session_state:
    st.session_state.ig_last_username = ""

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
                    return {str(bid): {"columns": "1", "fill": "Progressive", "category": "Mens", "durationMs": None} for bid in data}
                # Ensure defaults for carousel fields
                for bid, cfg in data.items():
                    cfg.setdefault("category", "Mens")
                    cfg.setdefault("durationMs", None)
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
    st.markdown("""
    <style>
    .stDialog .stImage img {
        max-height: 40vh !important;
        width: auto !important;
        object-fit: contain;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.write("Your honors board images have been generated successfully!")
    
    folder = "automated_images"
    image_files = []
    if os.path.exists(folder):
        image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg')) and "_8bit" not in f]
    
    if len(image_files) == 0:
        st.warning("No images were found in the output folder.")
        return

    selected_image = image_files[0]
    if len(image_files) > 1:
        selected_image = st.selectbox("Select board to preview:", sorted(image_files))

    preview_col, actions_col = st.columns([2, 1], gap="medium")

    with preview_col:
        img_path = os.path.join(folder, selected_image)
        st.image(img_path, caption=f"Preview: {selected_image}", width=380)

    with actions_col:
        with open(img_path, "rb") as f:
            st.download_button(
                label=f"💾 Download {selected_image}",
                data=f,
                file_name=selected_image,
                mime="image/png",
                use_container_width=True
            )
        zip_data = get_images_zip()
        if zip_data:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="💾 Download ZIP of All",
                data=zip_data,
                file_name=f"honors_boards_{timestamp}.zip",
                mime="application/zip",
                use_container_width=True
            )
        st.write("---")
        if st.button("🗑️ Cleanup & Close", use_container_width=True):
            cleanup_images()
            st.rerun()

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
    # Auto-detect category for new boards
    for bid in all_available_ids:
        bid_str = str(bid)
        if bid_str not in board_configs:
            title = boards_map.get(bid, "")
            cat = "Ladies" if "LADIES" in title.upper() else "Mens"
            board_configs[bid_str] = {"columns": "1", "fill": "Progressive", "category": cat, "durationMs": None}

    stats = []
    for bid in all_available_ids:
        bid_str = str(bid)
        board_cache = next((b for b in data if b["board_id"] == bid), None)
        status = "✅ Scraped" if board_cache else "⏳ Not Scraped"
        title = board_cache.get("title") if board_cache else boards_map.get(bid, f"Board {bid}")
        winners_count = len(board_cache.get("winners", [])) if board_cache else 0
        
        config = board_configs.get(bid_str, {})
        category = config.get("category", "Mens")
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
        
        cols_display = config.get("columns", "1")
        if cols_display == "Best Fit":
            cols_display = "1"
        fill_display = config.get("fill", "Progressive")
        dur_display = config.get("durationMs") or 0

        stats.append({
            "Scrape": bid_str in st.session_state.scrape_ids,
            "Gen": bid_str in st.session_state.selected_ids,
            "Board ID": bid,
            "Title": title,
            "Columns": cols_display,
            "Fill": fill_display,
            "Category": category,
            "DurationMs": dur_display,
            "Winners": winners_count,
            "Boards": boards_req,
            "Status": status
        })
    
    df = pd.DataFrame(stats)
    
    # --- Filter Logic ---
    filter_text = st.text_input("🔍 Filter Boards", value="", placeholder="Search by ID or Title...", help="Type to narrow down the list").lower()
    
    if filter_text:
        display_df = df[
            df["Board ID"].astype(str).str.contains(filter_text) | 
            df["Title"].str.lower().str.contains(filter_text)
        ]
    else:
        display_df = df

    # Selection controls (no data_editor to avoid JS module loading bugs)
    sel_scrape_key = "sel_scrape_ids"
    sel_gen_key = "sel_gen_ids"

    if sel_scrape_key not in st.session_state:
        st.session_state[sel_scrape_key] = list(st.session_state.scrape_ids)
    if sel_gen_key not in st.session_state:
        st.session_state[sel_gen_key] = list(st.session_state.selected_ids)

    all_id_strs = [str(b) for b in all_available_ids]
    all_id_strs_sorted = sorted(all_id_strs, key=lambda x: int(x))
    board_label = {s: f"{s} - {boards_map.get(int(s), '')}" for s in all_id_strs_sorted}

    col_sel, col_act = st.columns([2, 1], gap="large")
    with col_sel:
        st.multiselect("🗳️ Select boards to Scrape", options=all_id_strs_sorted, format_func=lambda x: board_label.get(x, x), key=sel_scrape_key)
        st.multiselect("🎨 Select boards to Generate", options=all_id_strs_sorted, format_func=lambda x: board_label.get(x, x), key=sel_gen_key)

    with col_act:
        st.markdown("**Quick actions**")
        if st.button("☑ All Scrape", use_container_width=True):
            st.session_state[sel_scrape_key] = all_id_strs_sorted
        if st.button("☐ Clear Scrape", use_container_width=True):
            st.session_state[sel_scrape_key] = []
        if st.button("☑ All Gen", use_container_width=True):
            st.session_state[sel_gen_key] = all_id_strs_sorted
            for bid in all_id_strs_sorted:
                if bid not in board_configs:
                    board_configs[bid] = {"columns": "1", "fill": "Progressive", "category": "Mens", "durationMs": None}
            save_board_configs(board_configs)
        if st.button("☐ Clear Gen", use_container_width=True):
            st.session_state[sel_gen_key] = []

    # Sync multiselect state to code-visible session vars
    st.session_state.scrape_ids = st.session_state.get(sel_scrape_key, [])
    st.session_state.selected_ids = st.session_state.get(sel_gen_key, [])

    # Action buttons
    col_scrape_btn, col_gen_btn = st.columns([1, 1], vertical_alignment="bottom")
    
    if col_scrape_btn.button("🔍 Scrape Selected", type="secondary", use_container_width=True, help="Scrapes selected boards"):
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

    if col_gen_btn.button("🎨 Generate Selected", type="primary", use_container_width=True):
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

    # Read-only table
    st.dataframe(
        display_df,
        column_order=["Board ID", "Title", "Columns", "Fill", "Category", "DurationMs", "Winners", "Boards", "Status"],
        hide_index=True,
        use_container_width=True
    )

    # Board configuration panel below the table
    with st.expander("⚙️ Board Configuration", expanded=False):
        board_ids_sorted = sorted(all_available_ids, key=lambda x: str(x))
        bid_opts = {str(b): f"{b} - {boards_map.get(b, '')}" for b in board_ids_sorted}
        selected_cfg_bid = st.selectbox("Select board to configure", options=list(bid_opts.keys()), format_func=lambda x: bid_opts[x], key="cfg_board_sel")

        if selected_cfg_bid:
            cfg = board_configs.get(selected_cfg_bid, {})
            cfg_cols = st.selectbox("Columns", options=["1", "2", "3", "4"], index=["1", "2", "3", "4"].index(cfg.get("columns", "1")), key="cfg_cols")
            cfg_fill = st.selectbox("Fill Method", options=["Progressive", "Balanced"], index=0 if cfg.get("fill", "Progressive") == "Progressive" else 1, key="cfg_fill")
            cfg_cat = st.selectbox("Category", options=["Mens", "Ladies", "Mixed"], index=["Mens", "Ladies", "Mixed"].index(cfg.get("category", "Mens")), key="cfg_cat")
            cfg_dur = st.number_input("Display Duration (ms)", value=cfg.get("durationMs") or 0, min_value=0, step=1000, key="cfg_dur")

            if st.button("Save Configuration", type="primary", use_container_width=True):
                board_configs[selected_cfg_bid] = {
                    "columns": cfg_cols,
                    "fill": cfg_fill,
                    "category": cfg_cat,
                    "durationMs": cfg_dur if cfg_dur > 0 else None
                }
                save_board_configs(board_configs)
                st.success(f"✅ Board {selected_cfg_bid} configuration saved!")
                st.rerun(scope="fragment")

    # --- Global Actions ---
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

    if st.button("💾 Export for USB", type="secondary", help="Generate images and export carousel_config.json + images to carousel_output/", use_container_width=True):
        selected = st.session_state.get('selected_ids', [])
        if not selected:
            st.warning("Please select at least one board first.")
        else:
            board_configs = load_board_configs()
            caps = get_board_capacities()
            with open(CACHE_FILE, "r") as f:
                cache_data = json.load(f)
            # Generate images first (inline generation, avoid download popup)
            scraped_selected = [bid for bid in selected if any(str(b["board_id"]) == bid for b in data)]
            if not scraped_selected:
                st.warning("Select at least one scraped board.")
            else:
                final_configs = {}
                for bid in scraped_selected:
                    config = board_configs.get(bid, {"columns": "1", "fill": "Progressive"})
                    cols = config["columns"]
                    if cols == "Best Fit":
                        board_cache = next((b for b in cache_data if str(b["board_id"]) == bid), None)
                        w_count = len(board_cache["winners"]) if board_cache else 0
                        cols = calculate_best_fit(w_count, caps)
                    final_configs[bid] = {"columns": cols, "fill": config.get("fill", "Progressive").lower()}
                with st.spinner("🎨 Generating images for USB export..."):
                    cleanup_images()
                    config_json = json.dumps(final_configs)
                    cmd = [sys.executable, "generate_boards.py", "--config", config_json] + [str(i) for i in scraped_selected]
                    gen_result = subprocess.run(cmd, capture_output=True, text=True)
                    if gen_result.returncode != 0:
                        st.error("❌ Image generation failed.")
                        with st.expander("View Logs"):
                            st.code(gen_result.stdout)
                            st.code(gen_result.stderr)
                    else:
                        # Build carousel export
                        display_config = carousel_builder.load_display_config()
                        result = carousel_builder.export_carousel(selected, board_configs, display_config, cache_data)
                        if result:
                            st.success(f"✅ USB export ready in `{result}/`")
                        else:
                            st.error("❌ USB export failed.")


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

st.title("🏆 FFGC Honors Board Management v1.1")
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

# Reset login state if username changed
if username_input != st.session_state.ig_last_username:
    st.session_state.ig_logged_in = None
    st.session_state.ig_logged_in_user = ""
    st.session_state.ig_last_username = username_input

log_col1, log_col2 = st.sidebar.columns([1, 1])
login_clicked = log_col1.button("🔑 Test Login", use_container_width=True, type="primary")
logout_clicked = log_col2.button("🚪 Logout", use_container_width=True)

if logout_clicked:
    st.session_state.ig_logged_in = None
    st.session_state.ig_logged_in_user = ""
    st.rerun()

if login_clicked:
    if not username_input or not pin_input:
        st.sidebar.error("Enter User ID and PIN first.")
    else:
        with st.spinner("Verifying credentials with Intelligent Golf..."):
            env = os.environ.copy()
            env["USERNAME"] = username_input
            env["PIN"] = pin_input
            process = subprocess.run(
                [sys.executable, "verify_login.py"],
                env=env, capture_output=True, text=True
            )
            if process.returncode == 0:
                st.session_state.ig_logged_in = True
                st.session_state.ig_logged_in_user = username_input
                st.rerun()
            else:
                st.session_state.ig_logged_in = False
                st.session_state.ig_logged_in_user = ""

ig_status = st.session_state.ig_logged_in
if ig_status is True:
    st.sidebar.markdown(f"🟢 **Logged in as** `{st.session_state.ig_logged_in_user}`")
elif ig_status is False:
    st.sidebar.markdown("🔴 **Invalid credentials**")
else:
    st.sidebar.markdown("⚪ **Not tested**")

st.sidebar.markdown("---")

# --- Carousel Settings ---
st.sidebar.header("📺 Carousel Settings")
display_config = carousel_builder.load_display_config()

fallback_duration = st.sidebar.number_input(
    "Global fallback (ms)", 
    value=display_config.get("globalConfig", {}).get("fallbackDurationMs", 8000),
    min_value=1000, step=1000,
    key="global_fallback"
)

with st.sidebar.expander("Per-category defaults", expanded=False):
    for cat_name in ["Mens", "Ladies", "Mixed"]:
        st.markdown(f"**{cat_name}**")
        cat_cfg = display_config.get("categories", {}).get(cat_name, {})
        col1, col2 = st.columns(2)
        d_dur = col1.number_input("Duration (ms)", value=cat_cfg.get("defaultDurationMs", 8000), min_value=1000, step=1000, key=f"cat_dur_{cat_name}")
        d_tag = col2.text_input("Theme tag", value=cat_cfg.get("themeTag", cat_name.lower()), key=f"cat_tag_{cat_name}")
        c_top = st.text_input("Top colour", value=cat_cfg.get("backgroundTopColor", "#1a1a2e"), key=f"cat_top_{cat_name}")
        c_bot = st.text_input("Bottom colour", value=cat_cfg.get("backgroundBottomColor", "#16213e"), key=f"cat_bot_{cat_name}")
        
        display_config.setdefault("categories", {})[cat_name] = {
            "defaultDurationMs": d_dur,
            "themeTag": d_tag,
            "backgroundTopColor": c_top,
            "backgroundBottomColor": c_bot
        }

display_config.setdefault("globalConfig", {})["fallbackDurationMs"] = fallback_duration
carousel_builder.save_display_config(display_config)

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
