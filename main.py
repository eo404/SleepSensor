"""
SleepSensor – Driver Drowsiness Detection
==========================================
Entry point. Run:  python main.py
Press  q  to quit,  c  to calibrate,  s  to toggle settings overlay.
"""

from core.app import App

if __name__ == "__main__":
    app = App()
    app.run()
