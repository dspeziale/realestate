// static/js/knowledge_base.js
// Gestione completa Knowledge Base e Categorie

// Variabili globali (vengono iniettate dal template)
// const kbFiles = ...;
// let categoriesData = ...;

// Inizializzazione modals Bootstrap
const createModal = new bootstrap.Modal(document.getElementById('createModal'));
const uploadModal = new bootstrap.Modal(document.getElementById('uploadModal'));
const viewModal = new bootstrap.Modal(document.getElementById('viewModal'));
const categoriesModal = new bootstrap.Modal(document.getElementById('categoriesModal'));

// ============================================
// GESTIONE CATEGORIE
// ============================================

/**
 * Renderizza la lista delle categorie nel modal di gestione
 */
function renderCategoriesList() {
    const container = document.getElementById('categoriesList');
    container.innerHTML = '';

    if (!categoriesData.categories || categoriesData.categories.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info">
                <i class="bi bi-info-circle"></i> Nessuna categoria presente.
                Clicca su "Aggiungi Categoria" per crearne una.
            </div>
        `;
        return;
    }

    categoriesData.categories.forEach((cat, index) => {
        const categoryCard = document.createElement('div');
        categoryCard.className = 'card mb-3 category-card';
        categoryCard.innerHTML = `
            <div class="card-body">
                <div class="row g-3 align-items-end">
                    <div class="col-md-2">
                        <label class="form-label small fw-bold mb-1">ID *</label>
                        <input type="text" class="form-control form-control-sm category-id"
                               value="${cat.id}" data-index="${index}" required>
                        <small class="text-muted" style="font-size: 0.7rem;">Univoco</small>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label small fw-bold mb-1">Nome *</label>
                        <input type="text" class="form-control form-control-sm category-name"
                               value="${cat.name}" data-index="${index}" required>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small fw-bold mb-1">Descrizione</label>
                        <input type="text" class="form-control form-control-sm category-description"
                               value="${cat.description || ''}" data-index="${index}">
                    </div>
                    <div class="col-md-2">
                        <label class="form-label small fw-bold mb-1">Colore Badge</label>
                        <select class="form-select form-select-sm category-color" data-index="${index}">
                            <option value="primary" ${cat.color === 'primary' ? 'selected' : ''}>🔵 Blu</option>
                            <option value="secondary" ${cat.color === 'secondary' ? 'selected' : ''}>⚪ Grigio</option>
                            <option value="success" ${cat.color === 'success' ? 'selected' : ''}>🟢 Verde</option>
                            <option value="danger" ${cat.color === 'danger' ? 'selected' : ''}>🔴 Rosso</option>
                            <option value="warning" ${cat.color === 'warning' ? 'selected' : ''}>🟡 Giallo</option>
                            <option value="info" ${cat.color === 'info' ? 'selected' : ''}>🔵 Ciano</option>
                            <option value="dark" ${cat.color === 'dark' ? 'selected' : ''}>⚫ Nero</option>
                        </select>
                    </div>
                    <div class="col-md-1 text-end">
                        <button class="btn btn-sm btn-outline-danger delete-category-btn w-100"
                                data-index="${index}" title="Elimina categoria">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="mt-2">
                    <span class="badge bg-${cat.color} badge-preview">Anteprima: ${cat.name}</span>
                </div>
            </div>
        `;
        container.appendChild(categoryCard);
    });

    // Aggiungi event listeners per i pulsanti elimina
    attachCategoryDeleteListeners();

    // Aggiungi event listeners per gli input
    attachCategoryInputListeners();
}

/**
 * Gestisce l'eliminazione di una categoria
 */
function attachCategoryDeleteListeners() {
    document.querySelectorAll('.delete-category-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const index = parseInt(this.dataset.index);
            const categoryName = categoriesData.categories[index].name;

            if (confirm(`Sei sicuro di voler eliminare la categoria "${categoryName}"?\n\nLe Knowledge Base con questa categoria manterranno il vecchio ID.`)) {
                categoriesData.categories.splice(index, 1);
                renderCategoriesList();
            }
        });
    });
}

/**
 * Gestisce l'aggiornamento in tempo reale delle categorie
 */
function attachCategoryInputListeners() {
    document.querySelectorAll('.category-id, .category-name, .category-description, .category-color').forEach(input => {
        input.addEventListener('input', function() {
            const index = parseInt(this.dataset.index);
            const cat = categoriesData.categories[index];

            if (this.classList.contains('category-id')) {
                cat.id = this.value;
            }
            if (this.classList.contains('category-name')) {
                cat.name = this.value;
                // Aggiorna anche il testo dell'anteprima
                const badge = this.closest('.card-body').querySelector('.badge-preview');
                if (badge) {
                    badge.textContent = `Anteprima: ${this.value}`;
                }
            }
            if (this.classList.contains('category-description')) {
                cat.description = this.value;
            }
            if (this.classList.contains('category-color')) {
                cat.color = this.value;
                // Aggiorna anteprima badge
                const badge = this.closest('.card-body').querySelector('.badge-preview');
                if (badge) {
                    badge.className = `badge bg-${this.value} badge-preview`;
                }
            }
        });
    });
}

/**
 * Aggiunge una nuova categoria
 */
function addNewCategory() {
    const newCategory = {
        id: 'categoria_' + Date.now(),
        name: 'Nuova Categoria',
        description: 'Descrizione della categoria',
        color: 'secondary'
    };

    categoriesData.categories.push(newCategory);
    renderCategoriesList();

    // Scroll verso il basso per vedere la nuova categoria
    setTimeout(() => {
        const container = document.getElementById('categoriesList');
        container.scrollTop = container.scrollHeight;
    }, 100);
}

/**
 * Valida i dati delle categorie prima del salvataggio
 */
function validateCategories() {
    // Controlla ID duplicati
    const ids = categoriesData.categories.map(c => c.id);
    const duplicates = ids.filter((item, index) => ids.indexOf(item) !== index);

    if (duplicates.length > 0) {
        alert('❌ Errore: ID duplicati trovati: ' + duplicates.join(', ') + '\n\nOgni categoria deve avere un ID univoco.');
        return false;
    }

    // Controlla campi obbligatori
    const invalid = categoriesData.categories.filter(c => !c.id || !c.id.trim() || !c.name || !c.name.trim());
    if (invalid.length > 0) {
        alert('❌ Errore: Tutte le categorie devono avere un ID e un Nome validi.');
        return false;
    }

    return true;
}

/**
 * Salva le categorie sul server
 */
async function saveCategories() {
    if (!validateCategories()) {
        return;
    }

    const btn = document.getElementById('saveCategoriesBtn');
    const originalHTML = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Salvataggio...';

        const response = await fetch('/categories/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(categoriesData)
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ Categorie salvate con successo!\n\nLa pagina verrà ricaricata per applicare le modifiche.');
            categoriesModal.hide();
            location.reload();
        } else {
            alert('❌ Errore nel salvataggio: ' + result.error);
        }
    } catch (error) {
        alert('❌ Errore di connessione: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

/**
 * Ripristina le categorie ai valori di default
 */
async function resetCategories() {
    if (!confirm('⚠️ Sei sicuro di voler ripristinare le categorie di default?\n\nQuesta azione sovrascriverà tutte le categorie personalizzate!\n\nLe Knowledge Base esistenti NON saranno modificate.')) {
        return;
    }

    try {
        const response = await fetch('/categories/reset', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ Categorie ripristinate ai valori di default!\n\nLa pagina verrà ricaricata.');
            location.reload();
        } else {
            alert('❌ Errore: ' + result.error);
        }
    } catch (error) {
        alert('❌ Errore di connessione: ' + error.message);
    }
}

// ============================================
// GESTIONE KNOWLEDGE BASE
// ============================================

/**
 * Filtra le KB per categoria
 */
function setupCategoryFilter() {
    const categoryFilter = document.getElementById('categoryFilter');
    if (!categoryFilter) return;

    categoryFilter.addEventListener('change', function() {
        const category = this.value;
        const items = document.querySelectorAll('.kb-item');
        let visibleCount = 0;

        items.forEach(item => {
            if (!category || item.dataset.category === category) {
                item.style.display = 'block';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });

        // Mostra/nascondi messaggio "nessun risultato"
        updateNoResultMessage(visibleCount, items.length);
    });
}

/**
 * Mostra messaggio quando non ci sono risultati dal filtro
 */
function updateNoResultMessage(visibleCount, totalCount) {
    const grid = document.getElementById('kbGrid');
    let noResultMsg = document.getElementById('noResultMsg');

    if (visibleCount === 0 && totalCount > 0) {
        if (!noResultMsg) {
            noResultMsg = document.createElement('div');
            noResultMsg.id = 'noResultMsg';
            noResultMsg.className = 'col-12 text-center text-muted py-5';
            noResultMsg.innerHTML = `
                <i class="bi bi-inbox display-4"></i>
                <p class="mt-3 mb-0">Nessuna Knowledge Base trovata per questa categoria</p>
            `;
            grid.appendChild(noResultMsg);
        }
    } else if (noResultMsg) {
        noResultMsg.remove();
    }
}

/**
 * Visualizza i dettagli di una KB
 */
function setupViewButtons() {
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const id = this.dataset.id;
            const kb = kbFiles.find(k => k.id === id);

            if (kb) {
                document.getElementById('viewName').textContent = kb.name;

                // Trova il nome della categoria
                const category = categoriesData.categories.find(c => c.id === kb.category);
                document.getElementById('viewCategory').textContent = category ? category.name : kb.category;

                document.getElementById('viewDescription').textContent = kb.description || 'Nessuna descrizione';
                document.getElementById('viewContent').textContent = kb.content;
                document.getElementById('viewCreated').textContent = kb.created_at;
                document.getElementById('viewUpdated').textContent = kb.updated_at;

                viewModal.show();
            }
        });
    });
}

/**
 * Apre il modal di modifica KB
 */
function setupEditButtons() {
    document.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const id = this.dataset.id;

            try {
                const response = await fetch(`/knowledge-base/get/${id}`);
                const result = await response.json();

                if (result.success) {
                    const kb = result.data;

                    document.getElementById('modalTitle').innerHTML = '<i class="bi bi-pencil"></i> Modifica Knowledge Base';
                    document.getElementById('kbId').value = kb.id;
                    document.getElementById('kbName').value = kb.name;
                    document.getElementById('kbCategory').value = kb.category;
                    document.getElementById('kbDescription').value = kb.description || '';
                    document.getElementById('kbContent').value = kb.content;

                    createModal.show();
                } else {
                    alert('❌ Errore nel caricamento: ' + result.error);
                }
            } catch (error) {
                alert('❌ Errore di connessione: ' + error.message);
            }
        });
    });
}

/**
 * Elimina una KB
 */
function setupDeleteButtons() {
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const id = this.dataset.id;
            const kb = kbFiles.find(k => k.id === id);
            const kbName = kb ? kb.name : 'questa knowledge base';

            if (!confirm(`Sei sicuro di voler eliminare "${kbName}"?\n\nQuesta azione non può essere annullata.`)) {
                return;
            }

            try {
                const response = await fetch(`/knowledge-base/delete/${id}`, {
                    method: 'DELETE'
                });

                const result = await response.json();

                if (result.success) {
                    // Rimuovi l'elemento dalla pagina con animazione
                    const kbCard = this.closest('.kb-item');
                    kbCard.style.opacity = '0';
                    kbCard.style.transform = 'scale(0.9)';

                    setTimeout(() => {
                        location.reload();
                    }, 300);
                } else {
                    alert('❌ Errore: ' + result.error);
                }
            } catch (error) {
                alert('❌ Errore di connessione: ' + error.message);
            }
        });
    });
}

/**
 * Salva una KB (nuova o modificata)
 */
async function saveKnowledgeBase() {
    const id = document.getElementById('kbId').value;
    const name = document.getElementById('kbName').value.trim();
    const category = document.getElementById('kbCategory').value;
    const description = document.getElementById('kbDescription').value.trim();
    const content = document.getElementById('kbContent').value.trim();

    if (!name || !content) {
        alert('❌ Nome e contenuto sono obbligatori');
        return;
    }

    const data = { name, category, description, content };
    const btn = document.getElementById('saveKbBtn');
    const originalHTML = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Salvataggio...';

        const url = id ? `/knowledge-base/update/${id}` : '/knowledge-base/create';
        const method = id ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (result.success) {
            createModal.hide();
            location.reload();
        } else {
            alert('❌ Errore: ' + result.error);
        }
    } catch (error) {
        alert('❌ Errore di connessione: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

/**
 * Upload di un file come KB
 */
async function uploadKnowledgeFile() {
    const fileInput = document.getElementById('uploadFile');
    const name = document.getElementById('uploadName').value.trim();
    const category = document.getElementById('uploadCategory').value;
    const description = document.getElementById('uploadDescription').value.trim();

    if (!fileInput.files.length) {
        alert('❌ Seleziona un file');
        return;
    }

    const file = fileInput.files[0];

    // Verifica dimensione file (max 1MB per file di testo)
    if (file.size > 1024 * 1024) {
        alert('❌ Il file è troppo grande. Dimensione massima: 1MB');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', name);
    formData.append('category', category);
    formData.append('description', description);

    const btn = document.getElementById('uploadKbBtn');
    const originalHTML = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Caricamento...';

        const response = await fetch('/knowledge-base/upload-file', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            uploadModal.hide();
            location.reload();
        } else {
            alert('❌ Errore: ' + result.error);
        }
    } catch (error) {
        alert('❌ Errore di connessione: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

/**
 * Reset form quando si apre il modal di creazione
 */
function setupCreateModalReset() {
    const createNewBtn = document.querySelector('[data-bs-target="#createModal"]');
    if (createNewBtn) {
        createNewBtn.addEventListener('click', function() {
            document.getElementById('modalTitle').innerHTML = '<i class="bi bi-plus-circle"></i> Nuova Knowledge Base';
            document.getElementById('kbForm').reset();
            document.getElementById('kbId').value = '';
        });
    }
}

/**
 * Reset form upload
 */
function setupUploadModalReset() {
    const uploadBtn = document.querySelector('[data-bs-target="#uploadModal"]');
    if (uploadBtn) {
        uploadBtn.addEventListener('click', function() {
            document.getElementById('uploadForm').reset();
        });
    }
}

// ============================================
// INIZIALIZZAZIONE
// ============================================

document.addEventListener('DOMContentLoaded', function() {
    // Setup gestione categorie
    document.getElementById('addCategoryBtn')?.addEventListener('click', addNewCategory);
    document.getElementById('saveCategoriesBtn')?.addEventListener('click', saveCategories);
    document.getElementById('resetCategoriesBtn')?.addEventListener('click', resetCategories);

    // Render categorie quando si apre il modal
    document.querySelector('[data-bs-target="#categoriesModal"]')?.addEventListener('click', renderCategoriesList);

    // Setup gestione KB
    setupCategoryFilter();
    setupViewButtons();
    setupEditButtons();
    setupDeleteButtons();
    setupCreateModalReset();
    setupUploadModalReset();

    // Event listeners per salvataggio KB
    document.getElementById('saveKbBtn')?.addEventListener('click', saveKnowledgeBase);
    document.getElementById('uploadKbBtn')?.addEventListener('click', uploadKnowledgeFile);

    console.log('✅ Knowledge Base Manager inizializzato');
});