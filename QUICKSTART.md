# AEGIS AI OS - Quick Start Guide

## Website (Always Available)
The AEGIS Control Panel is hosted on Firebase and runs 24/7:
**https://aegis-ai-os.web.app**

## To Wake AEGIS Remotely

### Option 1: Using ngrok (Recommended for local testing)

1. **Download ngrok**: https://ngrok.com/download
2. **Start AEGIS locally**:
   ```bash
   python run_production.py
   ```

3. **Expose with ngrok** (in another terminal):
   ```bash
   ngrok http 8000
   ```

4. **Update the gateway URL**:
   - Copy your ngrok URL (e.g., `https://abc123.ngrok.io`)
   - Edit `aegis-control-panel/.env`
   - Change: `VITE_AEGIS_GATEWAY_URL=https://abc123.ngrok.io/api/secure`

5. **Deploy updated website**:
   ```bash
   cd aegis-control-panel
   npm run deploy
   ```

6. **Now you can wake AEGIS from the web!**

### Option 2: Deploy to a VPS/Server (Production)

1. **Upload AEGIS to your server**
2. **Set environment variables**:
   ```bash
   export HOST=0.0.0.0
   export PORT=8000
   export VITE_AEGIS_GATEWAY_URL=https://your-server.com/api/secure
   ```

3. **Start AEGIS**:
   ```bash
   python run_production.py
   ```

4. **Update .env with your server URL**
5. **Deploy website**

### Option 3: Cloud Run (Google Cloud)

1. **Build container**:
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/aegis-backend
   ```

2. **Deploy**:
   ```bash
   gcloud run deploy --image gcr.io/PROJECT_ID/aegis-backend
   ```

3. **Update .env with the Cloud Run URL**

---

## Quick Commands

### Start AEGIS locally:
```bash
python run_production.py
```

### Start in development mode:
```bash
python run_production.py --dev
```

### Deploy website:
```bash
cd aegis-control-panel
npm run deploy
```

---

## Troubleshooting

**"Wake failed: Network error"**
- AEGIS is not running, or ngrok tunnel is down
- Start AEGIS and ngrok, then try again

**"Missing VITE_AEGIS_GATEWAY_URL"**
- Update the .env file with your ngrok/server URL

**Firebase auth errors**
- Make sure Firebase config is correct in .env
