# Auris

**A**udio **U**tterance **R**efinement **&** **I**njection **S**ystem

Local voice-to-prompt tool for Ubuntu (Wayland-friendly).

**Flow:** hotkey → speak → local STT (faster-whisper) → prompt enhancement via
**Ollama** (local model, or Ollama Cloud free tier) → colorfully printed to
the terminal **and copied to your clipboard** — nothing is ever typed or
executed. Paste with `Ctrl+V`, proofread, press Enter yourself.

The daemon starts **idle (not listening)**. A hotkey toggles recording on/off.

## Install

```bash
git clone <your-repo-url> auris && cd auris
sudo apt install portaudio19-dev wl-clipboard   # wl-clipboard = Wayland; xclip works too
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Choose the enhancement model (config file)

**This is the file where you configure which model to use:**

```
~/.config/auris/config.toml
```

(`.config` is hidden — in the Files app press **Ctrl+H**, or run
`nano ~/.config/auris/config.toml`.)

The key line:

```toml
model = "gemma4:31b-cloud"
```

Change it, save, restart the daemon. Or one-off without editing:

```bash
.venv/bin/python -m auris --model llama3.2:1b
```

| Kind | Example | Setup |
|---|---|---|
| Local | `llama3.2:1b`, `qwen3.5:4b`, `gemma4` | `ollama pull <name>` once |
| **Cloud (free tier)** | `gemma4:31b-cloud` (default), `gpt-oss:120b-cloud` | `ollama signin` once, then `ollama pull <name>-cloud` |

> Heads-up: tiny local models (e.g. `llama3.2:1b`) are fast but weak at
> prompt expansion — expect simpler enhancements than cloud models.

A template lives in the repo as `auris.example.toml`.

## Run

```bash
.venv/bin/python -m auris
```

You'll see a colorful dashboard:

```
── Auris — Audio Utterance Refinement & Injection System ──
    model: gemma4:31b-cloud | stt: base | ollama: http://localhost:11434
○ [IDLE] not listening
    Bind this command to a hotkey in your desktop settings:
    pkill -USR1 -f auris
```

**Keep this terminal open** — it's the daemon.

## Bind the hotkey (GNOME)

1. Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts → **Add**
2. Name: `Auris toggle`
3. Command: `pkill -USR1 -f auris`
4. Shortcut: e.g. `Ctrl+Alt+Z` (yours to choose)

Every press of that combo toggles: **start listening ↔ stop & process**.

## Usage

1. Start the daemon (command above).
2. Press the hotkey → `● REC` (red) + beep → speak your rough idea.
3. Stop by pressing the hotkey again **or** staying silent ~1.2 s.
4. Wait: the transcript appears in a **yellow panel**, the enhanced prompt in
   a **bright cyan panel**, and it's **copied to your clipboard**.
5. Click into your terminal / opencode, `Ctrl+V`, proofread, press Enter.

## Flags (override the config file)

| Flag | Default | Meaning |
|---|---|---|
| `--model` | `gemma4:31b-cloud` | Ollama model name |
| `--ollama-url` | `http://localhost:11434` | Ollama base URL |
| `--stt-model` | `base` | faster-whisper size (`tiny`/`base`/`small`/…) |
| `--no-inject` | off | print only; don't even touch the clipboard |
| `--config PATH` | auto | TOML config file |
| `--verbose` | off | extra logging |

## API keys

**None required.** Local models and cloud models used through your local
Ollama daemon (`ollama signin`) need no key in Auris. The only optional key
is for the direct `ollama.com` API (`OLLAMA_API_KEY` env var) — never commit
keys; `.gitignore` already excludes `.env` / `api_key` files.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `cannot reach Ollama` | `ollama serve` isn't running — start it |
| `model 'X' not found` | `ollama pull X` (local) or fix the name in config.toml |
| `cloud model unavailable` | `ollama signin && ollama pull <name>-cloud` |
| `no clipboard tool found` | `sudo apt install wl-clipboard` (Wayland) or `xclip` (X11) |
| `microphone unavailable` | check `arecord -l`, close other apps holding the mic |
| Hotkey does nothing | confirm the shortcut runs `pkill -USR1 -f auris`; check `pgrep -af auris` |
| Output looks unstyled | your terminal lacks truecolor; rich degrades gracefully |
| Whisper model download slow | first run only; use `--stt-model tiny` to shrink it |

## Stop the daemon

`Ctrl+C` in its terminal, or `pkill -f auris`.

## License

MIT — see [LICENSE](LICENSE).
