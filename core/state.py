"""
core/state.py
Drowsiness state machine: timers, scoring, event tracking.
"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from config import (
    EAR_THRESHOLD_DEFAULT, EAR_CONSEC_FRAMES,
    MAR_THRESHOLD, MAR_CONSEC_FRAMES, YAWN_COOLDOWN_SEC,
    PITCH_DROWSY_DEG, HEAD_POSE_CONSEC,
    EYES_CLOSED_TRIGGER_SECONDS, EYES_OPEN_CLEAR_SECONDS,
    NO_FACE_DECAY_RATE, ALARM_STAGE1_SEC, ALARM_STAGE2_SEC,
    SCORE_CLOSED_PER_SEC, SCORE_YAWN_EVENT, SCORE_HEAD_POSE,
    SCORE_DECAY_PER_SEC, EAR_HISTORY_LEN,
    CALIBRATION_SECONDS,
)


@dataclass
class DrowsinessEvent:
    kind: str           # "closed", "yawn", "head_pose"
    timestamp: float
    duration: float = 0.0


class DrowsinessState:
    def __init__(self):
        self.ear_threshold = EAR_THRESHOLD_DEFAULT

        # Timers
        self.eyes_closed_seconds: float = 0.0
        self.eyes_open_seconds:   float = 0.0

        # Consecutive-frame counters (noise guards)
        self.consec_closed:    int = 0
        self.consec_yawn:      int = 0
        self.consec_head_pose: int = 0

        # Status flags
        self.eyes_confirmed_closed: bool = False
        self.yawning:               bool = False
        self.bad_head_pose:         bool = False

        # Alarm
        self.alarm_stage: int = 0   # 0=off 1=soft 2=loud
        self._closed_event_start: Optional[float] = None

        # Drowsiness score (0–100)
        self.score: float = 0.0

        # Event log
        self.events: list[DrowsinessEvent] = []

        # Yawn cooldown
        self._last_yawn_t: float = 0.0

        # EAR history for graph
        self.ear_history: deque = deque([0.0] * EAR_HISTORY_LEN,
                                        maxlen=EAR_HISTORY_LEN)

        # Session stats
        self.session_start = time.time()
        self.total_closed_sec:   float = 0.0
        self.total_yawn_count:   int   = 0
        self.total_alarm_count:  int   = 0

        # Calibration
        self.calibrating:       bool  = False
        self._calib_ears:       list  = []
        self._calib_start:      float = 0.0

    # ── Calibration ───────────────────────────────────────────────────────────

    def start_calibration(self):
        self.calibrating    = True
        self._calib_ears    = []
        self._calib_start   = time.time()

    def feed_calibration(self, ear: float) -> bool:
        """Feed an EAR sample; returns True when calibration is complete."""
        if not self.calibrating:
            return False
        self._calib_ears.append(ear)
        if time.time() - self._calib_start >= CALIBRATION_SECONDS:
            if self._calib_ears:
                mean = sum(self._calib_ears) / len(self._calib_ears)
                self.ear_threshold = mean * 0.75   # 75 % of open-eye baseline
            self.calibrating = False
            return True
        return False

    @property
    def calib_progress(self) -> float:
        """0.0 – 1.0 calibration progress."""
        if not self.calibrating:
            return 0.0
        return min((time.time() - self._calib_start) / CALIBRATION_SECONDS, 1.0)

    # ── Per-frame update ──────────────────────────────────────────────────────

    def update(self, det, dt: float):
        """
        det  – DetectionResult from core.detector
        dt   – elapsed seconds since last frame
        """
        dt = min(dt, 0.2)

        # Always push EAR to history
        self.ear_history.append(det.mean_ear if det.face_found else 0.0)

        if not det.face_found:
            self._handle_no_face(dt)
            return

        if self.calibrating:
            done = self.feed_calibration(det.mean_ear)
            return

        self._handle_eyes(det, dt)
        self._handle_yawn(det)
        self._handle_head_pose(det, dt)
        self._update_score(dt)

    def _handle_no_face(self, dt):
        self.eyes_closed_seconds = max(0.0, self.eyes_closed_seconds - dt * NO_FACE_DECAY_RATE)
        self.eyes_open_seconds   = max(0.0, self.eyes_open_seconds   - dt * NO_FACE_DECAY_RATE)
        self.consec_closed = 0
        self.eyes_confirmed_closed = False

    def _handle_eyes(self, det, dt):
        below = det.mean_ear < self.ear_threshold
        if below:
            self.consec_closed += 1
        else:
            self.consec_closed = 0

        self.eyes_confirmed_closed = self.consec_closed >= EAR_CONSEC_FRAMES

        if self.eyes_confirmed_closed:
            self.eyes_closed_seconds += dt
            self.eyes_open_seconds    = 0.0
            self.total_closed_sec    += dt
            if self._closed_event_start is None:
                self._closed_event_start = time.time()
        else:
            if self._closed_event_start is not None:
                dur = time.time() - self._closed_event_start
                if dur >= EYES_CLOSED_TRIGGER_SECONDS:
                    self.events.append(
                        DrowsinessEvent("closed", self._closed_event_start, dur)
                    )
                self._closed_event_start = None
            self.eyes_open_seconds  += dt
            self.eyes_closed_seconds = 0.0

    def _handle_yawn(self, det):
        yawning_now = det.mar > MAR_THRESHOLD
        if yawning_now:
            self.consec_yawn += 1
        else:
            self.consec_yawn = 0

        was_yawning = self.yawning
        self.yawning = self.consec_yawn >= MAR_CONSEC_FRAMES

        now = time.time()
        if self.yawning and not was_yawning:
            if now - self._last_yawn_t > YAWN_COOLDOWN_SEC:
                self.score           += SCORE_YAWN_EVENT
                self.total_yawn_count += 1
                self.events.append(DrowsinessEvent("yawn", now))
                self._last_yawn_t = now

    def _handle_head_pose(self, det, dt):
        if det.head_pose is None:
            self.consec_head_pose = 0
            self.bad_head_pose    = False
            return

        pitch = det.head_pose[0]
        if abs(pitch) > PITCH_DROWSY_DEG:
            self.consec_head_pose += 1
        else:
            self.consec_head_pose = 0

        self.bad_head_pose = self.consec_head_pose >= HEAD_POSE_CONSEC

        if self.bad_head_pose:
            self.score += SCORE_HEAD_POSE * 0.016   # approx per-frame at 60 fps

    def _update_score(self, dt):
        if self.eyes_confirmed_closed:
            self.score += SCORE_CLOSED_PER_SEC * dt

        # Decay when alert
        if not self.eyes_confirmed_closed and not self.yawning and not self.bad_head_pose:
            self.score = max(0.0, self.score - SCORE_DECAY_PER_SEC * dt)

        self.score = min(self.score, 100.0)

    # ── Alarm stage ───────────────────────────────────────────────────────────

    def desired_alarm_stage(self) -> int:
        if self.eyes_closed_seconds >= ALARM_STAGE2_SEC:
            return 2
        if self.eyes_closed_seconds >= ALARM_STAGE1_SEC:
            return 1
        return 0

    def should_clear_alarm(self) -> bool:
        return (
            self.eyes_open_seconds >= EYES_OPEN_CLEAR_SECONDS
            and self.alarm_stage > 0
        )
