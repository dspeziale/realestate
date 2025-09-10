# Copyright 2025 SILICONDEV SPA
# Filename: models/auction.py
# Description: Auction and Bid models for Real Estate Auction Management

from datetime import datetime
from sqlalchemy import Numeric
from database import db


class Auction(db.Model):
    """Auction model for property auctions"""

    __tablename__ = 'auctions'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Auction details
    auction_number = db.Column(db.String(50), unique=True, nullable=False)
    auction_type = db.Column(db.String(50), nullable=False, default='synchronous')
    # synchronous = sincrona, asynchronous = asincrona, telematic = telematica

    # Timing
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)
    registration_deadline = db.Column(db.DateTime, nullable=True)

    # Financial terms
    starting_price = db.Column(Numeric(12, 2), nullable=False)
    minimum_bid_increment = db.Column(Numeric(10, 2), nullable=False, default=1000.00)
    deposit_amount = db.Column(Numeric(12, 2), nullable=False)  # Cauzione
    deposit_percentage = db.Column(db.Float, nullable=True, default=10.0)  # % della cauzione

    # Current auction state
    current_price = db.Column(Numeric(12, 2), nullable=True)
    highest_bid = db.Column(Numeric(12, 2), nullable=True)
    total_bids = db.Column(db.Integer, nullable=False, default=0)

    # Status
    status = db.Column(db.String(20), nullable=False, default='scheduled')
    # Possibili stati: scheduled, active, ended, cancelled, sold, unsold

    # Legal and administrative details
    court = db.Column(db.String(100), nullable=True)
    procedure_number = db.Column(db.String(50), nullable=True)
    professional_delegate = db.Column(db.String(200), nullable=True)  # Professionista delegato

    # Participation requirements
    requires_registration = db.Column(db.Boolean, default=True, nullable=False)
    allows_remote_bidding = db.Column(db.Boolean, default=True, nullable=False)

    # Notes and conditions
    special_conditions = db.Column(db.Text, nullable=True)
    viewing_schedule = db.Column(db.Text, nullable=True)  # Orari visita
    notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Foreign keys
    property_id = db.Column(db.Integer, db.ForeignKey('properties.id'), nullable=False)

    # Relationships
    bids = db.relationship('Bid', backref='auction', lazy='dynamic', cascade='all, delete-orphan',
                           order_by='Bid.created_at.desc()')

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @property
    def status_label(self):
        """Return human-readable status"""
        status_map = {
            'scheduled': 'Programmata',
            'active': 'In corso',
            'ended': 'Terminata',
            'cancelled': 'Annullata',
            'sold': 'Venduta',
            'unsold': 'Invenduta'
        }
        return status_map.get(self.status, self.status)

    @property
    def auction_type_label(self):
        """Return human-readable auction type"""
        type_map = {
            'synchronous': 'Sincrona',
            'asynchronous': 'Asincrona',
            'telematic': 'Telematica'
        }
        return type_map.get(self.auction_type, self.auction_type)

    @property
    def is_active(self):
        """Check if auction is currently active"""
        now = datetime.utcnow()
        return (self.status == 'active' and
                self.start_date <= now and
                (self.end_date is None or now <= self.end_date))

    @property
    def is_upcoming(self):
        """Check if auction is scheduled for future"""
        return self.status == 'scheduled' and self.start_date > datetime.utcnow()

    @property
    def time_remaining(self):
        """Get time remaining for auction"""
        if not self.end_date or self.status != 'active':
            return None

        remaining = self.end_date - datetime.utcnow()
        if remaining.total_seconds() <= 0:
            return None

        return remaining

    def can_bid(self, user):
        """Check if user can place bids"""
        if not self.is_active:
            return False

        # Additional checks could include:
        # - User registration for auction
        # - Deposit payment verification
        # - User qualification status

        return True

    def get_winning_bid(self):
        """Get the current winning bid"""
        return self.bids.filter_by(is_winning=True).first()

    def update_current_price(self):
        """Update current price based on highest bid"""
        highest_bid = self.bids.order_by(Bid.amount.desc()).first()
        if highest_bid:
            self.current_price = highest_bid.amount
            self.highest_bid = highest_bid.amount
            self.total_bids = self.bids.count()
        else:
            self.current_price = self.starting_price
            self.highest_bid = None
            self.total_bids = 0

    def to_dict(self):
        """Convert auction to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'auction_number': self.auction_number,
            'auction_type': self.auction_type,
            'auction_type_label': self.auction_type_label,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'starting_price': float(self.starting_price),
            'current_price': float(self.current_price) if self.current_price else float(self.starting_price),
            'deposit_amount': float(self.deposit_amount),
            'status': self.status,
            'status_label': self.status_label,
            'total_bids': self.total_bids,
            'is_active': self.is_active,
            'is_upcoming': self.is_upcoming,
            'property_title': self.property.title if self.property else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<Auction {self.auction_number}>'


class Bid(db.Model):
    """Bid model for auction bids"""

    __tablename__ = 'bids'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(Numeric(12, 2), nullable=False)

    # Bid status
    is_winning = db.Column(db.Boolean, default=False, nullable=False)
    is_valid = db.Column(db.Boolean, default=True, nullable=False)

    # Bid details
    bid_type = db.Column(db.String(20), nullable=False, default='standard')
    # standard, automatic, proxy

    notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Foreign keys
    auction_id = db.Column(db.Integer, db.ForeignKey('auctions.id'), nullable=False)
    bidder_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @property
    def bid_type_label(self):
        """Return human-readable bid type"""
        type_map = {
            'standard': 'Standard',
            'automatic': 'Automatica',
            'proxy': 'Proxy'
        }
        return type_map.get(self.bid_type, self.bid_type)

    def to_dict(self):
        """Convert bid to dictionary"""
        return {
            'id': self.id,
            'amount': float(self.amount),
            'is_winning': self.is_winning,
            'is_valid': self.is_valid,
            'bid_type': self.bid_type,
            'bid_type_label': self.bid_type_label,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'bidder_name': self.bidder.full_name if self.bidder else None,
            'auction_number': self.auction.auction_number if self.auction else None
        }

    def __repr__(self):
        return f'<Bid €{self.amount} by {self.bidder.full_name if self.bidder else "Unknown"}>'