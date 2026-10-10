"""SATURDAY Resources — system resource manager: meter, budget, protect.

Why it exists: Blender renders, SD image dreams, and stacked Ollama models
can pin CPU/RAM for minutes. This module meters the box, budgets model
memory, and REFUSES heavy jobs before they overheat or stall the machine —
an honest "not now, here's why" beats a frozen laptop every time.

- snapshot()      : cpu%, RAM, disk C:/D:, CPU temp (best-effort), Ollama
                    loaded models, throttle verdict. Never raises.
- should_throttle(): True when CPU>92%, RAM free<1GB, disk D:<2GB, or
                    temp>85C (when readable). Heavy jobs must ask first.
- ollama_models() : what's actually resident via Ollama /api/ps.
- unload_idle()   : `ollama stop` every loaded model (frees GBs before a
                    render/dream). Safe: models reload on next use.
- guard(job)      : returns {"ok": True} or {"ok": False, "reason"}.

All thresholds overridable via env (SATURDAY_CPU_MAX etc.). No new deps:
psutil is already required; temp via stdlib WMI on Windows.
"""

import logging
import os
import subprocess
import time
from typing import Any, Dict, List

logger = logging.getLogger("SATURDAY.Resources")

CPU_MAX = float(os.getenv("SATURDAY_CPU_MAX", "") or "92")
RAM_MIN_GB = float(os.getenv("SATURDAY_RAM_MIN_GB", "") or "1.0")
DISK_MIN_GB = float(os.getenv("SATURDAY_DISK_MIN_GB", "") or "2.0")
TEMP_MAX_C = float(os.getenv("SATURDAY_TEMP_MAX_C", "") or "85")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")

_last_snapshot: Dict[str, Any] = {}
_last_at = 0.0


def cpu_temp_c() -> Dict[str, Any]:
    """Best-effort CPU temp. Most Windows laptops hide this from WMI —
    unavailable is reported honestly, never faked."""
    try:
        import subprocess as _sp
        ps = ("Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace "
              "root/wmi -ErrorAction Stop | Select-Object -ExpandProperty "
              "CurrentTemperature")
        r = _sp.run(["powershell", "-NoProfile", "-Command", ps],
                    capture_output=True, text=True, timeout=6)
        vals = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if line.isdigit():
                c = int(line) / 10.0 - 273.15
                if 20.0 <= c <= 120.0:
                    vals.append(round(c, 1))
        if vals:
            return {"available": True, "cpu_c": max(vals)}
    except Exception as e:
        logger.debug(f"cpu temp unreadable: {e}")
    return {"available": False, "cpu_c": None}


def ollama_models() -> Dict[str, Any]:
    """What's resident in Ollama RAM right now (/api/ps)."""
    try:
        import json as _j
        import urllib.request as _u
        req = _u.Request(OLLAMA_HOST + "/api/ps", method="GET")
        with _u.urlopen(req, timeout=4) as resp:
            data = _j.loads(resp.read().decode())
        models = [{"name": m.get("name", "?"),
                   "size_gb": round(m.get("size", 0) / 1e9, 2)}
                  for m in data.get("models", [])]
        return {"available": True, "models": models,
                "total_gb": round(sum(m["size_gb"] for m in models), 2)}
    except Exception as e:
        return {"available": False, "models": [], "total_gb": 0.0,
                "error": str(e)[:100]}


def unload_idle(except_models: List[str] = ()) -> Dict[str, Any]:
    """Stop resident Ollama models to free GBs before heavy jobs.
    Safe: Ollama reloads any model on next use (slow first call)."""
    info = ollama_models()
    if not info.get("available"):
        return {"success": False, "error": "Ollama unreachable"}
    freed, kept, failed = 0.0, [], []
    keep = {k.lower() for k in (except_models or [])}
    for m in info["models"]:
        name = m["name"]
        if any(k in name.lower() for k in keep):
            kept.append(name)
            continue
        try:
            r = subprocess.run(["ollama", "stop", name],
                               capture_output=True, text=True, timeout=60)
            if r.returncode == 0:
                freed += m["size_gb"]
            else:
                failed.append(name)
        except Exception as e:
            failed.append(f"{name} ({e})"[:80])
    return {"success": not failed, "freed_gb": round(freed, 2),
            "kept": kept, "failed": failed}


def snapshot(force: bool = False, cpu_interval: float = 1.0,
             light: bool = False) -> Dict[str, Any]:
    """Full meter reading. Cached 5s so HUD polling can't hot-spin.
    cpu_interval=0 for non-blocking reads (HUD payload); 1.0 for accuracy.
    light=True skips slow probes (WMI temp, Ollama ps) — sub-second HUD path."""
    global _last_snapshot, _last_at
    if not force and _last_snapshot and time.time() - _last_at < 5.0:
        return dict(_last_snapshot)
    out: Dict[str, Any] = {"at": time.time()}
    try:
        import psutil
        out["cpu_pct"] = round(psutil.cpu_percent(interval=cpu_interval), 1)
        vm = psutil.virtual_memory()
        out["ram_total_gb"] = round(vm.total / 1e9, 2)
        out["ram_avail_gb"] = round(vm.available / 1e9, 2)
        out["ram_pct"] = round(vm.percent, 1)
        for drive, key in (("C:/", "disk_c_free_gb"), ("D:/", "disk_d_free_gb")):
            try:
                out[key] = round(psutil.disk_usage(drive).free / 1e9, 2)
            except Exception:
                out[key] = None
        try:
            out["load_1m"] = round(psutil.getloadavg()[0], 2)
        except Exception:
            out["load_1m"] = None
    except Exception as e:
        out["error"] = f"psutil failed: {e}"
        out.update({"cpu_pct": 0.0, "ram_avail_gb": 0.0,
                    "disk_d_free_gb": None})
    t = cpu_temp_c() if not light else {"available": False, "cpu_c": None,
                                          "note": "light mode"}
    out["temp"] = t
    out["ollama"] = ollama_models() if not light else {"available": None,
                                                       "models": [], "total_gb": 0.0,
                                                       "note": "light mode"}
    out["throttle"] = _verdict(out)
    _last_snapshot, _last_at = dict(out), time.time()
    return out


def _verdict(s: Dict[str, Any]) -> Dict[str, Any]:
    reasons = []
    if s.get("cpu_pct", 0) > CPU_MAX:
        reasons.append(f"CPU {s['cpu_pct']}% > {CPU_MAX:g}% cap")
    if (s.get("ram_avail_gb") or 99) < RAM_MIN_GB:
        reasons.append(f"RAM free {s.get('ram_avail_gb')}GB < {RAM_MIN_GB:g}GB floor")
    if (s.get("disk_d_free_gb") or 99) < DISK_MIN_GB:
        reasons.append(f"D: free {s.get('disk_d_free_gb')}GB < {DISK_MIN_GB:g}GB floor")
    t = (s.get("temp") or {})
    if t.get("available") and (t.get("cpu_c") or 0) > TEMP_MAX_C:
        reasons.append(f"CPU {t['cpu_c']}C > {TEMP_MAX_C:g}C ceiling")
    return {"throttled": bool(reasons), "reasons": reasons}


def should_throttle() -> Dict[str, Any]:
    return snapshot().get("throttle", {"throttled": False, "reasons": []})


def guard(job: str) -> Dict[str, Any]:
    """Heavy jobs call this first. Returns ok True/False + a remedy."""
    v = should_throttle()
    if not v.get("throttled"):
        return {"ok": True, "job": job}
    remedy = ("Free the box first: `resources unload` drops resident models, "
              "close heavy apps, then retry. Nothing was started.")
    return {"ok": False, "job": job,
            "reason": f"'{job}' deferred — " + "; ".join(v["reasons"]) + ". " + remedy}


def status_line() -> str:
    s = snapshot()
    t = (s.get("temp") or {})
    temp_s = f"{t['cpu_c']}C" if t.get("available") else "temp n/a"
    v = s.get("throttle", {})
    flag = "🟢" if not v.get("throttled") else "🔴 THROTTLED"
    return (f"{flag} CPU {s.get('cpu_pct')}% | RAM free {s.get('ram_avail_gb')}GB | "
            f"D: free {s.get('disk_d_free_gb')}GB | {temp_s} | "
            f"Ollama {s.get('ollama', {}).get('total_gb', 0)}GB resident")
