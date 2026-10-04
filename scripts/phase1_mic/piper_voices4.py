import urllib.request, os
v = r"D:\S.A.T.U.R.D.A.Y\models\piper\voices"
os.makedirs(v, exist_ok=True)
base = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
files = ["en/en_US/joe/medium/en_US-joe-medium.onnx.json",
         "en/en_US/john/medium/en_US-john-medium.onnx",
         "en/en_US/john/medium/en_US-john-medium.onnx.json"]
for f in files:
    dst = os.path.join(v, os.path.basename(f))
    if os.path.exists(dst) and os.path.getsize(dst) > 1000000:
        print(f"have {os.path.basename(dst)}", flush=True)
        continue
    print(f"get {f} ...", flush=True)
    try:
        urllib.request.urlretrieve(base + "/" + f, dst)
        print(f"ok {os.path.getsize(dst)} bytes", flush=True)
    except Exception as e:
        print(f"FAIL {f}: {e}", flush=True)
print("DONE", flush=True)
