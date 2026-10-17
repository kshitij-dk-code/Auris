# Auris — PLAN.md

Design document for the **A**udio **U**tterance **R**efinement **&**
**I**njection **S**ystem daemon.

## Goal

Capture voice, transcribe it locally, expand it into a detailed coding-agent
prompt with **Ollama** (local model or Ollama Cloud via `:cloud` model names),
print it colorfully to the terminal **and** copy it to the clipboard —
nothing is ever typed or executed, so the user always proofreads first.

## Architecture

```
SIGUSR1 (hotkey → pkill -USR1 -f auris)
        │
        ▼
┌──────────── cli.py ────────────┐
│  daemon loop, state machine    │
│  IDLE ⇄ RECORDING → PROCESSING │
└───┬──────────────┬─────────────┘
    │ start        │ stop (toggle / silence)
    ▼              ▼
 audio.py       transcribe.py          enhance.py           inject.py
 sounddevice    faster-whisper base    Ollama /api/chat     wl-copy → xclip
 16kHz mono     int8 CPU, local        model from           → xsel
 RMS VAD                              config.toml           clipboard only,
                                      (local or :cloud)    NEVER types or presses Enter
        │
        ▼
 notify.py (rich) — colored panels: transcript (yellow), enhanced prompt (cyan)
```

### State machine (cli.py)

- **IDLE** (default): prints status + the exact command to bind to a DE hotkey.
- **SIGUSR1 while IDLE** → **RECORDING** (`● REC`, red, terminal bell).
- **Stop conditions**: SIGUSR1 again, OR ~1.2 s of silence *after speech is
  detected* (so room noise/fan hum doesn't end the clip early, and pre-speech
  silence doesn't either).
- **PROCESSING**: transcribe → enhance → pretty-print + clipboard. Back to IDLE.
- SIGINT/SIGTERM → clean shutdown (mic released, temp WAV deleted).

Signal handler only sets `threading.Event`s — no work done in the handler.

### Hotkey mechanism (signal + DE shortcut)

In-process global hotkeys (`pynput`, `keyboard`) are unreliable on Wayland and
`keyboard` needs root/uinput. Instead the daemon prints:

```
pkill -USR1 -f auris
```

Bind that to any combo in GNOME Settings → Keyboard → Custom Shortcuts.
Wayland-proof; the hotkey is whatever the user picks in the DE.

### Audio (audio.py)

- `sounddevice` (PortAudio) 16 kHz mono int16 → temp WAV.
- Energy VAD: RMS threshold (default 0.01) + 1.2 s silence tail, armed only
  after speech is seen. `max_seconds` config exists, default unlimited.
- Mic errors (no device, busy, permission) surface as clear messages.

### Transcription (transcribe.py)

- `faster-whisper`, `base`, CPU int8 (first run downloads the model).
- WAV decoded with the stdlib `wave` module → float32 numpy, passed directly
  to `model.transcribe()` — avoids a known PyAV `metadata_errors` kwarg
  incompatibility between faster-whisper 1.2.x and av 19.x on Python 3.14.

### Enhancement (enhance.py)

- `requests.post` to `http://localhost:11434/api/chat`, `stream=false`,
  temperature 0.4, 120 s timeout, 1 retry + backoff on 429/5xx.
- **Model comes from the config file** (`~/.config/auris/config.toml`, key
  `model`), default `gemma4:31b-cloud`. CLI `--model` overrides it.
- **Ollama Cloud**: model names ending `:cloud` / `-cloud` are offloaded by
  the local daemon after `ollama signin`. Direct `ollama.com` API also
  supported (`ollama_url = "https://ollama.com"` + Bearer key from
  `OLLAMA_API_KEY` / `~/.config/auris/api_key`).
- Exact required system prompt is hardcoded in `config.py`
  (`DEFAULT_SYSTEM_PROMPT`) — do not reword.
- Errors: connection refused → "is `ollama serve` running?"; 404 local →
  "run `ollama pull <model>`"; 404 cloud → "ollama signin && pull"; 401 →
  key hint; 429/5xx → retry, then fall back to raw transcript. Strips
  accidental markdown fences.

### Clipboard output (inject.py)

- Both channels: pretty panels on stdout, then **copied to the system
  clipboard** — nothing is typed into any window (pynput/xdotool typing
  proved unreliable under Wayland).
- Clipboard chain: `wl-copy` (Wayland) → `xclip` → `xsel` (first available
  wins). User pastes manually with Ctrl+V.
- Newlines/tabs collapsed to spaces; `assert` guarantees no control chars —
  shell-safe single line. **Nothing is ever executed.**

### Rich output (notify.py)

- `rich` Console split: status/rule lines → stderr; transcript + enhanced
  prompt panels → stdout (ANSI stripped automatically when piped).
- Transcript: dim-yellow italic panel. Enhanced prompt: bold-white text in a
  bright-cyan panel ("also copied to clipboard" subtitle).

## Key design decisions

| Decision | Rationale |
|---|---|
| Signals over pynput hotkeys | Wayland can't see global keys in-process; DE shortcuts always work |
| Clipboard over synthetic typing | pynput/xdotool typing unreliable under Wayland; clipboard always works |
| sounddevice over pyaudio | Cleaner callback API, no ALSA compile friction |
| faster-whisper over Vosk | Better accuracy, still local & CPU-fast |
| Ollama over hosted APIs | Free local models + free cloud tier; one config file switches model |
| Stdlib WAV decode | sidesteps PyAV/faster-whisper version break |
| Collapse newlines | shell-safe single-line clipboard paste |
| Fallback to raw transcript | pipeline never leaves the user empty-handed |
| rich for output | readable, colorful, degrades gracefully when piped |

## Files

```
auris/
├── __init__.py     name + version
├── __main__.py     python -m auris entrypoint
├── cli.py          daemon, SIGUSR1 state machine, orchestration
├── config.py       Config dataclass, TOML load, env overrides, system prompt
├── audio.py        Recorder + record_mic (silence VAD)
├── transcribe.py   faster-whisper wrapper
├── enhance.py      Ollama client (local + cloud)
├── inject.py       clipboard copy (wl-copy/xclip/xsel)
└── notify.py       rich status/banner/panel helpers
auris.example.toml  config template
requirements.txt
README.md, PLAN.md, LICENSE, .gitignore
```
