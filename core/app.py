"""
core/app.py
Main application loop.

Architecture:
  Camera
     │
     ▼
  Drowsiness Detection  (core.detector)
     │
     ▼
  Safety Awareness Engine  (safety.engine)
     │
     ├─ Fatigue Alerts
     ├─ Driving Time Monitoring
     ├─ Safety Messages
     └─ Driver Safety Score
     │
     ▼
  Environment Awareness Engine (environment.env_engine)
     │
     ├─ Weather Monitoring
     ├─ Night Mode Detection
     ├─ Road Hazard Reporting
     └─ Blind Spot Detection
     │
     ▼
  Driver Interface  (ui.hud + safety panel)
"""

import cv2
import time

from core.detector import Detector
from core.state import DrowsinessState
from alerts.alarm import AlarmManager
from safety.engine import SafetyAwarenessEngine
from environment.env_engine import EnvironmentEngine
from ui.hud import HUD, draw_safety_panel
from logs.logger import SessionLogger


class App:
    def __init__(self):
        self.detector = Detector()
        self.state = DrowsinessState()
        self.alarm = AlarmManager()

        # Safety system
        self.safety = SafetyAwarenessEngine()

        # Environment system (NEW)
        self.env = EnvironmentEngine()

        self.hud = HUD()
        self.logger = SessionLogger()

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[App] Error: Could not open camera.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        last_t = time.time()
        prev_alarm = 0

        print("[App] Running.")
        print("      Q = quit   C = calibrate EAR   S = settings")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("[App] Frame grab failed – exiting.")
                    break

                now = time.time()
                dt = min(now - last_t, 0.2)
                last_t = now

                # ── Detection ──────────────────────────────────────────────
                det = self.detector.process(frame)

                # ── Environment Engine (NEW) ───────────────────────────────
                self.env.update(frame, self.state)

                # Speak environment alerts
                for msg in self.env.pop_voice_messages():
                    self.safety.voice.say(msg)

                # ── Drowsiness state ───────────────────────────────────────
                self.state.update(det, dt)

                # ── Alarm stage ────────────────────────────────────────────
                if self.state.should_clear_alarm():
                    self.alarm.set_stage(0, prev_alarm)
                else:
                    desired = self.state.desired_alarm_stage()
                    if desired != prev_alarm:
                        if desired > prev_alarm:
                            self.state.total_alarm_count += 1
                        self.alarm.set_stage(desired, prev_alarm)

                prev_alarm = self.alarm.stage

                # ── Safety Awareness Engine ────────────────────────────────
                self.safety.update(self.state, det, self.alarm.stage, dt)

                # ── Log new events ─────────────────────────────────────────
                for ev in self.state.events:
                    if not getattr(ev, "_logged", False):
                        self.logger.log_event(
                            ev.kind, ev.timestamp, ev.duration
                        )
                        ev._logged = True

                if det.face_found:
                    self.logger.log_frame(det, self.state, self.alarm.stage)

                # ── Draw HUD ───────────────────────────────────────────────
                self.hud.draw(frame, det, self.state, self.alarm.stage)

                # safety score + drive time
                draw_safety_panel(frame, self.safety)

                cv2.imshow("SleepSensor", frame)

                # ── Keyboard ───────────────────────────────────────────────
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break

                elif key == ord("c"):
                    self.state.start_calibration()
                    self.safety.voice.say(
                        "Calibration started. Please keep your eyes open.",
                        priority=True,
                    )

                elif key == ord("s"):
                    self.hud.show_settings = not self.hud.show_settings

                # Hazard reporting hotkeys
                elif key in (ord("p"), ord("a"), ord("x"), ord("d"), ord("f")):
                    msg = self.env.handle_key(chr(key))
                    if msg:
                        self.safety.voice.say(msg)

        finally:
            self._cleanup(cap)

    def _cleanup(self, cap):
        self.alarm.stop()
        self.detector.close()
        self.env.close()
        self.logger.close()
        cap.release()
        cv2.destroyAllWindows()
        print("[App] Shutdown complete.")
