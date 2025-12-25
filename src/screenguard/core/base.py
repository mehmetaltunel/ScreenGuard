"""
Base classes for detectors and monitors.

Provides abstract interfaces that all detection/monitoring components must implement.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from threading import Thread, Event as ThreadEvent
from typing import Optional

from screenguard.core.events import EventBus
from screenguard.core.settings import Settings

logger = logging.getLogger(__name__)


class BaseComponent(ABC):
    """
    Base class for all background components.
    
    Provides common functionality for starting, stopping, and running
    background threads with proper lifecycle management.
    """
    
    def __init__(self, settings: Settings, event_bus: Optional[EventBus] = None) -> None:
        """
        Initialize the component.
        
        Args:
            settings: Application settings
            event_bus: Event bus for communication (uses singleton if not provided)
        """
        self._settings = settings
        self._event_bus = event_bus or EventBus()
        self._thread: Optional[Thread] = None
        self._stop_event = ThreadEvent()
        self._running = False
    
    @property
    def name(self) -> str:
        """Get the component name for logging."""
        return self.__class__.__name__
    
    @property
    def is_running(self) -> bool:
        """Check if the component is currently running."""
        return self._running and self._thread is not None and self._thread.is_alive()
    
    def start(self) -> None:
        """Start the component in a background thread."""
        if self.is_running:
            logger.warning(f"{self.name} is already running")
            return
        
        self._stop_event.clear()
        self._running = True
        self._thread = Thread(target=self._run_wrapper, daemon=True, name=self.name)
        self._thread.start()
        
        logger.info(f"{self.name} started")
    
    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the component gracefully.
        
        Args:
            timeout: Maximum seconds to wait for thread to stop
        """
        if not self._running:
            return
        
        logger.info(f"Stopping {self.name}...")
        self._running = False
        self._stop_event.set()
        
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(f"{self.name} did not stop gracefully")
        
        self._cleanup()
        logger.info(f"{self.name} stopped")
    
    def _run_wrapper(self) -> None:
        """Wrapper around run() with error handling."""
        try:
            self._setup()
            self._run()
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            from screenguard.core.events import Event, EventType
            self._event_bus.emit(Event(
                type=EventType.DETECTOR_ERROR,
                data={"error": str(e), "component": self.name},
                source=self.name
            ))
        finally:
            self._cleanup()
    
    def _setup(self) -> None:
        """Setup resources before running. Override in subclass if needed."""
        pass
    
    def _cleanup(self) -> None:
        """Cleanup resources after stopping. Override in subclass if needed."""
        pass
    
    @abstractmethod
    def _run(self) -> None:
        """
        Main run loop. Must be implemented by subclasses.
        
        Should check self._stop_event.is_set() periodically and exit when True.
        """
        pass


class BaseDetector(BaseComponent):
    """
    Base class for detection components (e.g., face detection).
    
    Detectors observe some input and emit events when conditions change.
    """
    
    @property
    @abstractmethod
    def is_detected(self) -> bool:
        """Return True if the target is currently detected."""
        pass


class BaseMonitor(BaseComponent):
    """
    Base class for monitoring components (e.g., activity monitoring).
    
    Monitors track user activity and emit events on state changes.
    """
    
    @abstractmethod
    def reset_timer(self) -> None:
        """Reset the inactivity timer due to detected activity."""
        pass
