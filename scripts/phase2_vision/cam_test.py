import cv2, numpy as np
print("cv2:", cv2.__version__, flush=True)
for backend, bname in ((cv2.CAP_DSHOW, "DSHOW"), (cv2.CAP_MSMF, "MSMF")):
    for idx in (0, 1, 2):
        cap = cv2.VideoCapture(idx, backend)
        opened = cap.isOpened()
        info = f"{bname} idx={idx}: opened={opened}"
        if opened:
            ok, frame = cap.read()
            if ok and frame is not None:
                mean = float(frame.mean()); mx = int(frame.max())
                h, w = frame.shape[:2]
                nonblack = "NON-BLACK" if mean > 3.0 else "BLACK"
                info += f" shape={w}x{h} mean={mean:.1f} max={mx} {nonblack}"
            else:
                info += " read FAILED"
        print(info, flush=True)
        cap.release()
print("DONE", flush=True)
