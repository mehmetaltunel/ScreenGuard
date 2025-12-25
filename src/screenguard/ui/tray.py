"""
System tray application using pystray.

Provides a system tray icon with menu for controlling the application.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem, Menu

from screenguard.core.events import Event, EventBus, EventType
from screenguard.core.settings import Settings

logger = logging.getLogger(__name__)


def create_default_icon(size: int = 64) -> Image.Image:
    """
    Create a default icon if no icon file exists.
    
    Creates a simple shield-like icon with a lock symbol.
    
    Args:
        size: Icon size in pixels
        
    Returns:
        PIL Image object
    """
    # Create a new image with transparent background
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw a filled circle (shield base)
    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(46, 204, 113, 255),  # Green color
        outline=(39, 174, 96, 255),
        width=2
    )
    
    # Draw a simple lock shape
    lock_margin = size // 3
    lock_width = size // 3
    lock_height = size // 4
    lock_x = (size - lock_width) // 2
    lock_y = size // 2
    
    # Lock body
    draw.rectangle(
        [lock_x, lock_y, lock_x + lock_width, lock_y + lock_height],
        fill=(255, 255, 255, 255)
    )
    
    # Lock shackle (arc)
    shackle_width = lock_width * 0.6
    shackle_x = lock_x + (lock_width - shackle_width) // 2
    draw.arc(
        [shackle_x, lock_y - lock_height // 2, shackle_x + shackle_width, lock_y + 2],
        start=0,
        end=180,
        fill=(255, 255, 255, 255),
        width=3
    )
    
    return image


def create_disabled_icon(size: int = 64) -> Image.Image:
    """Create an icon indicating disabled state."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(149, 165, 166, 255),  # Gray color
        outline=(127, 140, 141, 255),
        width=2
    )
    
    return image


class TrayApplication:
    """
    System tray application for ScreenGuard.
    
    Provides menu items for:
    - Enabling/disabling face detection
    - Enabling/disabling inactivity detection
    - Accessing settings
    - Quitting the application
    """
    
    def __init__(
        self,
        settings: Settings,
        event_bus: Optional[EventBus] = None,
        on_quit: Optional[Callable[[], None]] = None,
        icon_path: Optional[Path] = None,
        face_recognizer: Optional[any] = None
    ) -> None:
        """
        Initialize the tray application.
        
        Args:
            settings: Application settings
            event_bus: Event bus for communication
            on_quit: Callback when user quits
            icon_path: Optional path to custom icon
            face_recognizer: Face recognizer for settings window
        """
        self._settings = settings
        self._event_bus = event_bus or EventBus()
        self._on_quit = on_quit
        self._icon_path = icon_path
        self._face_recognizer = face_recognizer
        self._icon: Optional[pystray.Icon] = None
        self._status_text = "Active"
        
        # Subscribe to events
        self._event_bus.subscribe(EventType.LOCK_WARNING, self._on_lock_warning)
        self._event_bus.subscribe(EventType.LOCK_EXECUTED, self._on_lock_executed)
        self._event_bus.subscribe(EventType.DETECTOR_ERROR, self._on_detector_error)
        self._event_bus.subscribe(EventType.UNKNOWN_FACE_DETECTED, self._on_unknown_face)
    
    def _load_icon(self) -> Image.Image:
        """Load or create the tray icon."""
        if self._icon_path and self._icon_path.exists():
            try:
                return Image.open(self._icon_path)
            except Exception as e:
                logger.warning(f"Failed to load icon: {e}")
        
        return create_default_icon()
    
    def _create_menu(self) -> Menu:
        """Create the tray menu."""
        return Menu(
            MenuItem(
                lambda text: f"ScreenGuard - {self._status_text}",
                action=None,
                enabled=False
            ),
            Menu.SEPARATOR,
            MenuItem(
                "⚙️ Ayarlar",
                self._open_settings
            ),
            Menu.SEPARATOR,
            MenuItem(
                lambda text: f"{'✓ ' if self._settings.face_detection_enabled else '  '}Yüz Tanıma",
                self._toggle_face_detection
            ),
            MenuItem(
                lambda text: f"{'✓ ' if self._settings.inactivity_detection_enabled else '  '}Hareketsizlik Kilitleme",
                self._toggle_inactivity_detection
            ),
            Menu.SEPARATOR,
            MenuItem(
                "🔒 Şimdi Kilitle",
                self._lock_now
            ),
            Menu.SEPARATOR,
            MenuItem(
                "❌ Çıkış",
                self._quit
            )
        )
    
    def _open_settings(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Open the settings window."""
        logger.info("Opening settings window")
        from screenguard.ui.settings_window import show_settings_window
        show_settings_window(self._settings, self._face_recognizer)
    
    def _toggle_face_detection(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Toggle face detection on/off."""
        self._settings.face_detection_enabled = not self._settings.face_detection_enabled
        self._settings.save()
        
        logger.info(f"Face detection {'enabled' if self._settings.face_detection_enabled else 'disabled'}")
        
        self._event_bus.emit(Event(
            type=EventType.SETTINGS_CHANGED,
            data={"setting": "face_detection_enabled", "value": self._settings.face_detection_enabled},
            source="TrayApplication"
        ))
        
        self._update_icon()
    
    def _toggle_inactivity_detection(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Toggle inactivity detection on/off."""
        self._settings.inactivity_detection_enabled = not self._settings.inactivity_detection_enabled
        self._settings.save()
        
        logger.info(f"Inactivity detection {'enabled' if self._settings.inactivity_detection_enabled else 'disabled'}")
        
        self._event_bus.emit(Event(
            type=EventType.SETTINGS_CHANGED,
            data={"setting": "inactivity_detection_enabled", "value": self._settings.inactivity_detection_enabled},
            source="TrayApplication"
        ))
        
        self._update_icon()
    
    def _lock_now(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Manually lock the screen."""
        logger.info("Manual lock requested")
        self._event_bus.emit(Event(
            type=EventType.LOCK_REQUESTED,
            data={"reason": "manual"},
            source="TrayApplication"
        ))
    
    def _quit(self, icon: pystray.Icon, item: MenuItem) -> None:
        """Quit the application."""
        logger.info("Quit requested from tray")
        if self._icon is not None:
            self._icon.stop()
        if self._on_quit:
            self._on_quit()
    
    def _update_icon(self) -> None:
        """Update the icon based on current state."""
        if self._icon is None:
            return
        
        if not self._settings.face_detection_enabled and not self._settings.inactivity_detection_enabled:
            self._icon.icon = create_disabled_icon()
            self._status_text = "Disabled"
        else:
            self._icon.icon = self._load_icon()
            self._status_text = "Active"
        
        # Force menu update
        self._icon.update_menu()
    
    def _on_lock_warning(self, event: Event) -> None:
        """Handle lock warning event."""
        if self._icon and self._settings.show_notifications:
            seconds = event.data.get("seconds_remaining", 5)
            message = event.data.get("message", "Dikkat!")
            
            self._icon.notify(
                title=f"⚠️ {message}",
                message=f"Ekran {int(seconds)} saniye içinde kilitlenecek!"
            )
    
    def _on_lock_executed(self, event: Event) -> None:
        """Handle lock executed event."""
        self._status_text = "Active"
        self._update_icon()
    
    def _on_detector_error(self, event: Event) -> None:
        """Handle detector error event."""
        if self._icon:
            error = event.data.get("error", "Unknown error")
            self._icon.notify(
                title="ScreenGuard Error",
                message=f"Hata: {error}"
            )
    
    def _on_unknown_face(self, event: Event) -> None:
        """Handle unknown face detected event."""
        if self._icon and self._settings.show_notifications:
            message = event.data.get("message", "Bilinmeyen yüz algılandı!")
            self._icon.notify(
                title="⚠️ ScreenGuard Uyarı",
                message=message
            )
    
    def run(self) -> None:
        """Run the tray application (blocking)."""
        logger.info("Starting tray application")
        
        self._icon = pystray.Icon(
            name="ScreenGuard",
            icon=self._load_icon(),
            title="ScreenGuard",
            menu=self._create_menu()
        )
        
        self._icon.run()
    
    def stop(self) -> None:
        """Stop the tray application."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
