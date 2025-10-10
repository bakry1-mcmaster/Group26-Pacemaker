# File: dcm_ui/register_dialog.py
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QLabel, QPushButton, QHBoxLayout
)
from PyQt5.QtCore import Qt

class RegisterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register User")
        self.setModal(True)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)

        self.lbl_info = QLabel(
            "Create a new account (max 10 users).\n"
            "Username must be unique and both passwords must match."
        )
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)

        self.ed_user = QLineEdit()
        self.ed_user.setPlaceholderText("Username")
        layout.addWidget(self.ed_user)

        self.ed_pw = QLineEdit()
        self.ed_pw.setPlaceholderText("Password")
        self.ed_pw.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.ed_pw)

        self.ed_pw2 = QLineEdit()
        self.ed_pw2.setPlaceholderText("Confirm Password")
        self.ed_pw2.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.ed_pw2)

        # Buttons
        row = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_ok = QPushButton("Register")
        self.btn_ok.setDefault(True)
        self.btn_ok.setEnabled(False)
        row.addWidget(self.btn_cancel)
        row.addStretch(1)
        row.addWidget(self.btn_ok)
        layout.addLayout(row)

        # Signals
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok.clicked.connect(self.accept)
        self.ed_user.textChanged.connect(self._check_inputs)
        self.ed_pw.textChanged.connect(self._check_inputs)
        self.ed_pw2.textChanged.connect(self._check_inputs)

    # --- helpers ---
    def _check_inputs(self):
        user = self.ed_user.text().strip()
        p1 = self.ed_pw.text()
        p2 = self.ed_pw2.text()
        # enable OK only if username not empty and passwords match
        ok = bool(user) and bool(p1) and (p1 == p2)
        self.btn_ok.setEnabled(ok)

    def values(self):
        """Return (username, password) tuple."""
        return self.ed_user.text().strip(), self.ed_pw.text()