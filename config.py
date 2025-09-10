# Copyright 2025 SILICONDEV SPA
# Filename: config.py
# Description: Configuration classes for Real Estate Auction Management

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class BaseConfig:
    """Base configuration class"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///real_estate_auctions.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # WTF Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Google OAuth Configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    OAUTH_REDIRECT_URI = os.environ.get('OAUTH_REDIRECT_URI', 'http://127.0.0.1:5000/auth/google/callback')

    # User management settings
    USER_REGISTRATION_ENABLED = os.environ.get('USER_REGISTRATION_ENABLED', 'True').lower() == 'true'
    USER_EMAIL_VERIFICATION_REQUIRED = os.environ.get('USER_EMAIL_VERIFICATION_REQUIRED', 'False').lower() == 'true'
    USER_PASSWORD_MIN_LENGTH = int(os.environ.get('USER_PASSWORD_MIN_LENGTH', '6'))

    # Gmail Configuration
    GMAIL_USER = os.environ.get('GMAIL_USER')
    GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD')

    # Email Settings
    EMAIL_SENDER_NAME = os.environ.get('EMAIL_SENDER_NAME', 'Sistema Aste Immobiliari')
    EMAIL_REPLY_TO = os.environ.get('EMAIL_REPLY_TO')


class DevelopmentConfig(BaseConfig):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(BaseConfig):
    """Production configuration"""
    DEBUG = False
    SQLALCHEMY_ECHO = False

    # Security settings for production
    WTF_CSRF_SSL_STRICT = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True


class TestingConfig(BaseConfig):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    USER_REGISTRATION_ENABLED = True


# Configuration dictionary
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}