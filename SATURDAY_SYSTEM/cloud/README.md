# SATURDAY on Oracle Cloud (free forever)

## 1. Account (your hands, ~10 min + approval wait)
- cloud.oracle.com → Start for free → email + card (verification hold only).
- If "out of capacity": retry, or switch region (ap-hyderabad-1 ↔ ap-mumbai-1).

## 2. Instance (Always Free eligible!)
- Shape: **Ampere ARM**, 4 OCPU, 24 GB RAM. Image: Ubuntu 24.04.
- Boot volume 100 GB. VCN default. **Save the SSH private key** (`saturday.key`).
- Paste `cloud/oracle-setup.sh` content into **Advanced options → user-data**,
  or run it manually after first SSH.

## 3. First unlock (SSH, one time)
```bash
ssh -i saturday.key ubuntu@<PUBLIC-IP>
cd ~/SATURDAY_SYSTEM && source .venv/bin/activate
tmux new -s saturday
python main.py   # enter vault passphrase, leave it running (Ctrl+B, D to detach)
```

## 4. Handoff to me
Give me the **public IP + path to saturday.key on YOUR pc** (never paste the
key itself). I will SSH from here: verify services, open the tunnel
(`share on` inside tmux via `tmux send-keys`), and confirm world-access.

## Notes
- ARM Linux runs SATURDAY from **source**, not the Windows .exe.
- Whisper/onnx/ollama all ship ARM builds — microphone/camera are the only
  things that stay home (the VM is headless; senses that need hardware
  report honestly unavailable there).
- Keep the home PC as primary brain; the VM is uptime + public front door.
