#!/usr/bin/env python3
import sys
import os
AEGIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AEGIS_DIR)
os.chdir(AEGIS_DIR)
os.environ.setdefault('AEGIS_MODE', 'production')
if __name__ == "__main__":
    import run_production
    run_production.main()
