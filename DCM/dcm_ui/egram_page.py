# dcm_ui/egram_page.py

from __future__ import annotations

from collections import deque
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QSizePolicy,
)

from dcm_core.telemetry import TelemetryService
import pyqtgraph as pg  # for plotting


class EgramPage(QWidget):
    goHome = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("EgramPage")

        self._telemetry: Optional[TelemetryService] = None

        self._max_samples = 1000
        self._atr_buf = deque(maxlen=self._max_samples)
        self._ven_buf = deque(maxlen=self._max_samples)

        self._build_ui()

        self._timer = QTimer(self)
        self._timer.setInterval(40)  # ~25 fps
        self._timer.timeout.connect(self._refresh_plot)
        self._timer.start()

    def setTelemetry(self, telemetry: TelemetryService):
        self._telemetry = telemetry
        telemetry.egramSampleReceived.connect(self._on_egram_sample)

    # --- UI ---
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Title
        title = QLabel("Egram Viewer")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        root.addWidget(title)

        # Channel selection
        chan_box = QGroupBox("Channels")
        chan_layout = QHBoxLayout(chan_box)

        self.rb_atrial = QRadioButton("Atrial")
        self.rb_ventricular = QRadioButton("Ventricular")
        self.rb_both = QRadioButton("Both")

        # default: ventricular
        self.rb_ventricular.setChecked(True)

        self.channel_group = QButtonGroup(self)
        for rb in (self.rb_atrial, self.rb_ventricular, self.rb_both):
            self.channel_group.addButton(rb)

        chan_layout.addWidget(self.rb_atrial)
        chan_layout.addWidget(self.rb_ventricular)
        chan_layout.addWidget(self.rb_both)
        chan_layout.addStretch(1)

        root.addWidget(chan_box)

        # Plot area
        plot_box = QGroupBox("Real-time Egram")
        plot_layout = QVBoxLayout(plot_box)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel("left", "Amplitude", units="mV")
        self.plot_widget.setLabel("bottom", "Sample")
        self.plot_widget.setYRange(-5000, 5000)

        self._atr_curve = self.plot_widget.plot(pen=pg.mkPen("r", width=1))
        self._ven_curve = self.plot_widget.plot(pen=pg.mkPen("b", width=1))

        plot_layout.addWidget(self.plot_widget)
        root.addWidget(plot_box, stretch=1)

        # Control row
        ctrl_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Egram")
        self.btn_stop = QPushButton("Stop Egram")
        self.btn_stop.setEnabled(False)

        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_stop)
        ctrl_row.addStretch(1)
        root.addLayout(ctrl_row)

        # Back button (same style as other pages)
        back_row = QHBoxLayout()
        back_row.addStretch(1)
        self.btn_back = QPushButton("Back to Dashboard")
        self.btn_back.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        back_row.addWidget(self.btn_back)
        back_row.addStretch(1)
        root.addLayout(back_row)

        # signals
        self.btn_back.clicked.connect(self.goHome.emit)
        self.btn_start.clicked.connect(self._start_egram)
        self.btn_stop.clicked.connect(self._stop_egram)


    # --- telemetry interaction ---
    def _start_egram(self):
        if not self._telemetry:
            return

        self._atr_buf.clear()
        self._ven_buf.clear()

        self._telemetry.request_egram()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def _stop_egram(self):
        if self._telemetry:
            self._telemetry.stop_egram()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _on_egram_sample(self, atr, atr_marker, ven, ven_marker):
        self._atr_buf.append(atr)
        self._ven_buf.append(ven)

    # --- plotting ---
    def _refresh_plot(self):
        if not self._ven_buf:
            return

        n = len(self._ven_buf)
        x = list(range(n))

        show_atrial = self.rb_atrial.isChecked() or self.rb_both.isChecked()
        show_vent = self.rb_ventricular.isChecked() or self.rb_both.isChecked()

        atr_vals = [a if isinstance(a, (int, float)) else 0 for a in self._atr_buf]
        ven_vals = [v if isinstance(v, (int, float)) else 0 for v in self._ven_buf]

        if show_atrial:
            self._atr_curve.setData(x, atr_vals)
        else:
            self._atr_curve.setData([], [])

        if show_vent:
            self._ven_curve.setData(x, ven_vals)
        else:
            self._ven_curve.setData([], [])
