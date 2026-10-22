"""Grain_yantra_1 - report generation (PDF and standalone HTML)."""

import datetime as _dt
import hashlib
import html
import json

from . import drawing, markup
from .engine import APP_NAME, REFERENCE
from .pdf import PDF, PAGE_H, PAGE_W, draw_prims, measure

INK = "#1B2533"
MUTED = "#5B6878"
RULE = "#C5CED8"
PAPER = "#F3F5F8"
RED = "#B23A2E"
AMBER = "#9A6200"
OK = "#2E6B4A"

ML, MR = 46.0, 46.0
CW = PAGE_W - ML - MR
TOP = 64.0
BOTTOM = PAGE_H - 58.0


def report_meta(result, raw):
    now = _dt.datetime.now()
    digest = hashlib.sha1(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()[:6].upper()
    g = result["geometry"]
    ref = f"GY1-{now:%Y%m%d}-{g['id'][:4].upper()}-{digest}"
    return {"ref": ref, "date": now.strftime("%d %b %Y, %H:%M"), "stamp": now.strftime("%Y%m%d_%H%M")}


def file_basename(result, meta):
    g = result["geometry"]
    return f"{APP_NAME}_Report_{g['name'].split(' /')[0].replace(' ', '_').replace('-', '_')}_{meta['stamp']}"


# ======================================================================================
# PDF
# ======================================================================================
class _Doc:
    def __init__(self, result, meta):
        self.r = result
        self.meta = meta
        g = result["geometry"]
        self.pdf = PDF(title=f"{APP_NAME} - {g['name']} grain report", author=APP_NAME)
        self.y = TOP
        self.new_page(first=True)

    def new_page(self, first=False):
        self.pdf.add_page()
        p = self.pdf
        g = self.r["geometry"]
        p.text(ML, 34, APP_NAME, 9, "sansb", INK, plain=True)
        p.text(PAGE_W - MR, 34, f"Grain geometry design report  |  Fig. {g['fig']}  {g['name']}", 8, "sans", MUTED, "right", plain=True)
        p.line(ML, 41, PAGE_W - MR, 41, INK, 0.8)
        self.y = TOP if not first else 58

    def ensure(self, h):
        if self.y + h > BOTTOM:
            self.new_page()

    def heading(self, num, title, sub=None, need=46):
        self.ensure(need)
        p = self.pdf
        self.y += 10
        p.text(ML, self.y + 12, f"{num}", 13, "sansb", RED, plain=True)
        p.text(ML + 22, self.y + 12, title, 13, "sansb", INK, plain=True)
        if sub:
            p.text(PAGE_W - MR, self.y + 12, sub, 8, "sans", MUTED, "right", plain=True)
        p.line(ML, self.y + 18, PAGE_W - MR, self.y + 18, RULE, 0.6)
        self.y += 28

    def para(self, text, size=9, color=INK, indent=0, gap=3, family="sans"):
        lines = self.pdf.wrap(text, size, CW - indent, family)
        for ln in lines:
            self.ensure(size + 4)
            self.pdf.text(ML + indent, self.y + size, ln, size, family, color, plain=True)
            self.y += size + 3.2
        self.y += gap

    # ------------------------------------------------------------------ blocks
    def title_block(self):
        p = self.pdf
        r = self.r
        g = r["geometry"]
        y0 = self.y
        h = 118
        p.rect(ML, y0, CW, h, stroke=INK, lw=1.0)
        split = ML + CW * 0.56
        p.line(split, y0, split, y0 + h, INK, 0.6)
        p.text(ML + 14, y0 + 34, APP_NAME, 25, "sansb", INK, plain=True)
        p.text(ML + 14, y0 + 52, "Solid propellant grain geometry design report", 10.5, "sans", MUTED, plain=True)
        p.line(ML + 14, y0 + 64, split - 14, y0 + 64, RULE, 0.6)
        p.text(ML + 14, y0 + 80, f"Fig. {g['fig']}", 9, "sansb", RED, plain=True)
        p.fit_text(ML + 52, y0 + 80, g["name"], 12, split - ML - 66, family="sansb", color=INK, plain=True)
        p.fit_text(ML + 52, y0 + 95, g["subtitle"], 9, split - ML - 66, family="sans", color=MUTED, plain=True)
        status_ok = r["ok"]
        st = "Design status: valid" if status_ok else f"Design status: {len(r['errors'])} issue(s) to resolve"
        p.text(ML + 14, y0 + 110, st, 8.5, "sansb", OK if status_ok else RED, plain=True)
        rows = [
            ("Report ref.", self.meta["ref"]),
            ("Date", self.meta["date"]),
            ("Propellant", r["propellant"]),
            ("Grain OD x length", f"{_inp(r, 'OD')} mm x {_inp(r, 'L')} mm"),
            ("Units", "mm, mm², mm³, g, rad"),
            ("Equations", "Reference formulation sheet"),
        ]
        rh = h / len(rows)
        for i, (k, v) in enumerate(rows):
            yy = y0 + i * rh
            if i:
                p.line(split, yy, ML + CW, yy, RULE, 0.5)
            p.text(split + 8, yy + rh / 2 + 3, k, 7.5, "sans", MUTED, plain=True)
            p.fit_text(split + 86, yy + rh / 2 + 3, v, 8.5, ML + CW - split - 94, family="sansb", color=INK, plain=True)
        self.y = y0 + h + 8

    def summary(self):
        p = self.pdf
        items = self.r["summary"]
        cols = 4
        cw = CW / cols
        ch = 50
        self.ensure(ch * 2 + 4)
        y0 = self.y
        for i, it in enumerate(items):
            cx = ML + (i % cols) * cw
            cy = y0 + (i // cols) * ch
            p.rect(cx, cy, cw, ch, fill=PAPER if (i // cols + i % cols) % 2 == 0 else "#FFFFFF", stroke=RULE, lw=0.5)
            p.fit_text(cx + 8, cy + 14, it["label"], 7.5, cw - 16, family="sans", color=MUTED, plain=True)
            p.text(cx + 8, cy + 34, it["sym"], 10, "math", INK)
            p.fit_text(cx + cw - 8, cy + 34, it["value_str"], 13, cw - 50, family="sansb", color=INK, align="right", plain=True)
            p.text(cx + cw - 8, cy + 45, it["unit"], 7.5, "sans", MUTED, "right", plain=True)
        self.y = y0 + ch * ((len(items) + cols - 1) // cols) + 6

    def inputs_table(self):
        p = self.pdf
        rows = self.r["inputs"]
        cols = [(ML, "Parameter"), (ML + 250, "Symbol"), (ML + 330, "Value"), (ML + 440, "Unit")]
        self.ensure(18 + 16 * 3)
        p.rect(ML, self.y, CW, 17, fill=INK)
        for x, t in cols:
            p.text(x + 8, self.y + 11.5, t, 8, "sansb", "#FFFFFF", plain=True)
        self.y += 17
        for i, row in enumerate(rows):
            self.ensure(16)
            if i % 2 == 0:
                p.rect(ML, self.y, CW, 16, fill=PAPER)
            p.fit_text(ML + 8, self.y + 11, row["label"], 8.5, 236, family="sans", color=INK, plain=True)
            if row["sym"]:
                p.text(ML + 258, self.y + 11.5, row["sym"], 10, "math", INK)
            p.fit_text(ML + 338, self.y + 11, row["value_str"], 8.5, 100, family="sansb", color=INK, plain=True)
            p.text(ML + 448, self.y + 11, row["unit"], 8.5, "sans", MUTED, plain=True)
            self.y += 16
        p.line(ML, self.y, ML + CW, self.y, INK, 0.6)
        self.y += 8

    def diagram(self):
        p = self.pdf
        r = self.r
        g = r["geometry"]
        h = 372
        self.ensure(h + 34)
        y0 = self.y
        p.rect(ML, y0, CW, h, fill="#FBFCFD", stroke=INK, lw=0.8)
        # zone ticks around the frame, like a drawing sheet
        for i in range(1, 6):
            x = ML + CW * i / 6
            p.line(x, y0, x, y0 + 6, INK, 0.5)
            p.line(x, y0 + h - 6, x, y0 + h, INK, 0.5)
        for i in range(1, 4):
            yy = y0 + h * i / 4
            p.line(ML, yy, ML + 6, yy, INK, 0.5)
            p.line(ML + CW - 6, yy, ML + CW, yy, INK, 0.5)
        prims = drawing.build(r["scene"], annotate=True)
        bb = drawing.bbox(prims)
        span = max(bb[2] - bb[0], bb[3] - bb[1]) * 0.03
        bb = (bb[0] - span, bb[1] - span, bb[2] + span, bb[3] + span)
        draw_prims(p, prims, (ML + 14, y0 + 14, CW - 28, h - 28), bb, drawing.HATCH, drawing.GRAIN)
        self.y = y0 + h + 13
        p.text(ML, self.y, f"Figure 1.  2D cross-sectional profile: {g['name']} ({g['subtitle']}).", 8.5, "sansb", INK, plain=True)
        self.y += 12
        p.text(ML, self.y, "Drawn to scale from the entered parameters. Hatched area: propellant. White: port. "
               "Red dashed circle: maximum port radius.", 7.5, "sans", MUTED, plain=True)
        self.y += 10

    def calculations(self):
        p = self.pdf
        num = 0
        for si, sec in enumerate(self.r["sections"], 1):
            self.ensure(30 + 54)
            self.y += 4
            p.text(ML, self.y + 10, f"4.{si}", 10, "sansb", RED, plain=True)
            p.text(ML + 28, self.y + 10, sec["title"], 10, "sansb", INK, plain=True)
            if sec.get("ref"):
                p.text(PAGE_W - MR, self.y + 10, f"Reference {sec['ref']}", 7.5, "sans", MUTED, "right", plain=True)
            self.y += 18
            for st in sec["steps"]:
                num += 1
                self.ensure(56)
                y = self.y
                p.text(ML, y + 9, f"{num:02d}", 8, "sansb", MUTED, plain=True)
                p.fit_text(ML + 28, y + 9, st["name"], 8.5, CW - 170, family="sansb", color=INK, plain=True)
                res = f"{st['value_str']} {st['unit']}".strip()
                p.fit_text(PAGE_W - MR, y + 23, res, 11, 150, family="sansb", color=INK, align="right", plain=True)
                p.fit_text(ML + 28, y + 24, st["formula"], 10.5, CW - 190, family="math", color=INK)
                if st["subst"]:
                    p.fit_text(ML + 28, y + 39, "= " + st["subst"], 9, CW - 40, family="math", color=MUTED, min_size=5.5)
                self.y = y + 46
                p.line(ML + 28, self.y - 2, PAGE_W - MR, self.y - 2, "#E1E6EC", 0.4)
            self.y += 4

    def checks(self):
        r = self.r
        if not (r["errors"] or r["warnings"] or r["notes"]):
            self.para("All dimensional checks passed. No warnings.", 9, OK)
            return
        for title, items, color in (("Errors", r["errors"], RED), ("Warnings", r["warnings"], AMBER), ("Notes", r["notes"], MUTED)):
            if not items:
                continue
            self.ensure(30)
            self.pdf.text(ML, self.y + 10, title, 9.5, "sansb", color, plain=True)
            self.y += 16
            for it in items:
                self.ensure(14)
                self.pdf.text(ML + 4, self.y + 9, "-", 9, "sans", color, plain=True)
                self.para(it, 8.8, INK, indent=14, gap=2)
            self.y += 4

    def method(self):
        items = [
            f"All geometry equations are taken from the reference document \"{REFERENCE}\"; the section of the reference "
            "used for each calculation block is noted beside it.",
            "Propellant volume, mass and burning surface use the standard relations V_g = A_g * L, m = rho * V_g and "
            "A_b = P_0 * L (port surface only; grain end faces treated as inhibited).",
            "Integrals over polar profiles are evaluated with composite Simpson's rule; values are exact to well within "
            "the displayed precision.",
            "Propellant densities are ideal (theoretical) values; a cast or pressed grain is typically 92-97 % of ideal. "
            "Enter the measured density for as-built mass.",
            "All lengths in millimetres; angles entered in degrees and converted to radians where used in equations.",
        ]
        for it in items:
            self.ensure(14)
            self.pdf.text(ML + 4, self.y + 9, "-", 9, "sans", MUTED, plain=True)
            self.para(it, 8.8, INK, indent=14, gap=2)

    def finish(self):
        n = len(self.pdf.pages)
        for i, ops in enumerate(self.pdf.pages, 1):
            self.pdf.ops = ops
            self.pdf.line(ML, PAGE_H - 44, PAGE_W - MR, PAGE_H - 44, RULE, 0.6)
            self.pdf.text(ML, PAGE_H - 32, f"Generated by {APP_NAME}  |  {self.meta['date']}  |  Ref. {self.meta['ref']}",
                          7.5, "sans", MUTED, plain=True)
            self.pdf.text(PAGE_W - MR, PAGE_H - 32, f"Page {i} of {n}", 7.5, "sansb", INK, "right", plain=True)
        return self.pdf.output()


def _inp(result, key):
    for i in result["inputs"]:
        if i["key"] == key:
            return i["value_str"]
    return ""


def build_pdf(result, meta):
    d = _Doc(result, meta)
    d.title_block()
    d.heading("1", "Design summary", "Key results")
    d.summary()
    if result["errors"]:
        d.para("This design has dimensional errors. See section 5 before using the results.", 9, RED)
    d.heading("2", "Input parameters")
    d.inputs_table()
    d.heading("3", "2D grain cross-section", "Dimensions in mm", need=440)
    d.diagram()
    d.heading("4", "Detailed calculations", "Equation  |  substitution  |  result", need=130)
    d.calculations()
    d.heading("5", "Design checks & notes")
    d.checks()
    d.heading("6", "Method & assumptions")
    d.method()
    return d.finish()


# ======================================================================================
# HTML
# ======================================================================================
_HTML_CSS = """
:root{--ink:#1B2533;--muted:#5B6878;--rule:#C5CED8;--paper:#F3F5F8;--red:#B23A2E;--amber:#9A6200;--ok:#2E6B4A}
*{box-sizing:border-box}body{margin:0;background:#E9EDF1;color:var(--ink);
font:14px/1.5 Bahnschrift,"Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}
.sheet{max-width:900px;margin:24px auto;background:#fff;padding:40px 48px;border:1px solid var(--rule)}
.m{font-family:"Cambria Math",Cambria,"STIX Two Math","Times New Roman",serif;font-size:1.06em}
.m-sym{font-family:"Cambria Math",Cambria,"Times New Roman",serif}
header.top{display:flex;justify-content:space-between;border-bottom:2px solid var(--ink);padding-bottom:6px;font-size:12px;color:var(--muted)}
header.top b{color:var(--ink)}
.tb{display:grid;grid-template-columns:56% 44%;border:1.5px solid var(--ink);margin:18px 0 8px}
.tb .l{padding:16px 18px;border-right:1px solid var(--ink)}
.tb h1{margin:0;font-size:34px;line-height:1.1;letter-spacing:.2px}
.tb .sub{color:var(--muted);margin:4px 0 12px}.tb .fig{color:var(--red);font-weight:700;margin-right:8px}
.tb .gname{font-weight:700;font-size:17px}.tb .gsub{color:var(--muted)}
.status{margin-top:10px;font-weight:700;font-size:13px}.status.ok{color:var(--ok)}.status.bad{color:var(--red)}
.tb table{width:100%;border-collapse:collapse;height:100%}.tb td{padding:6px 10px;border-bottom:1px solid var(--rule);font-size:12.5px}
.tb tr:last-child td{border-bottom:0}.tb td:first-child{color:var(--muted);width:42%}.tb td:last-child{font-weight:600}
h2{font-size:19px;margin:30px 0 10px;padding-bottom:5px;border-bottom:1px solid var(--rule);display:flex;gap:12px;align-items:baseline}
h2 .n{color:var(--red)}h2 .aside{margin-left:auto;font-size:12px;color:var(--muted);font-weight:400}
.sum{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--rule);border-left:1px solid var(--rule)}
.sum div{padding:9px 11px;border-right:1px solid var(--rule);border-bottom:1px solid var(--rule)}
.sum .lab{font-size:11.5px;color:var(--muted)}.sum .val{display:flex;justify-content:space-between;align-items:baseline;margin-top:2px}
.sum .val b{font-size:19px}.sum .u{font-size:11px;color:var(--muted);text-align:right}
table.inp{width:100%;border-collapse:collapse;font-size:13px}table.inp th{background:var(--ink);color:#fff;text-align:left;padding:6px 10px;font-weight:600}
table.inp td{padding:5px 10px;border-bottom:1px solid #E1E6EC}table.inp tr:nth-child(even) td{background:var(--paper)}
.fig-frame{border:1.5px solid var(--ink);padding:16px;background:#FBFCFD}.fig-frame svg{width:100%;height:auto;max-height:560px;display:block}
.cap{font-size:12.5px;margin-top:8px}.cap span{color:var(--muted);display:block;font-size:12px}
.calc h3{font-size:15px;margin:22px 0 6px;display:flex;gap:10px}.calc h3 .n{color:var(--red)}.calc h3 .r{margin-left:auto;font-weight:400;color:var(--muted);font-size:12px}
.step{display:grid;grid-template-columns:34px 1fr auto;column-gap:8px;padding:8px 0;border-bottom:1px solid #E6EAEF}
.step .no{color:var(--muted);font-size:12px;font-weight:700;padding-top:2px}.step .nm{font-weight:700;font-size:13px}
.step .f{font-size:16px;margin-top:2px}.step .s{color:var(--muted);font-size:14px;overflow-wrap:anywhere}
.step .res{grid-row:1/span 3;grid-column:3;align-self:center;text-align:right;font-weight:700;font-size:16px;white-space:nowrap}
.step .res small{font-weight:400;color:var(--muted);font-size:12px;margin-left:3px}
ul.chk{padding-left:18px}ul.chk li{margin:4px 0}.e{color:var(--red)}.w{color:var(--amber)}.nt{color:var(--muted)}
footer{margin-top:30px;border-top:1px solid var(--rule);padding-top:8px;font-size:11.5px;color:var(--muted);display:flex;justify-content:space-between}
@media print{body{background:#fff}.sheet{margin:0;border:0;padding:0}h2,.step,.fig-frame{break-inside:avoid}}
@media (max-width:700px){.sheet{padding:20px}.tb{grid-template-columns:1fr}.tb .l{border-right:0;border-bottom:1px solid var(--ink)}.sum{grid-template-columns:repeat(2,1fr)}}
"""


def m(s):
    return f'<span class="m">{markup.to_html(s)}</span>'


def build_html(result, meta):
    r = result
    g = r["geometry"]
    e = html.escape
    svg = drawing.scene_svg(r["scene"], annotate=True, title=f"{g['name']} cross-section")
    status = ('<div class="status ok">Design status: valid</div>' if r["ok"]
              else f'<div class="status bad">Design status: {len(r["errors"])} issue(s) to resolve</div>')
    rows = [("Report ref.", meta["ref"]), ("Date", meta["date"]), ("Propellant", r["propellant"]),
            ("Grain OD × length", f"{_inp(r, 'OD')} mm × {_inp(r, 'L')} mm"), ("Units", "mm, mm², mm³, g, rad"),
            ("Equations", "Reference formulation sheet")]
    tb = "".join(f"<tr><td>{e(k)}</td><td>{e(v)}</td></tr>" for k, v in rows)
    summ = "".join(f'<div><div class="lab">{e(s["label"])}</div><div class="val">{m(s["sym"])}<b>{e(s["value_str"])}</b></div>'
                   f'<div class="u">{e(s["unit"])}</div></div>' for s in r["summary"])
    inp = "".join(f"<tr><td>{e(i['label'])}</td><td>{m(i['sym']) if i['sym'] else ''}</td><td><b>{e(i['value_str'])}</b></td>"
                  f"<td>{e(i['unit'])}</td></tr>" for i in r["inputs"])
    calc = []
    num = 0
    for si, sec in enumerate(r["sections"], 1):
        ref = f'<span class="r">Reference {e(sec["ref"])}</span>' if sec.get("ref") else ""
        calc.append(f'<h3><span class="n">4.{si}</span>{e(sec["title"])}{ref}</h3>')
        for st in sec["steps"]:
            num += 1
            calc.append(
                f'<div class="step"><div class="no">{num:02d}</div><div class="nm">{e(st["name"])}</div>'
                f'<div class="res">{e(st["value_str"])}<small>{e(st["unit"])}</small></div>'
                f'<div></div><div class="f">{m(st["formula"])}</div>'
                f'<div></div><div class="s">= {m(st["subst"])}</div></div>')
    chk = []
    for cls, items in (("e", r["errors"]), ("w", r["warnings"]), ("nt", r["notes"])):
        chk += [f'<li class="{cls}">{e(x)}</li>' for x in items]
    checks = f'<ul class="chk">{"".join(chk)}</ul>' if chk else '<p style="color:var(--ok)">All dimensional checks passed. No warnings.</p>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{APP_NAME} report: {e(g['name'])}</title><style>{_HTML_CSS}</style></head><body><div class="sheet">
<header class="top"><b>{APP_NAME}</b><span>Grain geometry design report | Fig. {g['fig']} {e(g['name'])}</span></header>
<div class="tb"><div class="l"><h1>{APP_NAME}</h1><div class="sub">Solid propellant grain geometry design report</div>
<div><span class="fig">Fig. {g['fig']}</span><span class="gname">{e(g['name'])}</span></div><div class="gsub">{e(g['subtitle'])}</div>{status}</div>
<table>{tb}</table></div>
<h2><span class="n">1</span>Design summary<span class="aside">Key results</span></h2><div class="sum">{summ}</div>
<h2><span class="n">2</span>Input parameters</h2><table class="inp"><tr><th>Parameter</th><th>Symbol</th><th>Value</th><th>Unit</th></tr>{inp}</table>
<h2><span class="n">3</span>2D grain cross-section<span class="aside">Dimensions in mm</span></h2>
<div class="fig-frame">{svg}</div><div class="cap"><b>Figure 1.</b> 2D cross-sectional profile: {e(g['name'])} ({e(g['subtitle'])}).
<span>Drawn to scale from the entered parameters. Hatched area: propellant. White: port. Red dashed circle: maximum port radius.</span></div>
<h2><span class="n">4</span>Detailed calculations<span class="aside">Equation, substitution, result</span></h2><div class="calc">{''.join(calc)}</div>
<h2><span class="n">5</span>Design checks &amp; notes</h2>{checks}
<h2><span class="n">6</span>Method &amp; assumptions</h2><ul class="chk">
<li>All geometry equations are taken from the reference document “{e(REFERENCE)}”; the section used for each calculation block is noted beside it.</li>
<li>Propellant volume, mass and burning surface use the standard relations {m('V_g = A_g · L')}, {m('m = ρ · V_g')} and {m('A_b = P_0 · L')} (port surface only; grain end faces treated as inhibited).</li>
<li>Integrals over polar profiles are evaluated with composite Simpson's rule.</li>
<li>Propellant densities are ideal (theoretical) values; a cast or pressed grain is typically 92–97 % of ideal. Enter the measured density for as-built mass.</li>
<li>All lengths in millimetres; angles entered in degrees and converted to radians where used in equations.</li></ul>
<footer><span>Generated by {APP_NAME} | {e(meta['date'])} | Ref. {e(meta['ref'])}</span><span>Print or save as PDF from your browser if needed.</span></footer>
</div></body></html>"""
