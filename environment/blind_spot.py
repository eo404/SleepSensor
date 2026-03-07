"""
environment/blind_spot.py
Blind spot monitor using a secondary camera (e.g. USB webcam on side mirror)
OR motion-based simulation on the primary camera's edge region.

If BLIND_SPOT_CAMERA_INDEX >= 0 and a camera exists there, it uses that.
Otherwise it falls back to monitoring the left/right edges of the main frame
for rapid motion (simulated blind spot — useful for testing).

Alert: voice + HUD warning when object detected in blind zone.
"""

from __future__ import annotations
import cv2
import time
import threading
import numpy as np
from config import BLIND_SPOT_CAMERA_INDEX, BLIND_SPOT_SENSITIVITY


class BlindSpotMonitor:
    def __init__(self):
        self._cam_index   = BLIND_SPOT_CAMERA_INDEX
        self._cap         = None
        self._active      = False
        self._left_alert  = False
        self._right_alert = False
        self._last_voice_t= 0.0
        self._lock        = threading.Lock()
        self._bg_sub      = cv2.createBackgroundSubtractorMOG2(
                                history=30, varThreshold=40, detectShadows=False)
        self._running     = False

        self._try_open_camera()

    # ── Camera setup ──────────────────────────────────────────────────────────

    def _try_open_camera(self):
        if self._cam_index < 0:
            print("[BlindSpot] No secondary camera configured. "
                  "Using primary frame edge detection.")
            self._active = False
            return

        cap = cv2.VideoCapture(self._cam_index)
        if cap.isOpened():
            self._cap    = cap
            self._active = True
            self._running = True
            threading.Thread(target=self._capture_loop, daemon=True).start()
            print(f"[BlindSpot] Secondary camera opened on index {self._cam_index}.")
        else:
            cap.release()
            self._active = False
            print(f"[BlindSpot] Camera index {self._cam_index} not available. "
                  "Falling back to edge detection.")

    # ── Secondary camera loop (daemon thread) ─────────────────────────────────

    def _capture_loop(self):
        while self._running and self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            h, w = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            fgmask = self._bg_sub.apply(gray)

            # Split into left / right halves
            left_motion  = np.sum(fgmask[:, :w//2] > 0)
            right_motion = np.sum(fgmask[:, w//2:] > 0)
            threshold    = h * (w // 2) * BLIND_SPOT_SENSITIVITY

            with self._lock:
                self._left_alert  = left_motion  > threshold
                self._right_alert = right_motion > threshold

            time.sleep(0.033)   # ~30 fps

    # ── Primary frame edge detection (fallback) ───────────────────────────────

    def update_from_frame(self, frame) -> str | None:
        """
        Call with the primary camera frame each loop when no secondary camera.
        Monitors left/right 15% columns for rapid motion.
        Returns voice alert string or None.
        """
        h, w = frame.shape[:2]
        edge_w = w // 7   # 15% each side

        gray   = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fgmask = self._bg_sub.apply(gray)

        left_zone  = fgmask[:, :edge_w]
        right_zone = fgmask[:, w - edge_w:]
        threshold  = h * edge_w * BLIND_SPOT_SENSITIVITY

        left_motion  = np.sum(left_zone  > 0)
        right_motion = np.sum(right_zone > 0)

        with self._lock:
            self._left_alert  = left_motion  > threshold
            self._right_alert = right_motion > threshold

        return self._check_voice()

    # ── Alert logic ───────────────────────────────────────────────────────────

    def _check_voice(self) -> str | None:
        now = time.time()
        if now - self._last_voice_t < 4.0:   # 4-second cooldown
            return None

        with self._lock:
            left  = self._left_alert
            right = self._right_alert

        if left and right:
            self._last_voice_t = now
            return "Warning! Vehicles detected on both sides. Do not change lanes."
        if left:
            self._last_voice_t = now
            return "Warning! Vehicle in left blind spot. Do not turn left."
        if right:
            self._last_voice_t = now
            return "Warning! Vehicle in right blind spot. Do not turn right."
        return None

    def update(self) -> str | None:
        """For secondary camera mode — just check alerts."""
        if self._active:
            return self._check_voice()
        return None

    # ── Properties ───────────────────────────────────────────────────────────

    @property
    def left_alert(self) -> bool:
        with self._lock:
            return self._left_alert

    @property
    def right_alert(self) -> bool:
        with self._lock:
            return self._right_alert

    @property
    def using_secondary_camera(self) -> bool:
        return self._active

    @property
    def status_str(self) -> str:
        if self._active:
            return f"CAM{self._cam_index}"
        return "EDGE"

    def close(self):
        self._running = False
        if self._cap:
            self._cap.release()
