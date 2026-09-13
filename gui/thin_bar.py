"""A thin single-line floating bar (like the Bijoy keyboard bar).

Always stays on top in a corner of the screen with just two controls:
a record/stop button and a small settings button. This is the only window
the user needs to see; the app itself lives in the background + tray.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel


class ThinBar(QWidget):
    """Compact frameless, always-on-top vertical bar."""

    toggle_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedHeight(38)

        container = QWidget(self)
        container.setObjectName("container")
        container.setStyleSheet(
            "#container { background: #1a1a2e; border-radius: 8px; }"
            "QPushButton {"
            "  border: none; border-radius: 6px; background: #00bcd4;"
            "  color: #ffffff; font-size: 14px; font-weight: bold;"
            "  padding: 4px 12px;"
            "}"
            "QPushButton:hover { background: #26c6da; }"
            "QPushButton#settingsBtn {"
            "  background: transparent; color: #00bcd4; font-size: 16px;"
            "  padding: 2px 8px;"
            "}"
            "QPushButton#settingsBtn:hover { color: #ffffff; }"
            "QPushButton#recBtn.recording { background: #e53935; }"
            "QLabel { color: #ffffff; font-size: 12px; }"
        )

        layout = QHBoxLayout(container)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(6)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #9e9e9e; font-size: 10px;")
        layout.addWidget(self.status_dot)

        self.rec_btn = QPushButton("রেকর্ড শুরু")
        self.rec_btn.setObjectName("recBtn")
        self.rec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rec_btn.clicked.connect(self.toggle_requested.emit)
        layout.addWidget(self.rec_btn)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setObjectName("settingsBtn")
        self.settings_btn.setToolTip("সেটিংস")
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn)

        # Make the whole bar draggable by making it a widget the user can
        # move; we handle mouse presses to move the frameless window.
        self._drag_offset = None

        # Reposition to the top-right corner of the primary screen.
        screen = self.screen() or self.window().screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.right() - self.sizeHint().width() - 16, geo.top() + 16)
        container.resize(self.sizeHint())

    def set_recording_state(self, recording: bool) -> None:
        """Update the bar visuals to reflect the current state."""
        if recording:
            self.rec_btn.setText("রেকর্ড বন্ধ")
            self.rec_btn.setProperty("recording", "true")
            self.rec_btn.style().polish(self.rec_btn)
            self.status_dot.setStyleSheet("color: #e53935; font-size: 12px;")
            self.setToolTip("রেকর্ডিং চলছে... Ctrl+Shift+B দিয়ে বন্ধ করুন")
        else:
            self.rec_btn.setText("রেকর্ড শুরু")
            self.rec_btn.setProperty("recording", "false")
            self.rec_btn.style().polish(self.rec_btn)
            self.status_dot.setStyleSheet("color: #9e9e9e; font-size: 10px;")
            self.setToolTip("রেকর্ড শুরু করতে Ctrl+Shift+B চাপুন")

    # --- drag support for the frameless bar ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = None
        super().mouseReleaseEvent(event)