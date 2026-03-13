from app import create_app, db
from app.models import User, Topic, UserProgress, Quiz
import json

app = create_app()


def seed_demo_data():
    """
    Lightweight demo seed so the dashboards and quiz system are immediately testable.
    Only runs on an empty database (no users).
    """
    if User.query.first():
        return

    # Demo teacher and student
    teacher = User(username="demo_teacher", email="teacher@example.com", role="teacher")
    teacher.set_password("password")
    student = User(username="demo_student", email="student@example.com", role="student")
    student.set_password("password")

    db.session.add_all([teacher, student])
    db.session.commit()

    # A couple of topics and basic progress
    topics = [
        Topic(name="Operating Systems", description="Processes, scheduling, deadlocks"),
        Topic(name="Databases", description="Relational models and normalization"),
    ]
    db.session.add_all(topics)
    db.session.commit()

    os_topic = Topic.query.filter_by(name="Operating Systems").first()
    db.session.add_all([
        UserProgress(user_id=student.id, topic_id=os_topic.id, score=72),
    ])
    db.session.commit()

    # Simple sample quiz that can be accessed via code 12345678
    questions = [
        {
            "question": "In an operating system, a deadlock is best described as:",
            "options": [
                "A condition where processes wait indefinitely for resources held by each other",
                "A crash of the operating system kernel",
                "A type of file system corruption",
                "A user logging out unexpectedly",
            ],
            "correct_index": 0,
            "type": "mcq",
            "topic": "OS Deadlocks",
            "difficulty": "easy",
        },
        {
            "question": "Which of the following is NOT a necessary condition for deadlock?",
            "options": [
                "Mutual exclusion",
                "Hold and wait",
                "No preemption",
                "Round-robin scheduling",
            ],
            "correct_index": 3,
            "type": "mcq",
            "topic": "OS Deadlocks",
            "difficulty": "easy",
        },
    ]

    quiz = Quiz(
        teacher_id=teacher.id,
        title="Sample Deadlocks Quiz",
        questions_json=json.dumps(questions),
        timer_minutes=10,
        code="12345678",
        is_active=True,
        source_type="topic",
        topic="Operating System – Deadlock",
        difficulty="easy",
        num_questions=len(questions),
        question_types="mcq",
    )
    db.session.add(quiz)
    db.session.commit()


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Topic': Topic, 'UserProgress': UserProgress}

if __name__ == '__main__':
    with app.app_context():
        # Tables and schema are ensured in create_app(); keep seed here.
        seed_demo_data()
        
        # Pre-populate static Gamification badges
        from app.services.gamification_service import seed_badges
        try:
            seed_badges()
        except Exception as e:
            print(f"Warning: Failed to seed badges: {e}")

    app.run(debug=True, port=5000)
