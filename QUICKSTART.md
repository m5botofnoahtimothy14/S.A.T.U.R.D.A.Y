# SATURDAY AI OS - Quick Start Guide

## Website (Always Available)
The SATURDAY Control Panel is hosted on Firebase and runs 24/7:
**https://saturday-ai-os.web.app**

## To Wake SATURDAY Remotely

### Option 1: Using ngrok (Recommended for local testing)

1. **Download ngrok**: https://ngrok.com/download
2. **Start SATURDAY locally**:
   ```bash
   python run_production.py
   ```

3. **Expose with ngrok** (in another terminal):
   ```bash
   ngrok http 8000
   ```

4. **Update the gateway URL**:
   - Copy your ngrok URL (e.g., `https://abc123.ngrok.io`)
   - Edit `saturday-control-panel/.env`
   - Change: `VITE_SATURDAY_GATEWAY_URL=https://abc123.ngrok.io/api/secure`

5. **Deploy updated website**:
   ```bash
   cd saturday-control-panel
   npm run deploy
   ```

6. **Now you can wake SATURDAY from the web!**

### Option 2: Deploy to a VPS/Server (Production)

1. **Upload SATURDAY to your server**
2. **Set environment variables**:
   ```bash
   export HOST=0.0.0.0
   export PORT=8000
   export VITE_SATURDAY_GATEWAY_URL=https://your-server.com/api/secure
   ```

3. **Start SATURDAY**:
   ```bash
   python run_production.py
   ```

4. **Update .env with your server URL**
5. **Deploy website**

### Option 3: Cloud Run (Google Cloud)

1. **Build container**:
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/saturday-backend
   ```

2. **Deploy**:
   ```bash
   gcloud run deploy --image gcr.io/PROJECT_ID/saturday-backend
   ```

3. **Update .env with the Cloud Run URL**

---

## Quick Commands

### Start SATURDAY locally:
```bash
python run_production.py
```

### Start in development mode:
```bash
python run_production.py --dev
```

### Deploy website:
```bash
cd saturday-control-panel
npm run deploy
```

---

## Troubleshooting

**"Wake failed: Network error"**
- SATURDAY is not running, or ngrok tunnel is down
- Start SATURDAY and ngrok, then try again

**"Missing VITE_SATURDAY_GATEWAY_URL"**
- Update the .env file with your ngrok/server URL

**Firebase auth errors**
- Make sure Firebase config is correct in .env
