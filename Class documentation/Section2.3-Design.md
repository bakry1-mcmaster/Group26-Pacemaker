# Section 2.3 Design

## System architecture

The UI is a stacked Qt desktop powered by `MainWindow`. Login, dashboard, telemetry controls, navigation shortcuts, and utility actions (about, clock, new patient, accessibility) live in that class while two feature sets are served by dedicated child widgets: `ModeParametersPage` for programmable parameters and `EgramPage` for real‑time egram capture (sources: `DCM/dcm_ui/main_window.py:23-174`, `DCM/dcm_ui/mode_parameters_page.py:61-267`, `DCM/dcm_ui/egram_page.py:32-212`). A `UserManager` in the login flow keeps credential handling separate, and the `TelemetryService` hides pyserial/serial-port concerns behind Qt signals, exposing only high-level actions such as `send_params`, `request_egram`, and `stop_egram` for the UI (`DCM/dcm_core/telemetry.py:40-224`). This layering keeps hardware communication isolated: the UI never opens the UART directly; instead it toggles telemetry via `MainWindow._toggle_connection` and interacts with telemetry signals for status updates, raw bytes, and egram samples.

## Programmable parameters

Parameters live in `PacingParams` (defaults mirror Table 3.1 in the SRS) and are serialized to `dcm_params.json`, so every change persists between sessions (`DCM/dcm_ui/mode_parameters_page.py:61-110`, `DCM/dcm_ui/mode_parameters_page.py:343-422`). The editor provides validators and specialized widgets for each type.

| Category | Parameter | Default & range (UI validator) | UI widget & persistence |
| --- | --- | --- | --- |
| **Rates** | Lower/Upper Rate Limit | 60–120 ppm stored as `lrl_ppm`/`url_ppm`; validators enforce 30–175 and 50–175, respectively | `QLineEdit` with `QIntValidator`; saved back to `PacingParams`; writes to `dcm_params.json`. |
| **Pulse amplitudes/widths** | Atrial/ventricular amplitude (0–5 V), width (1–30 ms) | Stored as millivolts (`a_amp_mV`, `v_amp_mV`) and milliseconds; `QDoubleSpinBox`/`QSpinBox` impose ranges matching the SRS tolerances | `PacingParams` ↔ UI binding + `_save`/`_reset`. |
| **Refractory & sensing** | ARP, VRP, PVARP, PVARP extension, atrial/ventricular sensitivity | Validators keep these in the SRS† ranges (150–500 ms for refractory periods, 0.0–5.0 V for sensitivities). | Fields read/write the same JSON snapshot before `TelemetryService._transmit_params`. |
| **Advanced pacing** | Hysteresis, rate smoothing, rate‑adaptive controls, AV delays | Flags and discrete selects (percent or preset strings) match the stored dataclass | Visible rows depend on `ModeParametersPage.visible_by_mode` so only the relevant controls appear for each mode (`DCM/dcm_ui/mode_parameters_page.py:118-175`, `DCM/dcm_ui/mode_parameters_page.py:453-483`). |

> †The SRS defines `p_hysteresisInterval`, `p_lowrateInterval`, `p_vPaceAmp`, `p_vPaceWidth`, and `p_VRP` for the pacemaker (see `DCM/srs_excerpt.txt:4-24`), and our UI ensures values stay within the documented ranges before calling `TelemetryService._build_params_frame`.

## Hardware inputs and outputs

The SRS describes the UART-centric interface with serial packets (`M_CommIn`, `C_CommOut`, `m_vraw`, `m_vs`, `c_vp` in `DCM/srs_excerpt.txt:4-35`), and `TelemetryService` implements the same protocol:

| Signal | Direction | Description | Code path |
| --- | --- | --- | --- |
| `i_CommIn` / UART receive | DCM → Pacemaker | Starts/stops egram (`FN_EGRAM`, `FN_ESTOP`), requests echo/params (`FN_ECHO`) and writes programmable parameters | `_build_simple_frame`, `_build_params_frame`, `send_params`, `request_egram`, `stop_egram` (`DCM/dcm_core/telemetry.py:173-224`). |
| `o_CommOut` / UART transmit | Pacemaker → DCM | Echoed parameters or streamed `m_vraw`/markers when egram is running, consistent with Figures 6–7 in the SRS | `_handle_rx_bytes` parses dual/single-chamber frames and emits `egramSampleReceived` to the UI (`DCM/dcm_core/telemetry.py:40-282`). |
| `m_magnet`, `m_vraw`, `m_vs` | Hardware inputs | Monitoring of magnet state and analog signals happens in the pacemaker firmware; DCM treats them as data/markers embedded in the UART stream | Surface-level handling occurs through the telemetry signals; the UI simply plots the samples (`DCM/dcm_ui/egram_page.py:136-235`). |
| `c_vp` | Controlled ventricular pulse | Out of scope for the DCM—handled by the pacemaker, but DCM pushes new amplitudes/widths via `send_params` so that the hardware state machine sees updated `p_vPaceAmp`, `p_vPaceWidth`, and `p_VRP` (`DCM/dcm_core/telemetry.py:198-239`). |

## State machine design for pacing modes

The pacemaker itself keeps a finite-state machine described in the SRS (VVI assumptions on `DCM/srs_excerpt.txt:7-24`), so the DCM does not reimplement those states. Instead the DCM:

- Presents only the parameters that make sense for the currently selected mode by toggling `ModeParametersPage.visible_by_mode`; the mapping ensures clinicians cannot tweak parameters that would break the pacemaker state machine (`DCM/dcm_ui/mode_parameters_page.py:118-175`, `DCM/dcm_ui/mode_parameters_page.py:453-483`).
- When a clinician saves values, `ModeParametersPage._transmit_params` translates the UI values into the frame documented in Section 5.1.2 of the SRS, sending `pacing_state`, `mode`, `hysteresis`, `lowrate_interval`, `v_amp_mV`, `v_width_ms`, and `vrp_ms` for the pacemaker FSM to consume (`DCM/dcm_ui/mode_parameters_page.py:531-556`, `DCM/dcm_core/telemetry.py:198-239`).
- The SRS also describes magnet handling and VOO/VVI transitions in Section 5.4 (`DCM/srs_excerpt.txt:33`). The DCM adapts by not forcing modes—magnet detection occurs on the hardware side—but it exposes the parameters (`p_lowrateInterval`, `p_vPaceWidth`, etc.) that govern those transitions.

## Simulink diagram

We currently defer to the SRS figures as our model diagrams. Figure 2 (VVI dataflow) and Figures 6–7 (DCM ↔ pacemaker communication) are the authoritative visual spec (`DCM/srs_excerpt.txt:7-31`). A future iteration could reverse-engineer those flows into an actual Simulink model, but this deliverable keeps the documentation textual so we can point reviewers at the exact code paths that fulfill each block.

## Screenshots of the DCM

The PyQt layout in `MainWindow` (login widget + stacked dashboard + status box + utility row) naturally yields the required screenshot set; the telemetry status box and mode selection row are grouped together because they share a `QVBoxLayout`, while the stacked widget swaps between `ModeParametersPage` and `EgramPage` without reinitializing `TelemetryService` (`DCM/dcm_ui/main_window.py:113-174`, `DCM/dcm_ui/main_window.py:223-174`). Capturing one screenshot per stacked page plus the dashboard mirrors the structure described above.

## Mapping design decisions to requirements

1. **Download programmable parameters (Req 1)** – `ModeParametersPage._save` validates the controls, persists the JSON snapshot, and pushes the telemetry frame defined in Section 5.1.2 (`DCM/dcm_ui/mode_parameters_page.py:513-558`, `DCM/dcm_core/telemetry.py:198-239`).
2. **Trigger the pacemaker to send current parameters (Req 2)** – `TelemetryService.request_echo` issues `FN_ECHO`, mirroring the packet structure diagrammed in Section 5.1.1 (`DCM/dcm_core/telemetry.py:203-210`, `DCM/srs_excerpt.txt:24-27`).
3. **Request and display egram stream (Req 3)** – The UI button wires to `EgramPage._start_egram`, which loads the latest params/mode, builds a recording template, and calls `TelemetryService.request_egram`; received frames are plotted and stored through the `egramSampleReceived` signal (`DCM/dcm_ui/egram_page.py:136-217`, `DCM/dcm_core/telemetry.py:205-282`).
4. **Stop the egram stream (Req 4)** – `TelemetryService.stop_egram` sends `FN_ESTOP` so the pacemaker halts transmission (`DCM/dcm_core/telemetry.py:213-220`).
5. **Store/display parameter history (Req 5)** – Every save rewrites `dcm_params.json`, and the export helper in `DCM/dcm_core/egram_export.py` can snapshot that file into a clean `EgramRecord` header for logging/printing (`DCM/dcm_core/egram_export.py:13-45`).
6. **Derive protocol details from communications (Req 6)** – The constants in the telemetry module (`SYNC`, `SOH`, `FN_*`) are defined to match Section 3.2 (`DCM/dcm_core/telemetry.py:15-43`, `DCM/srs_excerpt.txt:5-13`).
7. **Performance/battery awareness (Req 7)** – While the Qt client cannot force the pacemaker’s standby, the telemetry threads (`TelemetryService._read_loop`) avoid busy waits (`DCM/dcm_core/telemetry.py:100-170`), and UART sessions end quickly when the user clicks “Disconnect Telemetry,” matching the spirit of the standby requirement listed in Section 7 of the SRS (`DCM/srs_excerpt.txt:34`).
