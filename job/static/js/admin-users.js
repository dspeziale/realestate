// static/js/admin-users.js - Admin Users Management JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Role change handlers
    document.querySelectorAll('.role-select').forEach(select => {
        select.addEventListener('change', async function() {
            const userId = this.getAttribute('data-user-id');
            const newRole = this.value;
            const originalRole = this.getAttribute('data-original-role') || this.value;

            if (!confirm(`Sei sicuro di voler cambiare il ruolo dell'utente a "${newRole}"?`)) {
                this.value = originalRole;
                return;
            }

            try {
                const response = await fetch(`/auth/admin/users/${userId}/role`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ role: newRole })
                });

                const data = await response.json();

                if (data.success) {
                    this.setAttribute('data-original-role', newRole);
                    window.timesheetApp.showAlert('success', data.message);
                } else {
                    this.value = originalRole;
                    window.timesheetApp.showAlert('danger', data.message);
                }
            } catch (error) {
                this.value = originalRole;
                window.timesheetApp.showAlert('danger', 'Errore nella comunicazione con il server');
            }
        });

        // Store original value
        select.setAttribute('data-original-role', select.value);
    });

    // Status toggle handlers
    document.querySelectorAll('.toggle-status-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const userId = this.getAttribute('data-user-id');
            const statusBadge = document.querySelector(`.status-badge[data-user-id="${userId}"]`);
            const isActive = statusBadge.classList.contains('bg-success');
            const action = isActive ? 'disattivare' : 'attivare';

            if (!confirm(`Sei sicuro di voler ${action} questo utente?`)) {
                return;
            }

            try {
                const response = await fetch(`/auth/admin/users/${userId}/toggle`, {
                    method: 'POST'
                });

                const data = await response.json();

                if (data.success) {
                    // Update status badge
                    if (data.is_active) {
                        statusBadge.className = 'badge bg-success status-badge';
                        statusBadge.innerHTML = '<i class="bi bi-check-circle"></i> Attivo';
                        statusBadge.setAttribute('data-user-id', userId);
                        this.title = 'Disattiva';
                    } else {
                        statusBadge.className = 'badge bg-warning status-badge';
                        statusBadge.innerHTML = '<i class="bi bi-pause-circle"></i> Disattivato';
                        statusBadge.setAttribute('data-user-id', userId);
                        this.title = 'Attiva';
                    }

                    window.timesheetApp.showAlert('success', data.message);
                } else {
                    window.timesheetApp.showAlert('danger', data.message);
                }
            } catch (error) {
                window.timesheetApp.showAlert('danger', 'Errore nella comunicazione con il server');
            }
        });
    });

    // Delete user handlers (only for users with no data)
    document.querySelectorAll('.delete-user-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const userId = this.getAttribute('data-user-id');

            if (!confirm('Sei sicuro di voler eliminare questo utente? Questa azione non può essere annullata.')) {
                return;
            }

            try {
                const response = await fetch(`/auth/admin/users/${userId}/delete`, {
                    method: 'POST'
                });

                const data = await response.json();

                if (data.success) {
                    // Remove row from table
                    const row = document.querySelector(`tr[data-user-id="${userId}"]`);
                    row.remove();

                    window.timesheetApp.showAlert('success', data.message);

                    // Update statistics
                    updateStatistics();
                } else {
                    window.timesheetApp.showAlert('danger', data.message);
                }
            } catch (error) {
                window.timesheetApp.showAlert('danger', 'Errore nella comunicazione con il server');
            }
        });
    });

    // Table search/filter functionality
    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'form-control mb-3';
    searchInput.placeholder = 'Cerca utenti...';
    searchInput.id = 'user-search';

    const cardBody = document.querySelector('.card-body');
    if (cardBody && document.getElementById('users-table')) {
        cardBody.insertBefore(searchInput, cardBody.firstChild);

        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const rows = document.querySelectorAll('#users-table tbody tr');

            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });

            // Update visible count
            const visibleRows = Array.from(rows).filter(row => row.style.display !== 'none');
            updateVisibleCount(visibleRows.length, rows.length);
        });
    }

    function updateVisibleCount(visible, total) {
        const badge = document.querySelector('.badge.bg-info');
        if (badge) {
            if (visible === total) {
                badge.textContent = `${total} utenti totali`;
            } else {
                badge.textContent = `${visible} di ${total} utenti`;
            }
        }
    }

    function updateStatistics() {
        // This could be enhanced to update the statistics cards
        // without a full page reload
        console.log('Statistics updated after user deletion');
    }

    // Bulk actions (future enhancement)
    function initBulkActions() {
        // Add checkboxes to rows for bulk operations
        // This is a placeholder for future bulk user management
    }

    // Export users functionality (future enhancement)
    function exportUsers() {
        // Export user list to CSV
        console.log('Export users functionality placeholder');
    }

    // Initialize any additional features
    console.log('Admin users management loaded');
});