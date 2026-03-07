"""
environment/env_engine.py
Environment Awareness Engine — orchestrates:
  • WeatherMonitor    (weather-adaptive alerts)
  • HazardReporter    (crowdsourced road hazards)
  • NightModeDetector (auto low-light mode)
  • BlindSpotMonitor  (secondary camera / edge detection)
"""

from __future__ import annotations
import time

from environment.weather    import WeatherMonitor
from environment.hazards    import HazardReporter
from environment.night_mode import NightModeDetector
from environment.blind_spot import BlindSpotMonitor


class EnvironmentEngine:
    def __init__(self):
        self.weather    = WeatherMonitor()
        self.hazards    = HazardReporter()
        self.night_mode = NightModeDetector()
        self.blind_spot = BlindSpotMonitor()

        self._pending_voice: list[str] = []

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, frame, state) -> None:
        """
        Call every frame with the raw BGR frame and drowsiness state.
        Applies night-mode EAR/MAR threshold boosts to state directly.
        """
        # ── Night mode ────────────────────────────────────────────────────────
        night_msg = self.night_mode.update(frame)
        if night_msg:
            self._pending_voice.append(night_msg)

        # Apply threshold boosts from night mode + weather
        weather_mult  = self.weather.ear_threshold_multiplier
        night_boost   = self.night_mode.ear_threshold_boost
        base_threshold = state.ear_threshold
        state.ear_threshold = base_threshold * weather_mult + night_boost

        # ── Weather ───────────────────────────────────────────────────────────
        weather_msg = self.weather.update()
        if weather_msg:
            self._pending_voice.append(weather_msg)

        # ── Hazards ───────────────────────────────────────────────────────────
        hazard_msg = self.hazards.update()
        if hazard_msg:
            self._pending_voice.append(hazard_msg)

        # ── Blind spot (fallback edge mode) ───────────────────────────────────
        if not self.blind_spot.using_secondary_camera:
            bs_msg = self.blind_spot.update_from_frame(frame)
        else:
            bs_msg = self.blind_spot.update()
        if bs_msg:
            self._pending_voice.append(bs_msg)

    def handle_key(self, key: str) -> str | None:
        """
        Handle hotkey press for hazard reporting.
        key: 'p' pothole | 'a' animal | 'x' accident | 'd' debris | 'f' flood
        Returns confirmation message or None.
        """
        return self.hazards.report(key)

    def pop_voice_messages(self) -> list[str]:
        """Returns and clears all pending voice messages."""
        msgs = self._pending_voice.copy()
        self._pending_voice.clear()
        return msgs

    def get_night_frame(self, frame):
        """Return night-enhanced frame if in night mode, else original."""
        return self.night_mode.apply_night_enhancement(frame)

    def close(self):
        self.blind_spot.close()
