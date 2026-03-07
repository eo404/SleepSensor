"""
safety/drive_timer.py
Tracks continuous driving time and issues escalating break reminders.

Break schedule (configurable in config.py):
  • 30 min  → gentle reminder
  • 60 min  → strong recommendation
  • 90 min  → urgent warning
  • 120 min → critical — stop immediately
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DriveTimerConfig:
    reminders_min: list[int] = field(
        default_factory=lambda: [30, 60, 90, 120]
    )
    face_absence_reset_sec: float = 60.0   # reset timer if no face this long


REMINDER_MESSAGES = {
    30:  ("Long driving detected – recommended break.",
          "You have been driving for 30 minutes. Consider taking a short break."),
    60:  ("One hour of driving detected.",
          "You have been driving for one hour. Please take a 15-minute break soon."),
    90:  ("Ninety minutes of continuous driving.",
          "Driving fatigue increases significantly after 90 minutes. Stop when safe."),
    120: ("Two hours of continuous driving. This is dangerous.",
          "You have been driving for two hours. Stop immediately and rest."),
}


class DriveTimer:
    def __init__(self, config: Optional[DriveTimerConfig] = None):
        self._cfg = config or DriveTimerConfig()
        self._start_t = time.time()
        self._elapsed_sec = 0.0
        self._no_face_since: Optional[float] = None
        self._fired: set[int] = set()       # which milestones already spoken
        # (short, long)
        self._pending_message: Optional[tuple[str, str]] = None

    # ── Update (call every frame) ─────────────────────────────────────────────

    def update(self, face_found: bool, dt: float) -> None:
        if face_found:
            self._no_face_since = None
            self._elapsed_sec += dt
            self._check_milestones()
        else:
            if self._no_face_since is None:
                self._no_face_since = time.time()
            elif time.time() - self._no_face_since > self._cfg.face_absence_reset_sec:
                # Driver likely left vehicle — reset
                self._elapsed_sec = 0.0
                self._fired = set()
                self._no_face_since = None

    def _check_milestones(self):
        elapsed_min = self._elapsed_sec / 60.0
        for mins in self._cfg.reminders_min:
            if elapsed_min >= mins and mins not in self._fired:
                self._fired.add(mins)
                self._pending_message = REMINDER_MESSAGES.get(
                    mins,
                    (f"You have been driving for {mins} minutes.",
                     f"You have been driving for {mins} minutes. Take a break.")
                )

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def elapsed_minutes(self) -> float:
        return self._elapsed_sec / 60.0

    @property
    def elapsed_str(self) -> str:
        total = int(self._elapsed_sec)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m:02d}m {s:02d}s"
        return f"{m:02d}m {s:02d}s"

    @property
    def risk_level(self) -> int:
        """0=low 1=moderate 2=high 3=critical based on drive time."""
        m = self.elapsed_minutes
        if m >= 120:
            return 3
        if m >= 90:
            return 2
        if m >= 60:
            return 1
        return 0

    def pop_pending_message(self) -> Optional[tuple[str, str]]:
        """Returns (short_msg, long_msg) if a milestone was just crossed, else None."""
        msg = self._pending_message
        self._pending_message = None
        return msg
