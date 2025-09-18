# blueprints/alerts.py - Alert management

from flask import Blueprint, render_template, jsonify, request, session
from models.database import Database
from core.traccar_framework import TraccarException
from datetime import datetime

alerts_bp = Blueprint('alerts', __name__, template_folder='../templates')

db = Database()


@alerts_bp.route('/')
def index():
    """Alert management page"""
    alerts = db.get_alerts(limit=100)
    return render_template('alerts/index.html', alerts=alerts)


@alerts_bp.route('/api/alerts')
def get_alerts():
    """Get alerts via API"""
    limit = request.args.get('limit', 50, type=int)
    acknowledged = request.args.get('acknowledged', 'false').lower() == 'true'

    alerts = db.get_alerts(limit=limit, acknowledged=acknowledged)
    return jsonify(alerts)


@alerts_bp.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    db.acknowledge_alert(alert_id)
    return jsonify({'success': True})


@alerts_bp.route('/api/alerts/create', methods=['POST'])
def create_alert():
    """Create new alert"""
    data = request.get_json()

    db.create_alert(
        vehicle_id=data['vehicle_id'],
        alert_type=data['alert_type'],
        message=data['message'],
        severity=data.get('severity', 'info')
    )

    return jsonify({'success': True})