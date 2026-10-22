#!/usr/bin/env python3
"""Grain_yantra_1 - Solid Propellant Grain Geometry Design Software.

Run:  python Grain_yantra_1.py            (opens the app window / your browser)
      python Grain_yantra_1.py --no-browser --port 8765

Only the Python 3.8+ standard library is required. If the optional `pywebview`
package is installed, the app opens in its own desktop window titled Grain_yantra_1;
otherwise it opens in your default web browser.
"""

import argparse
import os
import sys
import threading
import webbrowser

if sys.version_info < (3, 8):
    sys.stderr.write("Grain_yantra_1 needs Python 3.8 or newer. Install it from https://www.python.org/downloads/\n")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from grain_yantra.server import APP_NAME, VERSION, make_server  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=f"{APP_NAME} - solid propellant grain geometry design")
    ap.add_argument("--port", type=int, default=None, help="port to serve on (default: 8765 or the next free port)")
    ap.add_argument("--no-browser", action="store_true", help="do not open a window or browser")
    ap.add_argument("--browser", action="store_true", help="always use the web browser, even if pywebview is installed")
    args = ap.parse_args()

    httpd, port = make_server(args.port)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 62)
    print(f"  {APP_NAME}  v{VERSION}")
    print("  Solid Propellant Grain Geometry Design Software")
    print("=" * 62)
    print(f"  Running at {url}")
    print("  Keep this window open while you use the software.")
    print("  Press Ctrl+C to quit.\n")

    webview = None
    if not args.no_browser and not args.browser:
        try:
            import webview  # type: ignore  # optional
        except Exception:
            webview = None

    if webview is not None:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        webview.create_window(APP_NAME, url, width=1360, height=880, min_size=(960, 640))
        webview.start()
        httpd.shutdown()
        return

    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{APP_NAME} stopped.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
