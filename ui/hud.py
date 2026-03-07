"""
ui/hud.py
Draws all on-screen overlays: status panel, EAR graph, score bar,
eye contours, iris circles, settings overlay, calibration bar.
Stage 1 alarm → yellow border flash.
Stage 2 alarm → full red screen flash.
"""

import cv2
import math
import time
import numpy as np
from collections import deque

from config import EAR_HISTORY_LEN


# ── Colour palette ────────────────────────────────────────────────────────────
C_GREEN = (50,  220,  50)
C_RED = (30,   30, 230)
C_YELLOW = (0,   220, 220)
C_CYAN = (220, 200,   0)
C_WHITE = (240, 240, 240)
C_BLACK = (0,     0,   0)
C_ORANGE = (0,   140, 255)
C_PANEL = (20,   20,  20)

FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_MONO = cv2.FONT_HERSHEY_PLAIN

# ── Flash config ──────────────────────────────────────────────────────────────
FLASH_STAGE1_HZ = 1.5    # border flash frequency (cycles/sec)
FLASH_STAGE2_HZ = 3.0    # full-screen flash frequency
FLASH_STAGE1_ALPHA = 0.35  # border overlay opacity at peak
FLASH_STAGE2_ALPHA = 0.50  # full-screen overlay opacity at peak
BORDER_THICKNESS = 18    # px border width for stage-1 flash


# ── Drawing helpers ───────────────────────────────────────────────────────────

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


# ── Flash effect ──────────────────────────────────────────────────────────────

def _flash_intensity(hz: float) -> float:
    """Returns 0.0–1.0 pulsing value at the given frequency."""
    t = time.time()
    # Sine wave, clamped to positive half → smooth pulse
    return max(0.0, math.sin(2 * math.pi * hz * t))


def draw_flash(frame, alarm_stage: int):
    """
    Stage 1 → pulsing yellow border around the frame.
    Stage 2 → pulsing red full-screen overlay + thick red border.
    """
    if alarm_stage == 0:
        return

    ih, iw = frame.shape[:2]

    if alarm_stage == 1:
        intensity = _flash_intensity(FLASH_STAGE1_HZ)
        if intensity < 0.05:
            return  # skip near-zero frames — no flicker artifact
        alpha = FLASH_STAGE1_ALPHA * intensity
        color = (0, 200, 220)   # yellow (BGR)
        t = BORDER_THICKNESS

        overlay = frame.copy()
        # Top / bottom / left / right border rectangles
        cv2.rectangle(overlay, (0, 0),      (iw, t),       color, -1)
        cv2.rectangle(overlay, (0, ih - t), (iw, ih),      color, -1)
        cv2.rectangle(overlay, (0, 0),      (t, ih),       color, -1)
        cv2.rectangle(overlay, (iw - t, 0), (iw, ih),      color, -1)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    elif alarm_stage == 2:
        intensity = _flash_intensity(FLASH_STAGE2_HZ)
        if intensity < 0.05:
            return

        # Full-screen red tint
        alpha = FLASH_STAGE2_ALPHA * intensity
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (iw, ih), (0, 0, 200), -1)  # red (BGR)
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        # Thick red border on top
        t = BORDER_THICKNESS * 2
        cv2.rectangle(frame, (0, 0), (iw - 1, ih - 1), (0, 0, 255), t)


# ── HUD class ─────────────────────────────────────────────────────────────────

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
                cv2.line(frame, pts[i], pts[(i + 1) %
                         n], color, 1, cv2.LINE_AA)
        for iris_pts in (det.left_iris_pts, det.right_iris_pts):
            if len(iris_pts) >= 3:
                cx = sum(p[0] for p in iris_pts) // len(iris_pts)
                cy = sum(p[1] for p in iris_pts) // len(iris_pts)
                r = max(int(math.hypot(
                    iris_pts[0][0] - iris_pts[2][0],
                    iris_pts[0][1] - iris_pts[2][1],
                ) / 2), 2)
                cv2.circle(frame, (cx, cy), r, C_CYAN, 1, cv2.LINE_AA)

    # ── Status panel (top-left) ───────────────────────────────────────────────

    def draw_status_panel(self, frame, det, state, alarm_stage):
        ih, iw = frame.shape[:2]
        px, py, pw, ph = 10, 10, 280, 185
        _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.6)

        lines = []
        if not det.face_found:
            lines.append(("NO FACE DETECTED", C_YELLOW))
        else:
            if state.calibrating:
                pct = int(state.calib_progress * 100)
                lines.append((f"CALIBRATING... {pct}%", C_CYAN))
            elif state.eyes_confirmed_closed:
                lines.append(
                    (f"EYES CLOSED  {state.eyes_closed_seconds:.1f}s", C_RED))
            else:
                lines.append(
                    (f"EYES OPEN    {state.eyes_open_seconds:.1f}s", C_GREEN))

            lines.append((f"EAR  L:{det.left_ear:.2f}  R:{det.right_ear:.2f}  "
                          f"Thr:{state.ear_threshold:.2f}", C_WHITE))

            yawn_col = C_ORANGE if state.yawning else C_WHITE
            lines.append(
                (f"MAR  {det.mar:.2f}  {'YAWNING' if state.yawning else 'ok'}", yawn_col))

            if det.head_pose:
                p, y, r = det.head_pose
                hp_col = C_RED if state.bad_head_pose else C_WHITE
                lines.append(
                    (f"Pose P:{p:+.0f} Y:{y:+.0f} R:{r:+.0f}", hp_col))
            else:
                lines.append(("Pose  --", C_WHITE))

        alarm_labels = {0: "off", 1: "STAGE 1", 2: "STAGE 2"}
        alarm_cols = {0: C_GREEN, 1: C_YELLOW, 2: C_RED}
        lines.append(
            (f"Alarm: {alarm_labels[alarm_stage]}", alarm_cols[alarm_stage]))

        ty = py + 22
        for text, color in lines:
            cv2.putText(frame, text, (px + 8, ty), FONT,
                        0.45, color, 1, cv2.LINE_AA)
            ty += 22

        score_color = C_GREEN if state.score < 40 else (
            C_YELLOW if state.score < 70 else C_RED)
        _bar(frame, px + 8, py + ph - 22, pw - 16,
             14, state.score, 100.0, score_color)
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
            x1 = gx + int((i-1) / (n-1) * (gw-4)) + 2
            x2 = gx + int(i / (n-1) * (gw-4)) + 2
            y1 = gy + gh - 6 - int(history[i-1] / max_val * (gh-20))
            y2 = gy + gh - 6 - int(history[i] / max_val * (gh-20))
            y1 = max(gy+16, min(gy+gh-6, y1))
            y2 = max(gy+16, min(gy+gh-6, y2))
            cv2.line(frame, (x1, y1), (x2, y2), C_GREEN, 1, cv2.LINE_AA)
        ty = gy + gh - 6 - int(state.ear_threshold / max_val * (gh-20))
        ty = max(gy+16, min(gy+gh-6, ty))
        cv2.line(frame, (gx+2, ty), (gx+gw-2, ty), C_RED, 1, cv2.LINE_AA)

    # ── Session stats (top-right) ─────────────────────────────────────────────

    def draw_session_stats(self, frame, state):
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
            cv2.putText(frame, text, (px + 8, ty), FONT,
                        0.42, color, 1, cv2.LINE_AA)
            ty += 20

    # ── Big alarm banner ──────────────────────────────────────────────────────

    def draw_alarm_banner(self, frame, alarm_stage):
        if alarm_stage == 0:
            return
        ih, iw = frame.shape[:2]
        msg = "DROWSY - STAGE 1" if alarm_stage == 1 else "!! WAKE UP !!"
        color = C_YELLOW if alarm_stage == 1 else C_RED
        scale = 0.9 if alarm_stage == 1 else 1.3
        thick = 2 if alarm_stage == 1 else 3
        (tw, th), _ = cv2.getTextSize(msg, FONT, scale, thick)
        tx = (iw - tw) // 2
        ty = ih // 2
        _alpha_rect(frame, tx - 12, ty - th - 8,
                    tw + 24, th + 16, C_BLACK, 0.6)
        cv2.putText(frame, msg, (tx, ty), FONT,
                    scale, color, thick, cv2.LINE_AA)

    # ── Calibration overlay ───────────────────────────────────────────────────

    def draw_calibration(self, frame, state):
        if not state.calibrating:
            return
        ih, iw = frame.shape[:2]
        bw = 300
        bx = (iw - bw) // 2
        by = ih // 2 + 30
        _alpha_rect(frame, bx - 10, by - 30, bw + 20, 50, C_BLACK, 0.65)
        cv2.putText(frame, "Keep eyes OPEN for calibration...",
                    (bx, by - 8), FONT, 0.55, C_CYAN, 1, cv2.LINE_AA)
        _bar(frame, bx, by + 4, bw, 14, state.calib_progress, 1.0, C_CYAN)

    # ── Settings overlay ──────────────────────────────────────────────────────

    def draw_settings(self, frame, state):
        if not self.show_settings:
            return
        ih, iw = frame.shape[:2]
        pw, ph = 320, 200
        px = (iw - pw) // 2
        py = (ih - ph) // 2
        _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.85)
        cv2.rectangle(frame, (px, py), (px + pw, py + ph), C_WHITE, 1)
        lines = [
            ("--- SETTINGS -------------------", C_CYAN),
            (f"EAR threshold : {state.ear_threshold:.3f}", C_WHITE),
            (f"Trigger (closed): 1.5s", C_WHITE),
            (f"Alarm stage 1 : 1.5s", C_WHITE),
            (f"Alarm stage 2 : 3.0s", C_WHITE),
            ("", C_WHITE),
            ("[C]  Recalibrate EAR threshold", C_YELLOW),
            ("[S]  Close settings", C_YELLOW),
            ("[Q]  Quit", C_YELLOW),
        ]
        ty = py + 24
        for text, color in lines:
            cv2.putText(frame, text, (px + 12, ty), FONT,
                        0.45, color, 1, cv2.LINE_AA)
            ty += 22

    # ── Hotkey hint ───────────────────────────────────────────────────────────

    def draw_hotkeys(self, frame):
        ih, iw = frame.shape[:2]
        cv2.putText(frame, "Q=quit  C=calibrate  S=settings",
                    (10, ih - 10), FONT, 0.38, (130, 130, 130), 1, cv2.LINE_AA)

    # ── Composite draw ────────────────────────────────────────────────────────

    def draw(self, frame, det, state, alarm_stage):
        # Flash goes FIRST so all other overlays render on top of it
        draw_flash(frame, alarm_stage)

        self.draw_eyes(frame, det, state)
        self.draw_status_panel(frame, det, state, alarm_stage)
        self.draw_session_stats(frame, state)
        self.draw_ear_graph(frame, state)
        self.draw_alarm_banner(frame, alarm_stage)
        self.draw_calibration(frame, state)
        self.draw_settings(frame, state)
        self.draw_hotkeys(frame)


# ── Safety Awareness Panel (injected at bottom-right) ─────────────────────────

def draw_safety_panel(frame, engine):
    """
    Draws the Driver Safety Score + Drive Time panel.
    Call after HUD.draw() so it renders on top.
    """
    ih, iw = frame.shape[:2]
    pw, ph = 220, 110
    px = iw - pw - 10
    py = ih - ph - 10

    _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.7)
    cv2.rectangle(frame, (px, py), (px + pw, py + ph),
                  engine.safety_score.color, 1)

    score = engine.safety_score.score
    label = engine.safety_score.label
    trend = engine.safety_score.trend
    color = engine.safety_score.color

    # Title
    cv2.putText(frame, "SAFETY SCORE", (px + 8, py + 18),
                FONT, 0.45, C_WHITE, 1, cv2.LINE_AA)

    # Big score number
    cv2.putText(frame, f"{score:.0f}/100 {trend}",
                (px + 8, py + 44), FONT, 0.8, color, 2, cv2.LINE_AA)

    # Label band
    cv2.putText(frame, label, (px + 8, py + 66),
                FONT, 0.55, color, 1, cv2.LINE_AA)

    # Score bar
    _bar(frame, px + 8, py + 74, pw - 16, 10, score, 100.0, color)

    # Drive time
    cv2.putText(frame,
                f"Drive time: {engine.drive_timer.elapsed_str}",
                (px + 8, py + 100), FONT, 0.38, C_WHITE, 1, cv2.LINE_AA)


# ── Environment Detection Panel (right side) ──────────────────────────────────

def draw_environment_panel(frame, env_data):
    """
    Draws the Environment Detection panel on the right side of the screen.
    Shows day/night mode, ambient light, weather conditions, and simulated
    temperature/wind data similar to a vehicle dashboard.
    
    Args:
        frame: OpenCV frame to draw on
        env_data: Dictionary containing environment data from EnvironmentMonitor
    """
    ih, iw = frame.shape[:2]
    
    # Panel dimensions and position (right side, middle)
    pw, ph = 200, 140
    px = iw - pw - 10  # 10px from right edge
    py = (ih - ph) // 2 - 50  # Center vertically, offset up to avoid safety panel
    
    # Draw panel background
    _alpha_rect(frame, px, py, pw, ph, C_PANEL, alpha=0.7)
    
    # Determine border color based on mode
    if env_data["mode"] == "DAY":
        border_color = C_YELLOW
    elif env_data["mode"] == "NIGHT":
        border_color = (100, 100, 255)  # Light blue
    else:  # DUSK
        border_color = C_ORANGE
    
    cv2.rectangle(frame, (px, py), (px + pw, py + ph), border_color, 1)
    
    # Title
    cv2.putText(frame, "ENVIRONMENT", (px + 8, py + 18),
                FONT, 0.45, C_WHITE, 1, cv2.LINE_AA)
    
    # Mode (DAY/NIGHT/DUSK)
    mode_color = border_color
    cv2.putText(frame, f"Mode: {env_data['mode']}", (px + 8, py + 38),
                FONT, 0.4, mode_color, 1, cv2.LINE_AA)
    
    # Ambient Light (Lux)
    lux_value = env_data["lux"]
    cv2.putText(frame, f"Lux: {lux_value:,}", (px + 8, py + 54),
                FONT, 0.4, C_WHITE, 1, cv2.LINE_AA)
    
    # Weather condition
    weather_color = C_WHITE
    if env_data["weather"] in ["Sunny", "Partly Cloudy"]:
        weather_color = C_YELLOW
    elif env_data["weather"] in ["Cloudy", "Overcast"]:
        weather_color = (180, 180, 180)  # Light gray
    
    cv2.putText(frame, f"Weather: {env_data['weather']}", (px + 8, py + 70),
                FONT, 0.4, weather_color, 1, cv2.LINE_AA)
    
    # Temperature
    temp_color = C_WHITE
    temp = env_data["temp"]
    if temp > 30:
        temp_color = C_ORANGE  # Hot
    elif temp < 10:
        temp_color = C_CYAN   # Cold
    
    cv2.putText(frame, f"Temp: {temp}°C", (px + 8, py + 86),
                FONT, 0.4, temp_color, 1, cv2.LINE_AA)
    
    # Wind Speed
    wind_color = C_WHITE
    wind = env_data["wind"]
    if wind > 3.0:
        wind_color = C_ORANGE  # Windy conditions
    
    cv2.putText(frame, f"Wind: {wind} m/s", (px + 8, py + 102),
                FONT, 0.4, wind_color, 1, cv2.LINE_AA)
    
    # Light level bar (visual indicator)
    bar_y = py + 115
    bar_height = 8
    lux_max = 5000  # Max lux for bar display
    lux_for_bar = min(lux_value, lux_max)
    
    # Color code the light bar
    if lux_value > 3000:
        bar_color = C_YELLOW  # Bright daylight
    elif lux_value > 1000:
        bar_color = C_ORANGE  # Moderate light
    else:
        bar_color = C_CYAN    # Low light
    
    _bar(frame, px + 8, bar_y, pw - 16, bar_height, lux_for_bar, lux_max, bar_color)
    
    # Small label for the light bar
    cv2.putText(frame, "Light Level", (px + 8, py + 132),
                FONT_MONO, 0.3, (150, 150, 150), 1, cv2.LINE_AA)
