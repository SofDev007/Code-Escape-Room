# ============================================================
#  config.py — Flask Configuration
# ============================================================
import os
from datetime import timedelta

class Config:
    # ── Security
    SECRET_KEY     = os.environ.get('SECRET_KEY',     'cer_super_secret_key_change_in_production')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'cer_jwt_secret_change_in_production')
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=8)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # ── Database
    # Defaulting to SQLite for easy portability.
    # In Render.com, you can set DATABASE_URL to 'sqlite:////data/app.db' for persistence.
    _db_url = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False

    # ── NVIDIA NIM API Key
    # Paste your nvapi- key below (keep the quotes)
    NVIDIA_API_KEY = os.environ.get('NVIDIA_API_KEY', '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')

    # ── App
    DEBUG = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    QUESTIONS_PER_ROOM = 4
