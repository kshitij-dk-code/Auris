"""Put the enhanced prompt on the clipboard (Wayland: wl-copy, X11: xclip/xsel).

The text is never typed and Enter is never pressed — paste manually with
Ctrl+V / Shift+Insert where you want it, proofread, then execute.
"""

from __future__ import annotations

import shutil
import subprocess

from . import notify
from .config import Config

# Keys that must never appear (proofread guarantee; newlines would also
# break single-line clipboard paste into a shell prompt).
_FORBIDDEN = {"\n", "\r", "\t"}


def sanitize(text: str) -> str:
    """Collapse newlines/tabs to spaces, strip control chars — single-line shell-safe."""
    cleaned = []
    for ch in text:
        if ch in _FORBIDDEN or ord(ch) < 32:
            cleaned.append(" ")
        else:
            cleaned.append(ch)
    return " ".join("".join(cleaned).split())


def _copy_wl(text: str) -> None:
    subprocess.run(["wl-copy", "--", text], check=True, timeout=10)


def _copy_xclip(text: str) -> None:
    subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True, timeout=10)


def _copy_xsel(text: str) -> None:
    subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=True, timeout=10)


_STRATEGIES = [
    ("wl-copy", _copy_wl),
    ("xclip", _copy_xclip),
    ("xsel", _copy_xsel),
]


def inject(text: str, cfg: Config) -> bool:
    """Copy text to the system clipboard. Returns True on success."""
    if not cfg.inject:
        return False

    text = sanitize(text)
    assert not any(ch in _FORBIDDEN for ch in text), "sanitized text must not contain control chars"

    for name, fn in _STRATEGIES:
        if shutil.which(name) is None:
            continue
        try:
            fn(text)
            notify.info(f"copied to clipboard via {name} — paste with Ctrl+V, proofread, then Enter")
            return True
        except Exception as exc:
            notify.warn(f"{name} failed: {exc}")
            continue

    notify.warn("no clipboard tool found — install wl-clipboard (Wayland) or xclip (X11); "
                "copy the text from the output above instead")
    return False
