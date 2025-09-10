# Copyright 2025 SILICONDEV SPA
# Filename: utils/template_helpers.py
# Description: Template filters and context processors

from datetime import datetime
from flask import current_app
from flask_login import current_user


def register_template_filters(app):
    """Register custom template filters"""

    @app.template_filter('datetime')
    def datetime_filter(value, format='%d/%m/%Y %H:%M'):
        """Format datetime objects"""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value

        if value is None:
            return ''

        return value.strftime(format)

    @app.template_filter('date')
    def date_filter(value, format='%d/%m/%Y'):
        """Format date objects"""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value

        if value is None:
            return ''

        return value.strftime(format)

    @app.template_filter('currency')
    def currency_filter(value):
        """Format currency values"""
        if value is None:
            return '€0,00'

        try:
            return f"€{float(value):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except (ValueError, TypeError):
            return '€0,00'

    @app.template_filter('percentage')
    def percentage_filter(value, decimals=1):
        """Format percentage values"""
        if value is None:
            return '0%'

        try:
            return f"{float(value):.{decimals}f}%"
        except (ValueError, TypeError):
            return '0%'

    @app.template_filter('truncate_words')
    def truncate_words_filter(text, length=20, suffix='...'):
        """Truncate text by word count"""
        if not text:
            return ''

        words = text.split()
        if len(words) <= length:
            return text

        return ' '.join(words[:length]) + suffix

    @app.template_filter('pluralize')
    def pluralize_filter(count, singular, plural=None):
        """Pluralize words based on count"""
        if count == 1:
            return singular

        if plural is None:
            # Simple Italian pluralization rules
            if singular.endswith('a'):
                plural = singular[:-1] + 'e'
            elif singular.endswith('e'):
                plural = singular[:-1] + 'i'
            elif singular.endswith('o'):
                plural = singular[:-1] + 'i'
            else:
                plural = singular + 'i'

        return plural

    @app.template_filter('time_remaining')
    def time_remaining_filter(end_time):
        """Calculate and format time remaining"""
        if not end_time:
            return None

        if isinstance(end_time, str):
            try:
                end_time = datetime.fromisoformat(end_time)
            except ValueError:
                return None

        now = datetime.utcnow()
        remaining = end_time - now

        if remaining.total_seconds() <= 0:
            return None

        days = remaining.days
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days} {'giorno' if days == 1 else 'giorni'}")
        if hours > 0:
            parts.append(f"{hours} {'ora' if hours == 1 else 'ore'}")
        if minutes > 0 and days == 0:
            parts.append(f"{minutes} {'minuto' if minutes == 1 else 'minuti'}")
        if seconds > 0 and days == 0 and hours == 0:
            parts.append(f"{seconds} {'secondo' if seconds == 1 else 'secondi'}")

        return ', '.join(parts[:2])  # Show only first 2 parts

    @app.template_filter('file_size')
    def file_size_filter(size_bytes):
        """Format file size in human readable format"""
        if not size_bytes:
            return '0 B'

        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0

        return f"{size_bytes:.1f} TB"


def register_context_processors(app):
    """Register context processors for templates"""

    @app.context_processor
    def inject_app_info():
        """Inject app information into templates"""
        return {
            'app_name': 'AsteImmobili',
            'app_version': '1.0.0',
            'current_year': datetime.now().year
        }

    @app.context_processor
    def inject_user_stats():
        """Inject user statistics if admin"""
        if current_user.is_authenticated and current_user.is_admin:
            try:
                from models.user import User
                from models.property import Property
                from models.auction import Auction, Bid

                return {
                    'total_users': User.query.count(),
                    'total_properties': Property.query.count(),
                    'total_auctions': Auction.query.count(),
                    'total_bids': Bid.query.count()
                }
            except Exception as e:
                # In case of database errors, return zeros
                app.logger.error(f"Error getting stats: {str(e)}")
                return {
                    'total_users': 0,
                    'total_properties': 0,
                    'total_auctions': 0,
                    'total_bids': 0
                }

        return {}

    @app.context_processor
    def inject_current_year():
        """Inject current year"""
        from datetime import datetime
        return {'current_year': datetime.now().year}

    @app.context_processor
    def inject_navigation():
        """Inject navigation helpers"""
        return {
            'nav_items': [
                {
                    'name': 'Dashboard',
                    'endpoint': 'index',
                    'icon': 'house-door',
                    'admin_only': False
                },
                {
                    'name': 'Immobili',
                    'endpoint': 'properties.index',
                    'icon': 'building',
                    'admin_only': False
                },
                {
                    'name': 'Aste',
                    'endpoint': 'auctions.index',
                    'icon': 'hammer',
                    'admin_only': False
                },
                {
                    'name': 'Utenti',
                    'endpoint': 'users.index',
                    'icon': 'people',
                    'admin_only': True
                }
            ]
        }

    @app.context_processor
    def inject_constants():
        """Inject useful constants"""
        return {
            'PROPERTY_TYPES': [
                ('apartment', 'Appartamento'),
                ('villa', 'Villa'),
                ('house', 'Casa'),
                ('office', 'Ufficio'),
                ('commercial', 'Commerciale'),
                ('industrial', 'Industriale'),
                ('land', 'Terreno'),
                ('garage', 'Garage'),
                ('other', 'Altro')
            ],
            'PROPERTY_CONDITIONS': [
                ('excellent', 'Ottimo'),
                ('good', 'Buono'),
                ('fair', 'Discreto'),
                ('poor', 'Da ristrutturare'),
                ('to_renovate', 'Da rifare')
            ],
            'ENERGY_CLASSES': ['A+', 'A', 'B', 'C', 'D', 'E', 'F', 'G'],
            'ITALIAN_REGIONS': [
                'Abruzzo', 'Basilicata', 'Calabria', 'Campania', 'Emilia-Romagna',
                'Friuli-Venezia Giulia', 'Lazio', 'Liguria', 'Lombardia', 'Marche',
                'Molise', 'Piemonte', 'Puglia', 'Sardegna', 'Sicilia', 'Toscana',
                'Trentino-Alto Adige', 'Umbria', 'Valle d\'Aosta', 'Veneto'
            ]
        }