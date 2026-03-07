"""
core/detector.py  –  mediapipe 0.10.30+ (Tasks API, Python 3.13)
Uses FaceLandmarker via Tasks API since mp.solutions was removed in 0.10.30+.
"""

import math
import urllib.request
import os
import numpy as np
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode

from config import (
    DETECTION_CONFIDENCE, TRACKING_CONFIDENCE,
    LEFT_EYE, RIGHT_EYE, LEFT_IRIS, RIGHT_IRIS,
    MOUTH_TOP, MOUTH_BOTTOM, MOUTH_LEFT, MOUTH_RIGHT,
    HEAD_POSE_POINTS_IDX,
)

MODEL_PATH = "face_landmarker.task"
MODEL_URL  = ("https://storage.googleapis.com/mediapipe-models/"
              "face_landmarker/face_landmarker/float16/latest/face_landmarker.task")


def _ensure_model():
    if not os.path.exists(MODEL_PATH):
        print(f"[Detector] Downloading face_landmarker model (~30 MB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
        print("[Detector] Model downloaded.")


# ── geometry ──────────────────────────────────────────────────────────────────

def _dist(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def _px(lm, idx, w, h):
    p = lm[idx]
    return (p.x * w, p.y * h)

def compute_ear(lm, indices, w, h):
    pts = [_px(lm, i, w, h) for i in indices]
    A = _dist(pts[1], pts[5])
    B = _dist(pts[2], pts[4])
    C = _dist(pts[0], pts[3])
    return (A + B) / (2.0 * C) if C else 0.0

def compute_mar(lm, w, h):
    v  = _dist(_px(lm, MOUTH_TOP,    w, h), _px(lm, MOUTH_BOTTOM, w, h))
    hz = _dist(_px(lm, MOUTH_LEFT,   w, h), _px(lm, MOUTH_RIGHT,  w, h))
    return v / hz if hz else 0.0

_MODEL_PTS = np.array([
    (  0.,  0.,   0.), (-30.,-30.,-30.), (30.,-30.,-30.),
    (-25., 20., -20.), ( 25., 20., -20.), (0., 50., -30.),
], dtype=np.float64)

def compute_head_pose(lm, w, h):
    pts = np.array([_px(lm, i, w, h) for i in HEAD_POSE_POINTS_IDX], dtype=np.float64)
    cam = np.array([[w,0,w/2],[0,w,h/2],[0,0,1]], dtype=np.float64)
    ok, rvec, _ = cv2.solvePnP(_MODEL_PTS, pts, cam, np.zeros((4,1)),
                                flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return None
    R, _ = cv2.Rodrigues(rvec)
    sy = math.sqrt(R[0,0]**2 + R[1,0]**2)
    if sy >= 1e-6:
        p = math.atan2( R[2,1], R[2,2])
        y = math.atan2(-R[2,0], sy)
        r = math.atan2( R[1,0], R[0,0])
    else:
        p = math.atan2(-R[1,2], R[1,1])
        y = math.atan2(-R[2,0], sy)
        r = 0.0
    return tuple(math.degrees(a) for a in (p, y, r))


# ── result ────────────────────────────────────────────────────────────────────

class DetectionResult:
    __slots__ = ("face_found","left_ear","right_ear","mean_ear","mar","head_pose",
                 "left_eye_pts","right_eye_pts","left_iris_pts","right_iris_pts",
                 "raw_landmarks","img_w","img_h")
    def __init__(self):
        self.face_found=False; self.left_ear=0.0; self.right_ear=0.0
        self.mean_ear=0.0; self.mar=0.0; self.head_pose=None
        self.left_eye_pts=[]; self.right_eye_pts=[]
        self.left_iris_pts=[]; self.right_iris_pts=[]
        self.raw_landmarks=None; self.img_w=0; self.img_h=0


# ── detector ──────────────────────────────────────────────────────────────────

class Detector:
    def __init__(self):
        _ensure_model()
        base_opts = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
        opts = FaceLandmarkerOptions(
            base_options=base_opts,
            running_mode=RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=DETECTION_CONFIDENCE,
            min_face_presence_confidence=DETECTION_CONFIDENCE,
            min_tracking_confidence=TRACKING_CONFIDENCE,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = FaceLandmarker.create_from_options(opts)

    def process(self, bgr_frame) -> DetectionResult:
        res = DetectionResult()
        h, w = bgr_frame.shape[:2]
        res.img_w, res.img_h = w, h

        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        detection = self._landmarker.detect(mp_image)

        if not detection.face_landmarks:
            return res

        res.face_found = True
        lm = detection.face_landmarks[0]   # list of NormalizedLandmark
        res.raw_landmarks = lm

        res.left_ear  = compute_ear(lm, LEFT_EYE,  w, h)
        res.right_ear = compute_ear(lm, RIGHT_EYE, w, h)
        res.mean_ear  = (res.left_ear + res.right_ear) / 2.0
        res.mar       = compute_mar(lm, w, h)
        res.head_pose = compute_head_pose(lm, w, h)

        def pts(idx_list):
            return [(int(lm[i].x * w), int(lm[i].y * h)) for i in idx_list]

        res.left_eye_pts  = pts(LEFT_EYE)
        res.right_eye_pts = pts(RIGHT_EYE)
        try:
            res.left_iris_pts  = pts(LEFT_IRIS)
            res.right_iris_pts = pts(RIGHT_IRIS)
        except Exception:
            pass

        return res

    def close(self):
        try:
            self._landmarker.close()
        except Exception:
            pass