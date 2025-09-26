# app.py - Timesheet Application Main File
# Copyright 2025 SILICONDEV SPA
# Python 3.13 Compatible

import os
import logging
from datetime import datetime, date, timedelta
from flask import Flask, render_template, redirect, url_for, flash
from models import db, TimeEntry, Project, init_db
from blueprints.timesheet import timesheet_bp
from blueprints.projects import projects_bp
from blueprints.reports import reports_bp
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

    # Register blueprints
    app.register_blueprint(timesheet_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(reports_bp)

    # Main routes
    @app.route('/')
    def index():
        """Dashboard principale"""
        return redirect(url_for('timesheet.index'))

    @app.route('/dashboard')
    def dashboard():
        """Dashboard con statistiche"""
        # Statistiche oggi
        today = date.today()
        today_entries = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) == today
        ).all()

        today_hours = sum([entry.duration_hours for entry in today_entries if entry.duration_hours])

        # Statistiche settimana corrente
        start_of_week = today - timedelta(days=today.weekday())
        week_entries = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) >= start_of_week
        ).all()

        week_hours = sum([entry.duration_hours for entry in week_entries if entry.duration_hours])

        # Progetti attivi
        active_projects = Project.query.filter_by(is_active=True).count()
        total_projects = Project.query.count()

        stats = {
            'today_hours': round(today_hours, 2) if today_hours else 0,
            'week_hours': round(week_hours, 2) if week_hours else 0,
            'active_projects': active_projects,
            'total_projects': total_projects,
            'recent_entries': TimeEntry.query.order_by(TimeEntry.created_at.desc()).limit(5).all()
        }

        return render_template('dashboard.html', stats=stats)

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f'Server Error: {error}')
        return render_template('errors/500.html'), 500

    return app


if __name__ == '__main__':
    app = create_app()
    logger.info("Starting Timesheet Application...")
    app.run(debug=True, host='0.0.0.0', port=5000)