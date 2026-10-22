# Grain_yantra_1

**Solid propellant grain geometry design software.**
Choose a port geometry, enter the grain dimensions, solve the analytical equations, see the
2D cross-section drawn to scale, and download a full engineering report.

Built with **Python** (calculation engine, drawings, PDF/HTML report generator, local server)
and **JavaScript** (the interface). It uses only the Python standard library, so there is
nothing to install besides Python itself.

---

## Run it

**Requirement:** Python 3.8 or newer ([python.org/downloads](https://www.python.org/downloads/)).
On Windows, tick *"Add python.exe to PATH"* during setup.

| System | How to start |
| --- | --- |
| Windows | Double-click `Run_Grain_yantra_1.bat` |
| macOS / Linux | In a terminal: `./Run_Grain_yantra_1.sh` |
| Any | `python Grain_yantra_1.py` |

The software starts a private local server (`http://127.0.0.1:8765`, or the next free port) and
opens the interface. Keep the console window open while you work; close it (or press Ctrl+C) to quit.

*Optional:* `pip install pywebview` makes Grain_yantra_1 open in its own desktop window
titled **Grain_yantra_1** instead of a browser tab.

Command-line options: `--port 9000`, `--no-browser`, `--browser` (force the browser even if pywebview is installed).

### Standalone Windows .exe (optional)
Run `build_windows_exe.bat` once on a Windows PC with Python. It installs PyInstaller and
produces `dist\Grain_yantra_1.exe`, which runs on computers without Python.

---

## Workflow

1. **Start**: welcome page, click *Start the Software*.
2. **Geometry**: pick one of the 21 port geometries (filter by bores, perforated, slotted, lobed & polar).
3. **Parameters**: only the inputs that geometry needs: grain OD, length, propellant type and
   density, number of perforations / slots / fins / lobes, port diameter and the profile dimensions.
   A live preview redraws the cross-section and flags problems as you type.
4. **Results**: left, the 2D cross-section drawn to scale with OD, R_max and web dimensions;
   right, every calculation step: equation, the values substituted (mm), and the result.
5. **Download Report**: PDF (default) or standalone HTML, containing the inputs, the drawing, all
   equations and substitutions, results, design checks and assumptions.
6. **Feedback**: rate the developer (1–5 stars) and leave a comment. Saved to `data/feedback.json`.
7. **Download**: final page with the *Download Grain_yantra_1* button (this whole package as a zip).

---

## Geometries and equations

All geometry equations come from *Solid Rocket Motor Grain Geometries — Analytical Formulations
& 2D Profiles* (the reference sheet). Each calculation block in the app and report names the
section it comes from.

| Fig. | Geometry | Key inputs |
| --- | --- | --- |
| 1 | Circular Port (BATES) | D₀ |
| 2 | Multiperforated Circular Port | d_h, N_outer, N_center, R_pitch |
| 3 | Triangular Multiperforated Port | N, s, r_f, R_c |
| 4 | Star Port | N, R_p, R_r |
| 5 | Finocyl Port | D₀, N, L_f, t |
| 6 | Dendrite Port | D₀, N, L₁, t₁, L₂, t₂, φ |
| 7 | Dogbone Port | D₀, N, L_s, t, r_bulb |
| 8 | Wagon Wheel Port (tapered spokes, flared heads) | D₀, N, L_s, t₀, t₁, L_h, t_H, r_f |
| 9 | D-Shape Port | R_d, x_c |
| 10 | Moon Burner Port | D₀, e |
| 11 | Heart Port (classic heart) | W, H |
| 12 | Single Anchor Port | D₀, L_s, t_s, φ_arc, t_f |
| 13 | Double Anchor Port | D₀, L_s, t_s, φ_arc, t_f |
| 14 | Cloverleaf Port | s_c, R_c, R_lobe (N = 4) |
| 15 | Rounded Diamond Port | s₀, r_f |
| 16 | C-Slotted Dendrite Port (forked stems, C-slot heads) | D₀, N, L_s, t, φ, w_b, L_b, L_f, w_f |
| 17 | Sinusoidal-Port Grain | R₀, A, N |
| 18 | Helical Port | R₀, A, N, Φ (+ L) |
| 19 | Leaf Petal Profile | R₀, A, N |
| 20 | Star-Polygon Hybrid Port | N, R_c, R_lobe, R_spike |
| 21 | Infinity / Cassini-Oval | a, b |

Every geometry also uses the fundamental relations from the reference:
`A_case = πR_case²`, `w_max = R_case − R_max`, `A_g = πR_case² − A_p`, `V_f = (1 − A_p/πR_case²)·100 %`.

On top of those, standard relations give grain volume `V_g = A_g·L`, mass `m = ρ·V_g` and
initial port burning surface `A_b = P₀·L` (ends inhibited; for the helical port, `A_b = κ·P₂D·L`
from the reference).

### Implementation notes
* **Units:** lengths in mm, areas in mm², volumes in mm³ (and cm³), mass in g; angles are
  entered in degrees and converted to radians in an explicit step.
* **C-slotted dendrite:** circular hub (R₀) with N stems of width t that fork at R₀ + L_s into two branches swept back at
  angle φ (width w_b, length L_b) ending in outward feet (L_f long, w_f wide), with a V notch between the branches. Perimeter,
  area (shoelace over the half-stem vertices) and R_max (outer foot corner) are closed-form and checked against the drawn outline.
* **Wagon wheel:** circular hub (R₀), N spokes tapering from root width t₀ to neck width t₁ at radius R₀ + L_s, then
  flaring to head width t_H over length L_h, with r_f-rounded outer corners. Perimeter, area and R_max are closed-form
  (taper and flare side lengths, fillet tangent length and arc, hub segment correction) and are checked against the drawn outline.
* **Heart port:** drawn from the classic parametric heart `x = 16 sin³t`, `y = 13cos t − 5cos 2t − 2cos 3t − cos 4t`,
  scaled to the entered width W and height H and centred on the motor axis (area centroid at the axis).
  Area is exact (`180π·s_x·s_y`); perimeter uses Simpson's rule; R_max is found by a 20 000-point sweep.
* **Polar profiles** (sinusoidal, helical, petal, Cassini): perimeter and area integrals
  are evaluated with composite Simpson's rule (n ≥ 4000).
* **Triangular port, R_max:** the reference gives `R_c + s/√3 − r_f(√3 − 1)`. For a 60° vertex the
  exact fillet correction is `r_f`, i.e. `R_c + s/√3 − r_f`. The app uses the reference formula and
  shows the exact value alongside it as a note; the drawing uses exact geometry.
* **Star-Polygon Hybrid:** the reference defines `P₀ = N·S_lobe + 2N·L_spike` and
  `A_p = A_core + N·A_lobe,exposed + N·A_spike,exposed` but not the exposed terms themselves. The app
  fixes the construction (core circle R_c, lobes centred on it, spike flanks from the neighbouring
  lobe centres to R_spike) and evaluates the exposed terms numerically.
* **Anchor ports:** fluke arcs are centred on the motor axis with `R_arc = R₀ + L_s`.
* **Helical port:** the base cross-section is the N-lobe petal profile `r(θ) = R₀ + A cos(Nθ)`;
  the drawing shows the exit profile (rotated by Φ) dashed.
* **Propellant densities** are ideal values (KNSU 1.889, KNDX 1.879, KNSB 1.841, KNER 1.820,
  APCP 1.75 g/cm³); enter your measured density for as-built mass.

---

## Folder layout

```
Grain_yantra_1/
  Grain_yantra_1.py         launcher
  Run_Grain_yantra_1.bat    Windows launcher
  Run_Grain_yantra_1.sh     macOS / Linux launcher
  build_windows_exe.bat     optional standalone .exe build
  grain_yantra/
    engine.py               equations for all 21 geometries, validation
    shapes.py, drawing.py   2D geometry and to-scale drawings (SVG)
    pdf.py, report.py       dependency-free PDF writer, PDF/HTML report
    markup.py               equation markup (sub/superscripts, Greek)
    server.py               local web server and JSON API
  web/                      index.html, css/app.css, js/app.js, assets/
  tests/test_engine.py      self-tests:  python -m unittest discover -s tests
  data/                     feedback.json (created when feedback is submitted)
```
