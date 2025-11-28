"""Combined page: pacing mode selection + parameters with stable spacing.

This widget does not introspect ParametersPage's layout. Instead it
builds its own parameter rows (each in a dedicated QWidget container),
so hiding rows collapses space consistently across modes.
"""

import json
import os
from dataclasses import dataclass, asdict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator, QFont
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
    QDoubleSpinBox,
    QSpinBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QApplication,
)


PARAMS_FILE = "dcm_params.json"

PACEMAKER_MODES = [
    "Off",
    "AAT",
    "VVT",
    "AOO",
    "AAI",
    "VOO",
    "VVI",
    "VDD",
    "DOO",
    "DDI",
    "DDD",
    "AOOR",
    "AAIR",
    "VOOR",
    "VVIR",
    "VDDR",
    "DOOR",
    "DDIR",
    "DDDR",
]
# Index sent over telemetry as the mode code in FN_PARAMS when `_transmit_params` runs.
#   0=Off, 1=AAT, 2=VVT, 3=AOO, 4=AAI, 5=VOO, 6=VVI, 7=VDD, 8=DOO, 9=DDI, 10=DDD,
#   11=AOOR, 12=AAIR, 13=VOOR, 14=VVIR, 15=VDDR, 16=DOOR, 17=DDIR, 18=DDDR

AT_LEVELS = [
    "V-Low",
    "Low",
    "Med-Low",
    "Med",
    "Med-High",
    "High",
    "V-High",
]


@dataclass
class PacingParams:
    # Rates in bpm
    lrl_ppm: int = 60  # Lower Rate Limit
    url_ppm: int = 120  # Upper Rate Limit

    # Atrial (stored in millivolts for file compatibility)
    a_amp_mV: float = 3000.0
    a_pw_ms: int = 1  # 1-30 ms

    # Ventricular
    v_amp_mV: float = 3500.0
    v_pw_ms: int = 1

    # Refractory
    arp_ms: int = 250
    vrp_ms: int = 320

    # Sensing (V)
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
    fontPreferencesChanged = pyqtSignal(str, int)

    # Controls both mode selection and parameter editing; integrates with TelemetryService.

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModeParametersPage")
        base_font = self.font()
        self._font_family = base_font.family()
        self._font_size = base_font.pointSize() or 12

        # Mapping of mode selectors to the rows that should remain visible.
        # Only the radio-button set shown above is available in this widget.
        self.visible_by_mode = {
            "AOO":  ["LRL", "URL", "AA", "APW"],
            "AAI":  ["LRL", "URL", "AA", "APW", "AS", "ARP", "PVARP", "HYS", "RS"],
            "VOO":  ["LRL", "URL", "VA", "VPW"],
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
        self.telemetry = None
        self.current_mode = "AAI"
        self._build_ui()
        self._wire()
        self._select_default_mode()

    # --- UI ---
    def _build_ui(self):
        # Build the full vertical layout with spacing that holds mode selectors, parameters, and actions.
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Mode radios row (only requested modes)
        self.rb_aoo  = QRadioButton("AOO")
        self.rb_aai  = QRadioButton("AAI")
        self.rb_voo  = QRadioButton("VOO")
        self.rb_vvi  = QRadioButton("VVI")
        self.rb_aoor = QRadioButton("AOOR")
        self.rb_voor = QRadioButton("VOOR")
        self.rb_aair = QRadioButton("AAIR")
        self.rb_vvir = QRadioButton("VVIR")
        self.rb_ddd  = QRadioButton("DDD")
        self.rb_dddr = QRadioButton("DDDR")
        self.mode_group = QButtonGroup(self)
        for rb in (
            self.rb_aoo,
            self.rb_aai,
            self.rb_voo,
            self.rb_vvi,
            self.rb_aoor,
            self.rb_voor,
            self.rb_aair,
            self.rb_vvir,
            self.rb_ddd,
            self.rb_dddr,
        ):
            self.mode_group.addButton(rb)
            rb.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        mode_row = QHBoxLayout()
        # Group all radio buttons on a single row so modes stay visible.
        mode_row.addWidget(self.rb_aoo)
        mode_row.addWidget(self.rb_aai)
        mode_row.addWidget(self.rb_voo)
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

        self.ed_a_amp = self._create_amp_spinbox(self.params.a_amp_mV)

        self.ed_a_pw = self._create_pulse_width_spinbox(self.params.a_pw_ms)

        self.ed_v_amp = self._create_amp_spinbox(self.params.v_amp_mV)

        self.ed_v_pw = self._create_pulse_width_spinbox(self.params.v_pw_ms)

        self.ed_arp = QLineEdit(str(self.params.arp_ms))
        self.ed_arp.setValidator(QIntValidator(150, 500, self))

        self.ed_vrp = QLineEdit(str(self.params.vrp_ms))
        self.ed_vrp.setValidator(QIntValidator(150, 500, self))

        # Additional sensing
        self.ed_as_mv = self._create_sensitivity_spinbox(self.params.a_sense_mV)
        self.ed_vs_mv = self._create_sensitivity_spinbox(self.params.v_sense_mV)

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
        for t in AT_LEVELS:
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
            # Helper that pairs a label with an input widget and keeps layout consistent.
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
            "AA": make_row("Atrial Amplitude (V)", self.ed_a_amp),
            "APW": make_row("Atrial Pulse Width (ms)", self.ed_a_pw),
            "VA": make_row("Ventricular Amplitude (V)", self.ed_v_amp),
            "VPW": make_row("Ventricular Pulse Width (ms)", self.ed_v_pw),
            "ARP": make_row("ARP (ms)", self.ed_arp),
            "VRP": make_row("VRP (ms)", self.ed_vrp),
            "AS": make_row("Atrial Sensitivity (V)", self.ed_as_mv),
            "VS": make_row("Ventricular Sensitivity (V)", self.ed_vs_mv),
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

        # Buttons row (actions applying or resetting parameters)
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

    def _create_amp_spinbox(self, stored_mV: float) -> QDoubleSpinBox:
        # Normalize stored millivolt value into 0-5 V steps for display.
        spin = QDoubleSpinBox(self)
        spin.setDecimals(1)
        spin.setRange(0.0, 5.0)
        spin.setSingleStep(0.1)
        spin.setKeyboardTracking(False)
        spin.setSpecialValueText("Reg Off")
        spin.setValue(self._mv_to_v(stored_mV))
        return spin

    def _create_pulse_width_spinbox(self, stored_ms: float) -> QSpinBox:
        # Render pulse width between 1 and 30 ms using standard integer spinbox.
        spin = QSpinBox(self)
        spin.setRange(1, 30)
        spin.setSingleStep(1)
        spin.setValue(self._clamp_int(stored_ms, 1, 30))
        return spin

    def _create_sensitivity_spinbox(self, stored_v: float) -> QDoubleSpinBox:
        # Sensitivity editor constrained to the 0.0-5.0 V range the device expects.
        spin = QDoubleSpinBox(self)
        spin.setDecimals(1)
        spin.setRange(0.0, 5.0)
        spin.setSingleStep(0.1)
        spin.setKeyboardTracking(False)
        spin.setValue(self._clamp_float(stored_v, 0.0, 5.0))
        return spin

    def open_accessibility_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Accessibility")
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Interface Font:", dialog))
        font_combo = QFontComboBox(dialog)
        font_combo.setCurrentFont(QFont(self._font_family, self._font_size))
        layout.addWidget(font_combo)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Font Size:", dialog))
        size_spin = QSpinBox(dialog)
        size_spin.setRange(8, 32)
        size_spin.setValue(self._font_size)
        size_row.addWidget(size_spin)
        size_row.addStretch(1)
        layout.addLayout(size_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        layout.addWidget(buttons)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec_() == QDialog.Accepted:
            self._apply_font_preferences(font_combo.currentFont().family(), size_spin.value())

    def _apply_font_preferences(self, family: str = None, size: int = None):
        if family is not None:
            self._font_family = family
        if size is not None:
            self._font_size = size
        font = QFont(self._font_family)
        font.setPointSize(int(self._font_size))
        self.setFont(font)
        self.fontPreferencesChanged.emit(self._font_family, self._font_size)

    def _wire(self):
        # Connect UI widgets to callbacks that keep the model/status updated.
        self.mode_group.buttonClicked.connect(lambda btn: self.update_visible_params(btn.text()))

        inputs = (
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
        )
        for w in inputs:
            if isinstance(w, QLineEdit):
                w.textChanged.connect(self._clear_status)
            else:
                w.valueChanged.connect(self._clear_status)

        self.btn_save.clicked.connect(self._save)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_back.clicked.connect(self.goHome.emit)
        self._apply_font_preferences()

    def setTelemetry(self, telemetry):
        # Store reference to TelemetryService so `_transmit_params` can push frames.
        self.telemetry = telemetry

    # --- Behavior ---
    def _select_default_mode(self):
        # Default to AAI mode so the widget always shows a valid configuration on open.
        self.rb_aai.setChecked(True)
        self.update_visible_params("AAI")

    def update_visible_params(self, mode: str):
        self.current_mode = mode
        allowed = set(self.visible_by_mode.get(mode, []))
        for key, row in self.row_widgets.items():
            row.setVisible(key in allowed)
        self.adjustSize()
        self.updateGeometry()

    def _clear_status(self):
        if hasattr(self, "lbl_status"):
            self.lbl_status.clear()

    @staticmethod
    def _mv_to_v(value: float) -> float:
        try:
            mv = float(value)
        except (TypeError, ValueError):
            return 0.0
        return round(max(0.0, min(5000.0, mv)) / 1000.0, 1)

    @staticmethod
    def _v_to_mv(value: float) -> int:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return 0
        return int(round(max(0.0, min(5.0, v)) * 1000))

    @staticmethod
    def _clamp_int(value, minimum: int, maximum: int) -> int:
        try:
            v = int(round(float(value)))
        except (TypeError, ValueError):
            return minimum
        return max(minimum, min(maximum, v))

    @staticmethod
    def _clamp_float(value, minimum: float, maximum: float) -> float:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return minimum
        return max(minimum, min(maximum, v))

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
        # Push the current widget values into the PacingParams dataclass before saving.
        self.params.lrl_ppm = int(self.ed_lrl.text())
        self.params.url_ppm = int(self.ed_url.text())
        self.params.a_amp_mV = self._v_to_mv(self.ed_a_amp.value())
        self.params.a_pw_ms = int(self.ed_a_pw.value())
        self.params.v_amp_mV = self._v_to_mv(self.ed_v_amp.value())
        self.params.v_pw_ms = int(self.ed_v_pw.value())
        self.params.arp_ms = int(self.ed_arp.text())
        self.params.vrp_ms = int(self.ed_vrp.text())
        # New
        self.params.a_sense_mV = float(self.ed_as_mv.value())
        self.params.v_sense_mV = float(self.ed_vs_mv.value())
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

    def _transmit_params(self):
        # Build and send the FN_PARAMS frame with the latest pacing parameters.
        if not self.telemetry:
            return
        try:
            lrl = max(1, int(self.ed_lrl.text()))
        except ValueError:
            lrl = 60
        lowrate_interval = int(round(60000 / lrl))
        try:
            mode_code = PACEMAKER_MODES.index(self.current_mode)
        except ValueError:
            mode_code = PACEMAKER_MODES.index("AAI")
        at_level = self.params.at_level if self.params.at_level in AT_LEVELS else AT_LEVELS[0]
        a_sense_mV = int(round(self.params.a_sense_mV * 1000))
        v_sense_mV = int(round(self.params.v_sense_mV * 1000))
        payload = {
            "pacing_state": 0,  # PERMANENT
            "mode": mode_code,
            "hysteresis": self.params.hys_on,
            "hysteresis_interval": self.params.pvarp_ms,
            "lowrate_interval": lowrate_interval,
            "lrl_ppm": self.params.lrl_ppm,
            "url_ppm": self.params.url_ppm,
            "a_amp_mV": self.params.a_amp_mV,
            "a_pw_ms": self.params.a_pw_ms,
            "v_amp_mV": self.params.v_amp_mV,
            "v_pw_ms": self.params.v_pw_ms,
            "arp_ms": self.params.arp_ms,
            "vrp_ms": self.params.vrp_ms,
            "a_sense_mV": a_sense_mV,
            "v_sense_mV": v_sense_mV,
            "pvarp_ms": self.params.pvarp_ms,
            "pvarp_ext_ms": self.params.pvarp_ext_ms,
            "rs_percent": self.params.rs_percent,
            "msr_bpm": self.params.msr_bpm,
            "at_level_code": AT_LEVELS.index(at_level),
            "react_time_s": self.params.react_time_s,
            "response_factor": self.params.response_factor,
            "recovery_time_min": self.params.recovery_time_min,
            "favd_ms": self.params.favd_ms,
            "davd_ms": self.params.davd_ms,
            "savd_ms": self.params.savd_ms,
        }
        self.telemetry.send_params(payload)
        self.telemetry.request_echo()

    def _reset(self):
        # Restore hardcoded defaults and reflect immediately in the UI.
        self.params = PacingParams()
        self._refresh_fields()
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("Defaults restored.")

    def _refresh_fields(self):
        # Update all widgets from the current `self.params` snapshot.
        self.ed_lrl.setText(str(self.params.lrl_ppm))
        self.ed_url.setText(str(self.params.url_ppm))
        self.ed_a_amp.setValue(self._mv_to_v(self.params.a_amp_mV))
        self.ed_a_pw.setValue(self._clamp_int(self.params.a_pw_ms, 1, 30))
        self.ed_v_amp.setValue(self._mv_to_v(self.params.v_amp_mV))
        self.ed_v_pw.setValue(self._clamp_int(self.params.v_pw_ms, 1, 30))
        self.ed_arp.setText(str(self.params.arp_ms))
        self.ed_vrp.setText(str(self.params.vrp_ms))
        # New
        self.ed_as_mv.setValue(self._clamp_float(self.params.a_sense_mV, 0.0, 5.0))
        self.ed_vs_mv.setValue(self._clamp_float(self.params.v_sense_mV, 0.0, 5.0))
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
        # Quick validation ensures each field stays within allowed numeric ranges.
        def ok_line(w):
            if not isinstance(w, QLineEdit):
                return True
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
            # Persisted to disk, now push to the pacemaker hardware over UART.
            self._transmit_params()
        except Exception:
            pass
