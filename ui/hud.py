"""
ui/hud.py
Draws all on-screen overlays: status panel, EAR graph, score bar,
eye contours, iris circles, settings overlay, calibration bar.

Stage 1 alarm → yellow border flash.
Stage 2 alarm → full red screen flash.

Includes:
- Status panel
- Session stats
- EAR history graph
- Alarm banner
- Safety score panel
- Environment awareness panel
"""

import cv2
import math
import time
import numpy as np
from collections import deque

from config import EAR_HISTORY_LEN


# ── Colour palette ──────────────────────────────────────────────

C_GREEN = (50, 220, 50)
C_RED = (30, 30, 230)
C_YELLOW = (0, 220, 220)
C_CYAN = (220, 200, 0)
C_WHITE = (240, 240, 240)
C_BLACK = (0, 0, 0)
C_ORANGE = (0, 140, 255)
C_PANEL = (20, 20, 20)

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_MONO = cv2.FONT_HERSHEY_PLAIN


# ── Flash configuration ─────────────────────────────────────────

FLASH_STAGE1_HZ = 1.5
FLASH_STAGE2_HZ = 3.0
FLASH_STAGE1_ALPHA = 0.35
FLASH_STAGE2_ALPHA = 0.50
BORDER_THICKNESS = 18


# ── Drawing helpers ─────────────────────────────────────────────

def _alpha_rect(frame, x, y, w, h, color, alpha=0.55):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def _bar(frame, x, y, w, h, value, max_val, fill_color, bg_color=(60, 60, 60)):
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg_color, -1)

    filled = int(w * min(value / max_val, 1.0))
    if filled > 0:
        cv2.rectangle(frame, (x, y), (x + filled, y + h), fill_color, -1)

    cv2.rectangle(frame, (x, y), (x + w, y + h), C_WHITE, 1)


# ── Flash effect ─────────────────────────────────────────────────

def _flash_intensity(hz):
    t = time.time()
    return max(0.0, math.sin(2 * math.pi * hz * t))


def draw_flash(frame, alarm_stage):

    if alarm_stage == 0:
        return

    ih, iw = frame.shape[:2]

    if alarm_stage == 1:

        intensity = _flash_intensity(FLASH_STAGE1_HZ)
        alpha = FLASH_STAGE1_ALPHA * intensity
        color = (0, 200, 220)
        t = BORDER_THICKNESS

        overlay = frame.copy()

        cv2.rectangle(overlay, (0, 0), (iw, t), color, -1)
        cv2.rectangle(overlay, (0, ih - t), (iw, ih), color, -1)
        cv2.rectangle(overlay, (0, 0), (t, ih), color, -1)
        cv2.rectangle(overlay, (iw - t, 0), (iw, ih), color, -1)

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    elif alarm_stage == 2:

        intensity = _flash_intensity(FLASH_STAGE2_HZ)
        alpha = FLASH_STAGE2_ALPHA * intensity

        overlay = frame.copy()

        cv2.rectangle(overlay, (0, 0), (iw, ih), (0, 0, 200), -1)

        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        t = BORDER_THICKNESS * 2
        cv2.rectangle(frame, (0, 0), (iw - 1, ih - 1), (0, 0, 255), t)


# ── HUD class ───────────────────────────────────────────────────

class HUD:

    def __init__(self):
        self.show_settings = False

    # ── Eye overlays ─────────────────────────────────────────────

    def draw_eyes(self, frame, det, state):

        if not det.face_found:
            return

        color = C_RED if state.eyes_confirmed_closed else C_GREEN

        for pts in (det.left_eye_pts, det.right_eye_pts):

            n = len(pts)

            for i in range(n):

                cv2.line(
                    frame,
                    pts[i],
                    pts[(i + 1) % n],
                    color,
                    1,
                    cv2.LINE_AA,
                )

    # ── Status panel ─────────────────────────────────────────────

    def draw_status_panel(self, frame, det, state, alarm_stage):

        px, py, pw, ph = 10, 10, 280, 185

        _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.6)

        lines = []

        if not det.face_found:

            lines.append(("NO FACE DETECTED", C_YELLOW))

        else:

            if state.eyes_confirmed_closed:

                lines.append(
                    (f"EYES CLOSED {state.eyes_closed_seconds:.1f}s", C_RED)
                )

            else:

                lines.append(
                    (f"EYES OPEN {state.eyes_open_seconds:.1f}s", C_GREEN)
                )

            lines.append(
                (
                    f"EAR L:{det.left_ear:.2f} R:{det.right_ear:.2f}",
                    C_WHITE,
                )
            )

        alarm_labels = {0: "OFF", 1: "STAGE 1", 2: "STAGE 2"}

        lines.append((f"Alarm: {alarm_labels[alarm_stage]}", C_WHITE))

        ty = py + 22

        for text, color in lines:

            cv2.putText(frame, text, (px + 8, ty), FONT, 0.45, color, 1)

            ty += 22

    # ── Session stats ───────────────────────────────────────────

    def draw_session_stats(self, frame, state):

        ih, iw = frame.shape[:2]

        pw, ph = 200, 90
        px, py = iw - pw - 10, 10

        _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.6)

        elapsed = int(time.time() - state.session_start)
        m, s = divmod(elapsed, 60)

        lines = [

            (f"Session {m:02d}:{s:02d}", C_WHITE),

            (f"Yawns: {state.total_yawn_count}", C_WHITE),

            (f"Alarms: {state.total_alarm_count}", C_WHITE),

        ]

        ty = py + 20

        for text, color in lines:

            cv2.putText(frame, text, (px + 8, ty), FONT, 0.42, color, 1)

            ty += 20

    # ── Composite draw ──────────────────────────────────────────

    def draw(self, frame, det, state, alarm_stage):

        draw_flash(frame, alarm_stage)

        self.draw_eyes(frame, det, state)

        self.draw_status_panel(frame, det, state, alarm_stage)

        self.draw_session_stats(frame, state)


# ── Safety panel ───────────────────────────────────────────────

def draw_safety_panel(frame, engine):

    ih, iw = frame.shape[:2]

    pw, ph = 220, 110
    px = iw - pw - 10
    py = ih - ph - 10

    _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.7)

    score = engine.safety_score.score
    color = engine.safety_score.color

    cv2.putText(frame, "SAFETY SCORE", (px + 8, py + 18),
                FONT, 0.45, C_WHITE, 1)

    cv2.putText(frame, f"{score:.0f}/100",
                (px + 8, py + 50), FONT, 0.9, color, 2)

    _bar(frame, px + 8, py + 70, pw - 16, 12, score, 100, color)

    cv2.putText(
        frame,
        f"Drive: {engine.drive_timer.elapsed_str}",
        (px + 8, py + 100),
        FONT,
        0.38,
        C_WHITE,
        1,
    )


# ── NEW: Environment Panel ─────────────────────────────────────

def draw_environment_panel(frame, env):

    ih, iw = frame.shape[:2]

    pw, ph = 240, 140
    px = iw - pw - 10
    py = 120

    _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.7)

    cv2.putText(frame, "ENVIRONMENT", (px + 8, py + 20),
                FONT, 0.5, C_CYAN, 1)

    ty = py + 40

    # Night mode
    mode = env.night_mode.status_str

    cv2.putText(frame, f"Mode: {mode}",
                (px + 8, ty),
                FONT,
                0.42,
                C_WHITE,
                1)

    ty += 20

    # Weather
    adv = env.weather.advisory

    if adv:

        cv2.putText(
            frame,
            f"Wx: {adv.condition}",
            (px + 8, ty),
            FONT,
            0.42,
            adv.risk_color,
            1,
        )

        ty += 18

        cv2.putText(
            frame,
            f"{adv.temp_c:.1f}C  {adv.wind_mps:.0f}m/s",
            (px + 8, ty),
            FONT,
            0.42,
            C_WHITE,
            1,
        )

        ty += 20

    # Blind spot
    left = "L" if env.blind_spot.left_alert else "-"
    right = "R" if env.blind_spot.right_alert else "-"

    cv2.putText(frame,
                f"Drive time: {engine.drive_timer.elapsed_str}",
                (px + 8, py + 100), FONT, 0.38, C_WHITE, 1, cv2.LINE_AA)
