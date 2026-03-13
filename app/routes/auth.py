from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if getattr(current_user, "role", None) == "teacher":
            return redirect(url_for('teacher.dashboard'))
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('email') or not data.get('password'):
            return jsonify({'success': False, 'message': 'Missing email or password'}), 400
            
        user = User.query.filter_by(email=data['email']).first()
        if user is None or not user.check_password(data['password']):
            return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
            
        login_user(user, remember=True)
        redirect_url = url_for('teacher.dashboard') if user.role == 'teacher' else url_for('dashboard.index')
        return jsonify({'success': True, 'redirect': redirect_url})
        
    return render_template('login.html')

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'success': False, 'message': 'Missing fields'}), 400
        
    if User.query.filter_by(email=data['email']).first():
         return jsonify({'success': False, 'message': 'Email already registered'}), 400
         
    if User.query.filter_by(username=data['username']).first():
         return jsonify({'success': False, 'message': 'Username already taken'}), 400
         
    role = data.get('role', 'student')
    if role not in ['student', 'teacher']:
        role = 'student'
        
    user = User(username=data['username'], email=data['email'], role=role)
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    
    login_user(user, remember=True)
    redirect_url = url_for('teacher.dashboard') if role == 'teacher' else url_for('dashboard.index')
    return jsonify({'success': True, 'redirect': redirect_url})

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('landing.index'))
