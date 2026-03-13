from app import create_app, db
from app.models import User, ActivityLog, UserBadge, Badge
from app.services.gamification_service import log_activity, get_ai_motivation
from datetime import datetime, timedelta

app = create_app()

def run_simulation():
    with app.app_context():
        # Get demo student
        student = User.query.filter_by(username='demo_student').first()
        if not student:
            print("Demo student not found. Creating one...")
            student = User(username='demo_student', email='demo@example.com', role='student')
            student.set_password('demo123')
            db.session.add(student)
            db.session.commit()
            
        print(f"--- Simulating for User: {student.username} ---")
        
        # Helper to simulate an action on a specific date
        def sim_day(days_ago, action):
            # We must monkeypatch gamification_service time functions briefly
            import app.services.gamification_service as gs
            sim_time = datetime.utcnow() - timedelta(days=days_ago)
            
            # Monkeypatch
            orig_date = gs.get_current_date
            orig_time = gs.get_current_time
            gs.get_current_date = lambda: sim_time.date()
            gs.get_current_time = lambda: sim_time
            
            print(f"\n[Date: {sim_time.date()}] Simulating '{action}'")
            res = log_activity(student, action)
            
            print(f"   Current Streak: {student.current_streak}")
            print(f"   Longest Streak: {student.longest_streak}")
            print(f"   Motivation: {get_ai_motivation(student)}")
            
            if res.get('streak_message'):
                 print(f"   >>> MILESTONE HIT: {res['streak_message']}")
                 
            if res.get('new_badges'):
                 for b in res['new_badges']:
                     print(f"   >>> BADGE UNLOCKED: {b['name']} ({b['description']})")
                     
            # Restore
            gs.get_current_date = orig_date
            gs.get_current_time = orig_time

        # Day 1
        sim_day(3, 'ai_chat')
        # Day 2
        sim_day(2, 'upload')
        # Day 3 (Should unlock Starter Flame)
        sim_day(1, 'visual_tool')
        # Day 4 (Today: Should be a 4-day streak, perhaps Curious mind if we spam)
        sim_day(0, 'ai_chat')
        sim_day(0, 'ai_chat')
        sim_day(0, 'ai_chat')
        sim_day(0, 'ai_chat')
        sim_day(0, 'ai_chat')
        sim_day(0, 'ai_chat')
        sim_day(0, 'ai_chat')
        sim_day(0, 'ai_chat')
        sim_day(0, 'ai_chat')
        
        print("\n--- Summary ---")
        badges = student.earned_badges.all()
        print(f"Total Badges: {len(badges)}")
        for ub in badges:
            print(f" - {ub.badge.name} ({ub.badge.category})")

        
if __name__ == '__main__':
    run_simulation()
