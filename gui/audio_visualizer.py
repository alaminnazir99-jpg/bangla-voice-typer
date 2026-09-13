"""Real-time audio level visualizer widget.

Displays the current microphone input level as a
colorful animated bar.
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont
from PyQt6.QtWidgets import QWidget


class AudioVisualizer(QWidget):
    """Widget that shows the real-time audio input level."""

    def __init__(self, parent=None, accent_color="#00bcd4"):
        super().__init__(parent)
        self.accent_color = accent_color
        self.level = 0.0  # 0.0 to 1.0
        self.state = "idle"  # idle, listening, processing, error
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._decay)
        self._timer.start(50)
        self.setMinimumHeight(60)
        self.setMaximumHeight(120)

    def set_level(self, value: float) -> None:
        """Set current audio level (0.0 to 1.0)."""
        self.level = max(0.0, min(1.0, value))

    def set_state(self, state: str) -> None:
        """Set visualizer state: idle, listening, processing, error."""
        self.state = state
        self.update()

    def _decay(self) -> None:
        """Slowly decay the level when not receiving new data."""
        if self.state != "listening":
            self.level = max(0.0, self.level - 0.02)
        if self.level > 0:
            self.update()

    def _get_state_color(self) -> QColor:
        colors = {
            "idle": QColor("#555555"),
            "listening": QColor(self.accent_color),
            "processing": QColor("#FFC107"),
            "error": QColor("#F44336"),
            "success": QColor("#4CAF50"),
        }
        if self.state in colors:
            c = colors[self.state]
        else:
            c = QColor("#555555")
        return c

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        bar_h = 6
        center_y = h - bar_h - 10

        # Background
        bg_color = QColor("#2d2d2d")
        painter.fillRect(0, 0, w, h, bg_color)

        # Draw idle baseline bar
        baseline = QColor("#3a3a3a")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(baseline)
        painter.drawRoundedRect(10, center_y, w - 20, bar_h, 3, 3)

        # Draw active level bar
        active_width = int((w - 20) * self.level)
        if active_width > 0:
            state_color = self._get_state_color()
            gradient = QLinearGradient(10, 0, w - 10, 0)
            gradient.setColorAt(0.0, state_color.darker(150))
            gradient.setColorAt(1.0, state_color)
            painter.setBrush(gradient)
            painter.drawRoundedRect(
                10, center_y, active_width, bar_h, 3, 3
            )

        # Draw level number
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor("#aaaaaa"))
        text = f"{int(self.level * 100)}%"
        painter.drawText(10, center_y - 6, text)

        # Draw state label
        state_texts = {
            "idle": "প্রস্তুত",
            "listening": "শুনছি...",
            "processing": "প্রসেস হচ্ছে...",
            "error": "ত্রুটি",
        }
        if self.state in state_texts:
            label = state_texts[self.state]
            painter.setPen(self._get_state_color())
            painter.drawText(
                w - 100, center_y - 6,
                90, 20,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
