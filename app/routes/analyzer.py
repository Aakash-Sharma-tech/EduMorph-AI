from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app.services.pdf_service import analyze_exam_papers, optimize_syllabi, extract_text_from_files, analyze_pyq_schedule
from app import db
from app.models import AnalyzeQuizAttempt
from app.services.gamification_service import log_activity
import json

analyzer_bp = Blueprint('analyzer', __name__)

@analyzer_bp.route('/analyzer')
@login_required
def index():
    return render_template('analyzer.html')
    
@analyzer_bp.route('/api/analyze-exams', methods=['POST'])
@login_required
def api_analyze_exams():
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'No files provided'}), 400
        
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'success': False, 'message': 'No files selected'}), 400
        
    result = analyze_exam_papers(files)
    
    gamification = log_activity(current_user, 'upload')
    if isinstance(result, dict):
        result['gamification'] = gamification
        
    return jsonify(result)

@analyzer_bp.route('/api/optimize-syllabi', methods=['POST'])
@login_required
def api_optimize_syllabi():
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'No files provided'}), 400
        
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'success': False, 'message': 'No files selected'}), 400
        
    result = optimize_syllabi(files)
    
    gamification = log_activity(current_user, 'upload')
    if isinstance(result, dict):
        result['gamification'] = gamification
        
    return jsonify(result)

@analyzer_bp.route('/api/generate-pyq-schedule', methods=['POST'])
@login_required
def api_generate_pyq_schedule():
    if 'files' not in request.files:
        return jsonify({'success': False, 'message': 'No files provided'}), 400
        
    duration_days = request.form.get("duration", "15")
    try:
        duration_days = int(duration_days)
    except ValueError:
        duration_days = 15
        
    files = request.files.getlist('files')
    if not files or files[0].filename == '':
        return jsonify({'success': False, 'message': 'No files selected'}), 400
        
    result = analyze_pyq_schedule(files, duration_days)
    
    gamification = log_activity(current_user, 'upload')
    if isinstance(result, dict):
        result['gamification'] = gamification
        
    return jsonify(result)

@analyzer_bp.route('/api/generate-quiz', methods=['POST'])
@login_required
def api_generate_quiz():
    """
    Generate a self-study quiz in Analyze → Quiz with two modes:
    - mode='topic' : JSON body with topic and config
    - mode='pdf'   : multipart form-data with uploaded notes and config
    """
    mode = None
    topic = None
    num_questions = 5
    difficulty = "medium"
    duration_minutes = 10
    source_name = ""

    if request.content_type and request.content_type.startswith("application/json"):
        data = request.get_json() or {}
        mode = data.get("mode", "topic")
        topic = (data.get("topic") or "").strip()
        num_questions = int(data.get("num_questions") or 5)
        difficulty = (data.get("difficulty") or "medium").lower()
        duration_minutes = int(data.get("duration_minutes") or 10)
    else:
        # Assume multipart form-data
        mode = request.form.get("mode", "pdf")
        topic = (request.form.get("topic") or "").strip()
        num_questions = int(request.form.get("num_questions", 5))
        difficulty = (request.form.get("difficulty") or "medium").lower()
        duration_minutes = int(request.form.get("duration_minutes", 10))

    if difficulty not in ["easy", "medium", "hard"]:
        difficulty = "medium"

    from app.services.ai_engine import generate_quiz_from_topic, generate_quiz_from_notes

    try:
        if mode == "topic":
            if not topic:
                return jsonify({"success": False, "message": "Topic is required for topic-based quiz generation."}), 400

            questions = generate_quiz_from_topic(
                topic=topic,
                num_questions=num_questions,
                difficulty=difficulty,
                question_types=["mcq"]
            )
            source_name = topic
            quiz_type = "topic"

        elif mode == "pdf":
            if "files" not in request.files:
                return jsonify({"success": False, "message": "Please upload at least one notes file (PDF or TXT)."}), 400
            files = request.files.getlist("files")
            if not files or files[0].filename == "":
                return jsonify({"success": False, "message": "No files selected"}), 400

            text = extract_text_from_files(files)
            if not text:
                return jsonify({"success": False, "message": "Failed to extract text from notes (supported: PDF, TXT) or files are empty."}), 400

            questions = generate_quiz_from_notes(
                notes_text=text,
                num_questions=num_questions,
                difficulty=difficulty,
                question_types=["mcq"]
            )
            source_name = ", ".join([f.filename for f in files if getattr(f, "filename", "")])
            quiz_type = "pdf"
        else:
            return jsonify({"success": False, "message": "Invalid mode for quiz generation."}), 400

        quiz_payload = {
            "mode": quiz_type,
            "topic": topic if quiz_type == "topic" else "",
            "source_name": source_name,
            "difficulty": difficulty,
            "num_questions": len(questions),
            "duration_minutes": duration_minutes,
            "questions": questions,
        }
        return jsonify({"success": True, "quiz": quiz_payload})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error generating quiz: {str(e)}"}), 500


@analyzer_bp.route('/api/analyzer-quiz-submit', methods=['POST'])
@login_required
def api_analyzer_quiz_submit():
    """
    Evaluate a self-study quiz attempt, compute weak topics, and persist attempt.
    Expects JSON:
    {
      "quiz": { ... quiz metadata and questions ... },
      "answers": { "0": 1, "1": 2, ... },
      "time_taken_seconds": 123
    }
    """
    data = request.get_json() or {}
    quiz = data.get("quiz") or {}
    answers = data.get("answers") or {}
    time_taken_seconds = data.get("time_taken_seconds")

    questions = quiz.get("questions") or []
    if not questions:
        return jsonify({"success": False, "message": "Quiz questions missing."}), 400

    score = 0
    total = len(questions)
    question_results = []
    topic_stats = {}

    for idx, q in enumerate(questions):
        options = q.get("options") or []
        correct_idx = q.get("correct_index")
        chosen_raw = answers.get(str(idx))
        chosen_idx = None
        try:
            if chosen_raw is not None:
                chosen_idx = int(chosen_raw)
        except Exception:
            chosen_idx = None

        correct = False
        if correct_idx is not None and chosen_idx is not None:
            try:
                correct = int(correct_idx) == chosen_idx
            except Exception:
                correct = False

        if correct:
            score += 1

        topic_label = q.get("topic") or "General"
        if topic_label not in topic_stats:
            topic_stats[topic_label] = {"correct": 0, "wrong": 0}
        if correct:
            topic_stats[topic_label]["correct"] += 1
        else:
            topic_stats[topic_label]["wrong"] += 1

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

        question_results.append({
            "index": idx,
            "question": q.get("question"),
            "options": options,
            "chosen_index": chosen_idx,
            "correct_index": correct_idx,
            "chosen_option": chosen_option,
            "correct_option": correct_option,
            "correct": correct,
            "topic": topic_label,
            "difficulty": q.get("difficulty"),
            "explanation": q.get("explanation") or ""
        })

    # Identify weak topics: those with more wrong than correct, sorted by wrong desc
    weak_topics_summary = []
    for topic_label, stat in topic_stats.items():
        total_attempts = stat["correct"] + stat["wrong"]
        wrong = stat["wrong"]
        if total_attempts == 0:
            continue
        if wrong > 0:
            weak_topics_summary.append({
                "topic": topic_label,
                "wrong": wrong,
                "correct": stat["correct"],
                "total": total_attempts
            })
    weak_topics_summary.sort(key=lambda t: t["wrong"], reverse=True)

    try:
        attempt = AnalyzeQuizAttempt(
            user_id=current_user.id,
            quiz_type=quiz.get("mode"),
            topic_label=quiz.get("topic") or "",
            source_name=quiz.get("source_name") or "",
            difficulty=quiz.get("difficulty") or "",
            num_questions=quiz.get("num_questions") or total,
            duration_seconds=int(quiz.get("duration_minutes") or 0) * 60,
            score=score,
            total_questions=total,
            time_taken_seconds=int(time_taken_seconds or 0),
            weak_topics_json=json.dumps(weak_topics_summary),
            questions_json=json.dumps(questions),
            answers_json=json.dumps(answers),
        )
        db.session.add(attempt)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"Error saving quiz attempt: {str(e)}"}), 500

    gamification = log_activity(current_user, 'quiz_completed')

    return jsonify({
        "success": True,
        "score": score,
        "total": total,
        "time_taken_seconds": time_taken_seconds,
        "weak_topics": weak_topics_summary,
        "questions": question_results,
        "gamification": gamification
    })
