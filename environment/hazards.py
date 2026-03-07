"""
environment/hazards.py
Road hazard crowdsourcing — local file-based store.

Drivers press a hotkey to report:
  P = pothole    A = animal    X = accident    D = debris

Reports are saved to logs/hazards.json with GPS-like timestamps.
Nearby hazards (within HAZARD_RADIUS_KM) trigger voice alerts.

In a real deployment this JSON would be replaced by a cloud API
(Firebase, Supabase, etc.) to share hazards between multiple vehicles.
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional


HAZARDS_FILE      = os.path.join("logs", "hazards.json")
HAZARD_EXPIRY_SEC = 3600        # hazards expire after 1 hour
HAZARD_RADIUS_KM  = 0.5         # alert if hazard within 500 m (placeholder)
MAX_HAZARDS       = 200


HAZARD_TYPES = {
    "p": ("pothole",  "Pothole reported ahead. Drive carefully."),
    "a": ("animal",   "Animal on road reported ahead. Reduce speed."),
    "x": ("accident", "Accident reported ahead. Slow down and proceed with caution."),
    "d": ("debris",   "Road debris reported ahead. Stay alert."),
    "f": ("flood",    "Flooding reported on this road. Find an alternate route."),
}

HAZARD_ICONS = {
    "pothole":  "🕳",
    "animal":   "🐄",
    "accident": "🚨",
    "debris":   "⚠",
    "flood":    "🌊",
}


@dataclass
class Hazard:
    kind:      str
    timestamp: float
    note:      str = ""

    @property
    def age_minutes(self) -> float:
        return (time.time() - self.timestamp) / 60.0

    @property
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > HAZARD_EXPIRY_SEC

    @property
    def display_str(self) -> str:
        icon = HAZARD_ICONS.get(self.kind, "⚠")
        age  = self.age_minutes
        return f"{icon} {self.kind.title()}  {age:.0f}m ago"


class HazardReporter:
    def __init__(self):
        os.makedirs("logs", exist_ok=True)
        self._hazards: list[Hazard] = []
        self._load()
        self._pending_voice: Optional[str] = None
        self._last_alert_t: dict[str, float] = {}

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        if not os.path.exists(HAZARDS_FILE):
            return
        try:
            with open(HAZARDS_FILE) as f:
                raw = json.load(f)
            self._hazards = [Hazard(**h) for h in raw
                             if not Hazard(**h).is_expired]
            print(f"[Hazards] Loaded {len(self._hazards)} active hazards.")
        except Exception as e:
            print(f"[Hazards] Load error: {e}")

    def _save(self):
        try:
            with open(HAZARDS_FILE, "w") as f:
                json.dump([asdict(h) for h in self._hazards], f, indent=2)
        except Exception as e:
            print(f"[Hazards] Save error: {e}")

    # ── Report ────────────────────────────────────────────────────────────────

    def report(self, key: str) -> Optional[str]:
        """
        Report a hazard by key (p/a/x/d/f).
        Returns confirmation message or None if key unknown.
        """
        if key not in HAZARD_TYPES:
            return None

        kind, _ = HAZARD_TYPES[key]
        hazard   = Hazard(kind=kind, timestamp=time.time())
        self._hazards.append(hazard)

        # Trim old / over-limit
        self._hazards = [h for h in self._hazards if not h.is_expired]
        self._hazards = self._hazards[-MAX_HAZARDS:]
        self._save()

        msg = f"{kind.title()} reported and saved."
        print(f"[Hazards] Reported: {kind}")
        return msg

    # ── Alert nearby hazards ──────────────────────────────────────────────────

    def update(self) -> Optional[str]:
        """
        Returns a voice alert string if there are recent active hazards
        that haven't been announced recently. Call every frame.
        """
        now     = time.time()
        active  = [h for h in self._hazards if not h.is_expired]
        self._hazards = active

        # Alert about hazards reported in the last 10 minutes
        # (in a real system this would be geo-filtered)
        for h in sorted(active, key=lambda x: x.timestamp, reverse=True):
            last = self._last_alert_t.get(h.kind, 0.0)
            if h.age_minutes < 10 and now - last > 120:   # re-alert every 2 min
                _, voice_msg = HAZARD_TYPES.get(h.kind, ("", ""))
                if voice_msg:
                    self._last_alert_t[h.kind] = now
                    return voice_msg
        return None

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def active_hazards(self) -> list[Hazard]:
        return [h for h in self._hazards if not h.is_expired]

    @property
    def recent_hazards(self) -> list[Hazard]:
        """Last 5 non-expired hazards for HUD display."""
        active = self.active_hazards
        return sorted(active, key=lambda h: h.timestamp, reverse=True)[:5]
