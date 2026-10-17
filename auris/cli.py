"""Auris daemon entrypoint: SIGUSR1 toggle, pipeline orchestration."""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

from . import audio, enhance, inject, notify, transcribe
from .config import TOGGLE_COMMAND, Config, load_config

# Shared state
_toggle_event = threading.Event()   # set by SIGUSR1; worker flips recording state
_shutdown_event = threading.Event()
_recording_stop = threading.Event() # set to end an in-progress recording
_recording_active = False


def _handle_sigusr1(signum, frame) -> None:
    global _recording_active
    _toggle_event.set()
    if _recording_active:
        # second press while recording: stop the capture immediately
        _recording_stop.set()


def _handle_shutdown(signum, frame) -> None:
    _recording_stop.set()
    _shutdown_event.set()


def _pipeline(wav_path: Path, cfg: Config) -> None:
    """Transcribe -> enhance -> pretty-print + clipboard. Runs in main loop."""
    try:
        notify.banner("TRANSCRIBE")
        raw = transcribe.transcribe(wav_path, cfg)
        if not raw:
            notify.warn("empty transcript — nothing to do")
            return
        notify.transcript_panel(raw)

        notify.banner("ENHANCE")
        notify.info(f"model={cfg.model} ollama={cfg.ollama_url}")
        try:
            enhanced = enhance.enhance(raw, cfg)
        except enhance.LLMError as exc:
            notify.warn(str(exc))
            notify.warn("falling back to raw transcript")
            enhanced = raw

        notify.enhanced_panel(enhanced)

        if cfg.inject:
            inject.inject(enhanced, cfg)
        else:
            notify.info("clipboard copy disabled (--no-inject)")
    except Exception as exc:
        notify.error(f"pipeline failed: {exc}")
    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            pass


def run(cfg: Config) -> int:
    signal.signal(signal.SIGUSR1, _handle_sigusr1)
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    notify.banner("Auris — Audio Utterance Refinement & Injection System")
    notify.info(f"model: {cfg.model} | stt: {cfg.stt_model} | ollama: {cfg.ollama_url}")
    notify.info(f"config: {cfg.config_path or '(defaults — copy auris.example.toml to ~/.config/auris/config.toml)'}")
    print(flush=True)
    notify.status("○", "IDLE", "not listening", color="dim")
    notify.info("Bind this command to a hotkey in your desktop settings:")
    print(f"    {TOGGLE_COMMAND}", file=sys.stderr, flush=True)
    notify.info(f"suggested hotkey: {cfg.hotkey_hint}")
    print(flush=True)

    is_recording = False
    while not _shutdown_event.is_set():
        signaled = _toggle_event.wait(timeout=0.5)
        if _shutdown_event.is_set():
            break
        if not signaled:
            continue
        _toggle_event.clear()

        if not is_recording:
            # START recording
            is_recording = True
            _recording_stop.clear()
            global _recording_active
            _recording_active = True
            notify.status("●", "REC", "listening — speak now (hotkey again or silence to stop)",
                          color="red", bell=True)
            try:
                wav_path = audio.record_mic(cfg, stop_event=_recording_stop)
            except Exception as exc:
                notify.error(f"recording failed: {exc}")
                is_recording = False
                _recording_active = False
                _toggle_event.clear()  # consume the stop-press so we don't auto-restart
                notify.status("○", "IDLE", "not listening", color="dim")
                continue
            is_recording = False
            _recording_active = False
            _toggle_event.clear()  # consume the stop-press so we don't auto-restart
            notify.status("○", "stop", "processing...", color="yellow", bell=True)
            _pipeline(wav_path, cfg)
            notify.status("○", "IDLE", "not listening", color="dim")
        else:
            # STOP recording (toggle while recording)
            _recording_stop.set()

    notify.info("shutting down")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="auris",
        description="Auris: hotkey-toggled voice capture -> local STT -> Ollama prompt enhancement -> clipboard (never auto-executes).",
    )
    parser.add_argument("--model", help="Ollama model name (default: gemma4:31b-cloud; config file: model = ...)")
    parser.add_argument("--ollama-url", help="Ollama base URL (default: http://localhost:11434)")
    parser.add_argument("--stt-model", help="faster-whisper model size (default: base)")
    parser.add_argument("--no-inject", action="store_true", help="print only; do not copy to clipboard")
    parser.add_argument("--config", help="path to a TOML config file")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except (FileNotFoundError, KeyError, TypeError) as exc:
        notify.error(str(exc))
        return 2

    if args.model:
        cfg.model = args.model
    if args.ollama_url:
        cfg.ollama_url = args.ollama_url
    if args.stt_model:
        cfg.stt_model = args.stt_model
    if args.no_inject:
        cfg.inject = False
    if args.verbose:
        cfg.verbose = True

    return run(cfg)


if __name__ == "__main__":
    sys.exit(main())
