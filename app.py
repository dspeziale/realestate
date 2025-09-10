# Filename: app.py
# Copyright 2025 SILICONDEV SPA
# Description: Main Flask Application for Real Estate Auction Management

import os
import logging
import secrets
from flask import Flask, render_template
from flask_login import LoginManager
from config import config_dict
from database import init_db, db
from blueprints.auth import auth_bp
from blueprints.users import users_bp
from blueprints.properties import properties_bp
from blueprints.auctions import auctions_bp
# 🔥 AGGIUNGI QUESTA RIGA
from blueprints.email import email_bp
from utils.template_helpers import register_template_filters, register_context_processors
from models.user import User

from utils.db_helper import (
    execute_query, execute_select, execute_select_one, execute_insert,
    execute_update, execute_delete, get_database_info, get_all_users,
    get_table_count, table_exists
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__)

    # Determine config name from environment or use default
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    # Get config class from dictionary
    config_class = config_dict.get(config_name, config_dict['default'])
    app.config.from_object(config_class)

    # CSRF Configuration
    if 'WTF_CSRF_ENABLED' not in app.config:
        app.config['WTF_CSRF_ENABLED'] = True

    # Secret key
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = secrets.token_urlsafe(32)
        logger.warning("Using generated SECRET_KEY. Set a permanent one in production!")

    logger.info(f"Using configuration: {config_class.__name__}")
    logger.info(f"Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI', 'Not set')}")

    # Initialize database
    init_db(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Devi effettuare il login per accedere a questa pagina.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    logger.info("Flask-Login initialized successfully")

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(properties_bp)
    app.register_blueprint(auctions_bp)
    # 🔥 AGGIUNGI QUESTA RIGA
    app.register_blueprint(email_bp)

    # Register template helpers
    register_template_filters(app)
    register_context_processors(app)

    # Main route
    @app.route('/')
    def index():
        return render_template('dashboard/index.html')

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app


if __name__ == '__main__':
    app = create_app()
    # Fix per Windows - usa localhost invece di 0.0.0.0
    app.run(host='127.0.0.1', port=5000, debug=True)