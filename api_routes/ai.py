# ============================================================
#  routes/ai.py — NVIDIA NIM AI Integration
#  Model: mistralai/mistral-7b-instruct-v0.2
#
#  POST /api/ai/hint         - AI generated hint for a question
#  POST /api/ai/explain      - Explain why an answer is wrong
#  POST /api/ai/summary      - Personalized improvement advice
#  POST /api/ai/question-tip - Quick tip before attempting
# ============================================================

import json
from flask              import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from openai             import OpenAI
from models             import Question, Room
from config             import Config
import os

ai_bp = Blueprint('ai', __name__)

# ============================================================
#  NVIDIA NIM CLIENT SETUP
#  Paste your API key in config.py — never hardcode here!
# ============================================================
def get_nvidia_client():
    return OpenAI(
        base_url = "https://integrate.api.nvidia.com/v1",
        api_key  = Config.NVIDIA_API_KEY
    )

NVIDIA_MODEL = "mistralai/mistral-7b-instruct-v0.2"


# ============================================================
#  HELPER — Call NVIDIA NIM API
# ============================================================
def call_nvidia(system_prompt, user_prompt, max_tokens=300):
    try:
        client = get_nvidia_client()
        response = client.chat.completions.create(
            model      = NVIDIA_MODEL,
            messages   = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            temperature = 0.5,
            max_tokens  = max_tokens
        )
        return response.choices[0].message.content.strip(), None
    except Exception as e:
        return None, str(e)


# ============================================================
#  ROUTE 1 — AI Hint Generator
#  Generates a smart hint without revealing the answer
# ============================================================
@ai_bp.route('/hint', methods=['POST'])
@jwt_required()
def generate_hint():
    data = request.get_json()
    uid = get_jwt_identity()
    question_id = data.get('question_id')

    if not question_id:
        return jsonify({'error': 'question_id is required'}), 400

    question = Question.query.get_or_404(question_id)
    room     = Room.query.get(question.room_id)

    system_prompt = """You are a programming tutor inside a hacker-themed escape room game.
Your job is to give a HINT for a programming question WITHOUT revealing the answer.
Keep the hint to 2-3 sentences maximum.
Be encouraging but cryptic — guide the student to think, not just tell them.
Use technical terminology appropriate for BTech IT students.
Do NOT reveal the correct answer or correct option."""

    user_prompt = f"""
Programming Language: {room.language}
Question: {question.question_text}
Code Snippet: {question.code_snippet or 'No code snippet'}
Question Type: {question.type}
{"Options: " + str(question.options) if question.type == 'mcq' else ''}

Give a helpful hint that points them in the right direction WITHOUT revealing the answer.
"""

    hint, error = call_nvidia(system_prompt, user_prompt, max_tokens=150)

    if error:
        # Fallback to stored hint if AI fails
        return jsonify({
            'hint':   question.hint or 'Think carefully about the fundamentals!',
            'source': 'fallback'
        }), 200

    return jsonify({'hint': hint, 'source': 'ai'}), 200


# ============================================================
#  ROUTE 2 — AI Wrong Answer Explainer
#  Explains WHY the student's answer was wrong
# ============================================================
@ai_bp.route('/explain', methods=['POST'])
@jwt_required()
def explain_wrong_answer():
    data = request.get_json()
    uid = get_jwt_identity()
    question_id    = data.get('question_id')
    student_answer = data.get('student_answer')
    correct_answer = data.get('correct_answer')

    question = Question.query.get_or_404(question_id)
    room     = Room.query.get(question.room_id)

    system_prompt = """You are a friendly programming tutor in a hacker escape room.
A student just answered a question INCORRECTLY.
Explain clearly and concisely WHY their answer was wrong and WHY the correct answer is right.
Keep it to 3-4 sentences. Be encouraging — say something like "Good try, but..."
Use simple language appropriate for a BTech 3rd year IT student.
End with one key concept they should remember."""

    user_prompt = f"""
Language: {room.language}
Question: {question.question_text}
Code: {question.code_snippet or 'No code'}
Student answered: {student_answer}
Correct answer: {correct_answer}

Explain why the student's answer was wrong and why {correct_answer} is correct.
"""

    explanation, error = call_nvidia(system_prompt, user_prompt, max_tokens=200)

    if error:
        return jsonify({
            'explanation': f'The correct answer is {correct_answer}. Review the {room.language} fundamentals for this topic.',
            'source': 'fallback'
        }), 200

    return jsonify({'explanation': explanation, 'source': 'ai'}), 200


# ============================================================
#  ROUTE 3 — AI Personalized Summary Advice
#  After quiz completion — gives study recommendations
# ============================================================
@ai_bp.route('/summary', methods=['POST'])
@jwt_required()
def generate_summary_advice():
    data = request.get_json()
    uid = get_jwt_identity()
    name     = data.get('student_name', 'Student')
    score    = data.get('total_score', 0)
    weak     = data.get('weak_topics', [])
    rooms    = data.get('room_summaries', [])

    weak_str  = ', '.join([f"{w['topic']} in {w['room']}" for w in weak]) or 'None'
    rooms_str = '\n'.join([
        f"- {r['language']}: {r['correct']} correct, {r['wrong']} wrong ({r['percentage']}%)"
        for r in rooms
    ])

    system_prompt = """You are a senior programming mentor reviewing a BTech IT student's performance
in a programming quiz escape room game covering C, C++, Java, SQL, DSA, DAA, and Python.
Give personalized, actionable study advice based on their performance.
Be encouraging but honest. Keep response to 4-5 sentences.
Format: Start with a performance summary, then 2-3 specific study recommendations.
Do NOT use bullet points — write in flowing sentences."""

    user_prompt = f"""
Student: {name}
Total Score: {score}
Performance per room:
{rooms_str}
Weak topics identified: {weak_str}

Give this student personalized advice on what to study and how to improve.
"""

    advice, error = call_nvidia(system_prompt, user_prompt, max_tokens=250)

    if error:
        advice = f"Good effort, {name}! Focus on reviewing your weak topics: {weak_str}. Practice more problems on these concepts to strengthen your understanding."

    return jsonify({'advice': advice, 'source': 'ai' if not error else 'fallback'}), 200


# ============================================================
#  ROUTE 4 — AI Quick Concept Tip
#  Before student starts a room — gives a quick tip
# ============================================================
@ai_bp.route('/room-tip', methods=['POST'])
@jwt_required()
def room_tip():
    data = request.get_json()
    uid = get_jwt_identity()
    room_id = data.get('room_id')
    room    = Room.query.get_or_404(room_id)

    system_prompt = """You are a hacker guide in a programming escape room.
Before a student enters a room, give them ONE quick tip — a key concept reminder
for the programming language of that room.
Keep it to exactly 2 sentences. Make it sound dramatic and exciting like a hacker game.
Start with something like 'Agent, remember:' or 'Before you enter:'"""

    user_prompt = f"""
The student is about to enter the {room.language} room called "{room.name}".
Room description: {room.description}

Give them one quick, exciting tip to prepare them.
"""

    tip, error = call_nvidia(system_prompt, user_prompt, max_tokens=100)

    if error:
        tips = {
            'C':      'Agent, remember: In C, every pointer must be initialized before use!',
            'C++':    'Before you enter: Constructors run at creation, destructors at destruction!',
            'Java':   'Agent, remember: In Java, String literals share memory in the String Pool!',
            'SQL':    'Before you enter: WHERE filters rows, HAVING filters groups!',
            'DSA':    'Agent, remember: Always think about time complexity before choosing a data structure!',
            'DAA':    'Before you enter: Divide and conquer, dynamic programming, greedy — know when to use each!',
            'Python': 'Agent, remember: In Python, indentation is not optional — it IS the syntax!'
        }
        tip = tips.get(room.language, 'Stay sharp and think before you answer!')

    return jsonify({'tip': tip, 'source': 'ai' if not error else 'fallback'}), 200
