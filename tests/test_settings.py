"""Tests for Settings class."""

import json
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from screenguard.core.settings import Settings


class TestSettings:
    """Test cases for Settings dataclass."""
    
    def test_default_values(self):
        """Test that default values are set correctly."""
        settings = Settings()
        
        assert settings.face_detection_enabled is True
        assert settings.inactivity_detection_enabled is True
        assert settings.face_absence_timeout_seconds == 10
        assert settings.inactivity_timeout_seconds == 60
        assert settings.check_interval_ms == 500
        assert settings.camera_index == 0
        assert settings.show_notifications is True
        assert settings.notification_seconds_before == 5
    
    def test_save_and_load(self):
        """Test saving and loading settings from file."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            
            # Create settings with custom values
            settings = Settings(
                face_detection_enabled=False,
                inactivity_timeout_seconds=120,
                _config_file=config_file
            )
            settings.save()
            
            # Verify file was created
            assert config_file.exists()
            
            # Load settings from file
            loaded = Settings.load(config_file)
            
            assert loaded.face_detection_enabled is False
            assert loaded.inactivity_timeout_seconds == 120
    
    def test_update_method(self):
        """Test updating settings via update method."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            settings = Settings(_config_file=config_file)
            
            settings.update(
                face_absence_timeout_seconds=30,
                show_notifications=False
            )
            
            assert settings.face_absence_timeout_seconds == 30
            assert settings.show_notifications is False
            
            # Verify saved to file
            with open(config_file) as f:
                data = json.load(f)
            
            assert data["face_absence_timeout_seconds"] == 30
            assert data["show_notifications"] is False
    
    def test_load_nonexistent_file(self):
        """Test loading from nonexistent file returns defaults."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "nonexistent.json"
            
            settings = Settings.load(config_file)
            
            # Should have default values
            assert settings.face_detection_enabled is True
            assert settings.inactivity_timeout_seconds == 60
    
    def test_load_corrupted_file(self):
        """Test loading from corrupted file returns defaults."""
        with TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            
            # Write invalid JSON
            with open(config_file, "w") as f:
                f.write("not valid json {{{")
            
            settings = Settings.load(config_file)
            
            # Should have default values
            assert settings.face_detection_enabled is True
