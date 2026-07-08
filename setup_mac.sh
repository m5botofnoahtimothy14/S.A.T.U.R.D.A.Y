#!/bin/bash
# SATURDAY - macOS Setup Script
# ==============================
set -e

echo "========================================="
echo "  SATURDAY 3.0 - macOS Setup"
echo "========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check Python
echo -e "${YELLOW}[1/7] Checking Python...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python3 not found. Install with: brew install python@3.12${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}Found: $PYTHON_VERSION${NC}"

# Check/Install Homebrew dependencies
echo -e "${YELLOW}[2/7] Checking system dependencies via Homebrew...${NC}"
if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

echo "Installing portaudio (for PyAudio)..."
brew install portaudio 2>/dev/null || true

echo "Installing cmake (for dlib)..."
brew install cmake 2>/dev/null || true

echo "Installing other dependencies..."
brew install ffmpeg 2>/dev/null || true
brew install mosquitto 2>/dev/null || true

# Create virtual environment
echo -e "${YELLOW}[3/7] Creating Python virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "${GREEN}Virtual environment created.${NC}"
else
    echo -e "${GREEN}Virtual environment already exists.${NC}"
fi

# Activate venv
source .venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}[4/7] Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel

# Install Python dependencies
echo -e "${YELLOW}[5/7] Installing Python dependencies (this may take a while)...${NC}"
pip install -r requirements_mac.txt

# Create directories
echo -e "${YELLOW}[6/7] Creating required directories...${NC}"
mkdir -p logs data models

# Create prod.env if not exists
echo -e "${YELLOW}[7/7] Checking configuration...${NC}"
if [ ! -f "prod.env" ]; then
    cat > prod.env << 'EOF'
# SATURDAY Production Environment (macOS)
HOST=0.0.0.0
PORT=8000
WORKERS=1
LOG_LEVEL=info
SECRET_KEY=change-me-to-a-random-string
ALLOWED_HOSTS=*
SATURDAY_STRICT_PROD=false
SATURDAY_DISABLE_AUTH=true
SATURDAY_CORE_ORIGINS=http://localhost:5173,http://localhost:8000
MQTT_BROKER=localhost
MQTT_PORT=1883
EOF
    echo -e "${GREEN}Created prod.env with defaults.${NC}"
else
    echo -e "${GREEN}prod.env already exists.${NC}"
fi

echo ""
echo "========================================="
echo -e "${GREEN}  Setup complete!${NC}"
echo "========================================="
echo ""
echo "To run SATURDAY:"
echo "  source .venv/bin/activate"
echo "  python run_production.py --dev"
echo ""
echo "Then open: http://localhost:8000"
echo ""
echo "Optional - Start MQTT broker:"
echo "  brew services start mosquitto"
echo ""
