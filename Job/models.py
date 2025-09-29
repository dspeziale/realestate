# models.py - Timesheet Models with User Management
# Copyright 2025 SILICONDEV SPA
# SQLite Models for Python 3.13 - Complete with User System

from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
import enum

# Create a single SQLAlchemy instance
db = SQLAlchemy()


class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(db.Model, UserMixin):
    """User model for authentication and authorization"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255))
    first_name = db.Column(db.String(80))
    last_name = db.Column(db.String(80))
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    # OAuth fields
    provider = db.Column(db.String(50), default='local')  # 'local' or 'google'
    provider_id = db.Column(db.String(100))
    profile_picture = db.Column(db.String(500))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    last_login = db.Column(db.DateTime)

    # Relationships - Link user to their timesheet entries
    time_entries = db.relationship('TimeEntry', backref='user', lazy='dynamic')
    projects = db.relationship('Project', backref='owner', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username}>'

    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password against hash"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.username

    @property
    def display_name(self):
        """Get display name for UI"""
        return self.full_name or self.username

    @property
    def initials(self):
        """Get user initials for avatar"""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        return self.username[:2].upper()

    @property
    def is_admin(self):
        """Check if user is admin"""
        return self.role == UserRole.ADMIN

    @property
    def total_hours(self):
        """Get total hours logged by user"""
        total_minutes = db.session.query(func.sum(TimeEntry.duration_minutes)).filter(
            TimeEntry.user_id == self.id
        ).scalar()
        return round((total_minutes or 0) / 60, 2)

    @property
    def total_entries(self):
        """Get total number of time entries"""
        return self.time_entries.count()

    @property
    def projects_count(self):
        """Get number of projects owned by user"""
        return self.projects.count()

    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.now()
        db.session.commit()

    def get_recent_entries(self, limit=10):
        """Get user's recent time entries"""
        return TimeEntry.query.filter_by(user_id=self.id).order_by(
            TimeEntry.created_at.desc()
        ).limit(limit).all()

    def get_daily_stats(self, target_date=None):
        """Get user's daily timesheet stats"""
        return TimesheetStats.get_daily_stats_for_user(self.id, target_date)

    @staticmethod
    def create_user(username, email, password, **kwargs):
        """Create a new user"""
        user = User(
            username=username,
            email=email,
            first_name=kwargs.get('first_name', ''),
            last_name=kwargs.get('last_name', ''),
            role=kwargs.get('role', UserRole.USER),
            provider=kwargs.get('provider', 'local')
        )
        if password:
            user.set_password(password)

        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def get_by_email(email):
        """Get user by email"""
        return User.query.filter_by(email=email).first()

    @staticmethod
    def get_by_username(username):
        """Get user by username"""
        return User.query.filter_by(username=username).first()


class Project(db.Model):
    """Project model for timesheet"""
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#007bff')
    hourly_rate = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # User relationship
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for migration

    time_entries = db.relationship('TimeEntry', backref='project', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Project {self.name}>'

    @property
    def total_hours(self):
        total_minutes = db.session.query(func.sum(TimeEntry.duration_minutes)).filter(
            TimeEntry.project_id == self.id
        ).scalar()
        return round((total_minutes or 0) / 60, 2)

    @property
    def total_earnings(self):
        return round(self.total_hours * self.hourly_rate, 2)

    @property
    def entries_count(self):
        return self.time_entries.count()


class TimeEntry(db.Model):
    """Time entry model"""
    __tablename__ = 'time_entries'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)
    is_running = db.Column(db.Boolean, default=False)
    tags = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # User relationship
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Nullable for migration

    def __repr__(self):
        return f'<TimeEntry {self.id}: {self.description[:30]}>'

    @property
    def duration_hours(self):
        if self.duration_minutes:
            return round(self.duration_minutes / 60, 2)
        return 0.0

    @property
    def duration_display(self):
        if not self.duration_minutes:
            return "00:00"
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        return f"{hours:02d}:{minutes:02d}"

    @property
    def earnings(self):
        if self.project and self.project.hourly_rate:
            return round(self.duration_hours * self.project.hourly_rate, 2)
        return 0.0

    @property
    def tags_list(self):
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
        return []

    @property
    def is_today(self):
        return self.start_time.date() == datetime.now().date()

    def calculate_duration(self):
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            self.duration_minutes = int(delta.total_seconds() / 60)
            self.is_running = False
        elif self.start_time and self.is_running:
            delta = datetime.now() - self.start_time
            return int(delta.total_seconds() / 60)
        return self.duration_minutes or 0

    def stop_timer(self):
        if self.is_running:
            self.end_time = datetime.now()
            self.calculate_duration()
            return True
        return False

    @staticmethod
    def get_running_entry():
        return TimeEntry.query.filter_by(is_running=True).first()

    @staticmethod
    def stop_all_running():
        running_entries = TimeEntry.query.filter_by(is_running=True).all()
        for entry in running_entries:
            entry.stop_timer()
        db.session.commit()
        return len(running_entries)


class TimesheetStats:
    """Helper class for timesheet statistics"""

    @staticmethod
    def get_daily_stats(target_date=None, user_id=None):
        if not target_date:
            target_date = datetime.now().date()

        query = TimeEntry.query.filter(func.date(TimeEntry.start_time) == target_date)
        if user_id:
            query = query.filter_by(user_id=user_id)

        entries = query.all()

        total_minutes = sum([entry.duration_minutes for entry in entries if entry.duration_minutes])
        total_earnings = sum([entry.earnings for entry in entries])

        return {
            'date': target_date,
            'entries_count': len(entries),
            'total_hours': round(total_minutes / 60, 2) if total_minutes else 0,
            'total_earnings': round(total_earnings, 2),
            'entries': entries
        }

    @staticmethod
    def get_daily_stats_for_user(user_id, target_date=None):
        """Get daily stats for specific user"""
        return TimesheetStats.get_daily_stats(target_date, user_id)

    @staticmethod
    def get_weekly_stats(start_date=None, user_id=None):
        if not start_date:
            today = datetime.now().date()
            start_date = today - timedelta(days=today.weekday())

        end_date = start_date + timedelta(days=6)

        query = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) >= start_date,
            func.date(TimeEntry.start_time) <= end_date
        )
        if user_id:
            query = query.filter_by(user_id=user_id)

        entries = query.all()

        total_minutes = sum([entry.duration_minutes for entry in entries if entry.duration_minutes])
        total_earnings = sum([entry.earnings for entry in entries])

        daily_data = {}
        for i in range(7):
            current_date = start_date + timedelta(days=i)
            daily_entries = [e for e in entries if e.start_time.date() == current_date]
            daily_minutes = sum([e.duration_minutes for e in daily_entries if e.duration_minutes])

            daily_data[current_date] = {
                'entries_count': len(daily_entries),
                'hours': round(daily_minutes / 60, 2) if daily_minutes else 0,
                'entries': daily_entries
            }

        return {
            'start_date': start_date,
            'end_date': end_date,
            'total_hours': round(total_minutes / 60, 2) if total_minutes else 0,
            'total_earnings': round(total_earnings, 2),
            'entries_count': len(entries),
            'daily_data': daily_data
        }

    @staticmethod
    def get_project_stats(user_id=None):
        query = Project.query
        if user_id:
            query = query.filter_by(user_id=user_id)

        projects = query.filter_by(is_active=True).all()
        stats = []

        for project in projects:
            project_query = TimeEntry.query.filter_by(project_id=project.id)
            if user_id:
                project_query = project_query.filter_by(user_id=user_id)

            project_entries = project_query.all()
            total_minutes = sum([e.duration_minutes for e in project_entries if e.duration_minutes])

            stats.append({
                'project': project,
                'entries_count': len(project_entries),
                'total_hours': round(total_minutes / 60, 2) if total_minutes else 0,
                'total_earnings': project.total_earnings
            })

        return sorted(stats, key=lambda x: x['total_hours'], reverse=True)


def init_db(app):
    """Initialize the database with the Flask app"""
    db.init_app(app)

    with app.app_context():
        db.create_all()

        # Create sample projects only if no projects exist
        if Project.query.count() == 0:
            create_sample_projects()
            print("Sample projects created successfully")

        # Initialize user system
        init_user_system()


def init_user_system():
    """Initialize user system with default admin user"""
    # Create default admin user if no users exist
    if User.query.count() == 0:
        admin = User.create_user(
            username='admin',
            email='admin@timesheet.app',
            password='admin123',
            first_name='Admin',
            last_name='User',
            role=UserRole.ADMIN
        )
        print(f"Created default admin user: {admin.username}")
        print("Default password: admin123")

        # Assign orphaned data to admin
        TimeEntry.query.filter_by(user_id=None).update({'user_id': admin.id})
        Project.query.filter_by(user_id=None).update({'user_id': admin.id})
        db.session.commit()
        print("Assigned existing data to admin user")


def create_sample_projects():
    """Create sample projects"""
    sample_projects = [
        {
            'name': 'Sviluppo Web',
            'description': 'Progetto di sviluppo sito web aziendale',
            'color': '#007bff',
            'hourly_rate': 50.00
        },
        {
            'name': 'Consulenza IT',
            'description': 'Consulenza tecnica per cliente esterno',
            'color': '#28a745',
            'hourly_rate': 75.00
        },
        {
            'name': 'Formazione',
            'description': 'Ore dedicate alla formazione e aggiornamento',
            'color': '#ffc107',
            'hourly_rate': 0.00
        },
        {
            'name': 'Amministrazione',
            'description': 'Attività amministrative e gestionali',
            'color': '#6c757d',
            'hourly_rate': 40.00
        }
    ]

    for project_data in sample_projects:
        project = Project(
            name=project_data['name'],
            description=project_data['description'],
            color=project_data['color'],
            hourly_rate=project_data['hourly_rate'],
            is_active=True,
            user_id=None  # Will be assigned to admin during init_user_system
        )
        db.session.add(project)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error creating sample data: {str(e)}")