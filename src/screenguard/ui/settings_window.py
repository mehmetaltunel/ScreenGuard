"""
Beautiful OpenCV-based setup and settings interface.

Modern, dark-themed UI with smooth graphics.
"""

from __future__ import annotations

import logging
import cv2
import numpy as np
import sys
import time
from typing import Optional, TYPE_CHECKING

from screenguard.core.settings import Settings

if TYPE_CHECKING:
    from screenguard.detectors.face_recognizer import FaceRecognizer

logger = logging.getLogger(__name__)


# Color palette (BGR format)
COLORS = {
    "bg_dark": (30, 30, 35),
    "bg_card": (45, 45, 50),
    "accent_green": (113, 204, 46),    # #2ecc71
    "accent_blue": (219, 152, 52),      # #3498db
    "accent_orange": (39, 127, 230),    # #e67f27
    "accent_red": (85, 85, 231),        # #e75555
    "text_white": (255, 255, 255),
    "text_gray": (180, 180, 180),
    "text_dark": (120, 120, 120),
}


def draw_rounded_rect(img, pt1, pt2, color, radius=15, thickness=-1):
    """Draw a rounded rectangle."""
    x1, y1 = pt1
    x2, y2 = pt2
    
    # Draw the main rectangle parts
    cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, thickness)
    cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, thickness)
    
    # Draw corner circles
    cv2.circle(img, (x1 + radius, y1 + radius), radius, color, thickness)
    cv2.circle(img, (x2 - radius, y1 + radius), radius, color, thickness)
    cv2.circle(img, (x1 + radius, y2 - radius), radius, color, thickness)
    cv2.circle(img, (x2 - radius, y2 - radius), radius, color, thickness)


def create_gradient_bg(height, width):
    """Create a gradient background."""
    bg = np.zeros((height, width, 3), dtype=np.uint8)
    
    for y in range(height):
        ratio = y / height
        color = (
            int(25 + ratio * 15),
            int(25 + ratio * 15),
            int(30 + ratio * 10)
        )
        bg[y, :] = color
    
    return bg


def draw_button(img, text, x, y, w, h, color, selected=False):
    """Draw a stylish button."""
    if selected:
        # Glow effect
        cv2.rectangle(img, (x-2, y-2), (x+w+2, y+h+2), color, 2)
    
    draw_rounded_rect(img, (x, y), (x+w, y+h), color if selected else COLORS["bg_card"], radius=8)
    
    # Text
    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    text_x = x + (w - text_size[0]) // 2
    text_y = y + (h + text_size[1]) // 2
    cv2.putText(img, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                COLORS["text_white"] if selected else COLORS["text_gray"], 2)


def run_face_registration(
    settings: Settings,
    face_recognizer: "FaceRecognizer",
    name: Optional[str] = None
) -> bool:
    """Run beautiful face registration interface."""
    logger.info("Starting face registration...")
    
    # Open camera
    if sys.platform == "darwin":
        cap = cv2.VideoCapture(settings.camera_index, cv2.CAP_AVFOUNDATION)
    else:
        cap = cv2.VideoCapture(settings.camera_index)
    
    if not cap.isOpened():
        logger.error("Failed to open camera")
        return False
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # Warm up
    for _ in range(5):
        cap.read()
        time.sleep(0.05)
    
    frame_to_save = None
    input_name = name or ""
    typing_mode = name is None
    blink_counter = 0
    
    try:
        import face_recognition
        
        while True:
            ret, camera_frame = cap.read()
            if not ret:
                break
            
            blink_counter = (blink_counter + 1) % 30
            
            # Create beautiful display
            display = create_gradient_bg(540, 720)
            
            # Header
            cv2.putText(display, "SCREENGUARD", (250, 45), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLORS["accent_green"], 2)
            cv2.putText(display, "Yuz Tanima Kaydi", (270, 75), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["text_gray"], 1)
            
            # Camera frame (with border)
            camera_resized = cv2.resize(camera_frame, (400, 300))
            
            # Detect face
            rgb_frame = cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB)
            small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
            face_locations = face_recognition.face_locations(small_frame)
            
            # Draw face rectangle on camera
            for (top, right, bottom, left) in face_locations:
                # Scale to resized frame
                scale_x = 400 / 640
                scale_y = 300 / 480
                cv2.rectangle(camera_resized, 
                             (int(left * 4 * scale_x), int(top * 4 * scale_y)),
                             (int(right * 4 * scale_x), int(bottom * 4 * scale_y)),
                             COLORS["accent_green"], 3)
            
            # Camera border
            cam_x, cam_y = 160, 95
            cv2.rectangle(display, (cam_x-3, cam_y-3), (cam_x+403, cam_y+303), 
                         COLORS["accent_blue"] if len(face_locations) > 0 else COLORS["bg_card"], 3)
            display[cam_y:cam_y+300, cam_x:cam_x+400] = camera_resized
            
            # Status
            if len(face_locations) > 0:
                cv2.putText(display, "Yuz Algilandi!", (290, 420), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS["accent_green"], 2)
            else:
                cv2.putText(display, "Yuz Aranıyor...", (290, 420), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS["accent_orange"], 2)
            
            # Name input area
            draw_rounded_rect(display, (160, 440), (560, 480), COLORS["bg_card"], radius=10)
            
            if typing_mode:
                cursor = "_" if blink_counter < 15 else " "
                cv2.putText(display, f"Isim: {input_name}{cursor}", (180, 468), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS["text_white"], 2)
            else:
                cv2.putText(display, f"Merhaba, {input_name}!", (180, 468), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS["accent_green"], 2)
            
            # Instructions
            if typing_mode:
                cv2.putText(display, "Isminizi yazin, ENTER ile onaylayin", (200, 510), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_dark"], 1)
            else:
                cv2.putText(display, "SPACE: Kaydet  |  R: Ismi Degistir  |  ESC: Iptal", (150, 510), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_gray"], 1)
            
            cv2.imshow("ScreenGuard", display)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == 27:  # ESC
                break
            elif typing_mode:
                if key == 13 and input_name.strip():  # ENTER
                    typing_mode = False
                elif key == 8:  # BACKSPACE
                    input_name = input_name[:-1]
                elif 32 <= key < 127:
                    input_name += chr(key)
            else:
                if key == ord('r') or key == ord('R'):
                    typing_mode = True
                elif key == 32 and len(face_locations) > 0:  # SPACE
                    frame_to_save = camera_frame.copy()
                    break
    
    except ImportError:
        cap.release()
        cv2.destroyAllWindows()
        return False
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    if frame_to_save is not None and input_name.strip():
        return face_recognizer.register_face(input_name.strip(), frame_to_save)
    
    return False


def run_first_time_setup(
    settings: Settings,
    face_recognizer: "FaceRecognizer"
) -> bool:
    """Run beautiful first-time setup wizard."""
    logger.info("Running first-time setup...")
    
    # Create welcome screen (no camera needed initially)
    selected = 0  # 0 = register face, 1 = skip
    
    while True:
        display = create_gradient_bg(500, 700)
        
        # Logo/Title
        cv2.putText(display, "SCREENGUARD", (200, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.8, COLORS["accent_green"], 3)
        
        # Subtitle with icon
        cv2.putText(display, "Otomatik Ekran Kilitleme", (220, 140), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS["text_gray"], 2)
        
        # Description card
        draw_rounded_rect(display, (80, 170), (620, 290), COLORS["bg_card"], radius=15)
        
        cv2.putText(display, "Hosgeldiniz!", (290, 210), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS["text_white"], 2)
        
        cv2.putText(display, "Bu uygulama bilgisayar basindan kalktiginizda", (120, 245), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_gray"], 1)
        cv2.putText(display, "ekraninizi otomatik olarak kilitler.", (155, 270), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_gray"], 1)
        
        # Options
        cv2.putText(display, "Nasil kullanmak istersiniz?", (220, 330), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS["text_white"], 2)
        
        # Option 1: Face Recognition
        opt1_color = COLORS["accent_green"] if selected == 0 else COLORS["bg_card"]
        draw_rounded_rect(display, (100, 355), (350, 420), opt1_color, radius=10)
        cv2.putText(display, "Yuz Tanima + Hareketsizlik", (110, 380), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_white"], 2)
        cv2.putText(display, "(Kamera kullanir)", (155, 405), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLORS["text_gray"], 1)
        
        # Option 2: Inactivity Only
        opt2_color = COLORS["accent_blue"] if selected == 1 else COLORS["bg_card"]
        draw_rounded_rect(display, (370, 355), (600, 420), opt2_color, radius=10)
        cv2.putText(display, "Sadece Hareketsizlik", (395, 380), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_white"], 2)
        cv2.putText(display, "(Kamera kullanmaz)", (410, 405), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLORS["text_gray"], 1)
        
        # Instructions
        cv2.putText(display, "Sol/Sag Ok: Sec  |  ENTER: Onayla  |  ESC: Cik", (160, 470), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_dark"], 1)
        
        cv2.imshow("ScreenGuard", display)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == 27:  # ESC
            cv2.destroyAllWindows()
            return False
        elif key == 81 or key == 2:  # LEFT
            selected = 0
        elif key == 83 or key == 3:  # RIGHT
            selected = 1
        elif key == 13:  # ENTER
            cv2.destroyAllWindows()
            
            if selected == 0:
                # Face recognition mode
                success = run_face_registration(settings, face_recognizer)
                if success:
                    settings.face_detection_enabled = True
                    settings.first_run_completed = True
                    settings.save()
                    return True
                # If failed, continue showing setup
            else:
                # Inactivity only mode
                settings.face_detection_enabled = False
                settings.inactivity_detection_enabled = True
                settings.first_run_completed = True
                settings.save()
                return True
    
    return False


def show_settings_window(
    settings: Settings,
    face_recognizer: Optional["FaceRecognizer"] = None
) -> None:
    """Show beautiful settings menu."""
    if face_recognizer is None:
        return
    
    logger.info("Opening settings...")
    
    from screenguard import __version__, __author__
    
    selected = 0
    
    while True:
        display = create_gradient_bg(620, 650)
        
        # Header
        cv2.putText(display, "AYARLAR", (250, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLORS["accent_green"], 2)
        
        # Registered faces info
        names = face_recognizer.registered_names
        if names:
            cv2.putText(display, f"Kayitli: {', '.join(names)}", (30, 85), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["accent_green"], 1)
        else:
            cv2.putText(display, "Kayitli yuz yok", (30, 85), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["accent_orange"], 1)
        
        # Menu items
        menu_items = [
            ("Yuz Kaydet", "register", COLORS["accent_blue"]),
            ("Yuz Sil", "delete_face", COLORS["accent_red"]),
            (f"Yuz Tanima: {'ACIK' if settings.face_detection_enabled else 'KAPALI'}", 
             "toggle_face", COLORS["accent_green"] if settings.face_detection_enabled else COLORS["accent_red"]),
            (f"Hareketsizlik: {'ACIK' if settings.inactivity_detection_enabled else 'KAPALI'}", 
             "toggle_inactivity", COLORS["accent_green"] if settings.inactivity_detection_enabled else COLORS["accent_red"]),
            (f"Yuz Timeout: {settings.face_absence_timeout_seconds}s", "face_timeout", COLORS["text_gray"]),
            (f"Hareketsizlik Suresi: {settings.inactivity_timeout_seconds}s", "inactivity_timeout", COLORS["text_gray"]),
            ("Kapat", "close", COLORS["accent_orange"]),
        ]
        
        # Version info at bottom
        cv2.putText(display, f"ScreenGuard v{__version__} | {__author__}", (180, 590), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.45, COLORS["text_dark"], 1)
        cv2.putText(display, "Otomatik Ekran Kilitleme - Yuz Tanima | Hareketsizlik | Bildirimler", (70, 610), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLORS["text_dark"], 1)
        
        y = 110
        for i, (text, action, color) in enumerate(menu_items):
            is_selected = i == selected
            
            # Background
            bg_color = color if is_selected else COLORS["bg_card"]
            draw_rounded_rect(display, (50, y), (600, y+50), bg_color, radius=10)
            
            # Arrow indicator
            if is_selected:
                cv2.putText(display, ">", (70, y+35), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLORS["text_white"], 2)
            
            # Text
            text_color = COLORS["text_white"] if is_selected else COLORS["text_gray"]
            cv2.putText(display, text, (100, y+35), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)
            
            y += 55
        
        # Instructions
        cv2.putText(display, "Yukari/Asagi: Sec  |  ENTER: Uygula  |  ESC: Kapat", (120, 540), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_dark"], 1)
        
        cv2.imshow("ScreenGuard Ayarlar", display)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == 27:  # ESC
            break
        elif key == 82 or key == 0:  # UP
            selected = (selected - 1) % len(menu_items)
        elif key == 84 or key == 1:  # DOWN
            selected = (selected + 1) % len(menu_items)
        elif key == 13:  # ENTER
            action = menu_items[selected][1]
            
            if action == "close":
                break
            elif action == "register":
                cv2.destroyAllWindows()
                run_face_registration(settings, face_recognizer)
            elif action == "delete_face":
                # Show delete face submenu
                names = face_recognizer.registered_names
                if names:
                    delete_selected = 0
                    while True:
                        del_display = create_gradient_bg(400, 500)
                        cv2.putText(del_display, "YUZ SIL", (180, 50), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 1, COLORS["accent_red"], 2)
                        
                        y = 100
                        for i, name in enumerate(names):
                            is_sel = i == delete_selected
                            bg = COLORS["accent_red"] if is_sel else COLORS["bg_card"]
                            draw_rounded_rect(del_display, (50, y), (450, y+45), bg, radius=8)
                            cv2.putText(del_display, f"{'> ' if is_sel else '  '}{name}", (70, y+32), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS["text_white"], 2)
                            y += 55
                        
                        cv2.putText(del_display, "ENTER: Sil  |  ESC: Geri", (130, 370), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text_dark"], 1)
                        
                        cv2.imshow("ScreenGuard - Yuz Sil", del_display)
                        
                        del_key = cv2.waitKey(1) & 0xFF
                        if del_key == 27:
                            cv2.destroyWindow("ScreenGuard - Yuz Sil")
                            break
                        elif del_key == 82 or del_key == 0:
                            delete_selected = (delete_selected - 1) % len(names)
                        elif del_key == 84 or del_key == 1:
                            delete_selected = (delete_selected + 1) % len(names)
                        elif del_key == 13:
                            face_recognizer.remove_face(names[delete_selected])
                            cv2.destroyWindow("ScreenGuard - Yuz Sil")
                            break
            elif action == "toggle_face":
                settings.face_detection_enabled = not settings.face_detection_enabled
                settings.save()
            elif action == "toggle_inactivity":
                settings.inactivity_detection_enabled = not settings.inactivity_detection_enabled
                settings.save()
            elif action == "face_timeout":
                values = [5, 10, 15, 30, 60]
                idx = values.index(settings.face_absence_timeout_seconds) if settings.face_absence_timeout_seconds in values else 0
                settings.face_absence_timeout_seconds = values[(idx + 1) % len(values)]
                settings.save()
            elif action == "inactivity_timeout":
                values = [30, 60, 120, 180, 300]
                idx = values.index(settings.inactivity_timeout_seconds) if settings.inactivity_timeout_seconds in values else 0
                settings.inactivity_timeout_seconds = values[(idx + 1) % len(values)]
                settings.save()
    
    cv2.destroyAllWindows()

