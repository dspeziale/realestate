# blueprints/timesheet.py - Timesheet Blueprint
# Copyright 2025 SILICONDEV SPA
# Main timesheet functionality

import logging
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from models import db, TimeEntry, Project, TimesheetStats
from sqlalchemy import func, desc

logger = logging.getLogger(__name__)

timesheet_bp = Blueprint('timesheet', __name__, url_prefix='/timesheet')


@timesheet_bp.route('/')
def index():
    """Main timesheet page"""
    try:
        # Get today's entries
        today_stats = TimesheetStats.get_daily_stats()

        # Get active projects for quick selection
        active_projects = Project.query.filter_by(is_active=True).order_by(Project.name).all()

        # Get running entry if any
        running_entry = TimeEntry.get_running_entry()

        # Recent entries (last 10)
        recent_entries = TimeEntry.query.order_by(desc(TimeEntry.created_at)).limit(10).all()

        return render_template('timesheet/index.html',
                               today_stats=today_stats,
                               active_projects=active_projects,
                               running_entry=running_entry,
                               recent_entries=recent_entries)
    except Exception as e:
        logger.error(f"Error loading timesheet index: {str(e)}")
        flash(f'Errore nel caricamento del timesheet: {str(e)}', 'error')
        return render_template('timesheet/index.html',
                               today_stats={},
                               active_projects=[],
                               running_entry=None,
                               recent_entries=[])


@timesheet_bp.route('/start', methods=['POST'])
def start_timer():
    """Start a new timer"""
    try:
        # Stop any running timers first
        TimeEntry.stop_all_running()

        project_id = request.json.get('project_id')
        description = request.json.get('description', '').strip()

        if not project_id or not description:
            return jsonify({'success': False, 'message': 'Progetto e descrizione sono obbligatori'})

        # Verify project exists
        project = Project.query.get(project_id)
        if not project:
            return jsonify({'success': False, 'message': 'Progetto non trovato'})

        # Create new entry
        entry = TimeEntry(
            project_id=project_id,
            description=description,
            start_time=datetime.now(),
            is_running=True
        )

        db.session.add(entry)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Timer avviato per {project.name}',
            'entry_id': entry.id
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error starting timer: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore nell\'avvio del timer: {str(e)}'})


@timesheet_bp.route('/stop/<int:entry_id>', methods=['POST'])
def stop_timer(entry_id):
    """Stop a running timer"""
    try:
        entry = TimeEntry.query.get_or_404(entry_id)

        if not entry.is_running:
            return jsonify({'success': False, 'message': 'Questo timer non è attivo'})

        entry.stop_timer()
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Timer fermato. Durata: {entry.duration_display}',
            'duration': entry.duration_display,
            'earnings': entry.earnings
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error stopping timer: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore nel fermare il timer: {str(e)}'})


@timesheet_bp.route('/entry/<int:entry_id>')
def view_entry(entry_id):
    """View single entry details"""
    try:
        entry = TimeEntry.query.get_or_404(entry_id)
        return render_template('timesheet/entry_detail.html', entry=entry)
    except Exception as e:
        logger.error(f"Error viewing entry: {str(e)}")
        flash(f'Errore nel caricamento della voce: {str(e)}', 'error')
        return redirect(url_for('timesheet.index'))


@timesheet_bp.route('/entry/<int:entry_id>/edit', methods=['GET', 'POST'])
def edit_entry(entry_id):
    """Edit time entry"""
    try:
        entry = TimeEntry.query.get_or_404(entry_id)
        active_projects = Project.query.filter_by(is_active=True).order_by(Project.name).all()

        if request.method == 'POST':
            # Update entry
            entry.project_id = request.form.get('project_id')
            entry.description = request.form.get('description', '').strip()
            entry.tags = request.form.get('tags', '').strip()

            # Handle manual time input
            start_date = request.form.get('start_date')
            start_time = request.form.get('start_time')
            duration_hours = request.form.get('duration_hours', type=float)

            if start_date and start_time:
                start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
                entry.start_time = start_datetime

                if duration_hours and duration_hours > 0:
                    entry.duration_minutes = int(duration_hours * 60)
                    entry.end_time = start_datetime + timedelta(minutes=entry.duration_minutes)
                    entry.is_running = False

            db.session.commit()
            flash('Voce aggiornata con successo!', 'success')
            return redirect(url_for('timesheet.index'))

        return render_template('timesheet/edit_entry.html',
                               entry=entry,
                               active_projects=active_projects)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error editing entry: {str(e)}")
        flash(f'Errore nell\'aggiornamento: {str(e)}', 'error')
        return redirect(url_for('timesheet.index'))


@timesheet_bp.route('/entry/<int:entry_id>/delete', methods=['POST'])
def delete_entry(entry_id):
    """Delete time entry"""
    try:
        entry = TimeEntry.query.get_or_404(entry_id)
        db.session.delete(entry)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Voce eliminata con successo'})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting entry: {str(e)}")
        return jsonify({'success': False, 'message': f'Errore nell\'eliminazione: {str(e)}'})


@timesheet_bp.route('/quick-add', methods=['GET', 'POST'])
def quick_add():
    """Quick add manual time entry"""
    try:
        active_projects = Project.query.filter_by(is_active=True).order_by(Project.name).all()

        if request.method == 'POST':
            project_id = request.form.get('project_id')
            description = request.form.get('description', '').strip()
            start_date = request.form.get('start_date')
            start_time = request.form.get('start_time')
            duration_hours = request.form.get('duration_hours', type=float)
            tags = request.form.get('tags', '').strip()

            if not all([project_id, description, start_date, start_time, duration_hours]):
                flash('Tutti i campi sono obbligatori', 'error')
                return render_template('timesheet/quick_add.html', active_projects=active_projects)

            # Create datetime
            start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            duration_minutes = int(duration_hours * 60)
            end_datetime = start_datetime + timedelta(minutes=duration_minutes)

            # Create entry
            entry = TimeEntry(
                project_id=project_id,
                description=description,
                start_time=start_datetime,
                end_time=end_datetime,
                duration_minutes=duration_minutes,
                tags=tags,
                is_running=False
            )

            db.session.add(entry)
            db.session.commit()

            flash('Voce aggiunta con successo!', 'success')
            return redirect(url_for('timesheet.index'))

        # Default to today
        today = date.today()
        return render_template('timesheet/quick_add.html',
                               active_projects=active_projects,
                               default_date=today.strftime('%Y-%m-%d'))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in quick add: {str(e)}")
        flash(f'Errore nell\'aggiunta: {str(e)}', 'error')
        return redirect(url_for('timesheet.index'))


@timesheet_bp.route('/api/running-status')
def api_running_status():
    """API endpoint to get current running timer status"""
    try:
        running_entry = TimeEntry.get_running_entry()

        if running_entry:
            current_duration = running_entry.calculate_duration()
            hours = current_duration // 60
            minutes = current_duration % 60

            return jsonify({
                'is_running': True,
                'entry_id': running_entry.id,
                'project_name': running_entry.project.name,
                'description': running_entry.description,
                'start_time': running_entry.start_time.strftime('%H:%M'),
                'duration_minutes': current_duration,
                'duration_display': f"{hours:02d}:{minutes:02d}"
            })

        return jsonify({'is_running': False})

    except Exception as e:
        logger.error(f"Error getting running status: {str(e)}")
        return jsonify({'is_running': False, 'error': str(e)})


@timesheet_bp.route('/week/<path:week_start>')
def week_view(week_start):
    """View timesheet for a specific week"""
    try:
        start_date = datetime.strptime(week_start, '%Y-%m-%d').date()
        week_stats = TimesheetStats.get_weekly_stats(start_date)

        return render_template('timesheet/week_view.html', week_stats=week_stats)

    except Exception as e:
        logger.error(f"Error loading week view: {str(e)}")
        flash(f'Errore nel caricamento della settimana: {str(e)}', 'error')
        return redirect(url_for('timesheet.index'))