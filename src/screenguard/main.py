"""
Main application entry point.

Orchestrates all components and handles application lifecycle.
"""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path
from typing import Optional, Union

from screenguard.core.events import Event, EventBus, EventType
from screenguard.core.settings import Settings
from screenguard.monitors.activity_monitor import ActivityMonitor
from screenguard.platform.screen_locker import get_screen_locker, ScreenLocker
from screenguard.ui.tray import TrayApplication


def hide_from_dock():
    """Hide the application from macOS Dock (run as menu bar only app)."""
    if sys.platform == "darwin":
        try:
            import AppKit
            info = AppKit.NSBundle.mainBundle().infoDictionary()
            info["LSUIElement"] = "1"
        except ImportError:
            # PyObjC not installed, try alternative method
            pass


# Hide from Dock on macOS
hide_from_dock()

# Create log directory if it doesn't exist
log_dir = Path.home() / ".screenguard"
log_dir.mkdir(parents=True, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / "screenguard.log")
    ]
)

logger = logging.getLogger(__name__)


class ScreenGuardApp:
    """
    Main application class that orchestrates all components.
    
    Manages the lifecycle of detectors, monitors, and the tray application.
    Handles events and coordinates screen locking.
    """
    
    def __init__(self) -> None:
        """Initialize the application."""
        logger.info("Initializing ScreenGuard")
        
        # Load settings
        self._settings = Settings.load()
        
        # Initialize event bus (singleton)
        self._event_bus = EventBus()
        
        # Initialize components
        self._face_recognizer = None  # Will try FaceRecognizer first, fall back to FaceDetector
        self._activity_monitor: Optional[ActivityMonitor] = None
        self._screen_locker: Optional[ScreenLocker] = None
        self._tray_app: Optional[TrayApplication] = None
        
        # Subscribe to events
        self._event_bus.subscribe(EventType.LOCK_REQUESTED, self._on_lock_requested)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)
    
    def _on_lock_requested(self, event: Event) -> None:
        """Handle lock request events."""
        reason = event.data.get("reason", "unknown") if event.data else "unknown"
        logger.info(f"Lock requested: {reason}")
        
        if self._screen_locker is not None:
            success = self._screen_locker.lock()
            
            self._event_bus.emit(Event(
                type=EventType.LOCK_EXECUTED,
                data={"success": success, "reason": reason},
                source="ScreenGuardApp"
            ))
    
    def _initialize_components(self) -> None:
        """Initialize all components."""
        logger.info("Initializing components...")
        
        # Screen locker (platform-specific)
        try:
            self._screen_locker = get_screen_locker()
            logger.info(f"Screen locker initialized for {self._screen_locker.platform_name}")
        except NotImplementedError as e:
            logger.error(f"Failed to initialize screen locker: {e}")
            raise
        
        # Try to use FaceRecognizer (with face_recognition library)
        # Fall back to FaceDetector if not available
        try:
            from screenguard.detectors.face_recognizer import FaceRecognizer
            self._face_recognizer = FaceRecognizer(self._settings, self._event_bus)
            logger.info("Using FaceRecognizer (with face recognition support)")
        except ImportError as e:
            logger.warning(f"face_recognition not available: {e}")
            logger.info("Falling back to basic FaceDetector")
            from screenguard.detectors.face_detector import FaceDetector
            self._face_recognizer = FaceDetector(self._settings, self._event_bus)
        
        # Activity monitor
        self._activity_monitor = ActivityMonitor(self._settings, self._event_bus)
        
        # Find logo file
        import os
        logo_path = None
        # Try common locations
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "logo.jpeg",  # Project root
            Path(__file__).parent.parent / "assets" / "logo.jpeg",
            Path(__file__).parent.parent / "logo.jpeg",
        ]
        for p in possible_paths:
            if p.exists():
                logo_path = p
                break
        
        # Tray application
        self._tray_app = TrayApplication(
            settings=self._settings,
            event_bus=self._event_bus,
            on_quit=self.shutdown,
            face_recognizer=self._face_recognizer,
            icon_path=logo_path
        )
        
        logger.info("All components initialized")
    
    def _start_detectors(self) -> None:
        """Start detection and monitoring components."""
        logger.info("Starting detectors...")
        
        if self._face_recognizer is not None:
            try:
                self._face_recognizer.start()
            except Exception as e:
                logger.error(f"Failed to start face detector: {e}")
                # Continue without face detection
        
        if self._activity_monitor is not None:
            self._activity_monitor.start()
        
        logger.info("Detectors started")
    
    def run(self) -> None:
        """Run the application."""
        logger.info("Starting ScreenGuard")
        
        try:
            self._initialize_components()
            
            # Run first-time setup if needed
            if not self._settings.first_run_completed:
                logger.info("First run - showing setup wizard")
                self._run_first_time_setup()
                
                # Give time for OpenCV to fully cleanup
                import time
                import cv2
                cv2.destroyAllWindows()
                time.sleep(0.5)
            
            self._start_detectors()
            
            logger.info("Starting tray application...")
            
            # Run tray application (blocking)
            if self._tray_app is not None:
                self._tray_app.run()
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.exception(f"Application error: {e}")
        finally:
            self.shutdown()
    
    def _run_first_time_setup(self) -> None:
        """Run first-time setup wizard."""
        try:
            from screenguard.ui.settings_window import run_first_time_setup
            
            if self._face_recognizer is not None:
                success = run_first_time_setup(self._settings, self._face_recognizer)
                if success:
                    logger.info("First-time setup completed")
                else:
                    logger.info("First-time setup cancelled, exiting")
                    sys.exit(0)
        except Exception as e:
            logger.error(f"First-time setup failed: {e}")
        
        # Always mark first run as completed to prevent loop
        self._settings.first_run_completed = True
        self._settings.save()
        logger.info("Settings saved - first run completed")
    
    def shutdown(self) -> None:
        """Shutdown all components gracefully."""
        logger.info("Shutting down ScreenGuard...")
        
        # Stop detectors
        if self._face_recognizer is not None:
            self._face_recognizer.stop()
        
        if self._activity_monitor is not None:
            self._activity_monitor.stop()
        
        # Stop tray
        if self._tray_app is not None:
            self._tray_app.stop()
        
        # Save settings
        self._settings.save()
        
        logger.info("ScreenGuard shut down complete")


def main() -> None:
    """Main entry point."""
    # Ensure config directory exists
    config_dir = Path.home() / ".screenguard"
    config_dir.mkdir(parents=True, exist_ok=True)
    
    app = ScreenGuardApp()
    app.run()


if __name__ == "__main__":
    main()
