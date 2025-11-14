import unittest

from dcm_core.telemetry import (
    TelemetryService,
    SYNC,
    SOH,
    FN_PARAMS,
    FN_EGRAM,
)


class TelemetryEncodingTests(unittest.TestCase):
    def setUp(self):
        self.service = TelemetryService()
        self.sent_frame = None

        def capture(payload: bytes):
            self.sent_frame = payload

        # Monkey patch send_packet to capture frames without real UART
        self.service.send_packet = capture  # type: ignore[assignment]

    def test_params_frame_matches_srs_layout(self):
        """Deliverable spec 5.1.2 defines a 13 byte payload and XOR header."""
        params = {
            "pacing_state": 0,  # PERMANENT
            "mode": 6,  # VVI
            "hysteresis": True,
            "hysteresis_interval": 250,
            "lowrate_interval": 1000,
            "v_amp_mV": 3500,
            "v_width_ms": 0.5,
            "vrp_ms": 320,
        }

        self.service.send_params(params)
        frame = self.sent_frame
        self.assertIsNotNone(frame)
        frame = frame or b""

        # Header bytes
        self.assertEqual(frame[0], SYNC)
        self.assertEqual(frame[1], SOH)
        self.assertEqual(frame[2], FN_PARAMS)
        self.assertEqual(frame[3], SYNC ^ SOH ^ FN_PARAMS)

        # Payload (13 bytes)
        payload = frame[4:-1]
        self.assertEqual(len(payload), 13)
        expected_payload = bytes(
            [
                0,  # pacing state
                6,  # mode
                1,  # hysteresis flag
                250 & 0xFF,
                0,
                1000 & 0xFF,
                (1000 >> 8) & 0xFF,
                3500 & 0xFF,
                (3500 >> 8) & 0xFF,
                5,  # 10 * 0.5
                0,
                320 & 0xFF,
                (320 >> 8) & 0xFF,
            ]
        )
        self.assertEqual(payload, expected_payload)

        # Checksum is the sum of payload bytes mod 256
        self.assertEqual(frame[-1], sum(payload) & 0xFF)

    def test_request_egram_builds_simple_frame(self):
        self.service.request_egram()
        frame = self.sent_frame or b""
        self.assertEqual(frame[0], SYNC)
        self.assertEqual(frame[1], SOH)
        self.assertEqual(frame[2], FN_EGRAM)
        self.assertEqual(frame[3], SYNC ^ SOH ^ FN_EGRAM)
        self.assertEqual(len(frame), 18)  # 4 header + 13 payload + 1 checksum
        # Simple frames zero out payload/checksum
        self.assertTrue(all(b == 0 for b in frame[4:]))


if __name__ == "__main__":
    unittest.main()
