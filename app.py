import streamlit as st
import json
import os
import subprocess
import pandas as pd
from datetime import datetime

# Configuration
REQ_BOARDS_FILE = "req_boards.json"
CACHE_FILE = "honors_boards_cache.json"
SCRAPER_SCRIPT = "honors_scraper.py"

# Page config
st.set_page_config(page_title="Honors Board Scraper Manager", page_icon="🏆", layout="wide")

def load_board_ids():
    """Loads the list of board IDs from the JSON file."""
    if os.path.exists(REQ_BOARDS_FILE):
        try:
            with open(REQ_BOARDS_FILE, "r") as f:
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
        st.error(f"Error running scraper: {e}")
        return False

def trigger_image_generation(ids):
    """Runs generate_boards.py for specific IDs."""
    try:
        st.info(f"🎨 Generating images for {len(ids)} boards...")
        cmd = ["python", "generate_boards.py"] + [str(i) for i in ids]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            st.success("✅ Image generation complete!")
            st.code(result.stdout)
        else:
            st.error("❌ Image generation failed.")
            st.code(result.stderr)
    except Exception as e:
        st.error(f"Error: {e}")

def show_cache_stats():
    """Displays statistics and handles board selection for image generation."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
            
            if data:
                # Initialize session state for selection if not present
                if "selected_ids" not in st.session_state:
                    st.session_state.selected_ids = [board.get("board_id") for board in data]

                stats = []
                for board in data:
                    bid = board.get("board_id")
                    stats.append({
                        "Select": bid in st.session_state.selected_ids,
                        "Board ID": bid,
                        "Title": board.get("title"),
                        "Winners Count": len(board.get("winners", []))
                    })
                
                df = pd.DataFrame(stats)
                
                st.subheader("📊 Latest Scraping Results")
                
                # Selection and Generation control buttons
                col_all, col_none, col_gen, _ = st.columns([1, 1.2, 2.5, 2], vertical_alignment="bottom")
                
                if col_all.button("✅ Select All", use_container_width=True):
                    st.session_state.selected_ids = df["Board ID"].tolist()
                    st.rerun()
                if col_none.button("❌ Select None", use_container_width=True):
                    st.session_state.selected_ids = []
                    st.rerun()
                
                # Show interactive table using data_editor
                edited_df = st.data_editor(
                    df,
                    column_config={
                        "Select": st.column_config.CheckboxColumn(
                            "Select",
                            help="Check to include in image generation",
                            default=False,
                        ),
                        "Board ID": st.column_config.NumberColumn(format="%d"),
                    },
                    disabled=["Board ID", "Winners Count"],
                    hide_index=True,
                    key="board_selector"
                )

                # Sync session state with the editor results
                current_selected = edited_df[edited_df["Select"]]["Board ID"].tolist()
                st.session_state.selected_ids = current_selected

                # Save title changes back to the cache file if any were made
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
                        st.toast("✅ Titles updated and saved to cache!")
                    except IOError as e:
                        st.error(f"Failed to save title changes: {e}")

                # Generation button in the same row
                if col_gen.button("🎨 Generate Selected Display Boards", type="primary", use_container_width=True):
                    if not current_selected:
                        st.warning("Please select at least one board first.")
                    else:
                        trigger_image_generation(current_selected)
            else:
                st.warning("Cache file is empty.")
        except (json.JSONDecodeError, KeyError) as e:
            st.error(f"Error reading cache file: {e}")
    else:
        st.info("No cache file found. Run the scraper to generate data.")

# --- UI Layout ---

st.title("🏆 Honors Board Management")
st.markdown("---")

# Load current state
current_ids = load_board_ids()

# Sidebar for CRUD
st.sidebar.header("🛠️ Manage Board IDs")

# Add new ID
with st.sidebar.form("add_id_form", clear_on_submit=True):
    new_id = st.number_input("New Board ID", min_value=1, step=1)
    submitted = st.form_submit_button("Add Board")
    if submitted:
        if new_id not in current_ids:
            current_ids.append(int(new_id))
            if save_board_ids(current_ids):
                st.sidebar.success(f"Added ID {new_id}")
                st.rerun()
            else:
                st.sidebar.error("Failed to save.")
        else:
            st.sidebar.warning(f"ID {new_id} already exists.")

# Display and Delete IDs
st.sidebar.markdown("### Current IDs")
if current_ids:
    for bid in current_ids:
        col1, col2 = st.sidebar.columns([3, 1])
        col1.write(f"ID: **{bid}**")
        if col2.button("🗑️", key=f"del_{bid}"):
            current_ids.remove(bid)
            save_board_ids(current_ids)
            st.rerun()
else:
    st.sidebar.info("No boards configured.")

# Main Control Panel (Vertical Stack)
st.subheader("⚙️ Scraper Controls")
st.write(f"Currently tracking **{len(current_ids)}** boards.")

if st.button("🔥 Run Honors Scraper", type="primary"):
    if run_scraper():
        st.success("✅ Scraping complete!")
    else:
        st.error("❌ Scraping failed. Check logs above.")

st.markdown("---")

# Image Generation Section
show_cache_stats()

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
