# alerts package

import os
import threading
import pygame

from config import ALARM_FILE


class DummySound:
    def play(self, loops=0): print("[Alarm] Sound file not found – DummySound.")
    def stop(self): pass
    def set_volume(self, v): pass


def _load_sound(path: str):
    pygame.mixer.init()
    try:
        return pygame.mixer.Sound(path)
    except pygame.error as e:
        print(f"[Alarm] Error loading {path}: {e}")
        return DummySound()


class AlarmManager:
    def __init__(self):
        self._sound      = _load_sound(ALARM_FILE)
        self._stage      = 0          # 0=off 1=soft 2=loud
        self._tts_lock   = threading.Lock()
        self._tts_engine = self._init_tts()

    # ── TTS ───────────────────────────────────────────────────────────────────

    def _init_tts(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            return engine
        except Exception:
            return None

    def _speak(self, text: str):
        if self._tts_engine is None:
            return
        def _run():
            with self._tts_lock:
                try:
                    self._tts_engine.say(text)
                    self._tts_engine.runAndWait()
                except Exception:
                    pass
        threading.Thread(target=_run, daemon=True).start()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def stage(self) -> int:
        return self._stage

    def set_stage(self, desired: int, previous_stage: int):
        """Transition to a new alarm stage."""
        if desired == self._stage:
            return

        if desired == 0:
            self._sound.stop()
            self._stage = 0

        elif desired == 1:
            self._sound.set_volume(0.4)
            if self._stage == 0:
                self._sound.play(loops=-1)
            self._stage = 1

        elif desired == 2:
            self._sound.set_volume(1.0)
            if self._stage == 0:
                self._sound.play(loops=-1)
            self._stage = 2
            # Voice alert on first escalation to stage 2
            if previous_stage < 2:
                self._speak("Wake up! You are falling asleep!")

    def stop(self):
        self._sound.stop()
        self._stage = 0