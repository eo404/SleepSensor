"""
ui/hud.py
Draws all on-screen overlays: status panel, EAR graph, score bar,
eye contours, iris circles, settings overlay, calibration bar.
"""

import cv2
import math
import numpy as np
from collections import deque

from config import EAR_HISTORY_LEN


# ── Colour palette ────────────────────────────────────────────────────────────
C_GREEN  = (50,  220,  50)
C_RED    = (30,   30, 230)
C_YELLOW = (0,   220, 220)
C_CYAN   = (220, 200,   0)
C_WHITE  = (240, 240, 240)
C_BLACK  = (0,     0,   0)
C_ORANGE = (0,   140, 255)
C_PURPLE = (200,  50, 200)
C_PANEL  = (20,   20,  20)   # dark panel bg


FONT       = cv2.FONT_HERSHEY_SIMPLEX
FONT_MONO  = cv2.FONT_HERSHEY_PLAIN


def _alpha_rect(frame, x, y, w, h, color, alpha=0.55):
    """Draw a semi-transparent filled rectangle."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def _bar(frame, x, y, w, h, value, max_val, fill_color, bg_color=(60, 60, 60)):
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg_color, -1)
    filled = int(w * min(value / max_val, 1.0))
    if filled > 0:
        cv2.rectangle(frame, (x, y), (x + filled, y + h), fill_color, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), C_WHITE, 1)


class HUD:
    def __init__(self):
        self.show_settings = False

    # ── Eye / iris overlays ───────────────────────────────────────────────────

    def draw_eyes(self, frame, det, state):
        if not det.face_found:
            return

        color = C_RED if state.eyes_confirmed_closed else C_GREEN

        for pts in (det.left_eye_pts, det.right_eye_pts):
            n = len(pts)
            for i in range(n):
                cv2.line(frame, pts[i], pts[(i + 1) % n], color, 1, cv2.LINE_AA)

        iris_color = C_CYAN
        for iris_pts in (det.left_iris_pts, det.right_iris_pts):
            if len(iris_pts) >= 3:
                cx = sum(p[0] for p in iris_pts) // len(iris_pts)
                cy = sum(p[1] for p in iris_pts) // len(iris_pts)
                r  = max(int(math.hypot(
                    iris_pts[0][0] - iris_pts[2][0],
                    iris_pts[0][1] - iris_pts[2][1],
                ) / 2), 2)
                cv2.circle(frame, (cx, cy), r, iris_color, 1, cv2.LINE_AA)

    # ── Status panel (top-left) ───────────────────────────────────────────────

    def draw_status_panel(self, frame, det, state, alarm_stage):
        ih, iw = frame.shape[:2]
        px, py, pw, ph = 10, 10, 280, 185
        _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.6)

        lines = []

        if not det.face_found:
            lines.append(("NO FACE DETECTED", C_YELLOW))
        else:
            # Eye status
            if state.calibrating:
                pct = int(state.calib_progress * 100)
                lines.append((f"CALIBRATING... {pct}%", C_CYAN))
            elif state.eyes_confirmed_closed:
                lines.append((f"EYES CLOSED  {state.eyes_closed_seconds:.1f}s", C_RED))
            else:
                lines.append((f"EYES OPEN    {state.eyes_open_seconds:.1f}s", C_GREEN))

            lines.append((f"EAR  L:{det.left_ear:.2f}  R:{det.right_ear:.2f}  "
                          f"Thr:{state.ear_threshold:.2f}", C_WHITE))

            # Yawn
            yawn_col = C_ORANGE if state.yawning else C_WHITE
            lines.append((f"MAR  {det.mar:.2f}  {'YAWNING' if state.yawning else 'ok'}", yawn_col))

            # Head pose
            if det.head_pose:
                p, y, r = det.head_pose
                hp_col = C_RED if state.bad_head_pose else C_WHITE
                lines.append((f"Pose P:{p:+.0f} Y:{y:+.0f} R:{r:+.0f}", hp_col))
            else:
                lines.append(("Pose  --", C_WHITE))

        # Alarm
        alarm_labels = {0: "off", 1: "STAGE 1", 2: "STAGE 2 LOUD"}
        alarm_cols   = {0: C_GREEN, 1: C_YELLOW, 2: C_RED}
        lines.append((f"Alarm: {alarm_labels[alarm_stage]}", alarm_cols[alarm_stage]))

        ty = py + 22
        for text, color in lines:
            cv2.putText(frame, text, (px + 8, ty), FONT, 0.45, color, 1, cv2.LINE_AA)
            ty += 22

        # Score bar
        score_color = C_GREEN if state.score < 40 else (C_YELLOW if state.score < 70 else C_RED)
        _bar(frame, px + 8, py + ph - 22, pw - 16, 14,
             state.score, 100.0, score_color)
        cv2.putText(frame, f"Drowsiness score: {state.score:.0f}/100",
                    (px + 8, py + ph - 26), FONT, 0.38, C_WHITE, 1, cv2.LINE_AA)

    # ── EAR history graph (bottom-left) ───────────────────────────────────────

    def draw_ear_graph(self, frame, state):
        ih, iw = frame.shape[:2]
        gw, gh = 220, 70
        gx, gy = 10, ih - gh - 10

        _alpha_rect(frame, gx, gy, gw, gh, C_PANEL, alpha=0.6)
        cv2.putText(frame, "EAR history", (gx + 4, gy + 12),
                    FONT, 0.38, C_WHITE, 1, cv2.LINE_AA)

        history = list(state.ear_history)
        n = len(history)
        if n < 2:
            return

        max_val = 0.5
        for i in range(1, n):
            x1 = gx + int((i - 1) / (n - 1) * (gw - 4)) + 2
            x2 = gx + int(i       / (n - 1) * (gw - 4)) + 2
            y1 = gy + gh - 6 - int(history[i - 1] / max_val * (gh - 20))
            y2 = gy + gh - 6 - int(history[i]     / max_val * (gh - 20))
            y1 = max(gy + 16, min(gy + gh - 6, y1))
            y2 = max(gy + 16, min(gy + gh - 6, y2))
            cv2.line(frame, (x1, y1), (x2, y2), C_GREEN, 1, cv2.LINE_AA)

        # Threshold line
        ty = gy + gh - 6 - int(state.ear_threshold / max_val * (gh - 20))
        ty = max(gy + 16, min(gy + gh - 6, ty))
        cv2.line(frame, (gx + 2, ty), (gx + gw - 2, ty), C_RED, 1, cv2.LINE_AA)

    # ── Session stats (top-right) ─────────────────────────────────────────────

    def draw_session_stats(self, frame, state):
        import time
        ih, iw = frame.shape[:2]
        pw, ph = 200, 90
        px, py = iw - pw - 10, 10
        _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.6)

        elapsed = int(time.time() - state.session_start)
        m, s = divmod(elapsed, 60)
        lines = [
            (f"Session  {m:02d}:{s:02d}", C_WHITE),
            (f"Closed events: {len([e for e in state.events if e.kind == 'closed'])}", C_WHITE),
            (f"Yawns:   {state.total_yawn_count}", C_WHITE),
            (f"Alarms:  {state.total_alarm_count}", C_WHITE),
        ]
        ty = py + 20
        for text, color in lines:
            cv2.putText(frame, text, (px + 8, ty), FONT, 0.42, color, 1, cv2.LINE_AA)
            ty += 20

    # ── Big alarm banner ──────────────────────────────────────────────────────

    def draw_alarm_banner(self, frame, alarm_stage):
        if alarm_stage == 0:
            return
        ih, iw = frame.shape[:2]
        msg   = "⚠ DROWSY – STAGE 1" if alarm_stage == 1 else "⚠⚠ WAKE UP! ⚠⚠"
        color = C_YELLOW if alarm_stage == 1 else C_RED
        scale = 0.9 if alarm_stage == 1 else 1.3
        thick = 2 if alarm_stage == 1 else 3
        (tw, th), _ = cv2.getTextSize(msg, FONT, scale, thick)
        tx = (iw - tw) // 2
        ty = ih // 2
        _alpha_rect(frame, tx - 12, ty - th - 8, tw + 24, th + 16, C_BLACK, 0.6)
        cv2.putText(frame, msg, (tx, ty), FONT, scale, color, thick, cv2.LINE_AA)

    # ── Calibration overlay ───────────────────────────────────────────────────

    def draw_calibration(self, frame, state):
        if not state.calibrating:
            return
        ih, iw = frame.shape[:2]
        msg  = "Keep eyes OPEN for calibration..."
        pct  = state.calib_progress
        bw   = 300
        bx   = (iw - bw) // 2
        by   = ih // 2 + 30
        _alpha_rect(frame, bx - 10, by - 30, bw + 20, 50, C_BLACK, 0.65)
        cv2.putText(frame, msg, (bx, by - 8), FONT, 0.55, C_CYAN, 1, cv2.LINE_AA)
        _bar(frame, bx, by + 4, bw, 14, pct, 1.0, C_CYAN)

    # ── Settings overlay ──────────────────────────────────────────────────────

    def draw_settings(self, frame, state):
        if not self.show_settings:
            return
        ih, iw = frame.shape[:2]
        pw, ph = 320, 200
        px     = (iw - pw) // 2
        py     = (ih - ph) // 2
        _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.85)
        cv2.rectangle(frame, (px, py), (px + pw, py + ph), C_WHITE, 1)

        lines = [
            ("─── SETTINGS ───────────────────", C_CYAN),
            (f"EAR threshold : {state.ear_threshold:.3f}", C_WHITE),
            (f"Trigger (closed): {1.5:.1f}s", C_WHITE),
            (f"Alarm stage 1 : {1.5:.1f}s", C_WHITE),
            (f"Alarm stage 2 : {3.0:.1f}s", C_WHITE),
            ("", C_WHITE),
            ("[C]  Recalibrate EAR threshold", C_YELLOW),
            ("[S]  Close settings", C_YELLOW),
            ("[Q]  Quit", C_YELLOW),
        ]
        ty = py + 24
        for text, color in lines:
            cv2.putText(frame, text, (px + 12, ty), FONT, 0.45, color, 1, cv2.LINE_AA)
            ty += 22

    # ── Hotkey hint ───────────────────────────────────────────────────────────

    def draw_hotkeys(self, frame):
        ih, iw = frame.shape[:2]
        hints = "Q=quit  C=calibrate  S=settings"
        cv2.putText(frame, hints, (10, ih - 10), FONT, 0.38, (130, 130, 130), 1, cv2.LINE_AA)

    # ── Composite draw ────────────────────────────────────────────────────────

    def draw(self, frame, det, state, alarm_stage):
        self.draw_eyes(frame, det, state)
        self.draw_status_panel(frame, det, state, alarm_stage)
        self.draw_session_stats(frame, state)
        self.draw_ear_graph(frame, state)
        self.draw_alarm_banner(frame, alarm_stage)
        self.draw_calibration(frame, state)
        self.draw_settings(frame, state)
        self.draw_hotkeys(frame)
