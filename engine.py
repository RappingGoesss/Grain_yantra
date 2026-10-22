"""Grain_yantra_1 - calculation engine.

Every geometry below implements the analytical formulation given in the reference
document "Solid Rocket Motor Grain Geometries - Analytical Formulations & 2D Profiles".
All lengths are in millimetres, areas in mm^2, volumes in mm^3, angles in radians
(user inputs for angles are entered in degrees and converted explicitly).
"""

import math
import re

from . import shapes as S

PI = math.pi
SQ3 = math.sqrt(3.0)
SQ2 = math.sqrt(2.0)

APP_NAME = "Grain_yantra_1"
REFERENCE = "Solid Rocket Motor Grain Geometries — Analytical Formulations & 2D Profiles"

# --------------------------------------------------------------------------------------
# Propellants (ideal densities, g/cm^3). Density is editable in the interface.
# --------------------------------------------------------------------------------------
PROPELLANTS = [
    {"id": "KNSU", "name": "KNSU (KNO₃ / sucrose 65/35)", "rho": 1.889},
    {"id": "KNDX", "name": "KNDX (KNO₃ / dextrose 65/35)", "rho": 1.879},
    {"id": "KNSB", "name": "KNSB (KNO₃ / sorbitol 65/35)", "rho": 1.841},
    {"id": "KNER", "name": "KNER (KNO₃ / erythritol 65/35)", "rho": 1.820},
    {"id": "APCP", "name": "APCP (AP / HTPB / Al, typical)", "rho": 1.750},
    {"id": "CUSTOM", "name": "Custom propellant", "rho": 1.700},
]
PROP_BY_ID = {p["id"]: p for p in PROPELLANTS}


class InputError(Exception):
    pass


# --------------------------------------------------------------------------------------
# Number formatting
# --------------------------------------------------------------------------------------
def fnum(x, d=3):
    if x is None:
        return "—"
    if isinstance(x, int):
        return str(x)
    if abs(x) >= 1e7 or (0 < abs(x) < 1e-3):
        return f"{x:.4e}"
    return f"{x:,.{d}f}".replace(",", " ")


UNIT_DIGITS = {"rad": 4, "%": 2, "g": 2, "mm³": 1, "cm³": 3, "mm²": 3, "mm": 3, "°": 2, "": 4, "1/mm": 6, "g/cm³": 3}


# --------------------------------------------------------------------------------------
# Calculation recorder
# --------------------------------------------------------------------------------------
class Calc:
    def __init__(self):
        self.v = {}
        self.dig = {}
        self.sections = []
        self.errors = []
        self.warnings = []
        self.notes = []
        self.meta = {}
        self.scene = None

    def put(self, key, value, digits=3):
        self.v[key] = value
        self.dig[key] = digits

    def sec(self, title, ref=None):
        self.sections.append({"title": title, "ref": ref, "steps": []})

    def sub(self, template):
        def rep(m):
            k = m.group(1)
            if k not in self.v:
                return m.group(0)
            val = self.v[k]
            s = fnum(val, self.dig.get(k, 3))
            if isinstance(val, (int, float)) and val < 0:
                s = "(" + s.replace("-", "−") + ")"
            return s
        return re.sub(r"\$([A-Za-z][A-Za-z0-9_]*)", rep, template)

    def step(self, key, name, formula, subst, value, unit="mm", digits=None, note=None):
        if digits is None:
            digits = UNIT_DIGITS.get(unit, 3)
        text = self.sub(subst) if subst else ""
        self.v[key] = value
        self.dig[key] = digits
        self.sections[-1]["steps"].append({
            "key": key,
            "name": name,
            "formula": formula,
            "subst": text,
            "value": value,
            "value_str": fnum(value, digits),
            "unit": unit,
            "note": note,
        })
        return value

    def find_step(self, key):
        for s in self.sections:
            for st in s["steps"]:
                if st["key"] == key:
                    return st
        return None


# --------------------------------------------------------------------------------------
# Numerical helpers
# --------------------------------------------------------------------------------------
def simpson(f, a, b, n=4000):
    if n % 2:
        n += 1
    h = (b - a) / n
    s = f(a) + f(b)
    for k in range(1, n):
        s += (4 if k % 2 else 2) * f(a + k * h)
    return s * h / 3


def polar_perimeter(r, dr, n=4000):
    return simpson(lambda t: math.sqrt(r(t) ** 2 + dr(t) ** 2), 0.0, 2 * PI, n)


def polar_area(r, n=4000):
    return 0.5 * simpson(lambda t: r(t) ** 2, 0.0, 2 * PI, n)


def num_deriv(r, h=1e-6):
    return lambda t: (r(t + h) - r(t - h)) / (2 * h)


# --------------------------------------------------------------------------------------
# Parameter schema
# --------------------------------------------------------------------------------------
def P(key, label, sym, unit, default, mn=0.0, mx=None, integer=False, options=None, help=""):
    d = {"key": key, "label": label, "sym": sym, "unit": unit, "default": default,
         "min": mn, "max": mx, "integer": integer, "help": help}
    if options is not None:
        d["options"] = options
    return d


COMMON_PARAMS = [
    P("OD", "Grain outer diameter", "D_{OD}", "mm", 100.0, 1.0, help="Case-bonded grain OD (= motor casing inner diameter)."),
    P("L", "Grain length", "L", "mm", 150.0, 1.0, help="Axial length of the grain segment."),
]

GEOMETRIES = []
GEOM_BY_ID = {}


def geometry(gid, fig, name, subtitle, description, params, count_label=None):
    def deco(fn):
        g = {"id": gid, "fig": fig, "name": name, "subtitle": subtitle, "description": description,
             "params": params, "solver": fn, "count_label": count_label}
        GEOMETRIES.append(g)
        GEOM_BY_ID[gid] = g
        return fn
    return deco


# --------------------------------------------------------------------------------------
# Shared step groups
# --------------------------------------------------------------------------------------
def port_from_diameter(c, label="Central bore radius"):
    return c.step("R0", label, "R_0 = D_0 / 2", "$D0 / 2", c.v["D0"] / 2)


def web_generic(c, rmax_formula, rmax_subst, rmax_value, w_formula=None, w_subst=None):
    c.step("Rmax", "Maximum port radius", rmax_formula, rmax_subst, rmax_value)
    c.step("w", "Web thickness", w_formula or "w_{max} = R_{case} − R_{max}",
           w_subst or "$Rcase − $Rmax", c.v["Rcase"] - rmax_value)


def deg_to_rad(c, key, sym, name):
    return c.step(key + "_r", name + " (radians)", f"{sym} = {sym}_{{°}} · π/180", f"${key} × π / 180",
                  c.v[key] * PI / 180, "rad")


# ======================================================================================
#  1. Circular port
# ======================================================================================
@geometry("circular", 1, "Circular Port", "Cylindrical BATES",
          "A single central circular perforation, concentric with the motor casing.",
          [P("D0", "Port diameter", "D_0", "mm", 30.0)])
def g_circular(c):
    c.sec("Port geometry & web thickness", "§1")
    R0 = port_from_diameter(c)
    web_generic(c, "R_{max} = R_0", "$R0", R0, "w_{max} = R_{case} − R_0", "$Rcase − $R0")
    c.sec("Initial burning perimeter & port area", "§1")
    c.step("P0", "Initial burning perimeter", "P_0 = 2πR_0", "2π × $R0", 2 * PI * R0)
    c.step("Ap", "Initial port area", "A_p = πR_0^2", "π × $R0^2", PI * R0 ** 2, "mm²")
    c.scene = {"ports": [{"type": "circle", "c": (0, 0), "r": R0}]}


# ======================================================================================
#  2. Multiperforated circular port
# ======================================================================================
@geometry("multiperf", 2, "Multiperforated Circular Port", "N-Hole Configuration",
          "A central circular hole surrounded by a symmetric ring of outer circular perforations (progressive-regressive).",
          [P("dh", "Perforation diameter", "d_h", "mm", 10.0),
           P("Nout", "Number of outer perforations", "N_{outer}", "", 6, 2, 36, True),
           P("Ncen", "Number of central holes", "N_{center}", "", 1, 0, 1, True, options=[1, 0]),
           P("Rpitch", "Pitch-circle radius", "R_{pitch}", "mm", 22.0)],
          count_label="Nout")
def g_multiperf(c):
    v = c.v
    c.sec("Perforation geometry & web thickness", "§2")
    rh = c.step("rh", "Radius of each perforation", "r_h = d_h / 2", "$dh / 2", v["dh"] / 2)
    c.step("Rmax", "Maximum port radius", "R_{max} = R_{pitch} + r_h", "$Rpitch + $rh", v["Rpitch"] + rh)
    c.step("w", "Outer wall web thickness", "w_{outer} = R_{case} − (R_{pitch} + r_h)",
           "$Rcase − ($Rpitch + $rh)", v["Rcase"] - (v["Rpitch"] + rh))
    c.step("w_inner", "Inter-hole web thickness (adjacent outer holes)",
           "w_{inner} = 2R_{pitch} sin(π/N_{outer}) − 2r_h", "2 × $Rpitch × sin(π/$Nout) − 2 × $rh",
           2 * v["Rpitch"] * math.sin(PI / v["Nout"]) - 2 * rh)
    if v["Ncen"] >= 1:
        c.step("w_radial", "Center-to-ring web thickness", "w_{radial} = R_{pitch} − 2r_h", "$Rpitch − 2 × $rh",
               v["Rpitch"] - 2 * rh)
    else:
        c.notes.append("No central hole (N_center = 0): the center-to-ring web w_radial does not apply.")
    c.sec("Initial burning perimeter & port area", "§2")
    n = v["Ncen"] + v["Nout"]
    c.step("P0", "Initial burning perimeter", "P_0 = (N_{center} + N_{outer}) · 2πr_h", "($Ncen + $Nout) × 2π × $rh",
           n * 2 * PI * rh)
    c.step("Ap", "Initial port area", "A_p = (N_{center} + N_{outer}) · πr_h^2", "($Ncen + $Nout) × π × $rh^2",
           n * PI * rh ** 2, "mm²")
    for k in ("w_inner", "w_radial"):
        if k in v and v[k] <= 0:
            c.errors.append(f"{'Adjacent outer perforations overlap' if k == 'w_inner' else 'Central hole overlaps the outer ring'} "
                            f"({k.replace('_', ' ')} = {fnum(v[k])} mm). Increase R_pitch or reduce d_h.")
    ports = []
    if v["Ncen"] >= 1:
        ports.append({"type": "circle", "c": (0, 0), "r": rh})
    for k in range(v["Nout"]):
        a = PI / 2 + 2 * PI * k / v["Nout"]
        ports.append({"type": "circle", "c": S.pol(v["Rpitch"], a), "r": rh})
    c.scene = {"ports": ports}
    c.meta["web_key"] = "w"
    c.meta["web_sym"] = "w_{outer}"


# ======================================================================================
#  3. Triangular multiperforated port
# ======================================================================================
@geometry("triangular", 3, "Triangular Multiperforated Port", "N-Lobe Triform",
          "Identical equilateral triangles with filleted vertices, arranged symmetrically around the axis.",
          [P("N", "Number of triangular perforations", "N", "", 3, 1, 12, True),
           P("s", "Triangle side length (before filleting)", "s", "mm", 18.0),
           P("rf", "Vertex fillet radius", "r_f", "mm", 2.0, 0.0),
           P("Rc", "Centroid radial distance", "R_c", "mm", 20.0, 0.0)],
          count_label="N")
def g_triangular(c):
    v = c.v
    N, s, rf, Rc = v["N"], v["s"], v["rf"], v["Rc"]
    c.sec("Dimensional constraints & web thickness", "§3")
    rmax = Rc + s / SQ3 - rf * (SQ3 - 1)
    web_generic(c, "R_{max} = R_c + s/√3 − r_f(√3 − 1)", "$Rc + $s/√3 − $rf × (√3 − 1)", rmax)
    exact = Rc + s / SQ3 - rf
    c.notes.append(
        f"Geometry check: for a 60° vertex the fillet centre lies 2r_f from the sharp vertex, so the exact outermost "
        f"point is R_c + s/√3 − r_f = {fnum(exact)} mm. The reference formula gives {fnum(rmax)} mm "
        f"(difference {fnum(abs(rmax - exact))} mm). Results use the reference formula; the drawing uses exact geometry.")
    c.sec("Initial burning perimeter & port area", "§3")
    c.step("P0", "Initial burning perimeter", "P_0 = N(3s − 6√3 r_f + 2πr_f)", "$N × (3 × $s − 6√3 × $rf + 2π × $rf)",
           N * (3 * s - 6 * SQ3 * rf + 2 * PI * rf))
    c.step("Ap", "Initial port area", "A_p = N(√3/4 · s^2 − (3√3 − π)r_f^2)", "$N × (√3/4 × $s^2 − (3√3 − π) × $rf^2)",
           N * (SQ3 / 4 * s ** 2 - (3 * SQ3 - PI) * rf ** 2), "mm²")
    if rf > s / (2 * SQ3) + 1e-9:
        c.errors.append(f"Fillet radius too large: r_f must be ≤ s/(2√3) = {fnum(s / (2 * SQ3))} mm.")
    if Rc - s / (2 * SQ3) < 0:
        c.warnings.append("Triangles cross the motor axis (R_c is smaller than the triangle in-radius). Check the drawing.")
    if N > 1 and 2 * Rc * math.sin(PI / N) < 2 * s / SQ3 * 0.75:
        c.warnings.append("Adjacent triangles may overlap; increase R_c or reduce s.")
    ports = []
    rho = s / SQ3
    for k in range(N):
        a = PI / 2 + 2 * PI * k / N
        cx, cy = S.pol(Rc, a)
        verts = [(cx + rho * math.cos(a + 2 * PI * j / 3), cy + rho * math.sin(a + 2 * PI * j / 3)) for j in range(3)]
        ports.append({"type": "poly", "pts": S.fillet_polygon(verts, rf)})
    c.scene = {"ports": ports}


# ======================================================================================
#  4. Star port
# ======================================================================================
@geometry("star", 4, "Star Port", "N-Point Neutral Star",
          "A neutral-burning star of alternating inner root valleys and outer star points.",
          [P("N", "Number of star points", "N", "", 6, 3, 24, True),
           P("Rp", "Star point (tip) radius", "R_p", "mm", 25.0),
           P("Rr", "Root (valley) radius", "R_r", "mm", 12.0)],
          count_label="N")
def g_star(c):
    v = c.v
    N, Rp, Rr = v["N"], v["Rp"], v["Rr"]
    c.sec("Dimensional constraints & web thickness", "§4")
    th = c.step("theta", "Half-angle of the star sector", "θ = π/N", "π / $N", PI / N, "rad")
    web_generic(c, "R_{max} = R_p", "$Rp", Rp, "w_{max} = R_{case} − R_p", "$Rcase − $Rp")
    Ls = c.step("Ls", "Flank length (root to tip)", "L_s = √(R_p^2 + R_r^2 − 2R_pR_r cos θ)",
                "√($Rp^2 + $Rr^2 − 2 × $Rp × $Rr × cos $theta)", math.sqrt(Rp ** 2 + Rr ** 2 - 2 * Rp * Rr * math.cos(th)))
    c.sec("Initial burning perimeter & port area", "§4")
    c.step("P0", "Initial burning perimeter", "P_0 ≈ 2NL_s", "2 × $N × $Ls", 2 * N * Ls)
    c.step("Ap", "Initial port area", "A_p ≈ NR_pR_r sin(π/N)", "$N × $Rp × $Rr × sin(π/$N)", N * Rp * Rr * math.sin(PI / N), "mm²")
    c.notes.append("Star corners are modelled sharp (no tip/root fillet), as in the reference formulation.")
    if Rr >= Rp:
        c.errors.append("Root radius R_r must be smaller than the tip radius R_p.")
    pts = []
    for k in range(2 * N):
        r = Rp if k % 2 == 0 else Rr
        pts.append(S.pol(r, PI / 2 + PI * k / N))
    c.scene = {"ports": [{"type": "poly", "pts": pts}]}


# ======================================================================================
#  5. Finocyl
# ======================================================================================
@geometry("finocyl", 5, "Finocyl Port", "Square / Rectangular Fins",
          "A cylindrical central bore with flat-tipped rectangular radial fin slots.",
          [P("D0", "Central bore diameter", "D_0", "mm", 24.0),
           P("N", "Number of fin slots", "N", "", 6, 1, 24, True),
           P("Lf", "Fin radial length (from R₀)", "L_f", "mm", 18.0),
           P("t", "Fin slot width", "t", "mm", 5.0)],
          count_label="N")
def g_finocyl(c):
    _slotted(c, "Lf", "L_f", "§5")


@geometry("wagon", 8, "Wagon Wheel Port", "Tapered Spokes + Flared Heads",
          "A central hub with N tapered spokes (wide at the hub, narrowing outward), each ending in a flared "
          "trapezoidal head with rounded outer corners.",
          [P("D0", "Central hub diameter", "D_0", "mm", 20.0),
           P("N", "Number of spokes", "N", "", 6, 2, 24, True),
           P("Ls", "Spoke length (hub circle to neck)", "L_s", "mm", 23.0),
           P("t0", "Spoke root width (at hub)", "t_0", "mm", 6.0),
           P("t1", "Spoke neck width (narrowest, at head)", "t_1", "mm", 3.0),
           P("Lh", "Head length (neck to outer edge)", "L_h", "mm", 9.0),
           P("tH", "Head width (outer edge)", "t_H", "mm", 14.0),
           P("rf", "Outer corner fillet radius", "r_f", "mm", 1.0, 0.0)],
          count_label="N")
def g_wagon(c):
    v = c.v
    N, t0, t1, Ls, Lh, tH, rf = v["N"], v["t0"], v["t1"], v["Ls"], v["Lh"], v["tH"], v["rf"]
    c.sec("Dimensional constraints & web thickness", "§8")
    R0 = port_from_diameter(c, "Central hub radius")
    if t0 >= 2 * R0:
        raise InputError("Spoke root width t₀ must be smaller than the hub diameter D₀.")
    c.notes.append("Construction: a circular hub of radius R₀; N identical spokes spaced 360°/N. Each spoke leaves the hub "
                   "with root width t₀, tapers linearly to the neck width t₁ at radius R₀ + L_s, then flares linearly to "
                   "the head width t_H over the head length L_h. The two outer head corners are rounded with radius r_f.")
    phi0 = c.step("phi0", "Half-angle of the spoke root on the hub", "φ_0 = arcsin(t_0 / 2R_0)", "arcsin($t0 / (2 × $R0))",
                  math.asin(t0 / (2 * R0)), "rad")
    x0 = c.step("x0", "Radial position of the spoke root chord", "x_0 = √(R_0^2 − (t_0/2)^2)", "√($R0^2 − ($t0/2)^2)",
                math.sqrt(R0 ** 2 - (t0 / 2) ** 2))
    xn = c.step("xn", "Radius of the neck (taper-to-flare junction)", "x_n = R_0 + L_s", "$R0 + $Ls", R0 + Ls)
    xt = c.step("xt", "Radius of the outer head edge", "x_t = R_0 + L_s + L_h", "$R0 + $Ls + $Lh", R0 + Ls + Lh)
    m = c.step("m", "Half flare of the head", "m = (t_H − t_1) / 2", "($tH − $t1) / 2", (tH - t1) / 2)
    lt = c.step("lt", "Length of one tapered spoke side", "l_t = √((x_n − x_0)^2 + ((t_0 − t_1)/2)^2)",
                "√(($xn − $x0)^2 + (($t0 − $t1)/2)^2)", math.sqrt((xn - x0) ** 2 + ((t0 - t1) / 2) ** 2))
    lf = c.step("lf", "Length of one flared head side", "l_f = √(L_h^2 + m^2)", "√($Lh^2 + $m^2)", math.sqrt(Lh ** 2 + m ** 2))
    beta = c.step("beta", "Interior angle at each outer head corner", "β = arccos(m / l_f)", "arccos($m / $lf)",
                  math.acos(max(-1.0, min(1.0, m / lf))), "rad")
    d = c.step("dtan", "Fillet tangent length", "d = r_f (l_f + m) / L_h", "$rf × ($lf + $m) / $Lh", rf * (lf + m) / Lh)
    cx = xt - rf
    cy = tH / 2 - d
    c.step("cx", "Fillet centre, radial coordinate", "c_x = x_t − r_f", "$xt − $rf", cx)
    c.step("cy", "Fillet centre, tangential coordinate", "c_y = t_H/2 − d", "$tH/2 − $dtan", cy)
    rmax = c.step("Rmax", "Maximum port radius (outermost point of the rounded head corner)",
                  "R_{max} = √(c_x^2 + c_y^2) + r_f", "√($cx^2 + $cy^2) + $rf", math.hypot(cx, cy) + rf)
    c.step("w", "Web thickness", "w_{max} = R_{case} − R_{max}", "$Rcase − $Rmax", v["Rcase"] - rmax)
    c.sec("Initial burning perimeter & port area", "§8")
    arc_f = rf * (PI - beta)
    c.step("P0", "Initial burning perimeter",
           "P_0 = N[2l_t + 2l_f + t_H − 4d + 2r_f(π − β)] + R_0(2π − 2Nφ_0)",
           "$N × (2 × $lt + 2 × $lf + $tH − 4 × $dtan + 2 × $rf × (π − $beta)) + $R0 × (2π − 2 × $N × $phi0)",
           N * (2 * lt + 2 * lf + tH - 4 * d + 2 * arc_f) + R0 * (2 * PI - 2 * N * phi0))
    A1 = (t0 + t1) / 2 * (xn - x0)
    A2 = (t1 + tH) / 2 * Lh
    Af = d * rf - rf * arc_f / 2
    Aseg = R0 ** 2 / 2 * (2 * phi0 - math.sin(2 * phi0))
    c.step("Aspoke", "Area of one spoke beyond the root chord (taper + head)", "A_1 = (t_0 + t_1)/2 · (x_n − x_0) + (t_1 + t_H)/2 · L_h",
           "($t0 + $t1)/2 × ($xn − $x0) + ($t1 + $tH)/2 × $Lh", A1 + A2, "mm²")
    c.step("Afil", "Area removed by one corner fillet", "A_f = d·r_f − ½r_f^2(π − β)", "$dtan × $rf − 0.5 × $rf^2 × (π − $beta)", Af, "mm²")
    c.step("Aseg", "Hub circular segment already counted in the hub (per spoke root)", "A_{seg} = ½R_0^2(2φ_0 − sin 2φ_0)",
           "0.5 × $R0^2 × (2 × $phi0 − sin(2 × $phi0))", Aseg, "mm²")
    c.step("Ap", "Initial port area", "A_p = πR_0^2 + N(A_1 − 2A_f − A_{seg})",
           "π × $R0^2 + $N × ($Aspoke − 2 × $Afil − $Aseg)", PI * R0 ** 2 + N * (A1 + A2 - 2 * Af - Aseg), "mm²")
    if rf > 0 and (d > tH / 2 + 1e-9 or d > lf + 1e-9):
        c.errors.append(f"Fillet radius too large for the head: r_f gives a tangent length of {fnum(d)} mm, which exceeds the "
                        f"head half-width ({fnum(tH / 2)} mm) or flared side ({fnum(lf)} mm). Reduce r_f.")
    if N * 2 * phi0 >= 2 * PI:
        c.errors.append("Spoke roots do not fit around the hub: N·t₀ is too large for the hub circumference. Reduce N or t₀, or enlarge D₀.")
    psi = math.atan2(tH / 2, xt)
    gap = 2 * math.hypot(xt, tH / 2) * math.sin(PI / N - psi) if PI / N - psi > 0 else 0.0
    if gap <= 0:
        c.errors.append("Adjacent spoke heads overlap. Reduce the head width t_H or the number of spokes N.")
    elif gap < 1.0:
        c.warnings.append(f"Adjacent spoke heads are only {fnum(gap)} mm apart at their outer corners.")
    if tH < t1:
        c.warnings.append("Head width is smaller than the neck width: the head narrows instead of flaring.")
    # ---- drawing: one continuous outline -------------------------------------------------
    def to_global(pt, a):
        ca, sa = math.cos(a), math.sin(a)
        return (pt[0] * ca - pt[1] * sa, pt[0] * sa + pt[1] * ca)

    pts = []
    for k in range(N):
        a = PI / 2 + 2 * PI * k / N
        r_root_r = (x0, -t0 / 2)
        neck_r = (xn, -t1 / 2)
        tip_r = (xt, -tH / 2)
        tip_l = (xt, tH / 2)
        neck_l = (xn, t1 / 2)
        root_l = (x0, t0 / 2)
        local = [r_root_r, neck_r]
        local += S.fillet_corner(neck_r, tip_r, tip_l, rf, 32)
        local += S.fillet_corner(tip_r, tip_l, neck_l, rf, 32)
        local += [neck_l, root_l]
        pts += [to_global(q, a) for q in local]
        # hub arc (counter-clockwise) to the next spoke's root
        a_from = a + phi0
        a_to = a + 2 * PI / N - phi0
        n_arc = 48
        pts += [S.pol(R0, a_from + (a_to - a_from) * j / n_arc) for j in range(1, n_arc)]
    c.scene = {"ports": [{"type": "poly", "pts": pts}], "dim_angle": math.radians(30)}


def _slotted(c, lk, lsym, ref):
    v = c.v
    N, t = v["N"], v["t"]
    c.sec("Dimensional constraints & web thickness", ref)
    R0 = port_from_diameter(c)
    Lx = v[lk]
    web_generic(c, f"R_{{max}} = R_0 + {lsym}", f"$R0 + ${lk}", R0 + Lx,
                f"w_{{max}} = R_{{case}} − (R_0 + {lsym})", f"$Rcase − ($R0 + ${lk})")
    c.sec("Initial burning perimeter & port area", ref)
    c.step("P0", "Initial burning perimeter", f"P_0 = 2πR_0 − Nt + N(2{lsym} + t) = 2πR_0 + 2N{lsym}",
           f"2π × $R0 + 2 × $N × ${lk}", 2 * PI * R0 + 2 * N * Lx)
    c.step("Ap", "Initial port area", f"A_p = πR_0^2 + N({lsym} · t)", f"π × $R0^2 + $N × $" + lk + " × $t",
           PI * R0 ** 2 + N * Lx * t, "mm²")
    if N * t >= 2 * PI * R0:
        c.errors.append("Slots do not fit around the bore: N·t must be smaller than 2πR₀.")
    elif t > 2 * R0 * math.sin(PI / N) and N > 1:
        c.warnings.append("Adjacent slots touch at the bore; consider a larger bore or narrower slots.")
    ports = [{"type": "circle", "c": (0, 0), "r": R0}]
    for k in range(N):
        a = PI / 2 + 2 * PI * k / N
        ports.append({"type": "poly", "pts": S.radial_rect(a, 0.0, R0 + Lx, t)})
    c.scene = {"ports": ports}


# ======================================================================================
#  6. Dendrite
# ======================================================================================
@geometry("dendrite", 6, "Dendrite Port", "Bifurcated Y-Spokes",
          "Primary radial slots that bifurcate into two angled, square-tipped secondary branches.",
          [P("D0", "Central hub diameter", "D_0", "mm", 20.0),
           P("N", "Number of primary spokes", "N", "", 6, 1, 16, True),
           P("L1", "Primary spoke length", "L_1", "mm", 12.0),
           P("t1", "Primary spoke width", "t_1", "mm", 4.0),
           P("L2", "Secondary branch length", "L_2", "mm", 9.0),
           P("t2", "Secondary branch width", "t_2", "mm", 3.5),
           P("phi", "Branching half-angle", "φ", "°", 35.0, 1.0, 89.0)],
          count_label="N")
def g_dendrite(c):
    v = c.v
    N, L1, t1, L2, t2 = v["N"], v["L1"], v["t1"], v["L2"], v["t2"]
    c.sec("Dimensional constraints & web thickness", "§6")
    R0 = port_from_diameter(c, "Central hub radius")
    ph = deg_to_rad(c, "phi", "φ", "Branching half-angle")
    web_generic(c, "R_{max} = R_0 + L_1 + L_2 cos φ", "$R0 + $L1 + $L2 × cos $phi_r", R0 + L1 + L2 * math.cos(ph),
                "w_{max} = R_{case} − (R_0 + L_1 + L_2 cos φ)", "$Rcase − $Rmax")
    c.sec("Initial burning perimeter & port area", "§6")
    c.step("P0", "Initial burning perimeter", "P_0 = 2πR_0 − Nt_1 + N(2L_1 − 2t_2/sin φ + 4L_2 + 2t_2)",
           "2π × $R0 − $N × $t1 + $N × (2 × $L1 − 2 × $t2 / sin $phi_r + 4 × $L2 + 2 × $t2)",
           2 * PI * R0 - N * t1 + N * (2 * L1 - 2 * t2 / math.sin(ph) + 4 * L2 + 2 * t2))
    c.step("Ap", "Initial port area", "A_p ≈ πR_0^2 + N(L_1 · t_1) + 2N(L_2 · t_2)",
           "π × $R0^2 + $N × $L1 × $t1 + 2 × $N × $L2 × $t2", PI * R0 ** 2 + N * L1 * t1 + 2 * N * L2 * t2, "mm²")
    if N * t1 >= 2 * PI * R0:
        c.errors.append("Primary spokes do not fit around the hub: N·t₁ must be smaller than 2πR₀.")
    ports = [{"type": "circle", "c": (0, 0), "r": R0}]
    for k in range(N):
        a = PI / 2 + 2 * PI * k / N
        ports.append({"type": "poly", "pts": S.radial_rect(a, 0.0, R0 + L1, t1)})
        tip = S.pol(R0 + L1 - t2 / 2, a)
        for sgn in (1, -1):
            ports.append({"type": "poly", "pts": S.rect_from(tip, a + sgn * ph, L2, t2, back=t1 / 2)})
    c.scene = {"ports": ports}


# ======================================================================================
#  7. Dogbone
# ======================================================================================
@geometry("dogbone", 7, "Dogbone Port", "Bulbous Radial Slots",
          "Radial slots, each ending in an enlarged circular bulb to relieve stress and tailor burn progression.",
          [P("D0", "Central bore diameter", "D_0", "mm", 16.0),
           P("N", "Number of radial slots", "N", "", 3, 1, 12, True),
           P("Ls", "Straight slot length (hub to bulb)", "L_s", "mm", 14.0),
           P("t", "Slot width", "t", "mm", 4.0),
           P("rb", "Bulb radius", "r_{bulb}", "mm", 5.0)],
          count_label="N")
def g_dogbone(c):
    v = c.v
    N, Ls, t, rb = v["N"], v["Ls"], v["t"], v["rb"]
    c.sec("Dimensional constraints & web thickness", "§7")
    R0 = port_from_diameter(c, "Central bore hub radius")
    RL = c.step("RL", "Centerline distance to bulb center", "R_L = R_0 + L_s + r_{bulb}", "$R0 + $Ls + $rb", R0 + Ls + rb)
    web_generic(c, "R_{max} = R_L + r_{bulb}", "$RL + $rb", RL + rb,
                "w_{max} = R_{case} − (R_L + r_{bulb})", "$Rcase − ($RL + $rb)")
    c.sec("Initial burning perimeter & port area", "§7")
    c.step("P0", "Initial burning perimeter", "P_0 ≈ 2πR_0 − Nt + 2NL_s + N(2πr_{bulb} − t)",
           "2π × $R0 − $N × $t + 2 × $N × $Ls + $N × (2π × $rb − $t)",
           2 * PI * R0 - N * t + 2 * N * Ls + N * (2 * PI * rb - t))
    c.step("Ap", "Initial port area", "A_p ≈ πR_0^2 + N(L_s · t) + N(πr_{bulb}^2)",
           "π × $R0^2 + $N × $Ls × $t + $N × π × $rb^2", PI * R0 ** 2 + N * Ls * t + N * PI * rb ** 2, "mm²")
    if t >= 2 * rb:
        c.warnings.append("Slot width t is not smaller than the bulb diameter; the bulb will not be distinct.")
    ports = [{"type": "circle", "c": (0, 0), "r": R0}]
    for k in range(N):
        a = PI / 2 + 2 * PI * k / N
        ports.append({"type": "poly", "pts": S.radial_rect(a, 0.0, R0 + Ls + rb * 0.5, t)})
        ports.append({"type": "circle", "c": S.pol(RL, a), "r": rb})
    c.scene = {"ports": ports}


# ======================================================================================
#  9. D-shape
# ======================================================================================
@geometry("dshape", 9, "D-Shape Port", "Truncated Cylinder",
          "A circular port truncated along a straight vertical chord.",
          [P("Rd", "Arc radius of the D-port", "R_d", "mm", 20.0),
           P("xc", "Chord offset from origin", "x_c", "mm", 8.0, 0.0)])
def g_dshape(c):
    v = c.v
    Rd, xc = v["Rd"], v["xc"]
    if xc >= Rd:
        raise InputError("Chord offset x_c must be smaller than the arc radius R_d.")
    c.sec("Dimensional constraints & web thickness", "§9")
    web_generic(c, "R_{max} = R_d", "$Rd", Rd, "w_{max} = R_{case} − R_d", "$Rcase − $Rd")
    al = c.step("alpha", "Chord subtended half-angle", "α = arccos(x_c / R_d)", "arccos($xc / $Rd)", math.acos(xc / Rd), "rad")
    c.step("Lc", "Straight chord length", "L_c = 2R_d sin α", "2 × $Rd × sin $alpha", 2 * Rd * math.sin(al))
    c.sec("Initial burning perimeter & port area", "§9")
    c.step("P0", "Initial burning perimeter", "P_0 = 2R_d sin α + 2R_d(π − α)", "2 × $Rd × sin $alpha + 2 × $Rd × (π − $alpha)",
           2 * Rd * math.sin(al) + 2 * Rd * (PI - al))
    c.step("Ap", "Initial port area", "A_p = R_d^2(π − α + sin α cos α)", "$Rd^2 × (π − $alpha + sin $alpha × cos $alpha)",
           Rd ** 2 * (PI - al + math.sin(al) * math.cos(al)), "mm²")
    n = 180
    pts = [S.pol(Rd, -(PI - al) + 2 * (PI - al) * k / n) for k in range(n + 1)]
    c.scene = {"ports": [{"type": "poly", "pts": pts}]}


# ======================================================================================
# 10. Moon burner
# ======================================================================================
@geometry("moon", 10, "Moon Burner Port", "Eccentric Circular Bore",
          "A single circular bore offset eccentrically from the casing centerline.",
          [P("D0", "Bore diameter", "D_0", "mm", 30.0),
           P("e", "Eccentricity (center offset)", "e", "mm", 8.0, 0.0)])
def g_moon(c):
    v = c.v
    c.sec("Dimensional constraints & web thickness", "§10")
    R0 = port_from_diameter(c, "Radius of the eccentric bore")
    e = v["e"]
    c.step("Rmax", "Maximum port extent", "R_{max} = R_0 + e", "$R0 + $e", R0 + e)
    c.step("w", "Minimum web thickness", "w_{min} = R_{case} − (R_0 + e)", "$Rcase − ($R0 + $e)", v["Rcase"] - (R0 + e))
    c.step("w_max", "Maximum web thickness", "w_{max} = R_{case} + e − R_0", "$Rcase + $e − $R0", v["Rcase"] + e - R0)
    c.sec("Initial burning perimeter & port area", "§10")
    c.step("P0", "Initial burning perimeter", "P_0 = 2πR_0", "2π × $R0", 2 * PI * R0)
    c.step("Ap", "Initial port area", "A_p = πR_0^2", "π × $R0^2", PI * R0 ** 2, "mm²")
    c.meta["web_sym"] = "w_{min}"
    c.scene = {"ports": [{"type": "circle", "c": (e, 0), "r": R0}], "dim_angle": math.radians(20)}


# ======================================================================================
# 11. Heart
# ======================================================================================
# Classic parametric heart (two round lobes, a V-shaped cleft on top, a pointed tip below):
#   x(t) = 16 sin^3 t
#   y(t) = 13 cos t − 5 cos 2t − 2 cos 3t − cos 4t
# Natural size: 32 wide, H_n = 17 + 11.9233 = 28.9233 tall, area exactly 180π, centroid at y = 5/6.
_HEART_HN = 28.923252410839797


def _heart_xy(t, sx, sy):
    """Heart outline point at parameter t, scaled and shifted so the area centroid sits on the motor axis."""
    x = 16.0 * sx * math.sin(t) ** 3
    y = sy * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t) - 5.0 / 6.0)
    return x, y


def _heart_speed(t, sx, sy):
    dx = 48.0 * sx * math.sin(t) ** 2 * math.cos(t)
    dy = sy * (-13 * math.sin(t) + 10 * math.sin(2 * t) + 6 * math.sin(3 * t) + 4 * math.sin(4 * t))
    return math.sqrt(dx * dx + dy * dy)


@geometry("heart", 11, "Heart Port", "Classic Heart Profile",
          "A true heart-shaped port: two round lobes, a V-shaped cleft on top and a pointed tip below, centred on the motor axis.",
          [P("W", "Heart width (lobe to lobe)", "W", "mm", 34.0),
           P("H", "Heart height (cleft-to-tip extent)", "H", "mm", 31.0)])
def g_heart(c):
    v = c.v
    W, H = v["W"], v["H"]
    c.sec("Profile definition & web thickness", "§11")
    c.notes.append("Heart outline (parameter t from 0 to 2π): x(t) = 16·s_x·sin³t,  "
                   "y(t) = s_y·(13cos t − 5cos 2t − 2cos 3t − cos 4t − 5/6).  The −5/6 term moves the area centroid "
                   "onto the motor axis so the heart sits centred in the grain.")
    sx = c.step("sx", "Horizontal scale factor", "s_x = W / 32", "$W / 32", W / 32, "", 4)
    sy = c.step("sy", "Vertical scale factor", "s_y = H / H_n,  H_n = 28.9233", "$H / 28.9233", H / _HEART_HN, "", 4)
    n_s = 20000
    rmax = max(math.hypot(*_heart_xy(2 * PI * k / n_s, sx, sy)) for k in range(n_s))
    c.step("Rmax", "Maximum radial extent from the axis", "R_{max} = max_t √(x(t)^2 + y(t)^2)",
           "max over t of √(x(t)^2 + y(t)^2)   `[20 000-point sweep]`", rmax)
    c.step("w", "Web thickness", "w_{max} = R_{case} − R_{max}", "$Rcase − $Rmax", v["Rcase"] - rmax)
    c.sec("Initial burning perimeter & port area", "§11")
    c.step("P0", "Initial burning perimeter", "P_0 = ∫_0^{2π} √(x′(t)^2 + y′(t)^2) dt",
           "∫_0^{2π} √(x′(t)^2 + y′(t)^2) dt   `[Simpson, n = 4000]`",
           simpson(lambda t: _heart_speed(t, sx, sy), 0.0, 2 * PI, 4000))
    c.step("Ap", "Initial port area", "A_p = ½∮(x dy − y dx) = 180π · s_x · s_y",
           "180π × $sx × $sy", 180 * PI * sx * sy, "mm²")
    n_p = 2400
    # counter-clockwise outline (t runs backwards), starting at the top cleft
    pts = [_heart_xy(2 * PI * (1 - k / n_p), sx, sy) for k in range(n_p)]
    c.scene = {"ports": [{"type": "poly", "pts": pts}], "dim_angle": math.radians(-40)}


# ======================================================================================
# 12/13. Anchor ports
# ======================================================================================
_ANCHOR_PARAMS = [
    P("D0", "Central bore diameter", "D_0", "mm", 12.0),
    P("Ls", "Stem slot radial length", "L_s", "mm", 16.0),
    P("ts", "Stem slot width", "t_s", "mm", 4.0),
    P("phiarc", "Fluke arc angular sweep", "φ_{arc}", "°", 160.0, 1.0, 359.0),
    P("tf", "Fluke slot radial width", "t_f", "mm", 6.0),
]


@geometry("anchor1", 12, "Single Anchor Port", "Stem + Curved Fluke",
          "A central bore, a single straight radial stem slot and a broad curved anchor fluke slot.",
          [dict(p) for p in _ANCHOR_PARAMS])
def g_anchor1(c):
    _anchor(c, 1)


@geometry("anchor2", 13, "Double Anchor Port", "Mirrored Anchors",
          "A mirrored anchor: central hub, two opposing radial stems and two symmetrical curved fluke arcs.",
          [dict(p, default=(110.0 if p["key"] == "phiarc" else p["default"]), max=(179.0 if p["key"] == "phiarc" else p["max"]))
           for p in _ANCHOR_PARAMS])
def g_anchor2(c):
    _anchor(c, 2)


def _anchor(c, n):
    v = c.v
    ref = "§12" if n == 1 else "§13"
    c.sec("Dimensional constraints & web thickness", ref)
    R0 = port_from_diameter(c)
    Rarc = c.step("Rarc", "Fluke centerline radius", "R_{arc} = R_0 + L_s", "$R0 + $Ls", R0 + v["Ls"])
    pa = deg_to_rad(c, "phiarc", "φ_{arc}", "Fluke arc sweep")
    web_generic(c, "R_{max} = R_{arc} + t_f/2", "$Rarc + $tf / 2", Rarc + v["tf"] / 2,
                "w_{max} = R_{case} − (R_{arc} + t_f/2)", "$Rcase − ($Rarc + $tf / 2)")
    Larc = c.step("Larc", "Fluke centerline arc length" if n == 1 else "Single fluke arc length",
                  "L_{arc} = R_{arc} · φ_{arc}", "$Rarc × $phiarc_r", Rarc * pa)
    c.sec("Initial burning perimeter & port area", ref)
    if n == 1:
        c.step("P0", "Initial burning perimeter", "P_0 ≈ 2πR_0 − t_s + 2L_s + 2L_{arc} + 2t_f",
               "2π × $R0 − $ts + 2 × $Ls + 2 × $Larc + 2 × $tf",
               2 * PI * R0 - v["ts"] + 2 * v["Ls"] + 2 * Larc + 2 * v["tf"])
        c.step("Ap", "Initial port area", "A_p ≈ πR_0^2 + (L_s · t_s) + (L_{arc} · t_f)",
               "π × $R0^2 + $Ls × $ts + $Larc × $tf", PI * R0 ** 2 + v["Ls"] * v["ts"] + Larc * v["tf"], "mm²")
    else:
        c.step("P0", "Initial burning perimeter", "P_0 ≈ 2πR_0 − 2t_s + 4L_s + 4L_{arc} + 4t_f",
               "2π × $R0 − 2 × $ts + 4 × $Ls + 4 × $Larc + 4 × $tf",
               2 * PI * R0 - 2 * v["ts"] + 4 * v["Ls"] + 4 * Larc + 4 * v["tf"])
        c.step("Ap", "Initial port area", "A_p ≈ πR_0^2 + 2(L_s · t_s) + 2(L_{arc} · t_f)",
               "π × $R0^2 + 2 × $Ls × $ts + 2 × $Larc × $tf", PI * R0 ** 2 + 2 * v["Ls"] * v["ts"] + 2 * Larc * v["tf"], "mm²")
        if pa >= PI:
            c.errors.append("The two fluke arcs overlap: φ_arc must be below 180° for a double anchor.")
    if v["tf"] / 2 >= v["Ls"]:
        c.errors.append("Fluke slot intersects the central bore: t_f/2 must be smaller than L_s.")
    ports = [{"type": "circle", "c": (0, 0), "r": R0}]
    for k in range(n):
        a = PI / 2 + PI * k
        ports.append({"type": "poly", "pts": S.radial_rect(a, 0.0, Rarc, v["ts"])})
        ports.append({"type": "poly", "pts": S.annular_sector(Rarc - v["tf"] / 2, Rarc + v["tf"] / 2, a - pa / 2, a + pa / 2)})
    c.scene = {"ports": ports, "dim_angle": math.radians(-30 if n == 1 else 0)}
    c.notes.append("Fluke arcs are centred on the motor axis with R_arc = R₀ + L_s so the stem meets the fluke centerline.")


# ======================================================================================
# 14. Cloverleaf
# ======================================================================================
@geometry("cloverleaf", 14, "Cloverleaf Port", "4-Lobe Profile",
          "A central square core overlapped by four symmetric circular lobes on the orthogonal axes.",
          [P("sc", "Central core square side", "s_c", "mm", 8.0),
           P("Rc", "Lobe center offset", "R_c", "mm", 10.0),
           P("Rlobe", "Lobe radius", "R_{lobe}", "mm", 9.0)])
def g_cloverleaf(c):
    v = c.v
    c.put("N", 4)
    sc, Rc, Rl = v["sc"], v["Rc"], v["Rlobe"]
    c.sec("Dimensional constraints & web thickness", "§14")
    c.notes.append("Number of lobes is fixed at N = 4 for the cloverleaf profile.")
    web_generic(c, "R_{max} = R_c + R_{lobe}", "$Rc + $Rlobe", Rc + Rl,
                "w_{max} = R_{case} − (R_c + R_{lobe})", "$Rcase − ($Rc + $Rlobe)")
    c.sec("Initial burning perimeter & port area", "§14")
    c.step("P0", "Initial burning perimeter", "P_0 ≈ N(3/2 · πR_{lobe})", "4 × 1.5 × π × $Rlobe", 4 * 1.5 * PI * Rl)
    c.step("Ap", "Initial port area", "A_p ≈ s_c^2 + N(3/4 · πR_{lobe}^2)", "$sc^2 + 4 × 0.75 × π × $Rlobe^2",
           sc ** 2 + 4 * 0.75 * PI * Rl ** 2, "mm²")
    if Rc - Rl > sc / 2:
        c.errors.append("Lobes are detached from the core square (R_c − R_lobe > s_c/2).")
    h = sc / 2
    ports = [{"type": "poly", "pts": [(-h, -h), (h, -h), (h, h), (-h, h)]}]
    for k in range(4):
        ports.append({"type": "circle", "c": S.pol(Rc, PI / 2 * k), "r": Rl})
    c.scene = {"ports": ports, "dim_angle": math.radians(45)}


# ======================================================================================
# 15. Rounded diamond
# ======================================================================================
@geometry("diamond", 15, "Rounded Diamond Port", "45° Square, Filleted",
          "A square port rotated 45° (diamond orientation) with symmetrically filleted vertices.",
          [P("s0", "Square side length (unfilleted)", "s_0", "mm", 28.0),
           P("rf", "Corner fillet radius", "r_f", "mm", 4.0, 0.0)])
def g_diamond(c):
    v = c.v
    s0, rf = v["s0"], v["rf"]
    c.sec("Dimensional constraints & web thickness", "§15")
    c.step("d0", "Unfilleted half-diagonal", "d_0 = s_0/√2", "$s0 / √2", s0 / SQ2)
    web_generic(c, "R_{max} = s_0/√2 − r_f(√2 − 1)", "$s0/√2 − $rf × (√2 − 1)", s0 / SQ2 - rf * (SQ2 - 1))
    c.sec("Initial burning perimeter & port area", "§15")
    c.step("P0", "Initial burning perimeter", "P_0 = 4(s_0 − 2r_f) + 2πr_f", "4 × ($s0 − 2 × $rf) + 2π × $rf",
           4 * (s0 - 2 * rf) + 2 * PI * rf)
    c.step("Ap", "Initial port area", "A_p = s_0^2 − (4 − π)r_f^2", "$s0^2 − (4 − π) × $rf^2", s0 ** 2 - (4 - PI) * rf ** 2, "mm²")
    if rf > s0 / 2:
        c.errors.append("Fillet radius r_f must not exceed s₀/2.")
    d = s0 / SQ2
    verts = [(d, 0), (0, d), (-d, 0), (0, -d)]
    c.scene = {"ports": [{"type": "poly", "pts": S.fillet_polygon(verts, min(rf, s0 / 2 * 0.999))}],
               "dim_angle": math.radians(22)}


# ======================================================================================
# 16. C-slotted dendrite
# ======================================================================================
@geometry("cslot", 16, "C-Slotted Dendrite Port", "Spokes with Forked C-Slot Heads",
          "A central hub with N straight stems; each stem forks into two swept-back branches whose ends turn "
          "outward into short feet, forming a C-shaped slot head with a V notch between the branches.",
          [P("D0", "Central hub diameter", "D_0", "mm", 25.0),
           P("N", "Number of stems", "N", "", 4, 2, 12, True),
           P("Ls", "Stem length (hub circle to fork)", "L_s", "mm", 9.0),
           P("t", "Stem width", "t", "mm", 10.5),
           P("phi", "Branch angle from the stem axis", "φ", "°", 66.0, 5.0, 85.0),
           P("wb", "Branch width (perpendicular)", "w_b", "mm", 7.6),
           P("Lb", "Branch length (lower edge)", "L_b", "mm", 17.3),
           P("Lf", "Foot length (outer side)", "L_f", "mm", 10.7),
           P("wf", "Foot width", "w_f", "mm", 8.0)],
          count_label="N")
def g_cslot(c):
    v = c.v
    N, Ls, t, wb, Lb, Lf, wf = v["N"], v["Ls"], v["t"], v["wb"], v["Lb"], v["Lf"], v["wf"]
    c.sec("Dimensional constraints & web thickness", "§16")
    R0 = port_from_diameter(c, "Central hub radius")
    if t >= 2 * R0:
        raise InputError("Stem width t must be smaller than the hub diameter D₀.")
    ph = deg_to_rad(c, "phi", "φ", "Branch angle from the stem axis")
    sp, cp = math.sin(ph), math.cos(ph)
    c.notes.append("Construction (local axes: x along the stem, y across it): a circular hub of radius R₀; N identical stems "
                   "spaced 360°/N. Each stem of width t runs to x_s = R₀ + L_s, where it forks. The lower edge of each "
                   "branch leaves the stem corner (x_s, ±t/2) at angle φ to the stem axis for the length L_b; the foot then "
                   "runs parallel to the stem for L_f. The upper edges of the two branches are parallel to the lower edges, "
                   "w_b away, and meet on the axis in a V notch at x_v. The foot end is flat and w_f wide.")
    phi0 = c.step("phi0", "Half-angle of the stem root on the hub", "φ_0 = arcsin(t / 2R_0)", "arcsin($t / (2 × $R0))",
                  math.asin(t / (2 * R0)), "rad")
    x0 = c.step("x0", "Radial position of the stem root chord", "x_0 = √(R_0^2 − (t/2)^2)", "√($R0^2 − ($t/2)^2)",
                math.sqrt(R0 ** 2 - (t / 2) ** 2))
    xs = c.step("xs", "Radius where the stem forks", "x_s = R_0 + L_s", "$R0 + $Ls", R0 + Ls)
    dv = wb - (t / 2) * cp
    if dv <= 0:
        raise InputError("Branch width w_b is too small for this stem width and angle: the V notch would fall inside the stem. "
                         "Increase w_b or reduce t.")
    xv = c.step("xv", "Radius of the V notch between the branches", "x_v = x_s + (w_b − (t/2)cos φ) / sin φ",
                "$xs + ($wb − ($t/2) × cos $phi_r) / sin $phi_r", xs + dv / sp)
    xB = c.step("xB", "Radial position of the branch end (outer corner of the bend)", "x_B = x_s + L_b cos φ",
                "$xs + $Lb × cos $phi_r", xs + Lb * cp)
    yB = c.step("yB", "Lateral position of the branch end", "y_B = t/2 + L_b sin φ", "$t/2 + $Lb × sin $phi_r", t / 2 + Lb * sp)
    xE = c.step("xE", "Radial position of the foot end", "x_E = x_B + L_f", "$xB + $Lf", xB + Lf)
    yU = yB - wf
    if yU <= 0:
        raise InputError("Foot width w_f is too large: it must be smaller than y_B = t/2 + L_b sin φ.")
    c.step("yU", "Lateral position of the foot inner side", "y_U = y_B − w_f", "$yB − $wf", yU)
    xU = c.step("xU", "Radial position where the foot inner side meets the upper branch edge", "x_U = x_v + y_U cos φ / sin φ",
                "$xv + $yU × cos $phi_r / sin $phi_r", xv + yU * cp / sp)
    if xE - xU <= 0:
        raise InputError("The foot is too short: increase L_f or reduce w_f.")
    rmax = c.step("Rmax", "Maximum port radius (outer corner of the foot)", "R_{max} = √(x_E^2 + y_B^2)",
                  "√($xE^2 + $yB^2)", math.hypot(xE, yB))
    c.step("w", "Web thickness", "w_{max} = R_{case} − R_{max}", "$Rcase − $Rmax", v["Rcase"] - rmax)

    c.sec("Initial burning perimeter & port area", "§16")
    Lfi = c.step("Lfi", "Length of the foot inner side", "l_{fi} = x_E − x_U", "$xE − $xU", xE - xU)
    sU = c.step("sU", "Length of the upper branch edge (notch to foot)", "l_u = y_U / sin φ", "$yU / sin $phi_r", yU / sp)
    c.step("Pside", "Boundary length of one half-stem (one side of the axis)",
           "p = (x_s − x_0) + L_b + L_f + w_f + l_{fi} + l_u",
           "($xs − $x0) + $Lb + $Lf + $wf + $Lfi + $sU", (xs - x0) + Lb + Lf + wf + Lfi + sU)
    c.step("P0", "Initial burning perimeter", "P_0 = 2N·p + R_0(2π − 2Nφ_0)",
           "2 × $N × $Pside + $R0 × (2π − 2 × $N × $phi0)", 2 * N * v["Pside"] + R0 * (2 * PI - 2 * N * phi0))
    half = [(x0, 0.0), (x0, t / 2), (xs, t / 2), (xB, yB), (xE, yB), (xE, yU), (xU, yU), (xv, 0.0)]
    a_half = 0.0
    for i in range(len(half)):
        x1, y1 = half[i - 1]
        x2, y2 = half[i]
        a_half += x1 * y2 - x2 * y1
    a_half = abs(a_half) / 2
    c.step("Ahalf", "Area of one half-stem beyond the root chord",
           "A_h = ½|Σ(x_i y_{i+1} − x_{i+1} y_i)| over (x_0,0), (x_0,t/2), (x_s,t/2), (x_B,y_B), (x_E,y_B), (x_E,y_U), (x_U,y_U), (x_v,0)",
           "shoelace sum over the 8 vertices above, using the values of x_0, x_s, x_B, x_E, x_U, x_v, y_B, y_U", a_half, "mm²")
    Aseg = c.step("Aseg", "Hub circular segment already counted in the hub (per stem root)", "A_{seg} = ½R_0^2(2φ_0 − sin 2φ_0)",
                  "0.5 × $R0^2 × (2 × $phi0 − sin(2 × $phi0))", R0 ** 2 / 2 * (2 * phi0 - math.sin(2 * phi0)), "mm²")
    c.step("Ap", "Initial port area", "A_p = πR_0^2 + N(2A_h − A_{seg})",
           "π × $R0^2 + $N × (2 × $Ahalf − $Aseg)", PI * R0 ** 2 + N * (2 * a_half - Aseg), "mm²")

    if N * 2 * phi0 >= 2 * PI:
        c.errors.append("Stem roots do not fit around the hub: N·t is too large for the hub circumference. Reduce N or t, or enlarge D₀.")
    # clearance between neighbouring forks: distance of the outline from the bisector between two stems
    bis = PI / N
    dmin = min(x * math.sin(bis) - y * math.cos(bis) for x, y in half[1:])
    if dmin <= 0:
        c.errors.append("Neighbouring forks overlap. Reduce N, the branch length L_b / foot length L_f, or the branch angle φ.")
    elif 2 * dmin < 1.0:
        c.warnings.append(f"Neighbouring forks are only {fnum(2 * dmin)} mm apart.")

    # ---- drawing: one continuous outline --------------------------------------------------
    def to_global(pt, a):
        ca, sa = math.cos(a), math.sin(a)
        return (pt[0] * ca - pt[1] * sa, pt[0] * sa + pt[1] * ca)

    right = [(x0, -t / 2), (xs, -t / 2), (xB, -yB), (xE, -yB), (xE, -yU), (xU, -yU)]
    left = [(xU, yU), (xE, yU), (xE, yB), (xB, yB), (xs, t / 2), (x0, t / 2)]
    pts = []
    for k in range(N):
        a = PI / 2 + 2 * PI * k / N
        local = right + [(xv, 0.0)] + left
        pts += [to_global(q, a) for q in local]
        a_from, a_to = a + phi0, a + 2 * PI / N - phi0
        n_arc = 48
        pts += [S.pol(R0, a_from + (a_to - a_from) * j / n_arc) for j in range(1, n_arc)]
    c.scene = {"ports": [{"type": "poly", "pts": pts}], "dim_angle": PI / 2 - PI / N}


# ======================================================================================
# 17. Sinusoidal
# ======================================================================================
@geometry("sinusoidal", 17, "Sinusoidal-Port Grain", "Wavy Circular Bore",
          "A continuous high-frequency sinusoid superimposed on a base circular port boundary.",
          [P("R0", "Mean base radius", "R_0", "mm", 17.0),
           P("A", "Wave amplitude", "A", "mm", 1.5),
           P("N", "Number of wave cycles", "N", "", 24, 1, 120, True)],
          count_label="N")
def g_sinusoidal(c):
    v = c.v
    R0, A, N = v["R0"], v["A"], v["N"]
    if A >= R0:
        raise InputError("Wave amplitude A must be smaller than the mean radius R₀.")
    r = lambda t: R0 + A * math.sin(N * t)
    dr = lambda t: A * N * math.cos(N * t)
    c.sec("Profile definition & web thickness", "§17")
    c.notes.append("Polar profile: r(θ) = R₀ + A sin(Nθ).")
    web_generic(c, "R_{max} = R_0 + A", "$R0 + $A", R0 + A, "w_{max} = R_{case} − (R_0 + A)", "$Rcase − ($R0 + $A)")
    c.step("Rmin", "Minimum port radius", "R_{min} = R_0 − A", "$R0 − $A", R0 - A)
    c.sec("Initial burning perimeter & port area", "§17")
    n = max(4000, 200 * N)
    c.step("P0", "Initial burning perimeter (exact integral)",
           "P_0 = ∫_0^{2π} √((R_0 + A sin(Nθ))^2 + (AN cos(Nθ))^2) dθ",
           f"∫_0^{{2π}} √(($R0 + $A sin($Nθ))^2 + ($A × $N cos($Nθ))^2) dθ   `[Simpson, n = {n}]`",
           polar_perimeter(r, dr, n))
    c.step("P0_approx", "Perimeter, closed-form approximation", "P_0 ≈ 2πR_0(1 + N^2A^2/(4R_0^2))",
           "2π × $R0 × (1 + $N^2 × $A^2 / (4 × $R0^2))", 2 * PI * R0 * (1 + N ** 2 * A ** 2 / (4 * R0 ** 2)))
    dev = abs(v["P0_approx"] - v["P0"]) / v["P0"] * 100
    c.notes.append(f"The closed-form perimeter approximation differs from the exact integral by {dev:.2f} %. "
                   "The exact integral value is used for all downstream results.")
    c.step("Ap", "Initial port area", "A_p = ½∫_0^{2π} r(θ)^2 dθ = π(R_0^2 + ½A^2)", "π × ($R0^2 + 0.5 × $A^2)",
           PI * (R0 ** 2 + 0.5 * A ** 2), "mm²")
    c.scene = {"ports": [{"type": "poly", "pts": S.polar_curve(r, n=max(1440, 60 * N))}]}


# ======================================================================================
# 18. Helical
# ======================================================================================
@geometry("helical", 18, "Helical Port", "3D Extruded Twisted Profile",
          "A non-circular base profile swept along the motor axis with a continuous helical twist.",
          [P("R0", "Base profile mean radius", "R_0", "mm", 14.0),
           P("A", "Base profile lobe amplitude", "A", "mm", 5.0),
           P("Nl", "Number of lobes in base profile", "N", "", 4, 2, 16, True),
           P("Phi", "Total axial twist over length", "Φ", "°", 45.0, 0.0, 3600.0)],
          count_label="Nl")
def g_helical(c):
    v = c.v
    R0, A, N, L = v["R0"], v["A"], v["Nl"], v["L"]
    if A >= R0:
        raise InputError("Lobe amplitude A must be smaller than the mean radius R₀.")
    r = lambda t: R0 + A * math.cos(N * t)
    dr = lambda t: -A * N * math.sin(N * t)
    c.sec("Base 2D profile", "§18 / §19")
    c.notes.append("Base cross-section: N-lobe polar profile r(θ) = R₀ + A cos(Nθ) (the petal form of §19), "
                   "twisted helically along the grain axis.")
    c.step("P2D", "2D cross-sectional perimeter of the base profile", "P_{2D} = ∫_0^{2π} √(r(θ)^2 + (dr/dθ)^2) dθ",
           "∫_0^{2π} √(($R0 + $A cos($Nlθ))^2 + ($A × $Nl sin($Nlθ))^2) dθ   `[Simpson, n = 4000]`", polar_perimeter(r, dr))
    c.step("Ap2D", "2D cross-sectional port area", "A_{p,2D} = π(R_0^2 + ½A^2)", "π × ($R0^2 + 0.5 × $A^2)",
           PI * (R0 ** 2 + 0.5 * A ** 2), "mm²")
    ds = lambda t: math.sqrt(r(t) ** 2 + dr(t) ** 2)
    rbar = simpson(lambda t: r(t) * ds(t), 0, 2 * PI) / v["P2D"]
    c.step("Rbar", "Mean radial distance of the burning surface", "R̄ = (1/P_{2D}) ∮ r ds",
           "(1/$P2D) × ∮ r ds   `[Simpson, n = 4000]`", rbar)
    c.sec("Dimensional constraints & web thickness", "§18")
    web_generic(c, "R_{max} = R_0 + A", "$R0 + $A", R0 + A, "w_{max} = R_{case} − R_{max}", "$Rcase − $Rmax")
    c.sec("Helix magnification, perimeter & burning surface", "§18")
    Ph = deg_to_rad(c, "Phi", "Φ", "Total axial twist")
    al = c.step("alpha", "Axial twist rate", "α = Φ / L", "$Phi_r / $L", Ph / L, "1/mm")
    k = c.step("kappa", "Helix surface magnification factor", "κ = √(1 + (αR̄)^2)", "√(1 + ($alpha × $Rbar)^2)",
               math.sqrt(1 + (al * rbar) ** 2), "")
    c.step("P0", "Effective initial burning perimeter", "P_{eff} = κ · P_{2D} = P_{2D}√(1 + (ΦR̄/L)^2)", "$kappa × $P2D", k * v["P2D"])
    c.step("Ap", "Initial port area (twist does not change the cross-section)", "A_p = A_{p,2D}", "$Ap2D", v["Ap2D"], "mm²")
    c.meta["helical"] = True
    base = S.polar_curve(r)
    ghost = S.rotate(base, Ph % (2 * PI / N))
    c.scene = {"ports": [{"type": "poly", "pts": base}], "ghosts": [ghost] if (Ph % (2 * PI / N)) > 1e-6 else [],
               "dim_angle": math.radians(20)}


# ======================================================================================
# 19. Leaf petal
# ======================================================================================
@geometry("petal", 19, "Leaf Petal Profile", "Petal-Profile Grain",
          "A flower-like boundary with curved, rounded outward petal tips and smooth inward necks.",
          [P("R0", "Mean base radius", "R_0", "mm", 15.0),
           P("A", "Petal radial amplitude", "A", "mm", 9.0),
           P("N", "Number of petals", "N", "", 5, 2, 24, True)],
          count_label="N")
def g_petal(c):
    v = c.v
    R0, A, N = v["R0"], v["A"], v["N"]
    if A >= R0:
        raise InputError("Petal amplitude A must be smaller than the mean radius R₀.")
    r = lambda t: R0 + A * math.cos(N * t)
    dr = lambda t: -A * N * math.sin(N * t)
    c.sec("Profile definition & web thickness", "§19")
    c.notes.append("Polar profile: r(θ) = R₀ + A cos(Nθ).")
    web_generic(c, "R_{max} = R_0 + A", "$R0 + $A", R0 + A, "w_{max} = R_{case} − (R_0 + A)", "$Rcase − ($R0 + $A)")
    c.step("Rmin", "Minimum inner neck radius", "R_{min} = R_0 − A", "$R0 − $A", R0 - A)
    c.sec("Initial burning perimeter & port area", "§19")
    c.step("P0", "Initial burning perimeter", "P_0 = ∫_0^{2π} √((R_0 + A cos(Nθ))^2 + (−AN sin(Nθ))^2) dθ",
           "∫_0^{2π} √(($R0 + $A cos($Nθ))^2 + ($A × $N sin($Nθ))^2) dθ   `[Simpson, n = 4000]`",
           polar_perimeter(r, dr))
    c.step("Ap", "Initial port area", "A_p = ½∫_0^{2π} (R_0 + A cos(Nθ))^2 dθ = π(R_0^2 + ½A^2)",
           "π × ($R0^2 + 0.5 × $A^2)", PI * (R0 ** 2 + 0.5 * A ** 2), "mm²")
    rot = lambda t: r(t - PI / 2)
    c.scene = {"ports": [{"type": "poly", "pts": S.polar_curve(rot)}], "dim_angle": math.radians(-20)}


# ======================================================================================
# 20. Star-polygon hybrid
# ======================================================================================
@geometry("hybrid", 20, "Star-Polygon Hybrid Port", "Rounded Lobes + Sharp Spikes",
          "A composite boundary alternating between rounded circular lobes and sharp triangular star spikes.",
          [P("N", "Number of lobe + spike pairs", "N", "", 5, 2, 16, True),
           P("Rc", "Lobe center radius", "R_c", "mm", 13.0),
           P("Rlobe", "Lobe radius", "R_{lobe}", "mm", 6.5),
           P("Rspike", "Spike tip radius", "R_{spike}", "mm", 26.0)],
          count_label="N")
def g_hybrid(c):
    v = c.v
    N, Rc, Rl, Rs = v["N"], v["Rc"], v["Rlobe"], v["Rspike"]
    if Rs <= Rc:
        raise InputError("Spike tip radius R_spike must be larger than the lobe center radius R_c.")
    c.notes.append("Construction used for the exposed terms: a core circle of radius R_c; N circular lobes of radius "
                   "R_lobe centred on the core at θ = 2πk/N; N triangular spikes with tip at R_spike (θ = 2π(k+½)/N) "
                   "whose flanks start at the neighbouring lobe centres. Exposed lengths and areas are evaluated "
                   "numerically along the port boundary (36 000-point polar sweep).")
    lobes = [2 * PI * k / N for k in range(N)]
    spikes = [2 * PI * (k + 0.5) / N for k in range(N)]
    flanks = []
    for k, ts in enumerate(spikes):
        A = S.pol(Rs, ts)
        for nb in (ts - PI / N, ts + PI / N):
            flanks.append((k, S.pol(Rc, nb), A))

    def radius(t):
        ux, uy = math.cos(t), math.sin(t)
        best, who = Rc, ("core", -1)
        for k, tl in enumerate(lobes):
            d = t - tl
            dp = Rc * math.sin(d)
            if abs(dp) <= Rl:
                rr = Rc * math.cos(d) + math.sqrt(Rl * Rl - dp * dp)
                if rr > best:
                    best, who = rr, ("lobe", k)
        for k, B, A in flanks:
            dx, dy = A[0] - B[0], A[1] - B[1]
            det = -ux * dy + dx * uy
            if abs(det) < 1e-12:
                continue
            tt = (-B[0] * dy + dx * B[1]) / det
            ss = (ux * B[1] - uy * B[0]) / det
            if -1e-9 <= ss <= 1 + 1e-9 and tt > best:
                best, who = tt, ("spike", k)
        return best, who

    n = 2 * N * 3000
    pts, owners = [], []
    for i in range(n):
        t = 2 * PI * i / n
        rr, who = radius(t)
        pts.append(S.pol(rr, t))
        owners.append(who[0])
    per = {"lobe": 0.0, "spike": 0.0, "core": 0.0}
    area = {"lobe": 0.0, "spike": 0.0, "core": 0.0}
    for i in range(n):
        p1, p2 = pts[i - 1], pts[i]
        tm = 2 * PI * (i - 0.5) / n
        _, who = radius(tm)
        per[who[0]] += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        r1, r2 = math.hypot(*p1), math.hypot(*p2)
        area[who[0]] += 0.5 * (0.5 * (r1 * r1 + r2 * r2) - Rc * Rc) * (2 * PI / n)

    c.sec("Exposed boundary terms (numerical)", "§20")
    c.step("Slobe", "Exposed arc length of each circular lobe", "S_{lobe} = (1/N) Σ (lobe-owned boundary length)",
           "(numerical sweep) / $N", per["lobe"] / N)
    c.step("Lspike", "Exposed straight flank length of each spike", "L_{spike} = (1/2N) Σ (spike-owned boundary length)",
           "(numerical sweep) / (2 × $N)", per["spike"] / (2 * N))
    c.step("Acore", "Core area", "A_{core} = πR_c^2", "π × $Rc^2", PI * Rc ** 2, "mm²")
    c.step("Alobe", "Exposed area of each lobe (outside the core)", "A_{lobe,exposed} = (1/N) ∫_{lobe} ½(r^2 − R_c^2) dθ",
           "(numerical sweep) / $N", area["lobe"] / N, "mm²")
    c.step("Aspike", "Exposed area of each spike (outside core & lobes)", "A_{spike,exposed} = (1/N) ∫_{spike} ½(r^2 − R_c^2) dθ",
           "(numerical sweep) / $N", area["spike"] / N, "mm²")
    c.sec("Dimensional constraints & web thickness", "§20")
    web_generic(c, "R_{max} = max(R_{spike}, R_c + R_{lobe})", "max($Rspike, $Rc + $Rlobe)", max(Rs, Rc + Rl))
    c.sec("Initial burning perimeter & port area", "§20")
    p0 = N * v["Slobe"] + 2 * N * v["Lspike"]
    if per["core"] > 1e-6:
        c.step("Score", "Exposed core arc length (total)", "S_{core}", "(numerical sweep)", per["core"])
        c.warnings.append("Part of the core circle is exposed between lobes and spikes; its length is added to P₀. "
                          "Increase R_spike or R_lobe to close the gap.")
        c.step("P0", "Initial burning perimeter", "P_0 = N · S_{lobe} + 2N · L_{spike} + S_{core}",
               "$N × $Slobe + 2 × $N × $Lspike + $Score", p0 + per["core"])
    else:
        c.step("P0", "Initial burning perimeter", "P_0 = N · S_{lobe} + 2N · L_{spike}", "$N × $Slobe + 2 × $N × $Lspike", p0)
    c.step("Ap", "Initial port area", "A_p = A_{core} + N · A_{lobe,exposed} + N · A_{spike,exposed}",
           "$Acore + $N × $Alobe + $N × $Aspike", v["Acore"] + N * v["Alobe"] + N * v["Aspike"], "mm²")
    if v["Lspike"] <= 1e-6:
        c.warnings.append("Spikes are hidden inside the lobes (no exposed flank). Increase R_spike.")
    rot = PI / 2
    c.scene = {"ports": [{"type": "poly", "pts": S.rotate(pts[::6], rot)}], "dim_angle": math.radians(55)}


# ======================================================================================
# 21. Cassini oval
# ======================================================================================
@geometry("cassini", 21, "Infinity / Cassini-Oval Profile", "Waisted Quartic Oval",
          "A continuous waisted Cassini oval: a lemniscate-like figure-eight boundary with a finite central neck.",
          [P("a", "Half-focal separation", "a", "mm", 14.0),
           P("b", "Radius-product constant (b > a)", "b", "mm", 16.0)])
def g_cassini(c):
    v = c.v
    a, b = v["a"], v["b"]
    if b <= a:
        raise InputError("Cassini oval requires b > a for a single continuous loop.")

    def r(t):
        inner = b ** 4 - a ** 4 * math.sin(2 * t) ** 2
        return math.sqrt(a * a * math.cos(2 * t) + math.sqrt(max(inner, 0.0)))

    c.sec("Profile definition & web thickness", "§21")
    c.notes.append("Polar profile: r(θ) = √(a² cos 2θ + √(b⁴ − a⁴ sin² 2θ)).")
    c.step("Rmax", "Maximum horizontal extent (θ = 0, π)", "R_{max} = √(a^2 + b^2)", "√($a^2 + $b^2)", math.sqrt(a * a + b * b))
    c.step("Rmin", "Minimum central waist half-width (θ = ±π/2)", "R_{min} = √(b^2 − a^2)", "√($b^2 − $a^2)", math.sqrt(b * b - a * a))
    c.step("w", "Web thickness", "w_{max} = R_{case} − √(a^2 + b^2)", "$Rcase − $Rmax", v["Rcase"] - v["Rmax"])
    c.sec("Initial burning perimeter & port area", "§21")
    c.step("P0", "Initial burning perimeter", "P_0 = ∫_0^{2π} √(r(θ)^2 + (dr/dθ)^2) dθ",
           "r(θ) = √($a^2 cos 2θ + √($b^4 − $a^4 sin^2 2θ));  ∫_0^{2π} √(r^2 + r′^2) dθ   `[Simpson, n = 4000]`",
           polar_perimeter(r, num_deriv(r)))
    c.step("Ap", "Initial port area", "A_p = ½∫_0^{2π} r(θ)^2 dθ", "½ ∫_0^{2π} r(θ)^2 dθ   `[Simpson, n = 4000]`",
           polar_area(r), "mm²")
    if b < a * SQ2:
        c.notes.append("b < √2·a: the oval has a concave waist (peanut / infinity shape).")
    c.scene = {"ports": [{"type": "poly", "pts": S.polar_curve(r)}], "dim_angle": math.radians(40)}


# --------------------------------------------------------------------------------------
# Order the catalogue by figure number
# --------------------------------------------------------------------------------------
GEOMETRIES.sort(key=lambda g: g["fig"])


# ======================================================================================
# Public API
# ======================================================================================
def _coerce(param, raw):
    if raw is None or raw == "":
        raise InputError(f"{param['label']} is required.")
    try:
        x = float(raw)
    except (TypeError, ValueError):
        raise InputError(f"{param['label']} must be a number.")
    if not math.isfinite(x):
        raise InputError(f"{param['label']} must be a finite number.")
    if param.get("integer"):
        if abs(x - round(x)) > 1e-9:
            raise InputError(f"{param['label']} must be a whole number.")
        x = int(round(x))
    mn, mx = param.get("min"), param.get("max")
    if mn is not None:
        if param.get("integer") or param["unit"] == "°":
            if x < mn:
                raise InputError(f"{param['label']} must be at least {mn:g}.")
        elif mn == 0.0 and x < 0:
            raise InputError(f"{param['label']} cannot be negative.")
        elif mn > 0 and x <= 0:
            raise InputError(f"{param['label']} must be greater than 0.")
        elif mn > 0 and x < mn:
            raise InputError(f"{param['label']} must be at least {mn:g}.")
    if param["key"] not in ("rf", "xc", "e", "Rc", "Phi") and not param.get("integer") and param["unit"] in ("mm",) and x <= 0:
        raise InputError(f"{param['label']} must be greater than 0.")
    if mx is not None and x > mx:
        raise InputError(f"{param['label']} must be at most {mx:g}.")
    return x


def solve(gid, raw):
    """Solve a geometry. `raw` is a dict of user inputs (strings or numbers)."""
    if gid not in GEOM_BY_ID:
        raise InputError(f"Unknown grain geometry '{gid}'.")
    g = GEOM_BY_ID[gid]
    c = Calc()
    inputs = []
    for p in COMMON_PARAMS + g["params"]:
        val = _coerce(p, raw.get(p["key"]))
        c.put(p["key"], val, 0 if isinstance(val, int) else 3)
        inputs.append({"key": p["key"], "label": p["label"], "sym": p["sym"], "unit": p["unit"],
                       "value": val, "value_str": fnum(val, 0 if isinstance(val, int) else 3)})

    prop_id = str(raw.get("prop") or "KNSU")
    prop = PROP_BY_ID.get(prop_id, PROP_BY_ID["CUSTOM"])
    rho = _coerce(P("rho", "Propellant density", "ρ", "g/cm³", prop["rho"], 0.1), raw.get("rho", prop["rho"]))
    c.put("rho", rho, 3)
    prop_name = prop["name"] if prop_id != "CUSTOM" else (str(raw.get("prop_name") or "").strip() or "Custom propellant")
    inputs.append({"key": "prop", "label": "Propellant type", "sym": "", "unit": "", "value": prop_name, "value_str": prop_name})
    inputs.append({"key": "rho", "label": "Propellant density", "sym": "ρ", "unit": "g/cm³", "value": rho, "value_str": fnum(rho, 3)})

    c.sec("Grain envelope", "Fundamental equations")
    R = c.step("Rcase", "Grain outer radius (casing inner radius)", "R_{case} = D_{OD} / 2", "$OD / 2", c.v["OD"] / 2)
    c.step("Acase", "Outer casing cross-sectional area", "A_{case} = πR_{case}^2 = (π/4)D_{case}^2", "π × $Rcase^2", PI * R ** 2, "mm²")

    g["solver"](c)

    v = c.v
    # Fundamental relations
    c.sec("Fundamental motor design equations", "Fundamental equations")
    Ag = c.step("Ag", "Propellant grain cross-sectional area", "A_g = πR_{case}^2 − A_p", "π × $Rcase^2 − $Ap",
                PI * R ** 2 - v["Ap"], "mm²")
    c.step("Vf", "Volumetric loading fraction", "V_f = (1 − A_p/(πR_{case}^2)) × 100%", "(1 − $Ap / (π × $Rcase^2)) × 100",
           (1 - v["Ap"] / (PI * R ** 2)) * 100, "%")
    c.sec("Grain volume, mass & initial burning surface", "Standard relations")
    Vg = c.step("Vg", "Propellant volume", "V_g = A_g · L", "$Ag × $L", Ag * v["L"], "mm³")
    c.step("Vg_cm3", "Propellant volume", "V_g [cm^3] = V_g [mm^3] / 1000", "$Vg / 1000", Vg / 1000, "cm³")
    c.step("m", "Propellant mass", "m = ρ · V_g", "$rho × $Vg_cm3", rho * Vg / 1000, "g")
    if c.meta.get("helical"):
        c.step("Ab", "Total 3D burning surface area", "A_b = κ · P_{2D} · L", "$kappa × $P2D × $L", v["kappa"] * v["P2D"] * v["L"], "mm²")
    else:
        c.step("Ab", "Initial port burning surface (ends inhibited)", "A_b = P_0 · L", "$P0 × $L", v["P0"] * v["L"], "mm²")

    # Generic checks
    if v["Rmax"] >= R:
        c.errors.append(f"The port extends to the casing: R_max = {fnum(v['Rmax'])} mm ≥ R_case = {fnum(R)} mm. "
                        "Reduce the port dimensions or increase the grain OD.")
    elif v["w"] <= 0:
        c.errors.append("Web thickness is zero or negative. Reduce the port dimensions.")
    elif v["w"] < 0.08 * R:
        c.warnings.append(f"Thin web: {fnum(v['w'])} mm is under 8 % of the grain radius. Check structural margin.")
    if v["Ap"] <= 0:
        c.errors.append("Computed port area is not positive; check the inputs.")
    if v["P0"] <= 0:
        c.errors.append("Computed burning perimeter is not positive; check the inputs.")
    if v["Vf"] < 50 and v["Vf"] > 0:
        c.warnings.append(f"Low volumetric loading ({v['Vf']:.1f} %). Most motors target 70–90 %.")

    web_sym = c.meta.get("web_sym", "w_{max}")
    summary = [
        {"key": "Rmax", "label": "Maximum port radius", "sym": "R_{max}", "unit": "mm"},
        {"key": "w", "label": "Web thickness", "sym": web_sym, "unit": "mm"},
        {"key": "P0", "label": "Initial burning perimeter", "sym": "P_{eff}" if c.meta.get("helical") else "P_0", "unit": "mm"},
        {"key": "Ap", "label": "Initial port area", "sym": "A_p", "unit": "mm²"},
        {"key": "Ag", "label": "Grain cross-section area", "sym": "A_g", "unit": "mm²"},
        {"key": "Vf", "label": "Volumetric loading", "sym": "V_f", "unit": "%"},
        {"key": "m", "label": "Propellant mass", "sym": "m", "unit": "g"},
        {"key": "Ab", "label": "Initial burning surface", "sym": "A_b", "unit": "mm²"},
    ]
    for s in summary:
        val = v[s["key"]]
        s["value"] = val
        s["value_str"] = fnum(val, UNIT_DIGITS.get(s["unit"], 3))

    scene = dict(c.scene or {})
    scene.update({"R_case": R, "R_max": v["Rmax"], "web": v["w"], "web_sym": web_sym, "OD": v["OD"]})

    return {
        "app": APP_NAME,
        "geometry": public_geometry(g),
        "inputs": inputs,
        "propellant": prop_name,
        "sections": c.sections,
        "summary": summary,
        "errors": c.errors,
        "warnings": c.warnings,
        "notes": c.notes,
        "ok": not c.errors,
        "scene": scene,
        "reference": REFERENCE,
    }


def public_geometry(g):
    return {k: g[k] for k in ("id", "fig", "name", "subtitle", "description", "params", "count_label")}


def catalogue():
    return {
        "app": APP_NAME,
        "common": COMMON_PARAMS,
        "propellants": PROPELLANTS,
        "geometries": [public_geometry(g) for g in GEOMETRIES],
        "reference": REFERENCE,
    }


def defaults(gid):
    g = GEOM_BY_ID[gid]
    d = {p["key"]: p["default"] for p in COMMON_PARAMS + g["params"]}
    d["prop"] = "KNSU"
    d["rho"] = PROP_BY_ID["KNSU"]["rho"]
    return d
