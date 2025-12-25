# ScreenGuard 🛡️

Cross-platform automatic screen lock application with face detection and inactivity monitoring.

> Bilgisayar başından kalkınca otomatik ekran kilitleme - artık çikolata ısmarlamak yok! 🍫

## Features

- 👁️ **Face Detection** - Webcam ile yüz algılama, yüz görünmezse ekranı kilitle
- ⌨️ **Inactivity Monitor** - Mouse/klavye hareketi olmazsa belirli süre sonra kilitle
- 🖥️ **Cross-Platform** - macOS ve Windows desteği
- 🔧 **System Tray** - Arka planda çalışır, tray'den kontrol edilir
- ⚙️ **Configurable** - Timeout süreleri ve özellikler ayarlanabilir

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/screenguard.git
cd screenguard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .
```

## Usage

```bash
# Run the application
screenguard

# Or run directly
python -m screenguard
```

## Configuration

Settings are stored in `~/.screenguard/config.json`:

```json
{
    "face_detection_enabled": true,
    "inactivity_detection_enabled": true,
    "face_absence_timeout_seconds": 10,
    "inactivity_timeout_seconds": 60,
    "check_interval_ms": 500
}
```

## Project Structure

```
screenguard/
├── src/
│   └── screenguard/
│       ├── core/           # Core abstractions and settings
│       ├── detectors/      # Face detection implementations
│       ├── monitors/       # Activity monitoring
│       ├── platform/       # Platform-specific code (lock screen)
│       └── ui/             # System tray and UI
├── assets/                 # Icons and resources
├── tests/                  # Unit tests
└── pyproject.toml          # Project configuration
```

## Requirements

- Python 3.9+
- Webcam (for face detection)
- macOS 10.14+ or Windows 10+

## License

MIT License
