#!/usr/bin/env python3
from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv()
os.environ['AEGIS_ALLOW_MOCK_AUTH'] = 'true'
os.environ.setdefault("AEGIS_API_PORT", "8000")
os.environ.setdefault("AEGIS_DASHBOARD_ORIGINS", "http://localhost:5173,http://localhost:5174")
import api_gateway
def main() -> None:
    host = os.getenv("AEGIS_API_HOST", "127.0.0.1")
    port = int(os.getenv("AEGIS_API_PORT", "8000"))
    print(f"Starting AEGIS API Gateway on http://{host}:{port}")
    api_gateway.run()
if __name__ == "__main__":
    main()
