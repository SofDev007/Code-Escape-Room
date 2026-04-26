# ============================================================
#  routes/quiz.py — Core Quiz Game Logic
#
#  GET  /api/quiz/rooms              - Get all active rooms (with question count)
#  POST /api/quiz/start              - Start a new quiz session
#  GET  /api/quiz/session/<id>       - Get session status
#  GET  /api/quiz/room/<id>/questions - Get random questions for a room
#  POST /api/quiz/answer             - Submit an answer
#  POST /api/quiz/room/complete      - Mark a room as complete
#  POST /api/quiz/session/finish     - Finish entire quiz, get summary
#  GET  /api/quiz/summary/<session_id> - Get full session summary
# ============================================================

import random
import json
from flask              import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime           import datetime
from extensions         import db
from models             import (User, Room, Question, RoomAccess,
                                QuizSession, RoomAttempt, QuestionAttempt)
from config             import Config

quiz_bp = Blueprint('quiz', __name__)

QUESTIONS_PER_ROOM = Config.QUESTIONS_PER_ROOM  # = 4


# ── GET ALL ACTIVE ROOMS ─────────────────────────────────────
@quiz_bp.route('/rooms', methods=['GET'])
@jwt_required()
def get_all_rooms():
    """
    Returns all active rooms with question counts.
    Used by index.html as a fallback when no rooms are assigned.
    """
    rooms = Room.query.filter_by(is_active=True).all()
    result = []
    for r in rooms:
        d = r.to_dict()
        d['question_count'] = Question.query.filter_by(room_id=r.id).count()
        result.append(d)
    return jsonify({'rooms': result}), 200


@quiz_bp.route('/start', methods=['POST'])
@jwt_required()
def start_session():
    """
    Student starts a quiz. Returns session ID and their assigned rooms.
    Body: { "difficulty": "easy" | "medium" | "hard", "room_ids": [1, 2, 3] }
    """
    uid        = get_jwt_identity()
    data       = request.get_json()
    difficulty = data.get('difficulty', 'medium')
    selected_room_ids = data.get('room_ids', [])

    # Get student's assigned rooms
    access = RoomAccess.query.filter_by(user_id=uid).all()
    assigned_room_ids = [a.room_id for a in access]
    
    # Identify which rooms we are actually using
    if selected_room_ids:
        # Filter so student only enters rooms they have access to (assigned OR public)
        rooms = Room.query.filter(
            Room.id.in_(selected_room_ids),
            (Room.id.in_(assigned_room_ids)) | (Room.is_public == True),
            Room.is_active == True
        ).all()
    else:
        # Default to all assigned rooms if nothing selected
        rooms = Room.query.filter(Room.id.in_(assigned_room_ids), Room.is_active == True).all()

    if not rooms:
        return jsonify({'error': 'No access to selected rooms or no rooms assigned.'}), 403

    # Create new session
    session = QuizSession(
        user_id    = uid,
        difficulty = difficulty,
        status     = 'in_progress'
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({
        'session_id': session.id,
        'difficulty': difficulty,
        'rooms':      [r.to_dict() for r in rooms],
        'message':    'Quiz session started. Good luck!'
    }), 201


# ── GET RANDOM QUESTIONS FOR A ROOM ─────────────────────────
@quiz_bp.route('/room/<int:room_id>/questions', methods=['GET'])
@jwt_required()
def get_room_questions(room_id):
    """
    Returns N randomly selected questions for a room.
    Does NOT include correct answers — those are sent only after submission.
    """
    uid = get_jwt_identity()

    # Check if student has access to this room (Assigned OR Public)
    room   = Room.query.get(room_id)
    access = RoomAccess.query.filter_by(user_id=uid, room_id=room_id).first()
    
    if not room or not room.is_active:
        return jsonify({'error': 'Room not found or inactive'}), 404
        
    if not access and not room.is_public:
        return jsonify({'error': 'You do not have access to this room'}), 403

    # Get difficulty from query param
    difficulty = request.args.get('difficulty', 'medium')

    # Fetch questions — mix of difficulties for fairness
    all_questions = Question.query.filter_by(room_id=room_id).all()

    if len(all_questions) <= QUESTIONS_PER_ROOM:
        questions = all_questions
    else:
        # Sort questions to ensure stable deterministic order before bucketing
        all_questions.sort(key=lambda q: q.id)
        
        # Determine available disjoint buckets based on student id
        num_buckets = len(all_questions) // QUESTIONS_PER_ROOM
        if num_buckets > 1:
            bucket_idx = int(uid) % num_buckets
            start_idx = bucket_idx * QUESTIONS_PER_ROOM
            bucket_questions = all_questions[start_idx : start_idx + QUESTIONS_PER_ROOM]
            questions = random.sample(bucket_questions, len(bucket_questions))
        else:
            questions = random.sample(all_questions, QUESTIONS_PER_ROOM)

    # Return questions WITHOUT correct answers
    return jsonify({
        'room_id':   room_id,
        'questions': [q.to_dict(include_answer=False) for q in questions],
        'count':     len(questions)
    }), 200


# ── SUBMIT AN ANSWER ─────────────────────────────────────────
@quiz_bp.route('/answer', methods=['POST'])
@jwt_required()
def submit_answer():
    """
    Student submits answer to one question.
    Body: {
        "session_id": 1,
        "room_attempt_id": 1,   (or null if first question in room)
        "room_id": 1,
        "question_id": 5,
        "answer": "15",         (string for fill, "0"/"1"/"2"/"3" index for mcq)
        "hint_used": false,
        "time_taken": 12
    }
    """
    uid = get_jwt_identity()
    data     = request.get_json()

    question = Question.query.get_or_404(data['question_id'])

    # ── Check if answer is correct
    is_correct = False
    if question.type == 'mcq':
        try:
            selected_index = int(data['answer'])
            is_correct     = (selected_index == question.correct_index)
        except:
            is_correct = False
    else:  # fill
        is_correct = (str(data['answer']).strip().lower() ==
                      str(question.correct_answer).strip().lower())

    # ── Get or create room attempt
    room_attempt_id = data.get('room_attempt_id')
    if room_attempt_id:
        room_attempt = RoomAttempt.query.get(room_attempt_id)
    else:
        # First question in this room — create room attempt
        room_attempt = RoomAttempt(
            session_id = data['session_id'],
            user_id    = uid,
            room_id    = data['room_id']
        )
        db.session.add(room_attempt)
        db.session.flush()   # Get the ID without committing

    # ── Update room attempt counters
    if is_correct:
        room_attempt.correct_count += 1
        # Exactly 20 points per question as requested
        room_attempt.score += 20
    else:
        room_attempt.wrong_count += 1

    if data.get('hint_used'):
        room_attempt.hints_used += 1

    # ── Save question attempt
    q_attempt = QuestionAttempt(
        room_attempt_id = room_attempt.id,
        question_id     = question.id,
        user_answer     = str(data['answer']),
        is_correct      = is_correct,
        hint_used       = data.get('hint_used', False),
        time_taken      = data.get('time_taken', 0)
    )
    db.session.add(q_attempt)
    db.session.commit()

    # ── Return result with correct answer revealed
    return jsonify({
        'is_correct':      is_correct,
        'room_attempt_id': room_attempt.id,
        'correct_index':   question.correct_index   if question.type == 'mcq'  else None,
        'correct_answer':  question.correct_answer  if question.type == 'fill' else None,
        'score_so_far':    room_attempt.score,
        'message':         '✓ Correct!' if is_correct else '✗ Wrong!'
    }), 200


# ── COMPLETE A ROOM ──────────────────────────────────────────
@quiz_bp.route('/room/complete', methods=['POST'])
@jwt_required()
def complete_room():
    """
    Called when student finishes all questions in a room.
    Body: { "room_attempt_id": 1, "time_taken": 120, "status": "completed" }
    """
    data         = request.get_json()
    room_attempt = RoomAttempt.query.get_or_404(data['room_attempt_id'])

    room_attempt.time_taken = data.get('time_taken', 0)
    room_attempt.status     = data.get('status', 'completed')
    db.session.commit()

    # Update session total score
    session = QuizSession.query.get(room_attempt.session_id)
    session.total_score = db.session.query(
        db.func.sum(RoomAttempt.score)
    ).filter_by(session_id=session.id).scalar() or 0
    db.session.commit()

    return jsonify({
        'message':       f'Room completed!',
        'room_score':    room_attempt.score,
        'correct':       room_attempt.correct_count,
        'wrong':         room_attempt.wrong_count,
        'total_score':   session.total_score
    }), 200


# ── FINISH ENTIRE QUIZ ────────────────────────────────────────
@quiz_bp.route('/session/finish', methods=['POST'])
@jwt_required()
def finish_session():
    """
    Called when student completes all rooms or runs out of lives.
    Body: { "session_id": 1, "status": "completed", "lives_left": 2, "time_taken": 480 }
    """
    data    = request.get_json()
    session = QuizSession.query.get_or_404(data['session_id'])

    session.status       = data.get('status', 'completed')
    session.lives_left   = data.get('lives_left', 0)
    session.time_taken   = data.get('time_taken', 0)
    session.completed_at = datetime.utcnow()

    db.session.commit()

    return jsonify({
        'message':     'Quiz finished!',
        'session_id':  session.id,
        'total_score': session.total_score,
        'status':      session.status
    }), 200


# ── GET SESSION SUMMARY ───────────────────────────────────────
@quiz_bp.route('/summary/<int:session_id>', methods=['GET'])
@jwt_required()
def get_summary(session_id):
    """
    Returns full per-room performance summary for end screen.
    Shows weak topics, correct/wrong per room, total score.
    """
    uid = get_jwt_identity()
    user_obj = User.query.get(uid)
    session  = QuizSession.query.get_or_404(session_id)

    # Security — only owner or admin can see
    if str(session.user_id) != str(uid) and user_obj.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    user          = User.query.get(session.user_id)
    room_attempts = RoomAttempt.query.filter_by(session_id=session_id).all()

    room_summaries = []
    weak_topics    = []

    for ra in room_attempts:
        room = Room.query.get(ra.room_id)
        q_attempts = QuestionAttempt.query.filter_by(room_attempt_id=ra.id).all()

        # Find weak topics = tags of wrong answers
        for qa in q_attempts:
            if not qa.is_correct:
                q = Question.query.get(qa.question_id)
                if q and q.tag:
                    weak_topics.append({
                        'room':    room.language,
                        'topic':   q.tag,
                        'question': q.question_text[:80] + '...'
                    })

        room_summaries.append({
            'room_name':     room.name,
            'language':      room.language,
            'score':         ra.score,
            'correct':       ra.correct_count,
            'wrong':         ra.wrong_count,
            'hints_used':    ra.hints_used,
            'time_taken':    ra.time_taken,
            'status':        ra.status,
            'percentage':    round((ra.correct_count / max(ra.correct_count + ra.wrong_count, 1)) * 100)
        })

    return jsonify({
        'student_name':  user.name,
        'batch':         user.batch,
        'total_score':   session.total_score,
        'difficulty':    session.difficulty,
        'status':        session.status,
        'time_taken':    session.time_taken,
        'lives_left':    session.lives_left,
        'room_summaries': room_summaries,
        'weak_topics':   weak_topics,
        'completed_at':  str(session.completed_at) if session.completed_at else None
    }), 200
