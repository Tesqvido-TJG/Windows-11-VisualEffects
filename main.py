import sys
import ctypes
import ctypes.wintypes
import threading
import queue
import random
from pathlib import Path

import pygame
from pynput import keyboard

from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPointF,
    QRectF,
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
)


# ============================================================
# APPLICATION
# ============================================================

APP_NAME = "Keyboard Effects"
APP_VERSION = "1.0.0"


# ============================================================
# RESOURCE PATH
# ============================================================

def resource_path(relative_path):
    """
    Funktioniert sowohl mit Python als auch
    mit einer PyInstaller EXE.
    """

    if getattr(sys, "frozen", False):

        base_path = Path(
            sys._MEIPASS
        )

    else:

        base_path = Path(
            __file__
        ).resolve().parent

    return base_path / relative_path


# ============================================================
# FILES
# ============================================================

ICON_PATH = resource_path(
    "icon.ico"
)

SOUNDS_PATH = resource_path(
    "sounds"
)

NORMAL_SOUND = (
    SOUNDS_PATH /
    "general-sound.mp3"
)

ENTER_SOUND = (
    SOUNDS_PATH /
    "space-enter.mp3"
)

SPACE_SOUND = (
    SOUNDS_PATH /
    "space-enter.mp3"
)


# ============================================================
# SETTINGS
# ============================================================

CURSOR_TRAIL = True
CURSOR_GLOW = True
WINDOW_GLOW = False
RAIN_EFFECT = True
TYPING_EFFECT = True
KEYBOARD_SOUNDS = True


# ============================================================
# COLORS
# ============================================================

BG_COLOR = QColor(
    16,
    12,
    20
)

CARD_COLOR = QColor(
    27,
    20,
    33
)

CARD_HOVER = QColor(
    34,
    25,
    42
)

PINK = QColor(
    255,
    120,
    210
)

PINK_LIGHT = QColor(
    255,
    180,
    235
)

PINK_DARK = QColor(
    220,
    70,
    170
)

TEXT_COLOR = QColor(
    245,
    240,
    247
)

SECONDARY_TEXT = QColor(
    160,
    150,
    165
)


# ============================================================
# EFFECT SETTINGS
# ============================================================

CURSOR_PARTICLE_LIFE = 18

TYPING_PARTICLE_LIFE = 45

RAIN_AMOUNT = 120

RAIN_SPEED_MIN = 7

RAIN_SPEED_MAX = 15

WINDOW_GLOW_RADIUS = 12

WINDOW_CORNER_RADIUS = 10

UPDATE_INTERVAL = 16


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
# RAIN DROP
# ============================================================

class RainDrop:

    def __init__(
        self,
        width,
        height
    ):

        self.x = random.uniform(
            0,
            width
        )

        self.y = random.uniform(
            -height,
            0
        )

        self.length = random.uniform(
            10,
            20
        )

        self.speed = random.uniform(
            RAIN_SPEED_MIN,
            RAIN_SPEED_MAX
        )

        self.alpha = 255

    def update(
        self,
        width,
        height
    ):

        self.y += self.speed

        if self.y > height:

            self.x = random.uniform(
                0,
                width
            )

            self.y = random.uniform(
                -self.length,
                0
            )

            self.length = random.uniform(
                10,
                20
            )

            self.speed = random.uniform(
                RAIN_SPEED_MIN,
                RAIN_SPEED_MAX
            )

            self.alpha = 255

        else:

            self.alpha = max(
                0,
                self.alpha - 2
            )


# ============================================================
# WINDOWS HELPERS
# ============================================================

def get_window_class(hwnd):

    if not hwnd:
        return ""

    try:

        buffer = (
            ctypes.create_unicode_buffer(
                256
            )
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

        placement = (
            ctypes.wintypes.WINDOWPLACEMENT()
        )

        placement.length = (
            ctypes.sizeof(
                placement
            )
        )

        result = (
            user32.GetWindowPlacement(
                hwnd,
                ctypes.byref(
                    placement
                )
            )
        )

        if result:

            # SW_MAXIMIZE
            return (
                placement.showCmd == 3
            )

    except Exception:

        pass

    return False


def get_active_window_rect():

    hwnd = (
        user32.GetForegroundWindow()
    )

    if not hwnd:
        return None

    if is_shell_window(hwnd):
        return None

    if is_window_minimized(hwnd):
        return None

    rect = (
        ctypes.wintypes.RECT()
    )

    try:

        result = (
            dwmapi.DwmGetWindowAttribute(
                hwnd,
                DWMWA_EXTENDED_FRAME_BOUNDS,
                ctypes.byref(rect),
                ctypes.sizeof(rect)
            )
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

        result = (
            user32.GetWindowRect(
                hwnd,
                ctypes.byref(rect)
            )
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

        hwnd = (
            user32.GetForegroundWindow()
        )

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

pygame.mixer.init()


def play_sound(sound_path):

    if not KEYBOARD_SOUNDS:
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

        if hasattr(
            key,
            "char"
        ):

            if key.char is not None:

                return (
                    key.char.upper()
                )

        key_map = {

            keyboard.Key.enter:
                "ENTER",

            keyboard.Key.space:
                "SPACE",

            keyboard.Key.backspace:
                "BACKSPACE",

            keyboard.Key.delete:
                "DELETE",

            keyboard.Key.tab:
                "TAB",

            keyboard.Key.esc:
                "ESC",

            keyboard.Key.shift:
                "SHIFT",

            keyboard.Key.shift_l:
                "SHIFT",

            keyboard.Key.shift_r:
                "SHIFT",

            keyboard.Key.ctrl:
                "CTRL",

            keyboard.Key.ctrl_l:
                "CTRL",

            keyboard.Key.ctrl_r:
                "CTRL",

            keyboard.Key.alt:
                "ALT",

            keyboard.Key.alt_l:
                "ALT",

            keyboard.Key.alt_r:
                "ALT",

            keyboard.Key.cmd:
                "WIN",

            keyboard.Key.cmd_l:
                "WIN",

            keyboard.Key.cmd_r:
                "WIN",

            keyboard.Key.caps_lock:
                "CAPSLOCK",

            keyboard.Key.up:
                "UP",

            keyboard.Key.down:
                "DOWN",

            keyboard.Key.left:
                "LEFT",

            keyboard.Key.right:
                "RIGHT",

            keyboard.Key.home:
                "HOME",

            keyboard.Key.end:
                "END",

            keyboard.Key.page_up:
                "PAGEUP",

            keyboard.Key.page_down:
                "PAGEDOWN",

            keyboard.Key.insert:
                "INSERT",
        }

        if key in key_map:

            return key_map[key]

        value = str(key)

        if value.startswith(
            "Key."
        ):

            return value[4:].upper()

        return value.upper()

    except Exception:

        return str(key).upper()


def keyboard_on_press(key):

    key_name = (
        get_key_name(key)
    )

    with held_keys_lock:

        if key_name in held_keys:
            return

        held_keys.add(
            key_name
        )

    keyboard_queue.put(
        (
            "press",
            key_name
        )
    )

    if not KEYBOARD_SOUNDS:
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

    key_name = (
        get_key_name(key)
    )

    with held_keys_lock:

        held_keys.discard(
            key_name
        )


def keyboard_listener_thread():

    global keyboard_listener

    try:

        keyboard_listener = (
            keyboard.Listener(
                on_press=keyboard_on_press,
                on_release=keyboard_on_release
            )
        )

        keyboard_listener.start()

        keyboard_listener.join()

    except Exception:

        pass


# ============================================================
# CURSOR PARTICLE
# ============================================================

class CursorParticle:

    def __init__(
        self,
        x,
        y
    ):

        self.x = x
        self.y = y

        self.max_life = (
            CURSOR_PARTICLE_LIFE
        )

        self.life = (
            self.max_life
        )

        self.size = random.uniform(
            1.2,
            3.5
        )

        self.velocity_x = (
            random.uniform(
                -1.2,
                1.2
            )
        )

        self.velocity_y = (
            random.uniform(
                -1.2,
                1.2
            )
        )

        self.alive = True

    def update(self):

        self.x += (
            self.velocity_x
        )

        self.y += (
            self.velocity_y
        )

        self.velocity_x *= 0.96

        self.velocity_y *= 0.96

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

        self.x = x
        self.y = y

        self.text = text

        self.max_life = (
            TYPING_PARTICLE_LIFE
        )

        self.life = (
            self.max_life
        )

        self.velocity_x = (
            random.uniform(
                -0.5,
                0.5
            )
        )

        self.velocity_y = (
            random.uniform(
                -1.5,
                -0.5
            )
        )

        self.alive = True

    def update(self):

        self.x += (
            self.velocity_x
        )

        self.y += (
            self.velocity_y
        )

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

        self.timer = QTimer(
            self
        )

        self.timer.timeout.connect(
            self.update_effects
        )

        self.timer.start(
            UPDATE_INTERVAL
        )

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

        screen = (
            QApplication.primaryScreen()
        )

        if screen is None:
            return

        geometry = (
            screen.virtualGeometry()
        )

        self.virtual_left = (
            geometry.left()
        )

        self.virtual_top = (
            geometry.top()
        )

        self.screen_width = (
            geometry.width()
        )

        self.screen_height = (
            geometry.height()
        )

        self.setGeometry(
            geometry
        )

    def setup_rain(self):

        self.rain_drops.clear()

        for _ in range(
            RAIN_AMOUNT
        ):

            self.rain_drops.append(

                RainDrop(
                    self.screen_width,
                    self.screen_height
                )
            )

    def make_click_through(self):

        try:

            hwnd = int(
                self.winId()
            )

            current_style = (
                user32.GetWindowLongW(
                    hwnd,
                    GWL_EXSTYLE
                )
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

        mouse_pos = (
            QCursor.pos()
        )

        cursor_x = mouse_pos.x()

        cursor_y = mouse_pos.y()

        # Cursor Trail
        if CURSOR_TRAIL:

            local_x = (
                cursor_x
                -
                self.virtual_left
            )

            local_y = (
                cursor_y
                -
                self.virtual_top
            )

            self.cursor_particles.append(

                CursorParticle(
                    local_x,
                    local_y
                )
            )

            if len(
                self.cursor_particles
            ) > 80:

                self.cursor_particles = (
                    self.cursor_particles[-80:]
                )

        # Keyboard
        while True:

            try:

                event_type, key_name = (
                    keyboard_queue.get_nowait()
                )

            except queue.Empty:

                break

            if event_type != "press":
                continue

            if not TYPING_EFFECT:
                continue

            x = (
                cursor_x
                -
                self.virtual_left
            )

            y = (
                cursor_y
                -
                self.virtual_top
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

        # Cursor particles
        for particle in (
            self.cursor_particles
        ):

            particle.update()

        self.cursor_particles = [

            particle

            for particle
            in self.cursor_particles

            if particle.alive
        ]

        # Typing particles
        for particle in (
            self.typing_particles
        ):

            particle.update()

        self.typing_particles = [

            particle

            for particle
            in self.typing_particles

            if particle.alive
        ]

        # Rain
        if RAIN_EFFECT:

            for drop in (
                self.rain_drops
            ):

                drop.update(
                    self.screen_width,
                    self.screen_height
                )

        self.update()

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

        if (
            RAIN_EFFECT
            and desktop_is_visible()
        ):

            for drop in (
                self.rain_drops
            ):

                pen = QPen(

                    QColor(
                        255,
                        150,
                        220,
                        drop.alpha
                    )
                )

                pen.setWidthF(
                    1.2
                )

                painter.setPen(
                    pen
                )

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

        if CURSOR_GLOW:

            local_x = (
                cursor_x
                -
                self.virtual_left
            )

            local_y = (
                cursor_y
                -
                self.virtual_top
            )

            for radius in range(
                35,
                3,
                -4
            ):

                alpha = min(

                    40,

                    int(
                        2
                        +
                        (
                            35 - radius
                        )
                        * 0.7
                    )
                )

                painter.setPen(
                    Qt.PenStyle.NoPen
                )

                painter.setBrush(

                    QColor(
                        PINK.red(),
                        PINK.green(),
                        PINK.blue(),
                        alpha
                    )
                )

                painter.drawEllipse(

                    QPointF(
                        local_x,
                        local_y
                    ),

                    radius,
                    radius
                )

        # ====================================================
        # CURSOR PARTICLES
        # ====================================================

        for particle in (
            self.cursor_particles
        ):

            alpha = int(

                255
                *
                (
                    particle.life
                    /
                    particle.max_life
                )
            )

            painter.setPen(
                Qt.PenStyle.NoPen
            )

            painter.setBrush(

                QColor(
                    PINK.red(),
                    PINK.green(),
                    PINK.blue(),
                    alpha
                )
            )

            painter.drawEllipse(

                QPointF(
                    particle.x,
                    particle.y
                ),

                particle.size,
                particle.size
            )

        # ====================================================
        # TYPING
        # ====================================================

        for particle in (
            self.typing_particles
        ):

            alpha = int(

                255
                *
                (
                    particle.life
                    /
                    particle.max_life
                )
            )

            painter.setPen(

                QColor(
                    255,
                    170,
                    230,
                    alpha
                )
            )

            painter.setFont(

                QFont(
                    "Segoe UI",
                    14,
                    QFont.Weight.Bold
                )
            )

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

        if WINDOW_GLOW:

            hwnd = (
                user32.GetForegroundWindow()
            )

            if hwnd:

                window = (
                    get_active_window_rect()
                )

                if window:

                    left, top, right, bottom = (
                        window
                    )

                    maximized = (
                        is_window_maximized(
                            hwnd
                        )
                    )

                    local_left = (
                        left
                        -
                        self.virtual_left
                    )

                    local_top = (
                        top
                        -
                        self.virtual_top
                    )

                    local_right = (
                        right
                        -
                        self.virtual_left
                    )

                    local_bottom = (
                        bottom
                        -
                        self.virtual_top
                    )

                    width = (
                        local_right
                        -
                        local_left
                    )

                    height = (
                        local_bottom
                        -
                        local_top
                    )

                    if (
                        width > 0
                        and height > 0
                    ):

                        def create_path(
                            inset
                        ):

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

                            path = (
                                QPainterPath()
                            )

                            if maximized:

                                path.addRect(
                                    rect
                                )

                            else:

                                radius = max(

                                    0,

                                    WINDOW_CORNER_RADIUS
                                    -
                                    inset
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

                        for inset in range(
                            WINDOW_GLOW_RADIUS,
                            0,
                            -2
                        ):

                            outer = (
                                create_path(
                                    -inset
                                )
                            )

                            inner = (
                                create_path(
                                    -(inset - 2)
                                )
                            )

                            ring = (
                                outer.subtracted(
                                    inner
                                )
                            )

                            alpha = max(

                                2,

                                int(
                                    30
                                    *
                                    (
                                        1
                                        -
                                        inset
                                        /
                                        WINDOW_GLOW_RADIUS
                                    )
                                )
                            )

                            painter.setBrush(

                                QColor(
                                    PINK.red(),
                                    PINK.green(),
                                    PINK.blue(),
                                    alpha
                                )
                            )

                            painter.drawPath(
                                ring
                            )

                        # Main line

                        main_path = (
                            create_path(0)
                        )

                        pen = QPen(

                            QColor(
                                255,
                                125,
                                215,
                                180
                            )
                        )

                        pen.setWidthF(
                            1.5
                        )

                        painter.setPen(
                            pen
                        )

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

        super().__init__(
            parent
        )

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

        super().__init__(
            parent
        )

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

        self.setMinimumHeight(
            68
        )

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            16,
            10,
            16,
            10
        )

        layout.setSpacing(
            12
        )

        text_layout = QVBoxLayout()

        text_layout.setSpacing(
            2
        )

        title_label = QLabel(
            title
        )

        title_label.setStyleSheet("""
            color: #f5f0f7;
            font-size: 14px;
            font-weight: 600;
        """)

        description_label = QLabel(
            description
        )

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
# SETTINGS WINDOW
# ============================================================

class SettingsWindow(QWidget):

    def __init__(
        self,
        overlay
    ):

        super().__init__()

        self.overlay = overlay

        self.setWindowTitle(
            APP_NAME
        )

        self.setWindowIcon(
            QIcon(
                str(ICON_PATH)
            )
        )

        self.setFixedSize(
            470,
            600
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
    # UI
    # ========================================================

    def setup_ui(self):

        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            12,
            12,
            12,
            12
        )

        root.setSpacing(
            10
        )

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

        layout = QVBoxLayout(
            container
        )

        layout.setContentsMargins(
            24,
            22,
            24,
            20
        )

        layout.setSpacing(
            10
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

        layout.addLayout(
            header
        )

        # ====================================================
        # STATUS
        # ====================================================

        status = QLabel(
            "EFFECTS"
        )

        status.setStyleSheet("""
            color: #ff78d2;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 2px;
            margin-top: 10px;
        """)

        layout.addWidget(
            status
        )

        # ====================================================
        # EFFECTS
        # ====================================================

        layout.addWidget(

            EffectRow(

                "Keyboard Sounds",
                "Play a sound when a key is pressed.",
                KEYBOARD_SOUNDS,
                self.toggle_keyboard
            )
        )

        layout.addWidget(

            EffectRow(

                "Cursor Trail",
                "Particles follow your mouse cursor.",
                CURSOR_TRAIL,
                self.toggle_cursor_trail
            )
        )

        layout.addWidget(

            EffectRow(

                "Cursor Glow",
                "Soft pink glow around the cursor.",
                CURSOR_GLOW,
                self.toggle_cursor_glow
            )
        )

        layout.addWidget(

            EffectRow(

                "Window Glow",
                "Highlight the currently active window.",
                WINDOW_GLOW,
                self.toggle_window_glow
            )
        )

        layout.addWidget(

            EffectRow(

                "Rain Effect",
                "Animated rain particles on the desktop.",
                RAIN_EFFECT,
                self.toggle_rain
            )
        )

        layout.addWidget(

            EffectRow(

                "Typing Effect",
                "Floating symbols appear when typing.",
                TYPING_EFFECT,
                self.toggle_typing
            )
        )

        # ====================================================
        # SPACER
        # ====================================================

        layout.addItem(

            QSpacerItem(
                10,
                10,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding
            )
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

        layout.addLayout(
            footer
        )

    # ========================================================
    # TOGGLES
    # ========================================================

    def toggle_keyboard(
        self,
        value
    ):

        global KEYBOARD_SOUNDS

        KEYBOARD_SOUNDS = value

    def toggle_cursor_trail(
        self,
        value
    ):

        global CURSOR_TRAIL

        CURSOR_TRAIL = value

    def toggle_cursor_glow(
        self,
        value
    ):

        global CURSOR_GLOW

        CURSOR_GLOW = value

    def toggle_window_glow(
        self,
        value
    ):

        global WINDOW_GLOW

        WINDOW_GLOW = value

    def toggle_rain(
        self,
        value
    ):

        global RAIN_EFFECT

        RAIN_EFFECT = value

    def toggle_typing(
        self,
        value
    ):

        global TYPING_EFFECT

        TYPING_EFFECT = value

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
# TRAY APP
# ============================================================

class TrayApplication:

    def __init__(
        self,
        app,
        overlay
    ):

        self.app = app

        self.overlay = overlay

        self.window = (
            SettingsWindow(
                overlay
            )
        )

        self.tray = (
            QSystemTrayIcon()
        )

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
    # Global App Icon
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
    # Keyboard Listener
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
    # Start hidden
    # --------------------------------------------------------

    tray_app.window.hide()

    # --------------------------------------------------------
    # Event Loop
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
