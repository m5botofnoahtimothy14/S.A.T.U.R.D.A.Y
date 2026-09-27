#!/usr/bin/env bash
# SATURDAY Oracle Cloud deploy — Ubuntu 22.04/24.04 ARM (Ampere, free forever).
# Run ONCE on a fresh instance (or via cloud-init user-data):
#   curl -sL https://raw.githubusercontent.com/m5botofnoahtimothy14/S.A.T.U.R.D.A.Y/master/SATURDAY_SYSTEM/cloud/oracle-setup.sh | bash
# Then: ssh in, cd ~/SATURDAY_SYSTEM, unlock once inside tmux (see cloud/README).
set -euo pipefail

echo "=== SATURDAY Oracle setup ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git curl tmux \
  tesseract-ocr mosquitto mosquitto-clients portaudio19-dev

# Ollama (ARM64 build exists) + models
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama || true
sleep 5
ollama pull llama3.2 || true
ollama pull moondream || true

# Repo
if [ ! -d "$HOME/SATURDAY_SYSTEM" ]; then
  git clone https://github.com/m5botofnoahtimothy14/S.A.T.U.R.D.A.Y "$HOME/SATWORK" 2>/dev/null || true
  if [ -d "$HOME/SATWORK/SATURDAY_SYSTEM" ]; then
    mv "$HOME/SATWORK/SATURDAY_SYSTEM" "$HOME/SATURDAY_SYSTEM"
    rm -rf "$HOME/SATWORK"
  fi
fi
cd "$HOME/SATURDAY_SYSTEM"

# Venv + deps (pinned; ARM wheels exist for all of these)
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt || pip install cryptography python-dotenv firebase-admin \
  pyautogui pillow pytesseract opencv-contrib-python "numpy>=1.26,<3" scipy onnxruntime \
  sounddevice faster-whisper paho-mqtt pyserial

# Mosquitto locally (HomeBot bus) + cloudflared (share tunnels work here too)
sudo systemctl enable --now mosquitto || true
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o /tmp/cf.deb \
  && sudo dpkg -i /tmp/cf.deb || echo "cloudflared optional - install manually"

# Env template (fill secrets, never commit)
[ -f .env ] || cp .env.example .env
echo ""
echo "=== DONE. Next (over ssh): ==="
echo "  cd ~/SATURDAY_SYSTEM && source .venv/bin/activate"
echo "  tmux new -s saturday"
echo "  python main.py   # unlock ONCE, leave tmux running"
echo "  # inside SATURDAY: share on   (public URL, same as home)"
