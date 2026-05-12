"""Flask web app for FFGC Honors Board Manager."""

import json
import os
import subprocess
import sys
import io
import zipfile
import math
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_file
)
from dotenv import load_dotenv

import carousel_builder

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
REQ_BOARDS_FILE = "req_boards.json"
CACHE_FILE = "honors_boards_cache.json"
SCRAPER_SCRIPT = "honors_scraper.py"
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-in-prod")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ---------------------------------------------------------------------------
# Helpers (ported from Streamlit app.py)
# ---------------------------------------------------------------------------

def get_board_capacities():
    if not os.path.exists("board_configs.json"):
        return {1: 16, 2: 36, 3: 44, 4: 58}
    try:
        with open("board_configs.json") as f:
            configs = json.load(f)
        caps = {}
        for col_str, config in configs.items():
            cols = int(col_str)
            max_rows = config["max_rows"]
            total = 0
            for i in range(cols):
                total += max_rows - 1 if (cols >= 3 and 0 < i < cols - 1) else max_rows
            caps[cols] = total
        return caps
    except Exception:
        return {1: 16, 2: 36, 3: 44, 4: 58}


def calculate_best_fit(winners_count, caps):
    for cols in sorted(caps.keys()):
        if winners_count <= caps[cols]:
            return cols
    return max(caps.keys()) if caps else 1


def load_board_configs():
    if os.path.exists(REQ_BOARDS_FILE):
        try:
            with open(REQ_BOARDS_FILE) as f:
                data = json.load(f)
            if isinstance(data, list):
                return {str(bid): {"columns": "1", "fill": "Progressive", "category": "Mens", "durationMs": None}
                        for bid in data}
            for cfg in data.values():
                cfg.setdefault("category", "Mens")
                cfg.setdefault("durationMs", None)
            return data
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_board_configs(configs):
    try:
        with open(REQ_BOARDS_FILE, "w") as f:
            json.dump(configs, f, indent=2)
        return True
    except IOError:
        return False


def load_available_boards():
    if os.path.exists("available_boards.json"):
        try:
            with open("available_boards.json") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def load_cache_data():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def strip_title_prefix(title):
    """Remove Ladies/Mens category prefixes from board titles."""
    prefixes = ["LADIES", "LADIE'S", "LADIES'", "LADY", "WOMEN'S", "WOMENS",
                "MENS", "MEN'S", "MENS'", "MEN"]
    upper = title.upper().strip()
    for p in prefixes:
        if upper.startswith(p):
            rest = title[len(p):].strip()
            return rest if rest else title
    return title


def clean_cache_titles():
    """Strip category prefixes from board titles in the cache file in-place."""
    if not os.path.exists(CACHE_FILE):
        return
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    changed = False
    for board in data:
        cleaned = strip_title_prefix(board.get("title", ""))
        if cleaned != board["title"]:
            board["title"] = cleaned
            changed = True
    if changed:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)


def cleanup_images():
    folder = "automated_images"
    if os.path.exists(folder):
        for filename in os.listdir(folder):
            fp = os.path.join(folder, filename)
            try:
                if os.path.isfile(fp) or os.path.islink(fp):
                    os.unlink(fp)
                elif os.path.isdir(fp):
                    shutil.rmtree(fp)
            except Exception:
                pass


def run_subprocess(cmd, env=None):
    """Run a subprocess, return (returncode, stdout+stderr)."""
    try:
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        return result.returncode, result.stdout + "\n" + result.stderr
    except subprocess.TimeoutExpired:
        return 1, "Process timed out after 300 seconds."


def make_env():
    """Build env dict with IG credentials from session."""
    env = os.environ.copy()
    env["USERNAME"] = session.get("username", "")
    env["PIN"] = session.get("pin", "")
    return env


# ---------------------------------------------------------------------------
# Background scrape tasks
# ---------------------------------------------------------------------------
scrape_tasks = {}

def _run_scrape_thread(task_id, ids, env):
    """Run scraper subprocess and update progress dict."""
    total = len(ids)
    scrape_tasks[task_id] = {"progress": 0, "status": "running", "output": "", "done": False}
    cmd = [sys.executable, SCRAPER_SCRIPT] + ids
    try:
        process = subprocess.Popen(
            cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        completed = 0
        out_lines = []
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            out_lines.append(line)
            if "Found" in line and "winners" in line:
                completed += 1
                pct = int((completed / total) * 99) if total else 99
                scrape_tasks[task_id]["progress"] = min(pct, 99)
        process.wait()
        rc = process.returncode
        scrape_tasks[task_id]["progress"] = 100
        scrape_tasks[task_id]["done"] = True
        scrape_tasks[task_id]["status"] = "success" if rc == 0 else "error"
        scrape_tasks[task_id]["output"] = "".join(out_lines)
    except Exception as e:
        scrape_tasks[task_id]["status"] = "error"
        scrape_tasks[task_id]["done"] = True
        scrape_tasks[task_id]["output"] = str(e)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    available_boards = load_available_boards()
    board_configs = load_board_configs()
    cache_data = load_cache_data()
    caps = get_board_capacities()
    display_config = carousel_builder.load_display_config()

    # Build board map
    boards_map = {int(b["id"]): b["title"] for b in available_boards}
    all_ids = sorted([int(b["id"]) for b in available_boards])

    # Auto-detect Ladies from board title for ALL boards
    for bid in all_ids:
        bid_str = str(bid)
        title = boards_map.get(bid, "")
        title_upper = title.upper()
        is_ladies = any(kw in title_upper for kw in ["LADIES", "LADIE", "WOMEN", "LADY"])

        if bid_str not in board_configs:
            board_configs[bid_str] = {
                "columns": "1", "fill": "Progressive",
                "category": "Ladies" if is_ladies else "Mens",
                "durationMs": None
            }
        elif is_ladies and board_configs[bid_str].get("category") != "Ladies":
            board_configs[bid_str]["category"] = "Ladies"

    # Persist any auto-corrections
    save_board_configs(board_configs)

    # Build rows for table
    rows = []
    for bid in all_ids:
        bid_str = str(bid)
        board_cache = next((b for b in cache_data if b["board_id"] == bid), None)
        title = board_cache.get("title") if board_cache else boards_map.get(bid, f"Board {bid}")
        winners_count = len(board_cache.get("winners", [])) if board_cache else 0
        config = board_configs.get(bid_str, {})

        cols_display = config.get("columns", "1")
        if cols_display == "Best Fit":
            cols_display = "1"
        fill_display = config.get("fill", "Progressive")
        category = config.get("category", "Mens")
        dur_display = config.get("durationMs") or 0

        selected_cols = config.get("columns", "1")
        eff_cols = int(selected_cols) if selected_cols != "Best Fit" else calculate_best_fit(winners_count, caps)
        capacity = caps.get(eff_cols, 1) or 1
        boards_req = max(math.ceil(winners_count / capacity), 1)

        rows.append({
            "id": bid,
            "title": title,
            "columns": cols_display,
            "fill": fill_display,
            "category": category,
            "duration_ms": dur_display,
            "winners": winners_count,
            "boards": boards_req,
            "scraped": "✅" if board_cache else "⏳",
        })

    scrape_ids = session.get("scrape_ids", [])
    selected_ids = session.get("selected_ids", [])

    preview_images = session.get("preview_images", [])
    if preview_images:
        session.pop("preview_images", None)
        session.modified = True

    return render_template("index.html",
                           rows=rows,
                           boards_map=boards_map,
                           board_configs=board_configs,
                           display_config=display_config,
                           scrape_ids=scrape_ids,
                           selected_ids=selected_ids,
                           username=session.get("username", ""),
                           pin=session.get("pin", ""),
                           ig_logged_in=session.get("ig_logged_in"),
                           preview_images=preview_images)


@app.route("/scrape", methods=["POST"])
def scrape():
    ids = request.form.getlist("scrape_ids")
    if not ids:
        flash("No boards selected for scraping.", "warning")
        return redirect(url_for("index"))
    if not session.get("username") or not session.get("pin"):
        flash("Enter User ID and PIN in the sidebar first.", "error")
        return redirect(url_for("index"))

    session["scrape_ids"] = ids
    session.modified = True

    # Start background scrape and redirect
    task_id = str(uuid.uuid4())
    session["scrape_task_id"] = task_id
    session.modified = True
    env = make_env()
    thread = threading.Thread(target=_run_scrape_thread, args=(task_id, ids, env), daemon=True)
    thread.start()
    return redirect(url_for("index"))


@app.route("/start-scrape", methods=["POST"])
def start_scrape():
    ids = request.form.getlist("scrape_ids")
    if not ids:
        return {"error": "No boards selected"}, 400
    if not session.get("username") or not session.get("pin"):
        return {"error": "Enter credentials first"}, 400

    session["scrape_ids"] = ids
    session.modified = True

    task_id = str(uuid.uuid4())
    env = make_env()
    thread = threading.Thread(target=_run_scrape_thread, args=(task_id, ids, env), daemon=True)
    thread.start()
    return {"task_id": task_id}


@app.route("/scrape-progress/<task_id>")
def scrape_progress(task_id):
    task = scrape_tasks.get(task_id)
    if not task:
        return {"error": "Unknown task"}, 404
    return {
        "progress": task["progress"],
        "status": task["status"],
        "done": task["done"],
    }


@app.route("/generate", methods=["POST"])
def generate():
    ids = request.form.getlist("gen_ids")
    if not ids:
        flash("No boards selected for generation.", "warning")
        return redirect(url_for("index"))

    session["selected_ids"] = ids
    session.modified = True

    board_configs = load_board_configs()
    cache_data = load_cache_data()
    caps = get_board_capacities()

    # Only generate scraped boards
    scraped_ids = [bid for bid in ids if any(str(b["board_id"]) == bid for b in cache_data)]
    if not scraped_ids:
        flash("None of the selected boards have been scraped yet.", "warning")
        return redirect(url_for("index"))

    final_configs = {}
    for bid in scraped_ids:
        config = board_configs.get(bid, {"columns": "1", "fill": "Progressive"})
        cols = config["columns"]
        if cols == "Best Fit":
            board_cache = next((b for b in cache_data if str(b["board_id"]) == bid), None)
            wc = len(board_cache["winners"]) if board_cache else 0
            cols = calculate_best_fit(wc, caps)
        final_configs[bid] = {"columns": str(cols), "fill": config.get("fill", "Progressive").lower()}

    cleanup_images()
    clean_cache_titles()
    config_json = json.dumps(final_configs)
    code, output = run_subprocess(
        [sys.executable, "generate_boards.py", "--config", config_json] + scraped_ids
    )
    if code == 0:
        flash(f"✅ Generated images for {len(scraped_ids)} board(s).", "success")
        # Store generated image list for preview
        preview = sorted([
            f for f in os.listdir("automated_images")
            if f.endswith(".png") and "_8bit" not in f
            and os.path.isfile(os.path.join("automated_images", f))
        ])
        session["preview_images"] = preview
    else:
        flash(f"❌ Generation failed:\n{output[:500]}", "error")
        session.pop("preview_images", None)
    session.modified = True
    return redirect(url_for("index"))


@app.route("/export-usb", methods=["POST"])
def export_usb():
    ids = request.form.getlist("gen_ids")
    if not ids:
        flash("No boards selected for USB export.", "warning")
        return redirect(url_for("index"))

    board_configs = load_board_configs()
    cache_data = load_cache_data()
    caps = get_board_capacities()
    display_config = carousel_builder.load_display_config()

    scraped_ids = [bid for bid in ids if any(str(b["board_id"]) == bid for b in cache_data)]
    if not scraped_ids:
        flash("None of the selected boards have been scraped yet.", "warning")
        return redirect(url_for("index"))

    final_configs = {}
    for bid in scraped_ids:
        config = board_configs.get(bid, {"columns": "1", "fill": "Progressive"})
        cols = config["columns"]
        if cols == "Best Fit":
            board_cache = next((b for b in cache_data if str(b["board_id"]) == bid), None)
            wc = len(board_cache["winners"]) if board_cache else 0
            cols = calculate_best_fit(wc, caps)
        final_configs[bid] = {"columns": str(cols), "fill": config.get("fill", "Progressive").lower()}

    cleanup_images()
    clean_cache_titles()
    config_json = json.dumps(final_configs)
    code, output = run_subprocess(
        [sys.executable, "generate_boards.py", "--config", config_json] + scraped_ids
    )
    if code != 0:
        flash(f"❌ Image generation failed:\n{output[:500]}", "error")
        return redirect(url_for("index"))

    # Store generated images for preview (exclude _8bit duplicates)
    preview = sorted([
        f for f in os.listdir("automated_images")
        if f.endswith(".png") and "_8bit" not in f
        and os.path.isfile(os.path.join("automated_images", f))
    ])
    session["preview_images"] = preview

    result = carousel_builder.export_carousel(ids, board_configs, display_config, cache_data)
    if result:
        flash(f"✅ USB export ready in {result}/", "success")
    else:
        flash("❌ USB export failed.", "error")
    return redirect(url_for("index"))


@app.route("/save-config", methods=["POST"])
def save_config():
    bid = request.form.get("board_id")
    if not bid:
        flash("No board specified.", "warning")
        return redirect(url_for("index"))

    board_configs = load_board_configs()
    board_configs[bid] = {
        "columns": request.form.get("columns", "1"),
        "fill": request.form.get("fill", "Progressive"),
        "category": request.form.get("category", "Mens"),
        "durationMs": int(request.form["duration_ms"]) if request.form.get("duration_ms", "0") != "0" else None,
    }
    if save_board_configs(board_configs):
        flash(f"✅ Board {bid} configuration saved.", "success")
    else:
        flash("❌ Failed to save configuration.", "error")
    return redirect(url_for("index"))


@app.route("/save-display-config", methods=["POST"])
def save_display_config():
    display_config = carousel_builder.load_display_config()
    display_config.setdefault("globalConfig", {})["fallbackDurationMs"] = int(request.form.get("global_fallback", 8000))

    for cat in ["Mens", "Ladies", "Mixed"]:
        display_config.setdefault("categories", {})[cat] = {
            "defaultDurationMs": int(request.form.get(f"cat_dur_{cat}", 8000)),
            "themeTag": request.form.get(f"cat_tag_{cat}", cat.lower()),
            "backgroundTopColor": request.form.get(f"cat_top_{cat}", "#1a1a2e"),
            "backgroundBottomColor": request.form.get(f"cat_bot_{cat}", "#16213e"),
        }

    carousel_builder.save_display_config(display_config)
    flash("✅ Display settings saved.", "success")
    return redirect(url_for("index"))


@app.route("/select-all-scrape", methods=["POST"])
def select_all_scrape():
    available = load_available_boards()
    session["scrape_ids"] = [str(b["id"]) for b in available]
    session.modified = True
    return redirect(url_for("index"))


@app.route("/clear-scrape", methods=["POST"])
def clear_scrape():
    session["scrape_ids"] = []
    session.modified = True
    return redirect(url_for("index"))


@app.route("/select-all-gen", methods=["POST"])
def select_all_gen():
    available = load_available_boards()
    ids = [str(b["id"]) for b in available]
    session["selected_ids"] = ids
    session.modified = True
    # Ensure configs exist
    board_configs = load_board_configs()
    for bid in ids:
        if bid not in board_configs:
            board_configs[bid] = {"columns": "1", "fill": "Progressive", "category": "Mens", "durationMs": None}
    save_board_configs(board_configs)
    return redirect(url_for("index"))


@app.route("/clear-gen", methods=["POST"])
def clear_gen():
    session["selected_ids"] = []
    session.modified = True
    return redirect(url_for("index"))


@app.route("/refresh-boards", methods=["POST"])
def refresh_boards():
    if not session.get("username") or not session.get("pin"):
        flash("Enter User ID and PIN first.", "error")
        return redirect(url_for("index"))

    env = make_env()
    code, output = run_subprocess([sys.executable, "fetch_available_boards.py"], env=env)
    if code == 0:
        flash("✅ Board list updated!", "success")
    else:
        flash(f"❌ Failed to refresh:\n{output[:300]}", "error")
    return redirect(url_for("index"))


@app.route("/test-login", methods=["POST"])
def test_login():
    username = request.form.get("username", "").strip()
    pin = request.form.get("pin", "").strip()
    if not username or not pin:
        flash("Enter User ID and PIN.", "warning")
        return redirect(url_for("index"))

    session["username"] = username
    session["pin"] = pin
    session.modified = True

    env = make_env()
    code, output = run_subprocess([sys.executable, "verify_login.py"], env=env)
    if code == 0:
        session["ig_logged_in"] = True
        flash(f"✅ Logged in as {username}.", "success")
    else:
        session["ig_logged_in"] = False
        flash("🔴 Invalid credentials.", "error")
    return redirect(url_for("index"))


@app.route("/logout", methods=["POST"])
def logout():
    session["ig_logged_in"] = None
    session.pop("username", None)
    session.pop("pin", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))


@app.route("/download-zip")
def download_zip():
    folder = "automated_images"
    if not os.path.exists(folder):
        flash("No images to download.", "warning")
        return redirect(url_for("index"))
    files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
    if not files:
        flash("No images to download.", "warning")
        return redirect(url_for("index"))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for fname in files:
            zf.write(os.path.join(folder, fname), fname)
    buf.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(buf, mimetype="application/zip",
                     as_attachment=True,
                     download_name=f"honors_boards_{ts}.zip")


@app.route("/automated_images/<filename>")
def serve_preview(filename):
    return send_file(os.path.join("automated_images", filename))


@app.route("/download-carousel")
def download_carousel():
    folder = "carousel_output"
    if not os.path.exists(folder):
        flash("No carousel export to download.", "warning")
        return redirect(url_for("index"))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for root, dirs, files in os.walk(folder):
            for fname in files:
                fp = os.path.join(root, fname)
                arcname = os.path.relpath(fp, folder)
                zf.write(fp, arcname)
    buf.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return send_file(buf, mimetype="application/zip",
                     as_attachment=True,
                     download_name=f"carousel_export_{ts}.zip")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
