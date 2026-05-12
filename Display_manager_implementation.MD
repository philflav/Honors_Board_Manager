# Display Manager Implementation Plan

## Overview
Add USB carousel export functionality to the FFGC Honors Board Manager. Users can assign boards to categories (Mens/Ladies/Mixed), configure display durations and gradient colors, then export images + `carousel_config.json` to a `carousel_output/` folder.

---

## Step 1 — Data Model

### Extend `req_boards.json`

Two new fields per board:

```json
{"1": {"columns": "1", "fill": "Progressive", "category": "Mens", "durationMs": null}}
```

- `category`: `"Mens" | "Ladies" | "Mixed"` (default `"Mens"`)
- `durationMs`: optional per-board override in ms. `null` = use category default.

### New file `display_config.json`

```json
{
  "globalConfig": { "fallbackDurationMs": 8000 },
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
```

---

## Step 2 — Create `carousel_builder.py`

New standalone module with:

```
carousel_builder.py
├── load_display_config(path) → dict
├── save_display_config(config, path)
├── build_carousel_config(board_ids, board_configs, display_config, cache_data)
│     → hierarchical JSON per PRD spec
├── export_carousel(board_ids, board_configs, display_config, cache_data, output_dir)
│     → copies images (no _8bit) → output_dir/images/
│     → writes carousel_config.json to output_dir/
```

### Grouping logic
- Each board = one group (groupId = sanitized title, groupName = original title)
- Multi-part images (`-1`, `-2`, `-3…`) within a board → sequential image objects in the group
- Groups sorted by board ID within their category

### Duration resolution order
1. Per-image `durationMs` (from per-board override in `req_boards.json`)
2. Category `defaultDurationMs`
3. Global `fallbackDurationMs`

→ Only emit `durationMs` on an image when it differs from the category default.

### Output folder structure

```
carousel_output/
├── carousel_config.json
└── images/
    ├── LADIES_ADAMS_TROPHY-1.png
    ├── LADIES_ADAMS_TROPHY-2.png
    └── ...
```

### Sample `carousel_config.json`

```json
{
  "globalConfig": { "fallbackDurationMs": 8000 },
  "categories": [
    {
      "name": "Mens",
      "defaultDurationMs": 8000,
      "groups": [
        {
          "groupId": "MENS_CLUB_CHAMPIONSHIP",
          "groupName": "MENS CLUB CHAMPIONSHIP",
          "sharedProperties": {
            "backgroundTopColor": "#1a1a2e",
            "backgroundBottomColor": "#16213e",
            "themeTag": "mens"
          },
          "images": [
            { "id": "MENS_CLUB_CHAMPIONSHIP-1", "url": "images/MENS_CLUB_CHAMPIONSHIP-1.png" },
            { "id": "MENS_CLUB_CHAMPIONSHIP-2", "url": "images/MENS_CLUB_CHAMPIONSHIP-2.png", "durationMs": 10000 }
          ]
        }
      ]
    }
  ]
}
```

---

## Step 3 — UI Changes (`app.py`)

### 3a. Per-board config pane (~line 430)
- **Category dropdown**: Mens / Ladies / Mixed (default Mens)
- **Display Duration (ms)**: optional number input (empty = use category default)

### 3b. New sidebar section "📺 Carousel Settings"
Inserted after credentials section (~line 621), before "Open User Guide" button:

- **Global fallback duration (ms)**
- **Per-category settings** — three expandable sections, each with:
  - Default duration (ms)
  - Gradient top colour (hex input)
  - Gradient bottom colour (hex input)
  - Theme tag (text input)
- All changes persist to `display_config.json` immediately

### 3c. "Export for USB" button
New button in the management panel action row. When clicked:
1. Generates images for selected boards (same as existing Gen flow)
2. Calls `carousel_builder.export_carousel()`
3. Copies non-quantized PNGs to `carousel_output/images/`
4. Writes `carousel_output/carousel_config.json`
5. Shows success message with folder path

---

## Step 4 — Other Changes

### `.gitignore`
Add `carousel_output/`

### No changes to `generate_boards.py`
Images already output to `automated_images/` — `carousel_builder` copies from there.

---

## Order of Implementation
1. Create `carousel_builder.py`
2. Update `app.py` — per-board config pane (category, durationMs)
3. Update `app.py` — sidebar carousel settings
4. Update `app.py` — Export for USB button
5. Update `.gitignore`
