# AIRGUARD — Local Testing Tools (Git Ignored)

This directory (`backend/local_testing/`) is dedicated to **local-only** testing scripts, manual verification utilities, and mock UI harnesses.

> [!NOTE]
> This folder and its contents are excluded from Git via `.gitignore`. Do NOT place production code, secrets, or live credentials here.

## Contents

1. `mock_test_harness.html`:
   - Interactive local browser UI for testing `POST /routes/pollution-aware` and `POST /analyze`.
   - Lets you test origin/destination inputs, toggle preferences (`faster`, `balanced`, `cleaner`), and trigger pre-configured test scenarios.
   - Run the backend (`uvicorn app.main:app --reload`), then open `mock_test_harness.html` in your browser.

2. `manual_smoke_test.py`:
   - Command-line manual smoke runner that tests all endpoints and displays color-coded output.
