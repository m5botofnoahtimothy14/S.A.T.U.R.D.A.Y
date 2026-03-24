from __future__ import annotations

from fastapi.testclient import TestClient

from api_gateway import app


def main() -> None:
    with TestClient(app) as client:
        response = client.get("/healthz")
        print("health_status", response.status_code)
        print("health_payload", response.json())


if __name__ == "__main__":
    main()
