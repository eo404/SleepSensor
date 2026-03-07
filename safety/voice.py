"""
safety/voice.py
Single persistent TTS worker thread.
All other modules call VoiceEngine.say() — non-blocking from any thread.
"""

from __future__ import annotations
import queue
import threading
import time


class VoiceEngine:
    """
    pyttsx3 must be created AND used on the same thread.
    We spin up one daemon thread that owns the engine forever
    and reads phrases from a Queue.
    """

    def __init__(self):
        self._q = queue.Queue()
        self._speaking = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="TTS-Worker")
        self._thread.start()

    # ── Public API ────────────────────────────────────────────────────────────

    def say(self, text: str, priority: bool = False) -> None:
        """
        Queue a phrase for speaking.
        priority=True clears any pending phrases first so this plays next.
        """
        if priority:
            self._drain()
        self._q.put(text)

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def say_if_free(self, text: str) -> bool:
        """Speak only if nothing is currently being said. Returns True if queued."""
        if not self.is_speaking() and self._q.empty():
            self._q.put(text)
            return True
        return False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _drain(self):
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

    def _run(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 150)
            engine.setProperty("volume", 1.0)

            # Prefer a clear English voice
            for v in engine.getProperty("voices"):
                name = v.name.lower()
                if any(k in name for k in ("zira", "david", "english", "hazel")):
                    engine.setProperty("voice", v.id)
                    break

            print("[Voice] TTS engine ready.")

            while True:
                text = self._q.get()          # blocks until phrase available
                self._speaking.set()
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception as e:
                    print(f"[Voice] TTS error: {e}")
                finally:
                    self._speaking.clear()

        except Exception as e:
            print(f"[Voice] pyttsx3 unavailable: {e}")
            print("[Voice] Install pyttsx3 for voice alerts:  pip install pyttsx3")
            # Fallback: print to console
            while True:
                text = self._q.get()
                print(f"[Voice] {text}")
