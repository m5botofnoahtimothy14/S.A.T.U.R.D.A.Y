#!/usr/bin/env bash
# SATURDAY home-Linux server — Ubuntu 24.04 on WSL2 or any bare Linux box.
# One command on the Linux side:
#   curl -sL https://raw.githubusercontent.com/m5botofnoahtimothy14/S.A.T.U.R.D.A.Y/master/SATURDAY_SYSTEM/cloud/linux-home-setup.sh | bash
# Then: tmux + unlock (same as cloud README). This node syncs with the
# Windows PC through Firebase RTDB (two nodes, one project):
#   PC exe  -> node "saturday-node"  (FIREBASE_NODE_ID)
#   Linux   -> node "saturday-linux" (FIREBASE_NODE_ID=saturday-linux)
# Both push presence + encrypted backups; either can read the other's
# presence. Ciphertext only, ever.
set -euo pipefail

echo "=== SATURDAY home-Linux setup ==="
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip git curl tmux \
    tesseract-ocr mosquitto mosquitto-clients portaudio19-dev
  sudo systemctl enable --now mosquitto || sudo service mosquitto start || true
fi

curl -fsSL https://ollama.com/install.sh | sh || true
(sudo systemctl enable --now ollama || true) 2>/dev/null || true
sleep 5
ollama pull llama3.2 || true
ollama pull moondream || true

if [ ! -d "$HOME/SATURDAY_SYSTEM" ]; then
  git clone --depth 1 https://github.com/m5botofnoahtimothy14/S.A.T.U.R.D.A.Y "$HOME/SATWORK" 2>/dev/null || true
  if [ -d "$HOME/SATWORK/SATURDAY_SYSTEM" ]; then
    mv "$HOME/SATWORK/SATURDAY_SYSTEM" "$HOME/SATURDAY_SYSTEM"
    rm -rf "$HOME/SATWORK"
  fi
fi
cd "$HOME/SATURDAY_SYSTEM"
python3 -m venv .venv 2>/dev/null || python3 -m venv --without-pip .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt || pip install cryptography python-dotenv firebase-admin \
  pyautogui pillow pytesseract opencv-contrib-python "numpy>=1.26,<3" scipy onnxruntime \
  sounddevice faster-whisper paho-mqtt pyserial

[ -f .env ] || cp .env.example .env
echo ""
echo "=== DONE. Make this node sync with home: ==="
echo "  1. .env: FIREBASE_SERVICE_ACCOUNT=/path/to/key.json"
echo "     FIREBASE_DATABASE_URL=https://aegis-os-75256-default-rtdb.asia-southeast1.firebasedatabase.app"
echo "     FIREBASE_NODE_ID=saturday-linux"
echo "  2. tmux new -s saturday && source .venv/bin/activate && python main.py"
echo "  3. Inside: cloudsetup <key> <url> saturday-linux && cloudbackup"
echo "  4. server / share on  -> same tunnel flow as PC"
