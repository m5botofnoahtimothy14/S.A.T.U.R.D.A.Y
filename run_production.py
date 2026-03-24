#!/usr/bin/env python3
"""
AEGIS Production Server
Run with: python run_production.py
"""
import os
import sys
import logging
import socket
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# Load production environment
from dotenv import load_dotenv
load_dotenv(BASE_DIR / "prod.env")

import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(BASE_DIR / "logs" / "aegis.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("AEGIS.Production")

def get_workers():
    """
    AEGIS uses hardware/audio/vision integrations and shared state.
    Multiple workers duplicate subsystems and frequently cause startup/runtime conflicts.
    """
    return 1


def is_port_available(host: str, port: int) -> bool:
    bind_host = host if host not in ("0.0.0.0", "::") else "127.0.0.1"
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        return sock.connect_ex((bind_host, port)) != 0
    finally:
        sock.close()

def run_server():
    """Run AEGIS with uvicorn production server"""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    requested_workers = int(os.getenv("WORKERS", get_workers()))
    workers = 1 if requested_workers != 1 else requested_workers

    if requested_workers != 1:
        logger.warning("Forcing WORKERS=1 for AEGIS runtime stability (requested=%s)", requested_workers)
    
    if not is_port_available(host, port):
        logger.error("Port %s is already in use. Stop the existing AEGIS/server process first.", port)
        return 1
    
    logger.info(f"Starting AEGIS Production Server on {host}:{port}")
    logger.info(f"Using {workers} workers")
    
    # Try to use uvloop if available, otherwise fall back to default loop
    try:
        import uvloop
        loop = "uvloop"
    except ImportError:
        loop = "auto"
        logger.info("uvloop not available, using default event loop")
    
    # Try to use httptools if available
    try:
        import httptools
        http = "httptools"
    except ImportError:
        http = "auto"
        logger.info("httptools not available, using default HTTP parser")
    
    uvicorn.run(
        "core.main:app",
        host=host,
        port=port,
        workers=workers,
        loop=loop,
        http=http,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    return 0

def run_standalone():
    """Run AEGIS in standalone mode (with uvicorn)"""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    if not is_port_available(host, port):
        logger.error("Port %s is already in use. Stop the existing AEGIS/server process first.", port)
        return 1

    logger.info("Starting AEGIS in standalone mode")
    
    # Try to use uvloop if available
    try:
        import uvloop
        loop = "uvloop"
    except ImportError:
        loop = "auto"
    
    uvicorn.run(
        "core.main:app",
        host=host,
        port=port,
        loop=loop,
        log_level="info",
    )
    return 0

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AEGIS Production Server")
    parser.add_argument("--mode", choices=["server", "standalone"], default="server",
                        help="Run mode: server (multi-worker) or standalone")
    parser.add_argument("--dev", action="store_true",
                        help="Development mode (reload enabled)")
    args = parser.parse_args()
    
    # Ensure data directories exist
    (BASE_DIR / "data").mkdir(exist_ok=True)
    (BASE_DIR / "logs").mkdir(exist_ok=True)
    
    if args.dev:
        # Development mode with auto-reload
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8000"))
        if not is_port_available(host, port):
            logger.error("Port %s is already in use. Stop the existing AEGIS/server process first.", port)
            return 1

        logger.info("Starting AEGIS in development mode")
        try:
            import uvloop
            loop = "uvloop"
        except ImportError:
            loop = "auto"
        uvicorn.run(
            "core.main:app",
            host=host,
            port=port,
            reload=True,
            loop=loop,
            log_level="debug",
        )
        return 0
    elif args.mode == "standalone":
        return run_standalone()
    else:
        return run_server()

if __name__ == "__main__":
    sys.exit(main())
