"""
test_camera.py
Simple camera test script to diagnose camera issues.
"""

import cv2
import sys

def test_camera():
    print("SleepSensor Camera Diagnostic")
    print("=" * 40)
    
    # Test different camera indices
    working_cameras = []
    
    for i in range(5):  # Test indices 0-4
        print(f"\nTesting camera index {i}...")
        
        # Try with DirectShow backend (Windows)
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        
        if cap.isOpened():
            print(f"  ✓ Camera {i} opened successfully")
            
            # Try to read a frame
            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                print(f"  ✓ Frame read successful: {w}x{h}")
                working_cameras.append(i)
                
                # Test frame properties
                fps = cap.get(cv2.CAP_PROP_FPS)
                print(f"  ✓ FPS: {fps}")
                
                # Show the frame for 2 seconds
                cv2.imshow(f"Camera {i} Test", frame)
                cv2.waitKey(2000)
                cv2.destroyAllWindows()
                
            else:
                print(f"  ✗ Camera {i} opened but cannot read frames")
            
            cap.release()
        else:
            print(f"  ✗ Camera {i} failed to open")
    
    print(f"\n" + "=" * 40)
    if working_cameras:
        print(f"✓ Working cameras found: {working_cameras}")
        print(f"✓ Recommended: Use camera index {working_cameras[0]}")
        print("\nYour SleepSensor should work now!")
    else:
        print("✗ No working cameras found")
        print("\nTroubleshooting:")
        print("1. Check camera is connected")
        print("2. Close other camera apps (Skype, Teams, Zoom, etc.)")
        print("3. Check Windows Camera Privacy Settings:")
        print("   Settings > Privacy & Security > Camera")
        print("4. Try running as administrator")
        print("5. Restart your computer")

if __name__ == "__main__":
    try:
        test_camera()
    except Exception as e:
        print(f"\nError during camera test: {e}")
        print("This suggests OpenCV or camera driver issues.")
    
    input("\nPress Enter to exit...")