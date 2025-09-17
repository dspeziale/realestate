/**
 * Traccar Fleet Management - Main Application JavaScript (FIXED)
 * ==============================================================
 */

// Namespace globale
window.TraccarFleet = window.TraccarFleet || {};

// Configurazione italiana per DataTables
window.italianDTLanguage = {
    "decimal": "",
    "emptyTable": "Nessun dato disponibile",
    "info": "Elementi da _START_ a _END_ di _TOTAL_ totali",
    "infoEmpty": "Elementi da 0 a 0 di 0 totali",
    "infoFiltered": "(filtrati da _MAX_ elementi totali)",
    "infoPostFix": "",
    "thousands": ".",
    "lengthMenu": "Mostra _MENU_ elementi",
    "loadingRecords": "Caricamento...",
    "processing": "Elaborazione...",
    "search": "Cerca:",
    "zeroRecords": "Nessun elemento trovato",
    "paginate": {
        "first": "Primo",
        "last": "Ultimo",
        "next": "Successivo",
        "previous": "Precedente"
    },
    "aria": {
        "sortAscending": ": attivare per ordinare la colonna in ordine crescente",
        "sortDescending": ": attivare per ordinare la colonna in ordine decrescente"
    }
};

// Configurazione globale
TraccarFleet.config = {
    apiBaseUrl: '/api',
    refreshInterval: 30000,
    mapDefaults: {
        center: [41.9028, 12.4964],
        zoom: 6,
        maxZoom: 18
    },
    dateFormats: {
        display: 'DD/MM/YYYY HH:mm:ss',
        api: 'YYYY-MM-DDTHH:mm:ss',
        short: 'DD/MM/YYYY'
    }
};

/**
 * INIZIALIZZAZIONE APPLICAZIONE
 */
$(document).ready(function() {
    TraccarFleet.init();
});

TraccarFleet.init = function() {
    console.log('🚀 Inizializzazione Traccar Fleet Management');

    if (typeof moment !== 'undefined') {
        moment.locale('it');
    }

    this.initializeGlobalEvents();
    this.initializeTooltips();
    this.initializeDataTables();
    this.initializeFormValidation();
    this.initializeAjaxDefaults();
    this.startAutoRefresh();
    this.handleResponsive();

    console.log('✅ Inizializzazione completata');
};

/**
 * DATATABLES CONFIGURAZIONE SICURA
 */
TraccarFleet.initializeDataTables = function() {
    if (typeof $.fn.DataTable !== 'undefined') {
        // ✅ CONFIGURAZIONE PREDEFINITA SICURA
        $.extend(true, $.fn.dataTable.defaults, {
            language: window.italianDTLanguage,
            responsive: true,
            pageLength: 25,
            lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "Tutti"]],
            dom: "<'row'<'col-sm-6'l><'col-sm-6'f>>" +
                 "<'row'<'col-sm-12'tr>>" +
                 "<'row'<'col-sm-5'i><'col-sm-7'p>>",
            // ✅ CALLBACK COMPLETO E SICURO
            initComplete: function(settings, json) {
                try {
                    $(this).closest('.dataTables_wrapper').find('.dt-buttons').addClass('mb-3');
                } catch (e) {
                    console.warn('DataTables initComplete warning:', e);
                }
            },
            // ✅ GESTIONE ERRORI PER PREVENIRE CRASH
            error: function(settings, helpPage, message) {
                console.error('DataTables Error:', message);
                // Non bloccare l'applicazione
                return false;
            }
        });
    }
};

/**
 * ✅ HELPER SICURO PER INIZIALIZZARE DATATABLES
 */
TraccarFleet.initDataTable = function(selector, options = {}) {
    const $table = $(selector);

    if ($table.length === 0) {
        console.warn(`DataTable: Tabella ${selector} non trovata`);
        return null;
    }

    // ✅ VERIFICA STRUTTURA TABELLA
    const headerColumns = $table.find('thead th').length;
    const bodyColumns = $table.find('tbody tr:first td').length;

    if (headerColumns > 0 && bodyColumns > 0 && headerColumns !== bodyColumns) {
        console.error(`DataTable: Mismatch colonne - Header: ${headerColumns}, Body: ${bodyColumns}`);
        // Ritorna null invece di creare una tabella rotta
        return null;
    }

    try {
        // ✅ SE GIÀ INIZIALIZZATO, DISTRUGGI IN MODO SICURO
        if ($.fn.DataTable.isDataTable(selector)) {
            console.log(`DataTable: Distruggendo tabella esistente ${selector}`);
            $table.DataTable().clear().destroy();
            $table.empty(); // ✅ PULISCI COMPLETAMENTE
        }

        // ✅ OPZIONI PREDEFINITE SICURE
        const defaultOptions = {
            responsive: true,
            language: window.italianDTLanguage,
            // ✅ PREVENZIONE ERRORI
            autoWidth: false,
            processing: true,
            deferRender: true,
            // ✅ GESTIONE ERRORI GLOBALE
            error: function(settings, helpPage, message) {
                console.error(`DataTable ${selector} Error:`, message);
                TraccarFleet.showToast('Errore nella tabella: ' + message, 'error');
            }
        };

        const finalOptions = $.extend(true, {}, defaultOptions, options);

        // ✅ INIZIALIZZA CON TRY-CATCH
        const dataTable = $table.DataTable(finalOptions);
        console.log(`✅ DataTable ${selector} inizializzato con successo`);

        return dataTable;

    } catch (error) {
        console.error(`DataTable ${selector} initialization failed:`, error);
        TraccarFleet.showToast(`Errore inizializzazione tabella: ${error.message}`, 'error');
        return null;
    }
};

/**
 * ✅ HELPER PER REINIZIALIZZARE DATATABLES SICURAMENTE
 */
TraccarFleet.safeReinitializeDataTable = function(selector, newData = null, options = {}) {
    try {
        const $table = $(selector);

        if ($.fn.DataTable.isDataTable(selector)) {
            const dt = $table.DataTable();

            if (newData) {
                // Aggiorna i dati mantenendo la struttura
                dt.clear().rows.add(newData).draw();
            } else {
                // Semplicemente ridisegna
                dt.draw();
            }

            return dt;
        } else {
            // Inizializza per la prima volta
            return TraccarFleet.initDataTable(selector, options);
        }
    } catch (error) {
        console.error(`Safe reinitialize failed for ${selector}:`, error);
        return null;
    }
};

/**
 * EVENTI GLOBALI
 */
TraccarFleet.initializeGlobalEvents = function() {
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

    // ✅ GESTIONE ERRORI AJAX MIGLIORATA
    $(document).ajaxError(function(event, xhr, settings, error) {
        console.error('AJAX Error:', {
            status: xhr.status,
            url: settings.url,
            error: error
        });

        if (xhr.status === 401) {
            TraccarFleet.handleUnauthorized();
        } else if (xhr.status >= 500) {
            TraccarFleet.showToast('Errore del server', 'error');
        } else if (xhr.status === 0) {
            TraccarFleet.showToast('Connessione persa', 'warning');
        }
    });

    window.addEventListener('online', function() {
        TraccarFleet.showToast('Connessione ripristinata', 'success');
        TraccarFleet.startAutoRefresh();
    });

    window.addEventListener('offline', function() {
        TraccarFleet.showToast('Connessione persa', 'warning');
        TraccarFleet.stopAutoRefresh();
    });
};

/**
 * TOOLTIPS E POPOVERS
 */
TraccarFleet.initializeTooltips = function() {
    if (typeof $.fn.tooltip !== 'undefined') {
        $('[data-toggle="tooltip"]').tooltip({
            container: 'body',
            delay: { show: 500, hide: 100 }
        });
    }

    if (typeof $.fn.popover !== 'undefined') {
        $('[data-toggle="popover"]').popover({
            container: 'body',
            trigger: 'hover',
            html: true
        });
    }
};

/**
 * VALIDAZIONE FORM
 */
TraccarFleet.initializeFormValidation = function() {
    $(document).on('blur', '.form-control[required]', function() {
        TraccarFleet.validateField(this);
    });

    $(document).on('submit', 'form[data-validate="true"]', function(e) {
        if (!TraccarFleet.validateForm(this)) {
            e.preventDefault();
            return false;
        }
    });
};

TraccarFleet.validateField = function(field) {
    const $field = $(field);
    const value = $field.val().trim();
    const isRequired = $field.prop('required');

    if (isRequired && !value) {
        $field.addClass('is-invalid').removeClass('is-valid');
        return false;
    } else {
        $field.addClass('is-valid').removeClass('is-invalid');
        return true;
    }
};

TraccarFleet.validateForm = function(form) {
    let isValid = true;
    $(form).find('.form-control[required]').each(function() {
        if (!TraccarFleet.validateField(this)) {
            isValid = false;
        }
    });
    return isValid;
};

/**
 * AJAX CONFIGURAZIONE
 */
TraccarFleet.initializeAjaxDefaults = function() {
    $.ajaxSetup({
        beforeSend: function(xhr) {
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        },
        timeout: 30000, // ✅ TIMEOUT DI 30 SECONDI
        error: function(xhr, status, error) {
            console.error('AJAX Error:', { status, error, xhr });
        }
    });
};

/**
 * ✅ TOAST SICURO
 */
TraccarFleet.showToast = function(message, type = 'info') {
    if (typeof Swal !== 'undefined') {
        Swal.fire({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: 3000,
            timerProgressBar: true,
            icon: type,
            title: message
        });
    } else {
        // Fallback per console
        console.log(`Toast ${type}: ${message}`);
    }
};

/**
 * AUTO-REFRESH
 */
TraccarFleet.startAutoRefresh = function() {
    this.stopAutoRefresh(); // Evita duplicati

    this.refreshInterval = setInterval(function() {
        $('.auto-refresh').each(function() {
            const url = $(this).data('refresh-url');
            if (url) {
                TraccarFleet.refreshComponent(this, url);
            }
        });
    }, TraccarFleet.config.refreshInterval);
};

TraccarFleet.stopAutoRefresh = function() {
    if (this.refreshInterval) {
        clearInterval(this.refreshInterval);
        this.refreshInterval = null;
    }
};

TraccarFleet.refreshComponent = function(element, url = null) {
    const $element = $(element);
    url = url || $element.data('refresh-url');

    if (!url) return;

    $.get(url)
        .done(function(data) {
            $element.html(data);
            // ✅ REINIZIALIZZA DATATABLES SE NECESSARIO
            $element.find('table').each(function() {
                if ($(this).hasClass('dataTable') || $(this).data('datatable')) {
                    TraccarFleet.safeReinitializeDataTable(this);
                }
            });
        })
        .fail(function() {
            TraccarFleet.showToast('Errore aggiornamento componente', 'error');
        });
};

/**
 * RESPONSIVE HANDLING
 */
TraccarFleet.handleResponsive = function() {
    $(window).on('resize', function() {
        // Ridisegna le DataTables responsive
        $('.dataTable').each(function() {
            if ($.fn.DataTable.isDataTable(this)) {
                $(this).DataTable().responsive.recalc();
            }
        });
    });
};

/**
 * UTILITÀ
 */
TraccarFleet.handleUnauthorized = function() {
    TraccarFleet.showToast('Sessione scaduta', 'warning');
    setTimeout(() => {
        window.location.href = '/login';
    }, 2000);
};

TraccarFleet.exportData = function(target) {
    const $target = $(target);
    if ($.fn.DataTable.isDataTable(target)) {
        $target.DataTable().button('.buttons-excel').trigger();
    }
};

TraccarFleet.toggleComponent = function(target) {
    $(target).toggle();
};

/**
 * STORAGE UTILITIES
 */
TraccarFleet.setStorage = function(key, value, maxAge = null, session = false) {
    const storage = session ? sessionStorage : localStorage;
    const data = {
        value: value,
        timestamp: Date.now()
    };

    if (maxAge) {
        data.maxAge = maxAge;
    }

    try {
        storage.setItem(`traccar_${key}`, JSON.stringify(data));
        return true;
    } catch (e) {
        console.warn('Storage write error:', e);
        return false;
    }
};

TraccarFleet.getStorage = function(key, maxAge = null, session = false) {
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

// Export per utilizzo globale
window.TraccarFleet = TraccarFleet;

console.log('📱 Traccar Fleet Management JavaScript loaded successfully');