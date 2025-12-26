"""
On-screen warning overlay for lock countdown.

Shows a visible countdown warning before screen locks.
"""

from __future__ import annotations

import logging
import threading
import time
import cv2
import numpy as np
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class WarningOverlay:
    """
    Shows an on-screen warning overlay with countdown.
    """
    
    # Singleton
    _instance: Optional["WarningOverlay"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._showing = False
        self._thread: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._initialized = True
    
    def show_countdown(
        self, 
        seconds: float, 
        reason: str = "Yüz tanınmadı",
        on_complete: Optional[Callable[[], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None
    ) -> None:
        """
        Show countdown warning overlay.
        
        Args:
            seconds: Seconds to count down
            reason: Reason for the warning (shown on screen)
            on_complete: Callback when countdown completes
            on_cancel: Callback when countdown is cancelled
        """
        if self._showing:
            return
        
        self._cancel_event.clear()
        self._thread = threading.Thread(
            target=self._show_overlay,
            args=(seconds, reason, on_complete, on_cancel),
            daemon=True
        )
        self._thread.start()
    
    def cancel(self) -> None:
        """Cancel the current countdown."""
        self._cancel_event.set()
    
    def _show_overlay(
        self,
        seconds: float,
        reason: str,
        on_complete: Optional[Callable[[], None]],
        on_cancel: Optional[Callable[[], None]]
    ) -> None:
        """Show the overlay in a separate thread."""
        self._showing = True
        start_time = time.time()
        
        # Colors
        BG_COLOR = (20, 20, 25)
        RED = (60, 60, 220)
        ORANGE = (40, 140, 230)
        WHITE = (255, 255, 255)
        GRAY = (150, 150, 150)
        
        window_name = "ScreenGuard Uyari"
        
        try:
            while not self._cancel_event.is_set():
                elapsed = time.time() - start_time
                remaining = max(0, seconds - elapsed)
                
                if remaining <= 0:
                    break
                
                # Create warning display
                display = np.zeros((300, 500, 3), dtype=np.uint8)
                display[:] = BG_COLOR
                
                # Warning icon (triangle)
                pts = np.array([[250, 40], [200, 120], [300, 120]], np.int32)
                cv2.fillPoly(display, [pts], ORANGE)
                cv2.putText(display, "!", (240, 105), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, WHITE, 3)
                
                # Reason text
                cv2.putText(display, reason, (130, 160), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, WHITE, 2)
                
                # Countdown
                countdown_text = f"{int(remaining)}"
                text_size = cv2.getTextSize(countdown_text, cv2.FONT_HERSHEY_SIMPLEX, 3, 4)[0]
                text_x = (500 - text_size[0]) // 2
                
                # Color based on remaining time
                color = RED if remaining < 3 else ORANGE
                cv2.putText(display, countdown_text, (text_x, 230), 
                           cv2.FONT_HERSHEY_SIMPLEX, 3, color, 4)
                
                # Message
                cv2.putText(display, "saniye icinde ekran kilitlenecek!", (85, 275), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, GRAY, 1)
                
                cv2.imshow(window_name, display)
                
                key = cv2.waitKeyEx(100)
                if key == 27:  # ESC to cancel (debug)
                    self._cancel_event.set()
                    break
            
            cv2.destroyWindow(window_name)
            
            if self._cancel_event.is_set():
                logger.info("Warning overlay cancelled")
                if on_cancel:
                    on_cancel()
            else:
                logger.info("Warning countdown completed")
                if on_complete:
                    on_complete()
                    
        except Exception as e:
            logger.error(f"Error showing warning overlay: {e}")
        finally:
            self._showing = False
            try:
                cv2.destroyWindow(window_name)
            except:
                pass


def show_warning(seconds: float, reason: str = "Yüz tanınmadı") -> WarningOverlay:
    """
    Show warning countdown overlay.
    
    Args:
        seconds: Countdown duration
        reason: Reason message
        
    Returns:
        WarningOverlay instance (can call .cancel() to stop)
    """
    overlay = WarningOverlay()
    overlay.show_countdown(seconds, reason)
    return overlay


def cancel_warning() -> None:
    """Cancel any active warning overlay."""
    overlay = WarningOverlay()
    overlay.cancel()
