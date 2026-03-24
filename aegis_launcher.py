#!/usr/bin/env python3
"""
AEGIS Launcher - Entry point for aegis.exe
Starts all AEGIS components in standalone mode
"""
import sys
import os

# Add the AEGIS directory to path
AEGIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AEGIS_DIR)

# Change to AEGIS directory
os.chdir(AEGIS_DIR)

# Set environment for production
os.environ.setdefault('AEGIS_MODE', 'production')

if __name__ == "__main__":
    # Import and run production server
    import run_production
    run_production.main()
