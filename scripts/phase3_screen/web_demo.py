import sys, time
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import screen_operator as so
op = so.ScreenOperator()

# research: light HTML results page, read it back
op.open_url("https://html.duckduckgo.com/html/?q=lofi+hip+hop+radio", confirm=True)
time.sleep(8.0)
s = op.screenshot(r"D:\demo_ddg.png")
rd = op.read_screen(s["path"])
print("DDG words:", len(rd.get("words", [])), "| sample:", rd.get("text", "")[:150], flush=True)

# youtube retry with long settle
op.open_url("https://www.youtube.com/watch?v=jfKfPfyJRdk", confirm=True)
s0 = op.screenshot(r"D:\demo_yt0.png")
st = op.wait_for_change(s0["path"], timeout=30.0)
print("YT settle:", {k: st.get(k) for k in ("changed_ratio", "stable")}, flush=True)
s1 = op.screenshot(r"D:\demo_yt1.png")
rd2 = op.read_screen(s1["path"])
print("YT words:", len(rd2.get("words", [])), "| sample:", rd2.get("text", "")[:150], flush=True)
print("DONE", flush=True)
