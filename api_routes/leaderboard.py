# ============================================================
#  routes/leaderboard.py — Class Leaderboard Routes
#
#  GET /api/leaderboard/room/<id>       - Leaderboard for one room
#  GET /api/leaderboard/overall         - Overall top scores
#  GET /api/leaderboard/batch/<batch>   - Leaderboard for a batch
# ============================================================

import json
from flask              import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions         import db
from models             import User, Room, RoomAttempt, QuizSession, RoomAccess

leaderboard_bp = Blueprint('leaderboard', __name__)


# ── LEADERBOARD FOR ONE ROOM ─────────────────────────────────
@leaderboard_bp.route('/room/<int:room_id>', methods=['GET'])
@jwt_required()
def room_leaderboard(room_id):
    uid  = get_jwt_identity()
    user = User.query.get(uid)
    room = Room.query.get_or_404(room_id)

    # Base query
    query = db.session.query(
        User.name,
        User.batch,
        User.roll_number,
        db.func.max(RoomAttempt.score).label('best_score'),
        db.func.min(RoomAttempt.time_taken).label('best_time'),
        db.func.max(RoomAttempt.correct_count).label('correct')
    ).join(RoomAttempt, User.id == RoomAttempt.user_id)\
     .filter(RoomAttempt.room_id == room_id,
             RoomAttempt.status  == 'completed')

    # Remove batch restriction for global visibility
    # if user and user.role == 'student' and user.batch:
    #     query = query.filter(User.batch == user.batch)

    results = query.group_by(User.id)\
                   .order_by(db.desc('best_score'), 'best_time')\
                   .all()

    leaderboard = []
    for rank, r in enumerate(results, 1):
        leaderboard.append({
            'rank':        rank,
            'name':        r.name,
            'batch':       r.batch,
            'roll_number': r.roll_number,
            'score':       r.best_score or 0,
            'time':        r.best_time,
            'correct':     r.correct,
            'is_me':       (r.name == user.name)  # Highlight current student
        })

    return jsonify({
        'room_name':   room.name,
        'language':    room.language,
        'leaderboard': leaderboard,
        'my_batch':    user.batch
    }), 200


# ── OVERALL LEADERBOARD (all rooms combined) ─────────────────
@leaderboard_bp.route('/overall', methods=['GET'])
@jwt_required()
def overall_leaderboard():
    uid  = get_jwt_identity()
    user = User.query.get(uid)

    query = db.session.query(
        User.name,
        User.batch,
        User.roll_number,
        db.func.sum(RoomAttempt.score).label('total_score'),
        db.func.sum(RoomAttempt.time_taken).label('total_time'),
        db.func.count(RoomAttempt.id).label('rooms_completed')
    ).join(RoomAttempt, User.id == RoomAttempt.user_id)\
     .filter(RoomAttempt.status == 'completed')

    # Remove batch restriction for global visibility
    # if user and user.role == 'student' and user.batch:
    #     query = query.filter(User.batch == user.batch)

    results = query.group_by(User.id)\
                   .order_by(db.desc('total_score'), 'total_time')\
                   .all()

    leaderboard = []
    for rank, r in enumerate(results, 1):
        leaderboard.append({
            'rank':            rank,
            'name':            r.name,
            'batch':           r.batch,
            'roll_number':     r.roll_number,
            'total_score':     r.total_score or 0,
            'total_time':      r.total_time or 0,
            'rooms_completed': r.rooms_completed,
            'is_me':           (r.name == user.name)
        })

    return jsonify({'leaderboard': leaderboard}), 200


# ── BATCH-SPECIFIC LEADERBOARD ────────────────────────────────
@leaderboard_bp.route('/batch/<string:batch>', methods=['GET'])
@jwt_required()
def batch_leaderboard(batch):
    uid = get_jwt_identity()
    user = User.query.get(uid) # Though not strictly needed for this specific route logic right now

    results = db.session.query(
        User.name,
        User.batch,
        User.roll_number,
        db.func.sum(RoomAttempt.score).label('total_score'),
        db.func.count(RoomAttempt.id).label('rooms_completed')
    ).join(RoomAttempt, User.id == RoomAttempt.user_id)\
     .filter(User.batch == batch, RoomAttempt.status == 'completed')\
     .group_by(User.id)\
     .order_by(db.desc('total_score'))\
     .all()

    leaderboard = []
    for rank, r in enumerate(results, 1):
        leaderboard.append({
            'rank':            rank,
            'name':            r.name,
            'roll_number':     r.roll_number,
            'total_score':     r.total_score or 0,
            'rooms_completed': r.rooms_completed
        })

    return jsonify({'batch': batch, 'leaderboard': leaderboard}), 200
