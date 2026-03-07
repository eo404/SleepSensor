"""
config.py – All tuneable constants in one place.
"""

# ── Files ─────────────────────────────────────────────────────────────────────
ALARM_FILE = "alarmaudio.mp3"

# ── Timing ────────────────────────────────────────────────────────────────────
EYES_CLOSED_TRIGGER_SECONDS = 1.5   # seconds closed → first alarm stage
EYES_OPEN_CLEAR_SECONDS     = 0.6   # seconds open   → stop alarm
NO_FACE_DECAY_RATE          = 1.0   # timer decay rate when no face visible

# ── EAR (Eye Aspect Ratio) ────────────────────────────────────────────────────
EAR_THRESHOLD_DEFAULT = 0.20        # overridden after calibration
EAR_CONSEC_FRAMES     = 2           # frames below threshold → confirmed closed
CALIBRATION_SECONDS   = 5           # duration of eyes-open baseline capture

# ── MAR (Mouth Aspect Ratio) yawn detection ───────────────────────────────────
MAR_THRESHOLD      = 0.65           # above this → yawn detected
MAR_CONSEC_FRAMES  = 4              # frames above threshold → confirmed yawn
YAWN_COOLDOWN_SEC  = 8.0            # ignore repeated yawns within this window

# ── Head pose ─────────────────────────────────────────────────────────────────
PITCH_DROWSY_DEG   = 20.0           # head-nod angle (forward tilt) threshold
HEAD_POSE_CONSEC   = 6              # frames past threshold → drowsy head pose

# ── Drowsiness score ──────────────────────────────────────────────────────────
SCORE_CLOSED_PER_SEC = 2.0          # points added per second eyes are closed
SCORE_YAWN_EVENT     = 10.0         # points added per yawn
SCORE_HEAD_POSE      = 1.5          # points per second of bad head pose
SCORE_DECAY_PER_SEC  = 0.5          # points removed per second when alert

# ── Alarm escalation ──────────────────────────────────────────────────────────
ALARM_STAGE1_SEC   = 1.5            # soft beep
ALARM_STAGE2_SEC   = 3.0            # loud alarm

# ── MediaPipe ─────────────────────────────────────────────────────────────────
DETECTION_CONFIDENCE = 0.5
TRACKING_CONFIDENCE  = 0.5

# ── MediaPipe landmark indices ────────────────────────────────────────────────
LEFT_EYE   = [362, 385, 387, 263, 373, 380]
RIGHT_EYE  = [33,  160, 158, 133, 153, 144]
LEFT_IRIS  = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]

# Mouth landmarks for MAR (outer lip)
MOUTH_TOP    = 13
MOUTH_BOTTOM = 14
MOUTH_LEFT   = 78
MOUTH_RIGHT  = 308
MOUTH_TOP2   = 312
MOUTH_BOTTOM2= 317

# 3-D head-pose reference points (canonical model)
HEAD_POSE_POINTS_IDX = [1, 33, 263, 61, 291, 199]

# ── EAR history for on-screen graph ──────────────────────────────────────────
EAR_HISTORY_LEN = 100               # number of samples to plot
