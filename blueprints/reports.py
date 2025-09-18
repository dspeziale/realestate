# blueprints/reports.py - VERSIONE COMPLETA RIDEFINITA

from flask import Blueprint, render_template, current_app, request, jsonify, send_file
from datetime import datetime, timedelta
from core.traccar_framework import TraccarException
import io
import csv

reports_bp = Blueprint('reports', __name__, template_folder='../templates')


@reports_bp.route('/')
def index():
    """Pagina principale report"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Carica lista veicoli per i filtri
        devices = traccar.devices.get_devices()
        return render_template('reports/index.html', vehicles=devices)
    except TraccarException as e:
        flash(f'Error loading vehicles: {str(e)}', 'error')
        return render_template('reports/index.html', vehicles=[])


@reports_bp.route('/generate', methods=['POST'])
def generate():
    """Genera report in base ai parametri"""
    traccar = current_app.config['TRACCAR_API']

    data = request.get_json()
    report_type = data.get('type')
    device_ids = data.get('device_ids', [])
    from_date = datetime.fromisoformat(data.get('from'))
    to_date = datetime.fromisoformat(data.get('to'))

    try:
        if report_type == 'summary':
            result = traccar.reports.get_summary_report(
                device_ids=device_ids,
                from_time=from_date,
                to_time=to_date
            )

        elif report_type == 'trips':
            result = traccar.reports.get_trips_report(
                device_ids=device_ids,
                from_time=from_date,
                to_time=to_date
            )

        elif report_type == 'stops':
            result = traccar.reports.get_stops_report(
                device_ids=device_ids,
                from_time=from_date,
                to_time=to_date
            )

        elif report_type == 'route':
            result = traccar.reports.get_route_report(
                device_ids=device_ids,
                from_time=from_date,
                to_time=to_date
            )

        else:
            return jsonify({'error': 'Invalid report type'}), 400

        return jsonify({
            'success': True,
            'data': result,
            'count': len(result),
            'report_type': report_type,
            'from_date': from_date.isoformat(),
            'to_date': to_date.isoformat()
        })

    except TraccarException as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/export/<report_type>', methods=['POST'])
def export(report_type):
    """Esporta report in CSV"""
    data = request.get_json()
    report_data = data.get('data', [])

    if not report_data:
        return jsonify({'error': 'No data to export'}), 400

    # Crea CSV in memoria
    output = io.StringIO()

    if report_type == 'summary':
        writer = csv.DictWriter(output, fieldnames=[
            'deviceName', 'distance', 'maxSpeed', 'averageSpeed', 'spentFuel', 'engineHours'
        ])
        writer.writeheader()
        writer.writerows(report_data)

    elif report_type == 'trips':
        writer = csv.DictWriter(output, fieldnames=[
            'deviceName', 'startTime', 'endTime', 'distance', 'duration',
            'maxSpeed', 'averageSpeed', 'startAddress', 'endAddress'
        ])
        writer.writeheader()
        writer.writerows(report_data)

    # Converti in BytesIO per il download
    output.seek(0)
    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)

    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{report_type}_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )


@reports_bp.route('/scheduled')
def scheduled():
    """Report programmati"""
    return render_template('reports/scheduled.html')


@reports_bp.route('/analytics')
def analytics():
    """Dashboard analytics avanzato"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()

        # Calcola statistiche per ultima settimana
        from_time = datetime.now() - timedelta(days=7)
        to_time = datetime.now()

        weekly_data = []
        for device in devices[:5]:  # Top 5 veicoli
            try:
                summary = traccar.reports.get_summary_report(
                    device_ids=[device['id']],
                    from_time=from_time,
                    to_time=to_time
                )
                if summary:
                    weekly_data.append(summary[0])
            except:
                pass

        return render_template('reports/analytics.html',
                               devices=devices,
                               weekly_data=weekly_data)

    except TraccarException as e:
        flash(f'Error loading analytics: {str(e)}', 'error')
        return render_template('reports/analytics.html',
                               devices=[],
                               weekly_data=[])
