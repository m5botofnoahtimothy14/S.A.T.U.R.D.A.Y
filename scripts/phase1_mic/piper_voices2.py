import urllib.request, os
v = r"D:\S.A.T.U.R.D.A.Y\models\piper\voices"
os.makedirs(v, exist_ok=True)
base = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
files = ["en/en_US/lessac/medium/en_US-lessac-medium.onnx",
         "en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
         "en/en_US/bryce/medium/en_US-bryce-medium.onnx",
         "en/en_US/bryce/medium/en_US-bryce-medium.onnx.json"]
for f in files:
    dst = os.path.join(v, os.path.basename(f))
    if os.path.exists(dst) and os.path.getsize(dst) > 1000000:
        print(f"have {os.path.basename(dst)}", flush=True)
        continue
    print(f"get {f} ...", flush=True)
    urllib.request.urlretrieve(base + "/" + f, dst)
    print(f"ok {os.path.getsize(dst)} bytes", flush=True)
print("DONE", flush=True)
