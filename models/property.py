# Copyright 2025 SILICONDEV SPA
# Filename: models/property.py
# Description: Property model for Real Estate Auction Management

from datetime import datetime
from sqlalchemy import Numeric
from database import db


class Property(db.Model):
    """Property model for auction properties"""

    __tablename__ = 'properties'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Property details
    property_type = db.Column(db.String(50), nullable=False)  # appartamento, villa, ufficio, etc.
    condition = db.Column(db.String(50), nullable=True)  # buono, da ristrutturare, etc.
    surface_area = db.Column(db.Float, nullable=True)  # mq
    rooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Integer, nullable=True)
    floor = db.Column(db.String(20), nullable=True)
    year_built = db.Column(db.Integer, nullable=True)

    # Location
    address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    province = db.Column(db.String(50), nullable=False)
    postal_code = db.Column(db.String(20), nullable=True)
    region = db.Column(db.String(50), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Financial information
    base_price = db.Column(Numeric(12, 2), nullable=False)  # Prezzo base asta
    estimated_value = db.Column(Numeric(12, 2), nullable=True)  # Valore di stima
    minimum_bid = db.Column(Numeric(12, 2), nullable=True)  # Offerta minima
    cadastral_income = db.Column(Numeric(10, 2), nullable=True)  # Rendita catastale

    # Legal information
    cadastral_data = db.Column(db.Text, nullable=True)  # Dati catastali completi
    court = db.Column(db.String(100), nullable=True)  # Tribunale competente
    procedure_number = db.Column(db.String(50), nullable=True)  # Numero procedura
    judge = db.Column(db.String(100), nullable=True)  # Giudice dell'esecuzione

    # Property status
    status = db.Column(db.String(20), nullable=False, default='pre_auction')
    # Possibili stati: pre_auction, auction_scheduled, in_auction, sold, unsold, withdrawn

    # Auction information
    auction_type = db.Column(db.String(50), nullable=True)  # sincrona, asincrona, etc.
    is_occupied = db.Column(db.Boolean, default=False, nullable=False)
    has_debts = db.Column(db.Boolean, default=False, nullable=False)
    debt_amount = db.Column(Numeric(12, 2), nullable=True)

    # Features
    has_garage = db.Column(db.Boolean, default=False, nullable=False)
    has_garden = db.Column(db.Boolean, default=False, nullable=False)
    has_terrace = db.Column(db.Boolean, default=False, nullable=False)
    has_elevator = db.Column(db.Boolean, default=False, nullable=False)
    energy_class = db.Column(db.String(5), nullable=True)  # A+, A, B, C, etc.

    # Documents and media
    documents = db.Column(db.Text, nullable=True)  # JSON list of document paths
    images = db.Column(db.Text, nullable=True)  # JSON list of image paths
    virtual_tour_url = db.Column(db.String(255), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Foreign keys
    agent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Relationships
    auctions = db.relationship('Auction', backref='property', lazy='dynamic', cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @property
    def full_address(self):
        """Return full address"""
        parts = [self.address, self.city]
        if self.province:
            parts.append(self.province)
        if self.postal_code:
            parts.append(self.postal_code)
        return ', '.join(filter(None, parts))

    @property
    def status_label(self):
        """Return human-readable status"""
        status_map = {
            'pre_auction': 'Pre-Asta',
            'auction_scheduled': 'Asta Programmata',
            'in_auction': 'In Asta',
            'sold': 'Venduto',
            'unsold': 'Invenduto',
            'withdrawn': 'Ritirato'
        }
        return status_map.get(self.status, self.status)

    @property
    def property_type_label(self):
        """Return human-readable property type"""
        type_map = {
            'apartment': 'Appartamento',
            'villa': 'Villa',
            'house': 'Casa',
            'office': 'Ufficio',
            'commercial': 'Commerciale',
            'industrial': 'Industriale',
            'land': 'Terreno',
            'garage': 'Garage',
            'other': 'Altro'
        }
        return type_map.get(self.property_type, self.property_type)

    def can_edit(self, user):
        """Check if user can edit this property"""
        return user.is_admin or user.id == self.agent_id

    def to_dict(self):
        """Convert property to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'property_type': self.property_type,
            'property_type_label': self.property_type_label,
            'condition': self.condition,
            'surface_area': float(self.surface_area) if self.surface_area else None,
            'rooms': self.rooms,
            'bathrooms': self.bathrooms,
            'full_address': self.full_address,
            'city': self.city,
            'province': self.province,
            'base_price': float(self.base_price),
            'estimated_value': float(self.estimated_value) if self.estimated_value else None,
            'status': self.status,
            'status_label': self.status_label,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'agent_name': self.agent.full_name if self.agent else None
        }

    def __repr__(self):
        return f'<Property {self.title}>'