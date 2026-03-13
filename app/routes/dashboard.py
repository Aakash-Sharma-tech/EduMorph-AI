from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    if getattr(current_user, "role", None) == "teacher":
        return redirect(url_for('teacher.dashboard'))
    return render_template('dashboard.html')
    
@dashboard_bp.route('/classroom')
@login_required
def classroom():
    return render_template('classroom.html')
