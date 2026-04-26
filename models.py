from extensions import db
from datetime   import datetime

# ── USER MODEL ──────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer,     primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    first_name    = db.Column(db.String(60),  nullable=True)
    last_name     = db.Column(db.String(60),  nullable=True)
    username      = db.Column(db.String(60),  unique=True, nullable=True, index=True)
    email         = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.Enum('admin','student'), default='student')
    batch         = db.Column(db.String(50))
    roll_number   = db.Column(db.String(20))
    is_active     = db.Column(db.Boolean,     default=True)
    is_banned     = db.Column(db.Boolean,     default=False)
    ban_reason    = db.Column(db.String(255), nullable=True)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)

    # ── FIXED: specify foreign_keys to avoid ambiguity
    room_access  = db.relationship('RoomAccess', foreign_keys='RoomAccess.user_id',    backref='user',     lazy=True)
    assigned_out = db.relationship('RoomAccess', foreign_keys='RoomAccess.assigned_by', backref='assigner', lazy=True)
    sessions     = db.relationship('QuizSession', backref='user', lazy=True)

    def to_dict(self):
        return {
            'id':          self.id,
            'name':        self.name,
            'first_name':  self.first_name,
            'last_name':   self.last_name,
            'username':    self.username,
            'email':       self.email,
            'role':        self.role,
            'batch':       self.batch,
            'roll_number': self.roll_number,
            'is_active':   self.is_active,
            'is_banned':   self.is_banned,
            'ban_reason':  self.ban_reason,
            'created_at':  str(self.created_at)
        }


# ── ROOM MODEL ──────────────────────────────────────────────
class Room(db.Model):
    __tablename__ = 'rooms'

    id          = db.Column(db.Integer,     primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    language    = db.Column(db.String(50),  nullable=False)
    description = db.Column(db.Text)
    lore        = db.Column(db.Text)
    color_var   = db.Column(db.String(50))
    time_limit  = db.Column(db.Integer,     default=180)
    is_active   = db.Column(db.Boolean,     default=True)
    is_public   = db.Column(db.Boolean,     default=False)
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    # Relationships
    questions   = db.relationship('Question',   backref='room', lazy=True)
    access      = db.relationship('RoomAccess', backref='room', lazy=True)

    def to_dict(self):
        return {
            'id':          self.id,
            'name':        self.name,
            'language':    self.language,
            'description': self.description,
            'lore':        self.lore,
            'color_var':   self.color_var,
            'time_limit':  self.time_limit,
            'is_active':   self.is_active,
            'is_public':   self.is_public
        }


# ── QUESTION MODEL ───────────────────────────────────────────
class Question(db.Model):
    __tablename__ = 'questions'

    id             = db.Column(db.Integer,            primary_key=True)
    room_id        = db.Column(db.Integer,            db.ForeignKey('rooms.id'), nullable=False)
    type           = db.Column(db.Enum('mcq','fill'), nullable=False)
    tag            = db.Column(db.String(100))
    question_text  = db.Column(db.Text,               nullable=False)
    code_snippet   = db.Column(db.Text)
    image_url      = db.Column(db.Text,               nullable=True)
    lang_label     = db.Column(db.String(20))
    options        = db.Column(db.JSON)
    correct_index  = db.Column(db.SmallInteger)
    correct_answer = db.Column(db.String(255))
    hint           = db.Column(db.Text)
    difficulty     = db.Column(db.Enum('easy','medium','hard'), default='medium')
    created_at     = db.Column(db.DateTime,           default=datetime.utcnow)

    def to_dict(self, include_answer=False):
        data = {
            'id':         self.id,
            'room_id':    self.room_id,
            'type':       self.type,
            'tag':        self.tag,
            'question':   self.question_text,
            'code':       self.code_snippet,
            'image_url':  self.image_url,
            'lang':       self.lang_label,
            'options':    self.options,
            'hint':       self.hint,
            'difficulty': self.difficulty
        }
        if include_answer:
            data['correct_index']  = self.correct_index
            data['correct_answer'] = self.correct_answer
        return data


# ── ROOM ACCESS MODEL ─────────────────────────────────────────
class RoomAccess(db.Model):
    __tablename__ = 'room_access'

    id          = db.Column(db.Integer,  primary_key=True)
    user_id     = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    room_id     = db.Column(db.Integer,  db.ForeignKey('rooms.id'), nullable=False)
    assigned_by = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'room_id'),)

    def to_dict(self):
        return {
            'user_id':     self.user_id,
            'room_id':     self.room_id,
            'assigned_by': self.assigned_by,
            'assigned_at': str(self.assigned_at)
        }


# ── QUIZ SESSION MODEL ────────────────────────────────────────
class QuizSession(db.Model):
    __tablename__ = 'quiz_sessions'

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    difficulty   = db.Column(db.Enum('easy','medium','hard'), default='medium')
    total_score  = db.Column(db.Integer, default=0)
    lives_left   = db.Column(db.Integer, default=3)
    status       = db.Column(db.Enum('in_progress','completed','failed','timeout'), default='in_progress')
    started_at   = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    time_taken   = db.Column(db.Integer)

    room_attempts = db.relationship('RoomAttempt', backref='session', lazy=True)

    def to_dict(self):
        return {
            'id':           self.id,
            'user_id':      self.user_id,
            'difficulty':   self.difficulty,
            'total_score':  self.total_score,
            'lives_left':   self.lives_left,
            'status':       self.status,
            'started_at':   str(self.started_at),
            'completed_at': str(self.completed_at) if self.completed_at else None,
            'time_taken':   self.time_taken
        }


# ── ROOM ATTEMPT MODEL ────────────────────────────────────────
class RoomAttempt(db.Model):
    __tablename__ = 'room_attempts'

    id            = db.Column(db.Integer, primary_key=True)
    session_id    = db.Column(db.Integer, db.ForeignKey('quiz_sessions.id'), nullable=False)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'),         nullable=False)
    room_id       = db.Column(db.Integer, db.ForeignKey('rooms.id'),         nullable=False)
    score         = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    wrong_count   = db.Column(db.Integer, default=0)
    hints_used    = db.Column(db.Integer, default=0)
    time_taken    = db.Column(db.Integer)
    status        = db.Column(db.Enum('completed','failed','timeout'), default='completed')
    attempted_at  = db.Column(db.DateTime, default=datetime.utcnow)

    question_attempts = db.relationship('QuestionAttempt', backref='room_attempt', lazy=True)

    def to_dict(self):
        return {
            'id':            self.id,
            'session_id':    self.session_id,
            'room_id':       self.room_id,
            'score':         self.score,
            'correct_count': self.correct_count,
            'wrong_count':   self.wrong_count,
            'hints_used':    self.hints_used,
            'time_taken':    self.time_taken,
            'status':        self.status,
            'attempted_at':  str(self.attempted_at)
        }


# ── QUESTION ATTEMPT MODEL ────────────────────────────────────
class QuestionAttempt(db.Model):
    __tablename__ = 'question_attempts'

    id              = db.Column(db.Integer, primary_key=True)
    room_attempt_id = db.Column(db.Integer, db.ForeignKey('room_attempts.id'), nullable=False)
    question_id     = db.Column(db.Integer, db.ForeignKey('questions.id'),     nullable=False)
    user_answer     = db.Column(db.String(255))
    is_correct      = db.Column(db.Boolean, default=False)
    hint_used       = db.Column(db.Boolean, default=False)
    time_taken      = db.Column(db.Integer)

    def to_dict(self):
        return {
            'question_id': self.question_id,
            'user_answer': self.user_answer,
            'is_correct':  self.is_correct,
            'hint_used':   self.hint_used,
            'time_taken':  self.time_taken
        }
