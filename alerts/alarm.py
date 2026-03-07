"""
alerts/alarm.py
Escalating alarm with rotating voice safety advice.

Stage 0 – silent
Stage 1 – soft beep + first voice warning
Stage 2 – loud alarm + urgent voice advice, cycling every ADVICE_INTERVAL_SEC
"""

import time
import random
import threading
import pygame

from config import ALARM_FILE


# ── Safety advice library ─────────────────────────────────────────────────────

STAGE1_PHRASES = [
    "You seem drowsy. Please stay alert.",
    "Warning. Your eyes are closing. Stay focused.",
    "Drowsiness detected. Take a deep breath.",
    "Stay awake. You are driving.",
    "Eyes closing. Please concentrate on the road.",
]

STAGE2_PHRASES = [
    "Danger! Pull over now and rest.",
    "You are falling asleep! Stop the vehicle safely.",
    "Critical drowsiness! Find a safe place to stop immediately.",
    "Wake up! Your life is at risk. Pull over.",
    "Severe drowsiness detected. Do not continue driving.",
    "Please stop driving immediately. You need rest.",
    "Alert! You are a danger to yourself and others. Pull over now.",
]

CLEARED_PHRASES = [
    "Good. Eyes open. Stay alert and drive safe.",
    "Welcome back. Keep focusing on the road.",
    "Stay alert. Take a break if you feel tired.",
]

ADVICE_INTERVAL_SEC = 8.0  # how often to repeat advice while alarm is active


# ── Helpers ───────────────────────────────────────────────────────────────────

class DummySound:
    def play(self, loops=0):
        print("[Alarm] Sound file not found – using DummySound.")

    def stop(self):
        pass

    def set_volume(self, v):
        pass


def _load_sound(path: str):
    pygame.mixer.init()
    try:
        return pygame.mixer.Sound(path)
    except pygame.error as e:
        print(f"[Alarm] Could not load sound '{path}': {e}")
        return DummySound()


# ── AlarmManager ─────────────────────────────────────────────────────────────

class AlarmManager:
    def __init__(self):
        self._sound = _load_sound(ALARM_FILE)
        self._stage = 0
        self._tts_lock = threading.Lock()
        self._tts_engine = self._init_tts()
        self._advice_thread = None
        self._stop_advice = threading.Event()

    # ── TTS engine ────────────────────────────────────────────────────────────

    def _init_tts(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 155)
            engine.setProperty("volume", 1.0)
            # Pick a clear voice if available
            voices = engine.getProperty("voices")
            for v in voices:
                if "english" in v.name.lower() or "zira" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            return engine
        except Exception as e:
            print(
                f"[Alarm] TTS unavailable: {e}. Install pyttsx3 for voice advice.")
            return None

    def _speak(self, text: str, interrupt: bool = False):
        """Speak text in a background thread. If interrupt=True, skip if already speaking."""
        if self._tts_engine is None:
            print(f"[Voice] {text}")
            return

        if interrupt and self._tts_lock.locked():
            return  # don't queue up behind an ongoing phrase

        def _run():
            with self._tts_lock:
                try:
                    self._tts_engine.say(text)
                    self._tts_engine.runAndWait()
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    # ── Repeating advice loop (runs while stage > 0) ──────────────────────────

    def _start_advice_loop(self):
        """Start (or restart) the repeating advice loop."""
        # Stop any existing loop
        self._stop_advice_loop()
        self._stop_advice.clear()

        def _loop():
            # Speak immediately, then repeat every ADVICE_INTERVAL_SEC
            while not self._stop_advice.is_set():
                pool = STAGE2_PHRASES if self._stage >= 2 else STAGE1_PHRASES
                self._speak(random.choice(pool), interrupt=True)

                # Wait for the next cycle, but remain responsive to stop requests
                # (sleep in small increments instead of a single long sleep)
                step = 0.1
                steps = int(ADVICE_INTERVAL_SEC / step)
                for _ in range(max(1, steps)):
                    if self._stop_advice.is_set():
                        return
                    time.sleep(step)

        self._advice_thread = threading.Thread(target=_loop, daemon=True)
        self._advice_thread.start()

    def _stop_advice_loop(self):
        self._stop_advice.set()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def stage(self) -> int:
        return self._stage

    def set_stage(self, desired: int, previous_stage: int):
        if desired == self._stage:
            return

        if desired == 0:
            # Alarm clearing
            self._sound.stop()
            self._stop_advice_loop()
            self._stage = 0
            if previous_stage > 0:
                self._speak(random.choice(CLEARED_PHRASES))

        elif desired == 1:
            self._sound.set_volume(0.4)
            if self._stage == 0:
                self._sound.play(loops=-1)
                self._start_advice_loop()
            self._stage = 1

        elif desired == 2:
            self._sound.set_volume(1.0)
            if self._stage == 0:
                self._sound.play(loops=-1)
                self._start_advice_loop()
            if previous_stage < 2:
                # Escalation — speak urgently
                self._speak(random.choice(STAGE2_PHRASES), interrupt=False)
            self._stage = 2

    def stop(self):
        self._stop_advice_loop()
        self._sound.stop()
        self._stage = 0
