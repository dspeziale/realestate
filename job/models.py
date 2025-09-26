# models.py - Timesheet Models
# Copyright 2025 SILICONDEV SPA
# SQLite Models for Python 3.13

from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# Create a single SQLAlchemy instance
db = SQLAlchemy()


class Project(db.Model):
    """Project model for timesheet"""
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#007bff')
    hourly_rate = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

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
    def get_daily_stats(target_date=None):
        if not target_date:
            target_date = datetime.now().date()

        entries = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) == target_date
        ).all()

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
    def get_weekly_stats(start_date=None):
        if not start_date:
            today = datetime.now().date()
            start_date = today - timedelta(days=today.weekday())

        end_date = start_date + timedelta(days=6)

        entries = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) >= start_date,
            func.date(TimeEntry.start_time) <= end_date
        ).all()

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
    def get_project_stats():
        projects = Project.query.filter_by(is_active=True).all()
        stats = []

        for project in projects:
            project_entries = TimeEntry.query.filter_by(project_id=project.id).all()
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

        if Project.query.count() == 0:
            create_sample_projects()
            print("Sample projects created successfully")


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
            is_active=True
        )
        db.session.add(project)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error creating sample data: {str(e)}")