#!/usr/bin/env python3
"""
SATURDAY Cross-Platform Setup & Model Downloader
==================================================
Runs on Windows, Linux, macOS and Android (Termux).

Two jobs:
  1) `setup`  - create a virtual environment (when supported) and install the
                Python dependencies SATURDAY needs to run.
  2) `download`- fetch the AI models SATURDAY uses for voice (STT+TTS), image
                vision and agentic (LLM) support. Downloads are resumable,
                verified against an expected size, and skipped when already
                present so it is safe to re-run.

Works offline: with `--offline` no network call is made; existing models are
reported and missing ones listed.

Standard library only (no third-party imports needed to run this script).

Examples
--------
    python saturday_downloader.py setup
    python saturday_downloader.py download --category agentic
    python saturday_downloader.py download --category all
    python saturday_downloader.py models          # list what is present / missing
    python saturday_downloader.py status          # environment + model status
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
MODELS_DIR = Path(os.getenv("SATURDAY_MODELS_DIR", str(ROOT / "models")))

# --------------------------------------------------------------------------- #
#  Model registry
# --------------------------------------------------------------------------- #

def _hf(split_url: str) -> str:
    """Build a huggingface.co resolve URL from a `repo/path` fragment."""
    repo, _, filename = split_url.partition("/")
    return f"https://huggingface.co/{repo}/resolve/main/{filename}"


MODELS: dict[str, list[dict]] = {
    "agentic": [
        {
            "name": "Qwen2.5-0.5B-Instruct (GGUF Q4_K_M)",
            "file": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
            "url": _hf("Qwen/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_k_m.gguf"),
            "size": 397 * 1024 * 1024,  # ~397 MB
            "desc": "Small local LLM for agentic reasoning. Runs on most devices incl. low-RAM/Android.",
        },
        {
            "name": "Phi-3-mini-4k-instruct (GGUF Q4_K_M)",
            "file": "phi-3-mini-4k-instruct-q4_k_m.gguf",
            "url": _hf("microsoft/Phi-3-mini-4k-instruct-gguf/Phi-3-mini-4k-instruct-q4_k_m.gguf"),
            "size": 2351 * 1024 * 1024,  # ~2.3 GB
            "desc": "Higher quality local LLM. Needs ~2.5 GB RAM.",
        },
        {
            "name": "Qwen3-0.6B (GGUF Q4_K_M) — compact backup",
            "file": "qwen3-0.6b-q4_k_m.gguf",
            "url": _hf("bartowski/Qwen_Qwen3-0.6B-GGUF/Qwen3-0.6B-Q4_K_M.gguf"),
            "size": 484 * 1024 * 1024,  # ~484 MB
            "desc": "Compact (0.6B) backup LLM. Full llama-cpp support including thinking-mode toggle.",
        },
        {
            "name": "Falcon-H1-Tiny-R-90M (GGUF Q4_K_M) — emergency tiny",
            "file": "falcon-h1-tiny-r-90m-q4_k_m.gguf",
            "url": _hf("tiiuae/Falcon-H1-Tiny-R-90M-GGUF/Falcon-H1-Tiny-R-90M-GGUF-Q4_K_M.gguf"),
            "size": 68 * 1024 * 1024,  # ~68 MB
            "desc": "Extremely small 90M emergency brain. Runs anywhere; lower quality but always available.",
        },
    ],
    "voice-stt": [
        {
            "name": "Faster-Whisper tiny (STT)",
            "file": "faster-whisper-tiny",
            "url": None,
            "size": 75 * 1024 * 1024,
            "desc": "Offline speech-to-text. Downloaded through faster-whisper.",
        },
        {
            "name": "Faster-Whisper small (STT)",
            "file": "faster-whisper-small",
            "url": None,
            "size": 464 * 1024 * 1024,
            "desc": "Balanced offline speech-to-text accuracy.",
        },
    ],
    "voice-tts": [
        {
            "name": "Piper en_US-lessac-medium (TTS)",
            "file": "piper/en_US-lessac-medium.onnx",
            "url": _hf("rhasspy/piper-voices/en/en_US/lessac/medium/en_US-lessac-medium.onnx"),
            "size": 63 * 1024 * 1024,
            "desc": "Offline text-to-speech voice (medium quality).",
            "extra": [
                {
                    "name": "Piper en_US-lessac-medium config",
                    "file": "piper/en_US-lessac-medium.onnx.json",
                    "url": _hf("rhasspy/piper-voices/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"),
                    "size": 5 * 1024,
                }
            ],
        },
    ],
    "vision": [
        {
            "name": "MediaPipe Face Landmarker",
            "file": "face_landmarker.task",
            "url": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
            "size": 3.6 * 1024 * 1024,
            "desc": "Face detection / landmarks for vision features.",
        },
    ],
}

CATEGORY_DEPENDENCIES: dict[str, list[str]] = {
    "agentic": ["llama-cpp-python"],
    "voice-stt": ["faster-whisper"],
    "voice-tts": ["piper-tts"],
    "vision": ["mediapipe", "opencv-python-headless"],
}

BASE_DEPENDENCIES: list[str] = [
    "fastapi",
    "uvicorn",
    "pydantic>=2.0",
    "structlog",
    "python-dotenv",
    "numpy",
    "psutil",
    "requests",
    "aiohttp",
    "jinja2",
    "paho-mqtt",
    "Pillow",
]


# --------------------------------------------------------------------------- #
#  Platform helpers
# --------------------------------------------------------------------------- #

def detect_platform() -> str:
    if os.getenv("ANDROID_ROOT") or os.getenv("TERMUX_VERSION") or os.path.exists("/data/data/com.termux"):
        return "android"
    system = platform.system().lower()
    if system.startswith("win"):
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def python_cmd() -> str:
    if detect_platform() == "android":
        return sys.executable
    return "python"


def pip_install(packages: list[str], target: str | None = None) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q"]
    if target:
        cmd += ["--target", target]
    cmd += packages
    try:
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


# --------------------------------------------------------------------------- #
#  Setup
# --------------------------------------------------------------------------- #

def setup(include_models: bool = False, categories: list[str] | None = None) -> int:
    pf = detect_platform()
    print(f"┌───────────────────────────────────────────────────────────┐")
    print(f"│  SATURDAY Setup  (platform: {pf.upper()})                  │")
    print(f"└───────────────────────────────────────────────────────────┘")
    print()

    if not categories:
        categories = ["all"]
    wants_all = "all" in categories

    if pf == "android":
        print("[setup] Android/Termux detected - using system Python (no venv).")
        venv_python = sys.executable
    else:
        venv_python = create_venv()
        if venv_python is None:
            print("[setup] No virtual environment created; using system Python.")
            venv_python = sys.executable

    print("\n[setup] Installing base dependencies...")
    if not pip_install(BASE_DEPENDENCIES):
        print("  [warn] Base dependency install reported an error; continuing.")

    extra: list[str] = []
    if wants_all:
        for deps in CATEGORY_DEPENDENCIES.values():
            extra.extend(deps)
    else:
        for cat in categories:
            extra.extend(CATEGORY_DEPENDENCIES.get(cat, []))
    extra = list(dict.fromkeys(extra))

    if extra:
        print(f"\n[setup] Installing category dependencies: {', '.join(extra)}")
        if not pip_install(extra):
            print("  [warn] Some category dependencies failed. Re-run with --category to retry.")

    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "data").mkdir(exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("\n[setup] Creating default prod.env if missing...")
    ensure_prod_env()

    if include_models or wants_all:
        print()
        download(categories=["all"] if wants_all else categories, offline=False)

    print("\n✔ Setup complete. Run:  python saturday_downloader.py status")
    print("  Start the agent:       python saturday_agent_cli.py")
    print("  Start the web server:  python run_production.py")
    return 0


def create_venv() -> str | None:
    if VENV_DIR.exists() and (VENV_DIR / "pyvenv.cfg").exists():
        print("[setup] Virtual environment already exists.")
    else:
        print("[setup] Creating virtual environment...")
        if shutil.which("python3"):
            base = "python3"
        elif shutil.which("python"):
            base = "python"
        else:
            return None
        if subprocess.run([base, "-m", "venv", str(VENV_DIR)]).returncode != 0:
            return None
    py = VENV_DIR / ("Scripts/python.exe" if detect_platform() == "windows" else "bin/python")
    return str(py) if py.exists() else str(VENV_DIR / "bin/python")


def ensure_prod_env() -> None:
    prod_env = ROOT / "prod.env"
    if prod_env.exists():
        return
    prod_env.write_text(
        "HOST=0.0.0.0\n"
        "PORT=8000\n"
        "WORKERS=1\n"
        "LOG_LEVEL=info\n"
        "SECRET_KEY=change-me-to-a-random-string\n"
        "ALLOWED_HOSTS=*\n"
        "SATURDAY_STRICT_PROD=false\n"
        "SATURDAY_DISABLE_AUTH=true\n"
        "SATURDAY_CORE_ORIGINS=http://localhost:5173,http://localhost:8000\n",
        encoding="utf-8",
    )
    print("  Created prod.env with defaults. Edit SECRET_KEY before production.")


# --------------------------------------------------------------------------- #
#  Downloads
# --------------------------------------------------------------------------- #

def _human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} TB"


def download_file(url: str, dest: Path, expected_size: int | None = None) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        if expected_size is None or dest.stat().st_size >= expected_size * 0.98:
            print(f"  [skip] {dest.name} already present.")
            return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"  Downloading {url}")

    resume = tmp.stat().st_size if tmp.exists() else 0
    headers = {"User-Agent": "SATURDAY-downloader/1.0"}
    if resume:
        headers["Range"] = f"bytes={resume}-"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "ab") as out:
            total = int(resp.headers.get("Content-Length", 0)) + resume
            mode = "ab" if resume else "wb"
            done = resume
            with open(tmp, mode) as handle:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    handle.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = done * 100.0 / total
                        sys.stdout.write(f"\r    {pct:5.1f}%  {_human_size(done)} / {_human_size(total)}")
                        sys.stdout.flush()
        sys.stdout.write("\n")
        tmp.replace(dest)
        return True
    except Exception as e:
        print(f"  [error] Download failed: {e}")
        return False


def _extract_whisper(dest: Path, model_size: str) -> bool:
    """Bootstrap a Faster-Whisper model so it works fully offline later."""
    try:
        from faster_whisper import WhisperModel
        from huggingface_hub import snapshot_download
        cache_dir = MODELS_DIR / "whisper" / model_size
        snapshot_download(repo_id=f"Systran/faster-whisper-{model_size}", cache_dir=cache_dir)
        print(f"  Whisper '{model_size}' cached under {cache_dir}")
        return True
    except Exception as e:
        print(f"  [error] Whisper download failed: {e}")
        return False


def download(categories: list[str] | None = None, offline: bool = False) -> int:
    if not categories:
        categories = ["all"]
    wants_all = "all" in categories

    print("┌───────────────────────────────────────────────────────────┐")
    print("│  SATURDAY Model Downloader                                │")
    print("└───────────────────────────────────────────────────────────┘")
    print(f"  Platform : {detect_platform().upper()}")
    print(f"  Models   : {MODELS_DIR}")
    print(f"  Offline  : {offline}")
    print()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    selected: list[str] = list(MODELS.keys()) if wants_all else [c for c in categories if c in MODELS]
    if not selected:
        print("No valid categories selected.")
        print("Available: all, " + ", ".join(MODELS.keys()))
        return 1

    failures = 0
    for cat in selected:
        print(f"\n[{cat}]")
        for entry in MODELS[cat]:
            rel = Path(entry["file"])
            dest = MODELS_DIR / rel
            if entry.get("url") is None:
                # Model is fetched through its package (faster-whisper).
                if offline:
                    present = any(MODELS_DIR.glob(f"whisper/**/*model.bin")) or dest.exists()
                    print(f"  {'[present]' if present else '[missing]'} {entry['name']} (downloaded via faster-whisper)")
                    if not present:
                        failures += 1
                    continue
                ok = _extract_whisper(MODELS_DIR, rel.name.replace("faster-whisper-", ""))
                if not ok:
                    failures += 1
                continue
            if offline:
                present = dest.exists() and dest.stat().st_size > 0
                print(f"  {'[present]' if present else '[missing]'} {entry['name']}")
                if not present:
                    failures += 1
                continue
            ok = download_file(entry["url"], dest, entry.get("size"))
            if not ok:
                failures += 1
            for extra in entry.get("extra", []):
                extra_dest = MODELS_DIR / Path(extra["file"])
                if offline:
                    present = extra_dest.exists() and extra_dest.stat().st_size > 0
                    print(f"  {'[present]' if present else '[missing]'} {extra['name']}")
                    if not present:
                        failures += 1
                    continue
                if not download_file(extra["url"], extra_dest, extra.get("size")):
                    failures += 1

    print()
    if failures:
        print(f"✖ Finished with {failures} missing/failed item(s). Re-run to retry.")
        return 1
    print("✔ All requested models are present.")
    return 0


def human_size(num: float) -> str:
    return _human_size(num)


def categories_summary() -> dict:
    """Return a JSON-friendly summary of available model categories."""
    return {
        "models_dir": str(MODELS_DIR),
        "platform": detect_platform(),
        "categories": {
            cat: [
                {
                    "name": entry["name"],
                    "file": entry["file"],
                    "url": entry.get("url"),
                    "size": entry.get("size"),
                    "desc": entry.get("desc", ""),
                    "present": (MODELS_DIR / Path(entry["file"])).exists()
                    and (MODELS_DIR / Path(entry["file"])).stat().st_size > 0
                    or (entry.get("url") is None and any(MODELS_DIR.glob("whisper/**/*model.bin"))),
                }
                for entry in entries
            ]
            for cat, entries in MODELS.items()
        },
    }


def models_status() -> int:
    print("SATURDAY models")
    print("===============")
    missing = 0
    for cat, entries in MODELS.items():
        print(f"\n[{cat}]")
        for entry in entries:
            dest = MODELS_DIR / Path(entry["file"])
            present = dest.exists() and dest.stat().st_size > 0
            if entry.get("url") is None:
                present = present or any(MODELS_DIR.glob("whisper/**/*model.bin"))
            tag = "[present]" if present else "[missing]"
            size = f"  {_human_size(dest.stat().st_size)}" if present else ""
            print(f"  {tag} {entry['name']}{size}")
            if not present:
                missing += 1
            for extra in entry.get("extra", []):
                extra_dest = MODELS_DIR / Path(extra["file"])
                present = extra_dest.exists() and extra_dest.stat().st_size > 0
                tag = "[present]" if present else "[missing]"
                print(f"  {tag} {extra['name']}")
                if not present:
                    missing += 1
    print(f"\nTotal missing: {missing}. Run `python saturday_downloader.py download` to fetch them.")
    return 0 if missing == 0 else 1


def env_status() -> None:
    print("SATURDAY environment")
    print("====================")
    print(f"  Python     : {sys.version.split()[0]}")
    print(f"  Platform   : {detect_platform().upper()}")
    print(f"  ROOT       : {ROOT}")
    print(f"  Models dir : {MODELS_DIR}")

    checks = ["numpy", "psutil", "fastapi", "uvicorn", "structlog"]
    for mod in checks:
        try:
            __import__(mod)
            print(f"  [present] {mod}")
        except ImportError:
            print(f"  [missing] {mod}")
    for mod in ["llama_cpp", "faster_whisper", "piper", "mediapipe"]:
        try:
            __import__(mod)
            print(f"  [present] {mod} (optional)")
        except ImportError:
            print(f"  [missing] {mod} (optional)")


def status() -> int:
    env_status()
    print()
    models_status()
    return 0


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(description="SATURDAY setup & model downloader")
    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser("setup", help="Install dependencies and prepare environment")
    p_setup.add_argument("--models", action="store_true", help="Also download models after setup")
    p_setup.add_argument("--category", action="append", help="Dependency categories (default: all)")

    p_dl = sub.add_parser("download", help="Download AI models")
    p_dl.add_argument("--category", action="append", help="Model categories: all, agentic, voice-stt, voice-tts, vision")
    p_dl.add_argument("--offline", action="store_true", help="Do not touch the network; only report status")

    sub.add_parser("models", help="List model status")
    sub.add_parser("status", help="Show environment and model status")

    args = parser.parse_args()

    if args.command == "setup":
        return setup(include_models=args.models, categories=args.category)
    if args.command == "download":
        return download(categories=args.category, offline=args.offline)
    if args.command == "models":
        return models_status()
    if args.command == "status":
        return status()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
