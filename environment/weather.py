"""
environment/weather.py
Real-time weather monitoring via OpenWeatherMap API.

Fetches weather every POLL_INTERVAL_SEC and issues voice + HUD alerts
based on conditions: rain, fog, snow, storm, extreme heat/cold.

Setup:
  1. Get a free API key at https://openweathermap.org/api
  2. Set it in config.py:  WEATHER_API_KEY = "your_key_here"
     OR set env var:       OPENWEATHER_API_KEY=your_key
"""

from __future__ import annotations
import threading
import time
import os
import json
from dataclasses import dataclass, field
from typing import Optional

try:
    import urllib.request as _urllib
except ImportError:
    _urllib = None

from config import (
    WEATHER_API_KEY,
    WEATHER_CITY,
    WEATHER_POLL_INTERVAL_SEC,
    WEATHER_UNITS,
)


# ── Weather condition codes → advisory ───────────────────────────────────────
# OpenWeatherMap condition code ranges:
#   2xx Thunderstorm  3xx Drizzle  5xx Rain  6xx Snow
#   7xx Atmosphere (fog/haze/dust)  800 Clear  80x Clouds

@dataclass
class WeatherAdvisory:
    condition:   str         # e.g. "Rain"
    description: str         # e.g. "moderate rain"
    temp_c:      float = 0.0
    wind_mps:    float = 0.0
    visibility_m:float = 10000.0
    code:        int   = 800

    # Derived risk level 0–3
    @property
    def risk_level(self) -> int:
        if self.code in range(200, 300):   return 3  # thunderstorm
        if self.code in range(600, 700):   return 2  # snow
        if self.code in range(500, 600):   return 2  # rain
        if self.code in range(300, 400):   return 1  # drizzle
        if self.code in (741, 721, 711):   return 2  # fog/smoke/haze
        if self.code in range(700, 800):   return 1  # atmosphere
        if self.wind_mps > 15:             return 2  # strong wind
        if self.visibility_m < 1000:       return 3  # very low visibility
        return 0

    @property
    def risk_color(self):
        """BGR colour for HUD."""
        return {0: (50,220,50), 1:(0,220,220), 2:(0,140,255), 3:(30,30,230)}.get(
            self.risk_level, (240,240,240))

    @property
    def voice_message(self) -> Optional[str]:
        c = self.code
        if c in range(200, 300):
            return ("Thunderstorm detected. Reduce speed significantly "
                    "and increase following distance.")
        if c in range(500, 510):
            return "Rain detected. Wet road ahead. Increase following distance."
        if c in range(510, 600):
            return "Heavy rain detected. Reduce speed and drive with caution."
        if c in range(300, 400):
            return "Drizzle detected. Roads may be slippery."
        if c in range(600, 700):
            return "Snow detected. Drive slowly and increase following distance."
        if c == 741:
            return "Fog detected. Reduce speed and use fog lights."
        if c in (721, 711, 731, 751, 761, 762):
            return "Poor visibility due to haze or dust. Drive carefully."
        if self.wind_mps > 15:
            return f"Strong wind detected at {self.wind_mps:.0f} metres per second. Hold the steering wheel firmly."
        if self.visibility_m < 1000:
            return "Very low visibility. Reduce speed immediately."
        return None


class WeatherMonitor:
    def __init__(self):
        self._api_key    = WEATHER_API_KEY or os.environ.get("OPENWEATHER_API_KEY", "")
        self._city       = WEATHER_CITY
        self._units      = WEATHER_UNITS
        self._advisory: Optional[WeatherAdvisory] = None
        self._last_fetch = 0.0
        self._error      = ""
        self._lock       = threading.Lock()
        self._last_voice_t = 0.0

        if self._api_key:
            # Fetch immediately in background
            threading.Thread(target=self._fetch, daemon=True).start()
        else:
            self._error = "No API key – set WEATHER_API_KEY in config.py"
            print(f"[Weather] {self._error}")

    # ── Fetch ─────────────────────────────────────────────────────────────────

    def _fetch(self):
        try:
            url = (f"https://api.openweathermap.org/data/2.5/weather"
                   f"?q={self._city}&appid={self._api_key}"
                   f"&units={'metric' if self._units == 'metric' else 'imperial'}")
            with _urllib.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            weather   = data["weather"][0]
            main_data = data["main"]
            wind_data = data.get("wind", {})
            vis       = data.get("visibility", 10000)

            advisory = WeatherAdvisory(
                condition    = weather["main"],
                description  = weather["description"],
                temp_c       = main_data["temp"],
                wind_mps     = wind_data.get("speed", 0.0),
                visibility_m = vis,
                code         = weather["id"],
            )
            with self._lock:
                self._advisory   = advisory
                self._last_fetch = time.time()
                self._error      = ""

            print(f"[Weather] {advisory.condition} – {advisory.description} "
                  f"| Risk: {advisory.risk_level} | Temp: {advisory.temp_c:.1f}°")

        except Exception as e:
            with self._lock:
                self._error = str(e)
            print(f"[Weather] Fetch error: {e}")

    def _poll_if_due(self):
        if not self._api_key:
            return
        if time.time() - self._last_fetch > WEATHER_POLL_INTERVAL_SEC:
            threading.Thread(target=self._fetch, daemon=True).start()

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self) -> Optional[str]:
        """
        Call every frame. Returns a voice message string if a new
        advisory should be spoken, else None.
        """
        self._poll_if_due()

        with self._lock:
            adv = self._advisory

        if adv is None:
            return None

        # Speak advisory once per fetch cycle (not every frame)
        now = time.time()
        msg = adv.voice_message
        if msg and now - self._last_voice_t > WEATHER_POLL_INTERVAL_SEC * 0.9:
            self._last_voice_t = now
            return msg
        return None

    @property
    def advisory(self) -> Optional[WeatherAdvisory]:
        with self._lock:
            return self._advisory

    @property
    def error(self) -> str:
        return self._error

    @property
    def ear_threshold_multiplier(self) -> float:
        """
        Increase drowsiness sensitivity in bad weather.
        Returns a multiplier for EAR threshold (>1 = stricter).
        """
        adv = self.advisory
        if adv is None:
            return 1.0
        return {0: 1.0, 1: 1.05, 2: 1.10, 3: 1.15}.get(adv.risk_level, 1.0)
