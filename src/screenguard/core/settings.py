"""
Application settings management.

Handles loading, saving, and accessing configuration values.
Settings are persisted to ~/.screenguard/config.json
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    config_dir = Path.home() / ".screenguard"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.json"


@dataclass
class Settings:
    """
    Application settings with sensible defaults.
    
    Attributes:
        face_detection_enabled: Enable face detection based locking
        inactivity_detection_enabled: Enable inactivity based locking
        face_absence_timeout_seconds: Seconds to wait after face disappears before locking
        inactivity_timeout_seconds: Seconds of inactivity before locking
        check_interval_ms: Milliseconds between face detection checks
        camera_index: Camera device index to use
        show_notifications: Show notifications before locking
        notification_seconds_before: Seconds before lock to show notification
    """
    
    face_detection_enabled: bool = True
    inactivity_detection_enabled: bool = True
    face_absence_timeout_seconds: int = 10
    inactivity_timeout_seconds: int = 60
    check_interval_ms: int = 500
    camera_index: int = 0
    show_notifications: bool = True
    notification_seconds_before: int = 5
    
    # Internal state (not persisted)
    _config_file: Optional[Path] = field(default=None, repr=False, compare=False)
    
    def __post_init__(self) -> None:
        """Initialize config file path."""
        if self._config_file is None:
            self._config_file = get_config_file()
    
    @classmethod
    def load(cls, config_file: Optional[Path] = None) -> Settings:
        """
        Load settings from config file.
        
        Args:
            config_file: Optional path to config file. Uses default if not specified.
            
        Returns:
            Settings instance with loaded or default values.
        """
        config_path = config_file or get_config_file()
        
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Filter out internal fields
                valid_fields = {
                    k: v for k, v in data.items() 
                    if not k.startswith("_")
                }
                
                logger.info(f"Loaded settings from {config_path}")
                return cls(**valid_fields, _config_file=config_path)
                
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to load settings: {e}. Using defaults.")
                return cls(_config_file=config_path)
        
        logger.info("No config file found. Using default settings.")
        return cls(_config_file=config_path)
    
    def save(self) -> None:
        """Save current settings to config file."""
        if self._config_file is None:
            self._config_file = get_config_file()
        
        # Convert to dict, excluding internal fields
        data = {
            k: v for k, v in asdict(self).items() 
            if not k.startswith("_")
        }
        
        try:
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            
            logger.info(f"Saved settings to {self._config_file}")
            
        except IOError as e:
            logger.error(f"Failed to save settings: {e}")
    
    def update(self, **kwargs) -> None:
        """
        Update settings with new values and save.
        
        Args:
            **kwargs: Setting names and values to update.
        """
        for key, value in kwargs.items():
            if hasattr(self, key) and not key.startswith("_"):
                setattr(self, key, value)
            else:
                logger.warning(f"Unknown setting: {key}")
        
        self.save()
