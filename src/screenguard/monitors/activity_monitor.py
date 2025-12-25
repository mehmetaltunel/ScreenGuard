"""
Activity monitoring using pynput.

Monitors mouse and keyboard activity to detect user inactivity.
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Optional

from pynput import keyboard, mouse

from screenguard.core.base import BaseMonitor
from screenguard.core.events import Event, EventBus, EventType
from screenguard.core.settings import Settings

logger = logging.getLogger(__name__)


class ActivityMonitor(BaseMonitor):
    """
    Monitors user activity via mouse and keyboard.
    
    Tracks last activity time and emits INACTIVITY_TIMEOUT when
    the user has been inactive for the configured duration.
    
    Uses pynput listeners which run in their own threads.
    """
    
    def __init__(self, settings: Settings, event_bus: Optional[EventBus] = None) -> None:
        """
        Initialize the activity monitor.
        
        Args:
            settings: Application settings
            event_bus: Event bus for communication
        """
        super().__init__(settings, event_bus)
        
        self._last_activity_time: float = time.time()
        self._activity_lock = Lock()
        self._mouse_listener: Optional[mouse.Listener] = None
        self._keyboard_listener: Optional[keyboard.Listener] = None
        self._warning_shown = False
        self._was_inactive = False
    
    def reset_timer(self) -> None:
        """Reset the inactivity timer."""
        with self._activity_lock:
            self._last_activity_time = time.time()
            
            if self._was_inactive:
                self._was_inactive = False
                self._warning_shown = False
                self._event_bus.emit(Event(
                    type=EventType.ACTIVITY_DETECTED,
                    source=self.name
                ))
    
    def _get_inactive_seconds(self) -> float:
        """Get the number of seconds since last activity."""
        with self._activity_lock:
            return time.time() - self._last_activity_time
    
    def _on_activity(self, *args) -> None:
        """Called when any mouse or keyboard activity is detected."""
        self.reset_timer()
    
    def _setup(self) -> None:
        """Start mouse and keyboard listeners."""
        logger.info("Starting activity listeners")
        
        # Mouse listener
        self._mouse_listener = mouse.Listener(
            on_move=self._on_activity,
            on_click=self._on_activity,
            on_scroll=self._on_activity
        )
        self._mouse_listener.start()
        
        # Keyboard listener
        self._keyboard_listener = keyboard.Listener(
            on_press=self._on_activity,
            on_release=self._on_activity
        )
        self._keyboard_listener.start()
        
        self._event_bus.emit(Event(
            type=EventType.DETECTOR_STARTED,
            data={"detector": "activity"},
            source=self.name
        ))
        
        logger.info("Activity listeners started")
    
    def _cleanup(self) -> None:
        """Stop mouse and keyboard listeners."""
        if self._mouse_listener is not None:
            self._mouse_listener.stop()
            self._mouse_listener = None
        
        if self._keyboard_listener is not None:
            self._keyboard_listener.stop()
            self._keyboard_listener = None
        
        self._event_bus.emit(Event(
            type=EventType.DETECTOR_STOPPED,
            data={"detector": "activity"},
            source=self.name
        ))
        
        logger.info("Activity listeners stopped")
    
    def _run(self) -> None:
        """Main monitoring loop."""
        check_interval = 1.0  # Check every second
        
        while not self._stop_event.is_set():
            if not self._settings.inactivity_detection_enabled:
                self._stop_event.wait(check_interval)
                continue
            
            inactive_seconds = self._get_inactive_seconds()
            timeout = self._settings.inactivity_timeout_seconds
            warning_time = timeout - self._settings.notification_seconds_before
            
            # Mark as inactive after some time
            if inactive_seconds >= 5 and not self._was_inactive:
                self._was_inactive = True
            
            # Show warning before lock
            if (
                not self._warning_shown 
                and inactive_seconds >= warning_time 
                and self._settings.show_notifications
            ):
                self._warning_shown = True
                remaining = timeout - inactive_seconds
                logger.info(f"Inactivity warning: {remaining:.1f}s remaining")
                self._event_bus.emit(Event(
                    type=EventType.LOCK_WARNING,
                    data={"seconds_remaining": remaining, "reason": "inactivity"},
                    source=self.name
                ))
            
            # Request lock on timeout
            if inactive_seconds >= timeout:
                logger.info("Inactivity timeout - requesting lock")
                self._event_bus.emit(Event(
                    type=EventType.LOCK_REQUESTED,
                    data={"reason": "inactivity"},
                    source=self.name
                ))
                # Reset timer to avoid repeated lock requests
                self.reset_timer()
            
            self._stop_event.wait(check_interval)
