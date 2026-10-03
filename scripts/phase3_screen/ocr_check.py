import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import screen_operator as so
print("OCR_AVAILABLE:", so.ocr_available(), so._OCR_ERROR, flush=True)
op = so.ScreenOperator()
print("SIZE:", op.screen_size(), flush=True)
print("READ:", {k: v for k, v in op.read_screen(r"D:\screen_diag.png").items() if k != "words"}["text"][:200], flush=True)
r = op.read_screen(r"D:\screen_diag.png")
print("WORDS:", len(r.get("words", [])), "sample:", [(w["text"], w["x"], w["y"]) for w in r.get("words", [])[:8]], flush=True)
