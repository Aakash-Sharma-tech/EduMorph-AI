from app import db
from app.models import User
from sqlalchemy import desc

def recalculate_rankings():
    """
    Ranks all students based on their average score descending,
    then by total tests taken descending as a tie-breaker.
    If total_tests_taken == 0, rank should be pushed to the bottom.
    """
    try:
        # Get all users with role 'student'
        students = User.query.filter_by(role='student').all()
        
        # Sort them in memory for complex tie breakers, ignoring zero-tests temporarily
        active_students = [s for s in students if s.total_tests_taken > 0]
        inactive_students = [s for s in students if s.total_tests_taken == 0 or s.total_tests_taken is None]
        
        # Sort active students: highest avg score first, then highest tests taken
        active_students.sort(key=lambda x: (x.average_score, x.total_tests_taken), reverse=True)
        
        # Assign ranks
        current_rank = 1
        for student in active_students:
            student.calculated_rank = current_rank
            current_rank += 1
            
        # Give inactive students no rank (or push to bottom)
        for student in inactive_students:
            student.calculated_rank = None
            
        db.session.commit()
    except Exception as e:
        print(f"Error recalculating rankings: {e}")
        db.session.rollback()

def update_student_score(student, score, total_questions):
    """
    Updates the student's metrics after a quiz and triggers global rank recalculation.
    Scores here are normalized to percentage (0-100) for uniform weighting across varying question counts.
    """
    try:
        if total_questions == 0:
            return
            
        percentage_score = (score / total_questions) * 100.0
        
        # Initialize if None
        if student.total_tests_taken is None: student.total_tests_taken = 0
        if student.total_marks_scored is None: student.total_marks_scored = 0
        
        # Using percentage as the "marks scored" for a standardized average
        student.total_tests_taken += 1
        student.total_marks_scored += int(percentage_score)
        student.average_score = student.total_marks_scored / student.total_tests_taken
        
        db.session.commit()
        
        # Recalculate global ranks
        recalculate_rankings()
        
    except Exception as e:
        print(f"Error updating score for student {student.id}: {e}")
        db.session.rollback()
