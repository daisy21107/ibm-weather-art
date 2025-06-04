#!/usr/bin/env bash
# ----------------------------------------------------------------------
# setup.sh  –  one‑shot project bootstrap for Raspberry Pi (64‑bit OS)
#
#  • Installs system libraries the very first time (sudo password needed)
#    now including Noto Color Emoji for Kivy‑Label emoji support
#  • Creates / reuses a Python venv called “iwa‑venv”
#  • Installs all Python packages from requirements.txt
#  • Redirects pip / HF / PyTorch / yt‑dlp caches into ./.cache/
#  • Generates a skeleton UI/.env file on first run (next to main.py)
#  • Ensures a data/ directory exists
# ----------------------------------------------------------------------
set -euo pipefail

# -------- 0) system‑wide C/C++ libraries (one‑time) -------------------
if ! dpkg -s libvlc-dev >/dev/null 2>&1; then
  echo "🔧 Installing system libraries (sudo password may be required)…"
  sudo apt update
  sudo apt install -y python3-venv python3-dev build-essential \
       libffi-dev libssl-dev libvlc-dev \
       libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
       libgl1-mesa-dev libgles2-mesa-dev \
       libgstreamer1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
       fonts-noto-color-emoji            # ← emoji glyphs for Kivy labels
else
  echo "✔︎ System libraries already present – skipping apt install."
fi

# -------- emoji font symlink so Kivy finds 'Emoji.ttf' ---------------
EMOJI_SRC="/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
EMOJI_DST="$HOME/.local/share/fonts/Emoji.ttf"
if [ -f "$EMOJI_SRC" ] && [ ! -f "$EMOJI_DST" ]; then
  echo "🔤 Linking NotoColorEmoji.ttf → Emoji.ttf for Kivy…"
  mkdir -p "$(dirname "$EMOJI_DST")"
  ln -s "$EMOJI_SRC" "$EMOJI_DST"
  fc-cache -f -v >/dev/null 2>&1 || true
fi

# -------- 1) create & activate virtual environment -------------------
if [ ! -d "iwa-venv" ]; then
  echo "🐍 Creating virtual environment (Python 3)…"
  python3 -m venv iwa-venv
fi
# shellcheck disable=SC1091
source iwa-venv/bin/activate
echo "🔗 Virtual environment 'iwa-venv' activated."

# -------- 2) redirect caches into the repo ---------------------------
ACTIVATE_POST="$VIRTUAL_ENV/bin/postactivate"
if [ ! -f "$ACTIVATE_POST" ]; then
  echo "⚙️  Creating venv post‑activate hook to relocate caches…"
  cat <<'EOF' > "$ACTIVATE_POST"
# --- local cache dirs to keep everything inside /home/pi/aiweather ---
export PIP_CACHE_DIR="$VIRTUAL_ENV/../.cache/pip"
export HF_HOME="$VIRTUAL_ENV/../.cache/huggingface"
export TRANSFORMERS_CACHE="$HF_HOME"
export TORCH_HOME="$VIRTUAL_ENV/../.cache/torch"
export YTDLP_HOME="$VIRTUAL_ENV/../.cache/yt-dlp"
EOF
  chmod +x "$ACTIVATE_POST"
fi
# shellcheck disable=SC1091
source "$ACTIVATE_POST"
echo "🗂  Cache directories redirected into ./\.cache/*"

# -------- 3) upgrade installer tools, then install deps --------------
python -m pip install --upgrade pip setuptools wheel

#  -- pull PyTorch wheel first (fastest on ARM) -----------------------
pip install --no-cache-dir torch==2.3.0 --index-url https://pypi.org/simple

#  -- bulk‑install everything else ------------------------------------
pip install --no-cache-dir -r requirements.txt

# -------- 4) scaffold UI/.env with empty keys ------------------------
if [ ! -f UI/.env ]; then
  echo "🗝️  Creating UI/.env file with API‑key placeholders…"
  cat <<'EOF' > UI/.env
# ─── API / Secret keys ────────────────────────────────────────────────
WATSONX_AI_URL=
WATSONX_API_KEY=
WATSONX_PROJECT_ID=
WATSONX_MODEL_ID=
OPENWEATHER_API_KEY=
GUARDIAN_API_KEY=
EOF
  echo "→ UI/.env created — fill in your keys before running the app."
else
  echo "✔︎ UI/.env already exists — leaving it unchanged."
fi

# -------- 5) make sure data/ folder is present -----------------------
mkdir -p data/
echo "📂 Ensured data/ directory exists."

# -------- 6) helpful Kivy environment tweaks ------------------------
echo
echo "👉 Tip: add these to ~/.bashrc if you run Kivy full‑screen:"
echo "   export KIVY_GL_BACKEND=sdl2"
echo "   export KIVY_WINDOW=sdl2"
echo

echo "✅ Setup complete!  Run:"
echo "   source iwa-venv/bin/activate && python UI/main.py"
