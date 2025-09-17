/**
 * Traccar Fleet Management - Main Application JavaScript
 * ====================================================
 *
 * Funzioni globali, utilities e gestione eventi per l'intera applicazione
 * Compatibile con AdminLTE, DataTables, e Leaflet
 */

// Namespace globale per evitare conflitti
window.TraccarFleet = window.TraccarFleet || {};

// Configurazione globale
TraccarFleet.config = {
    apiBaseUrl: '/api',
    refreshInterval: 30000, // 30 secondi
    mapDefaults: {
        center: [41.9028, 12.4964], // Roma
        zoom: 6,
        maxZoom: 18
    },
    dateFormats: {
        display: 'DD/MM/YYYY HH:mm:ss',
        api: 'YYYY-MM-DDTHH:mm:ss',
        short: 'DD/MM/YYYY'
    }
};

// Cache per ottimizzazione
TraccarFleet.cache = {
    devices: null,
    positions: null,
    lastUpdate: null,
    ttl: 30000 // 30 secondi TTL
};

/**
 * ============================================
 * INIZIALIZZAZIONE APPLICAZIONE
 * ============================================
 */
$(document).ready(function() {
    TraccarFleet.init();
});

TraccarFleet.init = function() {
    console.log('🚀 Inizializzazione Traccar Fleet Management');

    // Setup moment.js locale
    if (typeof moment !== 'undefined') {
        moment.locale('it');
    }

    // Inizializza componenti base
    this.initializeGlobalEvents();
    this.initializeTooltips();
    this.initializeDataTables();
    this.initializeFormValidation();
    this.initializeAjaxDefaults();

    // Auto-refresh per componenti live
    this.startAutoRefresh();

    // Gestione responsive
    this.handleResponsive();

    console.log('✅ Inizializzazione completata');
};

/**
 * ============================================
 * EVENTI GLOBALI
 * ============================================ */
TraccarFleet.initializeGlobalEvents = function() {
    // Gestione click su elementi con data-action
    $(document).on('click', '[data-action]', function(e) {
        const action = $(this).data('action');
        const target = $(this).data('target');

        switch(action) {
            case 'refresh':
                TraccarFleet.refreshComponent(target);
                break;
            case 'export':
                TraccarFleet.exportData(target);
                break;
            case 'toggle':
                TraccarFleet.toggleComponent(target);
                break;
        }
    });

    // Gestione errori AJAX globali
    $(document).ajaxError(function(event, xhr, settings, error) {
        if (xhr.status === 401) {
            TraccarFleet.handleUnauthorized();
        } else if (xhr.status >= 500) {
            TraccarFleet.showToast('Errore del server', 'error');
        }
    });

    // Gestione connessione di rete
    window.addEventListener('online', function() {
        TraccarFleet.showToast('Connessione ripristinata', 'success');
        TraccarFleet.startAutoRefresh();
    });

    window.addEventListener('offline', function() {
        TraccarFleet.showToast('Connessione persa', 'warning');
        TraccarFleet.stopAutoRefresh();
    });

    // Gestione resize finestra
    $(window).resize(TraccarFleet.debounce(function() {
        TraccarFleet.handleResize();
    }, 250));
};

/**
 * ============================================
 * TOOLTIPS E POPOVERS
 * ============================================ */
TraccarFleet.initializeTooltips = function() {
    // Inizializza tooltips
    $('[data-toggle="tooltip"]').tooltip({
        container: 'body',
        delay: { show: 500, hide: 100 }
    });

    // Inizializza popovers
    $('[data-toggle="popover"]').popover({
        container: 'body',
        trigger: 'hover',
        html: true
    });

    // Refresh tooltips quando viene aggiunto contenuto dinamico
    $(document).on('DOMNodeInserted', function() {
        $('[data-toggle="tooltip"]:not([data-original-title])').tooltip();
        $('[data-toggle="popover"]:not([aria-describedby])').popover();
    });
};

/**
 * ============================================
 * DATATABLES CONFIGURAZIONE
 * ============================================ */
TraccarFleet.initializeDataTables = function() {
    // Configurazione globale DataTables
    if (typeof $.fn.DataTable !== 'undefined') {
        $.extend(true, $.fn.dataTable.defaults, {
            language: {
                url: '//cdn.datatables.net/plug-ins/1.13.6/i18n/it-IT.json'
            },
            responsive: true,
            pageLength: 25,
            lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "Tutti"]],
            dom: "<'row'<'col-sm-6'l><'col-sm-6'f>>" +
                 "<'row'<'col-sm-12'B>>" +
                 "<'row'<'col-sm-12'tr>>" +
                 "<'row'<'col-sm-5'i><'col-sm-7'p>>",
            buttons: [
                {
                    extend: 'copy',
                    className: 'btn btn-sm btn-secondary'
                },
                {
                    extend: 'csv',
                    className: 'btn btn-sm btn-secondary'
                },
                {
                    extend: 'excel',
                    className: 'btn btn-sm btn-secondary'
                },
                {
                    extend: 'pdf',
                    className: 'btn btn-sm btn-secondary'
                },
                {
                    extend: 'print',
                    className: 'btn btn-sm btn-secondary'
                }
            ],
            initComplete: function(settings, json) {
                // Applica stili personalizzati dopo inizializzazione
                $(this).closest('.dataTables_wrapper').find('.dt-buttons').addClass('mb-3');
            }
        });
    }
};

/**
 * ============================================
 * VALIDAZIONE FORM
 * ============================================ */
TraccarFleet.initializeFormValidation = function() {
    // Validazione in tempo reale
    $(document).on('blur', '.form-control[required]', function() {
        TraccarFleet.validateField(this);
    });

    // Validazione al submit
    $(document).on('submit', 'form[data-validate="true"]', function(e) {
        if (!TraccarFleet.validateForm(this)) {
            e.preventDefault();
            return false;
        }
    });

    // Auto-formatters
    $(document).on('input', 'input[data-format="phone"]', function() {
        this.value = TraccarFleet.formatPhone(this.value);
    });

    $(document).on('input', 'input[data-format="numeric"]', function() {
        this.value = this.value.replace(/[^0-9.-]/g, '');
    });
};

TraccarFleet.validateField = function(field) {
    const $field = $(field);
    const value = $field.val().trim();
    const fieldType = $field.attr('type');
    let isValid = true;
    let message = '';

    // Reset stato precedente
    $field.removeClass('is-valid is-invalid');
    $field.siblings('.invalid-feedback').remove();

    // Validazione campo obbligatorio
    if ($field.prop('required') && !value) {
        isValid = false;
        message = 'Questo campo è obbligatorio';
    }

    // Validazione email
    else if (fieldType === 'email' && value && !TraccarFleet.isValidEmail(value)) {
        isValid = false;
        message = 'Inserisci un indirizzo email valido';
    }

    // Validazione URL
    else if (fieldType === 'url' && value && !TraccarFleet.isValidUrl(value)) {
        isValid = false;
        message = 'Inserisci un URL valido';
    }

    // Validazione lunghezza minima
    const minLength = $field.attr('minlength');
    if (minLength && value.length < parseInt(minLength)) {
        isValid = false;
        message = `Minimo ${minLength} caratteri richiesti`;
    }

    // Validazione pattern personalizzato
    const pattern = $field.attr('pattern');
    if (pattern && value && !new RegExp(pattern).test(value)) {
        isValid = false;
        message = 'Formato non valido';
    }

    // Applica risultato validazione
    if (isValid) {
        $field.addClass('is-valid');
    } else {
        $field.addClass('is-invalid');
        $field.after(`<div class="invalid-feedback">${message}</div>`);
    }

    return isValid;
};

TraccarFleet.validateForm = function(form) {
    let isValid = true;

    // Valida tutti i campi obbligatori
    $(form).find('[required]').each(function() {
        if (!TraccarFleet.validateField(this)) {
            isValid = false;
        }
    });

    // Focus sul primo campo non valido
    if (!isValid) {
        $(form).find('.is-invalid').first().focus();
    }

    return isValid;
};

/**
 * ============================================
 * AJAX E API
 * ============================================ */
TraccarFleet.initializeAjaxDefaults = function() {
    // Setup CSRF token se presente
    const csrfToken = $('meta[name="csrf-token"]').attr('content');
    if (csrfToken) {
        $.ajaxSetup({
            beforeSend: function(xhr, settings) {
                if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                    xhr.setRequestHeader("X-CSRFToken", csrfToken);
                }
            }
        });
    }

    // Loading indicator globale
    $(document).ajaxStart(function() {
        TraccarFleet.showLoading();
    }).ajaxStop(function() {
        TraccarFleet.hideLoading();
    });
};

TraccarFleet.apiCall = function(endpoint, options = {}) {
    const defaults = {
        url: TraccarFleet.config.apiBaseUrl + endpoint,
        type: 'GET',
        dataType: 'json',
        cache: false,
        timeout: 30000
    };

    const settings = $.extend({}, defaults, options);

    return $.ajax(settings)
        .fail(function(xhr, status, error) {
            console.error('API Error:', endpoint, xhr.responseText);

            if (xhr.responseJSON && xhr.responseJSON.error) {
                TraccarFleet.showToast(xhr.responseJSON.error, 'error');
            } else {
                TraccarFleet.showToast('Errore di connessione', 'error');
            }
        });
};

/**
 * ============================================
 * NOTIFICHE E TOAST
 * ============================================ */
TraccarFleet.showToast = function(message, type = 'info', options = {}) {
    const defaults = {
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        icon: type === 'error' ? 'error' : type === 'warning' ? 'warning' : type === 'success' ? 'success' : 'info'
    };

    const config = Object.assign({}, defaults, options, { title: message });

    if (typeof Swal !== 'undefined') {
        Swal.fire(config);
    } else {
        // Fallback con alert nativo
        alert(message);
    }
};

TraccarFleet.showConfirm = function(title, text, confirmText = 'Conferma', cancelText = 'Annulla') {
    if (typeof Swal !== 'undefined') {
        return Swal.fire({
            title: title,
            text: text,
            icon: 'question',
            showCancelButton: true,
            confirmButtonColor: '#007bff',
            cancelButtonColor: '#6c757d',
            confirmButtonText: confirmText,
            cancelButtonText: cancelText
        });
    } else {
        // Fallback con confirm nativo
        return Promise.resolve({
            isConfirmed: confirm(`${title}\n\n${text}`)
        });
    }
};

TraccarFleet.showAlert = function(title, text, type = 'info') {
    if (typeof Swal !== 'undefined') {
        return Swal.fire({
            title: title,
            text: text,
            icon: type,
            confirmButtonColor: '#007bff'
        });
    } else {
        alert(`${title}\n\n${text}`);
        return Promise.resolve();
    }
};

/**
 * ============================================
 * LOADING E SPINNERS
 * ============================================ */
TraccarFleet.showLoading = function(target = null) {
    const spinner = '<div class="spinner-overlay"><div class="spinner-border-custom"></div></div>';

    if (target) {
        $(target).css('position', 'relative').append(spinner);
    } else {
        if (!$('#global-spinner').length) {
            $('body').append('<div id="global-spinner" class="spinner-overlay">' +
                           '<div class="spinner-border-custom"></div></div>');
        }
        $('#global-spinner').show();
    }
};

TraccarFleet.hideLoading = function(target = null) {
    if (target) {
        $(target).find('.spinner-overlay').remove();
    } else {
        $('#global-spinner').hide();
    }
};

/**
 * ============================================
 * AUTO-REFRESH E AGGIORNAMENTI
 * ============================================ */
TraccarFleet.startAutoRefresh = function() {
    if (TraccarFleet.refreshTimer) {
        clearInterval(TraccarFleet.refreshTimer);
    }

    TraccarFleet.refreshTimer = setInterval(function() {
        TraccarFleet.refreshLiveData();
    }, TraccarFleet.config.refreshInterval);
};

TraccarFleet.stopAutoRefresh = function() {
    if (TraccarFleet.refreshTimer) {
        clearInterval(TraccarFleet.refreshTimer);
        TraccarFleet.refreshTimer = null;
    }
};

TraccarFleet.refreshLiveData = function() {
    // Aggiorna solo se la pagina è visibile
    if (document.hidden) return;

    // Aggiorna statistiche dashboard
    if ($('#dashboard-stats').length) {
        TraccarFleet.refreshDashboardStats();
    }

    // Aggiorna posizioni mappa
    if ($('#live-map').length) {
        TraccarFleet.refreshMapPositions();
    }

    // Aggiorna notifiche
    TraccarFleet.refreshNotifications();
};

TraccarFleet.refreshDashboardStats = function() {
    TraccarFleet.apiCall('/dashboard/stats')
        .done(function(data) {
            // Aggiorna contatori
            $('#total-devices').text(data.total_devices || 0);
            $('#online-devices').text(data.online_devices || 0);
            $('#offline-devices').text(data.offline_devices || 0);
            $('#moving-devices').text(data.moving_devices || 0);

            // Aggiorna barre di progresso
            if (data.total_devices > 0) {
                const onlinePercent = (data.online_devices / data.total_devices) * 100;
                const offlinePercent = (data.offline_devices / data.total_devices) * 100;

                $('.progress-bar.bg-success').css('width', onlinePercent + '%');
                $('.progress-bar.bg-warning').css('width', offlinePercent + '%');
            }
        });
};

TraccarFleet.refreshNotifications = function() {
    TraccarFleet.apiCall('/notifications')
        .done(function(data) {
            $('#notification-count').text(data.count || 0);

            const dropdown = $('#notifications-dropdown');
            dropdown.empty();

            if (data.notifications && data.notifications.length > 0) {
                dropdown.append(`<span class="dropdown-item dropdown-header">${data.count} Notifiche</span>`);

                data.notifications.slice(0, 5).forEach(function(notification) {
                    const timeAgo = moment(notification.timestamp).fromNow();
                    dropdown.append(`
                        <div class="dropdown-divider"></div>
                        <a href="#" class="dropdown-item">
                            <i class="fas fa-${notification.icon || 'bell'} mr-2"></i>
                            ${notification.message}
                            <span class="float-right text-muted text-sm">${timeAgo}</span>
                        </a>
                    `);
                });

                dropdown.append('<div class="dropdown-divider"></div>');
                dropdown.append('<a href="/notifications" class="dropdown-item dropdown-footer">Vedi tutte le notifiche</a>');
            } else {
                dropdown.append('<span class="dropdown-item dropdown-header">Nessuna notifica</span>');
            }
        });
};

/**
 * ============================================
 * UTILITIES E HELPERS
 * ============================================ */
TraccarFleet.formatDateTime = function(dateString, format = null) {
    if (!dateString) return 'N/A';

    const date = moment(dateString);
    if (!date.isValid()) return 'N/A';

    return date.format(format || TraccarFleet.config.dateFormats.display);
};

TraccarFleet.formatDistance = function(meters) {
    if (!meters || meters === 0) return '0 m';

    const m = parseFloat(meters);
    if (m < 1000) {
        return `${Math.round(m)} m`;
    } else {
        return `${(m / 1000).toFixed(1)} km`;
    }
};

TraccarFleet.formatSpeed = function(knots) {
    if (!knots || knots === 0) return '0 km/h';

    const kmh = parseFloat(knots) * 1.852;
    return `${kmh.toFixed(1)} km/h`;
};

TraccarFleet.formatDuration = function(milliseconds) {
    if (!milliseconds) return '0m';

    const duration = moment.duration(milliseconds);
    const hours = Math.floor(duration.asHours());
    const minutes = duration.minutes();

    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    } else {
        return `${minutes}m`;
    }
};

TraccarFleet.formatPhone = function(phone) {
    // Rimuovi tutti i caratteri non numerici tranne +
    let cleaned = phone.replace(/[^\d+]/g, '');

    // Formatta numero italiano
    if (cleaned.startsWith('39') && cleaned.length === 12) {
        return `+${cleaned.substr(0, 2)} ${cleaned.substr(2, 3)} ${cleaned.substr(5, 3)} ${cleaned.substr(8, 4)}`;
    } else if (cleaned.startsWith('+39') && cleaned.length === 13) {
        return `${cleaned.substr(0, 3)} ${cleaned.substr(3, 3)} ${cleaned.substr(6, 3)} ${cleaned.substr(9, 4)}`;
    }

    return cleaned;
};

TraccarFleet.isValidEmail = function(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
};

TraccarFleet.isValidUrl = function(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
};

TraccarFleet.debounce = function(func, wait, immediate) {
    let timeout;
    return function executedFunction() {
        const context = this;
        const args = arguments;
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
};

TraccarFleet.throttle = function(func, limit) {
    let lastFunc;
    let lastRan;
    return function() {
        const context = this;
        const args = arguments;
        if (!lastRan) {
            func.apply(context, args);
            lastRan = Date.now();
        } else {
            clearTimeout(lastFunc);
            lastFunc = setTimeout(function() {
                if ((Date.now() - lastRan) >= limit) {
                    func.apply(context, args);
                    lastRan = Date.now();
                }
            }, limit - (Date.now() - lastRan));
        }
    };
};

/**
 * ============================================
 * GESTIONE RESPONSIVE
 * ============================================ */
TraccarFleet.handleResponsive = function() {
    const width = $(window).width();

    // Mobile
    if (width <= 768) {
        $('.sidebar').addClass('sidebar-collapse');
        $('.content-wrapper').css('margin-left', '0');
    }

    // Tablet
    else if (width <= 1024) {
        $('.sidebar').removeClass('sidebar-collapse');
        $('.content-wrapper').css('margin-left', '250px');
    }

    // Desktop
    else {
        $('.sidebar').removeClass('sidebar-collapse');
        $('.content-wrapper').css('margin-left', '250px');
    }
};

TraccarFleet.handleResize = function() {
    TraccarFleet.handleResponsive();

    // Ridimensiona mappe se presenti
    if (typeof L !== 'undefined') {
        $('.leaflet-container').each(function() {
            const mapId = $(this).attr('id');
            if (window[mapId]) {
                window[mapId].invalidateSize();
            }
        });
    }

    // Ridimensiona DataTables
    if (typeof $.fn.DataTable !== 'undefined') {
        $.fn.dataTable.tables({ visible: true, api: true }).columns.adjust();
    }
};

/**
 * ============================================
 * GESTIONE ERRORI
 * ============================================ */
TraccarFleet.handleUnauthorized = function() {
    TraccarFleet.showAlert(
        'Sessione scaduta',
        'La tua sessione è scaduta. Verrai reindirizzato alla pagina di login.',
        'warning'
    ).then(() => {
        window.location.href = '/login';
    });
};

TraccarFleet.handleError = function(error, context = '') {
    console.error('TraccarFleet Error:', context, error);

    let message = 'Si è verificato un errore imprevisto';

    if (typeof error === 'string') {
        message = error;
    } else if (error.responseJSON && error.responseJSON.error) {
        message = error.responseJSON.error;
    } else if (error.message) {
        message = error.message;
    }

    TraccarFleet.showToast(message, 'error');
};

/**
 * ============================================
 * EXPORT E UTILITIES VARIE
 * ============================================ */
TraccarFleet.exportData = function(target, format = 'csv') {
    const table = $(target).DataTable();
    if (table) {
        switch (format) {
            case 'csv':
                table.button('.buttons-csv').trigger();
                break;
            case 'excel':
                table.button('.buttons-excel').trigger();
                break;
            case 'pdf':
                table.button('.buttons-pdf').trigger();
                break;
            case 'print':
                table.button('.buttons-print').trigger();
                break;
        }
    }
};

TraccarFleet.refreshComponent = function(selector) {
    const $component = $(selector);

    if ($component.hasClass('card')) {
        $component.addClass('card-refresh');

        setTimeout(function() {
            $component.removeClass('card-refresh');
            location.reload();
        }, 1000);
    } else {
        location.reload();
    }
};

TraccarFleet.toggleComponent = function(selector) {
    $(selector).toggle();
};

/**
 * ============================================
 * STORAGE E CACHE
 * ============================================ */
TraccarFleet.setStorage = function(key, value, session = false) {
    const storage = session ? sessionStorage : localStorage;
    try {
        storage.setItem(`traccar_${key}`, JSON.stringify({
            value: value,
            timestamp: Date.now()
        }));
    } catch (e) {
        console.warn('Storage not available:', e);
    }
};

TraccarFleet.getStorage = function(key, session = false, maxAge = null) {
    const storage = session ? sessionStorage : localStorage;
    try {
        const item = storage.getItem(`traccar_${key}`);
        if (!item) return null;

        const data = JSON.parse(item);

        if (maxAge && (Date.now() - data.timestamp > maxAge)) {
            storage.removeItem(`traccar_${key}`);
            return null;
        }

        return data.value;
    } catch (e) {
        console.warn('Storage read error:', e);
        return null;
    }
};

TraccarFleet.clearStorage = function(session = false) {
    const storage = session ? sessionStorage : localStorage;
    const keys = Object.keys(storage).filter(key => key.startsWith('traccar_'));
    keys.forEach(key => storage.removeItem(key));
};

// Export per utilizzo in altri script
window.TraccarFleet = TraccarFleet;

console.log('📱 Traccar Fleet Management JavaScript loaded successfully');