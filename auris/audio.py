"""Microphone capture with silence-based auto-stop."""

from __future__ import annotations

import queue
import tempfile
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from . import notify
from .config import Config


class Recorder:
    """Records mic audio; caller requests stop via .stop()."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._q: queue.Queue[np.ndarray] = queue.Queue()
        self._stop = threading.Event()
        self._frames: list[np.ndarray] = []

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            notify.warn(f"audio: {status}")
        self._q.put(indata.copy())

    def record(self) -> Path:
        """Record until stop() is called or silence_duration elapses. Returns WAV path."""
        cfg = self.cfg
        wav_path = Path(tempfile.mkstemp(prefix="v2p_", suffix=".wav")[1])
        self._stop.clear()
        self._frames = []

        try:
            stream = sd.InputStream(
                samplerate=cfg.sample_rate,
                channels=1,
                dtype="int16",
                callback=self._callback,
            )
        except sd.PortAudioError as exc:
            raise RuntimeError(f"microphone unavailable: {exc}") from exc

        silent_run = 0.0
        speech_seen = False
        chunk_sec = 0.1
        with stream:
            while not self._stop.is_set():
                try:
                    block = self._q.get(timeout=1.0)
                except queue.Empty:
                    continue
                self._frames.append(block)
                rms = float(np.sqrt(np.mean((block.astype(np.float32) / 32768.0) ** 2)))
                if rms >= cfg.silence_threshold:
                    speech_seen = True
                    silent_run = 0.0
                elif speech_seen:
                    # only count silence toward auto-stop once speech has been seen,
                    # so room noise/fan hum doesn't end the clip early — and silence
                    # before any speech doesn't either.
                    silent_run += chunk_sec
                    if silent_run >= cfg.silence_duration:
                        notify.info("silence detected — stopping")
                        break
                if cfg.max_seconds > 0 and len(self._frames) * chunk_sec >= cfg.max_seconds:
                    notify.info("max duration reached — stopping")
                    break

        if not self._frames:
            raise RuntimeError("no audio captured (silent or broken mic)")

        audio = np.concatenate(self._frames, axis=0)
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(cfg.sample_rate)
            wf.writeframes(audio.tobytes())
        return wav_path

    def stop(self) -> None:
        self._stop.set()


def record_mic(cfg: Config, stop_event: threading.Event | None = None) -> Path:
    """Record audio; returns path to temporary WAV.

    If stop_event is provided, recording ends when the event is set (hotkey toggle)
    or on silence auto-stop, whichever comes first.
    """
    rec = Recorder(cfg)
    if stop_event is not None:
        watcher = threading.Thread(target=lambda: (stop_event.wait(), rec.stop()), daemon=True)
        watcher.start()
    return rec.record()
