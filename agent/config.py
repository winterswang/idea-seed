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


# Provider selection ("minimax" or "aliyun")
ACTIVE_PROVIDER = os.environ.get("PROVIDER", "minimax")

# Provider configurations
def load_ark_api_key() -> str:
    """Load ARK coding-plan API key from supported environment aliases."""
    return os.environ.get("ARK_API_KEY", "") or os.environ.get("ARKCODE_API_KEY", "")


def load_ark_base_url() -> str:
    """Load ARK Anthropic-compatible endpoint without accepting legacy MiniMax hosts."""
    return os.environ.get("ARK_CODING_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding")


def load_ark_model() -> str:
    """Load ARK model without letting known legacy MiniMax model names override defaults."""
    ark_model = os.environ.get("ARK_MODEL")
    if ark_model:
        return ark_model

    minimax_model = os.environ.get("MINIMAX_MODEL", "")
    if minimax_model and minimax_model.lower() not in {"minimax2.7", "minimax-2.7"}:
        return minimax_model

    return "minimax-m3"


PROVIDERS = {
    "minimax": {
        "api_key": load_ark_api_key(),
        "base_url": load_ark_base_url(),
        "model": load_ark_model(),
    },
    "aliyun": {
        "api_key": os.environ.get("ALIYUN_API_KEY", ""),
        "base_url": os.environ.get(
            "ALIYUN_BASE_URL", "https://coding.dashscope.aliyuncs.com/apps/anthropic"
        ),
        "model": os.environ.get("ALIYUN_MODEL", "qwen3.6-plus"),
    },
    "bytedance": {
        "api_key": os.environ.get("BYTEDANCE_API_KEY", ""),
        "base_url": os.environ.get(
            "BYTEDANCE_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding"
        ),
        "model": os.environ.get("BYTEDANCE_MODEL", "glm-5.1"),
    },
}


def get_provider_config() -> dict:
    """Get the active provider's configuration."""
    return PROVIDERS[ACTIVE_PROVIDER]


def get_api_key() -> str:
    """Get API key for active provider."""
    return get_provider_config()["api_key"]


def get_base_url() -> str:
    """Get base URL for active provider."""
    return get_provider_config()["base_url"]


def get_model() -> str:
    """Get model ID for active provider."""
    return get_provider_config()["model"]


# Backwards compatibility - MODEL_ID now points to active provider's model
MODEL_ID = get_model()
# minimax-m3 是 1M 上下文模型。主 agent loop(loop.py/team.py)已改流式调用，
# 不再受 anthropic SDK 非流式 ~21333 阈值限制，与其他项目统一取 30000。
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "30000"))

# Legacy names (kept for compatibility, but now delegated to active provider)
MINIMAX_API_KEY = get_api_key()
MINIMAX_BASE_URL = get_base_url()

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
