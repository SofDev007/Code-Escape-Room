# ============================================================
#  routes/admin.py — Admin Panel Routes
#
#  GET    /api/admin/students                     - List all students
#  POST   /api/admin/students                     - Create student
#  POST   /api/admin/students/<id>/ban            - Ban/unban student
#  POST   /api/admin/students/<id>/toggle         - Activate/deactivate
#  DELETE /api/admin/students/<id>               - Delete student
#  GET    /api/admin/rooms                        - List all rooms
#  POST   /api/admin/rooms                        - Create new room
#  PATCH  /api/admin/rooms/<id>                  - Update room
#  POST   /api/admin/rooms/<id>/access            - Assign rooms to student
#  DELETE /api/admin/students/<id>/access/<rid>   - Remove room from student
#  GET    /api/admin/students/<id>/access         - Student's assigned rooms
#  GET    /api/admin/stats                        - Dashboard stats
#  POST   /api/admin/batch-access                 - Assign rooms to entire batch
#  POST   /api/admin/questions/generate           - AI generate questions
#  GET    /api/admin/issues                       - List issues
#  POST   /api/admin/issues/<id>/resolve          - Mark issue resolved
# ============================================================

import json
from flask              import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from extensions         import db, bcrypt
from models             import User, Room, RoomAccess, QuizSession, RoomAttempt, Question
from config             import Config
import requests
import re
import os

admin_bp = Blueprint('admin', __name__)

# NVIDIA NIM API
NVIDIA_API_URL = 'https://integrate.api.nvidia.com/v1/chat/completions'
NVIDIA_MODEL   = 'meta/llama-3.1-8b-instruct'


# ── HELPER ───────────────────────────────────────────────────
def admin_required():
    uid  = get_jwt_identity()
    user = User.query.get(uid)
    if not user or user.role != 'admin':
        return None, jsonify({'error': 'Admin access required'}), 403
    return user, None, None


# ── LIST ALL STUDENTS ─────────────────────────────────────────
@admin_bp.route('/students', methods=['GET'])
@jwt_required()
def list_students():
    user, err, code = admin_required()
    if err: return err, code

    batch = request.args.get('batch')
    query = User.query.filter_by(role='student')
    if batch:
        query = query.filter_by(batch=batch)

    students = query.order_by(User.batch, User.name).all()
    result = []
    for s in students:
        student_data = s.to_dict()
        assigned_rooms = RoomAccess.query.filter_by(user_id=s.id).all()
        student_data['assigned_room_ids'] = [a.room_id for a in assigned_rooms]
        result.append(student_data)

    return jsonify({'students': result, 'total': len(result)}), 200


# ── CREATE STUDENT ────────────────────────────────────────────
@admin_bp.route('/students', methods=['POST'])
@jwt_required()
def create_student():
    admin, err, code = admin_required()
    if err: return err, code

    data = request.get_json()
    required = ['name', 'email', 'password']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required'}), 400

    if User.query.filter_by(email=data['email'].lower().strip()).first():
        return jsonify({'error': 'Email already registered'}), 409

    # Auto-generate username if not provided
    base_username = re.sub(r'[^a-z0-9_]', '', data['name'].split()[0].lower())
    username = base_username
    counter  = 1
    while User.query.filter(db.func.lower(User.username) == username).first():
        username = f'{base_username}{counter}'
        counter += 1

    hashed = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    student = User(
        name          = data['name'].strip(),
        username      = username,
        email         = data['email'].lower().strip(),
        password_hash = hashed,
        role          = 'student',
        batch         = data.get('batch', ''),
        roll_number   = data.get('roll_number', ''),
        is_active     = True,
        is_banned     = False
    )
    db.session.add(student)
    db.session.commit()

    # Assign rooms if provided
    room_ids = data.get('room_ids', [])
    for room_id in room_ids:
        room = Room.query.get(room_id)
        if room and not RoomAccess.query.filter_by(user_id=student.id, room_id=room_id).first():
            db.session.add(RoomAccess(user_id=student.id, room_id=room_id, assigned_by=admin.id))
    db.session.commit()

    return jsonify({'message': f'Student {student.name} created', 'student': student.to_dict()}), 201


# ── BAN / UNBAN STUDENT ───────────────────────────────────────
@admin_bp.route('/students/<int:student_id>/ban', methods=['POST'])
@jwt_required()
def ban_student(student_id):
    admin, err, code = admin_required()
    if err: return err, code

    student = User.query.get_or_404(student_id)
    data    = request.get_json() or {}

    if student.is_banned:
        # Unban
        student.is_banned   = False
        student.ban_reason  = None
        student.is_active   = True
        action = 'unbanned'
    else:
        # Ban
        student.is_banned  = True
        student.ban_reason = data.get('reason', 'Banned by moderator')
        student.is_active  = False
        action = 'banned'

    db.session.commit()
    return jsonify({'message': f'Player {student.name} has been {action}', 'user': student.to_dict()}), 200


# ── DEACTIVATE / REACTIVATE STUDENT ──────────────────────────
@admin_bp.route('/students/<int:student_id>/toggle', methods=['POST'])
@jwt_required()
def toggle_student(student_id):
    admin, err, code = admin_required()
    if err: return err, code

    student = User.query.get_or_404(student_id)
    student.is_active = not student.is_active
    db.session.commit()

    status = 'activated' if student.is_active else 'deactivated'
    return jsonify({'message': f'Student {student.name} {status}'}), 200


# ── BULK CREATE STUDENTS ──────────────────────────────────────
@admin_bp.route('/students/bulk', methods=['POST'])
@jwt_required()
def bulk_create_students():
    admin, err, code = admin_required()
    if err: return err, code

    data     = request.get_json()
    students = data.get('students', [])
    created  = []
    errors   = []

    for s in students:
        try:
            if User.query.filter_by(email=s['email'].lower().strip()).first():
                errors.append(f"{s['email']} already exists")
                continue
            hashed = bcrypt.generate_password_hash(s['password']).decode('utf-8')
            new_s  = User(
                name=s['name'], email=s['email'].lower().strip(),
                password_hash=hashed, role='student',
                batch=s.get('batch',''), roll_number=s.get('roll_number',''),
                is_active=True, is_banned=False
            )
            db.session.add(new_s)
            created.append(s['name'])
        except Exception as e:
            errors.append(str(e))

    db.session.commit()
    return jsonify({'created': created, 'errors': errors}), 201


# ── LIST ALL ROOMS ────────────────────────────────────────────
@admin_bp.route('/rooms', methods=['GET'])
@jwt_required()
def list_rooms():
    admin, err, code = admin_required()
    if err: return err, code

    rooms  = Room.query.all()
    result = []
    for r in rooms:
        room_data  = r.to_dict()
        room_data['question_count'] = len(r.questions)
        result.append(room_data)

    return jsonify({'rooms': result}), 200


# ── CREATE NEW ROOM ───────────────────────────────────────────
@admin_bp.route('/rooms', methods=['POST'])
@jwt_required()
def create_room():
    admin, err, code = admin_required()
    if err: return err, code

    data = request.get_json()
    required = ['name', 'language']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'{f} is required'}), 400

    # Create the room
    new_room = Room(
        name        = data.get('name', 'New Vault'),
        language    = data.get('language', 'Python'),
        description = data.get('description', ''),
        lore        = data.get('lore', ''),
        time_limit  = int(data.get('time_limit', 180)),
        is_active   = True,
        is_public   = data.get('is_public', False)
    )
    db.session.add(new_room)
    db.session.commit()

    return jsonify({'message': f'Room "{new_room.name}" created', 'room': new_room.to_dict()}), 201


# ── UPDATE ROOM ────────────────────────────────────────────────
@admin_bp.route('/rooms/<int:room_id>', methods=['PATCH'])
@jwt_required()
def update_room(room_id):
    admin, err, code = admin_required()
    if err: return err, code

    room = Room.query.get_or_404(room_id)
    data = request.get_json()

    for field in ['name', 'description', 'lore', 'color_var', 'time_limit', 'is_active']:
        if field in data:
            setattr(room, field, data[field])

    db.session.commit()
    return jsonify({'message': 'Room updated', 'room': room.to_dict()}), 200


# ── DELETE ROOM ────────────────────────────────────────────────
@admin_bp.route('/rooms/<int:room_id>', methods=['DELETE'])
@jwt_required()
def delete_room(room_id):
    admin, err, code = admin_required()
    if err: return err, code

    room = Room.query.get_or_404(room_id)
    
    # Optionally delete associated accesses and questions to avoid foreign key issues
    from models import RoomAccess, Question
    RoomAccess.query.filter_by(room_id=room_id).delete()
    Question.query.filter_by(room_id=room_id).delete()
    
    db.session.delete(room)
    db.session.commit()
    return jsonify({'message': f'Room "{room.name}" deleted'}), 200


# ── ASSIGN ROOMS TO A STUDENT ─────────────────────────────────
@admin_bp.route('/students/<int:student_id>/access', methods=['POST'])
@jwt_required()
def assign_rooms(student_id):
    admin, err, code = admin_required()
    if err: return err, code

    student  = User.query.get_or_404(student_id)
    data     = request.get_json()
    room_ids = data.get('room_ids', [])

    assigned = []
    for room_id in room_ids:
        room = Room.query.get(room_id)
        if not room:
            continue
        existing = RoomAccess.query.filter_by(user_id=student_id, room_id=room_id).first()
        if not existing:
            access = RoomAccess(user_id=student_id, room_id=room_id, assigned_by=admin.id)
            db.session.add(access)
            assigned.append(room.language)

    db.session.commit()
    return jsonify({'message': f'Assigned {len(assigned)} rooms to {student.name}', 'assigned': assigned}), 200


# ── REMOVE ROOM FROM STUDENT ──────────────────────────────────
@admin_bp.route('/students/<int:student_id>/access/<int:room_id>', methods=['DELETE'])
@jwt_required()
def remove_room_access(student_id, room_id):
    admin, err, code = admin_required()
    if err: return err, code

    access = RoomAccess.query.filter_by(user_id=student_id, room_id=room_id).first_or_404()
    db.session.delete(access)
    db.session.commit()
    return jsonify({'message': 'Room access removed'}), 200


# ── GET STUDENT'S ASSIGNED ROOMS ──────────────────────────────
@admin_bp.route('/students/<int:student_id>/access', methods=['GET'])
@jwt_required()
def get_student_access(student_id):
    admin, err, code = admin_required()
    if err: return err, code

    student = User.query.get_or_404(student_id)
    access  = RoomAccess.query.filter_by(user_id=student_id).all()
    rooms   = [Room.query.get(a.room_id).to_dict() for a in access]

    return jsonify({'student': student.to_dict(), 'rooms': rooms}), 200


# ── BULK ASSIGN ROOMS TO BATCH ────────────────────────────────
@admin_bp.route('/batch-access', methods=['POST'])
@jwt_required()
def batch_assign_rooms():
    admin, err, code = admin_required()
    if err: return err, code

    data     = request.get_json()
    batch    = data.get('batch')
    room_ids = data.get('room_ids', [])

    if not batch or not room_ids:
        return jsonify({'error': 'batch and room_ids are required'}), 400

    students = User.query.filter_by(role='student', batch=batch, is_active=True).all()
    count    = 0

    for student in students:
        for room_id in room_ids:
            existing = RoomAccess.query.filter_by(user_id=student.id, room_id=room_id).first()
            if not existing:
                db.session.add(RoomAccess(
                    user_id=student.id, room_id=room_id, assigned_by=admin.id
                ))
                count += 1

    db.session.commit()
    return jsonify({
        'message': f'Assigned rooms to {len(students)} students in batch {batch}',
        'total_assignments': count
    }), 200


# ── DASHBOARD STATS ────────────────────────────────────────────
@admin_bp.route('/stats', methods=['GET'])
@jwt_required()
def dashboard_stats():
    admin, err, code = admin_required()
    if err: return err, code

    total_students = User.query.filter_by(role='student', is_active=True).count()
    banned_count   = User.query.filter_by(role='student', is_banned=True).count()
    total_rooms    = Room.query.filter_by(is_active=True).count()
    total_sessions = QuizSession.query.count()
    completed      = QuizSession.query.filter_by(status='completed').count()
    total_attempts = RoomAttempt.query.count()

    top_students = db.session.query(
        User.name, User.batch,
        db.func.sum(RoomAttempt.score).label('total_score')
    ).join(RoomAttempt, User.id == RoomAttempt.user_id)\
     .group_by(User.id)\
     .order_by(db.desc('total_score'))\
     .limit(5).all()

    batches = db.session.query(User.batch)\
        .filter(User.role == 'student', User.batch != None)\
        .distinct().all()

    return jsonify({
        'stats': {
            'total_students':  total_students,
            'banned_students': banned_count,
            'total_rooms':     total_rooms,
            'total_sessions':  total_sessions,
            'completed_games': completed,
            'total_attempts':  total_attempts,
        },
        'top_students': [
            {'name': t.name, 'batch': t.batch, 'score': t.total_score}
            for t in top_students
        ],
        'batches': [b[0] for b in batches if b[0]]
    }), 200


# ── AI GENERATE QUESTIONS ──────────────────────────────────────
def generate_nvidia_image(prompt):
    """
    Calls NVIDIA NIM SDXL endpoint to generate a Base64 image.
    """
    import base64
    url = "https://ai.api.nvidia.com/v1/genai/stabilityai/sdxl"
    headers = {
        "Authorization": f"Bearer {Config.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "prompt": prompt,
        "header": { "image_size": "1024x1024" }
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=25)
        if res.status_code == 200:
            data = res.json()
            if 'data' in data and len(data['data']) > 0:
                b64 = data['data'][0].get('b64_json')
                if b64:
                    return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"NVIDIA Image Error: {e}")
    return None

@admin_bp.route('/questions/generate', methods=['POST'])
@jwt_required()
def generate_questions():
    admin, err, code = admin_required()
    if err: return err, code

    data       = request.get_json()
    room_id    = data.get('room_id')
    count      = int(data.get('count', 5))
    difficulty = data.get('difficulty', 'medium')
    syllabus   = data.get('syllabus', '').strip()
    include_images = data.get('include_images', False)

    if not room_id:
        return jsonify({'error': 'room_id is required'}), 400

    room = Room.query.get(room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    count = min(count, 10)  # Cap at 10 per request

    syllabus_rule = f"- STRICTLY restrict the questions to the following topics: {syllabus}" if syllabus else ""
    image_rule = '- You MUST include a highly detailed "image_prompt" field for EVERY single question describing what visual illustration should accompany it!' if include_images else ""
    format_example = '    "image_prompt": "A highly detailed prompt describing an illustration of the code or concept",\n' if include_images else ""

    prompt = f"""Generate {count} multiple-choice quiz questions about {room.language} programming for a coding escape room game.
Difficulty: {difficulty}

Return ONLY a valid JSON array, no explanation. Format:
[
  {{
    "question": "What does ... do?",
    "code": "optional code snippet or null",
{format_example}    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_index": 0,
    "hint": "Think about...",
    "tag": "TOPIC_TAG"
  }}
]

Rules:
- correct_index is 0-based (0=A, 1=B, 2=C, 3=D)
- Each question must have exactly 4 options
- DO NOT include prefixes like "A.", "B.", "1.", or "a)" in the option text strings!
- Questions should be relevant to {room.language} programming
{syllabus_rule}
{image_rule}
- tag should be short like: SYNTAX, LOOPS, FUNCTIONS, OOP, etc.
- Include code snippets for {min(count//2, 3)} questions"""

    try:
        response = requests.post(
            NVIDIA_API_URL,
            headers={
                'Authorization': f'Bearer {Config.NVIDIA_API_KEY}',
                'Content-Type':  'application/json'
            },
            json={
                'model':       NVIDIA_MODEL,
                'messages':    [{'role': 'user', 'content': prompt}],
                'temperature': 0.7,
                'max_tokens':  2048
            },
            timeout=60
        )
        response.raise_for_status()
        content = response.json()['choices'][0]['message']['content'].strip()

        # Extract JSON array from response
        start = content.find('[')
        end   = content.rfind(']') + 1
        if start == -1 or end == 0:
            return jsonify({'error': 'AI returned invalid format'}), 500

        questions_data = json.loads(content[start:end])

        saved = []
        for q in questions_data:
            if not all(k in q for k in ['question', 'options', 'correct_index']):
                continue
                
            img_url = None
            if include_images and q.get('image_prompt'):
                # Call NVIDIA NIM SDXL for a high-quality, permanent Base64 image
                img_url = generate_nvidia_image(q['image_prompt'])

            question = Question(
                room_id        = room_id,
                type           = 'mcq',
                tag            = q.get('tag', room.language.upper()),
                question_text  = q['question'],
                code_snippet   = q.get('code') if q.get('code') not in [None, 'null', ''] else None,
                image_url      = img_url,
                lang_label     = room.language,
                options        = q['options'],
                correct_index  = min(3, max(0, int(q['correct_index']))),
                hint           = q.get('hint', ''),
                difficulty     = difficulty
            )
            db.session.add(question)
            saved.append(q['question'][:60])

        db.session.commit()
        return jsonify({
            'message':   f'{len(saved)} questions generated and saved to {room.name}',
            'count':     len(saved),
            'questions': saved
        }), 201

    except requests.exceptions.Timeout:
        return jsonify({'error': 'AI request timed out. Please try again in a moment.'}), 504
    except requests.exceptions.ConnectionError as e:
        return jsonify({'error': f'Network Error: Could not connect to AI service. Please check your internet connection or DNS settings. ({str(e)})'}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'AI service error: {str(e)}'}), 502
    except Exception as e:
        return jsonify({'error': f'Failed to generate questions: {str(e)}'}), 500


# ── ISSUES — List ──────────────────────────────────────────────
# We store issues in a simple in-memory list + JSON file for now
# (No DB model to keep migration simple — can be extended later)
import json
from pathlib import Path

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


@admin_bp.route('/issues', methods=['GET'])
@jwt_required()
def list_issues():
    admin, err, code = admin_required()
    if err: return err, code

    issues   = load_issues()
    resolved = request.args.get('resolved', 'false').lower() == 'true'
    if request.args.get('resolved') is not None:
        issues = [i for i in issues if i.get('resolved', False) == resolved]

    return jsonify({'issues': issues, 'total': len(issues)}), 200


@admin_bp.route('/issues/<int:issue_id>/resolve', methods=['POST'])
@jwt_required()
def resolve_issue(issue_id):
    admin, err, code = admin_required()
    if err: return err, code

    issues = load_issues()
    for issue in issues:
        if issue['id'] == issue_id:
            issue['resolved']     = True
            issue['resolved_by']  = admin.name
            save_issues(issues)
            return jsonify({'message': 'Issue marked as resolved'}), 200

    return jsonify({'error': 'Issue not found'}), 404


@admin_bp.route('/issues/<int:issue_id>', methods=['DELETE'])
@jwt_required()
def delete_issue(issue_id):
    admin, err, code = admin_required()
    if err: return err, code

    issues = load_issues()
    issues = [i for i in issues if i['id'] != issue_id]
    save_issues(issues)
    return jsonify({'message': 'Issue deleted'}), 200

# ── GET ROOM QUESTIONS FOR ADMIN ───────────────────────────────
@admin_bp.route('/rooms/<int:room_id>/questions', methods=['GET'])
@jwt_required()
def admin_room_questions(room_id):
    admin, err, code = admin_required()
    if err: return err, code

    questions = Question.query.filter_by(room_id=room_id).order_by(Question.id.asc()).all()
    return jsonify({
        'questions': [q.to_dict(include_answer=True) for q in questions]
    }), 200

# ── MANUALLY ADD QUESTION ──────────────────────────────────────
@admin_bp.route('/rooms/<int:room_id>/questions', methods=['POST'])
@jwt_required()
def add_manual_question(room_id):
    admin, err, code = admin_required()
    if err: return err, code

    room = Room.query.get_or_404(room_id)
    data = request.get_json()
    
    question = Question(
        room_id        = room_id,
        type           = 'mcq',
        tag            = data.get('tag', room.language.upper()),
        question_text  = data['question'],
        code_snippet   = data.get('code') or None,
        image_url      = data.get('image_url') or None,
        lang_label     = room.language,
        options        = data['options'],
        correct_index  = int(data['correct_index']),
        hint           = data.get('hint', ''),
        difficulty     = data.get('difficulty', 'medium')
    )
    db.session.add(question)
    db.session.commit()
    return jsonify({'message': 'Question added successfully'}), 201

# ── DELETE SINGLE QUESTION ────────────────────────────────────
@admin_bp.route('/questions/<int:question_id>', methods=['DELETE'])
@jwt_required()
def delete_question(question_id):
    admin, err, code = admin_required()
    if err: return err, code

    # Clean up associated attempt history if any to prevent constraint errors
    from models import QuestionAttempt
    QuestionAttempt.query.filter_by(question_id=question_id).delete()
    
    q = Question.query.get_or_404(question_id)
    db.session.delete(q)
    db.session.commit()
    return jsonify({'message': 'Question deleted'}), 200

# ── DELETE ALL QUESTIONS IN ROOM ──────────────────────────────
@admin_bp.route('/rooms/<int:room_id>/questions/all', methods=['DELETE'])
@jwt_required()
def delete_all_questions(room_id):
    admin, err, code = admin_required()
    if err: return err, code

    questions = Question.query.filter_by(room_id=room_id).all()
    q_ids = [q.id for q in questions]
    if q_ids:
        from models import QuestionAttempt
        QuestionAttempt.query.filter(QuestionAttempt.question_id.in_(q_ids)).delete()
        Question.query.filter_by(room_id=room_id).delete()
        db.session.commit()
    return jsonify({'message': f'All questions deleted'}), 200
