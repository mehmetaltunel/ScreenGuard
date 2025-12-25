"""
Platform-specific screen locking implementations.

Provides a unified interface for locking the screen on different operating systems.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class ScreenLocker(ABC):
    """
    Abstract base class for platform-specific screen lockers.
    
    Each platform (Windows, macOS, Linux) has its own implementation.
    """
    
    @abstractmethod
    def lock(self) -> bool:
        """
        Lock the screen.
        
        Returns:
            True if lock was successful, False otherwise
        """
        pass
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Get the name of the platform."""
        pass


class WindowsScreenLocker(ScreenLocker):
    """Screen locker for Windows using Win32 API."""
    
    @property
    def platform_name(self) -> str:
        return "Windows"
    
    def lock(self) -> bool:
        """Lock the Windows workstation."""
        try:
            import ctypes
            
            result = ctypes.windll.user32.LockWorkStation()
            if result:
                logger.info("Windows screen locked successfully")
                return True
            else:
                logger.error("LockWorkStation returned False")
                return False
                
        except Exception as e:
            logger.error(f"Failed to lock Windows screen: {e}")
            return False


class MacOSScreenLocker(ScreenLocker):
    """Screen locker for macOS using multiple methods."""
    
    @property
    def platform_name(self) -> str:
        return "macOS"
    
    def lock(self) -> bool:
        """Lock the macOS screen using multiple fallback methods."""
        
        # Method 1: Use osascript to activate screen saver (most reliable)
        if self._lock_via_osascript():
            return True
        
        # Method 2: Use pmset to sleep display
        if self._lock_via_pmset():
            return True
        
        # Method 3: Use loginwindow via osascript
        if self._lock_via_loginwindow():
            return True
        
        logger.error("All macOS lock methods failed")
        return False
    
    def _lock_via_osascript(self) -> bool:
        """Lock screen using osascript and System Events."""
        try:
            # This triggers the lock screen via System Events
            script = '''
            tell application "System Events"
                keystroke "q" using {control down, command down}
            end tell
            '''
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info("macOS screen locked successfully via osascript (Cmd+Ctrl+Q)")
                return True
            
            logger.debug(f"osascript keystroke failed: {result.stderr.decode()}")
            
        except Exception as e:
            logger.debug(f"osascript method failed: {e}")
        
        return False
    
    def _lock_via_pmset(self) -> bool:
        """Lock screen by putting display to sleep."""
        try:
            result = subprocess.run(
                ["pmset", "displaysleepnow"],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info("macOS screen locked successfully via pmset")
                return True
            
            logger.debug(f"pmset failed: {result.stderr.decode()}")
            
        except Exception as e:
            logger.debug(f"pmset method failed: {e}")
        
        return False
    
    def _lock_via_loginwindow(self) -> bool:
        """Lock screen using loginwindow."""
        try:
            # Alternative: use /System/Library/CoreServices/ScreenSaverEngine.app
            result = subprocess.run(
                ["open", "-a", "ScreenSaverEngine"],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                logger.info("macOS screen locked successfully via ScreenSaverEngine")
                return True
            
            logger.debug(f"ScreenSaverEngine failed: {result.stderr.decode()}")
            
        except Exception as e:
            logger.debug(f"loginwindow method failed: {e}")
        
        return False


class LinuxScreenLocker(ScreenLocker):
    """Screen locker for Linux using various desktop environments."""
    
    # Commands to try in order
    LOCK_COMMANDS = [
        # GNOME
        ["gnome-screensaver-command", "-l"],
        # KDE
        ["qdbus", "org.freedesktop.ScreenSaver", "/ScreenSaver", "Lock"],
        # Cinnamon
        ["cinnamon-screensaver-command", "-l"],
        # MATE
        ["mate-screensaver-command", "-l"],
        # XFCE
        ["xflock4"],
        # Generic X11
        ["xdg-screensaver", "lock"],
        # loginctl (systemd)
        ["loginctl", "lock-session"],
    ]
    
    @property
    def platform_name(self) -> str:
        return "Linux"
    
    def lock(self) -> bool:
        """Lock the Linux screen."""
        for cmd in self.LOCK_COMMANDS:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    logger.info(f"Linux screen locked successfully via {cmd[0]}")
                    return True
                    
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                continue
            except Exception as e:
                logger.debug(f"Lock command {cmd[0]} failed: {e}")
                continue
        
        logger.error("No working screen lock command found for Linux")
        return False


def get_screen_locker() -> ScreenLocker:
    """
    Get the appropriate screen locker for the current platform.
    
    Returns:
        ScreenLocker instance for the current OS
        
    Raises:
        NotImplementedError: If the platform is not supported
    """
    platform = sys.platform
    
    if platform == "win32":
        return WindowsScreenLocker()
    elif platform == "darwin":
        return MacOSScreenLocker()
    elif platform.startswith("linux"):
        return LinuxScreenLocker()
    else:
        raise NotImplementedError(f"Platform '{platform}' is not supported")
