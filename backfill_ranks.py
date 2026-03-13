from app import create_app, db
from app.models import User, QuizResult, AnalyzeQuizAttempt
from app.services.ranking_service import recalculate_rankings

def backfill_rankings():
    app = create_app()
    with app.app_context():
        students = User.query.filter_by(role='student').all()
        for student in students:
            # Get teacher quizzes
            quiz_results = QuizResult.query.filter_by(student_id=student.id).all()
            # Get self-study quizzes
            analyze_results = AnalyzeQuizAttempt.query.filter_by(user_id=student.id).all()
            
            total_tests = 0
            total_marks = 0
            
            for r in quiz_results:
                if r.total_questions and r.total_questions > 0:
                    total_tests += 1
                    percentage = (r.score / r.total_questions) * 100.0
                    total_marks += int(percentage)
                    
            for a in analyze_results:
                if a.total_questions and a.total_questions > 0:
                    total_tests += 1
                    percentage = (a.score / a.total_questions) * 100.0
                    total_marks += int(percentage)
            
            student.total_tests_taken = total_tests
            student.total_marks_scored = total_marks
            if total_tests > 0:
                student.average_score = total_marks / total_tests
            else:
                student.average_score = 0.0
                
        db.session.commit()
        print("Backfilled raw scores. Now recalculating ranks...")
        recalculate_rankings()
        print("Done!")

if __name__ == "__main__":
    backfill_rankings()
