"""Tests for EventBus."""

import pytest
from screenguard.core.events import Event, EventBus, EventType


class TestEventBus:
    """Test cases for EventBus pub/sub system."""
    
    def setup_method(self):
        """Reset event bus before each test."""
        EventBus.reset_instance()
    
    def test_singleton(self):
        """Test that EventBus is a singleton."""
        bus1 = EventBus()
        bus2 = EventBus()
        
        assert bus1 is bus2
    
    def test_subscribe_and_emit(self):
        """Test basic subscribe and emit."""
        bus = EventBus()
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        bus.subscribe(EventType.FACE_DETECTED, handler)
        
        event = Event(type=EventType.FACE_DETECTED, source="test")
        bus.emit(event)
        
        assert len(received_events) == 1
        assert received_events[0].type == EventType.FACE_DETECTED
    
    def test_unsubscribe(self):
        """Test unsubscribe removes handler."""
        bus = EventBus()
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        unsubscribe = bus.subscribe(EventType.FACE_LOST, handler)
        
        # First event should be received
        bus.emit(Event(type=EventType.FACE_LOST, source="test"))
        assert len(received_events) == 1
        
        # Unsubscribe
        unsubscribe()
        
        # Second event should not be received
        bus.emit(Event(type=EventType.FACE_LOST, source="test"))
        assert len(received_events) == 1
    
    def test_subscribe_all(self):
        """Test subscribing to all events."""
        bus = EventBus()
        received_events = []
        
        def handler(event: Event):
            received_events.append(event)
        
        bus.subscribe_all(handler)
        
        bus.emit(Event(type=EventType.FACE_DETECTED, source="test"))
        bus.emit(Event(type=EventType.LOCK_REQUESTED, source="test"))
        
        assert len(received_events) == 2
    
    def test_handler_error_isolation(self):
        """Test that one handler error doesn't affect others."""
        bus = EventBus()
        received_events = []
        
        def failing_handler(event: Event):
            raise RuntimeError("Handler error")
        
        def working_handler(event: Event):
            received_events.append(event)
        
        bus.subscribe(EventType.FACE_DETECTED, failing_handler)
        bus.subscribe(EventType.FACE_DETECTED, working_handler)
        
        # Should not raise, and working handler should still receive
        bus.emit(Event(type=EventType.FACE_DETECTED, source="test"))
        
        assert len(received_events) == 1
