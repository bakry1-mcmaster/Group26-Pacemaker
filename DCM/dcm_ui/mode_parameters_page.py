"""Combined page: pacing mode selection + parameters with stable spacing.

This widget does not introspect ParametersPage's layout. Instead it
builds its own parameter rows (each in a dedicated QWidget container),
so hiding rows collapses space consistently across modes.
"""

import json
import os
from dataclasses import dataclass, asdict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator, QDoubleValidator
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QSizePolicy,
    QCheckBox,
    QComboBox,
)


PARAMS_FILE = "dcm_params.json"


@dataclass
class PacingParams:
    # Rates in bpm
    lrl_ppm: int = 60  # Lower Rate Limit
    url_ppm: int = 120  # Upper Rate Limit

    # Atrial
    a_amp_mV: float = 3000.0
    a_pw_ms: float = 0.4

    # Ventricular
    v_amp_mV: float = 3500.0
    v_pw_ms: float = 0.4

    # Refractory
    arp_ms: int = 250
    vrp_ms: int = 320

    # Sensing (mV)
    a_sense_mV: float = 2.5
    v_sense_mV: float = 2.5

    # Post-ventricular atrial refractory period
    pvarp_ms: int = 250
    pvarp_ext_ms: int = 0  # extension (rate-adaptive)

    # Hysteresis (enabled flag)
    hys_on: bool = False

    # Rate smoothing (0=Off; else allowed: 3..25 step 3)
    rs_percent: int = 0

    # Rate-adaptive parameters
    msr_bpm: int = 120
    at_level: str = "Med"  # Activity Threshold preset
    react_time_s: int = 30
    response_factor: int = 8
    recovery_time_min: int = 5

    # AV Delays (ms)
    favd_ms: int = 150
    davd_ms: int = 180
    savd_ms: int = 150


class ModeParametersPage(QWidget):
    goHome = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeParametersPage")

        # Mode → parameter keys (see Class documentation)
        # Supported selectable modes only: AAI, VVI, AOOR, VOOR, AAIR, VVIR, DDD, DDDR
        self.visible_by_mode = {
            "AAI":  ["LRL", "URL", "AA", "APW", "AS", "ARP", "PVARP", "HYS", "RS"],
            "VVI":  ["LRL", "URL", "VA", "VPW", "VS", "VRP", "HYS", "RS"],
            "AOOR": ["LRL", "URL", "MSR", "AA", "AS", "APW", "AT", "ReacT", "RF", "RespT"],
            "VOOR": ["LRL", "URL", "MSR", "VA", "VPW", "AT", "ReacT", "RF", "RespT"],
            "AAIR": ["LRL", "URL", "MSR", "AA", "APW", "AS", "ARP", "PVARP", "HYS", "RS", "AT", "ReacT", "RF", "RespT"],
            "VVIR": ["LRL", "URL", "MSR", "VA", "VPW", "VS", "VRP", "HYS", "RS", "AT", "ReacT", "RF", "RespT"],
            # Bonuses
            "DDD":  ["LRL", "URL", "FAVD", "DAVD", "SAVD", "AA", "APW", "AS", "ARP","VA", "VPW", "VS", "VRP", "PVARP", "PVARExt", "RS"],
            "DDDR": ["LRL", "URL", "MSR", "FAVD", "DAVD", "SAVD", "AA", "APW", "AS", "ARP", "VA", "VPW", "VS", "VRP", "PVARP", "PVARExt", "RS", "AT", "ReacT", "RF", "RespT"]
        }

        self.params = self._load()
        self._build_ui()
        self._wire()
        self._select_default_mode()

    # --- UI ---
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Mode radios row (only requested modes)
        self.rb_aai  = QRadioButton("AAI")
        self.rb_vvi  = QRadioButton("VVI")
        self.rb_aoor = QRadioButton("AOOR")
        self.rb_voor = QRadioButton("VOOR")
        self.rb_aair = QRadioButton("AAIR")
        self.rb_vvir = QRadioButton("VVIR")
        self.rb_ddd  = QRadioButton("DDD")
        self.rb_dddr = QRadioButton("DDDR")
        self.mode_group = QButtonGroup(self)
        for rb in (self.rb_aai, self.rb_vvi, self.rb_aoor, self.rb_voor, self.rb_aair, self.rb_vvir, self.rb_ddd, self.rb_dddr):
            self.mode_group.addButton(rb)
            rb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self.rb_aai)
        mode_row.addWidget(self.rb_vvi)
        mode_row.addWidget(self.rb_aoor)
        mode_row.addWidget(self.rb_voor)
        mode_row.addWidget(self.rb_aair)
        mode_row.addWidget(self.rb_vvir)
        mode_row.addWidget(self.rb_ddd)
        mode_row.addWidget(self.rb_dddr)
        mode_row.addStretch(1)
        root.addLayout(mode_row)

        # Parameter rows container
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(8)
        root.addLayout(self.rows_layout)

        # Build editor widgets
        self.ed_lrl = QLineEdit(str(self.params.lrl_ppm))
        self.ed_lrl.setValidator(QIntValidator(30, 175, self))

        self.ed_url = QLineEdit(str(self.params.url_ppm))
        self.ed_url.setValidator(QIntValidator(50, 175, self))

        self.ed_a_amp = QLineEdit(str(self.params.a_amp_mV))
        self.ed_a_amp.setValidator(QDoubleValidator(500.0, 7000.0, 1, self))

        self.ed_a_pw = QLineEdit(str(self.params.a_pw_ms))
        self.ed_a_pw.setValidator(QDoubleValidator(0.1, 1.9, 2, self))

        self.ed_v_amp = QLineEdit(str(self.params.v_amp_mV))
        self.ed_v_amp.setValidator(QDoubleValidator(500.0, 7000.0, 1, self))

        self.ed_v_pw = QLineEdit(str(self.params.v_pw_ms))
        self.ed_v_pw.setValidator(QDoubleValidator(0.1, 1.9, 2, self))

        self.ed_arp = QLineEdit(str(self.params.arp_ms))
        self.ed_arp.setValidator(QIntValidator(150, 500, self))

        self.ed_vrp = QLineEdit(str(self.params.vrp_ms))
        self.ed_vrp.setValidator(QIntValidator(150, 500, self))

        # Additional sensing
        self.ed_as_mv = QLineEdit(str(self.params.a_sense_mV))
        self.ed_as_mv.setValidator(QDoubleValidator(0.0, 5.0, 1, self))
        self.ed_vs_mv = QLineEdit(str(self.params.v_sense_mV))
        self.ed_vs_mv.setValidator(QDoubleValidator(0.0, 5.0, 1, self))

        # PVARP + extension
        self.ed_pvarp = QLineEdit(str(self.params.pvarp_ms))
        self.ed_pvarp.setValidator(QIntValidator(150, 500, self))
        self.ed_pvarext = QLineEdit(str(self.params.pvarp_ext_ms))
        self.ed_pvarext.setValidator(QIntValidator(0, 400, self))

        # Hysteresis
        self.cb_hys = QCheckBox("Enabled")
        self.cb_hys.setChecked(self.params.hys_on)

        # Rate smoothing
        self.cb_rs = QComboBox()
        self.cb_rs.addItem("Off", 0)
        for pct in (3, 6, 9, 12, 15, 18, 21, 25):
            self.cb_rs.addItem(f"{pct}%", pct)
        # Select from model value
        idx = max(0, self.cb_rs.findData(self.params.rs_percent))
        self.cb_rs.setCurrentIndex(idx)

        # Rate-adaptive
        self.ed_msr = QLineEdit(str(self.params.msr_bpm))
        self.ed_msr.setValidator(QIntValidator(50, 175, self))

        self.cb_at = QComboBox()
        at_choices = [
            "V-Low", "Low", "Med-Low", "Med", "Med-High", "High", "V-High",
        ]
        for t in at_choices:
            self.cb_at.addItem(t, t)
        at_index = max(0, self.cb_at.findData(self.params.at_level))
        self.cb_at.setCurrentIndex(at_index)

        self.ed_react = QLineEdit(str(self.params.react_time_s))
        self.ed_react.setValidator(QIntValidator(10, 50, self))

        self.ed_rf = QLineEdit(str(self.params.response_factor))
        self.ed_rf.setValidator(QIntValidator(1, 16, self))

        self.ed_respt = QLineEdit(str(self.params.recovery_time_min))
        self.ed_respt.setValidator(QIntValidator(2, 16, self))

        # AV delays
        self.ed_favd = QLineEdit(str(self.params.favd_ms))
        self.ed_favd.setValidator(QIntValidator(70, 300, self))
        self.ed_davd = QLineEdit(str(self.params.davd_ms))
        self.ed_davd.setValidator(QIntValidator(70, 300, self))
        self.ed_savd = QLineEdit(str(self.params.savd_ms))
        self.ed_savd.setValidator(QIntValidator(70, 300, self))

        # Row containers: key -> QWidget row with label+editor
        def make_row(label_text, editor):
            row = QWidget(self)
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)
            lbl = QLabel(label_text, row)
            h.addWidget(lbl)
            h.addWidget(editor, 1)
            return row

        self.row_widgets = {
            "LRL": make_row("Lower Rate Limit (ppm)", self.ed_lrl),
            "URL": make_row("Upper Rate Limit (ppm)", self.ed_url),
            "AA": make_row("Atrial Amplitude (mV)", self.ed_a_amp),
            "APW": make_row("Atrial Pulse Width (ms)", self.ed_a_pw),
            "VA": make_row("Ventricular Amplitude (mV)", self.ed_v_amp),
            "VPW": make_row("Ventricular Pulse Width (ms)", self.ed_v_pw),
            "ARP": make_row("ARP (ms)", self.ed_arp),
            "VRP": make_row("VRP (ms)", self.ed_vrp),
            "AS": make_row("Atrial Sensitivity (mV)", self.ed_as_mv),
            "VS": make_row("Ventricular Sensitivity (mV)", self.ed_vs_mv),
            "PVARP": make_row("PVARP (ms)", self.ed_pvarp),
            "PVARExt": make_row("PVARP Extension (ms)", self.ed_pvarext),
            "HYS": make_row("Hysteresis", self.cb_hys),
            "RS": make_row("Rate Smoothing (%)", self.cb_rs),
            "MSR": make_row("Max Sensor Rate (ppm)", self.ed_msr),
            "AT": make_row("Activity Threshold", self.cb_at),
            "ReacT": make_row("Reaction Time (s)", self.ed_react),
            "RF": make_row("Response Factor", self.ed_rf),
            "RespT": make_row("Recovery Time (min)", self.ed_respt),
            "FAVD": make_row("Fixed AV Delay (ms)", self.ed_favd),
            "DAVD": make_row("Dynamic AV Delay (ms)", self.ed_davd),
            "SAVD": make_row("Sensed AV Delay (ms)", self.ed_savd),
        }

        # Fixed order we will always use when (re)building the list
        self._row_order = [
            # Base
            "LRL", "URL", "AA", "APW", "VA", "VPW",
            # Sensing + refractory
            "AS", "VS", "ARP", "VRP", "PVARP", "PVARExt",
            # Enhancements
            "HYS", "RS",
            # Rate adaptive
            "MSR", "AT", "ReacT", "RF", "RespT",
            # AV delays
            "FAVD", "DAVD", "SAVD",
        ]

        # Add all rows initially (visibility handled by mode)
        for key in self._row_order:
            self.rows_layout.addWidget(self.row_widgets[key])

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_reset = QPushButton("Reset Defaults")
        self.btn_save = QPushButton("Save Parameters")
        btn_row.addWidget(self.btn_reset)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_save)
        root.addLayout(btn_row)

        # Inline status/confirmation label
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color:#2a7; font-weight:500;")
        root.addWidget(self.lbl_status)

        # Back button centered style (non-expanding)
        back_row = QHBoxLayout()
        back_row.addStretch(1)
        self.btn_back = QPushButton("Back to Dashboard")
        self.btn_back.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        back_row.addWidget(self.btn_back)
        back_row.addStretch(1)
        root.addLayout(back_row)

        root.addStretch(1)

    def _wire(self):
        for rb in (self.rb_aai, self.rb_vvi, self.rb_aoor, self.rb_voor, self.rb_aair, self.rb_vvir, self.rb_ddd, self.rb_dddr):
            rb.toggled.connect(lambda checked, m=rb.text(): checked and self.update_visible_params(m))

        for w in (
            self.ed_lrl,
            self.ed_url,
            self.ed_a_amp,
            self.ed_a_pw,
            self.ed_v_amp,
            self.ed_v_pw,
            self.ed_arp,
            self.ed_vrp,
            self.ed_as_mv,
            self.ed_vs_mv,
            self.ed_pvarp,
            self.ed_pvarext,
            self.ed_msr,
            self.ed_react,
            self.ed_rf,
            self.ed_respt,
            self.ed_favd,
            self.ed_davd,
            self.ed_savd,
        ):
            w.textChanged.connect(self._clear_status)

        self.btn_save.clicked.connect(self._save)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_back.clicked.connect(self.goHome.emit)

    # --- Behavior ---
    def _select_default_mode(self):
        self.rb_aai.setChecked(True)
        self.update_visible_params("AAI")

    def update_visible_params(self, mode: str):
        allowed = set(self.visible_by_mode.get(mode, []))
        for key, row in self.row_widgets.items():
            row.setVisible(key in allowed)
        self.adjustSize()
        self.updateGeometry()

    def _clear_status(self):
        if hasattr(self, "lbl_status"):
            self.lbl_status.clear()

    # --- Model IO ---
    def _load(self) -> PacingParams:
        if os.path.exists(PARAMS_FILE):
            try:
                with open(PARAMS_FILE, "r") as f:
                    data = json.load(f)
                return PacingParams(**data)
            except Exception:
                pass
        return PacingParams()

    def _apply_to_model(self):
        self.params.lrl_ppm = int(self.ed_lrl.text())
        self.params.url_ppm = int(self.ed_url.text())
        self.params.a_amp_mV = float(self.ed_a_amp.text())
        self.params.a_pw_ms = float(self.ed_a_pw.text())
        self.params.v_amp_mV = float(self.ed_v_amp.text())
        self.params.v_pw_ms = float(self.ed_v_pw.text())
        self.params.arp_ms = int(self.ed_arp.text())
        self.params.vrp_ms = int(self.ed_vrp.text())
        # New
        self.params.a_sense_mV = float(self.ed_as_mv.text())
        self.params.v_sense_mV = float(self.ed_vs_mv.text())
        self.params.pvarp_ms = int(self.ed_pvarp.text())
        self.params.pvarp_ext_ms = int(self.ed_pvarext.text())
        self.params.hys_on = bool(self.cb_hys.isChecked())
        self.params.rs_percent = int(self.cb_rs.currentData())
        self.params.msr_bpm = int(self.ed_msr.text())
        self.params.at_level = str(self.cb_at.currentData())
        self.params.react_time_s = int(self.ed_react.text())
        self.params.response_factor = int(self.ed_rf.text())
        self.params.recovery_time_min = int(self.ed_respt.text())
        self.params.favd_ms = int(self.ed_favd.text())
        self.params.davd_ms = int(self.ed_davd.text())
        self.params.savd_ms = int(self.ed_savd.text())

    def _reset(self):
        self.params = PacingParams()
        self._refresh_fields()
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("Defaults restored.")

    def _refresh_fields(self):
        self.ed_lrl.setText(str(self.params.lrl_ppm))
        self.ed_url.setText(str(self.params.url_ppm))
        self.ed_a_amp.setText(str(self.params.a_amp_mV))
        self.ed_a_pw.setText(str(self.params.a_pw_ms))
        self.ed_v_amp.setText(str(self.params.v_amp_mV))
        self.ed_v_pw.setText(str(self.params.v_pw_ms))
        self.ed_arp.setText(str(self.params.arp_ms))
        self.ed_vrp.setText(str(self.params.vrp_ms))
        # New
        self.ed_as_mv.setText(str(self.params.a_sense_mV))
        self.ed_vs_mv.setText(str(self.params.v_sense_mV))
        self.ed_pvarp.setText(str(self.params.pvarp_ms))
        self.ed_pvarext.setText(str(self.params.pvarp_ext_ms))
        self.cb_hys.setChecked(self.params.hys_on)
        idx = max(0, self.cb_rs.findData(self.params.rs_percent))
        self.cb_rs.setCurrentIndex(idx)
        self.ed_msr.setText(str(self.params.msr_bpm))
        idx_at = max(0, self.cb_at.findData(self.params.at_level))
        self.cb_at.setCurrentIndex(idx_at)
        self.ed_react.setText(str(self.params.react_time_s))
        self.ed_rf.setText(str(self.params.response_factor))
        self.ed_respt.setText(str(self.params.recovery_time_min))
        self.ed_favd.setText(str(self.params.favd_ms))
        self.ed_davd.setText(str(self.params.davd_ms))
        self.ed_savd.setText(str(self.params.savd_ms))

    def _validate_all(self) -> bool:
        def ok_line(w):
            v = w.validator()
            if v is None:
                return True
            s = w.text()
            pos = 0
            return v.validate(s, pos)[0] == v.Acceptable

        fields = [
            (self.ed_lrl, True),
            (self.ed_url, True),
            (self.ed_a_amp, True),
            (self.ed_a_pw, True),
            (self.ed_v_amp, True),
            (self.ed_v_pw, True),
            (self.ed_arp, True),
            (self.ed_vrp, True),
            (self.ed_as_mv, True),
            (self.ed_vs_mv, True),
            (self.ed_pvarp, True),
            (self.ed_pvarext, True),
            (self.ed_msr, True),
            (self.ed_react, True),
            (self.ed_rf, True),
            (self.ed_respt, True),
            (self.ed_favd, True),
            (self.ed_davd, True),
            (self.ed_savd, True),
        ]
        for w, _ in fields:
            if not ok_line(w):
                return False
        try:
            lrl = int(self.ed_lrl.text())
            url = int(self.ed_url.text())
            if lrl > url:
                return False
        except ValueError:
            return False
        return True

    def _save(self):
        if not self._validate_all():
            # Silent fail; validation UI could be added later
            return
        self._apply_to_model()
        try:
            with open(PARAMS_FILE, "w") as f:
                json.dump(asdict(self.params), f, indent=2)
            if hasattr(self, "lbl_status"):
                self.lbl_status.setText("Parameters saved.")
        except Exception:
            pass
