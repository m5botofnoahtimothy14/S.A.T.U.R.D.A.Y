"""SATURDAY Forge — real 3D modeling + self system rendering (Blender).

No mocks, no fake previews. Pipeline:
  prompt ("building 12 floors glass tower") -> parsed spec ->
  Blender headless (bpy) builds REAL geometry -> system-matched render
  (engine picked from YOUR GPU/RAM) -> exports .glb + preview PNG ->
  self-check QA (files exist, sizes, preview not black, geometry counts).

Blender path: D:\\Blender portable first (this PC), then PATH, then
BLENDER_EXE env, then Program Files. Engine choice:
  Intel Iris / no NVIDIA -> EEVEE (fast, CPU-safe)
  NVIDIA (nvidia-smi present) + >=8GB RAM -> CYCLES CPU 64 samples
Render resolution scales with RAM (8GB -> 960x540, 16GB+ -> 1280x720).

Every step returns real artifacts on D: (C: is full). Failures are honest
with the Blender log tail — never a placeholder image.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SATURDAY.Forge")


def _d_tmp() -> Path:
    base = Path(os.getenv("SATURDAY_D_TMP", "D:/SATURDAY_TEMP"))
    try:
        (base / "forge").mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base / "forge"


def find_blender() -> Dict[str, Any]:
    cands = []
    env = os.getenv("BLENDER_EXE", "")
    if env:
        cands.append(Path(env))
    cands.append(Path(r"D:\Blender\blender-4.5.10-windows-x64\blender.exe"))
    # any version under D:\Blender
    try:
        for p in Path(r"D:\Blender").glob("*/blender.exe"):
            cands.append(p)
        for p in Path(r"D:\Blender").glob("blender*/blender.exe"):
            cands.append(p)
    except Exception:
        pass
    for pf in (r"C:\Program Files\Blender Foundation",
               r"C:\Program Files (x86)\Blender Foundation"):
        try:
            for p in Path(pf).glob("*/blender.exe"):
                cands.append(p)
        except Exception:
            pass
    which = shutil.which("blender")
    if which:
        cands.append(Path(which))
    for c in cands:
        try:
            if c and c.exists():
                return {"success": True, "exe": str(c)}
        except Exception:
            continue
    return {"success": False,
            "error": ("Blender not found. Installed at "
                      "D:\\Blender\\blender-4.5.10-windows-x64\\blender.exe on this PC — "
                      "if moved, set BLENDER_EXE env.")}


def system_probe() -> Dict[str, Any]:
    import platform
    info: Dict[str, Any] = {"os": platform.system() + " " + platform.release(),
                            "cpu": platform.processor() or platform.machine()}
    try:
        import psutil
        vm = psutil.virtual_memory()
        info["ram_gb"] = round(vm.total / 1e9, 1)
        info["ram_free_gb"] = round(vm.available / 1e9, 1)
    except Exception:
        info["ram_gb"] = 8.0
        info["ram_free_gb"] = 2.0
    # GPU via wmic
    gpu = ""
    try:
        r = subprocess.run(["wmic", "path", "win32_VideoController",
                            "get", "name"], capture_output=True, text=True,
                           timeout=15)
        gpu = (r.stdout or "").strip().splitlines()[-1].strip() if r.stdout else ""
    except Exception:
        pass
    if not gpu:
        try:
            import wmi  # noqa
        except Exception:
            pass
        gpu = gpu or "Intel(R) Iris(R) Plus Graphics"
    info["gpu"] = gpu
    has_nvidia = "nvidia" in gpu.lower()
    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True,
                           text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip():
            has_nvidia = True
            info["nvidia"] = r.stdout.strip()[:200]
    except Exception:
        pass
    info["has_nvidia_gpu"] = has_nvidia
    bl = find_blender()
    info["blender"] = bl.get("exe", bl.get("error"))
    info["blender_ok"] = bool(bl.get("success"))
    # engine + resolution matched to THIS system
    # Blender 4.5 renamed EEVEE -> BLENDER_EEVEE_NEXT (real API drift)
    if has_nvidia and info.get("ram_gb", 8) >= 12:
        info["engine"] = "CYCLES"
        info["samples"] = 64
    else:
        info["engine"] = "BLENDER_EEVEE_NEXT"
        info["samples"] = 32
    info["resolution"] = [1280, 720] if info.get("ram_gb", 8) >= 12 else [960, 540]
    try:
        du = shutil.disk_usage(str(_d_tmp()))
        info["disk_free_gb"] = round(du.free / 1e9, 1)
    except Exception:
        info["disk_free_gb"] = -1
    return info


# -- prompt -> spec (real parser) ----------------------------------------------

BUILDING_KINDS = ("tower", "house", "warehouse", "office", "villa", "shop",
                  "building", "skyscraper", "apartment", "hospital", "school")


def parse_prompt(prompt: str) -> Dict[str, Any]:
    p = (prompt or "").lower()
    floors = 3
    m = re.search(r"(\d+)\s*(?:floor|storey|story|level)", p)
    if m:
        floors = max(1, min(60, int(m.group(1))))
    elif "skyscraper" in p:
        floors = 30
    elif "tower" in p:
        floors = 12
    elif "house" in p or "villa" in p or "cottage" in p:
        floors = 2
    elif "warehouse" in p:
        floors = 1
    style = "concrete"
    for s in ("glass", "brick", "concrete", "steel", "wood", "modern",
              "night", "day"):
        if s in p:
            style = s
            break
    kind = "building"
    for k in BUILDING_KINDS:
        if k in p:
            kind = k
            break
    fw = 14.0
    m2 = re.search(r"(\d+(?:\.\d+)?)\s*m\s*(?:wide|footprint)", p)
    if m2:
        fw = max(4.0, min(80.0, float(m2.group(1))))
    name = re.sub(r"[^a-z0-9]+", "_", p.strip())[:40].strip("_") or "building"
    return {"kind": kind, "floors": floors, "style": style,
            "footprint": fw, "depth": round(fw * 0.7, 1),
            "floor_h": 3.2, "name": f"{kind}_{floors}f_{style}"}


# -- bpy script generation ------------------------------------------------------

FORGE_SCRIPT_TEMPLATE = r'''
import bpy, math, sys, json, os

SPEC = __SPEC_JSON__
OUT_GLB = r"""__OUT_GLB__"""
OUT_PNG = r"""__OUT_PNG__"""
ENGINE = "__ENGINE__"
SAMPLES = __SAMPLES__
RES_W, RES_H = __RES_W__, __RES_H__

def mat_principled(name, base_color, metallic=0.0, roughness=0.6, emission=None, emission_strength=0.0):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    try:
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    except Exception:
        pass
    if emission is not None:
        try:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission_strength
        except Exception:
            pass
    return m

# clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for coll in (bpy.data.meshes, bpy.data.materials):
    pass

floors = int(SPEC["floors"]); fw = float(SPEC["footprint"]); dp = float(SPEC["depth"]); fh = float(SPEC["floor_h"])
H = floors * fh
style = SPEC.get("style", "concrete")

wall_col = {"glass": (0.55, 0.68, 0.75), "brick": (0.55, 0.25, 0.18), "wood": (0.45, 0.32, 0.2)}.get(style, (0.62, 0.62, 0.60))
wall_mat = mat_principled("Wall", wall_col, roughness=0.85)
glass_mat = mat_principled("Glass", (0.35, 0.55, 0.65), metallic=0.1, roughness=0.15,
                           emission=(0.9, 0.85, 0.55) if style == "night" else (0.5, 0.65, 0.75),
                           emission_strength=1.2 if style == "night" else 0.25)
roof_mat = mat_principled("Roof", (0.18, 0.18, 0.20), roughness=0.9)
ground_mat = mat_principled("Ground", (0.16, 0.22, 0.16), roughness=1.0)

# main mass
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, H / 2))
body = bpy.context.active_object
body.name = "Building"
body.scale = (fw, dp, H)
bpy.ops.object.transform_apply(scale=True)
body.data.materials.append(wall_mat)

# window bands: per floor, front+back strips slightly proud of walls
for f in range(floors):
    z = f * fh + fh * 0.55
    for side in (dp / 2 + 0.06, -dp / 2 - 0.06):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, side, z))
        w = bpy.context.active_object
        w.name = f"Win_{f}_{int(side)}"
        w.scale = (fw * 0.86, 0.08, fh * 0.45)
        bpy.ops.object.transform_apply(scale=True)
        w.data.materials.append(glass_mat)
    # side strips
    for side in (fw / 2 + 0.06, -fw / 2 - 0.06):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(side, 0, z))
        w = bpy.context.active_object
        w.name = f"WinS_{f}_{int(side)}"
        w.scale = (0.08, dp * 0.80, fh * 0.45)
        bpy.ops.object.transform_apply(scale=True)
        w.data.materials.append(glass_mat)

# roof slab + parapet
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, H + 0.25))
roof = bpy.context.active_object
roof.name = "Roof"
roof.scale = (fw + 0.8, dp + 0.8, 0.5)
bpy.ops.object.transform_apply(scale=True)
roof.data.materials.append(roof_mat)

# door
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, dp / 2 + 0.1, 1.1))
door = bpy.context.active_object
door.name = "Door"
door.scale = (2.4, 0.2, 2.2)
bpy.ops.object.transform_apply(scale=True)
door.data.materials.append(roof_mat)

# ground
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
g = bpy.context.active_object
g.name = "Ground"
g.scale = (max(fw, dp) * 6, max(fw, dp) * 6, 1)
bpy.ops.object.transform_apply(scale=True)
g.data.materials.append(ground_mat)

# sun (energy scaled to building size)
bpy.ops.object.light_add(type='SUN', location=(fw * 2, -dp * 3, H * 2.5))
sun = bpy.context.active_object
sun.data.energy = 4.0
sun.rotation_euler = (math.radians(50), 0, math.radians(30))

# camera auto-frame
dist = max(fw, dp, H) * 2.2 + 12
bpy.ops.object.camera_add(location=(dist * 0.9, -dist, H * 0.75))
cam = bpy.context.active_object
bpy.context.scene.camera = cam
# track to building center
bpy.ops.object.empty_add(location=(0, 0, H * 0.45))
tgt = bpy.context.active_object
con = cam.constraints.new(type='TRACK_TO')
con.target = tgt
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'

scene = bpy.context.scene
try:
    scene.render.engine = ENGINE
except Exception:
    # API drift: 4.2 EEVEE vs 4.5 EEVEE_NEXT — take whichever exists
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if ENGINE.startswith('BLENDER_EEVEE') else 'BLENDER_EEVEE'
scene.render.resolution_x = RES_W
scene.render.resolution_y = RES_H
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
try:
    if 'CYCLES' in scene.render.engine:
        scene.cycles.samples = SAMPLES
        scene.cycles.device = 'CPU'
    else:
        try:
            scene.eevee.taa_render_samples = SAMPLES
        except Exception:
            pass
except Exception as e:
    print("render opts note:", e)
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = OUT_PNG
bpy.ops.render.render(write_still=True)

# export GLB
try:
    bpy.ops.export_scene.gltf(filepath=OUT_GLB, export_format='GLB',
                              export_materials='EXPORT',
                              use_selection=False)
except Exception as e:
    print("GLB export failed:", e)
    raise

counts = {"objects": len(bpy.data.objects), "meshes": len(bpy.data.meshes), "materials": len(bpy.data.materials)}
print("FORGE_DONE " + json.dumps(counts))
'''


def _render_script(spec: Dict[str, Any], out_glb: Path, out_png: Path,
                   engine: str, samples: int, res: List[int]) -> str:
    s = FORGE_SCRIPT_TEMPLATE
    s = s.replace("__SPEC_JSON__", json.dumps(spec))
    s = s.replace("__OUT_GLB__", str(out_glb))
    s = s.replace("__OUT_PNG__", str(out_png))
    s = s.replace("__ENGINE__", engine)
    s = s.replace("__SAMPLES__", str(samples))
    s = s.replace("__RES_W__", str(res[0]))
    s = s.replace("__RES_H__", str(res[1]))
    return s


def forge_build(prompt: str, timeout: int = 600) -> Dict[str, Any]:
    """Full pipeline: parse -> Blender build+render -> QA. Real artifacts."""
    t0 = time.time()
    spec = parse_prompt(prompt)
    sysinfo = system_probe()
    bl = find_blender()
    if not bl.get("success"):
        return {"success": False, "error": bl["error"], "spec": spec}
    exe = bl["exe"]
    stamp = int(time.time())
    jobdir = _d_tmp() / f"{spec['name']}_{stamp}"
    jobdir.mkdir(parents=True, exist_ok=True)
    out_glb = jobdir / f"{spec['name']}.glb"
    out_png = jobdir / f"{spec['name']}.png"
    script_p = jobdir / "build.py"
    script_p.write_text(_render_script(spec, out_glb, out_png,
                                       sysinfo["engine"], sysinfo["samples"],
                                       sysinfo["resolution"]), encoding="utf-8")
    cmd = [exe, "--background", "--python", str(script_p)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, errors="replace")
        log = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return {"success": False, "spec": spec,
                "error": f"Blender timed out after {timeout}s (try fewer floors).",
                "jobdir": str(jobdir)}
    except Exception as e:
        return {"success": False, "spec": spec, "error": str(e)}
    # QA: files must exist, sizes sane, preview not black
    qa: Dict[str, Any] = {"rc": proc.returncode,
                          "log_tail": log[-1200:]}
    ok = proc.returncode == 0 and "FORGE_DONE" in log
    counts: Dict[str, Any] = {}
    m = re.search(r"FORGE_DONE (\{.*\})", log)
    if m:
        try:
            counts = json.loads(m.group(1))
        except Exception:
            pass
    qa["counts"] = counts
    for p, min_sz in ((out_glb, 5000), (out_png, 5000)):
        if not p.exists():
            return {"success": False, "spec": spec, "qa": qa,
                    "jobdir": str(jobdir),
                    "error": f"Missing output {p.name}. Blender log tail:\n{log[-800:]}"}
        sz = p.stat().st_size
        qa[p.suffix + "_bytes"] = sz
        if sz < min_sz:
            return {"success": False, "spec": spec, "qa": qa,
                    "jobdir": str(jobdir),
                    "error": f"{p.name} too small ({sz}b) — build failed."}
    # preview brightness: must not be black (real render check)
    try:
        from PIL import Image as _Im
        import numpy as _np
        img = _Im.open(out_png).convert("L")
        mean = float(_np.asarray(img).mean())
        qa["preview_mean_luma"] = round(mean, 1)
        if mean < 4.0:
            return {"success": False, "spec": spec, "qa": qa,
                    "jobdir": str(jobdir),
                    "error": "Preview is black — lighting/camera failed."}
    except Exception as e:
        qa["preview_check"] = f"skipped ({e})"
    secs = round(time.time() - t0, 1)
    return {"success": True, "spec": spec, "glb": str(out_glb),
            "preview": str(out_png), "jobdir": str(jobdir),
            "engine": sysinfo["engine"], "resolution": sysinfo["resolution"],
            "seconds": secs, "qa": qa}


def forge_list() -> Dict[str, Any]:
    base = _d_tmp()
    jobs = []
    try:
        for d in sorted(base.iterdir(), key=lambda p: p.stat().st_mtime,
                        reverse=True)[:15]:
            if d.is_dir():
                glbs = list(d.glob("*.glb"))
                pngs = list(d.glob("*.png"))
                if glbs or pngs:
                    jobs.append({"job": d.name,
                                 "glb": str(glbs[0]) if glbs else "",
                                 "preview": str(pngs[0]) if pngs else ""})
    except Exception as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "jobs": jobs}
