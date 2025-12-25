"""Core module - settings, events, and base abstractions."""

from screenguard.core.settings import Settings
from screenguard.core.events import Event, EventBus
from screenguard.core.base import BaseDetector, BaseMonitor

__all__ = ["Settings", "Event", "EventBus", "BaseDetector", "BaseMonitor"]
