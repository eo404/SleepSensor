"""
safety/environment.py
Environment detection for driver assistance - simulates vehicle environmental conditions.

Detects day/night mode, estimates ambient light, and provides weather-like conditions
based on camera frame brightness analysis.
"""

import cv2
import numpy as np
import time
import random


class EnvironmentMonitor:
    """
    Monitors environmental conditions using camera frame analysis.
    Provides vehicle dashboard-style environment information.
    """
    
    def __init__(self):
        self.brightness_history = []
        self.max_history = 30  # Keep 30 frame history for stability
        self.last_update = time.time()
        
        # Simulated temperature and wind (in real application, these would come from sensors)
        self.base_temp = 22  # Base temperature
        self.base_wind = 0.5  # Base wind speed
        
    def _calculate_brightness(self, frame):
        """Calculate average brightness of the frame."""
        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
            
        # Calculate mean brightness (0-255)
        return np.mean(gray)
    
    def _determine_mode(self, brightness):
        """Determine DAY/NIGHT mode based on brightness."""
        # Thresholds for day/night detection
        if brightness > 120:
            return "DAY"
        elif brightness < 60:
            return "NIGHT"
        else:
            return "DUSK"
    
    def _estimate_lux(self, brightness):
        """Convert brightness (0-255) to estimated lux value."""
        # Rough approximation: map 0-255 brightness to 0-10000 lux range
        # This is a simplified conversion - real lux meters would be more accurate
        lux = int((brightness / 255.0) * 10000)
        return max(0, min(lux, 10000))
    
    def _determine_weather(self, brightness):
        """Estimate weather condition based on brightness patterns."""
        if len(self.brightness_history) < 5:
            return "Unknown"
            
        # Calculate recent brightness variance for weather prediction
        recent_brightness = self.brightness_history[-10:]
        avg_brightness = np.mean(recent_brightness)
        brightness_variance = np.var(recent_brightness)
        
        # Weather classification based on brightness and variance
        if avg_brightness > 160:
            if brightness_variance < 50:
                return "Sunny"
            else:
                return "Partly Cloudy"
        elif avg_brightness > 100:
            if brightness_variance < 30:
                return "Cloudy"
            else:
                return "Partly Cloudy"
        elif avg_brightness > 60:
            if brightness_variance > 100:
                return "Overcast"
            else:
                return "Cloudy"
        else:
            return "Night/Dark"
    
    def _simulate_temperature(self, brightness, mode):
        """Simulate temperature based on environmental conditions."""
        now = time.time()
        
        # Base temperature varies with brightness (warmer in bright conditions)
        brightness_factor = (brightness - 128) / 128.0  # -1 to 1
        temp_adjustment = brightness_factor * 8  # ±8°C variation
        
        # Add some time-based variation (simulating temperature changes)
        time_factor = np.sin(now / 300) * 3  # 5-minute cycle, ±3°C
        
        # Night/day adjustment
        if mode == "NIGHT":
            temp_adjustment -= 5
        elif mode == "DAY":
            temp_adjustment += 3
            
        final_temp = self.base_temp + temp_adjustment + time_factor
        return round(final_temp, 1)
    
    def _simulate_wind(self, brightness_variance):
        """Simulate wind speed based on brightness variance (indicating movement/weather)."""
        # Higher variance might indicate more dynamic conditions
        variance_factor = min(brightness_variance / 100.0, 2.0)  # Cap at 2.0
        
        # Add some randomness for realistic wind variation
        random_factor = (random.random() - 0.5) * 2  # -1 to 1
        
        wind_speed = self.base_wind + variance_factor + random_factor
        return round(max(0, wind_speed), 1)
    
    def update(self, frame):
        """
        Update environment data based on current camera frame.
        
        Args:
            frame: OpenCV camera frame (BGR)
            
        Returns:
            dict: Environment data containing mode, lux, weather, temp, wind
        """
        # Calculate frame brightness
        brightness = self._calculate_brightness(frame)
        
        # Update brightness history
        self.brightness_history.append(brightness)
        if len(self.brightness_history) > self.max_history:
            self.brightness_history.pop(0)
        
        # Determine environmental conditions
        mode = self._determine_mode(brightness)
        lux = self._estimate_lux(brightness)
        weather = self._determine_weather(brightness)
        
        # Calculate variance for additional parameters
        brightness_variance = np.var(self.brightness_history) if len(self.brightness_history) > 1 else 0
        
        # Simulate temperature and wind
        temperature = self._simulate_temperature(brightness, mode)
        wind_speed = self._simulate_wind(brightness_variance)
        
        self.last_update = time.time()
        
        return {
            "mode": mode,
            "lux": lux,
            "weather": weather,
            "temp": temperature,
            "wind": wind_speed,
            "brightness": round(brightness, 1)  # For debugging/calibration
        }
    
    def get_status_summary(self):
        """Get a brief status summary for logging/debugging."""
        if not self.brightness_history:
            return "No data"
            
        avg_brightness = np.mean(self.brightness_history)
        return f"Avg brightness: {avg_brightness:.1f}, History: {len(self.brightness_history)} frames"