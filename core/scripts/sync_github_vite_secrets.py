import argparse
import shutil
import subprocess
from pathlib import Path


REQUIRED_KEYS = [
    "VITE_FIREBASE_API_KEY",
    "VITE_FIREBASE_AUTH_DOMAIN",
    "VITE_FIREBASE_PROJECT_ID",
    "VITE_FIREBASE_STORAGE_BUCKET",
    "VITE_FIREBASE_MESSAGING_SENDER_ID",
    "VITE_FIREBASE_APP_ID",
    "VITE_AEGIS_GATEWAY_URL",
]


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync VITE_* values from local env file to GitHub Actions secrets.")
    parser.add_argument("--env-file", default="aegis-control-panel/.env")
    parser.add_argument("--repo", default="", help="Optional owner/repo. If omitted, gh current repo is used.")
    args = parser.parse_args()

    gh_path = shutil.which("gh")
    if not gh_path:
        fallback_paths = [
            r"D:\GitHub CLI\gh.exe",
            r"C:\Program Files\GitHub CLI\gh.exe",
            r"C:\Program Files (x86)\GitHub CLI\gh.exe",
        ]
        for path in fallback_paths:
            if Path(path).exists():
                gh_path = path
                break
    if not gh_path:
        raise SystemExit("gh CLI is not installed or not in PATH.")

    env_path = Path(args.env_file)
    if not env_path.exists():
        raise SystemExit(f"Env file not found: {env_path}")

    env_values = read_env(env_path)
    missing = [key for key in REQUIRED_KEYS if not env_values.get(key)]
    if missing:
        raise SystemExit(f"Missing values in {env_path}: {', '.join(missing)}")

    repo_args: list[str] = []
    if args.repo:
        repo_args = ["--repo", args.repo]

    for key in REQUIRED_KEYS:
        value = env_values[key]
        cmd = [gh_path, "secret", "set", key, *repo_args, "-b", value]
        subprocess.run(cmd, check=True)
        print(f"Updated GitHub secret: {key}")


if __name__ == "__main__":
    main()
