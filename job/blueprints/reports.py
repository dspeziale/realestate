# blueprints/reports.py - Reports Blueprint
# Copyright 2025 SILICONDEV SPA
# Reports and analytics functionality

import logging
import csv
import io
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, make_response, flash, redirect, url_for
from database import db
from models import TimeEntry, Project, TimesheetStats
from sqlalchemy import func, extract, desc

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


@reports_bp.route('/')
def index():
    """Reports dashboard"""
    try:
        # Quick stats
        today_stats = TimesheetStats.get_daily_stats()
        week_stats = TimesheetStats.get_weekly_stats()
        project_stats = TimesheetStats.get_project_stats()

        # This month stats
        today = date.today()
        first_day = today.replace(day=1)
        month_entries = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) >= first_day
        ).all()

        month_hours = sum([e.duration_minutes for e in month_entries if e.duration_minutes]) / 60
        month_earnings = sum([e.earnings for e in month_entries])

        overview_stats = {
            'today': today_stats,
            'week': week_stats,
            'month': {
                'hours': round(month_hours, 2),
                'earnings': round(month_earnings, 2),
                'entries': len(month_entries)
            },
            'top_projects': project_stats[:5]  # Top 5 projects
        }

        return render_template('reports/index.html', stats=overview_stats)

    except Exception as e:
        logger.error(f"Error loading reports index: {str(e)}")
        flash(f'Errore nel caricamento dei report: {str(e)}', 'error')
        return render_template('reports/index.html', stats={})


@reports_bp.route('/time-range', methods=['GET', 'POST'])
def time_range_report():
    """Detailed report for custom time range"""
    try:
        # Default to current month
        today = date.today()
        default_start = today.replace(day=1)
        default_end = today

        start_date = default_start
        end_date = default_end

        if request.method == 'POST':
            start_date_str = request.form.get('start_date')
            end_date_str = request.form.get('end_date')

            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Get entries in range
        entries = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) >= start_date,
            func.date(TimeEntry.start_time) <= end_date
        ).order_by(desc(TimeEntry.start_time)).all()

        # Calculate totals
        total_minutes = sum([e.duration_minutes for e in entries if e.duration_minutes])
        total_hours = round(total_minutes / 60, 2)
        total_earnings = sum([e.earnings for e in entries])

        # Group by project
        project_breakdown = {}
        for entry in entries:
            project_id = entry.project_id
            if project_id not in project_breakdown:
                project_breakdown[project_id] = {
                    'project': entry.project,
                    'entries': [],
                    'total_minutes': 0,
                    'total_earnings': 0
                }

            project_breakdown[project_id]['entries'].append(entry)
            if entry.duration_minutes:
                project_breakdown[project_id]['total_minutes'] += entry.duration_minutes
            project_breakdown[project_id]['total_earnings'] += entry.earnings

        # Convert to list and add calculated fields
        project_list = []
        for project_data in project_breakdown.values():
            project_data['total_hours'] = round(project_data['total_minutes'] / 60, 2)
            project_data['entries_count'] = len(project_data['entries'])
            project_list.append(project_data)

        # Sort by hours desc
        project_list.sort(key=lambda x: x['total_hours'], reverse=True)

        # Group by day for daily chart
        daily_breakdown = {}
        for entry in entries:
            day_key = entry.start_time.date()
            if day_key not in daily_breakdown:
                daily_breakdown[day_key] = {
                    'date': day_key,
                    'hours': 0,
                    'entries': 0,
                    'earnings': 0
                }

            if entry.duration_minutes:
                daily_breakdown[day_key]['hours'] += entry.duration_minutes / 60
            daily_breakdown[day_key]['entries'] += 1
            daily_breakdown[day_key]['earnings'] += entry.earnings

        daily_list = sorted(daily_breakdown.values(), key=lambda x: x['date'], reverse=True)

        report_data = {
            'start_date': start_date,
            'end_date': end_date,
            'total_entries': len(entries),
            'total_hours': total_hours,
            'total_earnings': round(total_earnings, 2),
            'project_breakdown': project_list,
            'daily_breakdown': daily_list,
            'entries': entries[:100]  # Limit for display
        }

        return render_template('reports/time_range.html', report=report_data)

    except Exception as e:
        logger.error(f"Error generating time range report: {str(e)}")
        flash(f'Errore nella generazione del report: {str(e)}', 'error')
        return redirect(url_for('reports.index'))


@reports_bp.route('/project/<int:project_id>')
def project_report(project_id):
    """Detailed report for a specific project"""
    try:
        project = Project.query.get_or_404(project_id)

        # Get all entries for this project
        entries = TimeEntry.query.filter_by(project_id=project_id).order_by(
            desc(TimeEntry.start_time)
        ).all()

        # Calculate totals
        total_minutes = sum([e.duration_minutes for e in entries if e.duration_minutes])
        total_hours = round(total_minutes / 60, 2)
        total_earnings = round(total_hours * project.hourly_rate, 2)

        # Group by month
        monthly_data = {}
        for entry in entries:
            month_key = entry.start_time.strftime('%Y-%m')
            month_name = entry.start_time.strftime('%B %Y')

            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    'month': month_name,
                    'hours': 0,
                    'entries': 0,
                    'earnings': 0
                }

            if entry.duration_minutes:
                monthly_data[month_key]['hours'] += entry.duration_minutes / 60
            monthly_data[month_key]['entries'] += 1
            monthly_data[month_key]['earnings'] += entry.earnings

        monthly_list = sorted(monthly_data.values(), key=lambda x: x['month'], reverse=True)

        # Group by day of week
        weekday_data = {
            i: {'day': ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'][i], 'hours': 0,
                'entries': 0} for i in range(7)}

        for entry in entries:
            weekday = entry.start_time.weekday()
            if entry.duration_minutes:
                weekday_data[weekday]['hours'] += entry.duration_minutes / 60
            weekday_data[weekday]['entries'] += 1

        # Average session duration
        avg_session = round(total_hours / len(entries), 2) if entries else 0

        # Most productive time (hour of day)
        hourly_data = {i: 0 for i in range(24)}
        for entry in entries:
            hour = entry.start_time.hour
            if entry.duration_minutes:
                hourly_data[hour] += entry.duration_minutes / 60

        peak_hour = max(hourly_data.items(), key=lambda x: x[1])

        report_data = {
            'project': project,
            'total_entries': len(entries),
            'total_hours': total_hours,
            'total_earnings': total_earnings,
            'avg_session_hours': avg_session,
            'peak_hour': f"{peak_hour[0]:02d}:00" if peak_hour[1] > 0 else "N/A",
            'monthly_breakdown': monthly_list,
            'weekday_breakdown': list(weekday_data.values()),
            'recent_entries': entries[:20]
        }

        return render_template('reports/project_detail.html', report=report_data)

    except Exception as e:
        logger.error(f"Error generating project report: {str(e)}")
        flash(f'Errore nella generazione del report progetto: {str(e)}', 'error')
        return redirect(url_for('reports.index'))


@reports_bp.route('/export/csv')
def export_csv():
    """Export time entries to CSV"""
    try:
        # Get date range from query params
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        project_id = request.args.get('project_id', type=int)

        # Default to current month
        today = date.today()
        start_date = today.replace(day=1)
        end_date = today

        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # Build query
        query = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) >= start_date,
            func.date(TimeEntry.start_time) <= end_date
        )

        if project_id:
            query = query.filter_by(project_id=project_id)

        entries = query.order_by(TimeEntry.start_time).all()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow([
            'Data', 'Ora Inizio', 'Ora Fine', 'Durata (ore)',
            'Progetto', 'Descrizione', 'Tag', 'Tariffa Oraria', 'Guadagno'
        ])

        # Write data
        for entry in entries:
            writer.writerow([
                entry.start_time.strftime('%Y-%m-%d'),
                entry.start_time.strftime('%H:%M'),
                entry.end_time.strftime('%H:%M') if entry.end_time else 'In corso',
                entry.duration_hours,
                entry.project.name,
                entry.description,
                entry.tags or '',
                entry.project.hourly_rate,
                entry.earnings
            ])

        # Prepare response
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'

        filename = f"timesheet_{start_date}_{end_date}.csv"
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}")
        flash(f'Errore nell\'esportazione CSV: {str(e)}', 'error')
        return redirect(url_for('reports.index'))


@reports_bp.route('/analytics')
def analytics():
    """Advanced analytics page"""
    try:
        # Last 12 months data
        twelve_months_ago = date.today() - timedelta(days=365)

        entries = TimeEntry.query.filter(
            func.date(TimeEntry.start_time) >= twelve_months_ago
        ).all()

        # Monthly trends
        monthly_trends = {}
        for entry in entries:
            month_key = entry.start_time.strftime('%Y-%m')
            if month_key not in monthly_trends:
                monthly_trends[month_key] = {'hours': 0, 'earnings': 0, 'entries': 0}

            if entry.duration_minutes:
                monthly_trends[month_key]['hours'] += entry.duration_minutes / 60
            monthly_trends[month_key]['earnings'] += entry.earnings
            monthly_trends[month_key]['entries'] += 1

        # Project performance
        project_performance = {}
        for entry in entries:
            project_id = entry.project_id
            if project_id not in project_performance:
                project_performance[project_id] = {
                    'project': entry.project,
                    'hours': 0,
                    'earnings': 0,
                    'entries': 0,
                    'avg_session': 0
                }

            if entry.duration_minutes:
                project_performance[project_id]['hours'] += entry.duration_minutes / 60
            project_performance[project_id]['earnings'] += entry.earnings
            project_performance[project_id]['entries'] += 1

        # Calculate averages
        for data in project_performance.values():
            if data['entries'] > 0:
                data['avg_session'] = round(data['hours'] / data['entries'], 2)

        # Time patterns (hour of day)
        hourly_patterns = {i: 0 for i in range(24)}
        for entry in entries:
            if entry.duration_minutes:
                hourly_patterns[entry.start_time.hour] += entry.duration_minutes / 60

        # Day of week patterns
        daily_patterns = {i: 0 for i in range(7)}
        for entry in entries:
            if entry.duration_minutes:
                daily_patterns[entry.start_time.weekday()] += entry.duration_minutes / 60

        analytics_data = {
            'monthly_trends': monthly_trends,
            'project_performance': list(project_performance.values()),
            'hourly_patterns': hourly_patterns,
            'daily_patterns': daily_patterns,
            'total_entries': len(entries),
            'date_range': {
                'start': twelve_months_ago,
                'end': date.today()
            }
        }

        return render_template('reports/analytics.html', analytics=analytics_data)

    except Exception as e:
        logger.error(f"Error generating analytics: {str(e)}")
        flash(f'Errore nella generazione delle analisi: {str(e)}', 'error')
        return redirect(url_for('reports.index'))