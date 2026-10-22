/* Grain_yantra_1 — interface logic.
   The Python engine (served locally) does every calculation; this file drives the
   workflow: welcome → geometry → parameters → results → report → feedback → download. */
(function () {
  "use strict";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const ORDER = ["welcome", "geometry", "params", "results", "feedback", "download"];
  const GROUPS = {
    circular: "bore", dshape: "bore", moon: "bore", diamond: "bore",
    multiperf: "perf", triangular: "perf",
    finocyl: "slot", dendrite: "slot", dogbone: "slot", wagon: "slot", anchor1: "slot", anchor2: "slot", cslot: "slot",
    star: "lobe", heart: "lobe", cloverleaf: "lobe", sinusoidal: "lobe", helical: "lobe", petal: "lobe", hybrid: "lobe", cassini: "lobe",
  };

  const state = {
    cat: null,
    gid: null,
    values: {},       // gid -> {key: value}
    result: null,
    reached: 0,
    page: "welcome",
    previewTimer: null,
    previewSeq: 0,
  };

  // ------------------------------------------------------------------ storage (best effort)
  const store = {
    get(k, d) { try { const v = localStorage.getItem("gy1:" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("gy1:" + k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } },
  };

  // ------------------------------------------------------------------ math markup (mirrors grain_yantra/markup.py)
  const SYMBOLS = new Set("αβγδεζηθικλμνξπρστυφϕχψωΓΔΘΛΞΠΣΦΨΩ−·×≈√∫≤≥±∞°∑∂≠");
  const FUNCS = ["arccos", "arcsin", "arctan", "sin", "cos", "tan", "max", "min", "ln", "exp", "sqrt", "mod"];
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function emit(out, text, level, forceRm) {
    const wordGroup = forceRm || (level !== 0 && text.length > 1 && /^[A-Za-z,. ]+$/.test(text));
    let i = 0;
    while (i < text.length) {
      let matched = false;
      if (level === 0 && !forceRm) {
        for (const w of FUNCS) {
          if (text.startsWith(w, i) && (i === 0 || !/[A-Za-z]/.test(text[i - 1]))) {
            out.push([w, "rm", level]); i += w.length; matched = true; break;
          }
        }
      }
      if (matched) continue;
      const ch = text[i];
      let st = "rm";
      if (SYMBOLS.has(ch)) st = "sym";
      else if (/[A-Za-z]/.test(ch)) st = wordGroup ? "rm" : "it";
      out.push([ch, st, level]);
      i += 1;
    }
  }

  function parse(s) {
    const runs = [];
    let buf = "", i = 0;
    s = String(s || "");
    while (i < s.length) {
      const ch = s[i];
      if (ch === "_" || ch === "^") {
        if (buf) { emit(runs, buf, 0); buf = ""; }
        const level = ch === "_" ? -1 : 1;
        i += 1;
        let grp;
        if (s[i] === "{") { let j = s.indexOf("}", i); if (j < 0) j = s.length; grp = s.slice(i + 1, j); i = j + 1; }
        else { grp = s.slice(i, i + 1); i += 1; }
        emit(runs, grp, level);
      } else if (ch === "`") {
        if (buf) { emit(runs, buf, 0); buf = ""; }
        let j = s.indexOf("`", i + 1); if (j < 0) j = s.length;
        emit(runs, s.slice(i + 1, j), 0, true);
        i = j + 1;
      } else { buf += ch; i += 1; }
    }
    if (buf) emit(runs, buf, 0);
    const merged = [];
    for (const r of runs) {
      const last = merged[merged.length - 1];
      if (last && last[1] === r[1] && last[2] === r[2]) last[0] += r[0]; else merged.push(r.slice());
    }
    return merged;
  }

  function mh(s) {
    return '<span class="m">' + parse(s).map(([t, st, lv]) => {
      let h = esc(t);
      if (st === "it") h = "<i>" + h + "</i>"; else if (st === "sym") h = '<span class="m-sym">' + h + "</span>";
      if (lv === -1) h = "<sub>" + h + "</sub>"; else if (lv === 1) h = "<sup>" + h + "</sup>";
      return h;
    }).join("") + "</span>";
  }

  // ------------------------------------------------------------------ API
  async function api(path, body) {
    const res = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
    let data;
    try { data = await res.json(); } catch (e) { throw new Error("The calculation server did not answer. Is the Grain_yantra_1 window still running?"); }
    if (!res.ok) { const err = new Error(data.error || "Request failed"); err.input = !!data.input_error; throw err; }
    return data;
  }

  function toast(msg, ms = 2600) {
    const t = $("#toast");
    t.textContent = msg; t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { t.hidden = true; }, ms);
  }

  // ------------------------------------------------------------------ routing
  function canVisit(page) {
    const idx = ORDER.indexOf(page);
    if (page === "params") return !!state.gid;
    if (page === "results" || page === "feedback") return !!state.result;
    if (page === "download") return state.reached >= ORDER.indexOf("feedback");
    return idx <= state.reached || page === "geometry" || page === "welcome";
  }

  function show(page, opts = {}) {
    if (!canVisit(page)) return;
    state.page = page;
    state.reached = Math.max(state.reached, ORDER.indexOf(page));
    for (const p of ORDER) $("#page-" + p).hidden = p !== page;
    const cur = ORDER.indexOf(page);
    $$("#steps li").forEach((li) => {
      const i = ORDER.indexOf(li.dataset.step);
      li.classList.toggle("current", i === cur);
      li.classList.toggle("done", i !== cur && canVisit(li.dataset.step) && i <= state.reached);
      if (i === cur) li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current");
    });
    if (!opts.keepScroll) window.scrollTo(0, 0);
    const h = $("#page-" + page + " h1");
    if (h && opts.focus !== false) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
    document.title = page === "welcome" ? "Grain_yantra_1" : `Grain_yantra_1 | ${$("#steps li[data-step='" + page + "']").textContent.replace(/^\d/, "")}`;
  }

  document.addEventListener("click", (e) => {
    const go = e.target.closest("[data-go]");
    if (go) { e.preventDefault(); show(go.dataset.go); return; }
    const li = e.target.closest("#steps li.done");
    if (li) show(li.dataset.step);
  });

  // ------------------------------------------------------------------ welcome art (the one orchestrated motion)
  function heroArt() {
    const N = 6, Rp = 25, Rr = 12, R = 50;
    const pts = [];
    for (let k = 0; k < 2 * N; k++) {
      const r = k % 2 ? Rr : Rp, a = Math.PI / 2 + Math.PI * k / N;
      pts.push([r * Math.cos(a), -r * Math.sin(a)]);
    }
    const star = "M" + pts.map((p) => p[0].toFixed(2) + "," + p[1].toFixed(2)).join(" L") + " Z";
    const a = -40 * Math.PI / 180;
    const P = (r) => [r * Math.cos(a), r * Math.sin(a)];
    const [x1, y1] = P(Rp), [x2, y2] = P(R), [x3, y3] = P(R + 10);
    const d = (i) => `style="--len:1;animation-delay:${(0.15 + i * 0.22).toFixed(2)}s"`;
    $("#hero-art").innerHTML = `
      <defs><pattern id="hh" patternUnits="userSpaceOnUse" width="2.3" height="2.3" patternTransform="rotate(45)">
        <rect width="2.3" height="2.3" fill="#E3E9F0"/><line x1="0" y1="0" x2="0" y2="2.3" stroke="#97A8BC" stroke-width=".32"/></pattern></defs>
      <circle r="52.2" fill="#B9C4D1" class="draft-fill" style="animation-delay:.9s"/>
      <circle r="50" fill="url(#hh)" class="draft-fill" style="animation-delay:1.1s"/>
      <path d="${star}" fill="#fff" class="draft-fill" style="animation-delay:1.3s"/>
      <circle r="52.2" fill="none" stroke="#1B2533" stroke-width=".5" pathLength="1" class="draft" ${d(0)}/>
      <circle r="50" fill="none" stroke="#1B2533" stroke-width=".45" pathLength="1" class="draft" ${d(1)}/>
      <path d="${star}" fill="none" stroke="#1B2533" stroke-width=".7" stroke-linejoin="round" pathLength="1" class="draft" ${d(2)}/>
      <path d="M-58,0 H58 M0,-58 V58" stroke="#6C7A8C" stroke-width=".2" stroke-dasharray="5 1.2 1 1.2" class="draft-fill" style="animation-delay:.2s"/>
      <circle r="25" fill="none" stroke="#B23A2E" stroke-width=".3" stroke-dasharray="1.4 .9" class="draft-fill" style="animation-delay:1.6s"/>
      <path d="M0,0 L${x1},${y1} M${x1},${y1} L${x2},${y2} L${x3},${y3} h7" fill="none" stroke="#B23A2E" stroke-width=".32" pathLength="1" class="draft" ${d(5)}/>
      <g class="draft-fill" style="animation-delay:2.1s" fill="#B23A2E" font-size="3.6" font-family="Bahnschrift, Segoe UI, sans-serif">
        <text x="${x3 + 8.5}" y="${y3 - 4.2}"><tspan font-style="italic" font-family="Cambria Math, serif">R</tspan><tspan dy="1" font-size="2.6">max</tspan><tspan dy="-1"> = 25.000 mm</tspan></text>
        <text x="${x3 + 8.5}" y="${y3 + 1.2}"><tspan font-style="italic" font-family="Cambria Math, serif">w</tspan><tspan dy="1" font-size="2.6">max</tspan><tspan dy="-1"> = 25.000 mm</tspan></text>
      </g>
      <g class="draft-fill" style="animation-delay:1.9s" stroke="#1B2533" stroke-width=".25">
        <path d="M-50,2 V66 M50,2 V66 M-50,63.5 H50"/>
        <path d="M-50,63.5 l2.6,-.85 v1.7 Z M50,63.5 l-2.6,-.85 v1.7 Z" fill="#1B2533" stroke="none"/>
        <text x="0" y="70.5" text-anchor="middle" fill="#1B2533" stroke="none" font-size="3.6" font-family="Bahnschrift, Segoe UI, sans-serif">Ø 100.000 mm</text>
      </g>`;
  }

  // ------------------------------------------------------------------ geometry plates
  function renderPlates() {
    const host = $("#plates");
    host.innerHTML = state.cat.geometries.map((g) => `
      <button class="plate" data-gid="${g.id}" data-group="${GROUPS[g.id] || "lobe"}" aria-label="Fig. ${g.fig}: ${esc(g.name)}, ${esc(g.subtitle)}">
        <div class="art">${g.thumb}</div>
        <div class="tb"><div class="no">Fig. ${g.fig}</div><div class="nm"><b>${esc(g.name)}</b><small>${esc(g.subtitle)}</small></div></div>
      </button>`).join("");
    host.addEventListener("click", (e) => {
      const b = e.target.closest(".plate");
      if (b) selectGeometry(b.dataset.gid);
    });
    $("#filters").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-filter]");
      if (!b) return;
      $$("#filters button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
      const f = b.dataset.filter;
      $$(".plate").forEach((p) => { p.hidden = f !== "all" && p.dataset.group !== f; });
    });
  }

  // ------------------------------------------------------------------ parameters
  const geom = () => state.cat.geometries.find((g) => g.id === state.gid);
  const unitLabel = (p) => p.unit === "°" ? "deg" : p.unit === "" ? (p.integer ? "count" : "") : p.unit;

  function defaultsFor(g) {
    const d = {};
    for (const p of state.cat.common.concat(g.params)) d[p.key] = p.default;
    d.prop = "KNSU";
    d.rho = state.cat.propellants[0].rho;
    d.prop_name = "";
    return d;
  }

  function fieldHTML(p) {
    const id = "in-" + p.key;
    const lab = `<label for="${id}"><span>${esc(p.label)}</span>${p.sym ? mh(p.sym) : ""}</label>`;
    if (p.options) {
      return `<div class="field" data-key="${p.key}">${lab}<select id="${id}" name="${p.key}">${p.options.map((o) => `<option value="${o}">${o}</option>`).join("")}</select>
        ${p.help ? `<p class="help">${esc(p.help)}</p>` : ""}</div>`;
    }
    const u = unitLabel(p);
    return `<div class="field" data-key="${p.key}">${lab}
      <div class="input-unit"><input id="${id}" name="${p.key}" type="text" inputmode="${p.integer ? "numeric" : "decimal"}" autocomplete="off" spellcheck="false" aria-describedby="${id}-err">
      ${u ? `<span class="unit">${esc(u)}</span>` : ""}</div>
      ${p.help ? `<p class="help">${esc(p.help)}</p>` : ""}<p class="err" id="${id}-err" hidden></p></div>`;
  }

  function selectGeometry(gid) {
    state.gid = gid;
    const g = geom();
    if (!state.values[gid]) state.values[gid] = Object.assign(defaultsFor(g), (store.get("values", {}) || {})[gid] || {});
    $("#p-fig").textContent = "Fig. " + g.fig;
    $("#p-name").textContent = g.name;
    $("#p-desc").textContent = g.description;
    $("#f-common").innerHTML = state.cat.common.map(fieldHTML).join("");
    $("#f-geom").innerHTML = g.params.map(fieldHTML).join("");
    $("#f-rho").innerHTML = fieldHTML({ key: "rho", label: "Propellant density", sym: "ρ", unit: "g/cm³", help: "Ideal density is filled in; enter your measured value for as-built mass." });
    fillForm();
    $("#form-error").hidden = true;
    show("params");
    schedulePreview(0);
  }

  function fillForm() {
    const v = state.values[state.gid];
    for (const [k, val] of Object.entries(v)) {
      const el = $("#in-" + k);
      if (el) el.value = val;
    }
    $("#custom-name-field").hidden = v.prop !== "CUSTOM";
  }

  function readForm() {
    const v = state.values[state.gid];
    $$("#param-form input, #param-form select").forEach((el) => { v[el.name] = el.value.trim(); });
    const all = store.get("values", {}) || {};
    all[state.gid] = v;
    store.set("values", all);
    return v;
  }

  function validateLocal() {
    const g = geom();
    let ok = true;
    for (const p of state.cat.common.concat(g.params, [{ key: "rho", label: "Propellant density" }])) {
      if (p.options) continue;
      const el = $("#in-" + p.key);
      const f = el.closest(".field");
      const err = $("#in-" + p.key + "-err");
      const raw = el.value.trim().replace(",", ".");
      let msg = "";
      if (raw === "") msg = "Enter a value.";
      else if (!/^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$/.test(raw)) msg = "Enter a number, e.g. 12.5";
      else if (p.integer && !Number.isInteger(Number(raw))) msg = "Enter a whole number.";
      else if (Number(raw) < 0) msg = "Value cannot be negative.";
      if (raw !== el.value.trim()) el.value = raw;
      f.classList.toggle("invalid", !!msg);
      err.hidden = !msg; err.textContent = msg;
      if (msg) ok = false;
    }
    return ok;
  }

  function schedulePreview(delay = 280) {
    clearTimeout(state.previewTimer);
    state.previewTimer = setTimeout(runPreview, delay);
  }

  async function runPreview() {
    if (state.page !== "params" || !validateLocal()) {
      $("#preview-state").textContent = "Fix the highlighted fields to update the preview.";
      $("#preview-state").className = "preview-state bad";
      return;
    }
    const seq = ++state.previewSeq;
    const inputs = readForm();
    try {
      const r = await api("/api/solve", { geometry: state.gid, inputs });
      if (seq !== state.previewSeq) return;
      $("#preview-svg").innerHTML = r.svg;
      const pick = (k) => r.summary.find((s) => s.key === k);
      $("#readouts").innerHTML = ["Rmax", "w", "Vf", "m"].map((k) => {
        const s = pick(k);
        return `<div><dt>${esc(s.label)}</dt><dd>${esc(s.value_str)}<small>${esc(s.unit)}</small></dd></div>`;
      }).join("");
      const st = $("#preview-state");
      if (r.errors.length) { st.textContent = r.errors[0]; st.className = "preview-state bad"; }
      else if (r.warnings.length) { st.textContent = r.warnings[0]; st.className = "preview-state warn"; }
      else { st.textContent = "Geometry is valid. Preview updates as you type."; st.className = "preview-state"; }
      $("#form-error").hidden = true;
    } catch (e) {
      if (seq !== state.previewSeq) return;
      $("#preview-state").textContent = e.message;
      $("#preview-state").className = "preview-state bad";
    }
  }

  // ------------------------------------------------------------------ results
  function renderResults(r) {
    const g = r.geometry;
    $("#r-fig").textContent = "Fig. " + g.fig;
    $("#r-name").textContent = g.name;
    $("#r-sub").textContent = g.subtitle + ". " + g.description;
    const st = $("#r-status");
    st.className = "status " + (r.ok ? "ok" : "bad");
    st.textContent = r.ok ? "Design valid" : `${r.errors.length} issue${r.errors.length > 1 ? "s" : ""} to resolve`;
    $("#r-svg").innerHTML = r.svg;
    const inp = (k) => (r.inputs.find((i) => i.key === k) || {}).value_str;
    const now = new Date();
    $("#r-titleblock").innerHTML = `
      <tr><td class="brandcell" rowspan="2">Grain_yantra_1<small>Grain geometry design</small></td>
          <td><small>Drawing</small>Fig. ${g.fig} ${esc(g.name)}</td><td><small>Units</small>mm</td></tr>
      <tr><td><small>Propellant</small>${esc(r.propellant)}</td><td><small>Grain OD × L</small>${esc(inp("OD"))} × ${esc(inp("L"))}</td></tr>
      <tr><td><small>Date</small>${now.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })}</td>
          <td><small>Equations</small>Reference formulation sheet</td><td><small>Scale</small>Fitted</td></tr>`;
    $("#r-summary").innerHTML = r.summary.map((s) => `
      <div><div class="lab"><span>${esc(s.label)}</span><span class="sym">${mh(s.sym)}</span></div><div class="val">${esc(s.value_str)}</div><div class="u">${esc(s.unit)}</div></div>`).join("");
    const items = [].concat(
      r.errors.map((x) => `<li class="e"><b>Error</b>${esc(x)}</li>`),
      r.warnings.map((x) => `<li class="w"><b>Warning</b>${esc(x)}</li>`),
      r.notes.map((x) => `<li class="n"><b>Note</b>${esc(x)}</li>`));
    $("#r-checks").innerHTML = items.length ? `<ul class="checks">${items.join("")}</ul>` : "";
    let n = 0;
    $("#r-calc").innerHTML = r.sections.map((sec, si) => `
      <section class="calc-sec"><header><span class="n">${si + 1}</span><h3>${esc(sec.title)}</h3>${sec.ref ? `<span class="ref">Reference ${esc(sec.ref)}</span>` : ""}</header>
      ${sec.steps.map((s) => { n += 1; return `
        <div class="calc-step"><div class="no">${String(n).padStart(2, "0")}</div><div class="nm">${esc(s.name)}</div>
          <div class="res">${esc(s.value_str)}<small>${esc(s.unit)}</small></div>
          <div class="eq">${mh(s.formula)}</div>${s.subst ? `<div class="sb">= ${mh(s.subst)}</div>` : ""}</div>`; }).join("")}
      </section>`).join("");
  }

  async function solve(e) {
    if (e) e.preventDefault();
    if (!validateLocal()) {
      const fe = $("#form-error");
      fe.textContent = "Some values need attention. Check the highlighted fields.";
      fe.hidden = false;
      const first = $(".field.invalid input");
      if (first) first.focus();
      return;
    }
    const btn = $("#solve-btn");
    btn.classList.add("busy"); btn.disabled = true; btn.textContent = "Solving…";
    try {
      const r = await api("/api/solve", { geometry: state.gid, inputs: readForm() });
      state.result = r;
      state.resultInputs = Object.assign({}, state.values[state.gid]);
      renderResults(r);
      show("results");
    } catch (err) {
      const fe = $("#form-error");
      fe.textContent = err.message;
      fe.hidden = false;
      fe.scrollIntoView({ block: "center" });
    } finally {
      btn.classList.remove("busy"); btn.disabled = false; btn.textContent = "Solve geometry";
    }
  }

  // ------------------------------------------------------------------ report download
  async function downloadReport(format) {
    const payload = { geometry: state.gid, inputs: state.resultInputs, format };
    const url = "/api/report?data=" + encodeURIComponent(JSON.stringify(payload));
    const btn = format === "pdf" ? $("#dl-pdf") : $("#dl-html");
    btn.classList.add("busy"); btn.disabled = true;
    let fname = "Grain_yantra_1_Report." + format;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(await res.text());
      fname = res.headers.get("X-Filename") || fname;
      const blob = await res.blob();
      const obj = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = obj; a.download = fname; document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(obj), 4000);
    } catch (err) {
      if (/Report not generated/.test(err.message)) { toast(err.message, 5000); btn.classList.remove("busy"); btn.disabled = false; return; }
      window.location.href = url;   // fallback for embedded webviews
    }
    btn.classList.remove("busy"); btn.disabled = false;
    toast("Report downloaded: " + fname);
    const n = $("#dl-notice");
    n.innerHTML = `Report saved as <b>${esc(fname)}</b>. You can return to the results from step 4 at any time.`;
    n.hidden = false;
    setTimeout(() => { if (state.page === "results") show("feedback"); }, 1400);
  }

  // ------------------------------------------------------------------ feedback
  const STAR_TEXT = ["Choose 1 to 5 stars", "1 star: did not work for me", "2 stars: needs work", "3 stars: useful", "4 stars: very good", "5 stars: excellent"];
  function paintStars(n) {
    $$(".star-row label").forEach((l, i) => l.classList.toggle("on", i < n));
  }
  function currentRating() { const c = $(".star-row input:checked"); return c ? Number(c.value) : 0; }

  function initFeedback() {
    const row = $(".star-row");
    row.addEventListener("change", () => { paintStars(currentRating()); $("#star-text").textContent = STAR_TEXT[currentRating()]; $("#fb-error").hidden = true; });
    row.addEventListener("mouseover", (e) => { const l = e.target.closest("label"); if (l) paintStars(Number(l.getAttribute("for").slice(2))); });
    row.addEventListener("mouseleave", () => paintStars(currentRating()));
    $("#fb-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const rating = currentRating();
      const fe = $("#fb-error");
      if (!rating) { fe.textContent = "Choose a rating from 1 to 5 stars before submitting."; fe.hidden = false; return; }
      try {
        await api("/api/feedback", { rating, comment: $("#fb-comment").value, name: $("#fb-name").value, geometry: state.gid });
        $("#fb-thanks").hidden = false;
        $("#fb-form").reset(); paintStars(0); $("#star-text").textContent = STAR_TEXT[0];
        show("download");
      } catch (err) { fe.textContent = err.message; fe.hidden = false; }
    });
  }

  // ------------------------------------------------------------------ init
  async function init() {
    heroArt();
    initFeedback();
    show("welcome", { focus: false });
    $("#param-form").addEventListener("submit", solve);
    $("#param-form").addEventListener("input", (e) => {
      if (e.target.id === "in-prop") return;
      schedulePreview();
    });
    $("#in-prop").addEventListener("change", (e) => {
      const p = state.cat.propellants.find((x) => x.id === e.target.value);
      $("#in-rho").value = p.rho;
      $("#custom-name-field").hidden = p.id !== "CUSTOM";
      schedulePreview(0);
    });
    $("#reset-btn").addEventListener("click", () => {
      state.values[state.gid] = defaultsFor(geom());
      fillForm(); validateLocal(); schedulePreview(0);
    });
    $("#dl-pdf").addEventListener("click", () => downloadReport("pdf"));
    $("#dl-html").addEventListener("click", () => downloadReport("html"));
    $("#dl-package").addEventListener("click", () => toast("Downloading Grain_yantra_1.zip"));
    try {
      state.cat = await api("/api/catalogue");
    } catch (e) {
      $("#welcome-fine").textContent = "The calculation engine is not running. Start the software with Run_Grain_yantra_1 (or python Grain_yantra_1.py).";
      $("#welcome-fine").style.color = "var(--red)";
      $("#start-btn").disabled = true;
      return;
    }
    $("#ver").textContent = state.cat.version;
    $("#in-prop").innerHTML = state.cat.propellants.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("");
    renderPlates();
  }

  init();
})();
