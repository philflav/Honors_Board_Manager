# FFGC Honors Board Manager — TODO

## Testing & Quality
- [ ] Add unit tests (pytest) for scraper, image generator, config parsing
- [ ] Add integration tests for end-to-end scrape-and-generate flow
- [ ] Add Python type hints across all modules
- [ ] Set up linting/formatting (ruff, black)

## Code Health & Refactoring
- [ ] Break up `app.py` (~652 lines) into smaller modules
- [ ] Break up `ig_scraper.py` (~753 lines)
- [ ] Centralize error handling with custom exception classes
- [ ] Add proper logging

## Bugs & UI Fixes
- [ ] Investigate and fix various bugs with the UI
- [ ] Evaluate replacing Streamlit with Flask

## Google Drive Integration
- [ ] Add option to upload/download full-resolution images to Google Drive
- [ ] Make the Google Drive destination (folder ID / path) configurable

## PWA / Carousel Display App
- [ ] Build a progressive web app (convert to APK) for carousel display of images from Google Drive
- [ ] Create configuration file (drawing order, transitions, display time, screen number)
- [ ] Research screen sizes for Android TV (target platform)

## Features & Enhancements
- [ ] Parallel/async scraping
- [ ] Cache invalidation strategy
- [ ] Input validation for board configs
- [ ] Save/load full session state
- [ ] Progress indicators for long-running ops

## Infrastructure & DevOps
- [ ] Add CI pipeline (GitHub Actions)
- [ ] Add pre-commit hooks
- [ ] Improve Docker setup
- [ ] Production secrets management

## Documentation & UX
- [ ] Improve README with screenshots, architecture diagram
- [ ] Add inline help tooltips in Streamlit UI
- [ ] Better error messages in UI

## Security
- [ ] Use Streamlit secrets instead of session state for credentials
- [ ] Sanitize/validate all user inputs
