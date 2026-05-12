# AGENTS.md — FFGC Honors Board Manager

## Commands

```bash
streamlit run app.py                          # dev server at localhost:8501
docker compose up -d --build                  # prod build via Docker
python honors_scraper.py [board_id ...]       # scrape specific boards (default from req_boards.json)
python generate_boards.py [--config JSON] [--columns N] [board_id ...]  # generate images
python fetch_available_boards.py              # discover all boards → available_boards.json
python verify_login.py                        # test IG credentials
```

## Project structure

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI (652 lines) — the single app entrypoint |
| `ig_scraper.py` | Playwright-based scraper for intelligentgolf.co.uk (753 lines) |
| `honors_scraper.py` | CLI thin wrapper: reads `req_boards.json`, calls scraper, writes cache |
| `generate_boards.py` | Pillow image generation, per-board multi-column layout |
| `fetch_available_boards.py` | Board discovery: `boardcomps.php?board=N` links → JSON |
| `verify_login.py` | Standalone credential test |
| `board_configs.json` | Layout params per column count (font size, x-positions, row height, max rows) |
| `req_boards.json` | Per-board column/fill preference (`columns`: "1"-"4", `fill`: "Progressive"/"Balanced") |
| `Board_background_images/` | Background PNG templates (1column.png through 4column.png) |

## Data flow

```
IG Portal
  → fetch_available_boards.py  → available_boards.json  (board list)
  → honors_scraper.py          → honors_boards_cache.json (winner data per board)
  → generate_boards.py         → automated_images/*.png  (output images)
```

Config persistence: `req_boards.json` (writeable by app), `honors_boards_cache.json` (regenerated on scrape).

## Critical gotchas

- **Playwright Chromium must be installed**: `playwright install chromium` (Docker base image includes it).
- **Font loading**: Linux path looks for `LiberationSerif-Regular.ttf` via `fc-list` fallback. On Docker the Dockerfile copies Liberation fonts explicitly. On Windows uses `C:/Windows/Fonts/times.ttf`.
- **req_boards.json format**: Currently dict `{board_id: {columns, fill}}`. Old list format `[id, id, ...]` gets auto-converted on read in `app.py`.
- **No tests, no CI, no linting/formatters** (confirmed in TODO.md and absence of config files).
- **Cache and output files are gitignored**: `honors_boards_cache.json`, `available_boards.json`, `req_boards.json`, `automated_images/`, `*.png` (`Board_background_images/*.png` excluded from gitignore).
- **App auto-cleans `automated_images/`** on first session load.
- **Environment**: `.env` with `CLUB_URL`, `USERNAME`, `PIN`. These are passed as env vars to subprocess calls, not loaded inside scraper class (except via dotenv in the CLI scripts).
- **Docker**: `mcr.microsoft.com/playwright/python:v1.44.0-jammy` base. Volumes mount `req_boards.json` and `honors_boards_cache.json` for persistence.
- **Render deployment**: `render.yaml` with `sync: false` secrets (set in Render Dashboard, not in repo).
- **Supabase project linked** (`IG_Webscraper`) but unused in current app flow — no active database usage.
- **Image output**: Each board generates both full PNG and 8-bit quantized `_8bit.png`. Files named `{sanitized_title}-{part}.png`.
- **Fill methods**: `Progressive` (fill col 1 first, then 2…) vs `Balanced` (proportional split). `Progressive` is the default.
- **Text rendering**: Embossed effect (shadow + highlight offset), gold color `(195, 163, 102)`.

## Entrypoints

- App: `app.py:19` (`st.set_page_config`), `app.py:555` (title + layout), `app.py:649` (`show_cache_stats`)
- Scraper class: `ig_scraper.py:22` (`class IntelligentGolfScraper`)
- Image gen: `generate_boards.py:154` (`def automate_boards`)
