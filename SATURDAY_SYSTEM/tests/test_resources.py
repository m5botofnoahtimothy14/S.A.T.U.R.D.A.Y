"""Resource governor + doctor boot gates. No hardware required."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from saturday import resources as R


def test_snapshot_shape():
    s = R.snapshot(cpu_interval=0, light=True)
    for k in ("cpu_pct", "ram_avail_gb", "disk_d_free_gb", "throttle"):
        assert k in s, k
    assert isinstance(s["throttle"].get("throttled"), bool)


def test_verdict_logic():
    base = {"cpu_pct": 10.0, "ram_avail_gb": 8.0, "disk_d_free_gb": 50.0,
            "temp": {"available": False}}
    assert R._verdict(base) == {"throttled": False, "reasons": []}
    hot = dict(base, cpu_pct=99.0)
    v = R._verdict(hot)
    assert v["throttled"] and any("CPU" in r for r in v["reasons"])
    noram = dict(base, ram_avail_gb=0.2)
    assert R._verdict(noram)["throttled"]
    temp = dict(base, temp={"available": True, "cpu_c": 95.0})
    assert R._verdict(temp)["throttled"]


def test_guard_ok_shape():
    g = R.guard("unit-probe")
    assert set(g) >= {"ok", "job"} and g["job"] == "unit-probe"
    assert isinstance(g["ok"], bool)
    if not g["ok"]:
        assert "reason" in g and "resources unload" in g["reason"]


def test_ollama_budget_shape():
    m = R.ollama_models()
    assert set(m) >= {"available", "models", "total_gb"}


def test_doctor_runs():
    from saturday.saturday_core import SATURDAYCore
    tmp = Path(tempfile.mkdtemp(prefix="doctor_test_"))
    core = SATURDAYCore(passphrase="DoctorTestPass123!", project_root=tmp)
    core._camera_frame = lambda: {"success": False, "error": "test rig: no camera"}
    try:
        out = core.process_command("doctor", trusted=True)
        assert out.startswith("🩺 Doctor:"), out[:200]
        for gate in ("vault", "mic", "hearing", "voice", "camera",
                     "brain", "blender", "tunnel-bin", "firebase", "resources"):
            assert gate in out, f"gate {gate} missing"
    finally:
        try:
            core.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_"):
            fn()
            print(f"PASS {name}")
    print("RESOURCES GREEN")
