import subprocess, os
PIPER = r"D:\S.A.T.U.R.D.A.Y\models\piper\piper\piper.exe"
WORK = r"D:\S.A.T.U.R.D.A.Y\models\piper\piper"
V = r"D:\S.A.T.U.R.D.A.Y\models\piper\voices"
tests = [("en_US-amy-medium.onnx", "EDITH here. Same mind, at your service."),
         ("en_US-ryan-medium.onnx", "SATURDAY online. All systems running.")]
for model, text in tests:
    out = os.path.join(r"D:\SATURDAY_TEMP", model.replace(".onnx", "_test.wav"))
    r = subprocess.run([PIPER, "--model", os.path.join(V, model),
                        "--output_file", out],
                       input=text, capture_output=True, text=True,
                       timeout=120, cwd=WORK)
    ok = os.path.exists(out) and os.path.getsize(out) > 10000
    print(f"{model}: rc={r.returncode} wav={os.path.getsize(out) if os.path.exists(out) else 0} "
          f"err={(r.stderr or '')[:120]}", flush=True)
    if ok:
        import winsound
        print(f"PLAYING {model} - listen", flush=True)
        winsound.PlaySound(out, winsound.SND_FILENAME)
print("DONE", flush=True)
