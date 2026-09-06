import math
import unittest
from dataclasses import replace

from reknotting_model import (
    Protocol,
    box_coarse_grain,
    inaccessible_protocol,
    negative_protocol,
    recursive_diagnostics,
    route_a_protocol,
    route_b_protocol,
    simulate,
    transient_protocol,
)


class ReknottingModelTests(unittest.TestCase):
    def test_constant_profile_is_not_a_localized_defect(self):
        protocol = Protocol(name="test")
        persistent, _ = recursive_diagnostics([1.0] * protocol.points, protocol)
        self.assertFalse(persistent)

    def test_box_coarse_graining_preserves_constants(self):
        self.assertEqual(box_coarse_grain([2.0] * 9, 2), [2.0] * 9)

    def test_route_a_is_accessibility_driven_and_passes_all_gates(self):
        result, _ = simulate(*route_a_protocol())
        self.assertEqual(result.route, "accessibility-driven")
        self.assertTrue(result.reknotting)
        self.assertEqual(result.classification, "reknotting")
        self.assertLess(result.instability_crossing, result.accessibility_crossing)

    def test_route_b_is_background_driven_and_passes_all_gates(self):
        result, _ = simulate(*route_b_protocol())
        self.assertEqual(result.route, "background-driven")
        self.assertTrue(result.reknotting)
        self.assertLess(result.accessibility_crossing, result.instability_crossing)

    def test_stable_control_fails_instability_and_reknotting(self):
        result, _ = simulate(*negative_protocol())
        self.assertFalse(result.gate_i)
        self.assertTrue(result.gate_ii)
        self.assertFalse(result.reknotting)
        self.assertEqual(result.classification, "accessible but stable")
        self.assertTrue(math.isclose(result.final_amplitude, 0.0, abs_tol=1.0e-3))

    def test_inaccessible_control_passes_only_instability_gate(self):
        result, _ = simulate(*inaccessible_protocol())
        self.assertTrue(result.gate_i)
        self.assertFalse(result.gate_ii)
        self.assertFalse(result.gate_iii)
        self.assertFalse(result.reknotting)
        self.assertEqual(result.classification, "unstable but inaccessible")

    def test_transient_control_fails_persistence_gate(self):
        result, _ = simulate(*transient_protocol())
        self.assertTrue(result.gate_i)
        self.assertTrue(result.gate_ii)
        self.assertIsNotNone(result.active_crossing)
        self.assertFalse(result.gate_iii)
        self.assertFalse(result.reknotting)
        self.assertEqual(result.classification, "crossing without persistence")

    def test_route_classification_and_crossings_converge_under_dt_refinement(self):
        protocol, h_function, cutoff_function = route_b_protocol()
        coarse, _ = simulate(replace(protocol, dt=0.04), h_function, cutoff_function)
        fine, _ = simulate(replace(protocol, dt=0.02), h_function, cutoff_function)
        self.assertEqual(coarse.route, fine.route)
        self.assertEqual(coarse.reknotting, fine.reknotting)
        self.assertLessEqual(abs(coarse.active_crossing - fine.active_crossing), 0.04)
        self.assertLessEqual(abs(coarse.persistence_crossing - fine.persistence_crossing), 0.08)


if __name__ == "__main__":
    unittest.main()
