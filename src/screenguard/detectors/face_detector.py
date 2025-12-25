"""
Face detection using OpenCV and Haar Cascade.

Monitors webcam feed and emits events when face presence changes.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

from screenguard.core.base import BaseDetector
from screenguard.core.events import Event, EventBus, EventType
from screenguard.core.settings import Settings

logger = logging.getLogger(__name__)


class FaceDetector(BaseDetector):
    """
    Detects face presence using webcam and OpenCV Haar Cascade.
    
    Emits FACE_DETECTED when a face appears and FACE_LOST when it disappears.
    Uses a countdown timer after face loss before emitting lock request.
    
    Attributes:
        settings: Application settings
        event_bus: Event bus for communication
    """
    
    # Haar cascade file path (bundled with OpenCV)
    CASCADE_FILE = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    
    def __init__(self, settings: Settings, event_bus: Optional[EventBus] = None) -> None:
        """
        Initialize the face detector.
        
        Args:
            settings: Application settings
            event_bus: Event bus for communication
        """
        super().__init__(settings, event_bus)
        
        self._capture: Optional[cv2.VideoCapture] = None
        self._cascade: Optional[cv2.CascadeClassifier] = None
        self._face_detected = False
        self._face_lost_time: Optional[float] = None
        self._warning_shown = False
    
    @property
    def is_detected(self) -> bool:
        """Return True if a face is currently detected."""
        return self._face_detected
    
    def _setup(self) -> None:
        """Initialize camera and cascade classifier."""
        logger.info(f"Initializing camera (index: {self._settings.camera_index})")
        
        # Load Haar cascade
        self._cascade = cv2.CascadeClassifier(self.CASCADE_FILE)
        if self._cascade.empty():
            raise RuntimeError("Failed to load Haar cascade classifier")
        
        # Open camera with appropriate backend for macOS
        import sys
        if sys.platform == "darwin":
            # Use AVFoundation backend on macOS
            self._capture = cv2.VideoCapture(self._settings.camera_index, cv2.CAP_AVFOUNDATION)
        else:
            self._capture = cv2.VideoCapture(self._settings.camera_index)
        
        if not self._capture.isOpened():
            raise RuntimeError(f"Failed to open camera at index {self._settings.camera_index}")
        
        # Optimize camera settings for performance
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        self._capture.set(cv2.CAP_PROP_FPS, 15)
        
        # Warm up camera - discard first few frames
        logger.info("Warming up camera...")
        for _ in range(10):
            self._capture.read()
            time.sleep(0.1)
        
        logger.info("Camera initialized successfully")
        
        self._event_bus.emit(Event(
            type=EventType.DETECTOR_STARTED,
            data={"detector": "face"},
            source=self.name
        ))
    
    def _cleanup(self) -> None:
        """Release camera resources."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        
        self._event_bus.emit(Event(
            type=EventType.DETECTOR_STOPPED,
            data={"detector": "face"},
            source=self.name
        ))
        
        logger.info("Camera released")
    
    def _run(self) -> None:
        """Main detection loop."""
        check_interval = self._settings.check_interval_ms / 1000.0
        
        while not self._stop_event.is_set():
            if not self._settings.face_detection_enabled:
                time.sleep(check_interval)
                continue
            
            face_found = self._detect_face()
            self._process_detection_result(face_found)
            
            # Sleep until next check
            self._stop_event.wait(check_interval)
    
    def _detect_face(self) -> bool:
        """
        Capture frame and detect face.
        
        Returns:
            True if at least one face is detected
        """
        if self._capture is None or self._cascade is None:
            return False
        
        # Try to capture frame with retries
        frame = None
        for attempt in range(3):
            ret, frame = self._capture.read()
            if ret and frame is not None:
                break
            time.sleep(0.05)
        
        if frame is None:
            # Only log occasionally to avoid spam
            if not hasattr(self, '_frame_fail_count'):
                self._frame_fail_count = 0
            self._frame_fail_count += 1
            if self._frame_fail_count % 20 == 1:  # Log every 20th failure
                logger.warning(f"Failed to capture frame (count: {self._frame_fail_count})")
            return False
        
        # Reset failure count on success
        self._frame_fail_count = 0
        
        # Convert to grayscale for detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self._cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        return len(faces) > 0
    
    def _process_detection_result(self, face_found: bool) -> None:
        """
        Process detection result and emit appropriate events.
        
        Args:
            face_found: Whether a face was detected in the current frame
        """
        current_time = time.time()
        
        if face_found:
            # Face detected - reset everything
            if not self._face_detected:
                logger.info("Face detected")
                self._event_bus.emit(Event(
                    type=EventType.FACE_DETECTED,
                    source=self.name
                ))
            
            if self._face_lost_time is not None:
                # User came back before timeout
                logger.info("User returned - cancelling lock countdown")
                self._event_bus.emit(Event(
                    type=EventType.LOCK_CANCELLED,
                    source=self.name
                ))
            
            self._face_detected = True
            self._face_lost_time = None
            self._warning_shown = False
            
        else:
            # No face detected
            if self._face_detected:
                # Just lost the face
                logger.info("Face lost - starting countdown")
                self._face_lost_time = current_time
                self._face_detected = False
                self._warning_shown = False
                
                self._event_bus.emit(Event(
                    type=EventType.FACE_LOST,
                    source=self.name
                ))
            
            # Check timeout
            if self._face_lost_time is not None:
                elapsed = current_time - self._face_lost_time
                timeout = self._settings.face_absence_timeout_seconds
                warning_time = timeout - self._settings.notification_seconds_before
                
                # Show warning before lock
                if (
                    not self._warning_shown 
                    and elapsed >= warning_time 
                    and self._settings.show_notifications
                ):
                    self._warning_shown = True
                    remaining = timeout - elapsed
                    logger.info(f"Lock warning: {remaining:.1f}s remaining")
                    self._event_bus.emit(Event(
                        type=EventType.LOCK_WARNING,
                        data={"seconds_remaining": remaining, "reason": "face_absence"},
                        source=self.name
                    ))
                
                # Request lock
                if elapsed >= timeout:
                    logger.info("Face absence timeout - requesting lock")
                    self._event_bus.emit(Event(
                        type=EventType.LOCK_REQUESTED,
                        data={"reason": "face_absence"},
                        source=self.name
                    ))
                    # Reset timer to avoid repeated lock requests
                    self._face_lost_time = None
                    self._warning_shown = False
