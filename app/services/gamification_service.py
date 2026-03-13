from datetime import datetime
from pytz import timezone
from app import db
from app.models import User, Badge, UserBadge, ActivityLog, Topic, UserProgress

# Central timezone logic if everything is standard UTC
def get_current_date():
    return datetime.utcnow().date()
    
def get_current_time():
    return datetime.utcnow()

# Seed predefined badges into the database
def seed_badges():
    badges = [
        # Learning Badges
        {'name': 'First Step', 'desc': 'Complete first learning module', 'icon': '🎯', 'cat': 'Learning', 'cond': 'first_module_complete'},
        {'name': 'Curious Mind', 'desc': 'Ask 10 AI tutor questions', 'icon': '❓', 'cat': 'Learning', 'cond': '10_ai_questions'},
        {'name': 'Knowledge Explorer', 'desc': 'Study 10 topics', 'icon': '🧭', 'cat': 'Learning', 'cond': '10_topics_studied'},
        {'name': 'Deep Learner', 'desc': 'Study 50 topics', 'icon': '🧠', 'cat': 'Learning', 'cond': '50_topics_studied'},
        # Consistency Badges
        {'name': 'Starter Flame', 'desc': '3 day streak', 'icon': '🔥', 'cat': 'Consistency', 'cond': '3_day_streak'},
        {'name': 'Focused Flame', 'desc': '7 day streak', 'icon': '☄️', 'cat': 'Consistency', 'cond': '7_day_streak'},
        {'name': 'Learning Machine', 'desc': '30 day streak', 'icon': '🤖', 'cat': 'Consistency', 'cond': '30_day_streak'},
        {'name': 'Discipline Master', 'desc': '100 day streak', 'icon': '👑', 'cat': 'Consistency', 'cond': '100_day_streak'},
        # Exploration Badges
        {'name': 'AI Explorer', 'desc': 'Use AI tutor for the first time', 'icon': '🚀', 'cat': 'Exploration', 'cond': 'use_ai_tutor'},
        {'name': 'Note Master', 'desc': 'Upload learning notes', 'icon': '📝', 'cat': 'Exploration', 'cond': 'upload_notes'},
        {'name': 'Visual Learner', 'desc': 'Use visual explanation tools', 'icon': '👁️', 'cat': 'Exploration', 'cond': 'use_visual_tools'},
        {'name': 'Night Scholar', 'desc': 'Study after 10 PM', 'icon': '🦉', 'cat': 'Exploration', 'cond': 'study_after_10pm'},
    ]
    
    for b_data in badges:
        if not Badge.query.filter_by(name=b_data['name']).first():
            db.session.add(Badge(
                name=b_data['name'], 
                description=b_data['desc'], 
                icon=b_data['icon'], 
                category=b_data['cat'], 
                condition=b_data['cond']
            ))
    db.session.commit()

def log_activity(user, action_type):
    """
    Log an activity for gamification, update streak, and award badges.
    Returns: a dict containing new badges and milestone alerts if any.
    """
    if not user.is_authenticated:
        return {}
        
    now = get_current_time()
    today = now.date()
    
    # 1. Log Activity
    log_entry = ActivityLog(user_id=user.id, action_type=action_type, timestamp=now)
    db.session.add(log_entry)
    
    # 2. Update Streak
    streak_msg = update_streak(user, today)
    
    # 3. Check Badges
    new_badges = evaluate_badges(user, action_type, now)
    
    db.session.commit()
    return {
        'streak_message': streak_msg,
        'new_badges': new_badges
    }

def update_streak(user, today):
    """
    Updates the player's streak.
    Returns a milestone unlock string if they hit a major milestone, else None.
    """
    if user.last_active_date is None:
        # First day!
        user.current_streak = 1
        user.longest_streak = 1
        user.last_active_date = today
        return None
        
    delta_days = (today - user.last_active_date).days
    
    if delta_days == 0:
        # Already logged an activity today
        return None
    elif delta_days == 1:
        # Consecutive day!
        user.current_streak += 1
        if user.current_streak > user.longest_streak:
            user.longest_streak = user.current_streak
    else:
        # Streak broken
        user.current_streak = 1
        
    user.last_active_date = today
    db.session.commit()
    
    return check_streak_milestone(user.current_streak)

def check_streak_milestone(streak):
    milestones = {
        3: 'Getting Started',
        7: 'Consistent Learner',
        14: 'Focused Scholar',
        30: 'Knowledge Warrior',
        60: 'Learning Champion',
        100: 'Edumorph Legend'
    }
    if streak in milestones:
        # Will be shown via AI Motivation message
        return milestones[streak]
    return None

def award_badge(user, condition):
    """Helper to give a user a badge if they dont already have it."""
    badge = Badge.query.filter_by(condition=condition).first()
    if not badge:
        return None
        
    existing = UserBadge.query.filter_by(user_id=user.id, badge_id=badge.id).first()
    if not existing:
        ub = UserBadge(user_id=user.id, badge_id=badge.id)
        db.session.add(ub)
        return {"name": badge.name, "description": badge.description, "icon": badge.icon}
    return None


def evaluate_badges(user, action_type, now):
    new_badges = []
    
    # --- Exploration Badges ---
    if action_type == 'ai_chat':
        # AI Explorer
        unlocked = award_badge(user, 'use_ai_tutor')
        if unlocked: new_badges.append(unlocked)
        
    elif action_type == 'upload':
        # Note Master
        unlocked = award_badge(user, 'upload_notes')
        if unlocked: new_badges.append(unlocked)
        
    elif action_type == 'visual_tool':
        unlocked = award_badge(user, 'use_visual_tools')
        if unlocked: new_badges.append(unlocked)
        
    # Night Scholar
    if now.hour >= 22 or now.hour < 4:
        unlocked = award_badge(user, 'study_after_10pm')
        if unlocked: new_badges.append(unlocked)
        
    # --- Learning Badges ---
    # We do a quick count of AI interactions for "Curious Mind"
    if action_type == 'ai_chat':
        chat_count = ActivityLog.query.filter_by(user_id=user.id, action_type='ai_chat').count()
        if chat_count >= 10:
            unlocked = award_badge(user, '10_ai_questions')
            if unlocked: new_badges.append(unlocked)
            
    # Topics studied (from UserProgress which implies hitting a topic)
    if action_type in ['quiz_completed', 'topic_view']:
        topic_count = UserProgress.query.filter_by(user_id=user.id).count()
        if topic_count >= 1:
            unlocked = award_badge(user, 'first_module_complete')
            if unlocked: new_badges.append(unlocked)
        if topic_count >= 10:
            unlocked = award_badge(user, '10_topics_studied')
            if unlocked: new_badges.append(unlocked)
        if topic_count >= 50:
            unlocked = award_badge(user, '50_topics_studied')
            if unlocked: new_badges.append(unlocked)
            
    # --- Consistency Badges ---
    streak = user.current_streak
    if streak >= 3:
        unlocked = award_badge(user, '3_day_streak')
        if unlocked: new_badges.append(unlocked)
    if streak >= 7:
        unlocked = award_badge(user, '7_day_streak')
        if unlocked: new_badges.append(unlocked)
    if streak >= 30:
        unlocked = award_badge(user, '30_day_streak')
        if unlocked: new_badges.append(unlocked)
    if streak >= 100:
        unlocked = award_badge(user, '100_day_streak')
        if unlocked: new_badges.append(unlocked)
        
    return new_badges

def get_ai_motivation(user):
    """
    Returns a quick string to place on the dashboard regarding streaks.
    """
    if not user.last_active_date:
        return "Welcome to Edumorph AI! Complete an activity today to start your learning streak."
        
    today = get_current_date()
    delta = (today - user.last_active_date).days
    
    streak = user.current_streak
    
    if delta == 0:
        if streak == 1:
             return "Great start! Come back tomorrow to keep the flame alive."
        elif streak < 7:
             return f"Great job! You have a {streak} day learning streak. Keep it up!"
        else:
             return f"Unstoppable! {streak} days strong. Keep learning today to reach your next milestone."
             
    elif delta == 1:
        return f"Your {streak} day streak is waiting! Complete a learning activity today to keep it alive."
        
    else:
        return f"It's been {delta} days since you last studied. Every expert was once a beginner. Start a new streak today!"

def get_next_streak_milestone(current):
    milestones = [3, 7, 14, 30, 60, 100]
    for m in milestones:
        if m > current:
            return m
    return None
