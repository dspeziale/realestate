# Copyright 2025 SILICONDEV SPA
# Filename: blueprints/__init__.py
# Description: Blueprints package initialization

from .auth import auth_bp
from .users import users_bp
from .properties import properties_bp
from .auctions import auctions_bp

def register_blueprints(app):
    """Register all blueprints with the Flask app"""
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(properties_bp)
    app.register_blueprint(auctions_bp)

__all__ = ['auth_bp', 'users_bp', 'properties_bp', 'auctions_bp', 'register_blueprints']