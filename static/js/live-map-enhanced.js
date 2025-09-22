// static/js/live-map-enhanced.js
// Enhanced live map with improved vehicle popups

class LiveMapManager {
    constructor() {
        this.map = null;
        this.vehicleMarkers = {};
        this.allVehicles = [];
        this.currentFilter = 'all';
        this.selectedGroup = '';
        this.selectedCategory = '';
        this.updateInterval = null;
        this.isFullscreen = false;

        this.init();
    }

    init() {
        this.initializeMap();
        this.setupEventListeners();
        this.startAutoRefresh();
        this.loadInitialData();
    }

    initializeMap() {
        // Initialize map with custom controls
        this.map = L.map('map', {
            zoomControl: false,
            fullscreenControl: true,
            fullscreenControlOptions: {
                position: 'topleft'
            }
        }).setView([43.5, 11.5], 6);

        // Base layers
        const baseLayers = {
            'Light': L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                attribution: '© OpenStreetMap, © CartoDB',
                maxZoom: 19
            }),
            'Satellite': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: '© Esri',
                maxZoom: 19
            }),
            'Dark': L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '© OpenStreetMap, © CartoDB',
                maxZoom: 19
            }),
            'Street': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap',
                maxZoom: 19
            })
        };

        // Add default layer
        baseLayers['Light'].addTo(this.map);

        // Custom zoom control in bottom right
        L.control.zoom({ position: 'bottomright' }).addTo(this.map);

        // Layer control in bottom right
        L.control.layers(baseLayers, null, { position: 'bottomright' }).addTo(this.map);

        // Handle fullscreen events
        this.map.on('enterFullscreen', () => {
            document.body.classList.add('fullscreen');
            this.isFullscreen = true;
        });

        this.map.on('exitFullscreen', () => {
            document.body.classList.remove('fullscreen');
            this.isFullscreen = false;
        });
    }

    setupEventListeners() {
        // Filter event listeners
        document.getElementById('groupFilter').addEventListener('change', (e) => {
            this.selectedGroup = e.target.value;
            this.applyFilters();
        });

        document.getElementById('categoryFilter').addEventListener('change', (e) => {
            this.selectedCategory = e.target.value;
            this.applyFilters();
        });

        // Bottom bar filter buttons
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
            });
        });
    }

    async loadInitialData() {
        await this.loadVehicles();
        this.updateLastUpdateTime();
    }

    async loadVehicles() {
        try {
            console.log('Loading vehicles...');
            const response = await fetch('/api/vehicles');

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const vehicles = await response.json();

            if (vehicles.error) {
                throw new Error(vehicles.error);
            }

            console.log(`Loaded ${vehicles.length} vehicles`);
            this.allVehicles = vehicles;
            this.applyFilters();

        } catch (error) {
            console.error('Error loading vehicles:', error);
            this.showError(`Errore caricamento veicoli: ${error.message}`);
        }
    }

    applyFilters() {
        let filtered = [...this.allVehicles];

        // Apply status filter
        if (this.currentFilter === 'active') {
            filtered = filtered.filter(v => v.status === 'online' && (v.speed || 0) > 0);
        } else if (this.currentFilter === 'stopped') {
            filtered = filtered.filter(v => v.status === 'offline' || (v.speed || 0) === 0);
        }

        // Apply group filter
        if (this.selectedGroup) {
            filtered = filtered.filter(v => v.groupId == this.selectedGroup);
        }

        // Apply category filter
        if (this.selectedCategory) {
            filtered = filtered.filter(v => v.category === this.selectedCategory);
        }

        console.log(`Filtered ${filtered.length} vehicles from ${this.allVehicles.length} total`);

        this.updateVehicleList(filtered);
        this.updateMapMarkers(filtered);
        this.updateStats(filtered);
    }

    updateVehicleList(vehicles) {
        const container = document.getElementById('vehicleList');

        if (!vehicles || vehicles.length === 0) {
            container.innerHTML = `
                <div class="text-center text-gray-500 py-8">
                    <p class="font-medium">Nessun veicolo trovato</p>
                    <p class="text-xs mt-2">Prova a modificare i filtri</p>
                </div>
            `;
            return;
        }

        container.innerHTML = vehicles.map(v => {
            const status = this.getVehicleStatus(v);
            const statusColor = this.getStatusColorClass(status);
            const speed = Math.round(v.speed || 0);
            const timeAgo = this.getTimeAgo(v.lastUpdate);

            return `
                <div class="vehicle-card map-panel rounded-lg p-3 shadow-sm cursor-pointer hover:shadow-md transition-all duration-200"
                     onclick="liveMap.focusVehicle(${v.id})">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <div class="w-3 h-3 bg-${statusColor} rounded-full ${status === 'active' ? 'animate-pulse' : ''}"></div>
                            <span class="font-semibold text-sm text-gray-900 truncate">${v.name}</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-bold text-gray-700">${speed} km/h</span>
                            ${status === 'active' ? '<span class="text-xs">🚗</span>' : status === 'stopped' ? '<span class="text-xs">⏸️</span>' : '<span class="text-xs">📵</span>'}
                        </div>
                    </div>
                    <div class="flex justify-between items-center text-xs text-gray-600">
                        <span>${v.category || 'Non specificata'}</span>
                        <span class="${timeAgo.includes('giorni') ? 'text-red-500' : timeAgo.includes('h') ? 'text-yellow-500' : 'text-green-500'}">
                            ${timeAgo}
                        </span>
                    </div>
                </div>
            `;
        }).join('');

        // Update subtitle with vehicle count
        document.getElementById('subtitleText').textContent = `${vehicles.length} veicoli`;
    }

    updateMapMarkers(vehicles) {
        // Clear existing markers
        Object.values(this.vehicleMarkers).forEach(marker => this.map.removeLayer(marker));
        this.vehicleMarkers = {};

        vehicles.forEach(v => {
            if (v.latitude && v.longitude) {
                const status = this.getVehicleStatus(v);
                const color = this.getStatusColor(status);

                // Create enhanced marker
                const marker = L.circleMarker([v.latitude, v.longitude], {
                    radius: 12,
                    fillColor: color,
                    color: '#ffffff',
                    weight: 3,
                    opacity: 1,
                    fillOpacity: 0.9,
                    className: `vehicle-marker vehicle-marker-${status}`
                }).addTo(this.map);

                // Add enhanced popup
                marker.bindPopup(() => this.createVehiclePopup(v), {
                    className: 'vehicle-popup-container',
                    maxWidth: 400,
                    minWidth: 320,
                    offset: [0, -10],
                    closeButton: true,
                    autoPan: true,
                    keepInView: true
                });

                // Add hover effects
                marker.on('mouseover', function() {
                    this.setStyle({
                        radius: 15,
                        weight: 4
                    });
                });

                marker.on('mouseout', function() {
                    this.setStyle({
                        radius: 12,
                        weight: 3
                    });
                });

                this.vehicleMarkers[v.id] = marker;
            }
        });

        // Auto-fit bounds if we have markers
        const bounds = Object.values(this.vehicleMarkers).map(m => m.getLatLng());
        if (bounds.length > 0) {
            this.map.fitBounds(L.latLngBounds(bounds), {
                padding: [50, 50],
                maxZoom: 16
            });
        }
    }

    updateStats(vehicles) {
        const total = vehicles.length;
        const moving = vehicles.filter(v => v.status === 'online' && (v.speed || 0) > 0).length;

        // Calculate average speed
        const movingVehicles = vehicles.filter(v => (v.speed || 0) > 0);
        const avgSpeed = movingVehicles.length > 0 ?
            Math.round(movingVehicles.reduce((sum, v) => sum + (v.speed || 0), 0) / movingVehicles.length) : 0;

        // Update DOM
        document.getElementById('totalVehicles').textContent = total;
        document.getElementById('movingVehicles').textContent = moving;
        document.getElementById('avgSpeed').textContent = `${avgSpeed} km/h`;
    }

    focusVehicle(vehicleId) {
        const marker = this.vehicleMarkers[vehicleId];
        if (marker) {
            this.map.setView(marker.getLatLng(), 16);
            setTimeout(() => marker.openPopup(), 300);

            // Highlight in vehicle list
            document.querySelectorAll('.vehicle-card').forEach(card => {
                card.classList.remove('ring-2', 'ring-blue-400');
            });

            const vehicleCard = document.querySelector(`[onclick="liveMap.focusVehicle(${vehicleId})"]`);
            if (vehicleCard) {
                vehicleCard.classList.add('ring-2', 'ring-blue-400');
                vehicleCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
    }

    createVehiclePopup(vehicle) {
        const status = this.getVehicleStatus(vehicle);
        const statusText = this.getStatusText(status);
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
        const timeAgo = this.getTimeAgo(vehicle.lastUpdate);

        // Get direction text
        const getDirectionText = (course) => {
            if (!course) return 'N/D';
            const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
            const index = Math.round(course / 45) % 8;
            return directions[index];
        };

        const statusIcon = status === 'active' ? '🚗' : status === 'stopped' ? '⏸️' : '📵';
        const statusColor = this.getStatusColor(status);

        return `
            <div class="vehicle-popup-enhanced">
                <div class="popup-header" style="background: linear-gradient(135deg, ${statusColor} 0%, ${this.darkenColor(statusColor, 20)} 100%)">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center space-x-3">
                            <div class="vehicle-icon">
                                ${statusIcon}
                            </div>
                            <div>
                                <h3 class="popup-title">${vehicle.name}</h3>
                                <p class="popup-id">${vehicle.uniqueId || `ID: ${vehicle.id}`}</p>
                            </div>
                        </div>
                        <div class="status-badge">
                            ${statusText}
                        </div>
                    </div>
                </div>

                <div class="popup-content">
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
                                <span class="detail-label">Precisione:</span>
                                <span class="detail-value">${pos.accuracy ? `±${Math.round(pos.accuracy)}m` : 'N/D'}</span>
                            </div>
                        </div>
                    </div>

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

                    <div class="details-section">
                        <h4 class="section-title">🚙 Veicolo</h4>
                        <div class="detail-rows">
                            <div class="detail-row">
                                <span class="detail-label">Categoria:</span>
                                <span class="detail-value">${vehicle.category || 'Non specificata'}</span>
                            </div>
                            ${vehicle.model ? `
                            <div class="detail-row">
                                <span class="detail-label">Modello:</span>
                                <span class="detail-value">${vehicle.model}</span>
                            </div>
                            ` : ''}
                        </div>
                    </div>

                    <div class="actions-section">
                        <button onclick="liveMap.centerOnVehicle(${vehicle.id})" class="action-btn primary">
                            📍 Centra sulla mappa
                        </button>
                        <button onclick="liveMap.showVehicleHistory(${vehicle.id})" class="action-btn secondary">
                            📊 Storico
                        </button>
                        <button onclick="liveMap.showVehicleDetails(${vehicle.id})" class="action-btn secondary">
                            ℹ️ Dettagli
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    // Utility methods
    getVehicleStatus(vehicle) {
        if (vehicle.status === 'offline') return 'offline';
        if (vehicle.status === 'online' && (vehicle.speed || 0) > 0) return 'active';
        return 'stopped';
    }

    getStatusColor(status) {
        switch (status) {
            case 'active': return '#10b981';
            case 'stopped': return '#f59e0b';
            case 'offline': return '#ef4444';
            default: return '#6b7280';
        }
    }

    getStatusColorClass(status) {
        switch (status) {
            case 'active': return 'green-500';
            case 'stopped': return 'yellow-500';
            case 'offline': return 'red-500';
            default: return 'gray-500';
        }
    }

    getStatusText(status) {
        switch (status) {
            case 'active': return 'In movimento';
            case 'stopped': return 'Fermo';
            case 'offline': return 'Offline';
            default: return 'Sconosciuto';
        }
    }

    getTimeAgo(lastUpdate) {
        if (!lastUpdate) return 'N/A';

        const now = new Date();
        const lastUpdateDate = new Date(lastUpdate);
        const diffMinutes = Math.floor((now - lastUpdateDate) / (1000 * 60));

        if (diffMinutes < 1) return 'Ora';
        if (diffMinutes < 60) return `${diffMinutes} min fa`;
        if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h ${diffMinutes % 60}m fa`;
        return `${Math.floor(diffMinutes / 1440)} giorni fa`;
    }

    darkenColor(color, percent) {
        const num = parseInt(color.replace('#', ''), 16);
        const amt = Math.round(2.55 * percent);
        const R = (num >> 16) + amt;
        const G = (num >> 8 & 0x00FF) + amt;
        const B = (num & 0x0000FF) + amt;
        return '#' + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 +
            (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 +
            (B < 255 ? B < 1 ? 0 : B : 255)).toString(16).slice(1);
    }

    updateLastUpdateTime() {
        document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString('it-IT');
    }

    startAutoRefresh() {
        // Refresh every 30 seconds
        this.updateInterval = setInterval(() => {
            this.loadVehicles();
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
    }

    showError(message) {
        const container = document.getElementById('vehicleList');
        container.innerHTML = `
            <div class="text-center text-red-500 py-8">
                <p class="font-semibold">Errore</p>
                <p class="text-xs mt-2">${message}</p>
                <button onclick="liveMap.loadVehicles()" class="mt-4 px-4 py-2 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition-colors">
                    Riprova
                </button>
            </div>
        `;
    }

    // Action methods
    centerOnVehicle(vehicleId) {
        const marker = this.vehicleMarkers[vehicleId];
        if (marker) {
            this.map.setView(marker.getLatLng(), 16);
        }
    }

    showVehicleHistory(vehicleId) {
        window.open(`/vehicles/${vehicleId}/history`, '_blank');
    }

    showVehicleDetails(vehicleId) {
        window.open(`/vehicles/${vehicleId}`, '_blank');
    }
}

// Global functions for compatibility
function filterVehicles(filter) {
    liveMap.currentFilter = filter;
    liveMap.applyFilters();

    // Update button styles
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-blue-500', 'text-white');
        btn.classList.add('bg-white', 'text-gray-700');
    });

    const activeBtn = document.querySelector(`[onclick="filterVehicles('${filter}')"]`);
    if (activeBtn) {
        activeBtn.classList.remove('bg-white', 'text-gray-700');
        activeBtn.classList.add('active', 'bg-blue-500', 'text-white');
    }
}

function focusVehicle(vehicleId) {
    liveMap.focusVehicle(vehicleId);
}

function toggleCollapse() {
    const section = document.getElementById('filtersSection');
    const icon = document.getElementById('collapseIcon');

    if (section.style.display === 'none') {
        section.style.display = 'block';
        icon.classList.add('rotate-180');
    } else {
        section.style.display = 'none';
        icon.classList.remove('rotate-180');
    }
}

function toggleVehicleList() {
    const container = document.getElementById('vehicleListContainer');
    const icon = document.getElementById('toggleIcon');

    if (container.style.display === 'none') {
        container.style.display = 'block';
        icon.classList.add('rotate-180');
    } else {
        container.style.display = 'none';
        icon.classList.remove('rotate-180');
    }
}

// Initialize when DOM is loaded
let liveMap;
document.addEventListener('DOMContentLoaded', function() {
    liveMap = new LiveMapManager();

    // Add CSS for enhanced popup
    const style = document.createElement('style');
    style.textContent = `
        .vehicle-popup-enhanced {
            min-width: 320px;
            max-width: 380px;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.4;
        }

        .popup-header {
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
            background: rgba(255,255,255,0.2);
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
            background: rgba(255,255,255,0.2);
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

        .vehicle-marker {
            transition: all 0.3s ease;
        }

        .vehicle-marker-active {
            animation: pulse-green 2s infinite;
        }

        @keyframes pulse-green {
            0%, 100% {
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            }
            50% {
                box-shadow: 0 0 0 10px rgba(16, 185, 129, 0);
            }
        }
    `;
    document.head.appendChild(style);
});