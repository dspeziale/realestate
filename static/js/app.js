// Filename: static/js/app.js
// Copyright 2025 SILICONDEV SPA
// Description: Modern JavaScript for Real Estate Auction Management

class ModernUI {
    constructor() {
        this.sidebarCollapsed = false;
        this.darkMode = false;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupAnimations();
        this.setupTheme();
        this.setupNotifications();
        this.setupLoading();
        console.log('🚀 ModernUI initialized successfully');
    }

    setupEventListeners() {
        // Sidebar toggle
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        }

        // Dark mode toggle (if exists)
        const darkModeToggle = document.getElementById('darkModeToggle');
        if (darkModeToggle) {
            darkModeToggle.addEventListener('click', () => this.toggleDarkMode());
        }

        // Form enhancements
        this.enhanceForms();

        // Button enhancements
        this.enhanceButtons();

        // Card interactions
        this.enhanceCards();

        // Search functionality
        this.setupSearch();

        // Responsive handlers
        window.addEventListener('resize', () => this.handleResize());
        this.handleResize(); // Initial call
    }

    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.getElementById('mainContent');
        const topbar = document.getElementById('topbar');

        if (sidebar && mainContent && topbar) {
            this.sidebarCollapsed = !this.sidebarCollapsed;

            sidebar.classList.toggle('collapsed', this.sidebarCollapsed);
            mainContent.classList.toggle('sidebar-collapsed', this.sidebarCollapsed);
            topbar.classList.toggle('sidebar-collapsed', this.sidebarCollapsed);

            // Store state in localStorage
            localStorage.setItem('sidebarCollapsed', this.sidebarCollapsed);

            // Animate nav text
            const navTexts = document.querySelectorAll('.nav-text');
            navTexts.forEach(text => {
                if (this.sidebarCollapsed) {
                    text.style.opacity = '0';
                    setTimeout(() => text.style.display = 'none', 300);
                } else {
                    text.style.display = 'inline';
                    setTimeout(() => text.style.opacity = '1', 100);
                }
            });
        }
    }

    toggleDarkMode() {
        this.darkMode = !this.darkMode;
        const html = document.documentElement;

        if (this.darkMode) {
            html.setAttribute('data-bs-theme', 'dark');
        } else {
            html.setAttribute('data-bs-theme', 'light');
        }

        localStorage.setItem('darkMode', this.darkMode);
        this.updateThemeIcon();
    }

    setupTheme() {
        // Restore saved theme
        const savedTheme = localStorage.getItem('darkMode');
        if (savedTheme !== null) {
            this.darkMode = savedTheme === 'true';
            this.toggleDarkMode();
        }

        // Restore sidebar state
        const savedSidebarState = localStorage.getItem('sidebarCollapsed');
        if (savedSidebarState !== null) {
            this.sidebarCollapsed = savedSidebarState === 'true';
            if (this.sidebarCollapsed) {
                this.toggleSidebar();
            }
        }
    }

    updateThemeIcon() {
        const themeIcon = document.getElementById('themeIcon');
        if (themeIcon) {
            themeIcon.className = this.darkMode ? 'bi bi-sun' : 'bi bi-moon';
        }
    }

    enhanceForms() {
        // Add floating label animation
        const inputs = document.querySelectorAll('.form-control, .form-select');
        inputs.forEach(input => {
            // Add focus/blur effects
            input.addEventListener('focus', (e) => {
                e.target.parentElement.classList.add('input-focused');
                this.addRipple(e.target, e);
            });

            input.addEventListener('blur', (e) => {
                e.target.parentElement.classList.remove('input-focused');
            });

            // Validation styling
            input.addEventListener('invalid', (e) => {
                e.target.classList.add('is-invalid');
                this.showValidationError(e.target);
            });

            input.addEventListener('input', (e) => {
                if (e.target.checkValidity()) {
                    e.target.classList.remove('is-invalid');
                    e.target.classList.add('is-valid');
                }
            });
        });

        // Form submission with loading states
        const forms = document.querySelectorAll('form');
        forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                this.handleFormSubmission(form);
            });
        });
    }

    enhanceButtons() {
        const buttons = document.querySelectorAll('.btn');
        buttons.forEach(button => {
            // Add ripple effect
            button.addEventListener('click', (e) => {
                this.addRipple(button, e);

                // Add click animation
                button.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    button.style.transform = '';
                }, 150);
            });

            // Add loading state capability
            if (button.hasAttribute('data-loading-text')) {
                button.originalText = button.innerHTML;
            }
        });
    }

    enhanceCards() {
        const cards = document.querySelectorAll('.card-modern, .stats-card');
        cards.forEach(card => {
            // Add intersection observer for animations
            this.observeElement(card, () => {
                card.classList.add('animate-fade-in-up');
            });

            // Add hover effects
            card.addEventListener('mouseenter', () => {
                card.style.transform = 'translateY(-8px) scale(1.02)';
            });

            card.addEventListener('mouseleave', () => {
                card.style.transform = '';
            });
        });
    }

    setupSearch() {
        const searchInputs = document.querySelectorAll('[data-search]');
        searchInputs.forEach(input => {
            let searchTimeout;

            input.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                const searchTerm = e.target.value.toLowerCase();
                const target = e.target.getAttribute('data-search');

                searchTimeout = setTimeout(() => {
                    this.performSearch(searchTerm, target);
                }, 300);
            });
        });
    }

    performSearch(term, target) {
        const elements = document.querySelectorAll(`[data-searchable="${target}"]`);
        elements.forEach(element => {
            const text = element.textContent.toLowerCase();
            if (text.includes(term) || term === '') {
                element.style.display = '';
                element.classList.add('animate-fade-in-up');
            } else {
                element.style.display = 'none';
            }
        });
    }

    addRipple(element, event) {
        const ripple = document.createElement('div');
        const rect = element.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = event.clientX - rect.left - size / 2;
        const y = event.clientY - rect.top - size / 2;

        ripple.style.cssText = `
            position: absolute;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.3);
            transform: scale(0);
            animation: ripple 0.6s linear;
            width: ${size}px;
            height: ${size}px;
            left: ${x}px;
            top: ${y}px;
            pointer-events: none;
        `;

        element.style.position = 'relative';
        element.style.overflow = 'hidden';
        element.appendChild(ripple);

        setTimeout(() => ripple.remove(), 600);
    }

    showValidationError(input) {
        const errorMsg = input.validationMessage;
        let errorDiv = input.parentElement.querySelector('.validation-error');

        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.className = 'validation-error text-danger small mt-1';
            input.parentElement.appendChild(errorDiv);
        }

        errorDiv.textContent = errorMsg;
        errorDiv.style.animation = 'shake 0.5s ease-in-out';
    }

    handleFormSubmission(form) {
        const submitButton = form.querySelector('button[type="submit"]');
        if (submitButton) {
            this.setButtonLoading(submitButton, true);
        }

        // Show loading overlay
        this.showLoading();

        // Simulate form processing (remove in production)
        setTimeout(() => {
            this.hideLoading();
            if (submitButton) {
                this.setButtonLoading(submitButton, false);
            }
        }, 2000);
    }

    setButtonLoading(button, loading) {
        if (loading) {
            if (!button.originalText) {
                button.originalText = button.innerHTML;
            }
            button.innerHTML = `
                <span class="spinner-border spinner-border-sm me-2" role="status"></span>
                ${button.getAttribute('data-loading-text') || 'Caricamento...'}
            `;
            button.disabled = true;
        } else {
            button.innerHTML = button.originalText;
            button.disabled = false;
        }
    }

    setupLoading() {
        // Create loading overlay if it doesn't exist
        if (!document.getElementById('loadingOverlay')) {
            const overlay = document.createElement('div');
            overlay.id = 'loadingOverlay';
            overlay.className = 'loading-overlay';
            overlay.innerHTML = `
                <div class="text-center">
                    <div class="spinner mb-3"></div>
                    <p class="text-muted">Caricamento...</p>
                </div>
            `;
            document.body.appendChild(overlay);
        }
    }

    showLoading() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.classList.add('show');
        }
    }

    hideLoading() {
        const overlay = document.getElementById('loadingOverlay');
        if (overlay) {
            overlay.classList.remove('show');
        }
    }

    setupNotifications() {
        // Auto-hide alerts
        const alerts = document.querySelectorAll('.alert:not(.alert-danger)');
        alerts.forEach(alert => {
            setTimeout(() => {
                this.fadeOutAlert(alert);
            }, 5000);
        });

        // Keep error alerts longer
        const errorAlerts = document.querySelectorAll('.alert-danger');
        errorAlerts.forEach(alert => {
            setTimeout(() => {
                this.fadeOutAlert(alert);
            }, 10000);
        });
    }

    fadeOutAlert(alert) {
        alert.style.transition = 'all 0.5s ease';
        alert.style.opacity = '0';
        alert.style.transform = 'translateX(100%)';

        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            if (bsAlert) bsAlert.close();
        }, 500);
    }

    setupAnimations() {
        // Add CSS animations
        const style = document.createElement('style');
        style.textContent = `
            @keyframes ripple {
                to {
                    transform: scale(2);
                    opacity: 0;
                }
            }
            @keyframes shake {
                0%, 100% { transform: translateX(0); }
                25% { transform: translateX(-5px); }
                75% { transform: translateX(5px); }
            }
            .input-focused {
                transform: scale(1.02);
                z-index: 10;
            }
        `;
        document.head.appendChild(style);
    }

    observeElement(element, callback) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    callback();
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });

        observer.observe(element);
    }

    handleResize() {
        const isMobile = window.innerWidth <= 768;
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.getElementById('mainContent');
        const topbar = document.getElementById('topbar');

        if (isMobile) {
            // Mobile behavior
            if (sidebar) sidebar.classList.add('d-none', 'd-md-block');
            if (mainContent) {
                mainContent.style.marginLeft = '0';
                mainContent.classList.remove('sidebar-collapsed');
            }
            if (topbar) {
                topbar.style.left = '0';
                topbar.classList.remove('sidebar-collapsed');
            }
        } else {
            // Desktop behavior
            if (sidebar) sidebar.classList.remove('d-none');
            this.restoreDesktopLayout();
        }
    }

    restoreDesktopLayout() {
        const mainContent = document.getElementById('mainContent');
        const topbar = document.getElementById('topbar');

        if (this.sidebarCollapsed) {
            if (mainContent) mainContent.classList.add('sidebar-collapsed');
            if (topbar) topbar.classList.add('sidebar-collapsed');
        } else {
            if (mainContent) {
                mainContent.style.marginLeft = 'var(--sidebar-width)';
                mainContent.classList.remove('sidebar-collapsed');
            }
            if (topbar) {
                topbar.style.left = 'var(--sidebar-width)';
                topbar.classList.remove('sidebar-collapsed');
            }
        }
    }

    // Utility methods
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} toast-notification position-fixed`;
        toast.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            animation: slideInRight 0.5s ease-out;
        `;
        toast.innerHTML = `
            <i class="bi bi-${this.getToastIcon(type)} me-2"></i>
            ${message}
            <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
        `;

        document.body.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.style.animation = 'slideOutRight 0.5s ease-in';
                setTimeout(() => toast.remove(), 500);
            }
        }, 5000);
    }

    getToastIcon(type) {
        const icons = {
            'success': 'check-circle',
            'danger': 'exclamation-triangle',
            'warning': 'exclamation-triangle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    // Advanced table features
    enhanceTable(tableId) {
        const table = document.getElementById(tableId);
        if (!table) return;

        // Add sorting capability
        const headers = table.querySelectorAll('th[data-sort]');
        headers.forEach(header => {
            header.style.cursor = 'pointer';
            header.addEventListener('click', () => this.sortTable(table, header));
        });

        // Add row selection
        if (table.hasAttribute('data-selectable')) {
            this.makeTableSelectable(table);
        }

        // Add search filtering
        if (table.hasAttribute('data-filterable')) {
            this.addTableFilter(table);
        }
    }

    sortTable(table, header) {
        const column = Array.from(header.parentElement.children).indexOf(header);
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const sortType = header.getAttribute('data-sort');
        const isAsc = header.classList.contains('sort-asc');

        rows.sort((a, b) => {
            const aVal = a.children[column].textContent.trim();
            const bVal = b.children[column].textContent.trim();

            if (sortType === 'number') {
                return isAsc ? parseFloat(bVal) - parseFloat(aVal) : parseFloat(aVal) - parseFloat(bVal);
            } else if (sortType === 'date') {
                return isAsc ? new Date(bVal) - new Date(aVal) : new Date(aVal) - new Date(bVal);
            } else {
                return isAsc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal);
            }
        });

        // Update header classes
        table.querySelectorAll('th').forEach(th => th.classList.remove('sort-asc', 'sort-desc'));
        header.classList.add(isAsc ? 'sort-desc' : 'sort-asc');

        // Rebuild table
        rows.forEach(row => tbody.appendChild(row));
    }

    makeTableSelectable(table) {
        const tbody = table.querySelector('tbody');
        const rows = tbody.querySelectorAll('tr');

        rows.forEach(row => {
            row.addEventListener('click', () => {
                row.classList.toggle('table-active');
                const checkbox = row.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    checkbox.checked = row.classList.contains('table-active');
                }
            });
        });
    }

    // Modal enhancements
    enhanceModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        const bsModal = new bootstrap.Modal(modal);

        // Add backdrop blur effect
        modal.addEventListener('show.bs.modal', () => {
            document.body.style.filter = 'blur(2px)';
            modal.style.filter = 'none';
        });

        modal.addEventListener('hidden.bs.modal', () => {
            document.body.style.filter = 'none';
        });

        // Add loading state
        const form = modal.querySelector('form');
        if (form) {
            form.addEventListener('submit', () => {
                const submitBtn = form.querySelector('button[type="submit"]');
                if (submitBtn) {
                    this.setButtonLoading(submitBtn, true);
                }
            });
        }

        return bsModal;
    }

    // Chart integration (if needed)
    createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // This would integrate with Chart.js if included
        // For now, return a placeholder
        console.log(`Chart would be created on ${canvasId} with config:`, config);
    }

    // File upload enhancements
    enhanceFileUpload(inputId) {
        const input = document.getElementById(inputId);
        if (!input) return;

        const wrapper = document.createElement('div');
        wrapper.className = 'file-upload-wrapper position-relative';

        const dropzone = document.createElement('div');
        dropzone.className = 'file-dropzone border-2 border-dashed rounded p-4 text-center';
        dropzone.innerHTML = `
            <i class="bi bi-cloud-upload display-4 text-muted"></i>
            <p class="mt-2">Trascina i file qui o <span class="text-primary">clicca per selezionare</span></p>
            <small class="text-muted">Formati supportati: PDF, DOC, DOCX, JPG, PNG</small>
        `;

        input.parentElement.insertBefore(wrapper, input);
        wrapper.appendChild(dropzone);
        wrapper.appendChild(input);
        input.style.display = 'none';

        // Drag and drop functionality
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, this.preventDefaults, false);
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.add('border-primary'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, () => dropzone.classList.remove('border-primary'), false);
        });

        dropzone.addEventListener('drop', (e) => this.handleDrop(e, input), false);
        dropzone.addEventListener('click', () => input.click());

        input.addEventListener('change', () => this.displaySelectedFiles(input));
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    handleDrop(e, input) {
        const dt = e.dataTransfer;
        const files = dt.files;
        input.files = files;
        this.displaySelectedFiles(input);
    }

    displaySelectedFiles(input) {
        const fileList = Array.from(input.files);
        const wrapper = input.closest('.file-upload-wrapper');
        let fileDisplay = wrapper.querySelector('.file-display');

        if (!fileDisplay) {
            fileDisplay = document.createElement('div');
            fileDisplay.className = 'file-display mt-3';
            wrapper.appendChild(fileDisplay);
        }

        fileDisplay.innerHTML = fileList.map(file => `
            <div class="file-item d-flex align-items-center justify-content-between p-2 border rounded mb-2">
                <div>
                    <i class="bi bi-file-earmark me-2"></i>
                    <span>${file.name}</span>
                    <small class="text-muted ms-2">(${this.formatFileSize(file.size)})</small>
                </div>
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.parentElement.parentElement.remove()">
                    <i class="bi bi-x"></i>
                </button>
            </div>
        `).join('');
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Data export functionality
    exportTableData(tableId, format = 'csv') {
        const table = document.getElementById(tableId);
        if (!table) return;

        const rows = Array.from(table.querySelectorAll('tr'));
        const data = rows.map(row =>
            Array.from(row.querySelectorAll('th, td')).map(cell =>
                cell.textContent.trim()
            )
        );

        if (format === 'csv') {
            this.downloadCSV(data, `${tableId}-export.csv`);
        } else if (format === 'json') {
            this.downloadJSON(data, `${tableId}-export.json`);
        }
    }

    downloadCSV(data, filename) {
        const csv = data.map(row =>
            row.map(cell => `"${cell.replace(/"/g, '""')}"`).join(',')
        ).join('\n');

        this.downloadFile(csv, filename, 'text/csv');
    }

    downloadJSON(data, filename) {
        const json = JSON.stringify(data, null, 2);
        this.downloadFile(json, filename, 'application/json');
    }

    downloadFile(content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }

    // Performance monitoring
    measurePerformance(name, fn) {
        const start = performance.now();
        const result = fn();
        const end = performance.now();
        console.log(`${name} took ${end - start} milliseconds`);
        return result;
    }

    // Cleanup method
    destroy() {
        // Remove event listeners and cleanup
        const elements = document.querySelectorAll('[data-enhanced]');
        elements.forEach(el => {
            el.removeAttribute('data-enhanced');
            // Remove specific event listeners if needed
        });
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.modernUI = new ModernUI();

    // Hide initial loading after page load
    setTimeout(() => {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.classList.remove('show');
        }
    }, 1000);
});

// Expose utility functions globally
window.showToast = (message, type = 'info') => {
    if (window.modernUI) {
        window.modernUI.showToast(message, type);
    }
};

window.showLoading = () => {
    if (window.modernUI) {
        window.modernUI.showLoading();
    }
};

window.hideLoading = () => {
    if (window.modernUI) {
        window.modernUI.hideLoading();
    }
};

// Add additional CSS animations via JavaScript
const additionalStyles = `
@keyframes slideInRight {
    from {
        opacity: 0;
        transform: translateX(100%);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

@keyframes slideOutRight {
    from {
        opacity: 1;
        transform: translateX(0);
    }
    to {
        opacity: 0;
        transform: translateX(100%);
    }
}

.toast-notification {
    animation-fill-mode: both;
}

.file-dropzone {
    transition: all 0.3s ease;
    background: rgba(255, 255, 255, 0.5);
    backdrop-filter: blur(5px);
}

.file-dropzone:hover {
    background: rgba(102, 126, 234, 0.05);
    transform: translateY(-2px);
}

.file-dropzone.border-primary {
    background: rgba(102, 126, 234, 0.1);
    transform: scale(1.02);
}

.table th.sort-asc::after {
    content: " ↑";
    color: var(--primary-color);
}

.table th.sort-desc::after {
    content: " ↓";
    color: var(--primary-color);
}

.table-active {
    background-color: rgba(102, 126, 234, 0.1) !important;
    transform: scale(1.01);
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.2);
}
`;

// Inject additional styles
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);