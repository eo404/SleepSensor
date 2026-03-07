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
  Driver Interface  (ui.hud + safety panel)
"""

import cv2
import time

from core.detector import Detector
from core.state import DrowsinessState
from alerts.alarm import AlarmManager
from safety.engine import SafetyAwarenessEngine
from safety.environment import EnvironmentMonitor
from ui.hud import HUD, draw_safety_panel, draw_environment_panel
from logs.logger import SessionLogger


class App:
    def __init__(self):
        self.detector = Detector()
        self.state = DrowsinessState()
        self.alarm = AlarmManager()
        self.safety = SafetyAwarenessEngine()
        self.environment = EnvironmentMonitor()
        self.hud = HUD()
        self.logger = SessionLogger()

    def run(self):
        # Try multiple camera indices to find an available camera
        cap = None
        for camera_idx in range(3):  # Try camera indices 0, 1, 2
            print(f"[App] Trying camera index {camera_idx}...")
            test_cap = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)  # Use DirectShow on Windows
            if test_cap.isOpened():
                # Test if we can actually read a frame
                ret, test_frame = test_cap.read()
                if ret and test_frame is not None:
                    print(f"[App] Successfully opened camera {camera_idx}")
                    cap = test_cap
                    break
                else:
                    print(f"[App] Camera {camera_idx} opened but cannot read frames")
                    test_cap.release()
            else:
                test_cap.release()
        
        if cap is None:
            print("[App] ERROR: No working camera found!")
            print("      Please check:")
            print("      1. Camera is connected and working")
            print("      2. Camera is not being used by another application")
            print("      3. Camera permissions are granted")
            print("      4. Try closing Skype, Teams, or other video apps")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Verify camera settings
        actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"[App] Camera resolution: {actual_width:.0f}x{actual_height:.0f}")

        last_t = time.time()
        prev_alarm = 0

        print("[App] Running.")
        print("      Q = quit   C = calibrate EAR   S = settings")

        try:
            frame_fail_count = 0
            max_frame_failures = 5
            
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    frame_fail_count += 1
                    print(f"[App] Frame grab failed (attempt {frame_fail_count}/{max_frame_failures})")
                    
                    if frame_fail_count >= max_frame_failures:
                        print("[App] Too many frame grab failures – camera may have disconnected")
                        break
                    
                    # Short delay before retry
                    time.sleep(0.1)
                    continue
                
                # Reset failure count on successful frame
                frame_fail_count = 0

                now = time.time()
                dt = min(now - last_t, 0.2)
                last_t = now

                # ── Detection ──────────────────────────────────────────────
                det = self.detector.process(frame)

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

                # ── Environment Detection ──────────────────────────────────
                env_data = self.environment.update(frame)

                # ── Log new events ─────────────────────────────────────────
                for ev in self.state.events:
                    if not getattr(ev, "_logged", False):
                        self.logger.log_event(
                            ev.kind, ev.timestamp, ev.duration)
                        ev._logged = True

                if det.face_found:
                    self.logger.log_frame(det, self.state, self.alarm.stage)

                # ── Draw HUD ───────────────────────────────────────────────
                self.hud.draw(frame, det, self.state, self.alarm.stage)
                # safety score + drive time
                draw_safety_panel(frame, self.safety)
                # environment detection panel
                draw_environment_panel(frame, env_data)

                cv2.imshow("SleepSensor", frame)

                # ── Keyboard ───────────────────────────────────────────────
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("c"):
                    self.state.start_calibration()
                    self.safety.voice.say(
                        "Calibration started. Please keep your eyes open.", priority=True)
                elif key == ord("s"):
                    self.hud.show_settings = not self.hud.show_settings

        finally:
            self._cleanup(cap)

    def _cleanup(self, cap):
        self.alarm.stop()
        self.detector.close()
        self.logger.close()
        cap.release()
        cv2.destroyAllWindows()
        print("[App] Shutdown complete.")
