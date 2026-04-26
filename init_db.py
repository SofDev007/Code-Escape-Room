"""
init_db.py — Initialize (or reset) the database
--------------------------------------------------
• Drops all tables, recreates them fresh
• Seeds a default admin account (admin@escaperoom.com / admin123)
• Loads DATABASE_URL + keys from .env automatically

⚠️  WARNING: Running this WIPES all existing data.
   Only run on first deploy or when you want to reset everything.
"""
import os
from dotenv import load_dotenv

# Load .env before importing app/config so DATABASE_URL is picked up
load_dotenv()

from app        import create_app
from extensions import db, bcrypt
from models     import User

app = create_app()
with app.app_context():
    print(f"→ Using database: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[-1]}")

    # Drop all tables
    db.drop_all()
    print('✓ Tables dropped')

    # Recreate tables
    db.create_all()
    print('✓ Tables created (7 total)')

    # Create admin with bcrypt-hashed password
    password_hash = bcrypt.generate_password_hash('admin123').decode('utf-8')
    admin = User(
        name          = 'Admin',
        username      = 'admin',
        email         = 'admin@escaperoom.com',
        password_hash = password_hash,
        role          = 'admin',
        batch         = 'FACULTY',
        is_active     = True,
        is_banned     = False,
    )
    db.session.add(admin)
    db.session.commit()

    print('✓ Admin account created')
    print('  ─────────────────────────────')
    print('  Username : admin')
    print('  Email    : admin@escaperoom.com')
    print('  Password : admin123')
    print('  ─────────────────────────────')
    print('\n🎯 Database ready. You can now log in and start adding rooms/questions.')
