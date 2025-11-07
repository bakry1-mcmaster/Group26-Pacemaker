# 
# DEPRECIATED - moved to mode_parameters_page.py follwoing deliverable 1 feedback
# 

import json
import os
from dataclasses import dataclass, asdict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from PyQt5.QtWidgets import (
    QWidget,
    QFormLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
)

PARAMS_FILE = "dcm_params.json"


@dataclass
class PacingParams:
    # Rates in bpm
    lrl_bpm: int = 60  # Lower Rate Limit
    url_bpm: int = 120  # Upper Rate Limit

    # Atrial
    a_amp_mV: float = 3000.0 
    a_pw_ms: float = 0.4  # 0.1-1.9 ms

    # Ventricular
    v_amp_mV: float = 3500.0  # 500-7000 mV
    v_pw_ms: float = 0.4  # 0.1-1.9 ms

    # Refractory periods
    arp_ms: int = 250  # 150-500 ms
    vrp_ms: int = 320  # 150-500 ms


class ParametersPage(QWidget):
    """Collects and validates core D1 parameters and persists locally."""

    goHome = pyqtSignal()  # signal to go back to dashboard

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ParametersPage")

        self.params = self._load()

        self.form = QFormLayout()
        self.setLayout(QVBoxLayout())
        self.layout().addLayout(self.form)

        # --- Widgets ---
        self.ed_lrl = QLineEdit(str(self.params.lrl_bpm))
        self.ed_lrl.setValidator(QIntValidator(30, 175, self))
        self.form.addRow("Lower Rate Limit (bpm)", self.ed_lrl)

        self.ed_url = QLineEdit(str(self.params.url_bpm))
        self.ed_url.setValidator(QIntValidator(50, 175, self))
        self.form.addRow("Upper Rate Limit (bpm)", self.ed_url)

        # Atrial
        self.ed_a_amp = QLineEdit(str(self.params.a_amp_mV))
        self.ed_a_amp.setValidator(QDoubleValidator(500.0, 7000.0, 1, self))
        self.form.addRow("Atrial Amplitude (mV)", self.ed_a_amp)

        self.ed_a_pw = QLineEdit(str(self.params.a_pw_ms))
        self.ed_a_pw.setValidator(QDoubleValidator(0.1, 1.9, 2, self))
        self.form.addRow("Atrial Pulse Width (ms)", self.ed_a_pw)

        # Ventricular
        self.ed_v_amp = QLineEdit(str(self.params.v_amp_mV))
        self.ed_v_amp.setValidator(QDoubleValidator(500.0, 7000.0, 1, self))
        self.form.addRow("Ventricular Amplitude (mV)", self.ed_v_amp)

        self.ed_v_pw = QLineEdit(str(self.params.v_pw_ms))
        self.ed_v_pw.setValidator(QDoubleValidator(0.1, 1.9, 2, self))
        self.form.addRow("Ventricular Pulse Width (ms)", self.ed_v_pw)

        # Refractory
        self.ed_arp = QLineEdit(str(self.params.arp_ms))
        self.ed_arp.setValidator(QIntValidator(150, 500, self))
        self.form.addRow("ARP (ms)", self.ed_arp)

        self.ed_vrp = QLineEdit(str(self.params.vrp_ms))
        self.ed_vrp.setValidator(QIntValidator(150, 500, self))
        self.form.addRow("VRP (ms)", self.ed_vrp)

        # Computed labels
        self.lbl_lri = QLabel("")
        self.lbl_uri = QLabel("")
        self.form.addRow("Computed V-V Interval (LRI)", self.lbl_lri)
        self.form.addRow("Computed V-V Interval (URI)", self.lbl_uri)
        self._update_intervals()

        # Save / Reset buttons
        row = QHBoxLayout()
        self.btn_save = QPushButton("Save Parameters")
        self.btn_reset = QPushButton("Reset Defaults")
        row.addWidget(self.btn_reset)
        row.addStretch(1)
        row.addWidget(self.btn_save)
        self.layout().addLayout(row)

        # Status label
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#2a7; font-weight:500;")
        self.layout().addWidget(self.lbl_status)

        # Back button
        self.btn_back = QPushButton("Back to Dashboard")
        self.layout().addWidget(self.btn_back)

        self.layout().addStretch(1)

        # Signals
        for w in (
            self.ed_lrl,
            self.ed_url,
            self.ed_a_amp,
            self.ed_a_pw,
            self.ed_v_amp,
            self.ed_v_pw,
            self.ed_arp,
            self.ed_vrp,
        ):
            w.textChanged.connect(self._on_changed)

        self.btn_save.clicked.connect(self._save)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_back.clicked.connect(lambda: self.goHome.emit())  # emits signal

    # --- helpers ---
    def _load(self) -> PacingParams:
        if os.path.exists(PARAMS_FILE):
            try:
                with open(PARAMS_FILE, "r") as f:
                    data = json.load(f)
                return PacingParams(**data)
            except Exception:
                pass
        return PacingParams()

    def _save(self):
        if not self._validate_all(show_msg=True):
            return
        self._apply_to_model()
        try:
            with open(PARAMS_FILE, "w") as f:
                json.dump(asdict(self.params), f, indent=2)
            self.lbl_status.setText("Parameters saved")
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", str(e))

    def _reset(self):
        self.params = PacingParams()
        self._refresh_fields()
        self.lbl_status.setText("Defaults restored.")

    def _apply_to_model(self):
        self.params.lrl_bpm = int(self.ed_lrl.text())
        self.params.url_bpm = int(self.ed_url.text())
        self.params.a_amp_mV = float(self.ed_a_amp.text())
        self.params.a_pw_ms = float(self.ed_a_pw.text())
        self.params.v_amp_mV = float(self.ed_v_amp.text())
        self.params.v_pw_ms = float(self.ed_v_pw.text())
        self.params.arp_ms = int(self.ed_arp.text())
        self.params.vrp_ms = int(self.ed_vrp.text())

    def _refresh_fields(self):
        self.ed_lrl.setText(str(self.params.lrl_bpm))
        self.ed_url.setText(str(self.params.url_bpm))
        self.ed_a_amp.setText(str(self.params.a_amp_mV))
        self.ed_a_pw.setText(str(self.params.a_pw_ms))
        self.ed_v_amp.setText(str(self.params.v_amp_mV))
        self.ed_v_pw.setText(str(self.params.v_pw_ms))
        self.ed_arp.setText(str(self.params.arp_ms))
        self.ed_vrp.setText(str(self.params.vrp_ms))
        self._update_intervals()

    def _on_changed(self):
        self.lbl_status.clear()
        self._update_intervals()

    def _update_intervals(self):
        def to_ms(bpm_text: str):
            try:
                bpm = int(bpm_text)
                return int(round(60000.0 / bpm)) if bpm > 0 else 0
            except ValueError:
                return 0

        lri = to_ms(self.ed_lrl.text())
        uri = to_ms(self.ed_url.text())
        self.lbl_lri.setText(f"{lri} ms" if lri else "--")
        self.lbl_uri.setText(f"{uri} ms" if uri else "--")

    def _validate_all(self, show_msg: bool = False) -> bool:
        fields = [
            (self.ed_lrl, "LRL (30-175 bpm)"),
            (self.ed_url, "URL (50-175 bpm)"),
            (self.ed_a_amp, "Atrial Amplitude (500-7000 mV)"),
            (self.ed_a_pw, "Atrial PW (0.1-1.9 ms)"),
            (self.ed_v_amp, "Ventricular Amplitude (500-7000 mV)"),
            (self.ed_v_pw, "Ventricular PW (0.1-1.9 ms)"),
            (self.ed_arp, "ARP (150-500 ms)"),
            (self.ed_vrp, "VRP (150-500 ms)"),
        ]
        for w, name in fields:
            if not w.hasAcceptableInput():
                if show_msg:
                    QMessageBox.warning(self, "Invalid Input", f"Please correct: {name}")
                return False
        try:
            lrl = int(self.ed_lrl.text())
            url = int(self.ed_url.text())
            if lrl > url:
                if show_msg:
                    QMessageBox.warning(self, "Invalid Rates", "LRL must be <= URL.")
                return False
        except ValueError:
            if show_msg:
                QMessageBox.warning(self, "Invalid Rates", "Rates must be integers.")
            return False
        return True

