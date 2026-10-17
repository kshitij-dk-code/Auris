"""Speech-to-text via faster-whisper (local, CPU int8)."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from . import notify
from .config import Config

_model = None


def _get_model(cfg: Config):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        notify.info(f"loading whisper model '{cfg.stt_model}' (first run downloads it)...")
        _model = WhisperModel(cfg.stt_model, device=cfg.stt_device, compute_type=cfg.stt_compute_type)
    return _model


def _load_wav(path: Path) -> np.ndarray:
    """Decode a 16-bit PCM WAV to float32 mono [-1, 1].

    Avoids faster-whisper's PyAV decode path (incompatible kwarg on some
    av/faster-whisper version combos).
    """
    with wave.open(str(path), "rb") as wf:
        if wf.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit WAV, got {wf.getsampwidth() * 8}-bit")
        raw = wf.readframes(wf.getnframes())
        channels = wf.getnchannels()
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio


def transcribe(wav_path: Path, cfg: Config) -> str:
    """Transcribe a WAV file to raw text."""
    model = _get_model(cfg)
    audio = _load_wav(wav_path)
    segments, _info = model.transcribe(audio, beam_size=1, vad_filter=True)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text
