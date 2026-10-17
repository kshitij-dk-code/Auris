"""Prompt enhancement via Ollama (local daemon, or Ollama Cloud).

Two modes, chosen by config:

1. Local (default):  ollama_url = "http://localhost:11434"
   Any local model (e.g. "llama3.2:1b", "qwen3.5:4b"). Pull with `ollama pull <model>`.

2. Cloud: model names ending in ":cloud" / "-cloud" (e.g. "gemma4:31b-cloud").
   - Through your local daemon: run `ollama signin` once; the local Ollama
     offloads automatically. No API key needed here.
   - Direct cloud API: set ollama_url = "https://ollama.com" and put an API
     key in ~/.config/auris/api_key or OLLAMA_API_KEY.
"""

from __future__ import annotations

import requests

from . import notify
from .config import Config


class LLMError(RuntimeError):
    pass


def _strip_wrappers(text: str) -> str:
    """Safety net: remove accidental markdown fences / surrounding quotes."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def _is_cloud_model(model: str) -> bool:
    return model.endswith(":cloud") or model.endswith("-cloud")


def _headers(cfg: Config) -> dict:
    # Direct ollama.com cloud API needs a Bearer key; local daemon doesn't.
    if cfg.api_key and ("ollama.com" in cfg.api_url):
        return {"Authorization": f"Bearer {cfg.api_key}"}
    return {}


def enhance(raw_text: str, cfg: Config) -> str:
    """Send raw transcript to Ollama; return enhanced prompt."""
    url = f"{cfg.ollama_url.rstrip('/')}/api/chat"
    payload = {
        "model": cfg.model,
        "stream": False,
        "options": {"temperature": 0.4},
        "messages": [
            {"role": "system", "content": cfg.system_prompt},
            {"role": "user", "content": raw_text},
        ],
    }
    headers = _headers(cfg)

    last_exc: Exception | None = None
    for attempt in range(cfg.llm_retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=cfg.llm_timeout)
        except requests.exceptions.ConnectionError as exc:
            hint = ""
            if _is_cloud_model(cfg.model) and "ollama.com" not in cfg.api_url:
                hint = " (cloud model via local daemon — run `ollama signin` first)"
            raise LLMError(
                f"cannot reach Ollama at {cfg.ollama_url} — is `ollama serve` running?{hint}"
            ) from exc
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            notify.warn(f"Ollama timed out (attempt {attempt + 1})")
            continue

        if resp.status_code == 401:
            raise LLMError(
                "unauthorized (401) — for direct cloud API, set an API key in "
                "~/.config/auris/api_key or OLLAMA_API_KEY; "
                "for local daemon, run `ollama signin`"
            )
        if resp.status_code == 404:
            body = resp.text.lower()
            if "model" in body or _is_cloud_model(cfg.model):
                if _is_cloud_model(cfg.model):
                    raise LLMError(
                        f"cloud model '{cfg.model}' unavailable — run: ollama signin && "
                        f"ollama pull {cfg.model}  (or switch to a local model in the config file)"
                    )
                raise LLMError(
                    f"model '{cfg.model}' not found — run: ollama pull {cfg.model}  "
                    "(or set a different model in ~/.config/auris/config.toml)"
                )
            raise LLMError(f"Ollama 404: {resp.text[:200]}")
        if resp.status_code == 429:
            last_exc = LLMError("rate limited (429)")
            notify.warn(f"rate limited (attempt {attempt + 1})")
            continue
        if resp.status_code >= 500:
            last_exc = LLMError(f"Ollama server error {resp.status_code}: {resp.text[:200]}")
            notify.warn(f"server error {resp.status_code} (attempt {attempt + 1})")
            continue
        if resp.status_code != 200:
            raise LLMError(f"Ollama error {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        content = data.get("message", {}).get("content", "").strip()
        if not content:
            last_exc = LLMError("Ollama returned an empty response")
            continue
        return _strip_wrappers(content)

    raise LLMError(f"enhancement failed after retries: {last_exc}")
