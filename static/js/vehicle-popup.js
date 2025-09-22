<!-- static/js/vehicle-popup.js -->
<script>
function createVehiclePopup(vehicle) {
    const status = getVehicleStatus(vehicle);
    const statusText = getStatusText(status);
    const lastUpdate = vehicle.lastUpdate ?
        new Date(vehicle.lastUpdate).toLocaleString('it-IT', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }) : 'N/A';

    const attributes = vehicle.attributes || {};
    const pos = vehicle.latest_position || vehicle;

    // Calcola tempo dall'ultimo aggiornamento
    let timeAgo = '';
    if (vehicle.lastUpdate) {
        const now = new Date();
        const lastUpdateDate = new Date(vehicle.lastUpdate);
        const diffMinutes = Math.floor((now - lastUpdateDate) / (1000 * 60));

        if (diffMinutes < 1) {
            timeAgo = 'Ora';
        } else if (diffMinutes < 60) {
            timeAgo = `${diffMinutes} min fa`;
        } else if (diffMinutes < 1440) {
            timeAgo = `${Math.floor(diffMinutes / 60)}h ${diffMinutes % 60}m fa`;
        } else {
            timeAgo = `${Math.floor(diffMinutes / 1440)} giorni fa`;
        }
    }

    // Determina icone e colori
    const getStatusIcon = (status) => {
        switch (status) {
            case 'active': return '🚗';
            case 'stopped': return '⏸️';
            case 'offline': return '📵';
            default: return '❓';
        }
    };

    const getStatusColor = (status) => {
        switch (status) {
            case 'active': return { bg: '#10b981', text: 'text-green-800', ring: 'ring-green-200' };
            case 'stopped': return { bg: '#f59e0b', text: 'text-yellow-800', ring: 'ring-yellow-200' };
            case 'offline': return { bg: '#ef4444', text: 'text-red-800', ring: 'ring-red-200' };
            default: return { bg: '#6b7280', text: 'text-gray-800', ring: 'ring-gray-200' };
        }
    };

    const statusColor = getStatusColor(status);

    // Calcola direzione leggibile
    const getDirectionText = (course) => {
        if (!course) return 'N/D';
        const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
        const index = Math.round(course / 45) % 8;
        return directions[index];
    };

    return `
        <div class="vehicle-popup-enhanced">
            <div class="popup-header">
                <div class="flex items-center justify-between">
                    <div class="flex items-center space-x-3">
                        <div class="vehicle-icon" style="background: ${statusColor.bg}">
                            ${getStatusIcon(status)}
                        </div>
                        <div>
                            <h3 class="popup-title">${vehicle.name}</h3>
                            <p class="popup-id">${vehicle.uniqueId || `ID: ${vehicle.id}`}</p>
                        </div>
                    </div>
                    <div class="status-badge" style="background: ${statusColor.bg}">
                        ${statusText}
                    </div>
                </div>
            </div>

            <div class="popup-content">
                <!-- Metriche principali -->
                <div class="metrics-grid">
                    <div class="metric-card speed-metric">
                        <div class="metric-value">${Math.round(vehicle.speed || 0)}</div>
                        <div class="metric-label">km/h</div>
                        <div class="metric-icon">🏁</div>
                    </div>

                    <div class="metric-card direction-metric">
                        <div class="metric-value">${getDirectionText(vehicle.course)}</div>
                        <div class="metric-label">${vehicle.course || 0}°</div>
                        <div class="metric-icon">🧭</div>
                    </div>

                    <div class="metric-card altitude-metric">
                        <div class="metric-value">${Math.round(pos.altitude || 0)}</div>
                        <div class="metric-label">metri</div>
                        <div class="metric-icon">⛰️</div>
                    </div>
                </div>

                <!-- Informazioni dettagliate -->
                <div class="details-section">
                    <h4 class="section-title">📍 Posizione</h4>
                    <div class="detail-rows">
                        <div class="detail-row">
                            <span class="detail-label">Coordinate:</span>
                            <span class="detail-value coordinate">
                                ${vehicle.latitude?.toFixed(6) || 'N/A'}, ${vehicle.longitude?.toFixed(6) || 'N/A'}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Indirizzo:</span>
                            <span class="detail-value">${pos.address || vehicle.address || 'Localizzazione in corso...'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Precisione:</span>
                            <span class="detail-value">${pos.accuracy ? `±${Math.round(pos.accuracy)}m` : 'N/D'}</span>
                        </div>
                    </div>
                </div>

                <!-- Informazioni temporali -->
                <div class="details-section">
                    <h4 class="section-title">⏰ Aggiornamenti</h4>
                    <div class="detail-rows">
                        <div class="detail-row">
                            <span class="detail-label">Ultimo aggiornamento:</span>
                            <span class="detail-value">${lastUpdate}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Tempo trascorso:</span>
                            <span class="detail-value ${timeAgo.includes('giorni') ? 'text-red-600' : timeAgo.includes('h') ? 'text-yellow-600' : 'text-green-600'}">
                                ${timeAgo}
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Informazioni veicolo -->
                <div class="details-section">
                    <h4 class="section-title">🚙 Veicolo</h4>
                    <div class="detail-rows">
                        <div class="detail-row">
                            <span class="detail-label">Categoria:</span>
                            <span class="detail-value">${vehicle.category || 'Non specificata'}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Modello:</span>
                            <span class="detail-value">${vehicle.model || 'Non specificato'}</span>
                        </div>
                        ${vehicle.phone ? `
                        <div class="detail-row">
                            <span class="detail-label">Telefono:</span>
                            <span class="detail-value">${vehicle.phone}</span>
                        </div>
                        ` : ''}
                    </div>
                </div>

                <!-- Azioni rapide -->
                <div class="actions-section">
                    <button onclick="centerOnVehicle(${vehicle.id})" class="action-btn primary">
                        📍 Centra sulla mappa
                    </button>
                    <button onclick="showVehicleHistory(${vehicle.id})" class="action-btn secondary">
                        📊 Storico
                    </button>
                    <button onclick="showVehicleDetails(${vehicle.id})" class="action-btn secondary">
                        ℹ️ Dettagli completi
                    </button>
                </div>
            </div>
        </div>

        <style>
            .vehicle-popup-enhanced {
                min-width: 320px;
                max-width: 380px;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
                line-height: 1.4;
            }

            .popup-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 16px;
                border-radius: 12px 12px 0 0;
                margin: -12px -16px 0 -16px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }

            .vehicle-icon {
                width: 40px;
                height: 40px;
                border-radius: 20px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 18px;
                border: 3px solid rgba(255,255,255,0.3);
            }

            .popup-title {
                font-size: 16px;
                font-weight: 700;
                margin: 0;
                text-shadow: 0 1px 2px rgba(0,0,0,0.1);
            }

            .popup-id {
                font-size: 12px;
                opacity: 0.9;
                margin: 2px 0 0 0;
                font-family: 'Monaco', monospace;
            }

            .status-badge {
                padding: 4px 12px;
                border-radius: 16px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border: 2px solid rgba(255,255,255,0.3);
                backdrop-filter: blur(10px);
            }

            .popup-content {
                padding: 16px;
            }

            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 12px;
                margin-bottom: 20px;
            }

            .metric-card {
                background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
                border-radius: 12px;
                padding: 12px;
                text-align: center;
                position: relative;
                border: 1px solid #e2e8f0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }

            .speed-metric {
                background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
                border-color: #10b981;
            }

            .direction-metric {
                background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
                border-color: #3b82f6;
            }

            .altitude-metric {
                background: linear-gradient(135deg, #fefce8 0%, #fef3c7 100%);
                border-color: #f59e0b;
            }

            .metric-value {
                font-size: 18px;
                font-weight: 800;
                color: #1f2937;
                margin-bottom: 2px;
            }

            .metric-label {
                font-size: 10px;
                color: #6b7280;
                font-weight: 500;
            }

            .metric-icon {
                position: absolute;
                top: 4px;
                right: 6px;
                font-size: 12px;
                opacity: 0.6;
            }

            .details-section {
                margin-bottom: 16px;
            }

            .section-title {
                font-size: 13px;
                font-weight: 600;
                color: #374151;
                margin-bottom: 8px;
                padding-bottom: 4px;
                border-bottom: 2px solid #e5e7eb;
            }

            .detail-rows {
                space-y: 6px;
            }

            .detail-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 4px 0;
                border-bottom: 1px solid #f3f4f6;
            }

            .detail-row:last-child {
                border-bottom: none;
            }

            .detail-label {
                font-size: 11px;
                color: #6b7280;
                font-weight: 500;
                flex-shrink: 0;
                margin-right: 8px;
            }

            .detail-value {
                font-size: 12px;
                color: #1f2937;
                font-weight: 500;
                text-align: right;
                word-break: break-all;
            }

            .coordinate {
                font-family: 'Monaco', monospace;
                font-size: 10px;
            }

            .actions-section {
                margin-top: 16px;
                padding-top: 16px;
                border-top: 2px solid #e5e7eb;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }

            .action-btn {
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 11px;
                font-weight: 600;
                text-align: center;
                cursor: pointer;
                transition: all 0.2s ease;
                border: none;
            }

            .action-btn.primary {
                background: linear-gradient(135deg, #3b82f6, #1d4ed8);
                color: white;
                grid-column: 1 / -1;
                box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
            }

            .action-btn.primary:hover {
                transform: translateY(-1px);
                box-shadow: 0 4px 8px rgba(59, 130, 246, 0.4);
            }

            .action-btn.secondary {
                background: #f8fafc;
                color: #374151;
                border: 1px solid #d1d5db;
            }

            .action-btn.secondary:hover {
                background: #f1f5f9;
                border-color: #9ca3af;
            }

            /* Responsive adjustments */
            @media (max-width: 400px) {
                .vehicle-popup-enhanced {
                    min-width: 280px;
                    max-width: 320px;
                }

                .metrics-grid {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
        </style>
    `;
}

// Funzioni di supporto per le azioni
function centerOnVehicle(vehicleId) {
    const marker = vehicleMarkers[vehicleId];
    if (marker) {
        map.setView(marker.getLatLng(), 16);
        marker.openPopup();
    }
}

function showVehicleHistory(vehicleId) {
    // Implementa la logica per mostrare lo storico del veicolo
    console.log('Showing history for vehicle:', vehicleId);
    // Puoi aprire un modal o navigare a una pagina dedicata
    window.open(`/vehicles/${vehicleId}/history`, '_blank');
}

function showVehicleDetails(vehicleId) {
    // Implementa la logica per mostrare i dettagli completi del veicolo
    console.log('Showing details for vehicle:', vehicleId);
    // Puoi aprire un modal o navigare a una pagina dedicata
    window.open(`/vehicles/${vehicleId}`, '_blank');
}
</script>