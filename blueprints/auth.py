# blueprints/auth.py

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from core.traccar_framework import TraccarException

auth_bp = Blueprint('auth', __name__, template_folder='../templates')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            traccar = current_app.config['TRACCAR_API']
            user_info = traccar.session.login(email, password)

            session['user'] = {
                'id': user_info.get('id'),
                'name': user_info.get('name'),
                'email': user_info.get('email'),
                'administrator': user_info.get('administrator', False)
            }

            flash('Login successful!', 'success')
            return redirect(url_for('dashboard.index'))

        except TraccarException as e:
            flash(f'Login failed: {e.message}', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('auth.login'))