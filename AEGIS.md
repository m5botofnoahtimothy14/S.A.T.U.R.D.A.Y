# SATURDAY OS - System Documentation

SATURDAY (Advanced Engineering & Governance Intelligence System) is a local, AI-first operating system designed for local LLM orchestration, system governance, and embodied AI.

## 🛠 Permanent Environment
The system is anchored in a dedicated Python 3.12 virtual environment located at `./.venv`.
To maintain this environment, use:
```powershell
./setup.ps1
```

## 🏗 Build Components
- **Core Orchestrator**: Async event loop managing all modules.
- **Identity Layer**: Local SQLite database for user profiles and biometric metadata.
- **Communication Hub**: Integrated via Selenium for WhatsApp/Instagram and SMTP for Email.
- **Hybrid AI**: Automated switching between local Ollama nodes and cloud fallback.
- **Vision & Sensing**: OpenCV and MediaPipe for facial and gesture recognition.

## 🚀 Running the System
### Local Mode
```powershell
.venv\Scripts\python core/main.py
```
### Windows Service Mode
SATURDAY can run in the background as a native system service:
```powershell
cd services
# Install
python windows_service.py install
# Start
python windows_service.py start
```

## ⚙️ Configuration
Configure your system using the `.env` file (see `.env.example` for required keys).
- `LLM_MODEL`: Set to your preferred Ollama model (default: `llama3`).
- `MQTT_BROKER`: Set up for HomeBot integration.
