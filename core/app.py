"""
core/app.py
Main application loop. Ties detector → state → alarm → HUD → logger.
"""

import cv2
import time

from core.detector  import Detector
from core.state     import DrowsinessState
from alerts.alarm   import AlarmManager
from ui.hud         import HUD
from logs.logger    import SessionLogger


class App:
    def __init__(self):
        self.detector = Detector()
        self.state    = DrowsinessState()
        self.alarm    = AlarmManager()
        self.hud      = HUD()
        self.logger   = SessionLogger()

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("[App] Error: Could not open camera.")
            return

        # Attempt a higher resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        last_t      = time.time()
        prev_alarm  = 0

        print("[App] Running. Press Q=quit  C=calibrate  S=settings")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("[App] Frame grab failed – exiting.")
                    break

                now    = time.time()
                dt     = now - last_t
                last_t = now

                # ── Detection ──────────────────────────────────────────────
                det = self.detector.process(frame)

                # ── State update ───────────────────────────────────────────
                self.state.update(det, dt)

                # ── Alarm ──────────────────────────────────────────────────
                if self.state.should_clear_alarm():
                    self.alarm.set_stage(0, prev_alarm)
                else:
                    desired = self.state.desired_alarm_stage()
                    if desired != prev_alarm:
                        if desired > prev_alarm:   # escalating
                            self.state.total_alarm_count += 1
                        self.alarm.set_stage(desired, prev_alarm)

                prev_alarm = self.alarm.stage

                # ── Log events ─────────────────────────────────────────────
                new_events = [
                    e for e in self.state.events
                    if not getattr(e, "_logged", False)
                ]
                for ev in new_events:
                    self.logger.log_event(ev.kind, ev.timestamp, ev.duration)
                    ev._logged = True   # type: ignore[attr-defined]

                if det.face_found:
                    self.logger.log_frame(det, self.state, self.alarm.stage)

                # ── Draw HUD ───────────────────────────────────────────────
                self.hud.draw(frame, det, self.state, self.alarm.stage)

                cv2.imshow("SleepSensor", frame)

                # ── Keyboard ───────────────────────────────────────────────
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("c"):
                    self.state.start_calibration()
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