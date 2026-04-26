# ============================================================
#  wsgi.py — PythonAnywhere WSGI Entry Point
#  PythonAnywhere will import `application` from this file.
# ============================================================
import os
import sys
from dotenv import load_dotenv

# ── 1. Locate project directory ─────────────────────────────
# IMPORTANT: change this path to match YOUR PythonAnywhere folder.
# Example: /home/SofDev007/Code-Escape-Room
PROJECT_DIR = '/home/SofDev007/Code-Escape-Room'

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# ── 2. Load environment variables from .env file ────────────
load_dotenv(os.path.join(PROJECT_DIR, '.env'))

# ── 3. Create Flask app ─────────────────────────────────────
from app import create_app
application = create_app()
