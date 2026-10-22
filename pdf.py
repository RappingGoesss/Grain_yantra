"""Grain_yantra_1 - a small dependency-free PDF writer.

Uses only the PDF standard-14 fonts (Helvetica, Times, Symbol) so no font files
or third-party packages are needed. Coordinates passed to the public methods are
in points with the origin at the TOP-left of the page (y grows downward).
"""

import math
import zlib

from . import markup

PAGE_W, PAGE_H = 595.28, 841.89

FONTS = {
    "F1": "Helvetica",
    "F2": "Helvetica-Bold",
    "F3": "Times-Italic",
    "F4": "Times-Roman",
    "F5": "Symbol",
    "F6": "Times-Bold",
}

SYMBOL_MAP = {
    "α": 0x61, "β": 0x62, "γ": 0x67, "δ": 0x64, "ε": 0x65, "ζ": 0x7A, "η": 0x68, "θ": 0x71, "ι": 0x69,
    "κ": 0x6B, "λ": 0x6C, "μ": 0x6D, "ν": 0x6E, "ξ": 0x78, "π": 0x70, "ρ": 0x72, "σ": 0x73, "τ": 0x74,
    "υ": 0x75, "φ": 0x66, "ϕ": 0x66, "χ": 0x63, "ψ": 0x79, "ω": 0x77, "Γ": 0x47, "Δ": 0x44, "Θ": 0x51,
    "Λ": 0x4C, "Ξ": 0x58, "Π": 0x50, "Σ": 0x53, "Φ": 0x46, "Ψ": 0x59, "Ω": 0x57,
    "−": 0x2D, "·": 0xD7, "×": 0xB4, "≈": 0xBB, "√": 0xD6, "∫": 0xF2, "∮": 0xF2, "≤": 0xA3, "≥": 0xB3,
    "±": 0xB1, "∞": 0xA5, "°": 0xB0, "∑": 0xE5, "∂": 0xB6, "≠": 0xB9, "′": 0xA2, "→": 0xAE,
}
LEVEL_CHARS = {"²": ("2", "rm", 1), "³": ("3", "rm", 1), "⁴": ("4", "rm", 1), "₀": ("0", "rm", -1),
               "₁": ("1", "rm", -1), "₂": ("2", "rm", -1), "₃": ("3", "rm", -1)}
PLAIN_REPL = {"⁴": "^4", "₀": "0", "₁": "1", "₂": "2", "→": "->", "≥": ">=", "≤": "<="}

HELV = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191, "(": 333, ")": 333, "*": 389,
    "+": 584, ",": 278, "-": 333, ".": 278, "/": 278, ":": 278, ";": 278, "<": 584, "=": 584, ">": 584, "?": 556,
    "@": 1015, "[": 278, "\\": 278, "]": 278, "^": 469, "_": 556, "`": 333, "{": 334, "|": 260, "}": 334, "~": 584,
    "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722, "I": 278, "J": 500, "K": 667,
    "L": 556, "M": 833, "N": 722, "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611, "U": 722, "V": 667,
    "W": 944, "X": 667, "Y": 667, "Z": 611, "a": 556, "b": 556, "c": 500, "d": 556, "e": 556, "f": 278, "g": 556,
    "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833, "n": 556, "o": 556, "p": 556, "q": 556, "r": 333,
    "s": 500, "t": 278, "u": 556, "v": 500, "w": 722, "x": 500, "y": 500, "z": 500,
}
TIMES = {
    " ": 250, "(": 333, ")": 333, ",": 250, ".": 250, "-": 333, "+": 564, "=": 564, "/": 278, ":": 278, ";": 278,
    "[": 333, "]": 333, "%": 833, "'": 180,
    "A": 722, "B": 667, "C": 667, "D": 722, "E": 611, "F": 556, "G": 722, "H": 722, "I": 333, "J": 389, "K": 722,
    "L": 611, "M": 889, "N": 722, "O": 722, "P": 556, "Q": 722, "R": 667, "S": 556, "T": 611, "U": 722, "V": 722,
    "W": 944, "X": 722, "Y": 722, "Z": 611, "a": 444, "b": 500, "c": 444, "d": 500, "e": 444, "f": 333, "g": 500,
    "h": 500, "i": 278, "j": 278, "k": 500, "l": 278, "m": 778, "n": 500, "o": 500, "p": 500, "q": 500, "r": 333,
    "s": 389, "t": 278, "u": 500, "v": 500, "w": 722, "x": 500, "y": 500, "z": 444,
}

FAMILIES = {
    "sans": {"it": "F1", "rm": "F1", "sym": "F5"},
    "sansb": {"it": "F2", "rm": "F2", "sym": "F5"},
    "math": {"it": "F3", "rm": "F4", "sym": "F5"},
    "mathb": {"it": "F6", "rm": "F6", "sym": "F5"},
    "label": {"it": "F3", "rm": "F1", "sym": "F5"},
}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _cw(font, ch):
    if font == "F5":
        return 550 if ch not in (0xD7,) else 250
    if font in ("F1", "F2"):
        w = HELV.get(ch, 556)
        return w * (1.06 if font == "F2" else 1.0)
    if ch.isdigit():
        return 500
    return TIMES.get(ch, 500)


def _encode_char(ch):
    """Return (byte, is_symbol) or None."""
    if ch in SYMBOL_MAP and not ch == "°":
        return SYMBOL_MAP[ch], True
    try:
        b = ch.encode("cp1252")
        if len(b) == 1:
            return b[0], False
    except UnicodeEncodeError:
        pass
    if ch in SYMBOL_MAP:
        return SYMBOL_MAP[ch], True
    return None


def _esc(bs):
    out = []
    for b in bs:
        if b in (0x28, 0x29, 0x5C):
            out.append("\\" + chr(b))
        elif b < 32 or b > 126:
            out.append("\\%03o" % b)
        else:
            out.append(chr(b))
    return "".join(out)


def runs_for(s, family="sans", plain=False):
    """Convert text to drawable segments: list of (font_id, bytes_list, chars, level)."""
    fam = FAMILIES[family]
    if plain:
        src = []
        for ch in s:
            if ch in LEVEL_CHARS:
                src.append(LEVEL_CHARS[ch])
            elif ch in PLAIN_REPL and _encode_char(ch) is None:
                for c2 in PLAIN_REPL[ch]:
                    src.append((c2, "rm", 0))
            else:
                src.append((ch, "rm", 0))
        mruns = [(c, st, lv) for c, st, lv in src]
    else:
        mruns = []
        for text, style, level in markup.parse(s):
            for ch in text:
                mruns.append((ch, style, level))
    segs = []
    for ch, style, level in mruns:
        if ch == "̄":
            segs.append(("BAR", [], ch, level))
            continue
        enc = _encode_char(ch)
        if enc is None:
            enc = (ord("?"), False)
        b, is_sym = enc
        font = "F5" if is_sym else fam[style if style in fam else "rm"]
        if style == "sym" and not is_sym:
            font = fam["rm"]
        if segs and segs[-1][0] == font and segs[-1][3] == level:
            segs[-1][1].append(b)
            segs[-1] = (font, segs[-1][1], segs[-1][2] + ch, level)
        else:
            segs.append((font, [b], ch, level))
    return segs


def measure(s, size, family="sans", plain=False):
    w = 0.0
    for font, bs, chars, level in runs_for(s, family, plain):
        if font == "BAR":
            continue
        k = 0.7 if level else 1.0
        for b, ch in zip(bs, chars):
            w += _cw(font, ch if font != "F5" else b) * size * k / 1000
    return w


class PDF:
    def __init__(self, title="", author=""):
        self.pages = []
        self.ops = None
        self.title = title
        self.author = author

    # ----------------------------------------------------------------- page
    def add_page(self):
        self.ops = []
        self.pages.append(self.ops)

    def raw(self, s):
        self.ops.append(s)

    @staticmethod
    def Y(y):
        return PAGE_H - y

    # ----------------------------------------------------------------- style
    def _stroke(self, color, lw, dash=None):
        r, g, b = hex_rgb(color)
        self.raw(f"{r:.3f} {g:.3f} {b:.3f} RG {lw:.3f} w")
        self.raw(("[" + " ".join(f"{d:.2f}" for d in dash) + "] 0 d") if dash else "[] 0 d")

    def _fill(self, color):
        r, g, b = hex_rgb(color)
        self.raw(f"{r:.3f} {g:.3f} {b:.3f} rg")

    # ----------------------------------------------------------------- shapes (top-down coords)
    def rect(self, x, y, w, h, fill=None, stroke=None, lw=0.5):
        if fill:
            self._fill(fill)
        if stroke:
            self._stroke(stroke, lw)
        op = "B" if fill and stroke else ("f" if fill else "S")
        self.raw(f"{x:.2f} {self.Y(y + h):.2f} {w:.2f} {h:.2f} re {op}")

    def line(self, x1, y1, x2, y2, color="#000000", lw=0.5, dash=None):
        self._stroke(color, lw, dash)
        self.raw(f"{x1:.2f} {self.Y(y1):.2f} m {x2:.2f} {self.Y(y2):.2f} l S")

    # ----------------------------------------------------------------- native (bottom-up) paths
    def path_native(self, pts, closed=True):
        s = [f"{pts[0][0]:.3f} {pts[0][1]:.3f} m"]
        for x, y in pts[1:]:
            s.append(f"{x:.3f} {y:.3f} l")
        if closed:
            s.append("h")
        return " ".join(s)

    def circle_native(self, cx, cy, r):
        k = 0.5522847498 * r
        return (f"{cx + r:.3f} {cy:.3f} m "
                f"{cx + r:.3f} {cy + k:.3f} {cx + k:.3f} {cy + r:.3f} {cx:.3f} {cy + r:.3f} c "
                f"{cx - k:.3f} {cy + r:.3f} {cx - r:.3f} {cy + k:.3f} {cx - r:.3f} {cy:.3f} c "
                f"{cx - r:.3f} {cy - k:.3f} {cx - k:.3f} {cy - r:.3f} {cx:.3f} {cy - r:.3f} c "
                f"{cx + k:.3f} {cy - r:.3f} {cx + r:.3f} {cy - k:.3f} {cx + r:.3f} {cy:.3f} c h")

    # ----------------------------------------------------------------- text
    def text(self, x, y, s, size=10, family="sans", color="#1B2533", align="left", plain=False, native=False):
        """Draw text with baseline at y (top-down unless native). Returns width."""
        w = measure(s, size, family, plain)
        if align == "center":
            x -= w / 2
        elif align == "right":
            x -= w
        yb = y if native else self.Y(y)
        r, g, b = hex_rgb(color)
        parts = [f"BT {r:.3f} {g:.3f} {b:.3f} rg 1 0 0 1 {x:.3f} {yb:.3f} Tm"]
        bars = []
        cx = x
        last_w = 0.0
        for font, bs, chars, level in runs_for(s, family, plain):
            if font == "BAR":
                bars.append((cx - last_w, cx))
                continue
            fs = size * (0.7 if level else 1.0)
            rise = {0: 0.0, -1: -0.22 * size, 1: 0.36 * size}[level]
            parts.append(f"/{font} {fs:.2f} Tf {rise:.2f} Ts ({_esc(bs)}) Tj")
            seg_w = 0.0
            for bb, ch in zip(bs, chars):
                cw = _cw(font, ch if font != "F5" else bb) * fs / 1000
                seg_w += cw
                last_w = cw
            cx += seg_w
        parts.append("0 Ts ET")
        self.raw(" ".join(parts))
        for x0, x1 in bars:
            self.raw(f"{r:.3f} {g:.3f} {b:.3f} RG {size * 0.05:.2f} w [] 0 d "
                     f"{x0 + size * 0.12:.2f} {yb + size * 0.74:.2f} m {x1 - size * 0.02:.2f} {yb + size * 0.74:.2f} l S")
        return w

    def fit_text(self, x, y, s, size, max_w, min_size=6.0, **kw):
        fam = kw.get("family", "sans")
        plain = kw.get("plain", False)
        w = measure(s, size, fam, plain)
        if w > max_w:
            size = max(min_size, size * max_w / w)
        return self.text(x, y, s, size, **kw), size

    def wrap(self, s, size, width, family="sans"):
        words = s.split(" ")
        lines, cur = [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if measure(t, size, family, plain=True) <= width or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        return lines

    # ----------------------------------------------------------------- output
    def output(self):
        objs = []

        def add(body):
            objs.append(body)
            return len(objs)

        font_ids = {}
        for fid, base in FONTS.items():
            enc = "" if base == "Symbol" else " /Encoding /WinAnsiEncoding"
            font_ids[fid] = add(f"<< /Type /Font /Subtype /Type1 /BaseFont /{base}{enc} >>".encode())
        font_res = " ".join(f"/{k} {v} 0 R" for k, v in font_ids.items())
        pages_id_placeholder = len(objs) + 1
        add(b"PAGES")  # placeholder
        page_ids = []
        for ops in self.pages:
            stream = zlib.compress("\n".join(ops).encode("latin-1"))
            cid = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
            pid = add((f"<< /Type /Page /Parent {pages_id_placeholder} 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
                       f"/Resources << /Font << {font_res} >> >> /Contents {cid} 0 R >>").encode())
            page_ids.append(pid)
        objs[pages_id_placeholder - 1] = (f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] "
                                          f"/Count {len(page_ids)} >>").encode()
        def pdfstr(t):
            return "(" + _esc(t.encode("cp1252", "replace")) + ")"
        info = add(f"<< /Title {pdfstr(self.title)} /Author {pdfstr(self.author)} /Producer (Grain_yantra_1) "
                   f"/Creator (Grain_yantra_1) >>".encode())
        cat = add(f"<< /Type /Catalog /Pages {pages_id_placeholder} 0 R >>".encode())
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
        for o in offsets:
            out += f"{o:010d} 00000 n \n".encode()
        out += f"trailer\n<< /Size {len(objs) + 1} /Root {cat} 0 R /Info {info} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(out)


# ----------------------------------------------------------------------------------------
# Render drawing primitives (mm, y-up) into a box on the current page
# ----------------------------------------------------------------------------------------
def draw_prims(pdf, prims, box, bbox, hatch_color, grain_color):
    bx, by, bw, bh = box
    x0, y0, x1, y1 = bbox
    k = min(bw / (x1 - x0), bh / (y1 - y0))
    ox = bx + (bw - (x1 - x0) * k) / 2
    oy = PAGE_H - (by + bh) + (bh - (y1 - y0) * k) / 2

    def T(p):
        return (ox + (p[0] - x0) * k, oy + (p[1] - y0) * k)

    R = None
    for p in prims:
        if p["op"] == "circle" and p.get("fill") == "hatch":
            R = p["r"]
            break
    s = (R or 50) / 50.0
    for p in prims:
        if p["op"] == "text":
            X, Y = T((p["x"], p["y"]))
            align = {"start": "left", "middle": "center", "end": "right"}[p["anchor"]]
            pdf.text(X, Y, p["s"], p["size"] * k, family="label", color=p["fill"], align=align, native=True)
            continue
        if p["op"] == "circle":
            c = T(p["c"])
            geom = pdf.circle_native(c[0], c[1], p["r"] * k)
        else:
            geom = pdf.path_native([T(q) for q in p["pts"]], p.get("closed", False))
        fill = p.get("fill")
        stroke = p.get("stroke")
        if fill == "hatch":
            pdf._fill(grain_color)
            pdf.raw(geom + " f")
            pdf.raw("q " + geom + " W n")
            hs = 2.3 * s * k
            if p["op"] == "circle":
                c = T(p["c"])
                rr = p["r"] * k
                lx0, ly0, lx1, ly1 = c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr
            else:
                pts = [T(q) for q in p["pts"]]
                lx0, ly0 = min(q[0] for q in pts), min(q[1] for q in pts)
                lx1, ly1 = max(q[0] for q in pts), max(q[1] for q in pts)
            pdf._stroke(hatch_color, 0.32 * s * k)
            span = (lx1 - lx0) + (ly1 - ly0)
            # 45° lines, anchored to a global grid so neighbouring hatched areas line up
            start = math.floor((lx0 - ly1) / hs) * hs
            t = start
            segs = []
            while t <= lx1 - ly0 + hs:
                segs.append(f"{t + ly0:.2f} {ly0:.2f} m {t + ly0 + span:.2f} {ly0 + span:.2f} l")
                t += hs
            pdf.raw(" ".join(segs) + " S Q")
            if stroke:
                pdf._stroke(stroke, p["lw"] * k, p.get("dash") and [d * k for d in p["dash"]])
                pdf.raw(geom + " S")
            continue
        if fill:
            pdf._fill(fill)
        if stroke:
            pdf._stroke(stroke, p["lw"] * k, p.get("dash") and [d * k for d in p["dash"]])
            pdf.raw("1 J 1 j")
        op = "B" if fill and stroke else ("f" if fill else "S")
        pdf.raw(geom + " " + op)
    return k
