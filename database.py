# Copyright 2025 SILICONDEV SPA
# Filename: database.py
# Description: Database initialization and configuration

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import logging

logger = logging.getLogger(__name__)

# Initialize SQLAlchemy
db = SQLAlchemy()
migrate = Migrate()


def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    migrate.init_app(app, db)

    with app.app_context():
        try:
            # Import all models to ensure they are registered
            from models import user, property, auction
            logger.info("Models imported successfully")

            # Create tables
            db.create_all()
            logger.info("Database tables created successfully")

        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise