# blueprints/auth.py - Fixed authentication

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from core.traccar_framework import TraccarException

auth_bp = Blueprint('auth', __name__, template_folder='../templates')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Se già loggato, redirect a dashboard
    if 'user' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            traccar = current_app.config['TRACCAR_API']

            # Attempt login
            user_info = traccar.session.login(email, password)

            # Store user info in session
            session['user'] = {
                'id': user_info.get('id'),
                'name': user_info.get('name'),
                'email': user_info.get('email'),
                'administrator': user_info.get('administrator', False)
            }

            # Update Traccar client credentials for future requests
            traccar.client.username = email
            traccar.client.password = password
            traccar.client._setup_auth()

            flash('Login successful!', 'success')
            return redirect(url_for('dashboard.index'))

        except TraccarException as e:
            flash(f'Login failed: {e.message}', 'error')
        except Exception as e:
            flash(f'Login error: {str(e)}', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    # Clear session
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('auth.login'))