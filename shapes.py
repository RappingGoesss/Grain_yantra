"""Grain_yantra_1 - 2D shape helpers (all coordinates in mm, y axis up)."""

import math


def pol(r, a):
    return (r * math.cos(a), r * math.sin(a))


def add(p, q):
    return (p[0] + q[0], p[1] + q[1])


def circle_pts(cx, cy, r, n=180):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def rotate(pts, ang):
    c, s = math.cos(ang), math.sin(ang)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def radial_rect(angle, r1, r2, t):
    """Rectangle of width t lying along a ray at `angle`, from radius r1 to r2."""
    ux, uy = math.cos(angle), math.sin(angle)
    px, py = -uy * t / 2, ux * t / 2
    return [
        (r1 * ux + px, r1 * uy + py),
        (r2 * ux + px, r2 * uy + py),
        (r2 * ux - px, r2 * uy - py),
        (r1 * ux - px, r1 * uy - py),
    ]


def rect_from(p, angle, length, t, back=0.0):
    """Rectangle of width t starting at point p (optionally extended `back`) along `angle`."""
    ux, uy = math.cos(angle), math.sin(angle)
    px, py = -uy * t / 2, ux * t / 2
    sx, sy = p[0] - ux * back, p[1] - uy * back
    ex, ey = p[0] + ux * length, p[1] + uy * length
    return [(sx + px, sy + py), (ex + px, ey + py), (ex - px, ey - py), (sx - px, sy - py)]


def annular_sector(r_in, r_out, a0, a1, n=96):
    outer = [pol(r_out, a0 + (a1 - a0) * k / n) for k in range(n + 1)]
    inner = [pol(r_in, a1 - (a1 - a0) * k / n) for k in range(n + 1)]
    return outer + inner


def fillet_polygon(verts, r, n_arc=24):
    """Round every vertex of a convex CCW polygon with fillet radius r."""
    if r <= 0:
        return list(verts)
    out = []
    m = len(verts)
    for i in range(m):
        p0, p1, p2 = verts[i - 1], verts[i], verts[(i + 1) % m]
        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        u1 = (v1[0] / l1, v1[1] / l1)
        u2 = (v2[0] / l2, v2[1] / l2)
        cosb = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
        beta = math.acos(cosb)  # interior angle
        d = r / math.tan(beta / 2)
        bis = (u1[0] + u2[0], u1[1] + u2[1])
        lb = math.hypot(*bis)
        bis = (bis[0] / lb, bis[1] / lb)
        h = r / math.sin(beta / 2)
        c = (p1[0] + bis[0] * h, p1[1] + bis[1] * h)
        t1 = (p1[0] + u1[0] * d, p1[1] + u1[1] * d)
        t2 = (p1[0] + u2[0] * d, p1[1] + u2[1] * d)
        a1 = math.atan2(t1[1] - c[1], t1[0] - c[0])
        a2 = math.atan2(t2[1] - c[1], t2[0] - c[0])
        da = a2 - a1
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        for k in range(n_arc + 1):
            a = a1 + da * k / n_arc
            out.append((c[0] + r * math.cos(a), c[1] + r * math.sin(a)))
    return out


def fillet_corner(p0, p1, p2, r, n_arc=24):
    """Arc points that round the corner p1 (neighbours p0 before, p2 after); r = 0 keeps the sharp corner."""
    if r <= 0:
        return [p1]
    v1 = (p0[0] - p1[0], p0[1] - p1[1])
    v2 = (p2[0] - p1[0], p2[1] - p1[1])
    l1, l2 = math.hypot(*v1), math.hypot(*v2)
    u1 = (v1[0] / l1, v1[1] / l1)
    u2 = (v2[0] / l2, v2[1] / l2)
    beta = math.acos(max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1])))
    d = r / math.tan(beta / 2)
    bis = (u1[0] + u2[0], u1[1] + u2[1])
    lb = math.hypot(*bis)
    bis = (bis[0] / lb, bis[1] / lb)
    h = r / math.sin(beta / 2)
    c = (p1[0] + bis[0] * h, p1[1] + bis[1] * h)
    t1 = (p1[0] + u1[0] * d, p1[1] + u1[1] * d)
    t2 = (p1[0] + u2[0] * d, p1[1] + u2[1] * d)
    a1 = math.atan2(t1[1] - c[1], t1[0] - c[0])
    a2 = math.atan2(t2[1] - c[1], t2[0] - c[0])
    da = a2 - a1
    while da > math.pi:
        da -= 2 * math.pi
    while da < -math.pi:
        da += 2 * math.pi
    return [(c[0] + r * math.cos(a1 + da * k / n_arc), c[1] + r * math.sin(a1 + da * k / n_arc)) for k in range(n_arc + 1)]


def polar_curve(f, n=1440, extra=()):
    angles = sorted(set([2 * math.pi * k / n for k in range(n)] + [a % (2 * math.pi) for a in extra]))
    return [pol(f(a), a) for a in angles]


def poly_area(pts):
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i - 1]
        x2, y2 = pts[i]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def poly_perimeter(pts):
    return sum(math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(len(pts)))
