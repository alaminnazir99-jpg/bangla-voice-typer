"""Splash screen shown briefly at every app launch.

Displays the developer name and contact info for a couple of seconds in a
small frameless window, then disappears automatically.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


def _wa_link_url(number: str) -> str:
    """Build a wa.me link from a phone number.

    Handles local-style Bangladeshi numbers (e.g. 01796431795) by adding
    the +880 country code automatically.
    """
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    if not digits:
        return ""
    if digits.startswith("880") and len(digits) == 13:
        return "https://wa.me/" + digits
    if digits.startswith("0"):
        return "https://wa.me/" + "880" + digits[1:]
    return "https://wa.me/" + digits


class SplashScreen(QWidget):
    """Frameless, centered splash shown for ~2.5 seconds."""

    def __init__(self, settings, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(380, 232)

        self.setStyleSheet(
            "QWidget#panel {"
            "  background: #12121f; border: 1px solid #00bcd4;"
            "  border-radius: 16px;"
            "}"
        )

        name = settings.get("app", "name", "Bangla VoiceTyper")
        version = settings.get("app", "version", "1.0.0")
        about = settings.get_section("about") or {}
        developer = about.get("developer") or ""
        whatsapp = about.get("whatsapp") or ""
        facebook = about.get("facebook") or ""

        panel = QWidget(self)
        panel.setObjectName("panel")
        panel.setGeometry(0, 0, 380, 232)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(8)

        title = QLabel(name)
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #00bcd4; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel(f"সংস্করণ {version}")
        sub.setFont(QFont("Segoe UI", 11))
        sub.setStyleSheet("color: #90a4ae; background: transparent;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(6)

        dev_lbl = QLabel(developer)
        dev_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        dev_lbl.setStyleSheet("color: #ffffff; background: transparent;")
        dev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dev_lbl.setWordWrap(True)
        layout.addWidget(dev_lbl)

        link_style = 'color: #80cbc4; text-decoration: none; font-size: 12px;'

        # WhatsApp - clickable, opens wa.me in the browser.
        if whatsapp:
            wa_link = _wa_link_url(whatsapp)
            wa_lbl = QLabel(
                f'<a style="{link_style}" href="{wa_link}">'
                f'WhatsApp: {whatsapp}</a>'
            )
            wa_lbl.setOpenExternalLinks(True)
            wa_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            wa_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
            layout.addWidget(wa_lbl)

        # Facebook - clickable, opens the profile page in the browser.
        if facebook:
            fb_lbl = QLabel(
                f'<a style="{link_style}" href="{facebook}">Facebook</a>'
            )
            fb_lbl.setOpenExternalLinks(True)
            fb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fb_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
            layout.addWidget(fb_lbl)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)

        # Center on primary screen.
        screen = self.screen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    def show_for(self, ms: int = 2500, on_finished=None):
        """Show the splash, then call ``on_finished`` after ``ms`` msec."""
        self.show()
        self.raise_()
        self.activateWindow()
        if on_finished is not None:
            self._timer.timeout.connect(on_finished)
        self._timer.start(ms)