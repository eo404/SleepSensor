<<<<<<< HEAD
# SleepSensor 🚗💤

Real-time driver drowsiness detection using MediaPipe Face Mesh.

## Features

| Feature | Detail |
|---|---|
| **EAR eye detection** | Eye Aspect Ratio via 468-pt mesh – robust to glasses & lighting |
| **Iris tracking** | Iris landmarks drawn as circles on each eye |
| **Yawn detection** | Mouth Aspect Ratio (MAR) triggers yawn events |
| **Head pose** | Pitch/yaw/roll from solvePnP – detects nodding head |
| **Escalating alarm** | Stage 1 (soft, 1.5s) → Stage 2 (loud, 3s) |
| **Voice alert** | pyttsx3 says "Wake up!" on stage-2 escalation |
| **Adaptive calibration** | Press `C` to auto-set EAR threshold to your eyes |
| **Drowsiness score** | 0–100 fatigue score shown as on-screen bar |
| **EAR graph** | Real-time 100-sample history plotted bottom-left |
| **Session dashboard** | Elapsed time, event counts, alarm count top-right |
| **CSV logging** | Events + per-frame metrics saved to `logs/sessions/` |
| **Settings overlay** | Press `S` for live config display |

## Setup

```bash
# 1. Create & activate virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

## File Structure

```
SLEEPSENSOR/
├── main.py               ← entry point
├── config.py             ← all tuneable constants
├── requirements.txt
├── alarmaudio.mp3        ← your alarm sound
├── core/
│   ├── app.py            ← main loop
│   ├── detector.py       ← MediaPipe, EAR, MAR, head-pose
│   └── state.py          ← drowsiness state machine & scoring
├── alerts/
│   └── __init__.py       ← escalating alarm + voice (pyttsx3)
├── ui/
│   └── hud.py            ← all OpenCV HUD drawing
└── logs/
    ├── logger.py         ← CSV session writer
    └── sessions/         ← auto-created; one CSV pair per session
```

## Hotkeys

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `C` | Calibrate EAR threshold (keep eyes open for 5 s) |
| `S` | Toggle settings overlay |

## Tuning

Edit **`config.py`** to adjust thresholds without touching any logic:

- `EAR_THRESHOLD_DEFAULT` – default closed-eye threshold (calibration overrides)
- `EYES_CLOSED_TRIGGER_SECONDS` – seconds before alarm starts
- `MAR_THRESHOLD` – yawn sensitivity
- `PITCH_DROWSY_DEG` – head-nod angle for head-pose alert
- `SCORE_*` – drowsiness score weighting constants
=======

>>>>>>> 4611ed28827bd72f9029149ce23bd8ff4b3c284f
