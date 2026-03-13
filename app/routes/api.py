from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from app.models import UserProgress, Topic, Quiz, QuizResult, SavedMessage, StudyPlan, BookRecommendation
from app import db
from app.services.ai_engine import get_ai_response, get_code_review, generate_study_plan
from app.services.gamification_service import log_activity
from app.services.ranking_service import update_student_score

api_bp = Blueprint('api', __name__)

@api_bp.route('/stats')
@login_required
def get_stats():
    progress = UserProgress.query.filter_by(user_id=current_user.id).all()
    data = []
    for p in progress:
        data.append({
            'topic': p.topic.name,
            'score': p.score
        })
    # If no data, provide mock data for demonstrate MVP UI
    if not data:
        data = [
            {'topic': 'Algebra', 'score': 75},
            {'topic': 'Calculus', 'score': 45},
            {'topic': 'Physics', 'score': 80},
            {'topic': 'Chemistry', 'score': 60}
        ]
    return jsonify({'success': True, 'data': data})

@api_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({'success': False, 'message': 'Missing message content'}), 400
        
    user_message = data['message']
    chat_history = data.get('history', [])
    
    ai_reply = get_ai_response(user_message, chat_history)
    gamification = log_activity(current_user, 'ai_chat')
    
    return jsonify({
        'success': True, 
        'reply': ai_reply,
        'gamification': gamification
    })

@api_bp.route('/sandbox', methods=['GET'])
@login_required
def sandbox():
    # This route now serves the Book Recommendation dashboard instead of the legacy code sandbox.
    return render_template('sandbox.html')

@api_bp.route('/code-review', methods=['POST'])
@login_required
def api_code_review():
    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'python')
    output = data.get('output', '')
    had_error = data.get('had_error', False)
    
    from app.services.ai_engine import get_code_review
    review = get_code_review(code, language, output, had_error)
    return jsonify({'success': True, 'review': review})

@api_bp.route('/messages/save', methods=['POST'])
@login_required
def api_save_message():
    data = request.json
    content = data.get('content')
    if not content:
        return jsonify({'success': False, 'message': 'No content provided'}), 400
        
    from app.models import SavedMessage
    msg = SavedMessage(user_id=current_user.id, content=content)
    db.session.add(msg)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Message starred!'})


@api_bp.route('/messages/unstar', methods=['POST'])
@login_required
def api_unstar_message():
    """
    Remove starred explanation(s) for the current user that match the given content.
    This is content-based for simplicity; in practice you might use explicit IDs.
    """
    data = request.json
    msg_id = data.get('id')
    content = data.get('content')
    if not msg_id and not content:
        return jsonify({'success': False, 'message': 'No identifier provided'}), 400

    from app.models import SavedMessage
    try:
        query = SavedMessage.query.filter_by(user_id=current_user.id)
        if msg_id:
            query = query.filter_by(id=msg_id)
        elif content:
            query = query.filter_by(content=content)
        deleted = query.delete(synchronize_session=False)
        db.session.commit()
        if not deleted:
            return jsonify({'success': False, 'message': 'Nothing to unstar.'}), 404
        return jsonify({'success': True, 'message': 'Message unstarred and removed.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/dashboard-data')
@login_required
def api_dashboard_data():
    import json
    from app.models import AnalyzeQuizAttempt

    msgs = SavedMessage.query.filter_by(user_id=current_user.id).order_by(SavedMessage.timestamp.desc()).all()
    saved = [{'id': m.id, 'content': m.content, 'timestamp': m.timestamp.strftime('%Y-%m-%d %H:%M')} for m in msgs]
    
    # Identify quizzes the student has NOT taken yet
    all_quizzes = Quiz.query.order_by(Quiz.created_at.desc()).all()
    taken_ids = [r.quiz_id for r in QuizResult.query.filter_by(student_id=current_user.id).all()]

    quizzes = []
    for q in all_quizzes:
        # Legacy behaviour: auto-deploy quizzes without codes.
        if q.id in taken_ids:
            continue
        if q.code:  # code-based quizzes are joined via quiz code, not auto-pushed
            continue
        # If is_active is unset (legacy), treat as active by default
        is_active = q.is_active if hasattr(q, "is_active") else True
        if not is_active:
            continue
        try:
            qs = json.loads(q.questions_json)
            sanitized_qs = [{'question': qst['question'], 'options': qst['options']} for qst in qs]
            quizzes.append({
                'id': q.id,
                'title': q.title,
                'timer_minutes': q.timer_minutes,
                'questions': sanitized_qs
            })
        except Exception:
            pass

    # Student's own quiz results for dashboard result section
    my_results = QuizResult.query.filter_by(student_id=current_user.id).order_by(QuizResult.submitted_at.desc()).all()
    results_payload = []
    teacher_attempts = []
    for r in my_results:
        percentage = 0.0
        if r.total_questions:
            percentage = (r.score / r.total_questions) * 100.0
        label = r.quiz.title if r.quiz else "Quiz"
        topic_label = getattr(r.quiz, "topic", None) or label
        results_payload.append({
            "id": r.id,
            "quiz_title": label,
            "score": r.score,
            "total": r.total_questions,
            "percentage": round(percentage, 2),
            "time_taken_seconds": r.time_taken_seconds,
            "submitted_at": r.submitted_at.strftime('%Y-%m-%d %H:%M'),
            "teacher_feedback": r.teacher_feedback
        })
        teacher_attempts.append({
            "source": "teacher",
            "label": label,
            "topic": topic_label,
            "score": r.score,
            "total": r.total_questions,
            "percentage": percentage,
            "timestamp": r.submitted_at
        })

    # Self-study Analyze quiz attempts
    analyze_attempts_qs = AnalyzeQuizAttempt.query.filter_by(user_id=current_user.id).order_by(AnalyzeQuizAttempt.created_at.desc()).all()
    analyze_attempts = []
    for a in analyze_attempts_qs:
        pct = 0.0
        if a.total_questions:
            pct = (a.score / a.total_questions) * 100.0
        label = a.topic_label or a.source_name or "Self-Study Quiz"
        analyze_attempts.append({
            "source": "self",
            "label": label,
            "topic": a.topic_label or label,
            "score": a.score,
            "total": a.total_questions,
            "percentage": pct,
            "timestamp": a.created_at
        })

    # Aggregate performance
    all_attempts = teacher_attempts + analyze_attempts
    all_attempts_sorted = sorted(all_attempts, key=lambda x: x["timestamp"])

    total_quizzes = len(all_attempts_sorted)

    # Recent scores (last 5 attempts, newest first)
    recent_scores = []
    for att in reversed(all_attempts_sorted[-5:]):
        recent_scores.append({
            "label": att["label"],
            "source": att["source"],
            "percentage": round(att["percentage"], 2) if att["total"] else 0.0,
            "score": att["score"],
            "total": att["total"],
            "topic": att["topic"],
            "timestamp": att["timestamp"].strftime("%Y-%m-%d")
        })

    # Topic-wise accuracy and weak topics
    topic_stats = {}

    # From teacher quizzes: treat each quiz as a topic
    for att in teacher_attempts:
        topic_label = att["topic"] or "General"
        stat = topic_stats.setdefault(topic_label, {"correct": 0, "wrong": 0})
        stat["correct"] += att["score"]
        stat["wrong"] += max(att["total"] - att["score"], 0)

    # From self-study attempts: approximate topic using topic_label and score
    for att in analyze_attempts:
        topic_label = att["topic"] or "Self-Study"
        stat = topic_stats.setdefault(topic_label, {"correct": 0, "wrong": 0})
        stat["correct"] += att["score"]
        stat["wrong"] += max(att["total"] - att["score"], 0)

    topic_accuracy = []
    weak_topics = []
    for topic_label, stat in topic_stats.items():
        total = stat["correct"] + stat["wrong"]
        if total <= 0:
            continue
        accuracy = (stat["correct"] / total) * 100.0
        entry = {
            "topic": topic_label,
            "correct": stat["correct"],
            "wrong": stat["wrong"],
            "total": total,
            "accuracy_pct": round(accuracy, 1)
        }
        topic_accuracy.append(entry)
        if stat["wrong"] > 0:
            weak_topics.append(entry)

    weak_topics_sorted = sorted(weak_topics, key=lambda e: e["accuracy_pct"])

    # Improvement trend: chronological percentages across all attempts (last 8)
    trend = []
    for idx, att in enumerate(all_attempts_sorted[-8:]):
        trend.append({
            "label": f"#{len(all_attempts_sorted)-len(all_attempts_sorted[-8:])+idx+1}",
            "percentage": round(att["percentage"], 2) if att["total"] else 0.0
        })

    performance_summary = {
        "total_quizzes": total_quizzes,
        "recent_scores": recent_scores,
        "topic_accuracy": topic_accuracy,
        "weak_topics": weak_topics_sorted[:5],
        "trend": trend
    }

    # Study plans / recommendations
    study_plans = StudyPlan.query.filter_by(student_id=current_user.id).order_by(StudyPlan.created_at.desc()).all()
    study_plans_payload = []
    for sp in study_plans:
        try:
            recs = json.loads(sp.recommendations_json)
        except Exception:
            recs = []
        study_plans_payload.append({
            "id": sp.id,
            "created_at": sp.created_at.strftime('%Y-%m-%d %H:%M'),
            "recommendations": recs
        })

    # Gamification section for dashboard
    from app.services.gamification_service import get_ai_motivation, get_next_streak_milestone
    
    unlocked_badges_qs = current_user.earned_badges.order_by(db.text('date_earned DESC')).all()
    unlocked_badges = []
    for ub in unlocked_badges_qs:
        unlocked_badges.append({
            'name': ub.badge.name,
            'description': ub.badge.description,
            'icon': ub.badge.icon,
            'category': ub.badge.category,
            'date_earned': ub.date_earned.strftime('%Y-%m-%d')
        })

    gamification_data = {
        'current_streak': current_user.current_streak,
        'longest_streak': current_user.longest_streak,
        'next_milestone': get_next_streak_milestone(current_user.current_streak),
        'motivation_message': get_ai_motivation(current_user),
        'badges': unlocked_badges
    }

    return jsonify({
        'success': True,
        'saved_messages': saved,
        'quizzes': quizzes,
        'results': results_payload,
        'study_plans': study_plans_payload,
        'performance': performance_summary,
        'gamification': gamification_data
    })


@api_bp.route('/books/search', methods=['GET'])
@login_required
def api_books_search():
    """
    Search-based book recommendations for a given topic.
    """
    from app.services.book_service import search_books_by_topic

    query = (request.args.get('q') or "").strip()
    if not query:
        return jsonify({'success': False, 'message': 'Query parameter q is required.'}), 400

    books = search_books_by_topic(query, limit=8)

    # Persist as recommendations (source='search')
    for b in books:
        existing = BookRecommendation.query.filter_by(
            user_id=current_user.id,
            book_key=b["book_key"]
        ).first()
        if not existing:
            rec = BookRecommendation(
                user_id=current_user.id,
                source='search',
                topic=b.get("topic") or query,
                book_key=b.get("book_key") or "",
                title=b.get("title") or "",
                author=b.get("author") or "",
                cover_url=b.get("cover_url") or "",
                description=b.get("description") or ""
            )
            db.session.add(rec)
    db.session.commit()

    # Also include viewed flag for current user
    enriched = []
    for b in books:
        rec = BookRecommendation.query.filter_by(
            user_id=current_user.id,
            book_key=b["book_key"]
        ).order_by(BookRecommendation.created_at.desc()).first()
        enriched.append({
            **b,
            "id": rec.id if rec else None,
            "is_viewed": rec.is_viewed if rec else False
        })

    return jsonify({'success': True, 'books': enriched})


@api_bp.route('/books/performance', methods=['GET'])
@login_required
def api_books_from_performance():
    """
    Performance-based book recommendations using weak topics from the performance report.
    """
    import json
    from app.models import AnalyzeQuizAttempt
    from app.services.book_service import recommend_for_weak_topics
    from app.services.ai_engine import recommend_youtube_videos_for_topics

    # Build same performance summary as dashboard_data to get weak_topics
    my_results = QuizResult.query.filter_by(student_id=current_user.id).order_by(QuizResult.submitted_at.desc()).all()
    teacher_attempts = []
    for r in my_results:
        pct = 0.0
        if r.total_questions:
            pct = (r.score / r.total_questions) * 100.0
        label = r.quiz.title if r.quiz else "Quiz"
        topic_label = getattr(r.quiz, "topic", None) or label
        teacher_attempts.append({
            "topic": topic_label,
            "score": r.score,
            "total": r.total_questions
        })

    analyze_attempts_qs = AnalyzeQuizAttempt.query.filter_by(user_id=current_user.id).order_by(AnalyzeQuizAttempt.created_at.desc()).all()
    analyze_attempts = []
    for a in analyze_attempts_qs:
        analyze_attempts.append({
            "topic": a.topic_label or a.source_name or "Self-Study",
            "score": a.score,
            "total": a.total_questions
        })

    topic_stats = {}
    for att in teacher_attempts + analyze_attempts:
        topic_label = att["topic"] or "General"
        stat = topic_stats.setdefault(topic_label, {"correct": 0, "wrong": 0})
        stat["correct"] += att["score"]
        stat["wrong"] += max(att["total"] - att["score"], 0)

    weak_topics = []
    for topic_label, stat in topic_stats.items():
        total = stat["correct"] + stat["wrong"]
        if total <= 0:
            continue
        accuracy = (stat["correct"] / total) * 100.0
        if stat["wrong"] > 0:
            weak_topics.append({
                "topic": topic_label,
                "correct": stat["correct"],
                "wrong": stat["wrong"],
                "total": total,
                "accuracy_pct": round(accuracy, 1)
            })
    weak_topics_sorted = sorted(weak_topics, key=lambda e: e["accuracy_pct"])

    books = recommend_for_weak_topics(weak_topics_sorted[:5], per_topic_limit=2, overall_limit=12)

    # Videos grouped by topic via Gemini suggestions (no direct YouTube API)
    videos_by_topic = recommend_youtube_videos_for_topics(weak_topics_sorted[:5])

    # Persist as recommendations (source='performance')
    for b in books:
        existing = BookRecommendation.query.filter_by(
            user_id=current_user.id,
            book_key=b["book_key"]
        ).first()
        if not existing:
            rec = BookRecommendation(
                user_id=current_user.id,
                source='performance',
                topic=b.get("topic"),
                book_key=b.get("book_key") or "",
                title=b.get("title") or "",
                author=b.get("author") or "",
                cover_url=b.get("cover_url") or "",
                description=b.get("description") or ""
            )
            db.session.add(rec)
    db.session.commit()

    # Group books and videos by topic
    topic_groups = []
    for wt in weak_topics_sorted[:5]:
        topic_label = wt["topic"]
        topic_books = []
        for b in books:
            if b.get("topic") == topic_label:
                rec = BookRecommendation.query.filter_by(
                    user_id=current_user.id,
                    book_key=b["book_key"]
                ).order_by(BookRecommendation.created_at.desc()).first()
                topic_books.append({
                    **b,
                    "id": rec.id if rec else None,
                    "is_viewed": rec.is_viewed if rec else False
                })
        topic_videos = videos_by_topic.get(topic_label, [])
        topic_groups.append({
            "topic": topic_label,
            "accuracy_pct": wt["accuracy_pct"],
            "books": topic_books,
            "videos": topic_videos
        })

    # For backwards compatibility, still return flat books + weak_topics
    enriched_flat = []
    for b in books:
        rec = BookRecommendation.query.filter_by(
            user_id=current_user.id,
            book_key=b["book_key"]
        ).order_by(BookRecommendation.created_at.desc()).first()
        enriched_flat.append({
            **b,
            "id": rec.id if rec else None,
            "is_viewed": rec.is_viewed if rec else False
        })

    return jsonify({
        'success': True,
        'books': enriched_flat,
        'weak_topics': weak_topics_sorted[:5],
        'topics': topic_groups
    })


@api_bp.route('/books/mark-viewed', methods=['POST'])
@login_required
def api_book_mark_viewed():
    data = request.get_json() or {}
    rec_id = data.get("id")
    book_key = data.get("book_key")
    if not rec_id and not book_key:
        return jsonify({'success': False, 'message': 'Missing book identifier.'}), 400

    try:
        from datetime import datetime
        query = BookRecommendation.query.filter_by(user_id=current_user.id)
        if rec_id:
            query = query.filter_by(id=rec_id)
        elif book_key:
            query = query.filter_by(book_key=book_key)
        rec = query.first()
        if not rec:
            return jsonify({'success': False, 'message': 'Recommendation not found.'}), 404
        rec.is_viewed = True
        rec.viewed_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@api_bp.route('/submit-quiz', methods=['POST'])
@login_required
def api_submit_quiz():
    import json

    data = request.json
    quiz_id = data.get('quiz_id')
    user_answers = data.get('answers', {})
    time_taken_seconds = data.get('time_taken_seconds')
    violation_count = data.get('violation_count', 0)
    violation_logs = data.get('violation_logs', [])

    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return jsonify({'success': False, 'message': 'Quiz not found'}), 404

    try:
        questions = json.loads(quiz.questions_json)
        score = 0
        total = len(questions)
        question_breakdown = []

        for idx, q in enumerate(questions):
            chosen = user_answers.get(str(idx))
            correct_idx = q.get('correct_index')
            was_correct = False
            try:
                if chosen is not None and correct_idx is not None and int(chosen) == int(correct_idx):
                    was_correct = True
                    score += 1
            except Exception:
                was_correct = False

            options = q.get('options', [])
            chosen_idx = None
            try:
                if chosen is not None:
                    chosen_idx = int(chosen)
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
                    "was_correct": was_correct,
                    "chosen_option": chosen_option,
                    "correct_option": correct_option,
                }
            )

        time_taken_val = None
        try:
            if time_taken_seconds is not None:
                time_taken_val = int(time_taken_seconds)
        except Exception:
            time_taken_val = None

        res = QuizResult(
            quiz_id=quiz.id,
            student_id=current_user.id,
            score=score,
            total_questions=total,
            answers_json=json.dumps(user_answers),
            time_taken_seconds=time_taken_val,
            violation_count=violation_count,
            violation_logs=json.dumps(violation_logs) if violation_logs else None
        )
        db.session.add(res)
        db.session.commit()

        # Generate or refresh AI-powered study plan based on this attempt
        try:
            recommendations = generate_study_plan(quiz, res, question_breakdown)
            if recommendations:
                plan = StudyPlan(
                    student_id=current_user.id,
                    quiz_result_id=res.id,
                    recommendations_json=json.dumps(recommendations)
                )
                db.session.add(plan)
                db.session.commit()
        except Exception as e:
            # Do not fail submission if recommendations fail
            print(f"Error generating study plan after quiz submission: {e}")

        # Recalculate Rank & Average 
        update_student_score(current_user, score, total)

        gamification = log_activity(current_user, 'quiz_completed')

        return jsonify({
            'success': True, 
            'score': score, 
            'total': total,
            'gamification': gamification
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@api_bp.route('/quiz-by-code', methods=['POST'])
@login_required
def api_quiz_by_code():
    """
    Validate an 8-digit quiz code and return quiz details for the student to attempt.
    """
    data = request.json or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({'success': False, 'message': 'Quiz code is required.'}), 400

    quiz = Quiz.query.filter_by(code=code, is_active=True).first()
    if not quiz:
        return jsonify({'success': False, 'message': 'Invalid or inactive quiz code.'}), 404

    import json
    try:
        questions = json.loads(quiz.questions_json or "[]")
    except Exception:
        questions = []

    sanitized_questions = []
    for idx, q in enumerate(questions):
        sanitized_questions.append({
            "index": idx,
            "question": q.get("question"),
            "options": q.get("options", []),
            "type": q.get("type"),
        })

    return jsonify({
        "success": True,
        "quiz": {
            "id": quiz.id,
            "title": quiz.title,
            "code": quiz.code,
            "timer_minutes": quiz.timer_minutes,
            "num_questions": len(sanitized_questions),
            "difficulty": quiz.difficulty,
            "topic": quiz.topic,
            "questions": sanitized_questions
        }
    })

@api_bp.route('/leaderboard', methods=['GET'])
@login_required
def api_leaderboard():
    """
    Returns the top 10 ranked students globally and the current user's specific rank object.
    Only students with `calculated_rank` (meaning they took at least 1 test) are returned.
    """
    from app.models import User
    try:
        # Fetch Top 10 sorted ascending by their rank (1 is highest)
        top_10 = User.query.filter(User.calculated_rank.isnot(None), User.role == 'student')\
                           .order_by(User.calculated_rank.asc())\
                           .limit(10).all()
        
        leaderboard = []
        for u in top_10:
            leaderboard.append({
                "rank": u.calculated_rank,
                "username": u.username,
                "average_score": round(u.average_score, 1) if u.average_score else 0.0,
                "total_tests": u.total_tests_taken
            })
            
        # Get Current User Rank details
        current_rank_data = None
        if current_user.calculated_rank:
            current_rank_data = {
                "rank": current_user.calculated_rank,
                "username": current_user.username,
                "average_score": round(current_user.average_score, 1) if current_user.average_score else 0.0,
                "total_tests": current_user.total_tests_taken
            }

        # Optional total students pool for "Rank X out of Y"
        total_ranked_students = User.query.filter(User.calculated_rank.isnot(None), User.role == 'student').count()
        
        return jsonify({
            "success": True,
            "top_10": leaderboard,
            "current_user_rank": current_rank_data,
            "total_ranked_students": total_ranked_students
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
