from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

landing_bp = Blueprint('landing', __name__)

@landing_bp.route('/')
def index():
    if current_user.is_authenticated:
        if getattr(current_user, "role", None) == "teacher":
            return redirect(url_for('teacher.dashboard'))
        return redirect(url_for('dashboard.index'))
    return render_template('landing.html')
