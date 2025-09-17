"""
Blueprint per gestione dispositivi Traccar
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from emulator.traccar_framework import TraccarAPI, TraccarException

logger = logging.getLogger('devices_blueprint')

devices_bp = Blueprint('devices', __name__)


def get_traccar_api():
    """Ottiene istanza TraccarAPI dalla sessione"""
    from app import get_traccar_api
    return get_traccar_api()


@devices_bp.route('/')
@devices_bp.route('/list')
def list_devices():
    """Lista tutti i dispositivi"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        # Arricchisci i dati con informazioni aggiuntive
        for device in devices:
            # Ottieni ultima posizione
            try:
                positions = traccar.positions.get_positions(device_id=device['id'], limit=1)
                device['last_position'] = positions[0] if positions else None
            except:
                device['last_position'] = None

            # Calcola stato
            status = device.get('status', 'unknown')
            last_update = device.get('lastUpdate')

            if last_update:
                try:
                    last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
                    time_diff = datetime.now(last_update_dt.tzinfo) - last_update_dt

                    if time_diff > timedelta(minutes=30):
                        status = 'offline'
                    elif status == 'unknown':
                        status = 'online'
                except:
                    pass

            device['calculated_status'] = status

        return render_template('devices/list.html', devices=devices)

    except TraccarException as e:
        logger.error(f"Errore Traccar lista dispositivi: {e}")
        flash(f'Errore caricamento dispositivi: {e}', 'danger')
        return render_template('devices/list.html', devices=[])


@devices_bp.route('/add', methods=['GET', 'POST'])
def add_device():
    """Aggiungi nuovo dispositivo"""
    if request.method == 'POST':
        try:
            traccar = get_traccar_api()

            device_data = {
                'name': request.form.get('name', '').strip(),
                'uniqueId': request.form.get('uniqueId', '').strip(),
                'category': request.form.get('category', ''),
                'phone': request.form.get('phone', '').strip() or None,
                'model': request.form.get('model', '').strip() or None
            }

            # Validazione
            if not device_data['name']:
                flash('Il nome del dispositivo è obbligatorio', 'danger')
                return render_template('devices/add.html', form_data=device_data)

            if not device_data['uniqueId']:
                flash('L\'ID univoco è obbligatorio', 'danger')
                return render_template('devices/add.html', form_data=device_data)

            # Crea dispositivo
            new_device = traccar.devices.create_device(**device_data)

            flash(f'Dispositivo "{new_device["name"]}" creato con successo', 'success')
            return redirect(url_for('devices.view_device', device_id=new_device['id']))

        except TraccarException as e:
            logger.error(f"Errore creazione dispositivo: {e}")
            flash(f'Errore creazione dispositivo: {e}', 'danger')
            return render_template('devices/add.html', form_data=request.form)

    return render_template('devices/add.html')


@devices_bp.route('/<int:device_id>')
def view_device(device_id):
    """Visualizza dettagli dispositivo"""
    try:
        traccar = get_traccar_api()
        device = traccar.devices.get_device(device_id)

        # Ottieni posizioni recenti
        recent_positions = []
        try:
            recent_positions = traccar.positions.get_positions(device_id=device_id, limit=10)
        except:
            pass

        return render_template('devices/view.html',
                               device=device,
                               recent_positions=recent_positions)

    except TraccarException as e:
        logger.error(f"Errore visualizzazione dispositivo {device_id}: {e}")
        flash(f'Dispositivo non trovato: {e}', 'danger')
        return redirect(url_for('devices.list_devices'))


@devices_bp.route('/<int:device_id>/edit', methods=['GET', 'POST'])
def edit_device(device_id):
    """Modifica dispositivo"""
    try:
        traccar = get_traccar_api()
        device = traccar.devices.get_device(device_id)

        if request.method == 'POST':
            updated_data = {
                'id': device_id,
                'name': request.form.get('name', '').strip(),
                'uniqueId': request.form.get('uniqueId', '').strip(),
                'category': request.form.get('category', ''),
                'phone': request.form.get('phone', '').strip() or None,
                'model': request.form.get('model', '').strip() or None
            }

            if not updated_data['name']:
                flash('Il nome del dispositivo è obbligatorio', 'danger')
                return render_template('devices/edit.html', device=device)

            # Aggiorna dispositivo
            updated_device = traccar.devices.update_device(device_id, updated_data)

            flash(f'Dispositivo "{updated_device["name"]}" aggiornato con successo', 'success')
            return redirect(url_for('devices.view_device', device_id=device_id))

        return render_template('devices/edit.html', device=device)

    except TraccarException as e:
        logger.error(f"Errore modifica dispositivo {device_id}: {e}")
        flash(f'Errore modifica dispositivo: {e}', 'danger')
        return redirect(url_for('devices.list_devices'))


@devices_bp.route('/<int:device_id>/delete', methods=['POST'])
def delete_device(device_id):
    """Elimina dispositivo"""
    try:
        traccar = get_traccar_api()
        device = traccar.devices.get_device(device_id)
        device_name = device.get('name', f'ID {device_id}')

        traccar.devices.delete_device(device_id)

        flash(f'Dispositivo "{device_name}" eliminato con successo', 'success')
        return redirect(url_for('devices.list_devices'))

    except TraccarException as e:
        logger.error(f"Errore eliminazione dispositivo {device_id}: {e}")
        flash(f'Errore eliminazione dispositivo: {e}', 'danger')
        return redirect(url_for('devices.list_devices'))


@devices_bp.route('/status')
def device_status():
    """Stato in tempo reale di tutti i dispositivi"""
    try:
        traccar = get_traccar_api()
        devices = traccar.devices.get_devices()

        device_status_data = []

        for device in devices:
            try:
                positions = traccar.positions.get_positions(device_id=device['id'], limit=1)
                last_position = positions[0] if positions else None

                status = device.get('status', 'unknown')
                if last_position:
                    speed_knots = last_position.get('speed', 0)
                    speed_kmh = float(speed_knots) * 1.852

                    if speed_kmh > 5:
                        status = 'moving'
                    elif status == 'online':
                        status = 'stopped'

                device_status_data.append({
                    'device': device,
                    'position': last_position,
                    'status': status
                })

            except Exception as e:
                logger.warning(f"Errore status dispositivo {device['id']}: {e}")
                device_status_data.append({
                    'device': device,
                    'position': None,
                    'status': 'error'
                })

        return render_template('devices/status.html', device_data=device_status_data)

    except TraccarException as e:
        logger.error(f"Errore stato dispositivi: {e}")
        flash(f'Errore caricamento stato: {e}', 'danger')
        return render_template('devices/status.html', device_data=[])