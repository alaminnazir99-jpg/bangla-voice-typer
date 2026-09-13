"""License key activation dialog.

Shown on startup when the app has no valid license. The app will not
start voice typing until a valid key is entered.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from core.license import validate


class ActivationDialog(QDialog):
    """Enter a license key; on success exposes ``accepted_key``."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bangla VoiceTyper - লাইসেন্স সক্রিয়করণ")
        self.setFixedWidth(440)
        self.setModal(True)
        self.accepted_key = ""

        self.setStyleSheet(
            "QLabel { color: #e0e0e0; font-size: 12px; }"
            "QLineEdit {"
            "  background: #ffffff; color: #111111; font-size: 16px;"
            "  border: 1px solid #546e7a; border-radius: 6px;"
            "  padding: 8px; font-family: Consolas;"
            "}"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Bangla VoiceTyper")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #00bcd4;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        info = QLabel(
            "এই সফটওয়্যার ব্যবহার করতে একটি বৈধ লাইসেন্স কি প্রয়োজন।\n"
            "এক্টিভেশন কি দরকার ডেভলপারের কাছ থেকে সংগ্রহ করুন।"
        )
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setWordWrap(True)
        layout.addWidget(info)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.key_input.setMaxLength(19)
        self.key_input.returnPressed.connect(self._activate)
        layout.addWidget(self.key_input)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #e53935; font-size: 12px;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        activate_btn = QPushButton("সক্রিয় করুন")
        activate_btn.setStyleSheet(
            "QPushButton {"
            "  background: #00bcd4; color: #ffffff; font-weight: bold;"
            "  border: none; border-radius: 6px; padding: 8px 18px;"
            "}"
            "QPushButton:hover { background: #26c6da; }"
        )
        activate_btn.clicked.connect(self._activate)
        btn_row.addWidget(activate_btn)

        cancel_btn = QPushButton("বন্ধ করুন")
        cancel_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: #90a4ae; font-weight: bold;"
            "  border: 1px solid #546e7a; border-radius: 6px; padding: 8px 18px;"
            "}"
            "QPushButton:hover { background: #263238; color: #ffffff; }"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _activate(self):
        key = self.key_input.text().strip()
        if validate(key):
            self.accepted_key = key
            self.accept()
        else:
            self.error_label.setText("কি টি বৈধ নয়। সঠিক কি দিয়ে চেষ্টা করুন।")


def request_activation(parent=None) -> str:
    """Show the activation dialog; return the accepted key or '' if closed."""
    dlg = ActivationDialog(parent)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.accepted_key
    return ""