"""
Face recognition using face_recognition library.

Recognizes authorized users and triggers lock for unknown faces.
"""

from __future__ import annotations

import logging
import pickle
import time
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from threading import Lock

import cv2
import numpy as np

from screenguard.core.base import BaseDetector
from screenguard.core.events import Event, EventBus, EventType
from screenguard.core.settings import Settings, get_config_dir

logger = logging.getLogger(__name__)


def get_faces_dir() -> Path:
    """Get the directory for storing face encodings."""
    faces_dir = get_config_dir() / "faces"
    faces_dir.mkdir(parents=True, exist_ok=True)
    return faces_dir


def get_encodings_file() -> Path:
    """Get the path to the face encodings file."""
    return get_faces_dir() / "encodings.pkl"


class FaceRecognizer(BaseDetector):
    """
    Recognizes authorized users using face_recognition library.
    
    Features:
    - Register new faces with names
    - Recognize faces and match against registered users
    - Lock screen for unknown faces or no face
    
    Attributes:
        settings: Application settings
        event_bus: Event bus for communication
    """
    
    def __init__(self, settings: Settings, event_bus: Optional[EventBus] = None) -> None:
        """
        Initialize the face recognizer.
        
        Args:
            settings: Application settings
            event_bus: Event bus for communication
        """
        super().__init__(settings, event_bus)
        
        self._capture: Optional[cv2.VideoCapture] = None
        self._known_encodings: List[np.ndarray] = []
        self._known_names: List[str] = []
        self._encodings_lock = Lock()
        
        # State tracking
        self._authorized_detected = False
        self._face_lost_time: Optional[float] = None
        self._warning_shown = False
        self._frame_fail_count = 0
        
        # Load saved encodings
        self._load_encodings()
    
    @property
    def is_detected(self) -> bool:
        """Return True if an authorized face is currently detected."""
        return self._authorized_detected
    
    @property
    def has_registered_faces(self) -> bool:
        """Return True if there are registered faces."""
        with self._encodings_lock:
            return len(self._known_encodings) > 0
    
    @property
    def registered_names(self) -> List[str]:
        """Get list of registered user names."""
        with self._encodings_lock:
            return list(self._known_names)
    
    def _load_encodings(self) -> None:
        """Load face encodings from file."""
        encodings_file = get_encodings_file()
        
        if encodings_file.exists():
            try:
                with open(encodings_file, "rb") as f:
                    data = pickle.load(f)
                
                with self._encodings_lock:
                    self._known_encodings = data.get("encodings", [])
                    self._known_names = data.get("names", [])
                
                logger.info(f"Loaded {len(self._known_names)} registered face(s)")
                
            except Exception as e:
                logger.error(f"Failed to load face encodings: {e}")
    
    def _save_encodings(self) -> None:
        """Save face encodings to file."""
        encodings_file = get_encodings_file()
        
        try:
            with self._encodings_lock:
                data = {
                    "encodings": self._known_encodings,
                    "names": self._known_names
                }
            
            with open(encodings_file, "wb") as f:
                pickle.dump(data, f)
            
            logger.info(f"Saved {len(self._known_names)} face encoding(s)")
            
        except Exception as e:
            logger.error(f"Failed to save face encodings: {e}")
    
    def register_face(self, name: str, frame: Optional[np.ndarray] = None) -> bool:
        """
        Register a new face.
        
        Args:
            name: Name to associate with the face
            frame: Optional frame to use, captures new frame if not provided
            
        Returns:
            True if registration was successful
        """
        try:
            import face_recognition
        except ImportError:
            logger.error("face_recognition library not installed")
            return False
        
        # Capture frame if not provided
        if frame is None:
            if self._capture is None or not self._capture.isOpened():
                logger.error("Camera not available for face registration")
                return False
            
            ret, frame = self._capture.read()
            if not ret or frame is None:
                logger.error("Failed to capture frame for registration")
                return False
        
        # Convert BGR to RGB for face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Find face locations and encodings
        face_locations = face_recognition.face_locations(rgb_frame)
        
        if len(face_locations) == 0:
            logger.warning("No face detected in frame")
            return False
        
        if len(face_locations) > 1:
            logger.warning("Multiple faces detected, using the first one")
        
        # Get face encoding
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        if len(face_encodings) == 0:
            logger.error("Failed to compute face encoding")
            return False
        
        # Save the encoding
        with self._encodings_lock:
            self._known_encodings.append(face_encodings[0])
            self._known_names.append(name)
        
        self._save_encodings()
        
        logger.info(f"Successfully registered face for: {name}")
        return True
    
    def remove_face(self, name: str) -> bool:
        """
        Remove a registered face.
        
        Args:
            name: Name of the face to remove
            
        Returns:
            True if removal was successful
        """
        with self._encodings_lock:
            if name not in self._known_names:
                logger.warning(f"Face not found: {name}")
                return False
            
            index = self._known_names.index(name)
            del self._known_names[index]
            del self._known_encodings[index]
        
        self._save_encodings()
        
        logger.info(f"Removed face: {name}")
        return True
    
    def _setup(self) -> None:
        """Initialize camera."""
        logger.info(f"Initializing camera (index: {self._settings.camera_index})")
        
        # Open camera with appropriate backend for macOS
        if sys.platform == "darwin":
            self._capture = cv2.VideoCapture(self._settings.camera_index, cv2.CAP_AVFOUNDATION)
        else:
            self._capture = cv2.VideoCapture(self._settings.camera_index)
        
        if not self._capture.isOpened():
            raise RuntimeError(f"Failed to open camera at index {self._settings.camera_index}")
        
        # Optimize camera settings
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._capture.set(cv2.CAP_PROP_FPS, 15)
        
        # Warm up camera
        logger.info("Warming up camera...")
        for _ in range(10):
            self._capture.read()
            time.sleep(0.1)
        
        logger.info("Camera initialized successfully")
        
        self._event_bus.emit(Event(
            type=EventType.DETECTOR_STARTED,
            data={"detector": "face_recognizer"},
            source=self.name
        ))
    
    def _cleanup(self) -> None:
        """Release camera resources."""
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        
        self._event_bus.emit(Event(
            type=EventType.DETECTOR_STOPPED,
            data={"detector": "face_recognizer"},
            source=self.name
        ))
        
        logger.info("Camera released")
    
    def _run(self) -> None:
        """Main recognition loop."""
        check_interval = self._settings.check_interval_ms / 1000.0
        camera_was_disabled = False
        
        while not self._stop_event.is_set():
            if not self._settings.face_detection_enabled:
                # Release camera when disabled
                if self._capture is not None and not camera_was_disabled:
                    logger.info("Face detection disabled - releasing camera")
                    self._capture.release()
                    self._capture = None
                    camera_was_disabled = True
                
                time.sleep(check_interval)
                continue
            
            # Reopen camera if it was disabled
            if camera_was_disabled or self._capture is None:
                logger.info("Face detection enabled - reopening camera")
                if sys.platform == "darwin":
                    self._capture = cv2.VideoCapture(self._settings.camera_index, cv2.CAP_AVFOUNDATION)
                else:
                    self._capture = cv2.VideoCapture(self._settings.camera_index)
                
                if self._capture.isOpened():
                    self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    # Quick warmup
                    for _ in range(3):
                        self._capture.read()
                    camera_was_disabled = False
                else:
                    logger.error("Failed to reopen camera")
                    time.sleep(check_interval)
                    continue
            
            result = self._recognize_face()
            self._process_recognition_result(result)
            
            self._stop_event.wait(check_interval)
    
    def _recognize_face(self) -> Dict[str, Any]:
        """
        Capture frame and recognize face.
        
        Returns:
            Dict with keys:
            - face_found: bool - whether any face was found
            - authorized: bool - whether an authorized face was found
            - name: Optional[str] - name of recognized person
        """
        result = {"face_found": False, "authorized": False, "name": None}
        
        if self._capture is None:
            return result
        
        # Try to capture frame
        frame = None
        for _ in range(3):
            ret, frame = self._capture.read()
            if ret and frame is not None:
                break
            time.sleep(0.05)
        
        if frame is None:
            self._frame_fail_count += 1
            if self._frame_fail_count % 20 == 1:
                logger.warning(f"Failed to capture frame (count: {self._frame_fail_count})")
            return result
        
        self._frame_fail_count = 0
        
        # If no faces registered, just do basic face detection
        if not self.has_registered_faces:
            # Fall back to Haar cascade for basic detection
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
            
            if len(faces) > 0:
                result["face_found"] = True
                result["authorized"] = True  # No registered faces = any face is authorized
            
            return result
        
        # Use face_recognition for recognition
        try:
            import face_recognition
        except ImportError:
            logger.error("face_recognition not available")
            return result
        
        # Convert to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Resize for faster processing
        small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
        
        # Find faces
        face_locations = face_recognition.face_locations(small_frame)
        
        if len(face_locations) == 0:
            return result
        
        result["face_found"] = True
        
        # Get encodings
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)
        
        # Check each face against known faces
        with self._encodings_lock:
            for face_encoding in face_encodings:
                if len(self._known_encodings) == 0:
                    continue
                
                # Compare with known faces
                matches = face_recognition.compare_faces(
                    self._known_encodings, 
                    face_encoding,
                    tolerance=0.6
                )
                
                if True in matches:
                    match_index = matches.index(True)
                    result["authorized"] = True
                    result["name"] = self._known_names[match_index]
                    break
        
        return result
    
    def _process_recognition_result(self, result: Dict[str, Any]) -> None:
        """Process recognition result and emit events."""
        current_time = time.time()
        
        if result["authorized"]:
            # Authorized user detected
            if not self._authorized_detected:
                name = result.get("name", "Unknown")
                logger.info(f"Authorized face detected: {name}")
                self._event_bus.emit(Event(
                    type=EventType.FACE_DETECTED,
                    data={"name": name},
                    source=self.name
                ))
            
            if self._face_lost_time is not None:
                logger.info("Authorized user returned - cancelling lock")
                
                # Cancel warning overlay
                try:
                    from screenguard.ui.warning_overlay import cancel_warning
                    cancel_warning()
                except Exception:
                    pass
                
                self._event_bus.emit(Event(
                    type=EventType.LOCK_CANCELLED,
                    source=self.name
                ))
            
            self._authorized_detected = True
            self._face_lost_time = None
            self._warning_shown = False
            
        else:
            # No authorized face
            reason = "unknown_face" if result["face_found"] else "no_face"
            
            # Emit unknown face event (with 10 second cooldown)
            if result["face_found"] and not result["authorized"]:
                if not hasattr(self, '_last_unknown_face_time'):
                    self._last_unknown_face_time = 0
                
                if current_time - self._last_unknown_face_time > 10:
                    logger.warning("Unknown face detected!")
                    self._event_bus.emit(Event(
                        type=EventType.UNKNOWN_FACE_DETECTED,
                        data={"message": "Tanınmayan yüz algılandı!"},
                        source=self.name
                    ))
                    self._last_unknown_face_time = current_time
            
            if self._authorized_detected:
                logger.info(f"Authorized face lost ({reason}) - starting countdown")
                self._face_lost_time = current_time
                self._authorized_detected = False
                self._warning_shown = False
                
                self._event_bus.emit(Event(
                    type=EventType.FACE_LOST,
                    data={"reason": reason},
                    source=self.name
                ))
            
            # Check timeout
            if self._face_lost_time is not None:
                elapsed = current_time - self._face_lost_time
                timeout = self._settings.face_absence_timeout_seconds
                warning_time = timeout - self._settings.notification_seconds_before
                
                if (
                    not self._warning_shown 
                    and elapsed >= warning_time 
                    and self._settings.show_notifications
                ):
                    self._warning_shown = True
                    remaining = timeout - elapsed
                    reason_text = "Seni tanımıyorum!" if reason == "unknown_face" else "Yüz algılanmadı!"
                    logger.info(f"Lock warning: {remaining:.1f}s remaining - {reason_text}")
                    
                    self._event_bus.emit(Event(
                        type=EventType.LOCK_WARNING,
                        data={"seconds_remaining": remaining, "reason": reason, "message": reason_text},
                        source=self.name
                    ))
                
                if elapsed >= timeout:
                    logger.info(f"Timeout - requesting lock ({reason})")
                    self._event_bus.emit(Event(
                        type=EventType.LOCK_REQUESTED,
                        data={"reason": reason},
                        source=self.name
                    ))
                    self._face_lost_time = None
                    self._warning_shown = False
    
    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture and return a frame from the camera."""
        if self._capture is None or not self._capture.isOpened():
            return None
        
        ret, frame = self._capture.read()
        if not ret or frame is None:
            return None
        
        return frame
