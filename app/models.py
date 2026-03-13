from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    email = db.Column(db.String(120), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(20), default='student') # 'student' or 'teacher'
    progress = db.relationship('UserProgress', backref='student', lazy='dynamic')
    saved_messages = db.relationship('SavedMessage', backref='user', lazy='dynamic')
    quiz_results = db.relationship('QuizResult', backref='student', lazy='dynamic')
    study_plans = db.relationship('StudyPlan', backref='student', lazy='dynamic')
    analyze_quiz_attempts = db.relationship('AnalyzeQuizAttempt', backref='student', lazy='dynamic')
    book_recommendations = db.relationship('BookRecommendation', backref='student', lazy='dynamic')
    
    # Gamification
    current_streak = db.Column(db.Integer, default=0)
    longest_streak = db.Column(db.Integer, default=0)
    last_active_date = db.Column(db.Date, nullable=True)
    earned_badges = db.relationship('UserBadge', backref='student', lazy='dynamic')
    activities = db.relationship('ActivityLog', backref='student', lazy='dynamic')

    # Leaderboard & Ranking
    total_tests_taken = db.Column(db.Integer, default=0)
    total_marks_scored = db.Column(db.Integer, default=0)
    average_score = db.Column(db.Float, default=0.0)
    calculated_rank = db.Column(db.Integer, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text)
    progress_records = db.relationship('UserProgress', backref='topic', lazy='dynamic')

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    score = db.Column(db.Integer, default=0)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)

class SavedMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    questions_json = db.Column(db.Text, nullable=False) # Store the generated quiz as JSON string
    timer_minutes = db.Column(db.Integer, default=15)
    code = db.Column(db.String(8), unique=True, index=True)  # 8-digit access code for students
    is_active = db.Column(db.Boolean, default=False)  # Published state
    source_type = db.Column(db.String(32))  # 'notes' or 'topic'
    topic = db.Column(db.String(128))
    difficulty = db.Column(db.String(32))  # easy / medium / hard
    num_questions = db.Column(db.Integer)
    question_types = db.Column(db.String(128))  # comma-separated list, e.g. "mcq,true_false"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    results = db.relationship('QuizResult', backref='quiz', lazy='dynamic')

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    answers_json = db.Column(db.Text)
    teacher_feedback = db.Column(db.Text)
    time_taken_seconds = db.Column(db.Integer)  # how long the student took to submit
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Proctoring Data
    violation_count = db.Column(db.Integer, default=0)
    violation_logs = db.Column(db.Text) # JSON array of warnings

class StudyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_result_id = db.Column(db.Integer, db.ForeignKey('quiz_result.id'), nullable=True)
    recommendations_json = db.Column(db.Text, nullable=False)  # structured recommendations from AI
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AnalyzeQuizAttempt(db.Model):
    """
    Stores per-user self-study quiz attempts created from the Analyze → Quiz tools.
    These are independent from teacher-managed quizzes.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_type = db.Column(db.String(16))  # 'topic' or 'pdf'
    topic_label = db.Column(db.String(256))
    source_name = db.Column(db.String(256))
    difficulty = db.Column(db.String(32))
    num_questions = db.Column(db.Integer)
    duration_seconds = db.Column(db.Integer)
    score = db.Column(db.Integer)
    total_questions = db.Column(db.Integer)
    time_taken_seconds = db.Column(db.Integer)
    weak_topics_json = db.Column(db.Text)  # aggregated weak topics summary
    questions_json = db.Column(db.Text)    # full quiz questions with answers/explanations
    answers_json = db.Column(db.Text)      # student answers by index
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BookRecommendation(db.Model):
    """
    Stores book recommendations for a student (search-based or performance-based),
    along with whether the student has viewed them.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source = db.Column(db.String(16))  # 'search' or 'performance'
    topic = db.Column(db.String(256))
    book_key = db.Column(db.String(128))  # provider-specific ID (e.g. Open Library work key)
    title = db.Column(db.String(256))
    author = db.Column(db.String(256))
    cover_url = db.Column(db.String(512))
    description = db.Column(db.Text)
    is_viewed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    viewed_at = db.Column(db.DateTime, nullable=True)

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256), nullable=False)
    icon = db.Column(db.String(64), nullable=False) # emoji or class name
    category = db.Column(db.String(32), nullable=False) # 'Learning', 'Consistency', 'Exploration'
    condition = db.Column(db.String(128)) # A helpful identifier for logic

class UserBadge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    badge_id = db.Column(db.Integer, db.ForeignKey('badge.id'), nullable=False)
    date_earned = db.Column(db.DateTime, default=datetime.utcnow)
    badge = db.relationship('Badge', backref='awarded_to')

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action_type = db.Column(db.String(64), nullable=False) # 'ai_chat', 'quiz_completed', 'note_upload', 'visual_tool', 'general_study'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
