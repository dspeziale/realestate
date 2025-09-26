# blueprints/projects.py - Projects Management Blueprint
# Copyright 2025 SILICONDEV SPA
# Project management functionality

import logging
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from database import db
from models import Project, TimeEntry
from sqlalchemy import func

logger = logging.getLogger(__name__)

projects_bp = Blueprint('projects', __name__, url_prefix='/projects')


@projects_bp.route('/')
def index():
    """List all projects"""
    try:
        # Get projects with statistics
        projects = Project.query.order_by(Project.is_active.desc(), Project.name).all()

        # Calculate statistics for each project
        project_stats = []
        for project in projects:
            entries_count = TimeEntry.query.filter_by(project_id=project.id).count()
            total_minutes = db.session.query(func.sum(TimeEntry.duration_minutes)).filter(
                TimeEntry.project_id == project.id
            ).scalar() or 0

            project_stats.append({
                'project': project,
                'entries_count': entries_count,
                'total_hours': round(total_minutes / 60, 2),
                'total_earnings': round((total_minutes / 60) * project.hourly_rate, 2)
            })

        return render_template('projects/index.html', project_stats=project_stats)

    except Exception as e:
        logger.error(f"Error loading projects: {str(e)}")
        flash(f'Errore nel caricamento dei progetti: {str(e)}', 'error')
        return render_template('projects/index.html', project_stats=[])


@projects_bp.route('/create', methods=['GET', 'POST'])
def create():
    """Create new project"""
    try:
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            color = request.form.get('color', '#007bff')
            hourly_rate = request.form.get('hourly_rate', type=float, default=0.0)
            is_active = bool(request.form.get('is_active'))

            if not name:
                flash('Il nome del progetto è obbligatorio', 'error')
                return render_template('projects/form.html')

            # Check if project name already exists
            existing = Project.query.filter_by(name=name).first()
            if existing:
                flash('Esiste già un progetto con questo nome', 'error')
                return render_template('projects/form.html')

            # Create project
            project = Project(
                name=name,
                description=description,
                color=color,
                hourly_rate=hourly_rate or 0.0,
                is_active=is_active
            )

            db.session.add(project)
            db.session.commit()

            flash('Progetto creato con successo!', 'success')
            return redirect(url_for('projects.index'))

        return render_template('projects/form.html', project=None)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating project: {str(e)}")
        flash(f'Errore nella creazione del progetto: {str(e)}', 'error')
        return render_template('projects/form.html', project=None)


@projects_bp.route('/<int:project_id>')
def view(project_id):
    """View project details"""
    try:
        project = Project.query.get_or_404(project_id)

        # Get project statistics
        entries = TimeEntry.query.filter_by(project_id=project_id).order_by(
            TimeEntry.start_time.desc()
        ).all()

        total_minutes = sum([e.duration_minutes for e in entries if e.duration_minutes])
        total_hours = round(total_minutes / 60, 2)
        total_earnings = round(total_hours * project.hourly_rate, 2)

        # Group entries by month for chart
        monthly_data = {}
        for entry in entries:
            if entry.start_time:
                month_key = entry.start_time.strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = {'hours': 0, 'entries': 0}

                if entry.duration_minutes:
                    monthly_data[month_key]['hours'] += entry.duration_minutes / 60
                monthly_data[month_key]['entries'] += 1

        # Recent entries (last 20)
        recent_entries = entries[:20]

        stats = {
            'total_entries': len(entries),
            'total_hours': total_hours,
            'total_earnings': total_earnings,
            'monthly_data': monthly_data,
            'avg_session_hours': round(total_hours / len(entries), 2) if entries else 0
        }

        return render_template('projects/detail.html',
                               project=project,
                               stats=stats,
                               recent_entries=recent_entries)

    except Exception as e:
        logger.error(f"Error viewing project: {str(e)}")
        flash(f'Errore nel caricamento del progetto: {str(e)}', 'error')
        return redirect(url_for('projects.index'))


@projects_bp.route('/<int:project_id>/edit', methods=['GET', 'POST'])
def edit(project_id):
    """Edit project"""
    try:
        project = Project.query.get_or_404(project_id)

        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            color = request.form.get('color', '#007bff')
            hourly_rate = request.form.get('hourly_rate', type=float, default=0.0)
            is_active = bool(request.form.get('is_active'))

            if not name:
                flash('Il nome del progetto è obbligatorio', 'error')
                return render_template('projects/form.html', project=project)

            # Check if name conflicts with other projects
            existing = Project.query.filter(
                Project.name == name,
                Project.id != project_id
            ).first()

            if existing:
                flash('Esiste già un progetto con questo nome', 'error')
                return render_template('projects/form.html', project=project)

            # Update project
            project.name = name
            project.description = description
            project.color = color
            project.hourly_rate = hourly_rate or 0.0
            project.is_active = is_active

            db.session.commit()

            flash('Progetto aggiornato con successo!', 'success')
            return redirect(url_for('projects.view', project_id=project.id))

        return render_template('projects/form.html', project=project)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error editing project: {str(e)}")
        flash(f'Errore nell\'aggiornamento del progetto: {str(e)}', 'error')
        return redirect(url_for('projects.index'))


@projects_bp.route('/<int:project_id>/delete', methods=['POST'])
def delete(project_id):
    """Delete project"""
    try:
        project = Project.query.get_or_404(project_id)

        # Check if project has time entries
        entries_count = TimeEntry.query.filter_by(project_id=project_id).count()

        if entries_count > 0:
            return jsonify({
                'success': False,
                'message': f'Non puoi eliminare il progetto "{project.name}" perché ha {entries_count} voci temporali associate. Disattivalo invece di eliminarlo.'
            })

        project_name = project.name
        db.session.delete(project)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Progetto "{project_name}" eliminato con successo'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting project: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Errore nell\'eliminazione del progetto: {str(e)}'
        })


@projects_bp.route('/<int:project_id>/toggle-status', methods=['POST'])
def toggle_status(project_id):
    """Toggle project active status"""
    try:
        project = Project.query.get_or_404(project_id)
        project.is_active = not project.is_active

        db.session.commit()

        status_text = "attivato" if project.is_active else "disattivato"

        return jsonify({
            'success': True,
            'message': f'Progetto "{project.name}" {status_text}',
            'is_active': project.is_active
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling project status: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Errore nel cambio di stato: {str(e)}'
        })


@projects_bp.route('/api/active')
def api_active_projects():
    """API endpoint to get active projects"""
    try:
        projects = Project.query.filter_by(is_active=True).order_by(Project.name).all()

        projects_data = []
        for project in projects:
            projects_data.append({
                'id': project.id,
                'name': project.name,
                'color': project.color,
                'hourly_rate': project.hourly_rate
            })

        return jsonify({'projects': projects_data})

    except Exception as e:
        logger.error(f"Error getting active projects: {str(e)}")
        return jsonify({'projects': [], 'error': str(e)})


@projects_bp.route('/archive')
def archive():
    """View archived/inactive projects"""
    try:
        archived_projects = Project.query.filter_by(is_active=False).order_by(Project.name).all()

        # Calculate statistics for archived projects
        project_stats = []
        for project in archived_projects:
            entries_count = TimeEntry.query.filter_by(project_id=project.id).count()
            total_minutes = db.session.query(func.sum(TimeEntry.duration_minutes)).filter(
                TimeEntry.project_id == project.id
            ).scalar() or 0

            project_stats.append({
                'project': project,
                'entries_count': entries_count,
                'total_hours': round(total_minutes / 60, 2),
                'total_earnings': round((total_minutes / 60) * project.hourly_rate, 2)
            })

        return render_template('projects/archive.html', project_stats=project_stats)

    except Exception as e:
        logger.error(f"Error loading archived projects: {str(e)}")
        flash(f'Errore nel caricamento dei progetti archiviati: {str(e)}', 'error')
        return render_template('projects/archive.html', project_stats=[])