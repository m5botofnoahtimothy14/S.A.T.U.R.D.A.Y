import os
from typing import Any


def _env_true(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default).strip().lower()
    return value in {"1", "true", "yes", "on"}


def try_mount_secure_gateway(main_app: Any, logger: Any) -> dict[str, Any]:
    enabled = _env_true("AEGIS_ENABLE_SECURE_GATEWAY_MOUNT", "false")
    mount_path = os.getenv("AEGIS_SECURE_GATEWAY_MOUNT_PATH", "/api/secure").strip() or "/api/secure"

    status = {
        "enabled": enabled,
        "mounted": False,
        "path": mount_path,
        "error": None,
    }

    if not enabled:
        return status

    try:
        from api_gateway import app as secure_gateway_app

        main_app.mount(mount_path, secure_gateway_app)
        status["mounted"] = True
        logger.info("Secure gateway mounted", path=mount_path)
    except Exception as exc:
        status["error"] = str(exc)
        logger.warning("Secure gateway mount failed", error=str(exc), path=mount_path)

    return status
