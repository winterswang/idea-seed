"""Configuration for Idea Seed."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Project paths
# Use __file__ to ensure WORKDIR is always the project root, regardless of cwd
_WORKDIR = Path(__file__).parent.parent.resolve()

# Load .env from project directory before accessing environment variables
load_dotenv(_WORKDIR / ".env", override=True)

WORKDIR = _WORKDIR
STATE_DIR = WORKDIR / ".state"
TRANSCRIPT_DIR = WORKDIR / ".transcripts"
TEAM_DIR = WORKDIR / ".team"
INBOX_DIR = TEAM_DIR / "inbox"


# Model configuration
MODEL_ID = os.environ.get("MODEL_ID", "minimax2.7")
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "32000"))

# MiniMax API
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.chat")

# Context management
TOKEN_THRESHOLD = int(os.environ.get("TOKEN_THRESHOLD", "150000"))
KEEP_RECENT = int(os.environ.get("KEEP_RECENT", "3"))

# Iteration limits
MAX_ROUNDS = int(os.environ.get("MAX_ROUNDS", "10"))
MAX_ITERATIONS = int(os.environ.get("MAX_ITERATIONS", "10"))


def ensure_dirs() -> None:
    """Ensure all required directories exist."""
    STATE_DIR.mkdir(exist_ok=True)
    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    TEAM_DIR.mkdir(exist_ok=True)
    INBOX_DIR.mkdir(exist_ok=True)
