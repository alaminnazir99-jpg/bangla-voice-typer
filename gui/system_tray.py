"""System tray integration for Bangla VoiceTyper.

Provides the tray icon with a context menu for quick access
to toggle recording, show window, and quit.
"""

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class SystemTray(QSystemTrayIcon):
    """System tray icon wrapper."""

    toggle_requested = pyqtSignal()
    show_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, accent_color: str = "#00bcd4", parent=None):
        super().__init__(self._create_icon(accent_color), parent)
        self.setToolTip("Bangla VoiceTyper")
        self._build_menu()

    def _build_menu(self) -> None:
        """Build the tray context menu."""
        self._menu = QMenu()

        toggle_action = self._menu.addAction("রেকর্ড স্টার্ট/স্টপ (Ctrl+Shift+B)")
        toggle_action.triggered.connect(self.toggle_requested.emit)

        self._menu.addSeparator()

        show_action = self._menu.addAction("প্রদর্শন করুন")
        show_action.triggered.connect(self.show_requested.emit)

        self._menu.addSeparator()

        quit_action = self._menu.addAction("প্রস্থান")
        quit_action.triggered.connect(self.quit_requested.emit)

        self.setContextMenu(self._menu)

    def _create_icon(self, accent_color: str) -> QIcon:
        """Create a microphone icon programmatically."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        accent = QColor(accent_color)
        painter.setBrush(QBrush(accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(8, 4, 48, 56, 10, 10)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(24, 12, 16, 30, 6, 6)
        painter.drawEllipse(24, 44, 16, 6)
        painter.end()

        return QIcon(pixmap)
