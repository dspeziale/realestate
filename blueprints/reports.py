# blueprints/reports.py - VERSIONE COMPLETA CON TUTTI I REPORT FUNZIONANTI

from flask import Blueprint, render_template, current_app, request, jsonify, send_file, flash
from datetime import datetime, timedelta
from core.traccar_framework import TraccarException
import io
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER

reports_bp = Blueprint('reports', __name__, template_folder='../templates')


@reports_bp.route('/')
def index():
    """Pagina principale report"""
    traccar = current_app.config['TRACCAR_API']

    try:
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
            # Route Report = Positions nel periodo
            result = []
            for device_id in device_ids:
                try:
                    positions = traccar.positions.get_positions(
                        device_id=device_id,
                        from_time=from_date,
                        to_time=to_date
                    )

                    # Ottieni nome device
                    devices = traccar.devices.get_devices()
                    device = next((d for d in devices if d['id'] == device_id), None)
                    device_name = device['name'] if device else f'Device {device_id}'

                    # Aggiungi nome device a ogni posizione
                    for pos in positions:
                        pos['deviceName'] = device_name
                        result.append(pos)

                except Exception as e:
                    print(f"Error getting positions for device {device_id}: {e}")

            # Ordina per timestamp
            result.sort(key=lambda x: x.get('deviceTime', x.get('serverTime', '')))

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
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/export/csv/<report_type>', methods=['POST'])
def export_csv(report_type):
    """Esporta report in CSV"""
    data = request.get_json()
    report_data = data.get('data', [])

    if not report_data:
        return jsonify({'error': 'No data to export'}), 400

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

    elif report_type == 'stops':
        writer = csv.DictWriter(output, fieldnames=[
            'deviceName', 'startTime', 'endTime', 'duration', 'address', 'lat', 'lon'
        ])
        writer.writeheader()
        writer.writerows(report_data)

    elif report_type == 'route':
        writer = csv.DictWriter(output, fieldnames=[
            'deviceName', 'deviceTime', 'latitude', 'longitude', 'speed', 'course', 'altitude'
        ])
        writer.writeheader()
        # Scrivi solo i campi necessari
        for row in report_data:
            writer.writerow({
                'deviceName': row.get('deviceName', ''),
                'deviceTime': row.get('deviceTime', row.get('serverTime', '')),
                'latitude': row.get('latitude', ''),
                'longitude': row.get('longitude', ''),
                'speed': row.get('speed', 0),
                'course': row.get('course', 0),
                'altitude': row.get('altitude', 0)
            })

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


@reports_bp.route('/export/pdf/<report_type>', methods=['POST'])
def export_pdf(report_type):
    """Esporta report in PDF"""
    data = request.get_json()
    report_data = data.get('data', [])
    from_date = data.get('from_date', '')
    to_date = data.get('to_date', '')

    if not report_data:
        return jsonify({'error': 'No data to export'}), 400

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            rightMargin=30, leftMargin=30,
                            topMargin=30, bottomMargin=30)

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=30,
        alignment=TA_CENTER
    )

    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=20,
        alignment=TA_CENTER
    )

    # Titolo
    title = Paragraph(f"Fleet Manager Pro - {report_type.title()} Report", title_style)
    elements.append(title)

    # Periodo
    period_text = f"Period: {from_date[:10]} to {to_date[:10]} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    subtitle = Paragraph(period_text, subtitle_style)
    elements.append(subtitle)
    elements.append(Spacer(1, 20))

    # Prepara tabella dati
    if report_type == 'summary':
        table_data = [['Vehicle', 'Distance (km)', 'Max Speed (km/h)', 'Avg Speed (km/h)', 'Engine Hours']]
        for item in report_data:
            table_data.append([
                item.get('deviceName', 'N/A'),
                f"{item.get('distance', 0) / 1000:.2f}",
                f"{item.get('maxSpeed', 0) * 1.852:.1f}",
                f"{item.get('averageSpeed', 0) * 1.852:.1f}",
                f"{item.get('engineHours', 0):.1f}"
            ])

    elif report_type == 'trips':
        table_data = [['Vehicle', 'Start Time', 'End Time', 'Distance (km)', 'Duration (min)', 'Max Speed (km/h)']]
        for item in report_data:
            start_time = datetime.fromisoformat(item.get('startTime', '').replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(item.get('endTime', '').replace('Z', '+00:00'))

            table_data.append([
                item.get('deviceName', 'N/A'),
                start_time.strftime('%Y-%m-%d %H:%M'),
                end_time.strftime('%Y-%m-%d %H:%M'),
                f"{item.get('distance', 0) / 1000:.2f}",
                f"{item.get('duration', 0) / 60000:.0f}",
                f"{item.get('maxSpeed', 0) * 1.852:.1f}"
            ])

    elif report_type == 'stops':
        table_data = [['Vehicle', 'Start Time', 'End Time', 'Duration (min)', 'Address']]
        for item in report_data:
            start_time = datetime.fromisoformat(item.get('startTime', '').replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(item.get('endTime', '').replace('Z', '+00:00'))

            table_data.append([
                item.get('deviceName', 'N/A'),
                start_time.strftime('%Y-%m-%d %H:%M'),
                end_time.strftime('%Y-%m-%d %H:%M'),
                f"{item.get('duration', 0) / 60000:.0f}",
                item.get('address', 'N/A')[:40]
            ])

    elif report_type == 'route':
        table_data = [['Vehicle', 'Time', 'Latitude', 'Longitude', 'Speed (km/h)', 'Altitude (m)']]
        # Limita a max 500 righe per PDF
        for item in report_data[:500]:
            device_time = item.get('deviceTime', item.get('serverTime', ''))
            if device_time:
                try:
                    dt = datetime.fromisoformat(device_time.replace('Z', '+00:00'))
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = device_time[:19]
            else:
                time_str = 'N/A'

            table_data.append([
                item.get('deviceName', 'N/A'),
                time_str,
                f"{item.get('latitude', 0):.6f}",
                f"{item.get('longitude', 0):.6f}",
                f"{item.get('speed', 0) * 1.852:.1f}",
                f"{item.get('altitude', 0):.0f}"
            ])

    else:
        table_data = [['Data']]
        for item in report_data[:100]:
            table_data.append([str(item)[:80]])

    # Crea tabella
    table = Table(table_data)

    # Stile tabella
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))

    elements.append(table)

    # Footer
    elements.append(Spacer(1, 30))
    footer_text = f"Total Records: {len(report_data)} | Fleet Manager Pro © {datetime.now().year}"
    footer = Paragraph(footer_text, subtitle_style)
    elements.append(footer)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{report_type}_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
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
        from_time = datetime.now() - timedelta(days=7)
        to_time = datetime.now()

        weekly_data = []
        for device in devices[:5]:
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