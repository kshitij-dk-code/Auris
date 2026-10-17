"""Configuration for Auris.

Defaults can be overridden by a TOML config file and CLI flags.

Model selection lives in the config file:
  ~/.config/auris/config.toml   (created from auris.example.toml)
  Note: .config is a hidden directory — in a file manager press Ctrl+H,
  or edit with:  nano ~/.config/auris/config.toml

API key (only needed for the direct Ollama Cloud API, ollama.com):
  resolution order: OLLAMA_API_KEY / AURIS_API_KEY env,
  then ~/.config/auris/api_key (plain text, chmod 600).
  No API key is required for local models or cloud models used through the
  local Ollama daemon (ollama signin).
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "auris"
API_KEY_FILE = CONFIG_DIR / "api_key"

CONFIG_SEARCH_PATHS = [
    CONFIG_DIR / "config.toml",
    Path.cwd() / "auris.toml",
]

# Exact system prompt required by the spec. Do not reword.
DEFAULT_SYSTEM_PROMPT = (
    "You are an expert prompt engineer. The user will provide a rough, spoken idea. "
    "Your job is to expand it into a highly detailed, comprehensive instruction prompt "
    "for a coding agent. Infer missing technical requirements, structure it logically, "
    "and output ONLY the final enhanced prompt without any conversational filler or "
    "markdown wrappers."
)

TOGGLE_COMMAND = "pkill -USR1 -f auris"


@dataclass
class Config:
    # LLM (Ollama local daemon by default; ":cloud" models offload to Ollama Cloud)
    model: str = "gemma4:31b-cloud"
    ollama_url: str = "http://localhost:11434"
    api_key: str = ""          # only for direct ollama.com cloud API
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    llm_timeout: float = 120.0
    llm_retries: int = 1

    # STT
    stt_model: str = "base"
    stt_device: str = "cpu"
    stt_compute_type: str = "int8"

    # Audio
    sample_rate: int = 16000
    silence_threshold: float = 0.01   # RMS threshold considered "speech"
    silence_duration: float = 1.2     # seconds of silence to auto-stop
    max_seconds: float = 0.0          # 0 = unlimited

    # Clipboard
    inject: bool = True
    key_delay_ms: int = 12            # unused (typing removed); kept for config compat

    # Misc
    hotkey_hint: str = "Ctrl+Alt+Z (bind it yourself in your desktop settings)"
    verbose: bool = False

    config_path: Path | None = field(default=None, repr=False)


def _apply_mapping(cfg: Config, data: dict) -> None:
    # tolerate legacy key names
    data = dict(data)
    if "api_url" in data and "ollama_url" not in data:
        data["ollama_url"] = data.pop("api_url")
    if "inject_delay" in data:
        data.pop("inject_delay")  # no longer used since typing was removed
    for key, value in data.items():
        if not hasattr(cfg, key):
            raise KeyError(f"Unknown config key: {key!r}")
        current = getattr(cfg, key)
        if current is not None and not isinstance(current, type(value)):
            # allow int->float coercion
            if isinstance(current, float) and isinstance(value, int):
                value = float(value)
            else:
                raise TypeError(f"Config key {key!r}: expected {type(current).__name__}, got {type(value).__name__}")
        setattr(cfg, key, value)


def _load_api_key(cfg: Config) -> None:
    for env_name in ("OLLAMA_API_KEY", "AURIS_API_KEY"):
        val = os.environ.get(env_name, "").strip()
        if val:
            cfg.api_key = val
            return
    if cfg.api_key.strip():
        cfg.api_key = cfg.api_key.strip()
        return
    if API_KEY_FILE.is_file():
        cfg.api_key = API_KEY_FILE.read_text(encoding="utf-8").strip()


def load_config(path: str | Path | None = None) -> Config:
    cfg = Config()
    cfg_path: Path | None = None

    if path is not None:
        cfg_path = Path(path)
        if not cfg_path.is_file():
            raise FileNotFoundError(f"Config file not found: {cfg_path}")
    else:
        for candidate in CONFIG_SEARCH_PATHS:
            if candidate.is_file():
                cfg_path = candidate
                break

    if cfg_path is not None:
        with open(cfg_path, "rb") as fh:
            data = tomllib.load(fh)
        _apply_mapping(cfg, data)
        cfg.config_path = cfg_path

    _load_api_key(cfg)
    return cfg
