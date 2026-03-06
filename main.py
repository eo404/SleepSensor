import cv2
import pygame
import time
import os
from dataclasses import dataclass

# ----------------------------
# Configuration
# ----------------------------
ALARM_FILE = "alarmaudio.mp3"
FACE_CASCADE_FILE = "haarcascade_frontalface_default.xml"
EYE_CASCADE_FILE = "haarcascade_eye.xml"

# Trigger if eyes are not detected for this many seconds
EYES_CLOSED_TRIGGER_SECONDS = 1.5

# To prevent rapid toggling: require eyes to be detected for this many seconds
# before stopping the alarm.
EYES_OPEN_CLEAR_SECONDS = 0.6

# If face disappears, decay the closed timer toward 0 at this rate (seconds per second).
# 1.0 means "count down as fast as real time".
NO_FACE_DECAY_RATE = 1.0

# Ignore very small faces (helps reduce background false detections)
MIN_FACE_AREA = 90 * 90  # pixels^2

# Eye detection tuning (Haar)
EYE_MIN_NEIGHBORS = 10
EYE_SCALE_FACTOR = 1.1
EYE_MIN_SIZE = (18, 18)  # tune for your camera distance

# Face detection tuning (Haar)
FACE_SCALE_FACTOR = 1.3
FACE_MIN_NEIGHBORS = 5


# ----------------------------
# Alarm helpers
# ----------------------------
class DummySound:
    def play(self, loops=0):
        print("Alarm sound not found. (DummySound)")

    def stop(self):
        pass


def load_sound(path: str):
    pygame.mixer.init()
    try:
        return pygame.mixer.Sound(path)
    except pygame.error as e:
        print(f"Error loading sound file: {e}")
        print(f"Working dir: {os.getcwd()}")
        print(f"Expected alarm file at: {os.path.abspath(path)}")
        return DummySound()


def load_cascade(path: str, what: str):
    cascade = cv2.CascadeClassifier(path)
    if cascade.empty():
        raise IOError(f"Could not load {what} cascade: {path}")
    return cascade


# ----------------------------
# State
# ----------------------------
@dataclass
class DrowsyState:
    eyes_closed_seconds: float = 0.0
    eyes_open_seconds: float = 0.0
    alarm_playing: bool = False


def choose_primary_face(faces):
    """Return the largest face rectangle (x,y,w,h) or None."""
    if len(faces) == 0:
        return None
    # faces is an array of (x,y,w,h)
    largest = max(faces, key=lambda r: r[2] * r[3])
    return tuple(map(int, largest))


def update_alarm(sound, state: DrowsyState):
    # Start alarm when closed long enough
    if state.eyes_closed_seconds >= EYES_CLOSED_TRIGGER_SECONDS and not state.alarm_playing:
        sound.play(loops=-1)
        state.alarm_playing = True

    # Stop alarm when open long enough
    if state.eyes_open_seconds >= EYES_OPEN_CLEAR_SECONDS and state.alarm_playing:
        sound.stop()
        state.alarm_playing = False


def clamp01(x):
    return max(0.0, x)


def main():
    sound = load_sound(ALARM_FILE)

    try:
        face_cascade = load_cascade(FACE_CASCADE_FILE, "face")
        eye_cascade = load_cascade(EYE_CASCADE_FILE, "eye")
    except IOError as e:
        print(f"Error loading cascade files: {e}")
        print("Ensure the cascade XML files are in the project folder.")
        return

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open video stream.")
        return

    font = cv2.FONT_HERSHEY_SIMPLEX
    state = DrowsyState()
    last_t = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            now = time.time()
            dt = now - last_t
            last_t = now
            # guard against huge dt spikes (debugger pause, etc.)
            dt = min(dt, 0.2)

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=FACE_SCALE_FACTOR,
                minNeighbors=FACE_MIN_NEIGHBORS
            )

            primary = choose_primary_face(faces)

            if primary is None or (primary[2] * primary[3]) < MIN_FACE_AREA:
                # No (usable) face: decay closed/open timers toward 0 so we don't
                # accidentally trigger based on stale state.
                state.eyes_closed_seconds = clamp01(state.eyes_closed_seconds - dt * NO_FACE_DECAY_RATE)
                state.eyes_open_seconds = clamp01(state.eyes_open_seconds - dt * NO_FACE_DECAY_RATE)

                cv2.putText(frame, "NO FACE", (20, 50), font, 1, (0, 255, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, f"Closed: {state.eyes_closed_seconds:.2f}s", (20, 80), font, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
                update_alarm(sound, state)

                cv2.imshow("Drowsiness Detector", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue

            x, y, w, h = primary
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            roi_gray = gray[y:y + h, x:x + w]
            roi_color = frame[y:y + h, x:x + w]

            # Restrict eye search to upper half of face (eyes are typically there)
            upper_h = h // 2
            eye_search_gray = roi_gray[0:upper_h, :]

            eyes = eye_cascade.detectMultiScale(
                eye_search_gray,
                scaleFactor=EYE_SCALE_FACTOR,
                minNeighbors=EYE_MIN_NEIGHBORS,
                minSize=EYE_MIN_SIZE
            )

            eyes_detected = len(eyes) > 0

            if not eyes_detected:
                state.eyes_closed_seconds += dt
                state.eyes_open_seconds = 0.0

                cv2.putText(frame, "EYES NOT DETECTED", (20, 50), font, 1, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.putText(frame, f"Closed: {state.eyes_closed_seconds:.2f}s", (20, 80), font, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
            else:
                state.eyes_open_seconds += dt
                state.eyes_closed_seconds = 0.0

                # Draw rectangles around detected eyes (offset because we used upper-half ROI)
                for (ex, ey, ew, eh) in eyes:
                    cv2.rectangle(roi_color, (ex, ey), (ex + ew, ey + eh), (0, 255, 0), 2)

                cv2.putText(frame, "EYES DETECTED", (20, 50), font, 1, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.putText(frame, f"Open: {state.eyes_open_seconds:.2f}s", (20, 80), font, 0.7, (0, 255, 0), 2, cv2.LINE_AA)

            update_alarm(sound, state)

            # Alarm indicator
            if state.alarm_playing:
                cv2.putText(frame, "ALARM!", (20, 120), font, 1, (0, 0, 255), 3, cv2.LINE_AA)

            cv2.imshow("Drowsiness Detector", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

    finally:
        # Always release resources
        try:
            sound.stop()
        except Exception:
            pass
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()