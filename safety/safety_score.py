"""
safety/safety_score.py
Driver Safety Score (0–100, higher = safer).

Deducted by:
  • Drowsiness score from state machine
  • Yawn frequency
  • Head pose violations
  • Drive time risk level

Score bands:
  100–80  SAFE      (green)
   79–60  CAUTION   (yellow)
   59–40  AT RISK   (orange)
   39–0   DANGEROUS (red)
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class SafetyScoreWeights:
    drowsiness_weight: float = 0.50   # 50 % from drowsiness state score
    yawn_weight:       float = 0.20   # 20 % from yawn rate
    head_pose_weight:  float = 0.15   # 15 % from head pose
    drive_time_weight: float = 0.15   # 15 % from drive time risk


SCORE_LABELS = {
    (80, 100): ("SAFE",      (50,  220,  50)),   # green  (BGR)
    (60,  79): ("CAUTION",   (0,   200, 220)),   # yellow
    (40,  59): ("AT RISK",   (0,   140, 255)),   # orange
    (0,  39): ("DANGEROUS", (30,   30, 230)),   # red
}


class SafetyScore:
    def __init__(self, weights: SafetyScoreWeights | None = None):
        self._w = weights or SafetyScoreWeights()
        self.score = 100.0
        self._history: list[float] = []

    def update(self, drowsiness_score: float, yawn_count_per_hour: float,
               bad_head_pose_fraction: float, drive_time_risk: int) -> None:
        """
        drowsiness_score        – 0–100 from state machine (higher = worse)
        yawn_count_per_hour     – normalised yawn frequency
        bad_head_pose_fraction  – 0–1, fraction of recent frames with bad pose
        drive_time_risk         – 0–3 from DriveTimer.risk_level
        """
        # Convert each signal to a 0–100 penalty
        drowsy_penalty = drowsiness_score                              # already 0-100
        yawn_penalty = min(yawn_count_per_hour / 20.0, 1.0) * \
            100   # 20 yawns/hr = max
        pose_penalty = bad_head_pose_fraction * 100
        time_penalty = (drive_time_risk / 3.0) * \
            100                # 0-3 → 0-100

        total_penalty = (
            self._w.drowsiness_weight * drowsy_penalty +
            self._w.yawn_weight * yawn_penalty +
            self._w.head_pose_weight * pose_penalty +
            self._w.drive_time_weight * time_penalty
        )

        self.score = max(0.0, min(100.0, 100.0 - total_penalty))
        self._history.append(self.score)
        if len(self._history) > 300:
            self._history.pop(0)

    @property
    def label(self) -> str:
        for (lo, hi), (label, _) in SCORE_LABELS.items():
            if lo <= self.score <= hi:
                return label
        return "UNKNOWN"

    @property
    def color(self):
        """BGR colour matching the current band."""
        for (lo, hi), (_, color) in SCORE_LABELS.items():
            if lo <= self.score <= hi:
                return color
        return (240, 240, 240)

    @property
    def trend(self) -> str:
        """↑ improving  ↓ worsening  → stable"""
        if len(self._history) < 30:
            return "→"
        recent = sum(self._history[-10:]) / 10
        older = sum(self._history[-30:-20]) / 10
        diff = recent - older
        if diff > 3:
            return "↑"
        if diff < -3:
            return "↓"
        return "→"
