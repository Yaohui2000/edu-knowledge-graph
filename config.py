import json
import os
from pathlib import Path

CONFIG_FILE = Path(__file__).parent / ".config.json"
DEFAULTS = {
    "api_key": "",
    "base_url": "https://api.minimax.chat/v1",
    "model": "MiniMax-M2.7"
}

def load() -> dict:
    cfg = DEFAULTS.copy()
    if CONFIG_FILE.exists():
        cfg.update(json.loads(CONFIG_FILE.read_text()))
    # Environment variable takes precedence over file
    if os.environ.get("MINIMAX_API_KEY"):
        cfg["api_key"] = os.environ["MINIMAX_API_KEY"]
    if os.environ.get("MINIMAX_BASE_URL"):
        cfg["base_url"] = os.environ["MINIMAX_BASE_URL"]
    if os.environ.get("MINIMAX_MODEL"):
        cfg["model"] = os.environ["MINIMAX_MODEL"]
    return cfg


def save(data: dict) -> None:
    cfg = load()
    cfg.update(data)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
