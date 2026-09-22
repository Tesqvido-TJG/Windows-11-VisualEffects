import sys
import ctypes
import ctypes.wintypes
import threading
import queue
import random
import json
import math
from pathlib import Path

import pygame
from pynput import keyboard

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QRectF,
    QPoint,
    pyqtSignal,
)

from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QPainterPath,
    QIcon,
    QPixmap,
    QCursor,
)

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QSystemTrayIcon,
    QMenu,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QCheckBox,
    QSpacerItem,
    QSizePolicy,
    QColorDialog,
    QComboBox,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QScrollArea,
    QGridLayout,
)


# ============================================================
# APPLICATION
# ============================================================

APP_NAME = "Keyboard Effects"
APP_VERSION = "2.0.0"


# ============================================================
# RESOURCE PATH
# ============================================================

def resource_path(relative_path):
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).resolve().parent

    return base_path / relative_path


# ============================================================
# FILES
# ============================================================

ICON_PATH = resource_path("icon.ico")

SOUNDS_PATH = resource_path("sounds")

NORMAL_SOUND = SOUNDS_PATH / "general-sound.mp3"
ENTER_SOUND = SOUNDS_PATH / "space-enter.mp3"
SPACE_SOUND = SOUNDS_PATH / "space-enter.mp3"

SETTINGS_PATH = resource_path("settings.json")


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_SETTINGS = {

    "keyboard_sounds": True,

    # --------------------------------------------------------
    # Typing
    # --------------------------------------------------------

    "typing": {
        "enabled": True,
        "color": "#FFAADD",
        "font": "Segoe UI",
        "size": 14,
        "lifetime": 45,
        "velocity": 1.5,
        "bold": True,
    },

    # --------------------------------------------------------
    # Mouse trail
    # --------------------------------------------------------

    "mouse_trail": {
        "enabled": True,
        "color": "#FF78D2",
        "particle": "Circle",
        "size": 2.5,
        "lifetime": 18,
        "amount": 80,
        "velocity": 1.2,
    },

    # --------------------------------------------------------
    # Cursor glow
    # --------------------------------------------------------

    "cursor_glow": {
        "enabled": True,
        "color": "#FF78D2",
        "radius": 35,
        "opacity": 40,
    },

    # --------------------------------------------------------
    # Rain
    # --------------------------------------------------------

    "rain": {
        "enabled": True,
        "color": "#66AAFF",
        "amount": 120,
        "speed_min": 7,
        "speed_max": 15,
        "length_min": 10,
        "length_max": 20,
        "width": 1.2,
        "opacity": 255,
    },

    # --------------------------------------------------------
    # Window glow
    # --------------------------------------------------------

    "window_glow": {
        "enabled": False,
        "color": "#FF78D2",
        "radius": 12,
        "opacity": 30,
        "width": 1.5,
        "corner_radius": 10,
    },
}


# ============================================================
# SETTINGS
# ============================================================

def deep_copy_settings():
    return json.loads(
        json.dumps(DEFAULT_SETTINGS)
    )


settings = deep_copy_settings()


def load_settings():

    global settings

    try:

        if not SETTINGS_PATH.exists():
            save_settings()
            return

        with open(
            SETTINGS_PATH,
            "r",
            encoding="utf-8"
        ) as file:

            loaded = json.load(file)

        # Merge with defaults so new settings
        # are automatically added after updates.

        defaults = deep_copy_settings()

        def merge(default, custom):

            if isinstance(default, dict) and isinstance(custom, dict):

                result = {}

                for key in default:

                    if key in custom:

                        result[key] = merge(
                            default[key],
                            custom[key]
                        )

                    else:

                        result[key] = default[key]

                for key in custom:

                    if key not in result:

                        result[key] = custom[key]

                return result

            return custom

        settings = merge(
            defaults,
            loaded
        )

    except Exception:

        settings = deep_copy_settings()


def save_settings():

    try:

        with open(
            SETTINGS_PATH,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                settings,
                file,
                indent=4,
                ensure_ascii=False
            )

    except Exception as error:

        print(
            "Could not save settings:",
            error
        )


load_settings()


# ============================================================
# WINDOWS API
# ============================================================

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

GWL_EXSTYLE = -20

WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

DWMWA_EXTENDED_FRAME_BOUNDS = 9


SHELL_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
    "DV2ControlHost",
}


# ============================================================
# GLOBAL STATE
# ============================================================

running = True

cursor_x = 0
cursor_y = 0

keyboard_queue = queue.Queue()

held_keys = set()

held_keys_lock = threading.Lock()

keyboard_listener = None


# ============================================================
# COLOR HELPERS
# ============================================================

def qcolor(hex_color):

    color = QColor(hex_color)

    if not color.isValid():

        return QColor(
            255,
            255,
            255
        )

    return color


def color_to_hex(color):

    return color.name(
        QColor.NameFormat.HexArgb
    )


# ============================================================
# WINDOWS HELPERS
# ============================================================

def get_window_class(hwnd):

    if not hwnd:
        return ""

    try:

        buffer = ctypes.create_unicode_buffer(
            256
        )

        user32.GetClassNameW(
            hwnd,
            buffer,
            256
        )

        return buffer.value

    except Exception:

        return ""


def is_shell_window(hwnd):

    return (
        get_window_class(hwnd)
        in SHELL_CLASSES
    )


def is_window_minimized(hwnd):

    try:

        return bool(
            user32.IsIconic(hwnd)
        )

    except Exception:

        return False


def is_window_maximized(hwnd):

    try:

        placement = ctypes.wintypes.WINDOWPLACEMENT()

        placement.length = ctypes.sizeof(
            placement
        )

        result = user32.GetWindowPlacement(
            hwnd,
            ctypes.byref(placement)
        )

        if result:

            return placement.showCmd == 3

    except Exception:

        pass

    return False


def get_active_window_rect():

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return None

    if is_shell_window(hwnd):
        return None

    if is_window_minimized(hwnd):
        return None

    rect = ctypes.wintypes.RECT()

    try:

        result = dwmapi.DwmGetWindowAttribute(
            hwnd,
            DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rect),
            ctypes.sizeof(rect)
        )

        if result == 0:

            return (
                rect.left,
                rect.top,
                rect.right,
                rect.bottom
            )

    except Exception:

        pass

    try:

        result = user32.GetWindowRect(
            hwnd,
            ctypes.byref(rect)
        )

        if result:

            return (
                rect.left,
                rect.top,
                rect.right,
                rect.bottom
            )

    except Exception:

        pass

    return None


def desktop_is_visible():

    try:

        hwnd = user32.GetForegroundWindow()

        if not hwnd:
            return True

        if is_window_minimized(hwnd):
            return True

        if is_shell_window(hwnd):
            return True

        return False

    except Exception:

        return False


# ============================================================
# SOUND SYSTEM
# ============================================================

try:

    pygame.mixer.init()

except Exception as error:

    print(
        "Audio initialization failed:",
        error
    )


def play_sound(sound_path):

    if not settings["keyboard_sounds"]:
        return

    try:

        if not sound_path.exists():
            return

        sound = pygame.mixer.Sound(
            str(sound_path)
        )

        sound.play()

    except Exception:

        pass


# ============================================================
# KEYBOARD
# ============================================================

def get_key_name(key):

    try:

        if hasattr(key, "char"):

            if key.char is not None:

                return key.char.upper()

        key_map = {

            keyboard.Key.enter: "ENTER",
            keyboard.Key.space: "SPACE",
            keyboard.Key.backspace: "BACKSPACE",
            keyboard.Key.delete: "DELETE",
            keyboard.Key.tab: "TAB",
            keyboard.Key.esc: "ESC",

            keyboard.Key.shift: "SHIFT",
            keyboard.Key.shift_l: "SHIFT",
            keyboard.Key.shift_r: "SHIFT",

            keyboard.Key.ctrl: "CTRL",
            keyboard.Key.ctrl_l: "CTRL",
            keyboard.Key.ctrl_r: "CTRL",

            keyboard.Key.alt: "ALT",
            keyboard.Key.alt_l: "ALT",
            keyboard.Key.alt_r: "ALT",

            keyboard.Key.cmd: "WIN",
            keyboard.Key.cmd_l: "WIN",
            keyboard.Key.cmd_r: "WIN",

            keyboard.Key.caps_lock: "CAPSLOCK",

            keyboard.Key.up: "UP",
            keyboard.Key.down: "DOWN",
            keyboard.Key.left: "LEFT",
            keyboard.Key.right: "RIGHT",

            keyboard.Key.home: "HOME",
            keyboard.Key.end: "END",

            keyboard.Key.page_up: "PAGEUP",
            keyboard.Key.page_down: "PAGEDOWN",

            keyboard.Key.insert: "INSERT",
        }

        if key in key_map:

            return key_map[key]

        value = str(key)

        if value.startswith("Key."):

            return value[4:].upper()

        return value.upper()

    except Exception:

        return str(key).upper()


def keyboard_on_press(key):

    key_name = get_key_name(key)

    with held_keys_lock:

        if key_name in held_keys:
            return

        held_keys.add(key_name)

    keyboard_queue.put(
        (
            "press",
            key_name
        )
    )

    if not settings["keyboard_sounds"]:
        return

    if key_name == "ENTER":

        play_sound(
            ENTER_SOUND
        )

    elif key_name == "SPACE":

        play_sound(
            SPACE_SOUND
        )

    else:

        play_sound(
            NORMAL_SOUND
        )


def keyboard_on_release(key):

    key_name = get_key_name(key)

    with held_keys_lock:

        held_keys.discard(
            key_name
        )


def keyboard_listener_thread():

    global keyboard_listener

    try:

        keyboard_listener = keyboard.Listener(
            on_press=keyboard_on_press,
            on_release=keyboard_on_release
        )

        keyboard_listener.start()

        keyboard_listener.join()

    except Exception as error:

        print(
            "Keyboard listener error:",
            error
        )


# ============================================================
# RAIN DROP
# ============================================================

class RainDrop:

    def __init__(
        self,
        width,
        height
    ):

        self.reset(
            width,
            height,
            True
        )

    def reset(
        self,
        width,
        height,
        initial=False
    ):

        self.x = random.uniform(
            0,
            max(1, width)
        )

        if initial:

            self.y = random.uniform(
                -height,
                height
            )

        else:

            self.y = random.uniform(
                -50,
                0
            )

        rain = settings["rain"]

        self.length = random.uniform(
            rain["length_min"],
            rain["length_max"]
        )

        self.speed = random.uniform(
            rain["speed_min"],
            rain["speed_max"]
        )

        self.alpha = rain["opacity"]

    def update(
        self,
        width,
        height
    ):

        self.y += self.speed

        if self.y > height:

            self.reset(
                width,
                height
            )


# ============================================================
# CURSOR PARTICLE
# ============================================================

class CursorParticle:

    def __init__(
        self,
        x,
        y
    ):

        config = settings["mouse_trail"]

        self.x = x
        self.y = y

        self.max_life = max(
            1,
            config["lifetime"]
        )

        self.life = self.max_life

        self.size = max(
            0.2,
            random.uniform(
                config["size"] * 0.65,
                config["size"] * 1.35
            )
        )

        speed = config["velocity"]

        angle = random.uniform(
            0,
            math.pi * 2
        )

        self.velocity_x = math.cos(
            angle
        ) * random.uniform(
            0.1,
            speed
        )

        self.velocity_y = math.sin(
            angle
        ) * random.uniform(
            0.1,
            speed
        )

        self.rotation = random.uniform(
            0,
            360
        )

        self.rotation_speed = random.uniform(
            -5,
            5
        )

        self.alive = True

    def update(self):

        self.x += self.velocity_x
        self.y += self.velocity_y

        self.velocity_x *= 0.96
        self.velocity_y *= 0.96

        self.rotation += self.rotation_speed

        self.life -= 1

        if self.life <= 0:

            self.alive = False


# ============================================================
# TYPING PARTICLE
# ============================================================

class TypingParticle:

    def __init__(
        self,
        x,
        y,
        text
    ):

        config = settings["typing"]

        self.x = x
        self.y = y

        self.text = text

        self.max_life = max(
            1,
            config["lifetime"]
        )

        self.life = self.max_life

        velocity = config["velocity"]

        self.velocity_x = random.uniform(
            -velocity * 0.35,
            velocity * 0.35
        )

        self.velocity_y = random.uniform(
            -velocity,
            -velocity * 0.3
        )

        self.alive = True

    def update(self):

        self.x += self.velocity_x
        self.y += self.velocity_y

        self.velocity_y += 0.025

        self.life -= 1

        if self.life <= 0:

            self.alive = False


# ============================================================
# OVERLAY
# ============================================================

class VisualOverlay(QWidget):

    def __init__(self):

        super().__init__()

        self.cursor_particles = []
        self.typing_particles = []
        self.rain_drops = []

        self.virtual_left = 0
        self.virtual_top = 0

        self.screen_width = 0
        self.screen_height = 0

        self.setup_window()
        self.setup_geometry()
        self.setup_rain()

        self.timer = QTimer(self)

        self.timer.timeout.connect(
            self.update_effects
        )

        self.timer.start(16)

    # ========================================================
    # WINDOW
    # ========================================================

    def setup_window(self):

        self.setWindowFlags(

            Qt.WindowType.FramelessWindowHint
            |
            Qt.WindowType.WindowStaysOnTopHint
            |
            Qt.WindowType.Tool
            |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_NoSystemBackground,
            True
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True
        )

    def setup_geometry(self):

        screen = QApplication.primaryScreen()

        if screen is None:
            return

        geometry = screen.virtualGeometry()

        self.virtual_left = geometry.left()
        self.virtual_top = geometry.top()

        self.screen_width = geometry.width()
        self.screen_height = geometry.height()

        self.setGeometry(
            geometry
        )

    def setup_rain(self):

        self.rain_drops.clear()

        amount = settings["rain"]["amount"]

        for _ in range(amount):

            self.rain_drops.append(
                RainDrop(
                    self.screen_width,
                    self.screen_height
                )
            )

    def refresh_rain(self):

        desired = settings["rain"]["amount"]

        while len(self.rain_drops) < desired:

            self.rain_drops.append(
                RainDrop(
                    self.screen_width,
                    self.screen_height
                )
            )

        if len(self.rain_drops) > desired:

            self.rain_drops = self.rain_drops[
                :desired
            ]

    def make_click_through(self):

        try:

            hwnd = int(
                self.winId()
            )

            current_style = user32.GetWindowLongW(
                hwnd,
                GWL_EXSTYLE
            )

            user32.SetWindowLongW(

                hwnd,
                GWL_EXSTYLE,

                current_style
                |
                WS_EX_LAYERED
                |
                WS_EX_TRANSPARENT
                |
                WS_EX_TOOLWINDOW
                |
                WS_EX_NOACTIVATE
            )

        except Exception:

            pass

    # ========================================================
    # UPDATE
    # ========================================================

    def update_effects(self):

        global cursor_x
        global cursor_y

        if not running:
            return

        mouse_pos = QCursor.pos()

        cursor_x = mouse_pos.x()
        cursor_y = mouse_pos.y()

        # ----------------------------------------------------
        # Mouse trail
        # ----------------------------------------------------

        trail = settings["mouse_trail"]

        if trail["enabled"]:

            local_x = (
                cursor_x
                - self.virtual_left
            )

            local_y = (
                cursor_y
                - self.virtual_top
            )

            self.cursor_particles.append(
                CursorParticle(
                    local_x,
                    local_y
                )
            )

            maximum = max(
                1,
                trail["amount"]
            )

            if len(self.cursor_particles) > maximum:

                self.cursor_particles = (
                    self.cursor_particles[-maximum:]
                )

        # ----------------------------------------------------
        # Keyboard
        # ----------------------------------------------------

        while True:

            try:

                event_type, key_name = (
                    keyboard_queue.get_nowait()
                )

            except queue.Empty:

                break

            if event_type != "press":
                continue

            typing = settings["typing"]

            if not typing["enabled"]:
                continue

            x = (
                cursor_x
                - self.virtual_left
            )

            y = (
                cursor_y
                - self.virtual_top
            )

            text = None

            if key_name == "ENTER":

                text = "↵"

            elif key_name == "SPACE":

                text = "•"

            elif key_name == "BACKSPACE":

                text = "⌫"

            elif key_name == "DELETE":

                text = "⌦"

            elif key_name == "TAB":

                text = "⇥"

            elif (
                len(key_name) == 1
                and key_name.isprintable()
            ):

                text = key_name

            if text:

                self.typing_particles.append(
                    TypingParticle(
                        x,
                        y - 25,
                        text
                    )
                )

        # ----------------------------------------------------
        # Update particles
        # ----------------------------------------------------

        for particle in self.cursor_particles:

            particle.update()

        self.cursor_particles = [

            particle

            for particle in self.cursor_particles

            if particle.alive
        ]

        for particle in self.typing_particles:

            particle.update()

        self.typing_particles = [

            particle

            for particle in self.typing_particles

            if particle.alive
        ]

        # ----------------------------------------------------
        # Rain
        # ----------------------------------------------------

        if settings["rain"]["enabled"]:

            self.refresh_rain()

            for drop in self.rain_drops:

                drop.update(
                    self.screen_width,
                    self.screen_height
                )

        self.update()

    # ========================================================
    # DRAW PARTICLE
    # ========================================================

    def draw_particle(
        self,
        painter,
        particle,
        color
    ):

        particle_type = (
            settings["mouse_trail"]["particle"]
        )

        size = particle.size

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.setBrush(
            color
        )

        center = QPointF(
            particle.x,
            particle.y
        )

        if particle_type == "Circle":

            painter.drawEllipse(
                center,
                size,
                size
            )

        elif particle_type == "Square":

            painter.save()

            painter.translate(
                center
            )

            painter.rotate(
                particle.rotation
            )

            painter.drawRect(
                QRectF(
                    -size,
                    -size,
                    size * 2,
                    size * 2
                )
            )

            painter.restore()

        elif particle_type == "Diamond":

            path = QPainterPath()

            path.moveTo(
                particle.x,
                particle.y - size * 1.5
            )

            path.lineTo(
                particle.x + size * 1.5,
                particle.y
            )

            path.lineTo(
                particle.x,
                particle.y + size * 1.5
            )

            path.lineTo(
                particle.x - size * 1.5,
                particle.y
            )

            path.closeSubpath()

            painter.drawPath(path)

        elif particle_type == "Star":

            path = QPainterPath()

            points = 10

            for i in range(points):

                angle = (
                    -math.pi / 2
                    +
                    i * math.pi / 5
                )

                radius = (
                    size * 1.8
                    if i % 2 == 0
                    else size * 0.75
                )

                x = (
                    particle.x
                    +
                    math.cos(angle) * radius
                )

                y = (
                    particle.y
                    +
                    math.sin(angle) * radius
                )

                if i == 0:

                    path.moveTo(
                        x,
                        y
                    )

                else:

                    path.lineTo(
                        x,
                        y
                    )

            path.closeSubpath()

            painter.drawPath(path)

        elif particle_type == "Spark":

            pen = QPen(
                color
            )

            pen.setWidthF(
                max(
                    1,
                    size
                )
            )

            painter.setPen(
                pen
            )

            painter.drawLine(
                QPointF(
                    particle.x - size * 2,
                    particle.y
                ),
                QPointF(
                    particle.x + size * 2,
                    particle.y
                )
            )

            painter.drawLine(
                QPointF(
                    particle.x,
                    particle.y - size * 2
                ),
                QPointF(
                    particle.x,
                    particle.y + size * 2
                )
            )

    # ========================================================
    # PAINT
    # ========================================================

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.setRenderHint(
            QPainter.RenderHint.TextAntialiasing
        )

        # ====================================================
        # RAIN
        # ====================================================

        rain = settings["rain"]

        if (
            rain["enabled"]
            and desktop_is_visible()
        ):

            rain_color = qcolor(
                rain["color"]
            )

            for drop in self.rain_drops:

                color = QColor(
                    rain_color.red(),
                    rain_color.green(),
                    rain_color.blue(),
                    drop.alpha
                )

                pen = QPen(color)

                pen.setWidthF(
                    rain["width"]
                )

                painter.setPen(pen)

                painter.drawLine(

                    QPointF(
                        drop.x,
                        drop.y
                    ),

                    QPointF(
                        drop.x - 1,
                        drop.y + drop.length
                    )
                )

        # ====================================================
        # CURSOR GLOW
        # ====================================================

        glow = settings["cursor_glow"]

        if glow["enabled"]:

            local_x = (
                cursor_x
                - self.virtual_left
            )

            local_y = (
                cursor_y
                - self.virtual_top
            )

            glow_color = qcolor(
                glow["color"]
            )

            radius = max(
                1,
                glow["radius"]
            )

            for current_radius in range(
                radius,
                3,
                -4
            ):

                alpha = int(

                    glow["opacity"]
                    *
                    (
                        1
                        -
                        current_radius / radius
                    )
                )

                alpha = max(
                    0,
                    alpha
                )

                painter.setPen(
                    Qt.PenStyle.NoPen
                )

                painter.setBrush(
                    QColor(
                        glow_color.red(),
                        glow_color.green(),
                        glow_color.blue(),
                        alpha
                    )
                )

                painter.drawEllipse(

                    QPointF(
                        local_x,
                        local_y
                    ),

                    current_radius,
                    current_radius
                )

        # ====================================================
        # CURSOR PARTICLES
        # ====================================================

        trail = settings["mouse_trail"]

        if trail["enabled"]:

            trail_color = qcolor(
                trail["color"]
            )

            for particle in self.cursor_particles:

                alpha = int(

                    255
                    *
                    (
                        particle.life
                        /
                        particle.max_life
                    )
                )

                color = QColor(
                    trail_color.red(),
                    trail_color.green(),
                    trail_color.blue(),
                    alpha
                )

                self.draw_particle(
                    painter,
                    particle,
                    color
                )

        # ====================================================
        # TYPING
        # ====================================================

        typing = settings["typing"]

        if typing["enabled"]:

            typing_color = qcolor(
                typing["color"]
            )

            font = QFont(
                typing["font"],
                typing["size"]
            )

            font.setBold(
                typing["bold"]
            )

            painter.setFont(font)

            for particle in self.typing_particles:

                alpha = int(

                    255
                    *
                    (
                        particle.life
                        /
                        particle.max_life
                    )
                )

                color = QColor(
                    typing_color.red(),
                    typing_color.green(),
                    typing_color.blue(),
                    alpha
                )

                painter.setPen(color)

                painter.drawText(

                    QPointF(
                        particle.x,
                        particle.y
                    ),

                    particle.text
                )

        # ====================================================
        # WINDOW GLOW
        # ====================================================

        window_glow = settings["window_glow"]

        if window_glow["enabled"]:

            hwnd = user32.GetForegroundWindow()

            if hwnd:

                window = get_active_window_rect()

                if window:

                    left, top, right, bottom = window

                    maximized = is_window_maximized(
                        hwnd
                    )

                    local_left = (
                        left
                        - self.virtual_left
                    )

                    local_top = (
                        top
                        - self.virtual_top
                    )

                    local_right = (
                        right
                        - self.virtual_left
                    )

                    local_bottom = (
                        bottom
                        - self.virtual_top
                    )

                    width = (
                        local_right
                        - local_left
                    )

                    height = (
                        local_bottom
                        - local_top
                    )

                    if (
                        width > 0
                        and height > 0
                    ):

                        def create_path(inset):

                            rect = QRectF(

                                local_left + inset,
                                local_top + inset,

                                width - (
                                    2 * inset
                                ),

                                height - (
                                    2 * inset
                                )
                            )

                            path = QPainterPath()

                            if maximized:

                                path.addRect(
                                    rect
                                )

                            else:

                                radius = max(

                                    0,

                                    window_glow[
                                        "corner_radius"
                                    ]
                                    - inset
                                )

                                path.addRoundedRect(
                                    rect,
                                    radius,
                                    radius
                                )

                            return path

                        painter.setPen(
                            Qt.PenStyle.NoPen
                        )

                        radius = max(
                            1,
                            window_glow["radius"]
                        )

                        for inset in range(
                            radius,
                            0,
                            -2
                        ):

                            outer = create_path(
                                -inset
                            )

                            inner = create_path(
                                -(inset - 2)
                            )

                            ring = outer.subtracted(
                                inner
                            )

                            alpha = max(

                                2,

                                int(
                                    window_glow["opacity"]
                                    *
                                    (
                                        1
                                        -
                                        inset / radius
                                    )
                                )
                            )

                            glow_color = qcolor(
                                window_glow["color"]
                            )

                            painter.setBrush(
                                QColor(
                                    glow_color.red(),
                                    glow_color.green(),
                                    glow_color.blue(),
                                    alpha
                                )
                            )

                            painter.drawPath(
                                ring
                            )

                        main_path = create_path(0)

                        main_color = qcolor(
                            window_glow["color"]
                        )

                        pen = QPen(
                            QColor(
                                main_color.red(),
                                main_color.green(),
                                main_color.blue(),
                                min(
                                    255,
                                    window_glow["opacity"]
                                    * 6
                                )
                            )
                        )

                        pen.setWidthF(
                            window_glow["width"]
                        )

                        painter.setPen(pen)

                        painter.drawPath(
                            main_path
                        )

        painter.end()


# ============================================================
# TOGGLE BUTTON
# ============================================================

class ToggleButton(QCheckBox):

    def __init__(
        self,
        parent=None
    ):

        super().__init__(parent)

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.setFixedSize(
            48,
            26
        )

        self.setStyleSheet("""

            QCheckBox {
                background: transparent;
            }

            QCheckBox::indicator {
                width: 48px;
                height: 26px;
            }

            QCheckBox::indicator:unchecked {
                background-color: #332938;
                border: 1px solid #55445a;
                border-radius: 13px;
            }

            QCheckBox::indicator:checked {
                background-color: #ff78d2;
                border: 1px solid #ffb4eb;
                border-radius: 13px;
            }

        """)


# ============================================================
# COLOR BUTTON
# ============================================================

class ColorButton(QPushButton):

    colorChanged = pyqtSignal(str)

    def __init__(
        self,
        color,
        parent=None
    ):

        super().__init__(parent)

        self.color = color

        self.setFixedSize(
            72,
            30
        )

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.clicked.connect(
            self.pick_color
        )

        self.update_style()

    def update_style(self):

        color = qcolor(
            self.color
        )

        self.setStyleSheet(f"""

            QPushButton {{
                background-color: {color.name()};
                border: 1px solid #ffffff55;
                border-radius: 8px;
            }}

            QPushButton:hover {{
                border: 2px solid #ffffffaa;
            }}

        """)

    def pick_color(self):

        color = QColorDialog.getColor(
            qcolor(self.color),
            self.window(),
            "Choose color"
        )

        if not color.isValid():
            return

        self.color = color.name()

        self.update_style()

        self.colorChanged.emit(
            self.color
        )


# ============================================================
# EFFECT ROW
# ============================================================

class EffectRow(QFrame):

    def __init__(
        self,
        title,
        description,
        checked,
        callback,
        parent=None
    ):

        super().__init__(parent)

        self.setObjectName(
            "EffectRow"
        )

        self.setStyleSheet("""

            QFrame#EffectRow {
                background-color: #1b1421;
                border: 1px solid #302438;
                border-radius: 12px;
            }

            QFrame#EffectRow:hover {
                background-color: #22192a;
                border: 1px solid #49334d;
            }

            QLabel {
                background: transparent;
            }

        """)

        self.setMinimumHeight(68)

        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            16,
            10,
            16,
            10
        )

        layout.setSpacing(12)

        text_layout = QVBoxLayout()

        text_layout.setSpacing(2)

        title_label = QLabel(title)

        title_label.setStyleSheet("""
            color: #f5f0f7;
            font-size: 14px;
            font-weight: 600;
        """)

        description_label = QLabel(description)

        description_label.setStyleSheet("""
            color: #a096a5;
            font-size: 11px;
        """)

        text_layout.addWidget(
            title_label
        )

        text_layout.addWidget(
            description_label
        )

        layout.addLayout(
            text_layout
        )

        layout.addStretch()

        self.toggle = ToggleButton()

        self.toggle.setChecked(
            checked
        )

        self.toggle.toggled.connect(
            callback
        )

        layout.addWidget(
            self.toggle
        )


# ============================================================
# SECTION TITLE
# ============================================================

class SectionTitle(QLabel):

    def __init__(
        self,
        text
    ):

        super().__init__(
            text
        )

        self.setStyleSheet("""

            QLabel {
                color: #ff78d2;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 2px;
                padding-top: 10px;
                padding-bottom: 2px;
            }

        """)


# ============================================================
# SETTING ROW
# ============================================================

class SettingRow(QFrame):

    def __init__(
        self,
        title,
        description,
        widget,
        parent=None
    ):

        super().__init__(parent)

        self.setObjectName(
            "SettingRow"
        )

        self.setStyleSheet("""

            QFrame#SettingRow {
                background-color: #1b1421;
                border: 1px solid #302438;
                border-radius: 10px;
            }

            QLabel {
                background: transparent;
            }

        """)

        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            14,
            8,
            14,
            8
        )

        text_layout = QVBoxLayout()

        title_label = QLabel(title)

        title_label.setStyleSheet("""
            color: #f5f0f7;
            font-size: 12px;
            font-weight: 600;
        """)

        description_label = QLabel(description)

        description_label.setStyleSheet("""
            color: #827786;
            font-size: 10px;
        """)

        text_layout.addWidget(
            title_label
        )

        text_layout.addWidget(
            description_label
        )

        layout.addLayout(
            text_layout
        )

        layout.addStretch()

        layout.addWidget(
            widget
        )


# ============================================================
# DRAGGABLE + RESIZABLE SETTINGS WINDOW
# ============================================================

class SettingsWindow(QWidget):

    def __init__(
        self,
        overlay
    ):

        super().__init__()

        self.overlay = overlay

        self.dragging = False
        self.resizing = False

        self.drag_position = QPoint()
        self.resize_start_position = QPoint()

        self.resize_start_geometry = None

        self.resize_margin = 8

        self.setWindowTitle(
            APP_NAME
        )

        self.setWindowIcon(
            QIcon(
                str(ICON_PATH)
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # Not fixed anymore
        # ----------------------------------------------------

        self.setMinimumSize(
            470,
            500
        )

        self.resize(
            520,
            720
        )

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            |
            Qt.WindowType.Window
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )

        self.setup_ui()

    # ========================================================
    # MOUSE DRAG
    # ========================================================

    def mousePressEvent(self, event):

        if event.button() != Qt.MouseButton.LeftButton:
            return

        position = event.position().toPoint()

        if self.in_resize_area(position):

            self.resizing = True

            self.resize_start_position = (
                event.globalPosition().toPoint()
            )

            self.resize_start_geometry = (
                self.geometry()
            )

            event.accept()

            return

        # Top 60 px = title bar

        if position.y() <= 65:

            self.dragging = True

            self.drag_position = (
                event.globalPosition().toPoint()
                -
                self.frameGeometry().topLeft()
            )

            event.accept()

    def mouseMoveEvent(self, event):

        position = event.position().toPoint()

        if self.resizing:

            delta = (
                event.globalPosition().toPoint()
                -
                self.resize_start_position
            )

            geometry = self.resize_start_geometry

            new_width = max(
                self.minimumWidth(),
                geometry.width() + delta.x()
            )

            new_height = max(
                self.minimumHeight(),
                geometry.height() + delta.y()
            )

            self.resize(
                new_width,
                new_height
            )

            event.accept()

            return

        if self.dragging:

            self.move(
                event.globalPosition().toPoint()
                -
                self.drag_position
            )

            event.accept()

            return

        if self.in_resize_area(position):

            self.setCursor(
                Qt.CursorShape.SizeFDiagCursor
            )

        else:

            self.setCursor(
                Qt.CursorShape.ArrowCursor
            )

    def mouseReleaseEvent(self, event):

        self.dragging = False
        self.resizing = False

        self.setCursor(
            Qt.CursorShape.ArrowCursor
        )

    def in_resize_area(self, position):

        return (
            position.x()
            >=
            self.width()
            -
            self.resize_margin
            and
            position.y()
            >=
            self.height()
            -
            self.resize_margin
        )

    # ========================================================
    # UI
    # ========================================================

    def setup_ui(self):

        root = QVBoxLayout(self)

        root.setContentsMargins(
            10,
            10,
            10,
            10
        )

        root.setSpacing(0)

        container = QFrame()

        container.setObjectName(
            "Container"
        )

        container.setStyleSheet("""

            QFrame#Container {
                background-color: #100c14;
                border: 1px solid #3a2940;
                border-radius: 18px;
            }

        """)

        root.addWidget(
            container
        )

        container_layout = QVBoxLayout(
            container
        )

        container_layout.setContentsMargins(
            20,
            18,
            20,
            14
        )

        container_layout.setSpacing(
            8
        )

        # ====================================================
        # HEADER
        # ====================================================

        header = QHBoxLayout()

        icon_label = QLabel()

        if ICON_PATH.exists():

            pixmap = QPixmap(
                str(ICON_PATH)
            )

            pixmap = pixmap.scaled(
                38,
                38,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            icon_label.setPixmap(
                pixmap
            )

        header.addWidget(
            icon_label
        )

        title_layout = QVBoxLayout()

        title = QLabel(
            "Keyboard Effects"
        )

        title.setStyleSheet("""
            color: #f5f0f7;
            font-size: 21px;
            font-weight: 700;
        """)

        subtitle = QLabel(
            "Visual effects & keyboard sounds"
        )

        subtitle.setStyleSheet("""
            color: #a096a5;
            font-size: 11px;
        """)

        title_layout.addWidget(
            title
        )

        title_layout.addWidget(
            subtitle
        )

        header.addLayout(
            title_layout
        )

        header.addStretch()

        close_button = QPushButton(
            "×"
        )

        close_button.setFixedSize(
            34,
            34
        )

        close_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        close_button.setStyleSheet("""

            QPushButton {
                color: #a096a5;
                background: transparent;
                border: none;
                font-size: 24px;
                border-radius: 8px;
            }

            QPushButton:hover {
                color: white;
                background: #302238;
            }

        """)

        close_button.clicked.connect(
            self.hide
        )

        header.addWidget(
            close_button
        )

        container_layout.addLayout(
            header
        )

        # ====================================================
        # SCROLL AREA
        # ====================================================

        scroll = QScrollArea()

        scroll.setWidgetResizable(
            True
        )

        scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )

        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        scroll.setStyleSheet("""

            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical {
                background: #171119;
                width: 7px;
                margin: 3px;
                border-radius: 3px;
            }

            QScrollBar::handle:vertical {
                background: #49334d;
                border-radius: 3px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #ff78d2;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

        """)

        content = QWidget()

        content.setStyleSheet(
            "background: transparent;"
        )

        layout = QVBoxLayout(
            content
        )

        layout.setContentsMargins(
            2,
            8,
            8,
            8
        )

        layout.setSpacing(
            8
        )

        # ====================================================
        # GENERAL
        # ====================================================

        layout.addWidget(
            SectionTitle("GENERAL")
        )

        layout.addWidget(

            EffectRow(

                "Keyboard Sounds",
                "Play a sound when a key is pressed.",

                settings["keyboard_sounds"],

                self.toggle_keyboard
            )
        )

        # ====================================================
        # TYPING
        # ====================================================

        layout.addWidget(
            SectionTitle("TYPING EFFECT")
        )

        layout.addWidget(

            EffectRow(

                "Typing Effect",
                "Floating characters appear while typing.",

                settings["typing"]["enabled"],

                self.toggle_typing
            )
        )

        typing_color = ColorButton(
            settings["typing"]["color"]
        )

        typing_color.colorChanged.connect(
            self.set_typing_color
        )

        layout.addWidget(

            SettingRow(
                "Color",
                "Color of the floating characters.",
                typing_color
            )
        )

        self.typing_font = QComboBox()

        fonts = [
            "Segoe UI",
            "Arial",
            "Consolas",
            "Cascadia Code",
            "Cascadia Mono",
            "Tahoma",
            "Verdana",
            "Courier New",
            "Times New Roman",
        ]

        self.typing_font.addItems(
            fonts
        )

        current_font = settings["typing"]["font"]

        if current_font in fonts:

            self.typing_font.setCurrentText(
                current_font
            )

        self.typing_font.currentTextChanged.connect(
            self.set_typing_font
        )

        self.style_combo(
            self.typing_font
        )

        layout.addWidget(

            SettingRow(
                "Font",
                "Font used for typing particles.",
                self.typing_font
            )
        )

        self.typing_size = QSpinBox()

        self.typing_size.setRange(
            6,
            72
        )

        self.typing_size.setValue(
            settings["typing"]["size"]
        )

        self.typing_size.valueChanged.connect(
            self.set_typing_size
        )

        self.style_spin(
            self.typing_size
        )

        layout.addWidget(

            SettingRow(
                "Font Size",
                "Size of the typing characters.",
                self.typing_size
            )
        )

        self.typing_lifetime = QSpinBox()

        self.typing_lifetime.setRange(
            1,
            300
        )

        self.typing_lifetime.setValue(
            settings["typing"]["lifetime"]
        )

        self.typing_lifetime.valueChanged.connect(
            self.set_typing_lifetime
        )

        self.style_spin(
            self.typing_lifetime
        )

        layout.addWidget(

            SettingRow(
                "Lifetime",
                "How long a character remains visible.",
                self.typing_lifetime
            )
        )

        # ====================================================
        # MOUSE TRAIL
        # ====================================================

        layout.addWidget(
            SectionTitle("MOUSE TRAIL")
        )

        layout.addWidget(

            EffectRow(

                "Mouse Trail",
                "Particles follow your mouse cursor.",

                settings["mouse_trail"]["enabled"],

                self.toggle_mouse_trail
            )
        )

        trail_color = ColorButton(
            settings["mouse_trail"]["color"]
        )

        trail_color.colorChanged.connect(
            self.set_trail_color
        )

        layout.addWidget(

            SettingRow(
                "Color",
                "Color of the mouse particles.",
                trail_color
            )
        )

        self.particle_combo = QComboBox()

        particle_types = [
            "Circle",
            "Square",
            "Diamond",
            "Star",
            "Spark",
        ]

        self.particle_combo.addItems(
            particle_types
        )

        current_particle = (
            settings["mouse_trail"]["particle"]
        )

        if current_particle in particle_types:

            self.particle_combo.setCurrentText(
                current_particle
            )

        self.particle_combo.currentTextChanged.connect(
            self.set_particle_type
        )

        self.style_combo(
            self.particle_combo
        )

        layout.addWidget(

            SettingRow(
                "Particle",
                "Shape used by the mouse trail.",
                self.particle_combo
            )
        )

        self.trail_size = QDoubleSpinBox()

        self.trail_size.setRange(
            0.2,
            20
        )

        self.trail_size.setSingleStep(
            0.2
        )

        self.trail_size.setValue(
            settings["mouse_trail"]["size"]
        )

        self.trail_size.valueChanged.connect(
            self.set_trail_size
        )

        self.style_spin(
            self.trail_size
        )

        layout.addWidget(

            SettingRow(
                "Particle Size",
                "Size of individual particles.",
                self.trail_size
            )
        )

        self.trail_lifetime = QSpinBox()

        self.trail_lifetime.setRange(
            1,
            200
        )

        self.trail_lifetime.setValue(
            settings["mouse_trail"]["lifetime"]
        )

        self.trail_lifetime.valueChanged.connect(
            self.set_trail_lifetime
        )

        self.style_spin(
            self.trail_lifetime
        )

        layout.addWidget(

            SettingRow(
                "Lifetime",
                "How long particles stay alive.",
                self.trail_lifetime
            )
        )

        self.trail_amount = QSpinBox()

        self.trail_amount.setRange(
            1,
            500
        )

        self.trail_amount.setValue(
            settings["mouse_trail"]["amount"]
        )

        self.trail_amount.valueChanged.connect(
            self.set_trail_amount
        )

        self.style_spin(
            self.trail_amount
        )

        layout.addWidget(

            SettingRow(
                "Particle Amount",
                "Maximum number of trail particles.",
                self.trail_amount
            )
        )

        # ====================================================
        # CURSOR GLOW
        # ====================================================

        layout.addWidget(
            SectionTitle("CURSOR GLOW")
        )

        layout.addWidget(

            EffectRow(

                "Cursor Glow",
                "Soft glow around the mouse cursor.",

                settings["cursor_glow"]["enabled"],

                self.toggle_cursor_glow
            )
        )

        cursor_color = ColorButton(
            settings["cursor_glow"]["color"]
        )

        cursor_color.colorChanged.connect(
            self.set_cursor_glow_color
        )

        layout.addWidget(

            SettingRow(
                "Color",
                "Color of the cursor glow.",
                cursor_color
            )
        )

        self.cursor_radius = QSpinBox()

        self.cursor_radius.setRange(
            5,
            150
        )

        self.cursor_radius.setValue(
            settings["cursor_glow"]["radius"]
        )

        self.cursor_radius.valueChanged.connect(
            self.set_cursor_radius
        )

        self.style_spin(
            self.cursor_radius
        )

        layout.addWidget(

            SettingRow(
                "Radius",
                "Size of the cursor glow.",
                self.cursor_radius
            )
        )

        self.cursor_opacity = QSpinBox()

        self.cursor_opacity.setRange(
            1,
            255
        )

        self.cursor_opacity.setValue(
            settings["cursor_glow"]["opacity"]
        )

        self.cursor_opacity.valueChanged.connect(
            self.set_cursor_opacity
        )

        self.style_spin(
            self.cursor_opacity
        )

        layout.addWidget(

            SettingRow(
                "Opacity",
                "Brightness of the cursor glow.",
                self.cursor_opacity
            )
        )

        # ====================================================
        # RAIN
        # ====================================================

        layout.addWidget(
            SectionTitle("RAIN EFFECT")
        )

        layout.addWidget(

            EffectRow(

                "Rain Effect",
                "Animated rain particles across the desktop.",

                settings["rain"]["enabled"],

                self.toggle_rain
            )
        )

        rain_color = ColorButton(
            settings["rain"]["color"]
        )

        rain_color.colorChanged.connect(
            self.set_rain_color
        )

        layout.addWidget(

            SettingRow(
                "Color",
                "Independent color for the rain.",
                rain_color
            )
        )

        self.rain_amount = QSpinBox()

        self.rain_amount.setRange(
            0,
            500
        )

        self.rain_amount.setValue(
            settings["rain"]["amount"]
        )

        self.rain_amount.valueChanged.connect(
            self.set_rain_amount
        )

        self.style_spin(
            self.rain_amount
        )

        layout.addWidget(

            SettingRow(
                "Amount",
                "Number of rain drops.",
                self.rain_amount
            )
        )

        self.rain_speed_min = QSpinBox()

        self.rain_speed_min.setRange(
            1,
            100
        )

        self.rain_speed_min.setValue(
            settings["rain"]["speed_min"]
        )

        self.rain_speed_min.valueChanged.connect(
            self.set_rain_speed_min
        )

        self.style_spin(
            self.rain_speed_min
        )

        layout.addWidget(

            SettingRow(
                "Minimum Speed",
                "Slowest rain drop speed.",
                self.rain_speed_min
            )
        )

        self.rain_speed_max = QSpinBox()

        self.rain_speed_max.setRange(
            1,
            100
        )

        self.rain_speed_max.setValue(
            settings["rain"]["speed_max"]
        )

        self.rain_speed_max.valueChanged.connect(
            self.set_rain_speed_max
        )

        self.style_spin(
            self.rain_speed_max
        )

        layout.addWidget(

            SettingRow(
                "Maximum Speed",
                "Fastest rain drop speed.",
                self.rain_speed_max
            )
        )

        self.rain_length = QSpinBox()

        self.rain_length.setRange(
            1,
            100
        )

        self.rain_length.setValue(
            settings["rain"]["length_max"]
        )

        self.rain_length.valueChanged.connect(
            self.set_rain_length
        )

        self.style_spin(
            self.rain_length
        )

        layout.addWidget(

            SettingRow(
                "Drop Length",
                "Length of the rain drops.",
                self.rain_length
            )
        )

        self.rain_width = QDoubleSpinBox()

        self.rain_width.setRange(
            0.2,
            10
        )

        self.rain_width.setSingleStep(
            0.2
        )

        self.rain_width.setValue(
            settings["rain"]["width"]
        )

        self.rain_width.valueChanged.connect(
            self.set_rain_width
        )

        self.style_spin(
            self.rain_width
        )

        layout.addWidget(

            SettingRow(
                "Drop Width",
                "Thickness of the rain.",
                self.rain_width
            )
        )

        # ====================================================
        # WINDOW GLOW
        # ====================================================

        layout.addWidget(
            SectionTitle("WINDOW GLOW")
        )

        layout.addWidget(

            EffectRow(

                "Window Glow",
                "Highlight the currently active window.",

                settings["window_glow"]["enabled"],

                self.toggle_window_glow
            )
        )

        window_color = ColorButton(
            settings["window_glow"]["color"]
        )

        window_color.colorChanged.connect(
            self.set_window_glow_color
        )

        layout.addWidget(

            SettingRow(
                "Color",
                "Independent border glow color.",
                window_color
            )
        )

        self.window_radius = QSpinBox()

        self.window_radius.setRange(
            1,
            50
        )

        self.window_radius.setValue(
            settings["window_glow"]["radius"]
        )

        self.window_radius.valueChanged.connect(
            self.set_window_radius
        )

        self.style_spin(
            self.window_radius
        )

        layout.addWidget(

            SettingRow(
                "Glow Radius",
                "How far the glow spreads.",
                self.window_radius
            )
        )

        self.window_opacity = QSpinBox()

        self.window_opacity.setRange(
            1,
            100
        )

        self.window_opacity.setValue(
            settings["window_glow"]["opacity"]
        )

        self.window_opacity.valueChanged.connect(
            self.set_window_opacity
        )

        self.style_spin(
            self.window_opacity
        )

        layout.addWidget(

            SettingRow(
                "Glow Opacity",
                "Strength of the window glow.",
                self.window_opacity
            )
        )

        # ====================================================
        # RESET
        # ====================================================

        layout.addSpacing(
            15
        )

        reset_button = QPushButton(
            "Reset all settings"
        )

        reset_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        reset_button.setMinimumHeight(
            38
        )

        reset_button.setStyleSheet("""

            QPushButton {
                color: #f5f0f7;
                background-color: #211823;
                border: 1px solid #49334d;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #302238;
                border: 1px solid #ff78d2;
            }

        """)

        reset_button.clicked.connect(
            self.reset_settings
        )

        layout.addWidget(
            reset_button
        )

        layout.addStretch()

        scroll.setWidget(
            content
        )

        container_layout.addWidget(
            scroll
        )

        # ====================================================
        # FOOTER
        # ====================================================

        footer = QHBoxLayout()

        version = QLabel(
            f"v{APP_VERSION}"
        )

        version.setStyleSheet("""
            color: #675d6b;
            font-size: 10px;
        """)

        footer.addWidget(
            version
        )

        footer.addStretch()

        tray_text = QLabel(
            "Running in system tray"
        )

        tray_text.setStyleSheet("""
            color: #675d6b;
            font-size: 10px;
        """)

        footer.addWidget(
            tray_text
        )

        container_layout.addLayout(
            footer
        )

    # ========================================================
    # WIDGET STYLING
    # ========================================================

    def style_combo(
        self,
        combo
    ):

        combo.setMinimumWidth(
            145
        )

        combo.setStyleSheet("""

            QComboBox {
                color: #f5f0f7;
                background: #211823;
                border: 1px solid #49334d;
                border-radius: 7px;
                padding: 5px 9px;
            }

            QComboBox:hover {
                border: 1px solid #ff78d2;
            }

            QComboBox QAbstractItemView {
                color: #f5f0f7;
                background: #171119;
                border: 1px solid #49334d;
                selection-background-color: #33213a;
            }

        """)

    def style_spin(
        self,
        widget
    ):

        widget.setMinimumWidth(
            100
        )

        widget.setStyleSheet("""

            QSpinBox,
            QDoubleSpinBox {
                color: #f5f0f7;
                background: #211823;
                border: 1px solid #49334d;
                border-radius: 7px;
                padding: 5px;
            }

            QSpinBox:hover,
            QDoubleSpinBox:hover {
                border: 1px solid #ff78d2;
            }

        """)

    # ========================================================
    # GENERAL
    # ========================================================

    def save(self):

        save_settings()

        self.overlay.refresh_rain()

        self.overlay.update()

    def toggle_keyboard(
        self,
        value
    ):

        settings["keyboard_sounds"] = value

        self.save()

    # ========================================================
    # TYPING
    # ========================================================

    def toggle_typing(
        self,
        value
    ):

        settings["typing"]["enabled"] = value

        self.save()

    def set_typing_color(
        self,
        color
    ):

        settings["typing"]["color"] = color

        self.save()

    def set_typing_font(
        self,
        font
    ):

        settings["typing"]["font"] = font

        self.save()

    def set_typing_size(
        self,
        value
    ):

        settings["typing"]["size"] = value

        self.save()

    def set_typing_lifetime(
        self,
        value
    ):

        settings["typing"]["lifetime"] = value

        self.save()

    # ========================================================
    # TRAIL
    # ========================================================

    def toggle_mouse_trail(
        self,
        value
    ):

        settings["mouse_trail"]["enabled"] = value

        self.save()

    def set_trail_color(
        self,
        color
    ):

        settings["mouse_trail"]["color"] = color

        self.save()

    def set_particle_type(
        self,
        value
    ):

        settings["mouse_trail"]["particle"] = value

        self.save()

    def set_trail_size(
        self,
        value
    ):

        settings["mouse_trail"]["size"] = value

        self.save()

    def set_trail_lifetime(
        self,
        value
    ):

        settings["mouse_trail"]["lifetime"] = value

        self.save()

    def set_trail_amount(
        self,
        value
    ):

        settings["mouse_trail"]["amount"] = value

        self.save()

    # ========================================================
    # CURSOR GLOW
    # ========================================================

    def toggle_cursor_glow(
        self,
        value
    ):

        settings["cursor_glow"]["enabled"] = value

        self.save()

    def set_cursor_glow_color(
        self,
        color
    ):

        settings["cursor_glow"]["color"] = color

        self.save()

    def set_cursor_radius(
        self,
        value
    ):

        settings["cursor_glow"]["radius"] = value

        self.save()

    def set_cursor_opacity(
        self,
        value
    ):

        settings["cursor_glow"]["opacity"] = value

        self.save()

    # ========================================================
    # RAIN
    # ========================================================

    def toggle_rain(
        self,
        value
    ):

        settings["rain"]["enabled"] = value

        self.save()

    def set_rain_color(
        self,
        color
    ):

        settings["rain"]["color"] = color

        self.save()

    def set_rain_amount(
        self,
        value
    ):

        settings["rain"]["amount"] = value

        self.save()

    def set_rain_speed_min(
        self,
        value
    ):

        settings["rain"]["speed_min"] = value

        if (
            settings["rain"]["speed_max"]
            <
            value
        ):

            settings["rain"]["speed_max"] = value

            self.rain_speed_max.setValue(
                value
            )

        self.save()

    def set_rain_speed_max(
        self,
        value
    ):

        settings["rain"]["speed_max"] = value

        if (
            value
            <
            settings["rain"]["speed_min"]
        ):

            settings["rain"]["speed_min"] = value

            self.rain_speed_min.setValue(
                value
            )

        self.save()

    def set_rain_length(
        self,
        value
    ):

        settings["rain"]["length_max"] = value

        settings["rain"]["length_min"] = max(
            1,
            int(value * 0.5)
        )

        self.save()

    def set_rain_width(
        self,
        value
    ):

        settings["rain"]["width"] = value

        self.save()

    # ========================================================
    # WINDOW GLOW
    # ========================================================

    def toggle_window_glow(
        self,
        value
    ):

        settings["window_glow"]["enabled"] = value

        self.save()

    def set_window_glow_color(
        self,
        color
    ):

        settings["window_glow"]["color"] = color

        self.save()

    def set_window_radius(
        self,
        value
    ):

        settings["window_glow"]["radius"] = value

        self.save()

    def set_window_opacity(
        self,
        value
    ):

        settings["window_glow"]["opacity"] = value

        self.save()

    # ========================================================
    # RESET
    # ========================================================

    def reset_settings(self):

        global settings

        settings = deep_copy_settings()

        save_settings()

        # Rebuild the entire UI so every control
        # immediately reflects the defaults.

        self.overlay.setup_rain()

        self.hide()

        # Recreate the window

        new_window = SettingsWindow(
            self.overlay
        )

        # Replace contents through parent tray app

        global tray_app_reference

        if tray_app_reference is not None:

            old = tray_app_reference.window

            tray_app_reference.window = new_window

            old.deleteLater()

            new_window.show()

            new_window.raise_()

            new_window.activateWindow()


    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(
        self,
        event
    ):

        event.ignore()

        self.hide()


# ============================================================
# TRAY APPLICATION
# ============================================================

tray_app_reference = None


class TrayApplication:

    def __init__(
        self,
        app,
        overlay
    ):

        global tray_app_reference

        tray_app_reference = self

        self.app = app

        self.overlay = overlay

        self.window = SettingsWindow(
            overlay
        )

        self.tray = QSystemTrayIcon()

        self.tray.setIcon(
            QIcon(
                str(ICON_PATH)
            )
        )

        self.tray.setToolTip(
            APP_NAME
        )

        self.setup_menu()

        self.tray.activated.connect(
            self.tray_activated
        )

        self.tray.show()

    # ========================================================
    # MENU
    # ========================================================

    def setup_menu(self):

        menu = QMenu()

        menu.setStyleSheet("""

            QMenu {
                background-color: #171119;
                color: #f5f0f7;
                border: 1px solid #3a2940;
                padding: 6px;
            }

            QMenu::item {
                padding: 8px 28px 8px 12px;
                border-radius: 6px;
            }

            QMenu::item:selected {
                background-color: #33213a;
            }

            QMenu::separator {
                height: 1px;
                background: #302438;
                margin: 5px 8px;
            }

        """)

        show_action = menu.addAction(
            "Open Settings"
        )

        show_action.triggered.connect(
            self.show_window
        )

        hide_action = menu.addAction(
            "Hide Settings"
        )

        hide_action.triggered.connect(
            self.hide_window
        )

        menu.addSeparator()

        quit_action = menu.addAction(
            "Exit"
        )

        quit_action.triggered.connect(
            self.exit_application
        )

        self.tray.setContextMenu(
            menu
        )

    # ========================================================
    # TRAY CLICK
    # ========================================================

    def tray_activated(
        self,
        reason
    ):

        if reason in (

            QSystemTrayIcon.ActivationReason.Trigger,

            QSystemTrayIcon.ActivationReason.DoubleClick

        ):

            if self.window.isVisible():

                self.window.hide()

            else:

                self.show_window()

    # ========================================================
    # SHOW
    # ========================================================

    def show_window(self):

        self.window.show()

        self.window.raise_()

        self.window.activateWindow()

    # ========================================================
    # HIDE
    # ========================================================

    def hide_window(self):

        self.window.hide()

    # ========================================================
    # EXIT
    # ========================================================

    def exit_application(self):

        global running

        running = False

        try:

            if keyboard_listener:

                keyboard_listener.stop()

        except Exception:

            pass

        try:

            self.tray.hide()

        except Exception:

            pass

        try:

            pygame.mixer.stop()

            pygame.mixer.quit()

        except Exception:

            pass

        self.app.quit()


# ============================================================
# MAIN
# ============================================================

def main():

    global running

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    app.setApplicationVersion(
        APP_VERSION
    )

    app.setQuitOnLastWindowClosed(
        False
    )

    # --------------------------------------------------------
    # Application icon
    # --------------------------------------------------------

    if ICON_PATH.exists():

        app.setWindowIcon(
            QIcon(
                str(ICON_PATH)
            )
        )

    # --------------------------------------------------------
    # Overlay
    # --------------------------------------------------------

    overlay = VisualOverlay()

    overlay.show()

    overlay.make_click_through()

    # --------------------------------------------------------
    # Keyboard listener
    # --------------------------------------------------------

    keyboard_thread = threading.Thread(

        target=keyboard_listener_thread,

        daemon=True
    )

    keyboard_thread.start()

    # --------------------------------------------------------
    # Tray
    # --------------------------------------------------------

    tray_app = TrayApplication(
        app,
        overlay
    )

    # --------------------------------------------------------
    # Start settings hidden
    # --------------------------------------------------------

    tray_app.window.hide()

    # --------------------------------------------------------
    # Event loop
    # --------------------------------------------------------

    try:

        exit_code = app.exec()

    except KeyboardInterrupt:

        exit_code = 0

    running = False

    try:

        if keyboard_listener:

            keyboard_listener.stop()

    except Exception:

        pass

    try:

        pygame.mixer.stop()

        pygame.mixer.quit()

    except Exception:

        pass

    sys.exit(
        exit_code
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
