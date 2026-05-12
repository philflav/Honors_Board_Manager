"""Carousel builder for USB display export.

Builds a hierarchical carousel_config.json and copies images
to a carousel_output/ directory for use by the Android display app.
"""

import json
import os
import shutil

DEFAULT_DISPLAY_CONFIG = {
    "globalConfig": {"fallbackDurationMs": 8000},
    "categories": {
        "Mens": {
            "defaultDurationMs": 8000,
            "backgroundTopColor": "#1a1a2e",
            "backgroundBottomColor": "#16213e",
            "themeTag": "mens"
        },
        "Ladies": {
            "defaultDurationMs": 8000,
            "backgroundTopColor": "#2d1b3d",
            "backgroundBottomColor": "#1a1a2e",
            "themeTag": "ladies"
        },
        "Mixed": {
            "defaultDurationMs": 8000,
            "backgroundTopColor": "#1a1a2e",
            "backgroundBottomColor": "#0f3460",
            "themeTag": "mixed"
        }
    }
}


def sanitize_title(title):
    """Match generate_boards.py sanitization for consistent filenames."""
    safe = "".join([c for c in title if c.isalnum() or c in " -_"]).strip().replace(" ", "_")
    return safe


def load_display_config(path="display_config.json"):
    """Load display config or return defaults if file missing."""
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_DISPLAY_CONFIG.copy()


def save_display_config(config, path="display_config.json"):
    """Persist display config to disk."""
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False


def build_carousel_config(board_ids, board_configs, display_config, cache_data):
    """Build the hierarchical carousel_config.json dict per PRD spec.

    Args:
        board_ids: list of board ID strings selected for export.
        board_configs: dict from req_boards.json {board_id: {columns, fill, category, durationMs}}.
        display_config: loaded display_config.json dict.
        cache_data: list from honors_boards_cache.json [{board_id, title, winners}].

    Returns:
        dict ready for JSON serialization.
    """
    board_map = {str(b["board_id"]): b for b in cache_data}

    categories_map = {}  # category_name → list of groups

    for bid in board_ids:
        bid_str = str(bid)
        board_data = board_map.get(bid_str)
        if not board_data:
            continue

        board_cfg = board_configs.get(bid_str, {})
        category = board_cfg.get("category", "Mens")
        per_board_duration_ms = board_cfg.get("durationMs")

        category_cfg = display_config.get("categories", {}).get(category, {})
        cat_default_duration = category_cfg.get("defaultDurationMs", 8000)

        title = board_data["title"]
        group_id = sanitize_title(title)

        # Find all matching image files in automated_images/
        images_dir = "automated_images"
        image_files = []
        if os.path.exists(images_dir):
            prefix = f"{group_id}-"
            for fname in os.listdir(images_dir):
                if fname.startswith(prefix) and fname.endswith(".png") and "_8bit" not in fname:
                    image_files.append(fname)

        image_files.sort(key=lambda x: _part_number(x))

        if not image_files:
            continue

        images = []
        for fname in image_files:
            img_id = fname.replace(".png", "")
            img_entry = {"id": img_id, "url": f"images/{fname}"}

            # Only emit durationMs when it differs from the category default
            if per_board_duration_ms is not None and per_board_duration_ms != cat_default_duration:
                img_entry["durationMs"] = per_board_duration_ms

            images.append(img_entry)

        group = {
            "groupId": group_id,
            "groupName": title,
            "sharedProperties": {
                "backgroundTopColor": category_cfg.get("backgroundTopColor", "#1a1a2e"),
                "backgroundBottomColor": category_cfg.get("backgroundBottomColor", "#16213e"),
                "themeTag": category_cfg.get("themeTag", category.lower())
            },
            "images": images
        }

        categories_map.setdefault(category, []).append(group)

    # Build final structure with categories sorted consistently
    category_order = ["Mens", "Ladies", "Mixed"]
    categories_output = []
    for cat_name in category_order:
        groups = categories_map.get(cat_name, [])
        if not groups:
            continue
        cat_cfg = display_config.get("categories", {}).get(cat_name, {})
        categories_output.append({
            "name": cat_name,
            "defaultDurationMs": cat_cfg.get("defaultDurationMs", 8000),
            "groups": groups
        })

    return {
        "globalConfig": {
            "fallbackDurationMs": display_config.get("globalConfig", {}).get("fallbackDurationMs", 8000)
        },
        "categories": categories_output
    }


def _part_number(filename):
    """Extract part number from filename like TITLE-2.png for sorting."""
    base = filename.replace(".png", "")
    parts = base.rsplit("-", 1)
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return 0


def export_carousel(board_ids, board_configs, display_config, cache_data, output_dir="carousel_output"):
    """Export images and carousel_config.json to output_dir.

    1. Copy matching non-quantized images to output_dir/images/
    2. Write carousel_config.json to output_dir/

    Returns the path to the output directory on success, or None on failure.
    """
    config = build_carousel_config(board_ids, board_configs, display_config, cache_data)

    if not config.get("categories"):
        print("Warning: no categories built — no boards matched.")
        return None

    images_dir_out = os.path.join(output_dir, "images")
    os.makedirs(images_dir_out, exist_ok=True)

    # Collect all unique image URLs from the config
    image_urls = set()
    for cat in config.get("categories", []):
        for group in cat.get("groups", []):
            for img in group.get("images", []):
                url = img.get("url", "")
                if url:
                    image_urls.add(url)

    source_dir = "automated_images"
    copied = 0
    for url in sorted(image_urls):
        # url is "images/filename.png" — extract filename
        fname = os.path.basename(url)
        src = os.path.join(source_dir, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(images_dir_out, fname))
            copied += 1
        else:
            print(f"Warning: {src} not found, skipping.")

    config_path = os.path.join(output_dir, "carousel_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"Exported {copied} images and carousel_config.json to {output_dir}/")
    return output_dir
