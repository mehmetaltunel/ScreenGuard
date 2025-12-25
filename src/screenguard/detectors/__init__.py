"""Face detection module."""

from screenguard.detectors.face_detector import FaceDetector

# FaceRecognizer is optional - requires face_recognition library
try:
    from screenguard.detectors.face_recognizer import FaceRecognizer
    __all__ = ["FaceDetector", "FaceRecognizer"]
except ImportError:
    __all__ = ["FaceDetector"]

