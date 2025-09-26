# app.py - Timesheet Application Main File with User Management
# Copyright 2025 SILICONDEV SPA
# Python 3.13 Compatible

import os
import logging
from datetime import datetime, date, timedelta
from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from models import db, TimeEntry, Project, init_db, User, UserRole, init_user_system
from blueprints.timesheet import timesheet_bp
from blueprints.projects import projects_bp
from blueprints.reports import reports_bp
from blueprints.auth import auth_bp
from sqlalchemy import func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app():
    """Create Flask application factory"""
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'timesheet-dev-key-2025')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timesheet.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_recycle': 300,
        'pool_pre_ping': True
    }

    # Initialize database
    init_db(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Devi effettuare il login per accedere a questa pagina.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(timesheet_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(reports_bp)

    # Main routes
    @app.route('/')
    @login_required
    def index():
        """Dashboard principale"""
        return redirect(url_for('timesheet.index'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        """Dashboard con statistiche dell'utente corrente"""
        # Statistiche oggi per l'utente corrente
        today = date.today()
        today_entries = TimeEntry.query.filter(
            TimeEntry.user_id == current_user.id,
            func.date(TimeEntry.start_time) == today
        ).all()

        today_hours = sum([entry.duration_hours for entry in today_entries if entry.duration_hours])

        # Statistiche settimana corrente
        start_of_week = today - timedelta(days=today.weekday())
        week_entries = TimeEntry.query.filter(
            TimeEntry.user_id == current_user.id,
            func.date(TimeEntry.start_time) >= start_of_week
        ).all()

        week_hours = sum([entry.duration_hours for entry in week_entries if entry.duration_hours])

        # Progetti dell'utente
        user_projects = Project.query.filter_by(user_id=current_user.id)
        active_projects = user_projects.filter_by(is_active=True).count()
        total_projects = user_projects.count()

        stats = {
            'today_hours': round(today_hours, 2) if today_hours else 0,
            'week_hours': round(week_hours, 2) if week_hours else 0,
            'active_projects': active_projects,
            'total_projects': total_projects,
            'recent_entries': current_user.get_recent_entries(5)
        }

        return render_template('dashboard.html', stats=stats)

    # Context processor for global template variables
    @app.context_processor
    def inject_user():
        """Inject current user into all templates"""
        return dict(current_user=current_user)

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f'Server Error: {error}')
        db.session.rollback()
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    # Initialize user system on first run
    with app.app_context():
        try:
            init_user_system()
            logger.info("User system initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing user system: {str(e)}")

    return app


def create_admin_user():
    """Create default admin user - run this manually if needed"""
    with create_app().app_context():
        if User.query.filter_by(username='admin').first():
            print("Admin user already exists")
            return

        admin = User.create_user(
            username='admin',
            email='admin@timesheet.app',
            password='admin123',
            first_name='Admin',
            last_name='User',
            role=UserRole.ADMIN
        )
        print(f"Created admin user: {admin.username}")
        print("Default password: admin123")
        print("Please change the password after first login!")


if __name__ == '__main__':
    app = create_app()

    # Check if we should create admin user
    if '--create-admin' in os.sys.argv:
        create_admin_user()
    else:
        logger.info("Starting Timesheet Application with User Management...")
        logger.info("Default admin credentials: admin / admin123")
        logger.info("Visit /auth/register to create new users")
        app.run(debug=True, host='0.0.0.0', port=5000)