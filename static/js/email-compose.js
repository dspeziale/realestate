// Filename: static/js/email-compose.js
// Copyright 2025 SILICONDEV SPA
// Description: JavaScript for email compose functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize TinyMCE for HTML editor
    initializeTinyMCE();

    // Initialize form validation and handlers
    initializeFormHandlers();

    // Initialize preview functionality
    initializePreview();

    // Initialize file upload preview
    initializeFileUpload();
});

function initializeTinyMCE() {
    tinymce.init({
        selector: '#html_body',
        height: 400,
        plugins: [
            'advlist', 'autolink', 'lists', 'link', 'image', 'charmap', 'preview',
            'anchor', 'searchreplace', 'visualblocks', 'code', 'fullscreen',
            'insertdatetime', 'media', 'table', 'help', 'wordcount'
        ],
        toolbar: 'undo redo | blocks | bold italic forecolor backcolor | ' +
                'alignleft aligncenter alignright alignjustify | ' +
                'bullist numlist outdent indent | removeformat | help',
        content_style: 'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; font-size: 14px }',
        branding: false,
        menubar: false,
        statusbar: false
    });
}

function initializeFormHandlers() {
    const form = document.getElementById('emailForm');
    const sendBtn = document.getElementById('sendBtn');

    // Form submission handler
    form.addEventListener('submit', function(e) {
        // Update TinyMCE content
        tinymce.triggerSave();

        // Show loading state
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Invio in corso...';

        // Validate form
        if (!validateForm()) {
            e.preventDefault();
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="bi bi-send me-1"></i> Invia Email';
        }
    });

    // Email validation
    const emailInputs = ['to_emails', 'cc_emails', 'bcc_emails'];
    emailInputs.forEach(inputId => {
        const input = document.getElementById(inputId);
        if (input) {
            input.addEventListener('blur', function() {
                validateEmailList(this);
            });
        }
    });

    // Auto-save draft functionality
    let autoSaveTimer;
    const formInputs = form.querySelectorAll('input, textarea');
    formInputs.forEach(input => {
        input.addEventListener('input', function() {
            clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(saveDraft, 2000);
        });
    });
}

function validateForm() {
    let isValid = true;

    // Check required fields
    const toEmails = document.getElementById('to_emails').value.trim();
    const subject = document.getElementById('subject').value.trim();
    const body = document.getElementById('body').value.trim();
    const htmlBody = tinymce.get('html_body').getContent();

    if (!toEmails) {
        showValidationError('to_emails', 'Destinatario richiesto');
        isValid = false;
    }

    if (!subject) {
        showValidationError('subject', 'Oggetto richiesto');
        isValid = false;
    }

    if (!body && !htmlBody) {
        showAlert('Inserire almeno un contenuto (testo o HTML)', 'warning');
        isValid = false;
    }

    // Validate email format
    if (toEmails && !validateEmailList(document.getElementById('to_emails'))) {
        isValid = false;
    }

    return isValid;
}

function validateEmailList(input) {
    const emails = input.value.split(',').map(email => email.trim()).filter(email => email);
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    let isValid = true;
    for (const email of emails) {
        if (!emailRegex.test(email)) {
            showValidationError(input.id, `Email non valida: ${email}`);
            isValid = false;
            break;
        }
    }

    if (isValid) {
        clearValidationError(input.id);
    }

    return isValid;
}

function showValidationError(fieldId, message) {
    const field = document.getElementById(fieldId);
    field.classList.add('is-invalid');

    // Remove existing feedback
    const existingFeedback = field.parentNode.querySelector('.invalid-feedback');
    if (existingFeedback) {
        existingFeedback.remove();
    }

    // Add new feedback
    const feedback = document.createElement('div');
    feedback.className = 'invalid-feedback';
    feedback.textContent = message;
    field.parentNode.appendChild(feedback);
}

function clearValidationError(fieldId) {
    const field = document.getElementById(fieldId);
    field.classList.remove('is-invalid');

    const feedback = field.parentNode.querySelector('.invalid-feedback');
    if (feedback) {
        feedback.remove();
    }
}

function initializePreview() {
    const previewBtn = document.getElementById('previewBtn');
    const previewSection = document.getElementById('previewSection');
    const previewContent = document.getElementById('previewContent');

    previewBtn.addEventListener('click', function() {
        // Update TinyMCE content
        tinymce.triggerSave();

        // Get form data
        const formData = {
            to_emails: document.getElementById('to_emails').value,
            cc_emails: document.getElementById('cc_emails').value,
            bcc_emails: document.getElementById('bcc_emails').value,
            from_name: document.getElementById('from_name').value,
            subject: document.getElementById('subject').value,
            body: document.getElementById('body').value,
            html_body: document.getElementById('html_body').value
        };

        // Generate preview
        const preview = generateEmailPreview(formData);
        previewContent.innerHTML = preview;

        // Show preview section
        previewSection.style.display = 'block';
        previewSection.scrollIntoView({ behavior: 'smooth' });
    });
}

function generateEmailPreview(data) {
    return `
        <div class="email-preview">
            <div class="email-header mb-3">
                <div><strong>Da:</strong> ${data.from_name || 'Sistema'}</div>
                <div><strong>A:</strong> ${data.to_emails}</div>
                ${data.cc_emails ? `<div><strong>CC:</strong> ${data.cc_emails}</div>` : ''}
                ${data.bcc_emails ? `<div><strong>BCC:</strong> ${data.bcc_emails}</div>` : ''}
                <div><strong>Oggetto:</strong> ${data.subject}</div>
            </div>
            <hr>
            <div class="email-content">
                ${data.html_body || data.body.replace(/\n/g, '<br>')}
            </div>
        </div>
    `;
}

function initializeFileUpload() {
    const fileInput = document.getElementById('attachments');
    const maxSize = 25 * 1024 * 1024; // 25MB max per attachment

    fileInput.addEventListener('change', function() {
        const files = Array.from(this.files);
        let totalSize = 0;
        let hasError = false;

        files.forEach(file => {
            totalSize += file.size;
            if (file.size > maxSize) {
                showAlert(`Il file "${file.name}" supera i 25MB`, 'warning');
                hasError = true;
            }
        });

        if (totalSize > 50 * 1024 * 1024) { // 50MB total max
            showAlert('La dimensione totale degli allegati non può superare i 50MB', 'warning');
            hasError = true;
        }

        if (hasError) {
            this.value = '';
        } else {
            displayFileList(files);
        }
    });
}

function displayFileList(files) {
    // Remove existing file list
    const existingList = document.querySelector('.file-list');
    if (existingList) {
        existingList.remove();
    }

    if (files.length === 0) return;

    // Create new file list
    const fileList = document.createElement('div');
    fileList.className = 'file-list mt-2';
    fileList.innerHTML = '<small class="text-muted">File selezionati:</small>';

    files.forEach(file => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item d-flex justify-content-between align-items-center bg-light p-2 mt-1 rounded';
        fileItem.innerHTML = `
            <span>
                <i class="bi bi-file-earmark me-1"></i>
                ${file.name} (${formatFileSize(file.size)})
            </span>
        `;
        fileList.appendChild(fileItem);
    });

    const attachmentsInput = document.getElementById('attachments');
    attachmentsInput.parentNode.appendChild(fileList);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function saveDraft() {
    // Auto-save draft functionality (localStorage or server)
    const formData = {
        to_emails: document.getElementById('to_emails').value,
        cc_emails: document.getElementById('cc_emails').value,
        bcc_emails: document.getElementById('bcc_emails').value,
        from_name: document.getElementById('from_name').value,
        subject: document.getElementById('subject').value,
        body: document.getElementById('body').value,
        html_body: tinymce.get('html_body') ? tinymce.get('html_body').getContent() : '',
        timestamp: new Date().toISOString()
    };

    // Save to localStorage
    try {
        localStorage.setItem('email_draft', JSON.stringify(formData));
        console.log('Draft saved');
    } catch (e) {
        console.warn('Could not save draft to localStorage');
    }
}

function loadDraft() {
    try {
        const draft = JSON.parse(localStorage.getItem('email_draft'));
        if (draft && draft.timestamp) {
            const timeDiff = new Date() - new Date(draft.timestamp);
            if (timeDiff < 24 * 60 * 60 * 1000) { // 24 hours
                if (confirm('È stata trovata una bozza salvata. Vuoi ripristinarla?')) {
                    // Load draft data into form
                    Object.keys(draft).forEach(key => {
                        if (key !== 'timestamp' && key !== 'html_body') {
                            const element = document.getElementById(key);
                            if (element) {
                                element.value = draft[key];
                            }
                        }
                    });

                    // Load HTML content into TinyMCE when ready
                    setTimeout(() => {
                        if (tinymce.get('html_body')) {
                            tinymce.get('html_body').setContent(draft.html_body || '');
                        }
                    }, 1000);
                }
            }
        }
    } catch (e) {
        console.warn('Could not load draft from localStorage');
    }
}

function showAlert(message, type = 'info') {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    const container = document.querySelector('.container-fluid');
    container.insertAdjacentHTML('afterbegin', alertHtml);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alert = container.querySelector('.alert');
        if (alert) {
            alert.remove();
        }
    }, 5000);
}

// Load draft on page load
window.addEventListener('load', loadDraft);

// Clear draft on successful send
window.addEventListener('beforeunload', function(e) {
    // Only clear if form is empty
    const hasContent = document.getElementById('to_emails').value ||
                      document.getElementById('subject').value ||
                      document.getElementById('body').value;

    if (!hasContent) {
        localStorage.removeItem('email_draft');
    }
});