"""Environment-based configuration. Never hardcode API keys."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

INBOX_PATH = Path(os.getenv("INBOX_PATH", ROOT / "inbox.json"))
OUTBOX_DIR = Path(os.getenv("OUTBOX_DIR", ROOT / "outbox"))
TRACE_PATH = Path(os.getenv("TRACE_PATH", ROOT / "trace.jsonl"))
PREFS_PATH = Path(os.getenv("PREFS_PATH", ROOT / "prefs.json"))
DECISIONS_PATH = Path(os.getenv("DECISIONS_PATH", ROOT / "decisions.json"))
DASHBOARD_HTML = Path(os.getenv("DASHBOARD_HTML", ROOT / "dashboard.html"))
DASHBOARD_JSON = Path(os.getenv("DASHBOARD_JSON", ROOT / "dashboard.json"))

OWNER_EMAIL = os.getenv("OWNER_EMAIL", "sam@paperjet.io")
OWNER_NAME = os.getenv("OWNER_NAME", "Sam")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
LLM_CALL_DELAY_SEC = float(os.getenv("LLM_CALL_DELAY_SEC", "2.0"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "4"))

# Reference "now" for follow-up age calculations (inbox ends ~2026-09-09)
REFERENCE_NOW = os.getenv("REFERENCE_NOW", "2026-09-09T18:00:00")
