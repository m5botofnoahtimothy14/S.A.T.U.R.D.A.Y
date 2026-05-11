#!/usr/bin/env python3
import sys
import os
SATURDAY_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SATURDAY_DIR)
os.chdir(SATURDAY_DIR)
os.environ.setdefault('SATURDAY_MODE', 'production')
if __name__ == "__main__":
    import run_production
    run_production.main()
