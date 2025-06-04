#!/usr/bin/env bash
# ----------------------------------------------------------------------
# setup.sh  –  one-shot project bootstrap for Raspberry Pi (64-bit OS)
#
#  • Installs system libraries the very first time (sudo password needed)
#  • Creates / reuses a Python venv called “iwa-venv”
#  • Installs all Python packages from requirements.txt
#  • Redirects pip / HF / PyTorch / yt-dlp caches into ./.cache/
#  • Generates a skeleton .env file on first run
#  • Ensures a data/ directory exists
#  • Downloads the two emoji/icon fonts into UI/fonts if missing
# ----------------------------------------------------------------------
set -euo pipefail

# -------- 0) system-wide C/C++ libraries (one-time) -------------------
if ! dpkg -s libvlc-dev >/dev/null 2>&1; then
  echo "🔧 Installing system libraries (sudo password may be required)…"
  sudo apt update
  sudo apt install -y python3-venv python3-dev build-essential \
       libffi-dev libssl-dev libvlc-dev \
       libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
       libgl1-mesa-dev libgles2-mesa-dev \
       libgstreamer1.0-dev gstreamer1.0-plugins-base gstreamer1.0-plugins-good
else
  echo "✔︎ System libraries already present – skipping apt install."
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
  echo "⚙️  Creating venv post-activate hook to relocate caches…"
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

#  -- optional but faster: pull PyTorch wheel first -------------------
pip install --no-cache-dir torch==2.3.0 \
  --index-url https://download.pytorch.org/whl/cpu
  
#  -- bulk-install everything else ------------------------------------
pip install --no-cache-dir -r requirements.txt

# -------- 4) scaffold .env with empty keys ---------------------------
if [ ! -f .env ]; then
  echo "🗝️  Creating .env file with API-key placeholders…"
  cat <<'EOF' > .env
# ─── API / Secret keys ────────────────────────────────────────────────
WATSONX_AI_URL=
WATSONX_API_KEY=
WATSONX_PROJECT_ID=
WATSONX_MODEL_ID=
OPENWEATHER_API_KEY=
GUARDIAN_API_KEY=
EOF
  echo "→ .env created — fill in your keys before running the app."
else
  echo "✔︎ .env already exists — leaving it unchanged."
fi

# -------- 5) make sure data/ folder is present -----------------------
mkdir -p data/
echo "📂 Ensured data/ directory exists."

# -------- 6) ensure UI/fonts directory & download icon fonts --------
# main.py expects:
#   • 'UI/fonts/NotoSansSymbols2-Regular.ttf'  (icon glyphs)
#   • 'UI/fonts/fa-solid-900.ttf'              (Font Awesome solid)
# If missing, fetch from GitHub raw URLs.
FONTS_DIR="UI/fonts"
mkdir -p "$FONTS_DIR"

if [ ! -f "$FONTS_DIR/NotoSansSymbols2-Regular.ttf" ]; then
  echo "⬇️  Downloading NotoSansSymbols2-Regular.ttf…"
  wget -q -O "$FONTS_DIR/NotoSansSymbols2-Regular.ttf" \
    "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/NotoSansSymbols2/NotoSansSymbols2-Regular.ttf"
  echo "   → Saved to $FONTS_DIR/NotoSansSymbols2-Regular.ttf"
else
  echo "✔︎ NotoSansSymbols2-Regular.ttf already present."
fi

if [ ! -f "$FONTS_DIR/fa-solid-900.ttf" ]; then
  echo "⬇️  Downloading fa-solid-900.ttf…"
  wget -q -O "$FONTS_DIR/fa-solid-900.ttf" \
    "https://github.com/FortAwesome/Font-Awesome/raw/6.x/webfonts/fa-solid-900.ttf"
  echo "   → Saved to $FONTS_DIR/fa-solid-900.ttf"
else
  echo "✔︎ fa-solid-900.ttf already present."
fi

# -------- 7) helpful Kivy environment tweaks -------------------------
echo
echo "👉 Tip: add these to ~/.bashrc if you run Kivy full-screen:"
echo "   export KIVY_GL_BACKEND=sdl2"
echo "   export KIVY_WINDOW=sdl2"
echo

echo "✅ Setup complete!  Run:"
echo "   source iwa-venv/bin/activate && python main.py"
