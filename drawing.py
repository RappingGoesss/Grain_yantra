"""Grain_yantra_1 - 2D cross-section drawing.

A solved scene (ports in mm) is turned into a list of renderer-neutral primitives,
then rendered to SVG here, or to PDF by report.py. Port unions are drawn with the
two-pass technique: every port shape is first stroked with a double-width line, then
all port shapes are filled. Internal boundaries are covered; only the outline of the
union stays visible, exactly as a machined port would look.
"""

import html
import itertools
import math

from . import markup
from . import shapes as S

INK = "#1B2533"
CASE = "#B9C4D1"
GRAIN = "#E3E9F0"
HATCH = "#97A8BC"
PORT = "#FFFFFF"
DIM = "#B23A2E"
CENTER = "#6C7A8C"
GHOST = "#55657A"

_ids = itertools.count(1)


def _arrow(tip, direction, s, color):
    ux, uy = direction
    l = math.hypot(ux, uy) or 1.0
    ux, uy = ux / l, uy / l
    L, W = 2.6 * s, 0.85 * s
    bx, by = tip[0] - ux * L, tip[1] - uy * L
    return {"op": "path", "pts": [tip, (bx - uy * W, by + ux * W), (bx + uy * W, by - ux * W)], "closed": True,
            "fill": color, "stroke": None, "lw": 0}


def _fmt(x):
    return f"{x:.3f}"


def build(scene, annotate=True):
    R = scene["R_case"]
    s = R / 50.0
    prims = []
    wall = R + 2.2 * s
    prims.append({"op": "circle", "c": (0, 0), "r": wall, "fill": CASE, "stroke": INK, "lw": 0.5 * s})
    prims.append({"op": "circle", "c": (0, 0), "r": R, "fill": "hatch", "stroke": INK, "lw": 0.45 * s})

    ports = scene.get("ports", [])
    for p in ports:
        st = {"fill": None, "stroke": INK, "lw": 1.0 * s}
        if p["type"] == "circle":
            prims.append(dict(op="circle", c=p["c"], r=p["r"], **st))
        else:
            prims.append(dict(op="path", pts=p["pts"], closed=True, **st))
    for p in ports:
        st = {"fill": PORT, "stroke": None, "lw": 0}
        if p["type"] == "circle":
            prims.append(dict(op="circle", c=p["c"], r=p["r"], **st))
        else:
            prims.append(dict(op="path", pts=p["pts"], closed=True, **st))
    for isl in scene.get("islands", []):
        prims.append({"op": "circle", "c": isl["c"], "r": isl["r"], "fill": "hatch", "stroke": None, "lw": 0})
        n = 40
        arc = [(isl["c"][0] + isl["r"] * math.cos(isl["a0"] + (isl["a1"] - isl["a0"]) * k / n),
                isl["c"][1] + isl["r"] * math.sin(isl["a0"] + (isl["a1"] - isl["a0"]) * k / n)) for k in range(n + 1)]
        prims.append({"op": "path", "pts": arc, "closed": False, "fill": None, "stroke": INK, "lw": 0.5 * s})
    for g in scene.get("ghosts", []):
        prims.append({"op": "path", "pts": g, "closed": True, "fill": None, "stroke": GHOST, "lw": 0.35 * s,
                      "dash": [1.6 * s, 1.1 * s]})

    ext = wall + 4 * s
    cdash = [5 * s, 1.2 * s, 1.0 * s, 1.2 * s]
    prims.append({"op": "path", "pts": [(-ext, 0), (ext, 0)], "closed": False, "fill": None, "stroke": CENTER,
                  "lw": 0.2 * s, "dash": cdash})
    prims.append({"op": "path", "pts": [(0, -ext), (0, ext)], "closed": False, "fill": None, "stroke": CENTER,
                  "lw": 0.2 * s, "dash": cdash})

    if annotate:
        rmax = scene["R_max"]
        ang = scene.get("dim_angle", math.radians(40))
        u = (math.cos(ang), math.sin(ang))
        if 0 < rmax < R:
            prims.append({"op": "circle", "c": (0, 0), "r": rmax, "fill": None, "stroke": DIM, "lw": 0.3 * s,
                          "dash": [1.4 * s, 0.9 * s]})
        rm = max(0.0, min(rmax, R))
        p_rm = S.pol(rm, ang)
        p_R = S.pol(R, ang)
        prims.append({"op": "path", "pts": [(0, 0), p_rm], "closed": False, "fill": None, "stroke": DIM, "lw": 0.32 * s})
        prims.append(_arrow(p_rm, u, s, DIM))
        if rmax < R:
            prims.append({"op": "path", "pts": [p_rm, p_R], "closed": False, "fill": None, "stroke": DIM, "lw": 0.32 * s})
            if (R - rm) > 5.6 * s:
                prims.append(_arrow(p_R, u, s, DIM))
                prims.append(_arrow(p_rm, (-u[0], -u[1]), s, DIM))
        p_out = S.pol(wall + 7 * s, ang)
        side = 1 if u[0] >= 0 else -1
        p_shelf = (p_out[0] + side * 6 * s, p_out[1])
        prims.append({"op": "path", "pts": [p_R, p_out, p_shelf], "closed": False, "fill": None, "stroke": DIM,
                      "lw": 0.28 * s})
        tx = p_shelf[0] + side * 1.2 * s
        anchor = "start" if side > 0 else "end"
        fs = 3.4 * s
        prims.append({"op": "text", "x": tx, "y": p_shelf[1] + 0.6 * s, "s": f"R_{{max}} = {_fmt(rmax)} `mm`",
                      "size": fs, "anchor": anchor, "fill": DIM})
        prims.append({"op": "text", "x": tx, "y": p_shelf[1] - 4.6 * s,
                      "s": f"{scene.get('web_sym', 'w_{max}')} = {_fmt(scene['web'])} `mm`", "size": fs,
                      "anchor": anchor, "fill": DIM})
        # OD dimension
        y0 = -(wall + 7 * s)
        for x in (-R, R):
            prims.append({"op": "path", "pts": [(x, -2 * s), (x, y0 - 1.6 * s)], "closed": False, "fill": None,
                          "stroke": INK, "lw": 0.22 * s})
        prims.append({"op": "path", "pts": [(-R, y0), (R, y0)], "closed": False, "fill": None, "stroke": INK, "lw": 0.28 * s})
        prims.append(_arrow((-R, y0), (-1, 0), s, INK))
        prims.append(_arrow((R, y0), (1, 0), s, INK))
        prims.append({"op": "text", "x": 0, "y": y0 - 5.2 * s, "s": f"Ø D_{{OD}} = {_fmt(scene['OD'])} `mm`",
                      "size": fs, "anchor": "middle", "fill": INK})
    return prims


def _text_width(s_markup, size):
    w = 0.0
    for text, style, level in markup.parse(s_markup):
        k = 0.7 if level else 1.0
        w += len(text) * 0.56 * size * k
    return w


def bbox(prims):
    xs, ys = [], []
    for p in prims:
        if p["op"] == "circle":
            r = p["r"] + p.get("lw", 0)
            xs += [p["c"][0] - r, p["c"][0] + r]
            ys += [p["c"][1] - r, p["c"][1] + r]
        elif p["op"] == "path":
            for x, y in p["pts"]:
                xs.append(x)
                ys.append(y)
        elif p["op"] == "text":
            w = _text_width(p["s"], p["size"])
            x0 = p["x"] - (w if p["anchor"] == "end" else w / 2 if p["anchor"] == "middle" else 0)
            xs += [x0, x0 + w]
            ys += [p["y"] - 0.35 * p["size"], p["y"] + p["size"]]
    return min(xs), min(ys), max(xs), max(ys)


# --------------------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------------------
def _svg_text(p):
    size = p["size"]
    out = []
    dy_state = 0.0
    for text, style, level in markup.parse(p["s"]):
        target = {0: 0.0, -1: 0.3 * size, 1: -0.38 * size}[level]
        dy = target - dy_state
        dy_state = target
        attrs = []
        if dy:
            attrs.append(f'dy="{dy:.3f}"')
        if level:
            attrs.append(f'font-size="{size * 0.7:.3f}"')
        if style == "it":
            attrs.append('font-style="italic" font-family="Cambria Math, Cambria, \'Times New Roman\', serif"')
        elif style == "sym":
            attrs.append('font-family="Cambria Math, Cambria, \'Times New Roman\', serif"')
        out.append(f"<tspan {' '.join(attrs)}>{html.escape(text)}</tspan>")
    return (f'<text x="{p["x"]:.3f}" y="{-p["y"]:.3f}" font-size="{size:.3f}" fill="{p["fill"]}" '
            f'text-anchor="{p["anchor"]}" font-family="Bahnschrift, \'Segoe UI\', Arial, sans-serif">' + "".join(out) + "</text>")


def to_svg(prims, pad=None, css_class="gy-drawing", title=None):
    uid = f"h{next(_ids)}"
    x0, y0, x1, y1 = bbox(prims)
    span = max(x1 - x0, y1 - y0)
    pad = span * 0.03 if pad is None else pad
    x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
    R = None
    for p in prims:
        if p["op"] == "circle" and p.get("fill") == "hatch":
            R = p["r"]
            break
    s = (R or 50) / 50.0
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" class="{css_class}" viewBox="{x0:.3f} {-y1:.3f} {x1 - x0:.3f} {y1 - y0:.3f}" '
           f'role="img" preserveAspectRatio="xMidYMid meet">']
    if title:
        out.append(f"<title>{html.escape(title)}</title>")
    hs = 2.3 * s
    out.append(f'<defs><pattern id="{uid}" patternUnits="userSpaceOnUse" width="{hs:.3f}" height="{hs:.3f}" '
               f'patternTransform="rotate(45)"><rect width="{hs:.3f}" height="{hs:.3f}" fill="{GRAIN}"/>'
               f'<line x1="0" y1="0" x2="0" y2="{hs:.3f}" stroke="{HATCH}" stroke-width="{0.32 * s:.3f}"/></pattern></defs>')
    for p in prims:
        if p["op"] == "text":
            out.append(_svg_text(p))
            continue
        fill = p.get("fill")
        fill_attr = f"url(#{uid})" if fill == "hatch" else (fill or "none")
        stroke = p.get("stroke")
        st = f'fill="{fill_attr}"'
        if stroke:
            st += f' stroke="{stroke}" stroke-width="{p["lw"]:.3f}" stroke-linejoin="round" stroke-linecap="round"'
            if p.get("dash"):
                st += f' stroke-dasharray="{" ".join(f"{d:.3f}" for d in p["dash"])}"'
        if p["op"] == "circle":
            out.append(f'<circle cx="{p["c"][0]:.3f}" cy="{-p["c"][1]:.3f}" r="{p["r"]:.3f}" {st}/>')
        else:
            d = "M" + " L".join(f"{x:.3f},{-y:.3f}" for x, y in p["pts"]) + (" Z" if p.get("closed") else "")
            out.append(f'<path d="{d}" {st}/>')
    out.append("</svg>")
    return "".join(out)


def scene_svg(scene, annotate=True, title=None):
    return to_svg(build(scene, annotate), title=title)
