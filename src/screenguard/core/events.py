"""
Event system for loosely coupled communication between components.

Implements a simple pub/sub pattern for decoupled event handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events that can be emitted."""
    
    # Face detection events
    FACE_DETECTED = auto()
    FACE_LOST = auto()
    UNKNOWN_FACE_DETECTED = auto()  # Unknown/unregistered face detected
    
    # Activity events
    ACTIVITY_DETECTED = auto()
    INACTIVITY_TIMEOUT = auto()
    
    # Lock events
    LOCK_REQUESTED = auto()
    LOCK_WARNING = auto()  # Warning before lock
    LOCK_CANCELLED = auto()  # User returned before lock
    LOCK_EXECUTED = auto()
    
    # System events
    DETECTOR_STARTED = auto()
    DETECTOR_STOPPED = auto()
    DETECTOR_ERROR = auto()
    
    # Settings events
    SETTINGS_CHANGED = auto()


@dataclass
class Event:
    """
    Represents an event in the system.
    
    Attributes:
        type: The type of event
        data: Optional payload data
        timestamp: When the event occurred
        source: Name of the component that emitted the event
    """
    
    type: EventType
    data: Optional[Any] = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"
    
    def __str__(self) -> str:
        return f"Event({self.type.name}, source={self.source})"


# Type alias for event handlers
EventHandler = Callable[[Event], None]


class EventBus:
    """
    Central event bus for pub/sub communication.
    
    Thread-safe singleton that manages event subscriptions and dispatching.
    
    Example:
        >>> bus = EventBus()
        >>> bus.subscribe(EventType.FACE_LOST, lambda e: print("Face lost!"))
        >>> bus.emit(Event(EventType.FACE_LOST, source="face_detector"))
    """
    
    _instance: Optional[EventBus] = None
    _lock: Lock = Lock()
    
    def __new__(cls) -> EventBus:
        """Singleton pattern - only one event bus per application."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the event bus."""
        if self._initialized:
            return
        
        self._subscribers: Dict[EventType, List[EventHandler]] = {}
        self._global_subscribers: List[EventHandler] = []
        self._handler_lock = Lock()
        self._initialized = True
        
        logger.debug("EventBus initialized")
    
    def subscribe(
        self, 
        event_type: EventType, 
        handler: EventHandler
    ) -> Callable[[], None]:
        """
        Subscribe to a specific event type.
        
        Args:
            event_type: The type of event to subscribe to
            handler: Callback function to invoke when event occurs
            
        Returns:
            Unsubscribe function that can be called to remove the subscription
        """
        with self._handler_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
        
        logger.debug(f"Subscribed to {event_type.name}")
        
        # Return unsubscribe function
        def unsubscribe() -> None:
            self.unsubscribe(event_type, handler)
        
        return unsubscribe
    
    def subscribe_all(self, handler: EventHandler) -> Callable[[], None]:
        """
        Subscribe to all events.
        
        Args:
            handler: Callback function to invoke for any event
            
        Returns:
            Unsubscribe function
        """
        with self._handler_lock:
            self._global_subscribers.append(handler)
        
        logger.debug("Subscribed to all events")
        
        def unsubscribe() -> None:
            with self._handler_lock:
                if handler in self._global_subscribers:
                    self._global_subscribers.remove(handler)
        
        return unsubscribe
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """
        Unsubscribe from a specific event type.
        
        Args:
            event_type: The type of event to unsubscribe from
            handler: The handler to remove
        """
        with self._handler_lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(handler)
                    logger.debug(f"Unsubscribed from {event_type.name}")
                except ValueError:
                    pass  # Handler not found, ignore
    
    def emit(self, event: Event) -> None:
        """
        Emit an event to all subscribers.
        
        Args:
            event: The event to emit
        """
        logger.debug(f"Emitting {event}")
        
        with self._handler_lock:
            # Get handlers for this event type
            handlers = list(self._subscribers.get(event.type, []))
            global_handlers = list(self._global_subscribers)
        
        # Invoke specific handlers
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")
        
        # Invoke global handlers
        for handler in global_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in global event handler: {e}")
    
    def clear(self) -> None:
        """Clear all subscriptions. Useful for testing."""
        with self._handler_lock:
            self._subscribers.clear()
            self._global_subscribers.clear()
        
        logger.debug("EventBus cleared")
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        with cls._lock:
            cls._instance = None
