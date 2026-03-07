"""
ui/hud.py
Draws a compact camera HUD similar to a driver-monitoring dashboard.
"""

import cv2
import math
import time
import numpy as np

from config import EAR_HISTORY_LEN


C_GREEN = (50, 220, 50)
C_RED = (30, 30, 230)
C_YELLOW = (0, 220, 220)
C_CYAN = (220, 200, 0)
C_WHITE = (240, 240, 240)
C_MUTED = (150, 150, 150)
C_PANEL = (28, 28, 28)
C_DARK = (10, 10, 10)

FONT = cv2.FONT_HERSHEY_SIMPLEX

FLASH_STAGE1_HZ = 1.5
FLASH_STAGE2_HZ = 3.0
FLASH_STAGE1_ALPHA = 0.35
FLASH_STAGE2_ALPHA = 0.50
BORDER_THICKNESS = 18


def _alpha_rect(frame, x, y, w, h, color, alpha=0.55):
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def _panel(frame, x, y, w, h, title=None, title_color=C_WHITE, alpha=0.58,
           border_color=(90, 90, 90)):
    _alpha_rect(frame, x, y, w, h, C_PANEL, alpha=alpha)
    cv2.rectangle(frame, (x, y), (x + w, y + h), border_color, 1)
    if title:
        cv2.putText(frame, title, (x + 10, y + 18), FONT,
                    0.52, title_color, 1, cv2.LINE_AA)


def _bar(frame, x, y, w, h, value, max_val, fill_color, bg_color=(60, 60, 60)):
    cv2.rectangle(frame, (x, y), (x + w, y + h), bg_color, -1)
    fraction = 0.0 if max_val <= 0 else min(max(value / max_val, 0.0), 1.0)
    filled = int(w * fraction)
    if filled > 0:
        cv2.rectangle(frame, (x, y), (x + filled, y + h), fill_color, -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), C_WHITE, 1)


def _flash_intensity(hz):
    return max(0.0, math.sin(2 * math.pi * hz * time.time()))


def _pose_text(det):
    if det.head_pose is None:
        return "P:-- Y:-- R:--"
    pitch, yaw, roll = det.head_pose
    return f"P:{pitch:+.0f} Y:{yaw:+.0f} R:{roll:+.0f}"


def _alarm_text(alarm_stage):
    return {0: "off", 1: "stage 1", 2: "stage 2"}.get(alarm_stage, "unknown")


def _trend_text(trend):
    return {"↑": "UP", "↓": "DOWN", "→": "STABLE"}.get(trend, "STABLE")


def _wrap_text(text, width):
    words = text.split()
    if not words:
        return [""]

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _estimate_weather_fallback(env):
    brightness = env.night_mode.brightness
    if brightness >= 170:
        condition = "Clouds"
    elif brightness >= 120:
        condition = "Clear"
    elif brightness >= 80:
        condition = "Haze"
    else:
        condition = "Dark"

    temperature_c = 18.0 + (brightness / 255.0) * 12.0
    wind_mps = 1.0 if env.blind_spot.left_alert or env.blind_spot.right_alert else 0.0
    return condition, temperature_c, wind_mps, 0


def draw_flash(frame, alarm_stage):
    if alarm_stage == 0:
        return

    ih, iw = frame.shape[:2]

    if alarm_stage == 1:
        intensity = _flash_intensity(FLASH_STAGE1_HZ)
        alpha = FLASH_STAGE1_ALPHA * intensity
        overlay = frame.copy()
        color = (0, 200, 220)
        t = BORDER_THICKNESS
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
        cv2.rectangle(frame, (0, 0), (iw - 1, ih - 1),
                      (0, 0, 255), BORDER_THICKNESS * 2)


class HUD:
    def __init__(self):
        self.show_settings = False

    def draw_eyes(self, frame, det, state):
        if not det.face_found:
            return

        color = C_RED if state.eyes_confirmed_closed else C_GREEN
        for pts in (det.left_eye_pts, det.right_eye_pts):
            if len(pts) >= 2:
                cv2.polylines(
                    frame,
                    [np.array(pts, dtype=np.int32)],
                    True,
                    color,
                    1,
                    cv2.LINE_AA,
                )

        for iris_pts in (det.left_iris_pts, det.right_iris_pts):
            if len(iris_pts) >= 3:
                center = tuple(np.mean(np.array(iris_pts), axis=0).astype(int))
                radius = max(3, int(
                    np.mean([np.linalg.norm(np.array(p) - np.array(center)) for p in iris_pts])))
                cv2.circle(frame, center, radius, C_CYAN, 1, cv2.LINE_AA)

    def draw_status_panel(self, frame, det, state, alarm_stage):
        px, py, pw, ph = 12, 12, 286, 190
        _panel(frame, px, py, pw, ph, alpha=0.52)

        active_color = C_YELLOW if not det.face_found else (
            C_RED if state.eyes_confirmed_closed else C_GREEN)
        active_label = "NO FACE" if not det.face_found else (
            "EYES CLOSED" if state.eyes_confirmed_closed else "EYES OPEN")
        active_seconds = state.eyes_closed_seconds if state.eyes_confirmed_closed else state.eyes_open_seconds

        label_scale = 0.70
        label_x = px + 10
        label_y = py + 24
        cv2.putText(frame, active_label, (label_x, label_y),
                    FONT, label_scale, active_color, 2, cv2.LINE_AA)
        label_width = cv2.getTextSize(active_label, FONT, label_scale, 2)[0][0]
        cv2.putText(frame, f"{active_seconds:.1f}s", (label_x + label_width + 12,
                                                      label_y), FONT, label_scale, active_color, 2, cv2.LINE_AA)

        mar_status = "yawn" if state.yawning else "ok"
        mar_color = C_YELLOW if state.yawning else C_WHITE

        lines = [
            ("EAR", f"L:{det.left_ear:.2f}   R:{det.right_ear:.2f}   Thr:{state.ear_threshold:.2f}", C_WHITE),
            ("MAR", f"{det.mar:.2f}   {mar_status}", mar_color),
            ("Pose", _pose_text(det), C_WHITE),
            ("Alarm", _alarm_text(alarm_stage),
             active_color if alarm_stage else C_GREEN),
        ]

        ty = py + 50
        for label, text, value_color in lines:
            cv2.putText(frame, label, (px + 10, ty), FONT,
                        0.48, C_MUTED, 1, cv2.LINE_AA)
            cv2.putText(frame, text, (px + 54, ty), FONT,
                        0.48, value_color, 1, cv2.LINE_AA)
            ty += 24

        cv2.putText(frame, f"Drowsiness score: {state.score:.0f}/100",
                    (px + 10, py + ph - 26), FONT, 0.46, C_WHITE, 1, cv2.LINE_AA)
        _bar(frame, px + 10, py + ph - 16, pw - 20, 11, state.score, 100,
             C_GREEN if state.score < 35 else C_YELLOW if state.score < 65 else C_RED)

    def draw_session_stats(self, frame, state):
        ih, iw = frame.shape[:2]
        px, py, pw, ph = iw - 208, 12, 196, 92
        _panel(frame, px, py, pw, ph, alpha=0.52)

        elapsed = int(time.time() - state.session_start)
        minutes, seconds = divmod(elapsed, 60)
        closed_events = sum(
            1 for event in state.events if event.kind == "closed")

        lines = [
            f"Session   {minutes:02d}:{seconds:02d}",
            f"Closed events: {closed_events}",
            f"Yawns:    {state.total_yawn_count}",
            f"Alarms:   {state.total_alarm_count}",
        ]

        ty = py + 20
        for text in lines:
            cv2.putText(frame, text, (px + 10, ty), FONT,
                        0.50, C_WHITE, 1, cv2.LINE_AA)
            ty += 20

    def draw_ear_history(self, frame, state):
        ih, iw = frame.shape[:2]
        px, py, pw, ph = 10, ih - 82, 238, 72
        _panel(frame, px, py, pw, ph, alpha=0.52)

        cv2.putText(frame, "EAR history", (px + 8, py + 16),
                    FONT, 0.45, C_WHITE, 1, cv2.LINE_AA)

        gx1, gy1 = px + 8, py + 24
        gx2, gy2 = px + pw - 8, py + ph - 10
        cv2.rectangle(frame, (gx1, gy1), (gx2, gy2), (70, 70, 70), 1)

        history = np.array(list(state.ear_history), dtype=np.float32)
        if history.size >= 2:
            max_ear = max(0.45, float(np.max(history)) + 0.02)
            min_ear = min(0.05, float(np.min(history)) - 0.02)
            span = max(max_ear - min_ear, 1e-4)
            x_vals = np.linspace(
                gx1 + 1, gx2 - 1, history.size).astype(np.int32)
            y_vals = gy2 - ((history - min_ear) / span *
                            (gy2 - gy1 - 2)).astype(np.int32)
            points = np.column_stack((x_vals, y_vals)).reshape(-1, 1, 2)
            cv2.polylines(frame, [points], False, C_GREEN, 1, cv2.LINE_AA)

            threshold_y = gy2 - \
                int(((state.ear_threshold - min_ear) / span) * (gy2 - gy1 - 2))
            threshold_y = max(gy1, min(gy2, threshold_y))
            cv2.line(frame, (gx1, threshold_y),
                     (gx2, threshold_y), C_YELLOW, 1, cv2.LINE_AA)

        footer = "Q=quit   C=calibrate   S=settings"
        cv2.putText(frame, footer, (px + 6, py + ph - 4),
                    FONT, 0.31, C_MUTED, 1, cv2.LINE_AA)

    def draw_calibration(self, frame, state):
        if not state.calibrating:
            return

        ih, iw = frame.shape[:2]
        pw, ph = 330, 44
        px, py = (iw - pw) // 2, ih - 58
        _panel(frame, px, py, pw, ph, alpha=0.60, border_color=C_YELLOW)
        cv2.putText(frame, "Calibration in progress",
                    (px + 10, py + 18), FONT, 0.48, C_WHITE, 1, cv2.LINE_AA)
        _bar(frame, px + 10, py + 25, pw - 20, 10,
             state.calib_progress, 1.0, C_YELLOW)

    def draw(self, frame, det, state, alarm_stage):
        draw_flash(frame, alarm_stage)
        self.draw_eyes(frame, det, state)
        self.draw_status_panel(frame, det, state, alarm_stage)
        self.draw_session_stats(frame, state)
        self.draw_ear_history(frame, state)
        self.draw_calibration(frame, state)


def draw_safety_panel(frame, engine):
    ih, iw = frame.shape[:2]
    px, py, pw, ph = iw - 228, ih - 112, 218, 102
    score = engine.safety_score.score
    color = engine.safety_score.color

    _panel(frame, px, py, pw, ph, title="SAFETY SCORE",
           alpha=0.62, border_color=color)

    score_text = f"{score:.0f}/100"
    trend_text = _trend_text(engine.safety_score.trend)
    cv2.putText(frame, score_text, (px + 10, py + 48),
                FONT, 1.00, color, 2, cv2.LINE_AA)
    cv2.putText(frame, trend_text, (px + 146, py + 45),
                FONT, 0.52, color, 2, cv2.LINE_AA)
    cv2.putText(frame, engine.safety_score.label,
                (px + 10, py + 69), FONT, 0.72, color, 2, cv2.LINE_AA)
    _bar(frame, px + 10, py + 78, pw - 20, 10, score, 100, color)
    cv2.putText(frame, f"Drive time: {engine.drive_timer.elapsed_str}",
                (px + 10, py + 96), FONT, 0.40, C_WHITE, 1, cv2.LINE_AA)


def draw_environment_panel(frame, env):
    ih, iw = frame.shape[:2]
    px, py, pw, ph = iw - 228, ih - 300, 218, 170
    _panel(frame, px, py, pw, ph, title="ENVIRONMENT",
           title_color=C_CYAN, alpha=0.60)

    mode_text = "Night" if env.night_mode.is_night else "Day"
    lux_est = int((env.night_mode.brightness / 255.0) * 30000)
    cv2.putText(frame, f"Mode:  {mode_text}   lux~{lux_est}", (px + 10, py + 36), FONT,
                0.48, C_GREEN if not env.night_mode.is_night else C_YELLOW, 1, cv2.LINE_AA)

    adv = env.weather.advisory
    if adv is not None:
        wx_color = adv.risk_color
        wx_label = f"Wx:    {adv.condition}  R{adv.risk_level}"
        wx_detail = f"{adv.temp_c:.1f}C   {adv.wind_mps:.0f} m/s"
        wx_note = None
    else:
        condition, temp_c, wind_mps, risk_level = _estimate_weather_fallback(
            env)
        wx_color = C_GREEN
        wx_label = f"Wx:    {condition}  R{risk_level}"
        wx_detail = f"{temp_c:.1f}C   {wind_mps:.0f} m/s"
        wx_note = "local estimate"

    cv2.putText(frame, wx_label, (px + 10, py + 58),
                FONT, 0.48, wx_color, 1, cv2.LINE_AA)
    cv2.putText(frame, wx_detail, (px + 10, py + 80),
                FONT, 0.46, C_WHITE, 1, cv2.LINE_AA)
    if wx_note:
        cv2.putText(frame, wx_note, (px + 118, py + 80),
                    FONT, 0.32, C_MUTED, 1, cv2.LINE_AA)

    base_x = px + 10
    base_y = py + 104
    cv2.putText(frame, "Blind:", (base_x, base_y),
                FONT, 0.48, C_WHITE, 1, cv2.LINE_AA)
    cv2.putText(frame, "L", (base_x + 58, base_y), FONT, 0.48,
                C_GREEN if env.blind_spot.left_alert else C_MUTED, 2, cv2.LINE_AA)
    cv2.putText(frame, "R", (base_x + 92, base_y), FONT, 0.48,
                C_GREEN if env.blind_spot.right_alert else C_MUTED, 2, cv2.LINE_AA)
    cv2.putText(frame, f"[{env.blind_spot.status_str}]",
                (base_x + 118, base_y), FONT, 0.40, C_WHITE, 1, cv2.LINE_AA)

    hazards = env.hazards.recent_hazards
    if hazards:
        latest = hazards[0]
        hazard_text = f"Hazards: {latest.kind} {latest.age_minutes:.0f}m ago"
    else:
        hazard_text = "Hazards: none reported"

    cv2.putText(frame, hazard_text, (px + 10, py + 126),
                FONT, 0.44, C_MUTED, 1, cv2.LINE_AA)
    cv2.putText(frame, "P=pothole  A=animal  X=accident  D=debris",
                (px + 10, py + 149), FONT, 0.27, C_MUTED, 1, cv2.LINE_AA)


def draw_safety_message(frame, engine):
    message = engine.hud_message
    if not message:
        return

    ih, iw = frame.shape[:2]
    lines = _wrap_text(message, 54)[:2]
    line_height = 20
    padding = 12
    box_width = min(620, iw - 120)
    box_height = padding * 2 + len(lines) * line_height + 6
    px = max(20, (iw - box_width) // 2)
    py = ih - 150

    _panel(frame, px, py, box_width, box_height, title="SAFETY AWARENESS",
           title_color=C_YELLOW, alpha=0.66, border_color=C_YELLOW)

    ty = py + 36
    for line in lines:
        cv2.putText(frame, line, (px + 12, ty), FONT,
                    0.54, C_WHITE, 1, cv2.LINE_AA)
        ty += line_height
