/**
 * Traccar Fleet Management - Main Application JavaScript
 * ====================================================
 */

// Namespace globale
window.TraccarFleet = window.TraccarFleet || {};

// Configurazione italiana per DataTables (inline per evitare errori 404)
const italianDTLanguage = {
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
 * DATATABLES CONFIGURAZIONE
 */
TraccarFleet.initializeDataTables = function() {
    if (typeof $.fn.DataTable !== 'undefined') {
        $.extend(true, $.fn.dataTable.defaults, {
            language: italianDTLanguage, // ✅ USA CONFIGURAZIONE INLINE
            responsive: true,
            pageLength: 25,
            lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "Tutti"]],
            dom: "<'row'<'col-sm-6'l><'col-sm-6'f>>" +
                 "<'row'<'col-sm-12'tr>>" +
                 "<'row'<'col-sm-5'i><'col-sm-7'p>>",
            initComplete: function(settings, json) {
                $(this).closest('.dataTables_wrapper').find('.dt-buttons').addClass('mb-3');
            }
        });
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

    $(document).ajaxError(function(event, xhr, settings, error) {
        if (xhr.status === 401) {
            TraccarFleet.handleUnauthorized();
        } else if (xhr.status >= 500) {
            TraccarFleet.showToast('Errore del server', 'error');
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
    $('[data-toggle="tooltip"]').tooltip({
        container: 'body',
        delay: { show: 500, hide: 100 }
    });

    $('[data-toggle="popover"]').popover({
        container: 'body',
        trigger: 'hover',
        html: true
    });
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
        error: function(xhr, status, error) {
            console.error('AJAX Error:', status, error);
        }
    });
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
                TraccarFleet.refreshComponent($(this), url);
            }
        });
    }, this.config.refreshInterval);
};

TraccarFleet.stopAutoRefresh = function() {
    if (this.refreshInterval) {
        clearInterval(this.refreshInterval);
        this.refreshInterval = null;
    }
};

/**
 * UTILITY FUNCTIONS
 */
TraccarFleet.refreshComponent = function(target, url) {
    if (!url) return;

    $.get(url)
        .done(function(data) {
            if (typeof target === 'string') {
                $(target).html(data);
            } else {
                target.html(data);
            }
        })
        .fail(function() {
            console.warn('Refresh failed for:', url);
        });
};

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
        // Fallback se SweetAlert2 non è disponibile
        console.log(`Toast ${type}: ${message}`);
    }
};

TraccarFleet.handleUnauthorized = function() {
    this.showToast('Sessione scaduta, reindirizzamento...', 'warning');
    setTimeout(function() {
        window.location.href = '/login';
    }, 2000);
};

TraccarFleet.handleResponsive = function() {
    // Gestione responsive per mobile
    if ($(window).width() < 768) {
        $('.sidebar').addClass('sidebar-collapse');
    }
};

TraccarFleet.debounce = function(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = function() {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

// Storage utilities
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

// Export per utilizzo in altri script
window.TraccarFleet = TraccarFleet;

console.log('📱 Traccar Fleet Management JavaScript loaded successfully');