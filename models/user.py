# Copyright 2025 SILICONDEV SPA
# Filename: models/user.py
# Description: User model for Real Estate Auction Management

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db

class User(UserMixin, db.Model):
    """User model for authentication and authorization"""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    
    # OAuth fields
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    profile_picture = db.Column(db.Text, nullable=True)
    
    # User status and roles
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # Contact information
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    city = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(100), nullable=True, default='Italia')
    
    # Professional information
    license_number = db.Column(db.String(50), nullable=True)  # Numero iscrizione albo
    company_name = db.Column(db.String(200), nullable=True)
    vat_number = db.Column(db.String(20), nullable=True)  # Partita IVA
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    properties = db.relationship('Property', backref='agent', lazy='dynamic', cascade='all, delete-orphan')
    bids = db.relationship('Bid', backref='bidder', lazy='dynamic', cascade='all, delete-orphan')
    
    def __init__(self, email, first_name, last_name, **kwargs):
        self.email = email
        self.first_name = first_name  
        self.last_name = last_name
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password is correct"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        """Return full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def display_name(self):
        """Return display name (username or full name)"""
        return self.username or self.full_name
    
    def has_role(self, role):
        """Check if user has specific role"""
        if role == 'admin':
            return self.is_admin
        return True  # Default role for authenticated users
    
    def can_access_admin(self):
        """Check if user can access admin panel"""
        return self.is_admin
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'is_admin': self.is_admin,
            'phone': self.phone,
            'company_name': self.company_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    def __repr__(self):
        return f'<User {self.email}>'