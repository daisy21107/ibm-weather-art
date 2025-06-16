#!/usr/bin/env bash
#
# One-click launcher for the AIWeather app.
# -------------------------------------------------------------
# * Works no matter where the user double-clicks it from.
# * Activates the existing “iwa-venv” virtual-env.
# * Forwards any extra arguments to the Python program.
# -------------------------------------------------------------

# Resolve the absolute path to this script’s directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR" || exit 1        # fail hard if the repo folder cannot be entered

# Activate the virtual environment
source iwa-venv/bin/activate

# Start the Kivy UI
exec python UI/main.py "$@"
