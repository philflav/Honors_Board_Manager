import streamlit as st
import json
import os
import subprocess
import pandas as pd
import io
import zipfile
import shutil
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

def trigger_image_generation(ids):
    """Runs generate_boards.py for specific IDs."""
    try:
        with st.spinner(f"🎨 Generating {len(ids)} board images..."):
            cmd = ["python", "generate_boards.py"] + [str(i) for i in ids]
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

# Main Control Panel
col_controls, col_help = st.columns([1.6, 1], gap="medium")

with col_controls:
    st.subheader("⚙️ Scraper Controls")
    
    # Credentials section
    c1, c2 = st.columns([1, 1])
    with c1:
        username_input = st.text_input("User ID", value=os.getenv("USERNAME", ""), help="Your Intelligent Golf username")
    with c2:
        pin_input = st.text_input("PIN", value=os.getenv("PIN", ""), type="password", help="Your Intelligent Golf PIN")

    st.write(f"Currently tracking **{len(current_ids)}** boards.")

    if st.button("🔥 Run Honors Scraper", type="primary", use_container_width=True):
        if not username_input or not pin_input:
            st.error("Please provide both User ID and PIN.")
        else:
            # Pass credentials via environment variables for the subprocess
            env = os.environ.copy()
            env["USERNAME"] = username_input
            env["PIN"] = pin_input
            
            # We need to wrap run_scraper to accept env
            def run_scraper_with_env(env_vars):
                try:
                    with st.spinner(f"⏳ Extracting data from {len(current_ids)} boards... Please wait."):
                        process = subprocess.Popen(
                            ["python", SCRAPER_SCRIPT],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            bufsize=1,
                            env=env_vars
                        )
                        
                        # Consume the output so the process doesn't block, but don't display it
                        stdout, stderr = process.communicate()
                        
                        if process.returncode != 0:
                            with st.expander("⚠️ View Error Logs"):
                                st.code(stdout)
                                if stderr:
                                    st.code(stderr)
                            return False
                        return True
                except Exception as e:
                    st.error(f"Error running scraper: {e}")
                    return False

            if run_scraper_with_env(env):
                st.success("✅ Scraping complete!")
                st.rerun() # Refresh to show new counts
            else:
                st.error("❌ Scraping failed. Check logs in the expander above.")

with col_help:
    st.info("""
    ### 📖 Quick User Guide
    
    1.  **Manage Boards**: Use the **sidebar on the left** to add or remove Board IDs you want to track.
    2.  **Login Info**: Ensure your **User ID** and **PIN** are correct.
    3.  **Fetch Data**: Click **Run Honors Scraper** to get the latest winners from the club site.
    4.  **Renaming**: In the table below, you can click on any **Title** to change it (e.g. shorten it for the board).
    5.  **Pick Boards**: Click the checkboxes to select which boards to create as images.
    6.  **Create images**: Click **Generate Selected Display Boards**.
    7.  **ZIP & Exit**: Download your images in the popup, then click **Exit & Cleanup** in the sidebar.
    """, icon="💡")

st.markdown("---")

# Image Generation Section
show_cache_stats()

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
