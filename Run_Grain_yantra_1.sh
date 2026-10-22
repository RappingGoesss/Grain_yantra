#!/usr/bin/env sh
# Grain_yantra_1 launcher for macOS / Linux
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 Grain_yantra_1.py "$@"
elif command -v python >/dev/null 2>&1; then
  exec python Grain_yantra_1.py "$@"
else
  echo "Grain_yantra_1 needs Python 3.8 or newer: https://www.python.org/downloads/"
  exit 1
fi
