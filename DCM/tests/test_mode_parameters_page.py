import unittest

from PyQt5.QtWidgets import QApplication

from dcm_ui.mode_parameters_page import ModeParametersPage


_app = QApplication.instance() or QApplication([])


class ModeParametersPageTests(unittest.TestCase):
    """Behavioral checks driven by Deliverable 2 documentation."""

    def setUp(self):
        # Fresh widget per test ensures we have the default mode/parameter layout.
        self.page = ModeParametersPage()

    def tearDown(self):
        # Clean up the Qt widget after each test to prevent cross-test leakage.
        self.page.deleteLater()

    def test_required_modes_available(self):
        """Deliverable 2 Part 1 requires AOO/VOO etc to be programmable."""
        expected = {
            "AOO",
            "AAI",
            "VOO",
            "VVI",
            "AOOR",
            "VOOR",
            "AAIR",
            "VVIR",
            "DDD",
            "DDDR",
        }
        self.assertSetEqual(set(self.page.visible_by_mode.keys()), expected)

    def test_voltage_spinboxes_follow_table7_ranges(self):
        """Programmable amplitudes must be 0-5V in 0.1V increments (Deliverable 2 Table 7)."""
        for spin in (self.page.ed_a_amp, self.page.ed_v_amp):
            # Validate both atrial and ventricular amplitude controls share the documented range.
            self.assertEqual(spin.minimum(), 0.0)
            self.assertEqual(spin.maximum(), 5.0)
            self.assertAlmostEqual(spin.singleStep(), 0.1)
            self.assertEqual(spin.specialValueText(), "Reg Off")

    def test_pulse_width_spinboxes_follow_increment(self):
        """Pulse widths must cover 1-30ms in 1ms steps per requirements."""
        for spin in (self.page.ed_a_pw, self.page.ed_v_pw):
            # Each pulse-width spin should step through the allowable millisecond range.
            self.assertEqual(spin.minimum(), 1)
            self.assertEqual(spin.maximum(), 30)
            self.assertEqual(spin.singleStep(), 1)

    def test_accessibility_font_changes_apply(self):
        """Accessibility dialog hooks feed into the shared font preference logic."""
        baseline = self.page.font()
        new_family = "Arial" if baseline.family() != "Arial" else "Times New Roman"
        new_size = (baseline.pointSize() or 12) + 2
        # Mimic the accessibility dialog telling the page to switch font preferences.
        self.page._apply_font_preferences(new_family, new_size)
        updated = self.page.font()
        self.assertEqual(updated.family(), new_family)
        self.assertEqual(updated.pointSize(), new_size)


if __name__ == "__main__":
    unittest.main()
