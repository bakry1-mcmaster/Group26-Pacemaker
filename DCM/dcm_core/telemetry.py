from __future__ import annotations

import struct

from dataclasses import dataclass
from typing import Optional
from threading import Thread, Event

from PyQt5.QtCore import QObject, pyqtSignal

EGRAM_FRAME_SIZE = 18 

try:
    import serial  # type: ignore
except ImportError:  # pragma: no cover
    serial = None


class TelemetryState:
    DISCONNECTED = "Disconnected"
    CONNECTED = "Connected"
    OUT_OF_RANGE = "Out of Range"
    NOISE = "Noise Detected"
    DIFFERENT_DEVICE = "Different Device"


SYNC = 0x16
SOH = 0x01

# Function codes (SRS Section 3.2)
FN_EGRAM = 0x47
FN_ECHO = 0x49
FN_ESTOP = 0x62
FN_PARAMS = 0x55


@dataclass
class TelemetryStatus:
    state: str
    device_id: Optional[str] = None
    note: Optional[str] = None


class TelemetryService(QObject):
    """Telemetry/UART service.

    Manages the wireless link state as well as the underlying UART connection to
    the pacemaker hardware (Deliverable 2 requirement).  When pyserial is not
    available the class gracefully degrades to the simulated states used in D1.
    """

    stateChanged = pyqtSignal(str, object, object)  # state, device_id, note
    serialConnected = pyqtSignal(str)
    serialDisconnected = pyqtSignal()
    serialError = pyqtSignal(str)
    rawDataReceived = pyqtSignal(bytes)

    #EGRAM
    egramSampleReceived = pyqtSignal(object, object, object, object)


    def __init__(self):
        super().__init__()
        self._last_device_id: Optional[str] = None
        self._device_id: Optional[str] = None
        self._state: str = TelemetryState.DISCONNECTED
        self._port: Optional[str] = None
        self._baudrate: int = 115200
        self._serial = None
        self._rx_thread: Optional[Thread] = None
        self._stop_event = Event()

        #EGRAM
        self._rx_buf = bytearray() #buffer to accumulate egram bytes
        self._egram_streaming = False

    def status(self) -> TelemetryStatus:
        return TelemetryStatus(self._state, self._device_id)

    def _emit(self, state: str, note: Optional[str] = None):
        self._state = state
        self.stateChanged.emit(self._state, self._device_id, note)

    # Session controls
    def configure_serial(self, port: Optional[str], baudrate: int = 115200):
        self._port = port
        self._baudrate = baudrate

    def connect_serial(self, port: Optional[str] = None, baudrate: Optional[int] = None) -> bool:
        if port:
            self._port = port
        if baudrate:
            self._baudrate = baudrate
        if serial is None:
            self.serialError.emit("pyserial is not installed.")
            return False
        if not self._port:
            self.serialError.emit("No UART port configured.")
            return False
        # Already connected?
        if self._serial and getattr(self._serial, "is_open", False):
            self.serialConnected.emit(self._port)
            return True
        try:
            self._serial = serial.Serial(self._port, self._baudrate, timeout=0.1)
        except Exception as exc:  # pragma: no cover - hardware specific
            self.serialError.emit(str(exc))
            self._serial = None
            return False
        self._stop_event.clear()
        self._rx_thread = Thread(target=self._read_loop, daemon=True)
        self._rx_thread.start()
        self.serialConnected.emit(self._port)
        self._emit(TelemetryState.CONNECTED)
        return True

    def disconnect_serial(self):
        self._stop_event.set()
        if self._rx_thread and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
        self._rx_thread = None
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
        self._serial = None
        self.serialDisconnected.emit()

    def send_packet(self, payload: bytes):
        if not payload:
            return
        if not self._serial or not getattr(self._serial, "is_open", False):
            self.serialError.emit("UART port not connected.")
            return
        try:
            self._serial.write(payload)
            self._serial.flush()
        except Exception as exc:  # pragma: no cover - hardware specific
            self.serialError.emit(f"UART write failed: {exc}")

    def _read_loop(self):  # pragma: no cover - hardware specific
        unexpected = False
        while not self._stop_event.is_set():
            try:
                if not self._serial:
                    break
                data = self._serial.read(self._serial.in_waiting or 1)
            except Exception as exc:
                self.serialError.emit(f"UART read failed: {exc}")
                unexpected = True
                break
            if data:
                self.rawDataReceived.emit(bytes(data))

                self._handle_rx_bytes(data)

        if unexpected:
            self.serialDisconnected.emit()

    def start_session(self, device_id: str, port: Optional[str] = None):
        self._device_id = device_id
        if port:
            self._port = port
        if self._last_device_id and self._last_device_id != device_id:
            self._emit(
                TelemetryState.DIFFERENT_DEVICE,
                note="Approached device differs from previously interrogated.",
            )
        else:
            if self._port:
                connected = self.connect_serial()
                if not connected:
                    self._emit(TelemetryState.DISCONNECTED, note="Unable to open UART.")
                    return
            self._emit(TelemetryState.CONNECTED)

    def end_session(self):
        # Remember last device for comparison next time
        self._last_device_id = self._device_id
        self._device_id = None
        self.disconnect_serial()
        self._emit(TelemetryState.DISCONNECTED)

    # --- Protocol helpers ---
    def send_params(self, params: dict):
        frame = self._build_params_frame(params)
        self.send_packet(frame)

    def request_echo(self):
        self.send_packet(self._build_simple_frame(FN_ECHO))

    def request_egram(self):
        self.send_packet(self._build_simple_frame(FN_EGRAM))

        self._egram_streaming = True

    def stop_egram(self):
        self.send_packet(self._build_simple_frame(FN_ESTOP))

        self._egram_streaming = False

    def _build_simple_frame(self, fn_code: int) -> bytes:
        header = [SYNC, fn_code, fn_code ^ SYNC ^ SOH]
        payload = [0] * 13
        checksum = sum(payload) & 0xFF
        frame = bytes([SYNC, SOH, fn_code, header[2], *payload, checksum])
        return frame

    def _build_params_frame(self, params: dict) -> bytes:
        # Values are packed little-endian per SRS 5.1.2
        data = [0] * 13
        data[0] = params.get("pacing_state", 0)
        data[1] = params.get("mode", 0)
        data[2] = 1 if params.get("hysteresis") else 0
        self._write_u16(data, 3, params.get("hysteresis_interval", 300))
        self._write_u16(data, 5, params.get("lowrate_interval", 1000))
        self._write_u16(data, 7, params.get("v_amp_mV", 3500))
        width = int(round(params.get("v_width_ms", 0.4) * 10))
        self._write_u16(data, 9, width)
        self._write_u16(data, 11, params.get("vrp_ms", 320))
        header_checksum = SYNC ^ SOH ^ FN_PARAMS
        checksum = sum(data) & 0xFF
        frame = bytes([SYNC, SOH, FN_PARAMS, header_checksum, *data, checksum])
        return frame

    @staticmethod
    def _write_u16(buffer, idx: int, value: int):
        value = max(0, min(0xFFFF, int(value)))
        buffer[idx] = value & 0xFF
        buffer[idx + 1] = (value >> 8) & 0xFF

    # Simulated conditions
    def set_out_of_range(self, is_out: bool):
        if self._device_id is None:
            return
        self._emit(TelemetryState.OUT_OF_RANGE if is_out else TelemetryState.CONNECTED)

    def set_noise(self, is_noisy: bool):
        if self._device_id is None:
            return
        self._emit(TelemetryState.NOISE if is_noisy else TelemetryState.CONNECTED)

    def _handle_rx_bytes(self, data: bytes):

        if not self._egram_streaming:
            return
        
        self._rx_buf.extend(data)

        # dual-chamber frames (18)
        while len(self._rx_buf) >= EGRAM_FRAME_SIZE:
            frame = self._rx_buf[:EGRAM_FRAME_SIZE]
            del self._rx_buf[:EGRAM_FRAME_SIZE]

            atr_raw = struct.unpack("<d", frame[1:9])[0]
            ven_raw = struct.unpack("<d", frame[10:18])[0]

            # 0 -> atr 1 -> vtr
            atr_mark = frame[0]
            ven_mark = frame[9]

            atr = atr_raw
            ven = ven_raw 

            amk = "A" if atr_mark == 0 else "V"
            vmk = "A" if ven_mark == 0 else "V"

            # Emit to any connected egram plot / handler
            self.egramSampleReceived.emit(atr, amk, ven, vmk)
  

