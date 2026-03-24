from pathlib import Path
import ast


FILES = [
    "api_gateway.py",
    "auth_validator.py",
    "command_policy.py",
    "telemetry_sync.py",
    "ros_safety_bridge.py",
    "core/secure_gateway_mount.py",
    "core/main.py",
    "scripts/set_firebase_role.py",
]

for source in FILES:
    code = Path(source).read_text(encoding="utf-8")
    ast.parse(code, filename=source)

print("syntax_ok")
