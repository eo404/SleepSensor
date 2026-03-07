"""
demo_mode.py
Demo mode for SleepSensor that simulates camera input to test the environment detection 
and other features without requiring a physical camera.
"""

import cv2
import numpy as np
import time
import math

from safety.environment import EnvironmentMonitor
from ui.hud import draw_environment_panel


def create_demo_frame(width=1280, height=720, brightness=128, pattern="noise"):
    """Create a synthetic demo frame with specified brightness."""
    
    if pattern == "noise":
        # Random noise pattern
        frame = np.random.randint(
            max(0, brightness - 30), 
            min(255, brightness + 30), 
            (height, width, 3), 
            dtype=np.uint8
        )
    elif pattern == "gradient":
        # Gradient pattern
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        for y in range(height):
            level = int(brightness + 50 * math.sin(y * math.pi / height))
            level = max(0, min(255, level))
            frame[y, :] = [level, level, level]
    else:
        # Solid color
        frame = np.full((height, width, 3), brightness, dtype=np.uint8)
    
    return frame


def demo_mode():
    """Run SleepSensor in demo mode without camera."""
    print("[Demo] SleepSensor Demo Mode - Environment Detection Test")
    print("       No camera required - synthetic data simulation")
    print("       Press Q to quit, 1-4 to change lighting conditions")
    
    # Initialize environment monitor
    env_monitor = EnvironmentMonitor()
    
    # Demo scenarios
    scenarios = {
        "1": ("Bright Day", 200, "noise"),
        "2": ("Normal Day", 150, "gradient"), 
        "3": ("Dusk", 90, "noise"),
        "4": ("Night", 30, "gradient")
    }
    
    current_scenario = "2"  # Start with normal day
    
    print(f"\nStarting demo with scenario: {scenarios[current_scenario][0]}")
    print("Keys: 1=Bright Day, 2=Normal Day, 3=Dusk, 4=Night, Q=Quit")
    
    while True:
        scenario_name, brightness, pattern = scenarios[current_scenario]
        
        # Create synthetic frame
        frame = create_demo_frame(brightness=brightness, pattern=pattern)
        
        # Update environment detection
        env_data = env_monitor.update(frame)
        
        # Draw environment panel on frame
        draw_environment_panel(frame, env_data)
        
        # Add demo info overlay
        cv2.putText(frame, f"DEMO MODE - {scenario_name}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
        
        cv2.putText(frame, f"Brightness: {brightness} | Pattern: {pattern}", 
                   (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                   
        cv2.putText(frame, "Keys: 1-4=Scenarios, Q=Quit", 
                   (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Show frame
        cv2.imshow("SleepSensor Demo - Environment Detection", frame)
        
        # Handle keyboard input
        key = cv2.waitKey(50) & 0xFF
        if key == ord('q'):
            break
        elif key in [ord('1'), ord('2'), ord('3'), ord('4')]:
            current_scenario = chr(key)
            scenario_name = scenarios[current_scenario][0]
            print(f"[Demo] Switched to: {scenario_name}")
        
        # Small delay for realistic frame rate
        time.sleep(0.033)  # ~30 FPS
    
    cv2.destroyAllWindows()
    print("[Demo] Demo mode finished")


if __name__ == "__main__":
    try:
        demo_mode()
    except KeyboardInterrupt:
        print("\n[Demo] Interrupted by user")
    except Exception as e:
        print(f"[Demo] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cv2.destroyAllWindows()