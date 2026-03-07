"""
logs/logger.py
Writes drowsy events and per-frame metrics to CSV files under logs/sessions/.
"""

import csv
import os
import time
from datetime import datetime


SESSION_DIR = os.path.join(os.path.dirname(__file__), "sessions")


class SessionLogger:
    def __init__(self):
        os.makedirs(SESSION_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._events_path  = os.path.join(SESSION_DIR, f"{ts}_events.csv")
        self._metrics_path = os.path.join(SESSION_DIR, f"{ts}_metrics.csv")

        self._events_file  = open(self._events_path,  "w", newline="")
        self._metrics_file = open(self._metrics_path, "w", newline="")

        self._events_writer  = csv.writer(self._events_file)
        self._metrics_writer = csv.writer(self._metrics_file)

        self._events_writer.writerow(
            ["timestamp", "event_type", "duration_sec"]
        )
        self._metrics_writer.writerow(
            ["timestamp", "left_ear", "right_ear", "mean_ear",
             "mar", "pitch_deg", "yaw_deg", "score", "alarm_stage"]
        )

        self._frame_count    = 0
        self._log_every      = 3   # write metrics every N frames to avoid huge files

    def log_event(self, kind: str, ts: float, duration: float = 0.0):
        self._events_writer.writerow([
            datetime.fromtimestamp(ts).isoformat(),
            kind,
            f"{duration:.2f}",
        ])
        self._events_file.flush()

    def log_frame(self, det, state, alarm_stage: int):
        self._frame_count += 1
        if self._frame_count % self._log_every != 0:
            return

        pitch = yaw = ""
        if det.head_pose:
            pitch = f"{det.head_pose[0]:.1f}"
            yaw   = f"{det.head_pose[1]:.1f}"

        self._metrics_writer.writerow([
            datetime.now().isoformat(),
            f"{det.left_ear:.3f}",
            f"{det.right_ear:.3f}",
            f"{det.mean_ear:.3f}",
            f"{det.mar:.3f}",
            pitch, yaw,
            f"{state.score:.1f}",
            alarm_stage,
        ])

    def close(self):
        self._events_file.close()
        self._metrics_file.close()
        print(f"[Logger] Session saved to {SESSION_DIR}")
