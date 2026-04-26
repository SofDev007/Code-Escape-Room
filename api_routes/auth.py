# ============================================================
#  routes/auth.py — Authentication Routes
#  POST /api/auth/login      (username + password)
#  POST /api/auth/signup     (public player self-registration)
#  POST /api/auth/register   (Admin only creates student accounts)
#  GET  /api/auth/me         (Get current logged in user)
#  POST /api/auth/change-password
#  POST /api/auth/setup      (create first admin)
# ============================================================

import json
from flask              import Blueprint, request, jsonify
from flask_jwt_extended import (create_access_token, create_refresh_token,
                                jwt_required, get_jwt_identity)
from extensions         import db, bcrypt
from models             import User
import re

auth_bp = Blueprint('auth', __name__)


# ── LOGIN (accepts username OR email) ───────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400

    identifier = data['username'].strip().lower()

    # Try by username first, then by email
    user = (
        User.query.filter(db.func.lower(User.username) == identifier).first()
        or User.query.filter(db.func.lower(User.email) == identifier).first()
    )

    if not user:
        return jsonify({'error': 'Invalid username or password'}), 401

    if user.is_banned:
        return jsonify({'error': f'Account banned. Reason: {user.ban_reason or "Contact admin."}'}), 403

    if not user.is_active:
        return jsonify({'error': 'Account is deactivated. Contact admin.'}), 403

    if not bcrypt.check_password_hash(user.password_hash, data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401

    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        'message':       'Login successful',
        'access_token':  access_token,
        'refresh_token': refresh_token,
        'user':          user.to_dict()
    }), 200


# ── PUBLIC PLAYER SIGNUP ─────────────────────────────────────
@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()

    # Validate required fields
    required = ['first_name', 'last_name', 'email', 'username', 'password']
    for field in required:
        if not data.get(field, '').strip():
            return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400

    first_name = data['first_name'].strip()
    last_name  = data['last_name'].strip()
    email      = data['email'].strip().lower()
    username   = data['username'].strip().lower()
    password   = data['password']

    # Validate email format
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return jsonify({'error': 'Invalid email address'}), 400

    # Validate username (alphanumeric + underscore only)
    if not re.match(r'^[a-zA-Z0-9_]{3,30}$', data['username'].strip()):
        return jsonify({'error': 'Username must be 3-30 characters, letters/numbers/underscore only'}), 400

    # Validate password length
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    # Check uniqueness
    if User.query.filter(db.func.lower(User.email) == email).first():
        return jsonify({'error': 'Email is already registered'}), 409

    if User.query.filter(db.func.lower(User.username) == username).first():
        return jsonify({'error': 'Username is already taken'}), 409

    hashed = bcrypt.generate_password_hash(password).decode('utf-8')

    new_user = User(
        first_name    = first_name,
        last_name     = last_name,
        name          = f'{first_name} {last_name}',
        username      = username,
        email         = email,
        password_hash = hashed,
        role          = 'student',
        is_active     = True,
        is_banned     = False
    )

    db.session.add(new_user)
    db.session.commit()

    access_token  = create_access_token(identity=str(new_user.id))
    refresh_token = create_refresh_token(identity=str(new_user.id))

    return jsonify({
        'message':       f'Welcome, {new_user.name}! Account created.',
        'access_token':  access_token,
        'refresh_token': refresh_token,
        'user':          new_user.to_dict()
    }), 201


# ── REGISTER (Admin creates student accounts) ────────────────
@auth_bp.route('/register', methods=['POST'])
@jwt_required()
def register():
    uid = get_jwt_identity()
    current_user = User.query.get(uid)
    if not current_user or current_user.role != 'admin':
        return jsonify({'error': 'Only admins can create accounts'}), 403

    data = request.get_json()

    required = ['name', 'email', 'password']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    if User.query.filter_by(email=data['email'].lower().strip()).first():
        return jsonify({'error': 'Email already registered'}), 409

    # Build username from name if not provided
    base_username = (data.get('username') or data['name'].split()[0]).lower()
    base_username = re.sub(r'[^a-z0-9_]', '', base_username)
    username = base_username
    counter  = 1
    while User.query.filter(db.func.lower(User.username) == username).first():
        username = f'{base_username}{counter}'
        counter += 1

    hashed = bcrypt.generate_password_hash(data['password']).decode('utf-8')

    new_user = User(
        name          = data['name'].strip(),
        username      = username,
        email         = data['email'].lower().strip(),
        password_hash = hashed,
        role          = data.get('role', 'student'),
        batch         = data.get('batch', ''),
        roll_number   = data.get('roll_number', ''),
        is_active     = True,
        is_banned     = False
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        'message': f'Account created for {new_user.name}',
        'user':    new_user.to_dict()
    }), 201


# ── GET CURRENT USER ─────────────────────────────────────────
@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_me():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify({'user': user.to_dict()}), 200


# ── CHANGE PASSWORD ──────────────────────────────────────────
@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    uid  = get_jwt_identity()
    user = User.query.get(uid)
    data = request.get_json()

    if not bcrypt.check_password_hash(user.password_hash, data.get('old_password', '')):
        return jsonify({'error': 'Current password is incorrect'}), 400

    if len(data.get('new_password', '')) < 6:
        return jsonify({'error': 'New password must be at least 6 characters'}), 400

    user.password_hash = bcrypt.generate_password_hash(data['new_password']).decode('utf-8')
    db.session.commit()

    return jsonify({'message': 'Password changed successfully'}), 200


# ── SETUP — Create first admin ───────────────────────────────
@auth_bp.route('/setup', methods=['POST'])
def setup():
    if User.query.filter_by(role='admin').first():
        return jsonify({'error': 'Setup already completed'}), 403

    data   = request.get_json()
    hashed = bcrypt.generate_password_hash(data.get('password', 'admin123')).decode('utf-8')

    admin = User(
        name          = data.get('name', 'Admin'),
        username      = data.get('username', 'admin'),
        email         = data.get('email', 'admin@escaperoom.com'),
        password_hash = hashed,
        role          = 'admin',
        batch         = 'FACULTY',
        is_active     = True,
        is_banned     = False
    )
    db.session.add(admin)
    db.session.commit()

    return jsonify({'message': 'Admin account created. Please login.'}), 201
