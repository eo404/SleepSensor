"""
safety/engine.py
Safety Awareness Engine — the brain of the system.

Connects:
  • Drowsiness state  (from core.state)
  • Drive timer       (safety.drive_timer)
  • Safety score      (safety.safety_score)
  • Voice engine      (safety.voice)

Architecture:
  Camera
     │
     ▼
  Drowsiness Detection
     │
     ▼
  Safety Awareness Engine
     │
     ├─ Fatigue Alerts
     ├─ Driving Time Monitoring
     ├─ Safety Messages
     └─ Driver Safety Score
     │
     ▼
  Driver Interface (HUD + Voice)
"""

from __future__ import annotations

import time
import random
from typing import Optional

from safety.voice import VoiceEngine
from safety.drive_timer import DriveTimer
from safety.safety_score import SafetyScore


# ── Message pools ─────────────────────────────────────────────────────────────

_FATIGUE_STAGE1 = [
    "Driver fatigue detected.",
    "Warning. Your eyes are closing. Stay focused.",
    "You seem drowsy. Please stay alert.",
    "Eyes closing. Please concentrate on the road.",
    "Take a deep breath and stay awake.",
]

_FATIGUE_STAGE2 = [
    "Danger! Pull over now and rest.",
    "You are falling asleep. Stop the vehicle safely.",
    "Critical drowsiness detected. Find a safe place to stop.",
    "Wake up! Your life is at risk. Pull over now.",
    "Please stop driving immediately. You need rest.",
    "Alert! Pull over now.",
]

_YAWN_MESSAGES = [
    "Yawn detected. Driver fatigue increasing.",
    "You are yawning. Consider taking a break soon.",
    "Frequent yawning is a sign of fatigue. Pull over when safe.",
]

_HEAD_POSE_MESSAGES = [
    "Head drooping detected. Please sit up straight.",
    "Your head is nodding. You may be falling asleep.",
    "Head position alert. Stay upright and alert.",
]

_CLEARED_MESSAGES = [
    "Good. Eyes open. Stay alert and drive safe.",
    "Welcome back. Keep focusing on the road.",
    "Stay alert. Take a break if you feel tired again.",
]

_SCORE_WARNING = {
    "AT RISK":   "Driver safety score is at risk. Please take a break.",
    "DANGEROUS": "Danger! Driver safety score is critical. Stop driving now.",
}

_PERIODIC_TIPS = [
    "Remember to stay hydrated while driving.",
    "Take a break every two hours for safer driving.",
    "If you feel tired, open the window or stop for fresh air.",
    "Coffee may help short term, but sleep is the only real cure for fatigue.",
    "Your safety and others' safety depends on your alertness.",
]

REPEAT_INTERVAL_SEC = 8.0    # repeat fatigue alerts every N seconds
PERIODIC_TIP_SEC = 300.0  # wellness tip every 5 minutes
SCORE_WARN_COOLDOWN = 60.0   # don't repeat score warning within this window
YAWN_VOICE_COOLDOWN = 30.0   # don't repeat yawn message within this window
HEAD_VOICE_COOLDOWN = 20.0   # don't repeat head-pose message within this window


class SafetyAwarenessEngine:
    def __init__(self):
        self.voice = VoiceEngine()
        self.drive_timer = DriveTimer()
        self.safety_score = SafetyScore()

        self._alarm_stage = 0
        self._last_repeat_t = 0.0
        self._last_tip_t = time.time()
        self._last_score_warn_t = 0.0
        self._last_yawn_voice_t = 0.0
        self._last_head_voice_t = 0.0
        self._prev_score_label = "SAFE"

        # Stats for score calculation
        self._bad_pose_frames = 0
        self._total_frames = 0

    # ── Main update (call every frame) ───────────────────────────────────────

    def update(self, state, det, alarm_stage: int, dt: float) -> None:
        now = time.time()

        # ── Drive timer ───────────────────────────────────────────────────────
        self.drive_timer.update(det.face_found, dt)
        drive_msg = self.drive_timer.pop_pending_message()
        if drive_msg:
            short, long_msg = drive_msg
            self.voice.say(long_msg, priority=False)

        # ── Safety score ──────────────────────────────────────────────────────
        self._total_frames += 1
        if state.bad_head_pose:
            self._bad_pose_frames += 1

        elapsed_hr = max(self.drive_timer.elapsed_minutes / 60.0, 0.001)
        yawn_per_hr = state.total_yawn_count / elapsed_hr
        pose_frac = self._bad_pose_frames / max(self._total_frames, 1)

        self.safety_score.update(
            drowsiness_score=state.score,
            yawn_count_per_hour=yawn_per_hr,
            bad_head_pose_fraction=pose_frac,
            drive_time_risk=self.drive_timer.risk_level,
        )

        # ── Score degradation warning ─────────────────────────────────────────
        label = self.safety_score.label
        if label in _SCORE_WARNING and label != self._prev_score_label:
            if now - self._last_score_warn_t > SCORE_WARN_COOLDOWN:
                self.voice.say(_SCORE_WARNING[label], priority=False)
                self._last_score_warn_t = now
        self._prev_score_label = label

        # ── Fatigue alarm alerts ──────────────────────────────────────────────
        prev_stage = self._alarm_stage

        if alarm_stage == 0 and prev_stage > 0:
            # Alarm cleared
            self.voice.say(random.choice(_CLEARED_MESSAGES), priority=True)

        elif alarm_stage == 1:
            if prev_stage == 0:
                # First trigger
                self.voice.say(random.choice(_FATIGUE_STAGE1), priority=True)
                self._last_repeat_t = now
            elif now - self._last_repeat_t >= REPEAT_INTERVAL_SEC:
                # Repeat while active
                self.voice.say(random.choice(_FATIGUE_STAGE1), priority=False)
                self._last_repeat_t = now

        elif alarm_stage == 2:
            if prev_stage < 2:
                # Escalation
                self.voice.say(random.choice(_FATIGUE_STAGE2), priority=True)
                self._last_repeat_t = now
            elif now - self._last_repeat_t >= REPEAT_INTERVAL_SEC:
                self.voice.say(random.choice(_FATIGUE_STAGE2), priority=False)
                self._last_repeat_t = now

        self._alarm_stage = alarm_stage

        # ── Yawn event voice ──────────────────────────────────────────────────
        if state.yawning and now - self._last_yawn_voice_t > YAWN_VOICE_COOLDOWN:
            if alarm_stage == 0:   # don't interrupt an active alarm
                self.voice.say_if_free(random.choice(_YAWN_MESSAGES))
            self._last_yawn_voice_t = now

        # ── Head pose voice ───────────────────────────────────────────────────
        if state.bad_head_pose and now - self._last_head_voice_t > HEAD_VOICE_COOLDOWN:
            if alarm_stage == 0:
                self.voice.say_if_free(random.choice(_HEAD_POSE_MESSAGES))
            self._last_head_voice_t = now

        # ── Periodic wellness tips ────────────────────────────────────────────
        if (alarm_stage == 0
                and now - self._last_tip_t > PERIODIC_TIP_SEC):
            self.voice.say_if_free(random.choice(_PERIODIC_TIPS))
            self._last_tip_t = now
