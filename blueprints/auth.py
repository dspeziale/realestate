# Copyright 2025 SILICONDEV SPA
# Filename: blueprints/auth.py
# Description: Authentication Blueprint

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from authlib.integrations.flask_client import OAuth
import requests

from database import db
from models.user import User
from utils import execute_update

# Initialize Blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Initialize OAuth
oauth = OAuth()


def init_oauth(app):
    """Initialize OAuth with app configuration"""
    oauth.init_app(app)

    # Configure Google OAuth
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid_configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember_me = request.form.get('remember_me') == 'on'

        if not email or not password:
            flash('Email e password sono richiesti.', 'error')
            return render_template('auth/login.html')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Account disattivato. Contatta l\'amministratore.', 'error')
                return render_template('auth/login.html')

            user.last_login = datetime.utcnow()
            db.session.commit()

            login_user(user, remember=remember_me)
            flash(f'Benvenuto {user.full_name}!', 'success')

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Email o password non corretti.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/admin')
def make_admin():
    """Route per rendere admin un utente specifico"""
    try:
        # Use SQLAlchemy ORM instead of raw SQL
        user = User.query.filter_by(email='dspeziale@gmail.com').first()

        if user:
            user.is_admin = True
            db.session.commit()
            flash(f'Utente {user.email} è ora amministratore!', 'success')
        else:
            flash('Utente dspeziale@gmail.com non trovato.', 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'Errore: {str(e)}', 'error')

    return redirect(url_for('index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if not current_app.config.get('USER_REGISTRATION_ENABLED', True):
        flash('La registrazione è attualmente disabilitata.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        # Get form data
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form.get('username', '').strip()
        phone = request.form.get('phone', '').strip()

        # Validation
        errors = []

        if not email:
            errors.append('Email è richiesta.')
        elif User.query.filter_by(email=email).first():
            errors.append('Email già registrata.')

        if not password:
            errors.append('Password è richiesta.')
        elif len(password) < current_app.config.get('USER_PASSWORD_MIN_LENGTH', 6):
            errors.append(
                f'Password deve essere almeno {current_app.config.get("USER_PASSWORD_MIN_LENGTH", 6)} caratteri.')

        if password != confirm_password:
            errors.append('Le password non coincidono.')

        if not first_name:
            errors.append('Nome è richiesto.')

        if not last_name:
            errors.append('Cognome è richiesto.')

        if username and User.query.filter_by(username=username).first():
            errors.append('Username già utilizzato.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/register.html')

        # Create new user
        try:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                username=username or None,
                phone=phone or None,
                is_verified=not current_app.config.get('USER_EMAIL_VERIFICATION_REQUIRED', False)
            )
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash('Registrazione completata con successo! Puoi ora effettuare il login.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash(f'Errore durante la registrazione: {str(e)}', 'error')

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    user_name = current_user.full_name
    logout_user()
    flash(f'Logout effettuato. Arrivederci {user_name}!', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/google')
def google_login():
    """Redirect to Google OAuth"""
    if not current_app.config.get('GOOGLE_CLIENT_ID'):
        flash('Login con Google non configurato.', 'error')
        return redirect(url_for('auth.login'))

    redirect_uri = current_app.config.get('OAUTH_REDIRECT_URI') or url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route('/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    try:
        token = oauth.google.authorize_access_token()
        user_info = token.get('userinfo')

        if not user_info:
            flash('Errore nell\'autenticazione con Google.', 'error')
            return redirect(url_for('auth.login'))

        google_id = user_info.get('sub')
        email = user_info.get('email')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        profile_picture = user_info.get('picture')

        if not email:
            flash('Impossibile ottenere l\'email da Google.', 'error')
            return redirect(url_for('auth.login'))

        # Find or create user
        user = User.query.filter_by(email=email).first()

        if user:
            # Update Google ID if not set
            if not user.google_id:
                user.google_id = google_id

            # Update profile picture
            if profile_picture:
                user.profile_picture = profile_picture

            user.last_login = datetime.utcnow()
            db.session.commit()
        else:
            # Create new user
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                google_id=google_id,
                profile_picture=profile_picture,
                is_verified=True  # Google accounts are considered verified
            )

            db.session.add(user)
            db.session.commit()

            flash(f'Account creato con successo! Benvenuto {user.full_name}!', 'success')

        if not user.is_active:
            flash('Account disattivato. Contatta l\'amministratore.', 'error')
            return redirect(url_for('auth.login'))

        login_user(user, remember=True)

        next_page = session.pop('next_page', None) or request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('index'))

    except Exception as e:
        current_app.logger.error(f"Google OAuth error: {str(e)}")
        flash('Errore durante l\'autenticazione con Google.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('auth/profile.html', user=current_user)


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        # Get form data
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form.get('username', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        company_name = request.form.get('company_name', '').strip()
        license_number = request.form.get('license_number', '').strip()
        vat_number = request.form.get('vat_number', '').strip()

        # Validation
        errors = []

        if not first_name:
            errors.append('Nome è richiesto.')

        if not last_name:
            errors.append('Cognome è richiesto.')

        if username and username != current_user.username:
            if User.query.filter_by(username=username).first():
                errors.append('Username già utilizzato.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/edit_profile.html', user=current_user)

        # Update user
        try:
            current_user.first_name = first_name
            current_user.last_name = last_name
            current_user.username = username or None
            current_user.phone = phone or None
            current_user.address = address or None
            current_user.city = city or None
            current_user.postal_code = postal_code or None
            current_user.company_name = company_name or None
            current_user.license_number = license_number or None
            current_user.vat_number = vat_number or None
            current_user.updated_at = datetime.utcnow()

            db.session.commit()
            flash('Profilo aggiornato con successo!', 'success')
            return redirect(url_for('auth.profile'))

        except Exception as e:
            db.session.rollback()
            flash(f'Errore nell\'aggiornamento del profilo: {str(e)}', 'error')

    return render_template('auth/edit_profile.html', user=current_user)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    if current_user.google_id and not current_user.password_hash:
        flash('Non puoi cambiare la password per un account Google.', 'warning')
        return redirect(url_for('auth.profile'))

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        errors = []

        if not current_password:
            errors.append('Password attuale è richiesta.')
        elif not current_user.check_password(current_password):
            errors.append('Password attuale non corretta.')

        if not new_password:
            errors.append('Nuova password è richiesta.')
        elif len(new_password) < current_app.config.get('USER_PASSWORD_MIN_LENGTH', 6):
            errors.append(
                f'La password deve essere almeno {current_app.config.get("USER_PASSWORD_MIN_LENGTH", 6)} caratteri.')

        if new_password != confirm_password:
            errors.append('Le password non coincidono.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/change_password.html')

        # Update password
        try:
            current_user.set_password(new_password)
            current_user.updated_at = datetime.utcnow()
            db.session.commit()

            flash('Password cambiata con successo!', 'success')
            return redirect(url_for('auth.profile'))

        except Exception as e:
            db.session.rollback()
            flash(f'Errore nel cambio password: {str(e)}', 'error')

    return render_template('auth/change_password.html')


# Initialize OAuth when blueprint is registered
@auth_bp.record_once
def on_load(state):
    """Initialize OAuth when blueprint is registered with app"""
    if state.app.config.get('GOOGLE_CLIENT_ID'):
        init_oauth(state.app)
    else:
        state.app.logger.warning("Google OAuth not configured - GOOGLE_CLIENT_ID missing")