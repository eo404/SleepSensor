"""
alerts/alarm.py  –  voice-only alerts, no pygame, no ALARM_FILE
"""

from __future__ import annotations
import time
import random
import threading
import queue


STAGE1_PHRASES = [
    "You seem drowsy. Please stay alert.",
    "Warning. Your eyes are closing. Stay focused.",
    "Driver fatigue detected. Take a deep breath.",
    "Stay awake. You are driving.",
    "Eyes closing. Please concentrate on the road.",
]

STAGE2_PHRASES = [
    "Danger! Pull over now and rest.",
    "You are falling asleep! Stop the vehicle safely.",
    "Critical drowsiness! Find a safe place to stop immediately.",
    "Wake up! Your life is at risk. Pull over.",
    "Please stop driving immediately. You need rest.",
]

CLEARED_PHRASES = [
    "Good. Eyes open. Stay alert and drive safe.",
    "Welcome back. Keep focusing on the road.",
    "Stay alert. Take a break if you feel tired.",
]

ADVICE_INTERVAL_SEC = 8.0


class _TTSWorker:
    """Single daemon thread owns the pyttsx3 engine; receives phrases via queue."""

    def __init__(self):
        self._q = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def say(self, text: str, clear: bool = False) -> None:
        if clear:
            while not self._q.empty():
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break
        self._q.put(text)

    def _run(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 155)
            engine.setProperty("volume", 1.0)
            for v in engine.getProperty("voices"):
                if "english" in v.name.lower() or "zira" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            while True:
                text = self._q.get()
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception:
                    pass
        except Exception as e:
            print(f"[Voice] TTS unavailable: {e}. Install pyttsx3.")
            while True:
                print(f"[Voice] {self._q.get()}")


class AlarmManager:
    def __init__(self):
        self._stage = 0
        self._tts = _TTSWorker()
        self._stop_loop = threading.Event()
        self._loop_thread = None

    def _start_advice_loop(self):
        self._stop_loop.clear()

        def _loop():
            while not self._stop_loop.wait(timeout=ADVICE_INTERVAL_SEC):
                if self._stop_loop.is_set():
                    break
                pool = STAGE2_PHRASES if self._stage >= 2 else STAGE1_PHRASES
                self._tts.say(random.choice(pool), clear=True)

        self._loop_thread = threading.Thread(target=_loop, daemon=True)
        self._loop_thread.start()

    def _stop_advice_loop(self):
        self._stop_loop.set()

    @property
    def stage(self) -> int:
        return self._stage

    def set_stage(self, desired: int, previous_stage: int) -> None:
        if desired == self._stage:
            return

        if desired == 0:
            self._stop_advice_loop()
            self._stage = 0
            if previous_stage > 0:
                self._tts.say(random.choice(CLEARED_PHRASES), clear=True)

        elif desired == 1:
            if self._stage == 0:
                self._tts.say(random.choice(STAGE1_PHRASES), clear=True)
                self._start_advice_loop()
            self._stage = 1

        elif desired == 2:
            if self._stage == 0:
                self._start_advice_loop()
            if previous_stage < 2:
                self._tts.say(random.choice(STAGE2_PHRASES), clear=True)
            self._stage = 2

    def stop(self):
        self._stop_advice_loop()
        self._stage = 0
