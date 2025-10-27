from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal


class TelemetryState:
    DISCONNECTED = "Disconnected"
    CONNECTED = "Connected"
    OUT_OF_RANGE = "Out of Range"
    NOISE = "Noise Detected"
    DIFFERENT_DEVICE = "Different Device"


@dataclass
class TelemetryStatus:
    state: str
    device_id: Optional[str] = None
    note: Optional[str] = None


class TelemetryService(QObject):
    """Stub telemetry service for D1.

    Emits high-level state changes; no real hardware I/O.
    """

    stateChanged = pyqtSignal(str, object, object)  # state, device_id, note

    def __init__(self):
        super().__init__()
        self._last_device_id: Optional[str] = None
        self._device_id: Optional[str] = None
        self._state: str = TelemetryState.DISCONNECTED

    def status(self) -> TelemetryStatus:
        return TelemetryStatus(self._state, self._device_id)

    def _emit(self, state: str, note: Optional[str] = None):
        self._state = state
        self.stateChanged.emit(self._state, self._device_id, note)

    # Session controls
    def start_session(self, device_id: str):
        self._device_id = device_id
        if self._last_device_id and self._last_device_id != device_id:
            self._emit(TelemetryState.DIFFERENT_DEVICE, note="Approached device differs from previously interrogated.")
        else:
            self._emit(TelemetryState.CONNECTED)

    def end_session(self):
        # Remember last device for comparison next time
        self._last_device_id = self._device_id
        self._device_id = None
        self._emit(TelemetryState.DISCONNECTED)

    # Simulated conditions
    def set_out_of_range(self, is_out: bool):
        if self._device_id is None:
            return
        self._emit(TelemetryState.OUT_OF_RANGE if is_out else TelemetryState.CONNECTED)

    def set_noise(self, is_noisy: bool):
        if self._device_id is None:
            return
        self._emit(TelemetryState.NOISE if is_noisy else TelemetryState.CONNECTED)

