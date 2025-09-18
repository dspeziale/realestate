# blueprints/vehicles.py - VERSIONE COMPLETA RIDEFINITA

from flask import Blueprint, render_template, current_app, redirect, url_for, flash, jsonify
from core.traccar_framework import TraccarException
from datetime import datetime, timedelta

vehicles_bp = Blueprint('vehicles', __name__, template_folder='../templates')


@vehicles_bp.route('/')
def list():
    """Lista veicoli con dettagli live"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()

        # Arricchisci ogni veicolo con dati live
        for device in devices:
            try:
                # Ultima posizione
                positions = traccar.positions.get_positions(device_id=device['id'])
                device['latest_position'] = positions[-1] if positions else None

                # Calcola tempo dall'ultimo aggiornamento
                if device.get('lastUpdate'):
                    last_update = datetime.fromisoformat(device['lastUpdate'].replace('Z', '+00:00'))
                    now = datetime.now(last_update.tzinfo)
                    diff_minutes = int((now - last_update).total_seconds() / 60)
                    device['minutes_ago'] = diff_minutes
                else:
                    device['minutes_ago'] = None

            except Exception as e:
                print(f"Error loading data for device {device['id']}: {e}")
                device['latest_position'] = None
                device['minutes_ago'] = None

        # Ordina per stato (online prima) e poi per nome
        devices.sort(key=lambda x: (x['status'] != 'online', x['name']))

        return render_template('vehicles/list.html', vehicles=devices)

    except TraccarException as e:
        flash(f'Error loading vehicles: {str(e)}', 'error')
        return render_template('vehicles/list.html', vehicles=[])


@vehicles_bp.route('/<int:vehicle_id>')
def detail(vehicle_id):
    """Dettagli completi del veicolo"""
    traccar = current_app.config['TRACCAR_API']

    try:
        # Carica il veicolo
        devices = traccar.devices.get_devices()
        vehicle = next((d for d in devices if d['id'] == vehicle_id), None)

        if not vehicle:
            flash('Vehicle not found', 'error')
            return redirect(url_for('vehicles.list'))

        # Posizioni ultime 24h
        from_time = datetime.now() - timedelta(days=1)
        to_time = datetime.now()

        positions = traccar.positions.get_positions(
            device_id=vehicle_id,
            from_time=from_time,
            to_time=to_time
        )

        # Summary report
        try:
            summary = traccar.reports.get_summary_report(
                device_ids=[vehicle_id],
                from_time=from_time,
                to_time=to_time
            )
            vehicle['summary_24h'] = summary[0] if summary else None
        except:
            vehicle['summary_24h'] = None

        # Trip report
        try:
            trips = traccar.reports.get_trips_report(
                device_ids=[vehicle_id],
                from_time=from_time,
                to_time=to_time
            )
            vehicle['trips'] = trips[:10]  # Ultimi 10 viaggi
        except:
            vehicle['trips'] = []

        return render_template('vehicles/detail.html',
                               vehicle=vehicle,
                               positions=positions)

    except TraccarException as e:
        flash(f'Error loading vehicle details: {str(e)}', 'error')
        return redirect(url_for('vehicles.list'))


@vehicles_bp.route('/<int:vehicle_id>/live')
def live_tracking(vehicle_id):
    """Tracking live del veicolo"""
    traccar = current_app.config['TRACCAR_API']

    try:
        devices = traccar.devices.get_devices()
        vehicle = next((d for d in devices if d['id'] == vehicle_id), None)

        if not vehicle:
            flash('Vehicle not found', 'error')
            return redirect(url_for('vehicles.list'))

        # Posizioni ultime 6 ore
        from_time = datetime.now() - timedelta(hours=6)
        to_time = datetime.now()

        positions = traccar.positions.get_positions(
            device_id=vehicle_id,
            from_time=from_time,
            to_time=to_time
        )

        return render_template('vehicles/live_tracking.html',
                               vehicle=vehicle,
                               positions=positions)

    except TraccarException as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('vehicles.detail', vehicle_id=vehicle_id))
