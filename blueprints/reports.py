# blueprints/reports.py - VERSIONE POTENZIATA CON INDIRIZZI

from flask import Blueprint, render_template, current_app, request, jsonify, send_file, flash
from datetime import datetime, timedelta
from core.traccar_framework import TraccarException
import io
import csv
import json
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__, template_folder='../templates')


def get_address_for_coordinates(lat, lng, geocoding_service):
    """Ottieni indirizzo per coordinate usando il servizio geocoding"""
    if not geocoding_service or not lat or not lng:
        return 'Indirizzo non disponibile'

    try:
        address = geocoding_service.get_address_from_coordinates(lat, lng)
        if address:
            return address.formatted_address or 'Indirizzo non trovato'
        return 'Indirizzo non trovato'
    except Exception as e:
        logger.warning(f"Errore geocoding per {lat}, {lng}: {e}")
        return 'Errore geocoding'


def enhance_report_with_addresses(report_data, report_type, geocoding_service):
    """Arricchisce i dati del report con indirizzi"""
    if not report_data or not geocoding_service:
        return report_data

    enhanced_data = []

    for item in report_data:
        enhanced_item = item.copy()

        try:
            if report_type == 'trips':
                # Per i viaggi, aggiungi indirizzi di partenza e arrivo
                if 'startLat' in item and 'startLon' in item:
                    enhanced_item['startAddress'] = get_address_for_coordinates(
                        item['startLat'], item['startLon'], geocoding_service
                    )

                if 'endLat' in item and 'endLon' in item:
                    enhanced_item['endAddress'] = get_address_for_coordinates(
                        item['endLat'], item['endLon'], geocoding_service
                    )

            elif report_type == 'stops':
                # Per le soste, aggiungi indirizzo della sosta
                if 'latitude' in item and 'longitude' in item:
                    enhanced_item['address'] = get_address_for_coordinates(
                        item['latitude'], item['longitude'], geocoding_service
                    )

            elif report_type == 'route':
                # Per il percorso, aggiungi indirizzo per ogni posizione
                if 'latitude' in item and 'longitude' in item:
                    enhanced_item['address'] = get_address_for_coordinates(
                        item['latitude'], item['longitude'], geocoding_service
                    )

        except Exception as e:
            logger.warning(f"Errore arricchimento dati per item {item.get('id', 'unknown')}: {e}")

        enhanced_data.append(enhanced_item)

    return enhanced_data


@reports_bp.route('/')
def index():
    """Pagina principale report"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()
        groups = traccar.groups.get_groups()

        # Informazioni sul geocoding disponibile
        geocoding_available = current_app.config.get('GEOCODING_SERVICE') is not None

        return render_template('reports/index.html',
                               vehicles=devices,
                               groups=groups,
                               geocoding_available=geocoding_available)
    except TraccarException as e:
        flash(f'Error loading vehicles: {str(e)}', 'error')
        return render_template('reports/index.html', vehicles=[], groups=[], geocoding_available=False)


@reports_bp.route('/generate', methods=['POST'])
def generate():
    """Genera report in base ai parametri CON INDIRIZZI"""
    traccar = current_app.config['TRACCAR_API']
    geocoding_service = current_app.config.get('GEOCODING_SERVICE')

    data = request.get_json()
    report_type = data.get('type')
    device_ids = data.get('device_ids', [])
    from_date = datetime.fromisoformat(data.get('from'))
    to_date = datetime.fromisoformat(data.get('to'))
    include_addresses = data.get('include_addresses', True)

    try:
        logger.info(f"Generazione report {report_type} per dispositivi {device_ids}")

        if report_type == 'summary':
            result = traccar.reports.get_summary_report(
                device_ids=device_ids,
                from_time=from_date,
                to_time=to_date
            )

            # Per il summary, non aggiungiamo indirizzi specifici ma info generali
            if geocoding_service and include_addresses:
                logger.info(f"Report summary generato: {len(result)} record")

        elif report_type == 'trips':
            result = traccar.reports.get_trips_report(
                device_ids=device_ids,
                from_time=from_date,
                to_time=to_date
            )

            # Arricchisci viaggi con indirizzi
            if geocoding_service and include_addresses:
                logger.info(f"Arricchimento {len(result)} viaggi con indirizzi...")
                result = enhance_report_with_addresses(result, 'trips', geocoding_service)
                logger.info("Arricchimento viaggi completato")

        elif report_type == 'stops':
            result = traccar.reports.get_stops_report(
                device_ids=device_ids,
                from_time=from_date,
                to_time=to_date
            )

            # Arricchisci soste con indirizzi
            if geocoding_service and include_addresses:
                logger.info(f"Arricchimento {len(result)} soste con indirizzi...")
                result = enhance_report_with_addresses(result, 'stops', geocoding_service)
                logger.info("Arricchimento soste completato")

        elif report_type == 'route':
            result = traccar.reports.get_route_report(
                device_ids=device_ids,
                from_time=from_date,
                to_time=to_date
            )

            # Per il percorso, arricchisci solo alcuni punti per non sovraccaricare
            if geocoding_service and include_addresses and result:
                logger.info(f"Arricchimento percorso con {len(result)} posizioni...")
                # Prendi solo ogni 10° punto per evitare troppe chiamate
                route_sample = result[::10] if len(result) > 50 else result
                enhanced_sample = enhance_report_with_addresses(route_sample, 'route', geocoding_service)

                # Mappa gli indirizzi ai punti originali
                for i, item in enumerate(result):
                    if i % 10 == 0 and i // 10 < len(enhanced_sample):
                        item['address'] = enhanced_sample[i // 10].get('address', 'N/A')
                    else:
                        item['address'] = 'N/A'  # Non tutti i punti hanno indirizzi

                result = result
                logger.info("Arricchimento percorso completato")

        else:
            return jsonify({'error': f'Report type "{report_type}" not supported'}), 400

        # Aggiungi metadati al report
        report_metadata = {
            'report_type': report_type,
            'generated_at': datetime.now().isoformat(),
            'period_from': from_date.isoformat(),
            'period_to': to_date.isoformat(),
            'device_count': len(device_ids),
            'record_count': len(result) if result else 0,
            'addresses_included': include_addresses and geocoding_service is not None,
            'geocoding_available': geocoding_service is not None
        }

        return jsonify({
            'success': True,
            'data': result,
            'metadata': report_metadata
        })

    except TraccarException as e:
        logger.error(f"TraccarException in report generation: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        logger.error(f"Exception in report generation: {e}")
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500


@reports_bp.route('/export', methods=['POST'])
def export_report():
    """Esporta report in CSV o PDF CON INDIRIZZI"""
    data = request.get_json()
    report_data = data.get('data', [])
    report_type = data.get('type')
    format_type = data.get('format', 'csv')
    metadata = data.get('metadata', {})

    if not report_data:
        return jsonify({'error': 'No data to export'}), 400

    try:
        if format_type.lower() == 'csv':
            return export_csv(report_data, report_type, metadata)
        elif format_type.lower() == 'pdf':
            return export_pdf(report_data, report_type, metadata)
        else:
            return jsonify({'error': f'Format "{format_type}" not supported'}), 400

    except Exception as e:
        logger.error(f"Error exporting report: {e}")
        return jsonify({'error': str(e)}), 500


def export_csv(report_data, report_type, metadata):
    """Esporta report in formato CSV con indirizzi"""
    output = io.StringIO()

    if report_type == 'summary':
        fieldnames = ['deviceName', 'distance', 'maxSpeed', 'averageSpeed', 'engineHours', 'spentFuel']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for item in report_data:
            writer.writerow({
                'deviceName': item.get('deviceName', ''),
                'distance': f"{(item.get('distance', 0) / 1000):.2f} km",
                'maxSpeed': f"{(item.get('maxSpeed', 0) * 1.852):.1f} km/h",
                'averageSpeed': f"{(item.get('averageSpeed', 0) * 1.852):.1f} km/h",
                'engineHours': f"{(item.get('engineHours', 0) / 3600):.1f} h",
                'spentFuel': f"{item.get('spentFuel', 0):.2f} L"
            })

    elif report_type == 'trips':
        fieldnames = ['deviceName', 'startTime', 'endTime', 'distance', 'duration',
                      'averageSpeed', 'maxSpeed', 'startAddress', 'endAddress']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for item in report_data:
            writer.writerow({
                'deviceName': item.get('deviceName', ''),
                'startTime': item.get('startTime', ''),
                'endTime': item.get('endTime', ''),
                'distance': f"{(item.get('distance', 0) / 1000):.2f} km",
                'duration': f"{(item.get('duration', 0) / 60):.0f} min",
                'averageSpeed': f"{(item.get('averageSpeed', 0) * 1.852):.1f} km/h",
                'maxSpeed': f"{(item.get('maxSpeed', 0) * 1.852):.1f} km/h",
                'startAddress': item.get('startAddress', 'N/A'),
                'endAddress': item.get('endAddress', 'N/A')
            })

    elif report_type == 'stops':
        fieldnames = ['deviceName', 'startTime', 'endTime', 'duration',
                      'engineHours', 'spentFuel', 'address']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for item in report_data:
            writer.writerow({
                'deviceName': item.get('deviceName', ''),
                'startTime': item.get('startTime', ''),
                'endTime': item.get('endTime', ''),
                'duration': f"{(item.get('duration', 0) / 60):.0f} min",
                'engineHours': f"{(item.get('engineHours', 0) / 3600):.1f} h",
                'spentFuel': f"{item.get('spentFuel', 0):.2f} L",
                'address': item.get('address', 'N/A')
            })

    elif report_type == 'route':
        fieldnames = ['deviceName', 'timestamp', 'latitude', 'longitude',
                      'speed', 'course', 'altitude', 'address']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for item in report_data:
            writer.writerow({
                'deviceName': item.get('deviceName', ''),
                'timestamp': item.get('fixTime', item.get('deviceTime', '')),
                'latitude': f"{item.get('latitude', 0):.6f}",
                'longitude': f"{item.get('longitude', 0):.6f}",
                'speed': f"{(item.get('speed', 0) * 1.852):.1f} km/h",
                'course': f"{item.get('course', 0):.0f}°",
                'altitude': f"{item.get('altitude', 0):.0f} m",
                'address': item.get('address', 'N/A')
            })

    # Crea response
    output.seek(0)
    filename = f"report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    response = current_app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

    return response


def export_pdf(report_data, report_type, metadata):
    """Esporta report in formato PDF con indirizzi"""
    buffer = io.BytesIO()

    # Usa landscape per più spazio
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    # Stili
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        spaceAfter=30,
        alignment=TA_CENTER
    )

    story = []

    # Titolo
    title_text = f"Report {report_type.title()}"
    if metadata.get('addresses_included'):
        title_text += " (con Indirizzi)"
    story.append(Paragraph(title_text, title_style))

    # Metadati
    meta_data = [
        ['Periodo:', f"{metadata.get('period_from', 'N/A')} - {metadata.get('period_to', 'N/A')}"],
        ['Dispositivi:', str(metadata.get('device_count', 0))],
        ['Record:', str(metadata.get('record_count', 0))],
        ['Generato:', metadata.get('generated_at', 'N/A')],
        ['Indirizzi inclusi:', 'Sì' if metadata.get('addresses_included') else 'No']
    ]

    meta_table = Table(meta_data, colWidths=[100, 200])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
    ]))

    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Tabella dati
    if report_type == 'trips' and report_data:
        headers = ['Veicolo', 'Partenza', 'Arrivo', 'Distanza', 'Durata',
                   'Indirizzo Partenza', 'Indirizzo Arrivo']

        data = [headers]
        for item in report_data[:50]:  # Limita a 50 record per PDF
            row = [
                item.get('deviceName', '')[:20],  # Limita lunghezza
                item.get('startTime', '')[:16],
                item.get('endTime', '')[:16],
                f"{(item.get('distance', 0) / 1000):.1f} km",
                f"{(item.get('duration', 0) / 60):.0f} min",
                item.get('startAddress', 'N/A')[:40],  # Limita lunghezza
                item.get('endAddress', 'N/A')[:40]
            ]
            data.append(row)

    elif report_type == 'stops' and report_data:
        headers = ['Veicolo', 'Inizio', 'Fine', 'Durata', 'Indirizzo']

        data = [headers]
        for item in report_data[:50]:
            row = [
                item.get('deviceName', '')[:20],
                item.get('startTime', '')[:16],
                item.get('endTime', '')[:16],
                f"{(item.get('duration', 0) / 60):.0f} min",
                item.get('address', 'N/A')[:50]
            ]
            data.append(row)

    elif report_type == 'summary' and report_data:
        headers = ['Veicolo', 'Distanza', 'Vel. Max', 'Vel. Media', 'Ore Motore']

        data = [headers]
        for item in report_data:
            row = [
                item.get('deviceName', ''),
                f"{(item.get('distance', 0) / 1000):.1f} km",
                f"{(item.get('maxSpeed', 0) * 1.852):.1f} km/h",
                f"{(item.get('averageSpeed', 0) * 1.852):.1f} km/h",
                f"{(item.get('engineHours', 0) / 3600):.1f} h"
            ]
            data.append(row)
    else:
        data = [['Nessun dato disponibile']]

    # Crea tabella
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    story.append(table)

    # Note
    if metadata.get('addresses_included'):
        story.append(Spacer(1, 20))
        note_text = "Nota: Gli indirizzi sono stati risolti automaticamente tramite geocoding."
        story.append(Paragraph(note_text, styles['Normal']))

    doc.build(story)

    buffer.seek(0)
    filename = f"report_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )


@reports_bp.route('/geocoding-status')
def geocoding_status():
    """Endpoint per verificare lo stato del servizio geocoding"""
    geocoding_service = current_app.config.get('GEOCODING_SERVICE')

    if not geocoding_service:
        return jsonify({
            'available': False,
            'message': 'Servizio geocoding non configurato'
        })

    try:
        stats = geocoding_service.get_statistics()
        cache_stats = stats.get('cache_stats', {})

        return jsonify({
            'available': True,
            'cache_addresses': cache_stats.get('total_addresses', 0),
            'hit_rate': cache_stats.get('hit_rate_percent', 0),
            'db_size_mb': cache_stats.get('db_size_mb', 0)
        })

    except Exception as e:
        return jsonify({
            'available': False,
            'error': str(e)
        }), 500