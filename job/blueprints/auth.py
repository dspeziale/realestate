# blueprints/auth.py - Authentication Blueprint
# Copyright 2025 SILICONDEV SPA
# User authentication and session management

import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin
from models import db, User, UserRole
import requests

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def is_safe_url(target):
    """Check if redirect URL is safe"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login page"""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username_or_email = request.form.get('username_or_email', '').strip()
        password = request.form.get('password', '').strip()
        remember_me = bool(request.form.get('remember_me'))

        if not username_or_email or not password:
            flash('Tutti i campi sono obbligatori', 'error')
            return render_template('auth/login.html')

        # Try to authenticate user
        user = User.query.filter(
            (User.username == username_or_email) |
            (User.email == username_or_email)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Il tuo account è disattivato. Contatta l\'amministratore.', 'error')
                return render_template('auth/login.html')

            # Login successful
            user.update_last_login()
            login_user(user, remember=remember_me)

            logger.info(f"User logged in: {user.username}")
            flash(f'Benvenuto, {user.display_name}!', 'success')

            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if not next_page or not is_safe_url(next_page):
                next_page = url_for('index')

            return redirect(next_page)
        else:
            flash('Credenziali non valide', 'error')
            logger.warning(f"Failed login attempt for: {username_or_email}")

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration page"""
    # Redirect if already logged in
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            email = request.form.get('email', '').strip()
            first_name = request.form.get('first_name', '').strip()
            last_name = request.form.get('last_name', '').strip()
            password = request.form.get('password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            # Validation
            if not all([username, email, password, confirm_password]):
                flash('Tutti i campi obbligatori devono essere compilati', 'error')
                return render_template('auth/register.html')

            if len(username) < 3:
                flash('Il username deve essere di almeno 3 caratteri', 'error')
                return render_template('auth/register.html')

            if len(password) < 6:
                flash('La password deve essere di almeno 6 caratteri', 'error')
                return render_template('auth/register.html')

            if password != confirm_password:
                flash('Le password non coincidono', 'error')
                return render_template('auth/register.html')

            # Check if user already exists
            if User.get_by_username(username):
                flash('Username già esistente', 'error')
                return render_template('auth/register.html')

            if User.get_by_email(email):
                flash('Email già registrata', 'error')
                return render_template('auth/register.html')

            # Create new user
            user = User.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=UserRole.USER
            )

            flash('Registrazione completata con successo! Puoi ora effettuare il login.', 'success')
            logger.info(f"New user registered: {user.username}")

            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during registration: {str(e)}")
            flash('Errore durante la registrazione. Riprova.', 'error')

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    username = current_user.username
    logout_user()
    logger.info(f"User logged out: {username}")
    flash('Logout effettuato con successo', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    user_stats = {
        'total_hours': current_user.total_hours,
        'total_entries': current_user.total_entries,
        'projects_count': current_user.projects_count,
        'recent_entries': current_user.get_recent_entries(5)
    }
    return render_template('auth/profile.html', user_stats=user_stats)


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        try:
            current_user.first_name = request.form.get('first_name', '').strip()
            current_user.last_name = request.form.get('last_name', '').strip()
            current_user.email = request.form.get('email', '').strip()

            # Check if email is unique (excluding current user)
            existing_user = User.query.filter(
                User.email == current_user.email,
                User.id != current_user.id
            ).first()

            if existing_user:
                flash('Email già utilizzata da un altro utente', 'error')
                return render_template('auth/edit_profile.html')

            db.session.commit()
            flash('Profilo aggiornato con successo!', 'success')
            logger.info(f"Profile updated for user: {current_user.username}")

            return redirect(url_for('auth.profile'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating profile: {str(e)}")
            flash('Errore durante l\'aggiornamento del profilo', 'error')

    return render_template('auth/edit_profile.html')


@auth_bp.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    if request.method == 'POST':
        try:
            current_password = request.form.get('current_password', '').strip()
            new_password = request.form.get('new_password', '').strip()
            confirm_password = request.form.get('confirm_password', '').strip()

            # Validation
            if not all([current_password, new_password, confirm_password]):
                flash('Tutti i campi sono obbligatori', 'error')
                return render_template('auth/change_password.html')

            if not current_user.check_password(current_password):
                flash('Password attuale non corretta', 'error')
                return render_template('auth/change_password.html')

            if len(new_password) < 6:
                flash('La nuova password deve essere di almeno 6 caratteri', 'error')
                return render_template('auth/change_password.html')

            if new_password != confirm_password:
                flash('Le nuove password non coincidono', 'error')
                return render_template('auth/change_password.html')

            # Update password
            current_user.set_password(new_password)
            db.session.commit()

            flash('Password cambiata con successo!', 'success')
            logger.info(f"Password changed for user: {current_user.username}")

            return redirect(url_for('auth.profile'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error changing password: {str(e)}")
            flash('Errore durante il cambio password', 'error')

    return render_template('auth/change_password.html')


@auth_bp.route('/google')
def google_login():
    """Start Google OAuth flow"""
    # This would integrate with Google OAuth
    # For now, return a placeholder
    flash('Integrazione Google OAuth non ancora implementata', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    # This would handle the OAuth callback
    flash('Callback Google OAuth non ancora implementato', 'info')
    return redirect(url_for('auth.login'))


# Admin routes
@auth_bp.route('/admin/users')
@login_required
def admin_users():
    """Admin: List all users"""
    if not current_user.is_admin:
        flash('Accesso negato. Solo gli amministratori possono accedere a questa area.', 'error')
        return redirect(url_for('index'))

    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('auth/admin_users.html', users=users)


@auth_bp.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Admin: Toggle user active status"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accesso negato'}), 403

    try:
        user = User.query.get_or_404(user_id)

        if user.id == current_user.id:
            return jsonify({'success': False, 'message': 'Non puoi disattivare il tuo stesso account'}), 400

        user.is_active = not user.is_active
        db.session.commit()

        action = "attivato" if user.is_active else "disattivato"
        logger.info(f"User {user.username} {action} by admin {current_user.username}")

        return jsonify({
            'success': True,
            'message': f'Utente {user.username} {action}',
            'is_active': user.is_active
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling user status: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore durante l\'operazione'}), 500


@auth_bp.route('/admin/users/<int:user_id>/role', methods=['POST'])
@login_required
def change_user_role(user_id):
    """Admin: Change user role"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Accesso negato'}), 403

    try:
        user = User.query.get_or_404(user_id)
        new_role = request.json.get('role')

        if not new_role or new_role not in [role.value for role in UserRole]:
            return jsonify({'success': False, 'message': 'Ruolo non valido'}), 400

        if user.id == current_user.id and new_role != UserRole.ADMIN.value:
            return jsonify(
                {'success': False, 'message': 'Non puoi rimuovere i privilegi di admin dal tuo stesso account'}), 400

        user.role = UserRole(new_role)
        db.session.commit()

        logger.info(f"User {user.username} role changed to {new_role} by admin {current_user.username}")

        return jsonify({
            'success': True,
            'message': f'Ruolo di {user.username} cambiato a {new_role}',
            'role': new_role
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error changing user role: {str(e)}")
        return jsonify({'success': False, 'message': 'Errore durante l\'operazione'}), 500