# SATURDAY Production Deployment Guide

## Quick Start

### Windows
```bash
# Install dependencies
pip install -r requirements.txt

# Run production server
python run_production.py
```

### Linux
```bash
# Install dependencies
pip install -r requirements.txt

# Make run script executable
chmod +x run_production.py

# Run production server
python run_production.py
```

## Running Modes

### Production Mode (Multi-worker)
```bash
python run_production.py --mode server
```
- Uses multiple workers based on CPU cores
- Optimized for high performance
- Best for production deployments

### Development Mode
```bash
python run_production.py --dev
```
- Auto-reload on code changes
- Single worker
- Debug logging enabled

### Standalone Mode
```bash
python run_production.py --mode standalone
```
- Single process
- Useful for debugging

## Configuration

Edit `prod.env` to configure:
- Server port (default: 8000)
- Worker count
- Security settings
- Feature flags

## Access

- Web UI: http://localhost:8000
- API: http://localhost:8000/api/*
- WebSocket: ws://localhost:8000/ws

## System Service

### Linux (systemd)
```bash
sudo cp saturday.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable saturday
sudo systemctl start saturday
```

### Windows (NSSM)
```cmd
# Install NSSM
choco install nssm

# Create service
nssm install SATURDAY "python" "run_production.py"
nssm set SATURDAY AppDirectory "D:\SATURDAY"
nssm set SATURDAY DisplayName "SATURDAY AI OS"
nssm set SATURDAY Description "Advanced Engine for Global Integrated Systems"
nssm start SATURDAY
```

## Production Checklist

- [ ] Update SECRET_KEY in prod.env
- [ ] Configure ALLOWED_HOSTS
- [ ] Set up reverse proxy (nginx)
- [ ] Configure SSL/TLS certificates
- [ ] Set up log rotation
- [ ] Configure firewall rules
- [ ] Set up backup for data/ directory

## Nginx Configuration (Optional)

```nginx
server {
    listen 443 ssl;
    server_name saturday.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```
