# ============================================================
#  routes/student.py — Student Routes
#
#  GET  /api/student/rooms      - Get my assigned rooms
#  GET  /api/student/history    - My past quiz attempts
#  GET  /api/student/profile    - My profile + stats
#  POST /api/student/issues     - Submit an issue report
# ============================================================

import json
from flask              import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions         import db
from models             import User, Room, Question, RoomAccess, QuizSession, RoomAttempt
import json
from pathlib import Path
from datetime import datetime

student_bp = Blueprint('student', __name__)

ISSUES_FILE = Path(__file__).parent.parent / 'issues.json'

def load_issues():
    if ISSUES_FILE.exists():
        try:
            return json.loads(ISSUES_FILE.read_text())
        except:
            return []
    return []

def save_issues(issues):
    ISSUES_FILE.write_text(json.dumps(issues, indent=2))


# ── GET MY ASSIGNED ROOMS ─────────────────────────────────────
@student_bp.route('/rooms', methods=['GET'])
@jwt_required()
def get_my_rooms():
    uid = get_jwt_identity()
    # Get assigned rooms
    access   = RoomAccess.query.filter_by(user_id=uid).all()
    room_ids = [a.room_id for a in access]
    
    # Get rooms that are either assigned OR public
    rooms = Room.query.filter(
        (Room.id.in_(room_ids)) | (Room.is_public == True),
        Room.is_active == True
    ).all()
    
    result = []
    for r in rooms:
        d = r.to_dict()
        d['question_count'] = Question.query.filter_by(room_id=r.id).count()
        result.append(d)
    return jsonify({'rooms': result}), 200


# ── MY QUIZ HISTORY ───────────────────────────────────────────
@student_bp.route('/history', methods=['GET'])
@jwt_required()
def get_history():
    uid = get_jwt_identity()
    sessions = QuizSession.query.filter_by(user_id=uid)\
                                .order_by(QuizSession.started_at.desc())\
                                .limit(10).all()
    return jsonify({'history': [s.to_dict() for s in sessions]}), 200


# ── MY PROFILE + STATS ────────────────────────────────────────
@student_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    uid           = get_jwt_identity()
    user          = User.query.get(uid)
    total_score   = db.session.query(db.func.sum(RoomAttempt.score))\
                              .filter_by(user_id=uid).scalar() or 0
    rooms_cleared = RoomAttempt.query.filter_by(
                        user_id=uid, status='completed').count()
    games_played  = QuizSession.query.filter_by(user_id=uid).count()

    return jsonify({
        'profile':      user.to_dict(),
        'stats': {
            'total_score':   total_score,
            'rooms_cleared': rooms_cleared,
            'games_played':  games_played
        }
    }), 200


# ── SUBMIT ISSUE REPORT ───────────────────────────────────────
@student_bp.route('/issues', methods=['POST'])
@jwt_required()
def submit_issue():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    data     = request.get_json()

    if not data or not data.get('title') or not data.get('description'):
        return jsonify({'error': 'Title and description are required'}), 400

    issues = load_issues()

    new_issue = {
        'id':          (max([i['id'] for i in issues], default=0) + 1),
        'player_name': user.name if user else 'Unknown',
        'player_id':   uid,
        'title':       data['title'].strip(),
        'description': data['description'].strip(),
        'category':    data.get('category', 'general'),
        'resolved':    False,
        'resolved_by': None,
        'created_at':  datetime.utcnow().isoformat()
    }

    issues.append(new_issue)
    save_issues(issues)

    return jsonify({'message': 'Issue submitted. The moderator will look into it.', 'issue': new_issue}), 201
