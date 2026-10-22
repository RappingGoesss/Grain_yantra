"""Grain_yantra_1 - local web server (Python standard library only).

Serves the JavaScript interface from ./web and exposes a small JSON API:
  GET  /api/catalogue            geometry list, parameter schema, propellants, thumbnails
  POST /api/solve                {geometry, inputs}            -> results + SVG drawing
  POST /api/report               {geometry, inputs, format}    -> PDF or HTML report file
  POST /api/feedback             {rating, comment, name, ...}  -> stored in data/feedback.json
  GET  /download/Grain_yantra_1.zip                            -> the packaged software
"""

import io
import json
import mimetypes
import os
import socket
import sys
import threading
import time
import traceback
import urllib.parse
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import drawing, engine, report

APP_NAME = engine.APP_NAME
VERSION = "1.0.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
FROZEN = getattr(sys, "frozen", False)
DATA = os.path.join(os.path.dirname(sys.executable) if FROZEN else ROOT, "data")
_lock = threading.Lock()
_catalogue_cache = None

PACKAGE_EXCLUDE_DIRS = {"__pycache__", "data", "dist", "build", ".git", ".venv", "venv"}
PACKAGE_EXCLUDE_EXT = {".pyc", ".pyo", ".spec"}


def catalogue_payload():
    global _catalogue_cache
    if _catalogue_cache is None:
        cat = engine.catalogue()
        for g in cat["geometries"]:
            try:
                r = engine.solve(g["id"], engine.defaults(g["id"]))
                g["thumb"] = drawing.scene_svg(r["scene"], annotate=False, title=g["name"])
            except Exception:  # pragma: no cover - thumbnails are cosmetic
                g["thumb"] = ""
        cat["version"] = VERSION
        _catalogue_cache = cat
    return _catalogue_cache


def solve_payload(body):
    gid = body.get("geometry")
    inputs = body.get("inputs") or {}
    r = engine.solve(gid, inputs)
    r["svg"] = drawing.scene_svg(r["scene"], annotate=True, title=f"{r['geometry']['name']} cross-section")
    r.pop("scene", None)
    return r


def build_package_zip():
    buf = io.BytesIO()
    if FROZEN:  # running as a standalone executable: ship the executable itself
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(sys.executable, f"{APP_NAME}/{os.path.basename(sys.executable)}")
            readme = os.path.join(ROOT, "README.md")
            if os.path.exists(readme):
                z.write(readme, f"{APP_NAME}/README.md")
        return buf.getvalue()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = sorted(d for d in dirs if d not in PACKAGE_EXCLUDE_DIRS)
            for f in sorted(files):
                if os.path.splitext(f)[1] in PACKAGE_EXCLUDE_EXT:
                    continue
                full = os.path.join(base, f)
                rel = os.path.relpath(full, ROOT)
                info = zipfile.ZipInfo(os.path.join(APP_NAME, rel).replace(os.sep, "/"),
                                       time.localtime(os.path.getmtime(full))[:6])
                info.compress_type = zipfile.ZIP_DEFLATED
                if f.endswith((".sh", ".command")):
                    info.external_attr = 0o755 << 16
                else:
                    info.external_attr = 0o644 << 16
                with open(full, "rb") as fh:
                    z.writestr(info, fh.read())
        z.writestr(f"{APP_NAME}/data/.keep", "Feedback submitted in the app is stored here (feedback.json).\n")
    return buf.getvalue()


def save_feedback(body):
    try:
        rating = int(body.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        raise engine.InputError("Choose a rating from 1 to 5 stars.")
    entry = {
        "rating": rating,
        "comment": str(body.get("comment", ""))[:4000],
        "name": str(body.get("name", ""))[:120],
        "geometry": str(body.get("geometry", ""))[:60],
        "submitted": time.strftime("%Y-%m-%d %H:%M:%S"),
        "app": f"{APP_NAME} {VERSION}",
    }
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, "feedback.json")
    with _lock:
        items = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    items = json.load(fh)
            except (OSError, ValueError):
                items = []
        items.append(entry)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2, ensure_ascii=False)
    return {"ok": True, "saved_to": os.path.relpath(path, ROOT), "count": len(items)}


class Handler(BaseHTTPRequestHandler):
    server_version = f"{APP_NAME}/{VERSION}"

    def log_message(self, fmt, *args):  # keep the console quiet
        if os.environ.get("GY_DEBUG"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # ------------------------------------------------------------ helpers
    def _send(self, code, body, ctype, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 2_000_000:
            raise engine.InputError("Request too large.")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            raise engine.InputError("Malformed request.")

    # ------------------------------------------------------------ routes
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path == "/api/catalogue":
                return self._json(catalogue_payload())
            if path == "/api/health":
                return self._json({"ok": True, "app": APP_NAME, "version": VERSION})
            if path == "/api/report":
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                try:
                    body = json.loads(q.get("data", ["{}"])[0])
                except ValueError:
                    raise engine.InputError("Malformed report request.")
                return self._report(body)
            if path in (f"/download/{APP_NAME}.zip", "/download/package"):
                data = build_package_zip()
                return self._send(200, data, "application/zip",
                                  {"Content-Disposition": f'attachment; filename="{APP_NAME}.zip"'})
            return self._static(path)
        except engine.InputError as e:
            return self._send(400, f"Report not generated: {e}".encode("utf-8"), "text/plain; charset=utf-8")
        except Exception as e:  # pragma: no cover
            traceback.print_exc()
            return self._json({"ok": False, "error": str(e)}, 500)

    def _report(self, body):
        gid = body.get("geometry")
        inputs = body.get("inputs") or {}
        fmt = body.get("format", "pdf")
        res = engine.solve(gid, inputs)
        meta = report.report_meta(res, inputs)
        name = report.file_basename(res, meta)
        if fmt == "html":
            data = report.build_html(res, meta).encode("utf-8")
            return self._send(200, data, "text/html; charset=utf-8",
                              {"Content-Disposition": f'attachment; filename="{name}.html"', "X-Filename": name + ".html"})
        data = report.build_pdf(res, meta)
        return self._send(200, data, "application/pdf",
                          {"Content-Disposition": f'attachment; filename="{name}.pdf"', "X-Filename": name + ".pdf"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/solve":
                return self._json(solve_payload(body))
            if path == "/api/report":
                return self._report(body)
            if path == "/api/feedback":
                return self._json(save_feedback(body))
            return self._json({"ok": False, "error": "Not found"}, 404)
        except engine.InputError as e:
            return self._json({"ok": False, "error": str(e), "input_error": True}, 400)
        except Exception as e:
            traceback.print_exc()
            return self._json({"ok": False, "error": f"Internal error: {e}"}, 500)

    def _static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        rel = os.path.normpath(urllib.parse.unquote(path).lstrip("/"))
        full = os.path.join(WEB, rel)
        if not os.path.abspath(full).startswith(os.path.abspath(WEB) + os.sep) or not os.path.isfile(full):
            return self._send(404, b"Not found", "text/plain")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as fh:
            return self._send(200, fh.read(), ctype)


def find_port(preferred=8765):
    for port in [preferred] + list(range(preferred + 1, preferred + 40)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_server(port=None):
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("image/svg+xml", ".svg")
    port = port or find_port()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    return httpd, port
