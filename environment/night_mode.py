"""
environment/night_mode.py
Detects ambient light level from the camera frame and automatically:
  • Switches to night mode when light drops below threshold
  • Tightens EAR / MAR thresholds (drowsiness is harder to see in dark)
  • Boosts camera brightness hint via OpenCV
  • Issues a voice advisory when mode changes
"""

from __future__ import annotations
import time
import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class NightModeConfig:
    dark_threshold:   float = 60.0    # mean pixel brightness (0-255) below = night
    bright_threshold: float = 90.0    # above = day (hysteresis gap prevents flicker)
    ear_boost:        float = 0.03    # add to EAR threshold in night mode (stricter)
    mar_boost:        float = 0.05    # add to MAR threshold in night mode
    smoothing:        int   = 30      # frames to average brightness over


class NightModeDetector:
    def __init__(self, config: NightModeConfig | None = None):
        self._cfg          = config or NightModeConfig()
        self._is_night     = False
        self._brightness_history: list[float] = []
        self._last_mode_change = 0.0
        self._mode_change_voice: str | None = None

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, frame) -> str | None:
        """
        Pass the raw BGR frame each loop.
        Returns a voice message if mode just changed, else None.
        """
        brightness = self._measure_brightness(frame)
        self._brightness_history.append(brightness)
        if len(self._brightness_history) > self._cfg.smoothing:
            self._brightness_history.pop(0)

        avg = sum(self._brightness_history) / len(self._brightness_history)
        prev_night = self._is_night

        if not self._is_night and avg < self._cfg.dark_threshold:
            self._is_night = True
        elif self._is_night and avg > self._cfg.bright_threshold:
            self._is_night = False

        if self._is_night != prev_night:
            self._last_mode_change = time.time()
            if self._is_night:
                return ("Night driving mode activated. "
                        "Drowsiness detection sensitivity increased.")
            else:
                return "Daytime mode restored."
        return None

    # ── Brightness measurement ────────────────────────────────────────────────

    def _measure_brightness(self, frame) -> float:
        """
        Convert to grayscale and measure mean brightness.
        Uses centre 50% of frame to ignore dark borders/dashboards.
        """
        h, w = frame.shape[:2]
        cy1, cy2 = h // 4, 3 * h // 4
        cx1, cx2 = w // 4, 3 * w // 4
        roi  = frame[cy1:cy2, cx1:cx2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        return float(np.mean(gray))

    # ── Camera adaptation ─────────────────────────────────────────────────────

    def apply_night_enhancement(self, frame):
        """
        Apply CLAHE (contrast limited adaptive histogram equalisation)
        to improve face mesh visibility in low light.
        Returns enhanced frame (does NOT modify original).
        """
        if not self._is_night:
            return frame

        lab   = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_eq  = clahe.apply(l)
        enhanced = cv2.cvtColor(cv2.merge([l_eq, a, b]), cv2.COLOR_LAB2BGR)
        return enhanced

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def is_night(self) -> bool:
        return self._is_night

    @property
    def brightness(self) -> float:
        if not self._brightness_history:
            return 128.0
        return sum(self._brightness_history) / len(self._brightness_history)

    @property
    def ear_threshold_boost(self) -> float:
        return self._cfg.ear_boost if self._is_night else 0.0

    @property
    def mar_threshold_boost(self) -> float:
        return self._cfg.mar_boost if self._is_night else 0.0

    @property
    def status_str(self) -> str:
        mode = "NIGHT" if self._is_night else "DAY"
        return f"{mode}  lux~{self.brightness:.0f}"

    @property
    def color(self):
        """BGR colour for HUD label."""
        return (0, 180, 255) if self._is_night else (50, 220, 50)
