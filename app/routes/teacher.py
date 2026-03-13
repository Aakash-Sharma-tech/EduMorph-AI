from flask import Blueprint, render_template, request, jsonify, redirect, url_for, Response
from flask_login import login_required, current_user
from app.models import User, UserProgress, Quiz, QuizResult, Topic, StudyPlan
from app import db
import json
import random
from functools import wraps

teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'teacher':
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function

@teacher_bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    return render_template('teacher_dashboard.html')

@teacher_bp.route('/api/students-progress')
@login_required
@teacher_required
def api_students_progress():
    progress_records = UserProgress.query.join(User).join(Topic).all()
    data = []
    for p in progress_records:
        data.append({
            'student_name': p.student.username,
            'topic': p.topic.name,
            'score': p.score
        })
    return jsonify({'success': True, 'data': data})

@teacher_bp.route('/api/results')
@login_required
@teacher_required
def api_all_results():
    results = QuizResult.query.all()
    # Need to enrich with student and quiz names
    data = []
    for r in results:
        data.append({
            'id': r.id,
            'student_name': r.student.username,
            'quiz_title': r.quiz.title,
            'score': r.score,
            'total': r.total_questions,
            'feedback': r.teacher_feedback,
            'submitted_at': r.submitted_at.strftime('%Y-%m-%d %H:%M'),
            'violation_count': r.violation_count,
            'violation_logs': json.loads(r.violation_logs) if r.violation_logs else []
        })
    return jsonify({'success': True, 'data': data})

@teacher_bp.route('/api/badges/analytics')
@login_required
@teacher_required
def api_badge_analytics():
    from app.models import Badge, UserBadge, User
    badges = Badge.query.all()
    data = []
    
    for badge in badges:
        # Find all users who earned this badge
        user_badges = getattr(badge, 'awarded_to', [])
        student_names = []
        for ub in user_badges:
            student = User.query.get(ub.user_id)
            if student:
                student_names.append(student.username)
                
        data.append({
            'badge_id': badge.id,
            'name': badge.name,
            'description': badge.description,
            'icon': badge.icon,
            'category': badge.category,
            'students': student_names
        })
        
    return jsonify({'success': True, 'data': data})

@teacher_bp.route('/api/results/<int:result_id>/feedback', methods=['POST'])
@login_required
@teacher_required
def api_result_feedback(result_id):
    data = request.json
    feedback = data.get('feedback')
    if not feedback:
        return jsonify({'success': False, 'message': 'Feedback is required'}), 400
        
    result = QuizResult.query.get(result_id)
    if not result:
        return jsonify({'success': False, 'message': 'Result not found'}), 404
        
    result.teacher_feedback = feedback
    db.session.commit()

    # Update or (re)generate a personalized study plan for this quiz attempt
    try:
        quiz = result.quiz
        if quiz and quiz.questions_json:
            questions = json.loads(quiz.questions_json)
        else:
            questions = []

        user_answers = {}
        if result.answers_json:
            try:
                user_answers = json.loads(result.answers_json)
            except Exception:
                user_answers = {}

        question_breakdown = []
        for idx, q in enumerate(questions):
            options = q.get("options", [])
            correct_idx = q.get("correct_index")
            chosen_raw = user_answers.get(str(idx))
            chosen_idx = None
            try:
                if chosen_raw is not None:
                    chosen_idx = int(chosen_raw)
            except Exception:
                chosen_idx = None

            chosen_option = (
                options[chosen_idx]
                if options and chosen_idx is not None and 0 <= chosen_idx < len(options)
                else None
            )
            correct_option = (
                options[correct_idx]
                if options and correct_idx is not None and 0 <= correct_idx < len(options)
                else None
            )

            question_breakdown.append(
                {
                    "question": q.get("question"),
                    "topic": q.get("topic"),
                    "type": q.get("type"),
                    "was_correct": chosen_idx is not None and correct_idx is not None and chosen_idx == int(correct_idx),
                    "chosen_option": chosen_option,
                    "correct_option": correct_option,
                }
            )

        from app.services.ai_engine import generate_study_plan

        recommendations = generate_study_plan(
            quiz, result, question_breakdown, teacher_feedback=feedback
        )
        if recommendations:
            plan = StudyPlan.query.filter_by(
                quiz_result_id=result.id, student_id=result.student_id
            ).first()
            if not plan:
                plan = StudyPlan(
                    student_id=result.student_id,
                    quiz_result_id=result.id,
                    recommendations_json=json.dumps(recommendations),
                )
                db.session.add(plan)
            else:
                plan.recommendations_json = json.dumps(recommendations)
            db.session.commit()
    except Exception as e:
        # Do not block feedback saving if study plan generation fails
        print(f"Error generating study plan from teacher feedback: {e}")

    return jsonify({'success': True, 'message': 'Feedback saved!'})


def _generate_unique_quiz_code():
    """Generate a unique 8-digit numeric code for quizzes."""
    while True:
        code = "".join(random.choices("0123456789", k=8))
        if not Quiz.query.filter_by(code=code).first():
            return code

@teacher_bp.route('/api/generate-quiz', methods=['POST'])
@login_required
@teacher_required
def generate_class_quiz():
    """
    Generate a quiz in two modes:
    - From uploaded notes (PDF)  -> mode='notes'
    - From a topic name          -> mode='topic'

    Teachers can also choose duration, number of questions, difficulty, and question types.
    The quiz is saved in the database with an 8-digit code and remains inactive until published.
    """
    mode = request.form.get('mode', 'notes')  # 'notes' or 'topic'
    title = request.form.get('title', 'Untitled Quiz')
    timer_minutes = int(request.form.get('timer', 15))
    num_questions = int(request.form.get('num_questions', 5))
    difficulty = request.form.get('difficulty', 'medium').lower()
    question_types_raw = request.form.get('question_types', 'mcq')
    question_types = [q.strip().lower() for q in question_types_raw.split(',') if q.strip()]

    if difficulty not in ['easy', 'medium', 'hard']:
        difficulty = 'medium'

    # Normalize question types
    allowed_types = {'mcq', 'true_false', 'short_answer'}
    question_types = [qt for qt in question_types if qt in allowed_types] or ['mcq']

    try:
        from app.services.ai_engine import generate_quiz_from_notes, generate_quiz_from_topic
        from app.services.pdf_service import extract_text_from_files

        if mode == 'notes':
            if 'files' not in request.files:
                return jsonify({'success': False, 'message': 'Please upload at least one notes file (PDF or TXT).'}), 400
            files = request.files.getlist('files')
            if not files or files[0].filename == '':
                return jsonify({'success': False, 'message': 'No files selected'}), 400

            text = extract_text_from_files(files)
            if not text:
                return jsonify({'success': False, 'message': 'Failed to extract text from notes (supported: PDF, TXT) or files are empty.'}), 400

            questions = generate_quiz_from_notes(
                notes_text=text,
                num_questions=num_questions,
                difficulty=difficulty,
                question_types=question_types
            )
            source_type = 'notes'
            topic_label = request.form.get('topic') or ''

        elif mode == 'topic':
            topic_label = request.form.get('topic', '').strip()
            if not topic_label:
                return jsonify({'success': False, 'message': 'Topic name is required for topic-based quiz generation.'}), 400

            questions = generate_quiz_from_topic(
                topic=topic_label,
                num_questions=num_questions,
                difficulty=difficulty,
                question_types=question_types
            )
            source_type = 'topic'
        else:
            return jsonify({'success': False, 'message': 'Invalid generation mode.'}), 400

        # Persist quiz with inactive status and unique 8-digit code
        new_quiz = Quiz(
            teacher_id=current_user.id,
            title=title,
            questions_json=json.dumps(questions),
            timer_minutes=timer_minutes,
            source_type=source_type,
            topic=topic_label,
            difficulty=difficulty,
            num_questions=len(questions),
            question_types=",".join(question_types),
            is_active=False,
            code=_generate_unique_quiz_code()
        )
        db.session.add(new_quiz)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Quiz generated and saved successfully! Review and publish from the Quiz Management panel.",
            "quiz": {
                "id": new_quiz.id,
                "title": new_quiz.title,
                "code": new_quiz.code,
                "is_active": new_quiz.is_active,
                "timer_minutes": new_quiz.timer_minutes,
                "num_questions": new_quiz.num_questions,
                "difficulty": new_quiz.difficulty,
                "source_type": new_quiz.source_type,
                "topic": new_quiz.topic
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Error generating quiz: {str(e)}"}), 500


@teacher_bp.route('/api/quizzes', methods=['GET'])
@login_required
@teacher_required
def api_teacher_quizzes():
    """List all quizzes created by the current teacher with high-level stats."""
    quizzes = Quiz.query.filter_by(teacher_id=current_user.id).order_by(Quiz.created_at.desc()).all()
    data = []
    for q in quizzes:
        attempts = q.results.all()
        total_attempts = len(attempts)
        avg_pct = None
        if total_attempts:
            percentages = []
            for r in attempts:
                if r.total_questions:
                    percentages.append((r.score / r.total_questions) * 100.0)
            if percentages:
                avg_pct = sum(percentages) / len(percentages)

        data.append({
            "id": q.id,
            "title": q.title,
            "code": q.code,
            "is_active": bool(q.is_active),
            "timer_minutes": q.timer_minutes,
            "num_questions": q.num_questions,
            "difficulty": q.difficulty,
            "source_type": q.source_type,
            "topic": q.topic,
            "created_at": q.created_at.strftime('%Y-%m-%d %H:%M'),
            "attempt_count": total_attempts,
            "average_percentage": round(avg_pct, 2) if avg_pct is not None else None
        })

    return jsonify({"success": True, "data": data})


@teacher_bp.route('/api/quizzes/<int:quiz_id>', methods=['GET'])
@login_required
@teacher_required
def api_quiz_detail(quiz_id):
    """Detailed quiz view with questions, attempts, and per-question performance."""
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.id:
        return jsonify({"success": False, "message": "Not authorized to view this quiz."}), 403

    try:
        questions = json.loads(quiz.questions_json or "[]")
    except Exception:
        questions = []

    attempts = quiz.results.order_by(QuizResult.submitted_at.desc()).all()

    attempts_payload = []
    per_question_stats = [{"correct": 0, "wrong": 0} for _ in questions]

    for r in attempts:
        answers = {}
        if r.answers_json:
            try:
                answers = json.loads(r.answers_json)
            except Exception:
                answers = {}

        percentage = 0.0
        if r.total_questions:
            percentage = (r.score / r.total_questions) * 100.0

        # Build per-question stats
        for idx, q in enumerate(questions):
            correct_idx = q.get("correct_index")
            chosen_raw = answers.get(str(idx))
            chosen_idx = None
            try:
                if chosen_raw is not None:
                    chosen_idx = int(chosen_raw)
            except Exception:
                chosen_idx = None

            if correct_idx is not None and chosen_idx is not None:
                if int(correct_idx) == chosen_idx:
                    per_question_stats[idx]["correct"] += 1
                else:
                    per_question_stats[idx]["wrong"] += 1

        attempts_payload.append({
            "id": r.id,
            "student_name": r.student.username,
            "score": r.score,
            "total": r.total_questions,
            "percentage": round(percentage, 2),
            "time_taken_seconds": r.time_taken_seconds,
            "submitted_at": r.submitted_at.strftime('%Y-%m-%d %H:%M'),
            "teacher_feedback": r.teacher_feedback,
            "violation_count": r.violation_count,
            "violation_logs": json.loads(r.violation_logs) if r.violation_logs else []
        })

    questions_payload = []
    for idx, q in enumerate(questions):
        stats = per_question_stats[idx] if idx < len(per_question_stats) else {"correct": 0, "wrong": 0}
        total_attempts = stats["correct"] + stats["wrong"]
        correct_pct = (stats["correct"] / total_attempts) * 100.0 if total_attempts else None
        questions_payload.append({
            "index": idx,
            "question": q.get("question"),
            "options": q.get("options", []),
            "correct_index": q.get("correct_index"),
            "type": q.get("type"),
            "topic": q.get("topic"),
            "difficulty": q.get("difficulty"),
            "correct_count": stats["correct"],
            "wrong_count": stats["wrong"],
            "correct_pct": round(correct_pct, 2) if correct_pct is not None else None
        })

    return jsonify({
        "success": True,
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "code": quiz.code,
            "is_active": bool(quiz.is_active),
            "timer_minutes": quiz.timer_minutes,
            "num_questions": quiz.num_questions,
            "difficulty": quiz.difficulty,
            "source_type": quiz.source_type,
            "topic": quiz.topic,
            "created_at": quiz.created_at.strftime('%Y-%m-%d %H:%M'),
            "questions": questions_payload
        },
        "attempts": attempts_payload
    })


@teacher_bp.route('/api/quizzes/<int:quiz_id>/publish', methods=['POST'])
@login_required
@teacher_required
def api_quiz_publish(quiz_id):
    """Publish or unpublish a quiz (toggle is_active)."""
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.id:
        return jsonify({"success": False, "message": "Not authorized to publish this quiz."}), 403

    data = request.json or {}
    is_active = data.get("is_active", True)
    quiz.is_active = bool(is_active)
    if not quiz.code:
        quiz.code = _generate_unique_quiz_code()
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Quiz status updated.",
        "quiz": {
            "id": quiz.id,
            "code": quiz.code,
            "is_active": quiz.is_active
        }
    })


@teacher_bp.route('/api/quizzes/<int:quiz_id>/update', methods=['POST'])
@login_required
@teacher_required
def api_quiz_update(quiz_id):
    """Update quiz metadata and full question set."""
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.id:
        return jsonify({"success": False, "message": "Not authorized to edit this quiz."}), 403

    data = request.json or {}

    title = data.get("title")
    if title:
        quiz.title = title

    timer_minutes = data.get("timer_minutes")
    if timer_minutes is not None:
        try:
            quiz.timer_minutes = int(timer_minutes)
        except Exception:
            pass

    difficulty = data.get("difficulty")
    if difficulty:
        quiz.difficulty = difficulty

    topic_label = data.get("topic")
    if topic_label is not None:
        quiz.topic = topic_label

    questions = data.get("questions")
    if questions is not None:
        try:
            quiz.questions_json = json.dumps(questions)
            quiz.num_questions = len(questions)
        except Exception as e:
            return jsonify({"success": False, "message": f"Invalid questions payload: {e}"}), 400

    db.session.commit()

    return jsonify({"success": True, "message": "Quiz updated successfully."})


@teacher_bp.route('/api/quizzes/<int:quiz_id>/report.csv', methods=['GET'])
@login_required
@teacher_required
def api_quiz_report_csv(quiz_id):
    """Download a CSV report for a quiz's attempts."""
    quiz = Quiz.query.get_or_404(quiz_id)
    if quiz.teacher_id != current_user.id:
        return jsonify({"success": False, "message": "Not authorized to export this quiz."}), 403

    rows = ["Student,Score,Total,Percentage,Time Taken (seconds),Submitted At,Teacher Feedback"]
    for r in quiz.results.order_by(QuizResult.submitted_at.asc()).all():
        if r.total_questions:
            pct = (r.score / r.total_questions) * 100.0
        else:
            pct = 0.0
        rows.append(
            f"{r.student.username},{r.score},{r.total_questions},{pct:.2f},{r.time_taken_seconds or ''},{r.submitted_at.strftime('%Y-%m-%d %H:%M')},{(r.teacher_feedback or '').replace(',', ' ')}"
        )

    csv_content = "\n".join(rows)
    filename = f"quiz_{quiz.id}_report.csv"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
