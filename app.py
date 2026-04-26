"""
app.py — Flask application entry point
Loads .env automatically when imported (needed for local dev & WSGI).
"""
import os
import sys

# Load environment variables from .env (does nothing if .env is absent)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Ensure current directory is in path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from flask      import Flask, send_from_directory
from flask_cors import CORS
from config     import Config
from extensions import db, bcrypt, jwt

from api_routes.auth        import auth_bp
from api_routes.admin       import admin_bp
from api_routes.student     import student_bp
from api_routes.quiz        import quiz_bp
from api_routes.leaderboard import leaderboard_bp
from api_routes.ai          import ai_bp          # NVIDIA NIM AI


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    app.register_blueprint(auth_bp,        url_prefix='/api/auth')
    app.register_blueprint(admin_bp,       url_prefix='/api/admin')
    app.register_blueprint(student_bp,     url_prefix='/api/student')
    app.register_blueprint(quiz_bp,        url_prefix='/api/quiz')
    app.register_blueprint(leaderboard_bp, url_prefix='/api/leaderboard')
    app.register_blueprint(ai_bp,          url_prefix='/api/ai')

    @app.route('/')
    def index():
        return send_from_directory(BASE_DIR, 'login.html')

    @app.route('/<path:filename>')
    def serve_file(filename):
        return send_from_directory(BASE_DIR, filename)

    @app.route('/health')
    def health():
        return {'status': 'ok', 'message': 'Code Escape Room API is running'}, 200

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
