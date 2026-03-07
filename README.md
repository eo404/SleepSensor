# SleepSensor

Real-time driver drowsiness detection with a full Safety Awareness Engine.

## System Architecture

```
Camera
   │
   ▼
Drowsiness Detection  (MediaPipe Face Mesh – EAR / MAR / Head Pose)
   │
   ▼
Safety Awareness Engine
   │
   ├─ Fatigue Alerts          → voice warning when eyes close
   ├─ Driving Time Monitoring → break reminders at 30 / 60 / 90 / 120 min
   ├─ Safety Messages         → yawn, head-pose, wellness tips
   └─ Driver Safety Score     → composite 0–100 score (SAFE / CAUTION / AT RISK / DANGEROUS)
   │
   ▼
Driver Interface  (OpenCV HUD + pyttsx3 voice)
```

## Features

| Feature | Detail |
|---|---|
| EAR eye detection | Eye Aspect Ratio via 468-pt mesh |
| Yawn detection | Mouth Aspect Ratio (MAR) |
| Head pose | Pitch/yaw/roll via solvePnP — detects nodding |
| Escalating alarm | Stage 1 (1.5s) → Stage 2 (3s) |
| Screen flash | Yellow border (stage 1) → red full-screen (stage 2) |
| Voice fatigue alerts | Rotating phrases, repeats every 8 s while active |
| Yawn voice alert | Speaks when yawn detected (30 s cooldown) |
| Head-pose voice alert | Speaks when head droops (20 s cooldown) |
| Drive time monitoring | Break reminders at 30 / 60 / 90 / 120 min |
| Driver Safety Score | 0–100 composite with trend arrow |
| Calibration | Press C — 5-second EAR baseline |
| CSV logging | Events + per-frame metrics in logs/sessions/ |
| Settings overlay | Press S |

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py
```

## File Structure

```
SleepSensor/
├── main.py
├── config.py
├── requirements.txt
├── core/
│   ├── app.py          ← main loop
│   ├── detector.py     ← MediaPipe EAR/MAR/head-pose
│   └── state.py        ← drowsiness state machine
├── safety/             ← Safety Awareness Engine
│   ├── engine.py       ← orchestrator
│   ├── voice.py        ← TTS worker thread
│   ├── drive_timer.py  ← break reminders
│   └── safety_score.py ← composite safety score
├── alerts/
│   └── alarm.py        ← alarm stage manager
├── ui/
│   └── hud.py          ← all OpenCV drawing + safety panel
└── logs/
    ├── logger.py
    └── sessions/
```

## Hotkeys

| Key | Action |
|-----|--------|
| Q | Quit |
| C | Calibrate EAR threshold |
| S | Toggle settings overlay |