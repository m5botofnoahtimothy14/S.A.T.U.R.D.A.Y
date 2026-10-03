import sys
sys.path.insert(0, r"D:\S.A.T.U.R.D.A.Y\SATURDAY_SYSTEM")
from saturday import ears
print("candidates:", ears._candidate_inputs(), flush=True)
for d in [9, 1]:
    out = {}
    ears._record_native(d, 2.0, out)
    if "samples" in out:
        print(f"dev {d}: OK sr={out['recorded_sr']} n={len(out['samples'])} peak={abs(out['samples']).max()}", flush=True)
    else:
        print(f"dev {d}: FAIL {out.get('error')}", flush=True)
