"""
Main application entry point.

Orchestrates all components and handles application lifecycle.
"""

from __future__ import annotations

import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from screenguard.core.events import Event, EventBus, EventType
from screenguard.core.settings import Settings
from screenguard.detectors.face_detector import FaceDetector
from screenguard.monitors.activity_monitor import ActivityMonitor
from screenguard.platform.screen_locker import get_screen_locker, ScreenLocker
from screenguard.ui.tray import TrayApplication

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path.home() / ".screenguard" / "screenguard.log")
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
        self._face_detector: Optional[FaceDetector] = None
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
        
        # Face detector
        self._face_detector = FaceDetector(self._settings, self._event_bus)
        
        # Activity monitor
        self._activity_monitor = ActivityMonitor(self._settings, self._event_bus)
        
        # Tray application
        self._tray_app = TrayApplication(
            settings=self._settings,
            event_bus=self._event_bus,
            on_quit=self.shutdown
        )
        
        logger.info("All components initialized")
    
    def _start_detectors(self) -> None:
        """Start detection and monitoring components."""
        logger.info("Starting detectors...")
        
        if self._face_detector is not None:
            try:
                self._face_detector.start()
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
            self._start_detectors()
            
            # Run tray application (blocking)
            if self._tray_app is not None:
                self._tray_app.run()
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.exception(f"Application error: {e}")
        finally:
            self.shutdown()
    
    def shutdown(self) -> None:
        """Shutdown all components gracefully."""
        logger.info("Shutting down ScreenGuard...")
        
        # Stop detectors
        if self._face_detector is not None:
            self._face_detector.stop()
        
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
