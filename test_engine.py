"""Grain_yantra_1 self-tests (standard library unittest).

Run:  python -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grain_yantra import drawing, engine, report, shapes  # noqa: E402

# Geometries whose reference equations are exact for a single closed port outline:
# the equation results must match the area / perimeter of the drawn shape.
EXACT_SINGLE = ["circular", "star", "dshape", "moon", "diamond", "heart", "sinusoidal", "petal", "cassini", "hybrid", "wagon", "cslot"]


def shape_metrics(scene):
    p = scene["ports"][0]
    if p["type"] == "circle":
        return math.pi * p["r"] ** 2, 2 * math.pi * p["r"]
    return shapes.poly_area(p["pts"]), shapes.poly_perimeter(p["pts"])


class TestEngine(unittest.TestCase):
    def test_all_defaults_solve_valid(self):
        for g in engine.GEOMETRIES:
            with self.subTest(g=g["id"]):
                r = engine.solve(g["id"], engine.defaults(g["id"]))
                self.assertTrue(r["ok"], r["errors"])
                v = {s["key"]: s["value"] for s in r["summary"]}
                self.assertGreater(v["w"], 0)
                self.assertLess(v["Rmax"], r["scene"]["R_case"])
                self.assertTrue(0 < v["Vf"] < 100)
                self.assertGreater(v["m"], 0)

    def test_twenty_one_geometries(self):
        self.assertEqual([g["fig"] for g in engine.GEOMETRIES], list(range(1, 22)))

    def test_equations_match_drawn_shape(self):
        for gid in EXACT_SINGLE:
            with self.subTest(g=gid):
                r = engine.solve(gid, engine.defaults(gid))
                v = {s["key"]: s["value"] for s in r["summary"]}
                area, per = shape_metrics(r["scene"])
                self.assertAlmostEqual(v["Ap"], area, delta=area * 2e-3)
                self.assertAlmostEqual(v["P0"], per, delta=per * 3e-3)

    def test_heart_is_a_true_heart(self):
        r = engine.solve("heart", engine.defaults("heart"))
        pts = r["scene"]["ports"][0]["pts"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        self.assertAlmostEqual(max(xs) - min(xs), 34.0, delta=0.05)           # entered width
        self.assertAlmostEqual(max(ys) - min(ys), 31.0, delta=0.05)           # entered height
        self.assertAlmostEqual(max(xs), -min(xs), delta=1e-6)                 # left-right symmetric
        top = max(p[1] for p in pts if abs(p[0]) < 0.2)                       # cleft on the axis ...
        self.assertLess(top, max(ys) - 3.0)                                   # ... sits below the lobe tops
        self.assertAlmostEqual(min(ys), min(p[1] for p in pts if abs(p[0]) < 0.2), delta=0.05)  # pointed tip on axis
        cy = sum(y for _, y in pts) / len(pts)
        self.assertLess(abs(cy), 1.5)                                         # centred on the motor axis

    def test_wagon_wheel_matches_outline(self):
        for raw in ({}, {"N": 5, "rf": 0, "tH": 12}, {"N": 8, "t0": 4, "tH": 9, "rf": 1.5}):
            with self.subTest(raw=raw):
                r = engine.solve("wagon", dict(engine.defaults("wagon"), **raw))
                self.assertTrue(r["ok"], r["errors"])
                v = {s["key"]: s["value"] for s in r["summary"]}
                pts = r["scene"]["ports"][0]["pts"]
                area, per = shape_metrics(r["scene"])
                self.assertAlmostEqual(v["Ap"], area, delta=area * 2e-3)
                self.assertAlmostEqual(v["P0"], per, delta=per * 2e-3)
                self.assertAlmostEqual(v["Rmax"], max(math.hypot(x, y) for x, y in pts), delta=2e-3)

    def test_cslot_dendrite_matches_outline(self):
        for raw in ({}, {"N": 3, "phi": 55, "Lb": 15}, {"N": 5, "t": 8, "wb": 6, "Lb": 12, "Lf": 8, "wf": 6}):
            with self.subTest(raw=raw):
                r = engine.solve("cslot", dict(engine.defaults("cslot"), **raw))
                self.assertTrue(r["ok"], r["errors"])
                v = {s["key"]: s["value"] for s in r["summary"]}
                pts = r["scene"]["ports"][0]["pts"]
                area, per = shape_metrics(r["scene"])
                self.assertAlmostEqual(v["Ap"], area, delta=area * 2e-3)
                self.assertAlmostEqual(v["P0"], per, delta=per * 2e-3)
                self.assertAlmostEqual(v["Rmax"], max(math.hypot(x, y) for x, y in pts), delta=1e-6)

    def test_cslot_overlap_and_bad_geometry(self):
        self.assertFalse(engine.solve("cslot", dict(engine.defaults("cslot"), N=8))["ok"])
        with self.assertRaises(engine.InputError):
            engine.solve("cslot", dict(engine.defaults("cslot"), wf=40))

    def test_wagon_overlap_flagged(self):
        r = engine.solve("wagon", dict(engine.defaults("wagon"), N=12, tH=30))
        self.assertFalse(r["ok"])

    def test_multiperf_and_triangular_exact(self):
        r = engine.solve("multiperf", engine.defaults("multiperf"))
        v = {s["key"]: s["value"] for s in r["summary"]}
        self.assertAlmostEqual(v["Ap"], 7 * math.pi * 25, places=6)
        self.assertAlmostEqual(v["P0"], 7 * 2 * math.pi * 5, places=6)
        r = engine.solve("triangular", engine.defaults("triangular"))
        v = {s["key"]: s["value"] for s in r["summary"]}
        area = sum(shapes.poly_area(p["pts"]) for p in r["scene"]["ports"])
        per = sum(shapes.poly_perimeter(p["pts"]) for p in r["scene"]["ports"])
        self.assertAlmostEqual(v["Ap"], area, delta=area * 2e-3)
        self.assertAlmostEqual(v["P0"], per, delta=per * 2e-3)

    def test_hand_calculation_circular(self):
        r = engine.solve("circular", {"OD": 100, "L": 150, "D0": 30, "prop": "KNSU", "rho": 1.889})
        v = {s["key"]: s["value"] for s in r["summary"]}
        self.assertAlmostEqual(v["w"], 35.0)
        self.assertAlmostEqual(v["Ap"], math.pi * 225)
        self.assertAlmostEqual(v["Vf"], (1 - 225 / 2500) * 100)
        self.assertAlmostEqual(v["m"], 1.889 * (math.pi * (2500 - 225) * 150) / 1000)

    def test_port_too_large_is_flagged(self):
        r = engine.solve("circular", {"OD": 50, "L": 100, "D0": 60, "prop": "KNSU", "rho": 1.889})
        self.assertFalse(r["ok"])

    def test_bad_inputs_rejected(self):
        with self.assertRaises(engine.InputError):
            engine.solve("star", dict(engine.defaults("star"), N="2.5"))
        with self.assertRaises(engine.InputError):
            engine.solve("star", dict(engine.defaults("star"), Rp="abc"))
        with self.assertRaises(engine.InputError):
            engine.solve("cassini", dict(engine.defaults("cassini"), a=20, b=10))
        with self.assertRaises(engine.InputError):
            engine.solve("nope", {})

    def test_reports_and_drawings(self):
        for g in engine.GEOMETRIES:
            with self.subTest(g=g["id"]):
                raw = engine.defaults(g["id"])
                r = engine.solve(g["id"], raw)
                meta = report.report_meta(r, raw)
                pdf = report.build_pdf(r, meta)
                self.assertTrue(pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF"))
                html = report.build_html(r, meta)
                self.assertIn("Grain_yantra_1", html)
                self.assertIn("<svg", drawing.scene_svg(r["scene"]))


if __name__ == "__main__":
    unittest.main()
