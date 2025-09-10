// Filename: static/js/email-templates.js
// Copyright 2025 SILICONDEV SPA
// Description: JavaScript for email templates management

document.addEventListener('DOMContentLoaded', function() {
    // Initialize template cards with hover effects
    initializeTemplateCards();

    // Load template content previews
    loadTemplatePreviews();
});

function initializeTemplateCards() {
    const cards = document.querySelectorAll('.template-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
            this.style.boxShadow = '0 8px 25px rgba(0,0,0,0.15)';
            this.style.transition = 'all 0.3s ease';
        });

        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '';
        });
    });
}

function loadTemplatePreviews() {
    // Load actual template content previews (simplified)
    const previewElements = document.querySelectorAll('.template-preview');
    previewElements.forEach((element, index) => {
        // Simulate loading template preview
        setTimeout(() => {
            element.innerHTML = `
                <div class="small">
                    <strong>Subject:</strong> Template Email #${index + 1}<br>
                    <strong>Content:</strong> Lorem ipsum dolor sit amet, consectetur adipiscing elit...
                </div>
            `;
        }, 200 * index);
    });
}

function previewTemplate(templateName) {
    const previewModal = new bootstrap.Modal(document.getElementById('previewModal'));
    const previewContent = document.getElementById('previewContent');

    // Show loading
    previewContent.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-2">Caricamento anteprima...</p>
        </div>
    `;

    previewModal.show();

    // Simulate loading template content
    setTimeout(() => {
        previewContent.innerHTML = getTemplatePreview(templateName);
    }, 1000);
}

function getTemplatePreview(templateName) {
    // Mock template previews
    const previews = {
        'welcome.html': `
            <div class="email-preview">
                <div class="border-bottom pb-2 mb-3">
                    <strong>Da:</strong> Sistema Aste Immobiliari<br>
                    <strong>Oggetto:</strong> Benvenuto nel sistema!
                </div>
                <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2 style="color: #007bff;">Benvenuto {{ user_name }}!</h2>
                    <p>Grazie per esserti registrato al nostro sistema di gestione aste immobiliari.</p>
                    <p>Il tuo account è stato creato con successo con i seguenti dettagli:</p>
                    <ul>
                        <li><strong>Email:</strong> {{ user_email }}</li>
                        <li><strong>Data registrazione:</strong> {{ registration_date }}</li>
                    </ul>
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{{ login_url }}" style="background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Accedi al Sistema
                        </a>
                    </div>
                    <hr>
                    <p style="font-size: 12px; color: #666;">
                        &copy; 2025 Sistema Aste Immobiliari - Tutti i diritti riservati
                    </p>
                </div>
            </div>
        `,
        'auction_notification.html': `
            <div class="email-preview">
                <div class="border-bottom pb-2 mb-3">
                    <strong>Da:</strong> Sistema Aste Immobiliari<br>
                    <strong>Oggetto:</strong> Notifica Asta - {{ property_address }}
                </div>
                <div style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2 style="color: #28a745;">🔔 Notifica Asta</h2>
                    <p>Ciao {{ user_name }},</p>
                    <div style="background: #fff3cd; padding: 15px; border-radius: 5px; margin: 15px 0;">
                        <h3>⏰ L'asta sta per terminare!</h3>
                        <p>Rimangono pochi minuti per fare la tua offerta.</p>
                    </div>
                    <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #28a745; margin: 15px 0;">
                        <h4>Dettagli Proprietà</h4>
                        <ul>
                            <li><strong>Indirizzo:</strong> {{ property_address }}</li>
                            <li><strong>Tipo:</strong> {{ property_type }}</li>
                            <li><strong>Superficie:</strong> {{ property_size }} mq</li>
                            <li><strong>Offerta attuale:</strong> €{{ current_bid }}</li>
                        </ul>
                    </div>
                    <div style="text-align: center; margin: 20px 0;">
                        <a href="{{ auction_url }}" style="background: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                            Visualizza Asta
                        </a>
                    </div>
                </div>
            </div>
        `
    };

    return previews[templateName] || `
        <div class="text-center py-5">
            <i class="bi bi-file-earmark-text display-1 text-muted"></i>
            <h4 class="mt-3">Anteprima Non Disponibile</h4>
            <p class="text-muted">Template: ${templateName}</p>
        </div>
    `;
}

function sendTemplateEmail(templateName) {
    const modal = new bootstrap.Modal(document.getElementById('sendTemplateModal'));
    document.getElementById('selectedTemplate').value = templateName;

    // Set default subject based on template
    const subjects = {
        'welcome.html': 'Benvenuto nel sistema!',
        'auction_notification.html': 'Notifica Asta',
        'reset_password.html': 'Reset Password',
        'newsletter.html': 'Newsletter Mensile'
    };

    document.getElementById('templateSubjectSend').value = subjects[templateName] || 'Email dal template';

    // Load template variables
    loadTemplateVariables(templateName);

    modal.show();
}

function loadTemplateVariables(templateName) {
    const variablesContainer = document.getElementById('templateVariables');

    // Mock variables based on template
    const templateVars = {
        'welcome.html': [
            { name: 'user_name', label: 'Nome Utente', value: '', placeholder: 'Mario Rossi' },
            { name: 'user_email', label: 'Email Utente', value: '', placeholder: 'mario@example.com' },
            { name: 'registration_date', label: 'Data Registrazione', value: '', placeholder: '2025-01-15' },
            { name: 'login_url', label: 'URL Login', value: window.location.origin + '/auth/login', placeholder: 'https://...' }
        ],
        'auction_notification.html': [
            { name: 'user_name', label: 'Nome Utente', value: '', placeholder: 'Mario Rossi' },
            { name: 'property_address', label: 'Indirizzo Proprietà', value: '', placeholder: 'Via Roma 123, Milano' },
            { name: 'property_type', label: 'Tipo Proprietà', value: '', placeholder: 'Appartamento' },
            { name: 'property_size', label: 'Superficie', value: '', placeholder: '85' },
            { name: 'current_bid', label: 'Offerta Attuale', value: '', placeholder: '250,000' },
            { name: 'auction_url', label: 'URL Asta', value: '', placeholder: 'https://...' }
        ]
    };

    const variables = templateVars[templateName] || [];

    if (variables.length === 0) {
        variablesContainer.innerHTML = `
            <p class="text-muted mb-0">
                <i class="bi bi-info-circle me-1"></i>
                Nessuna variabile specifica per questo template
            </p>
        `;
        return;
    }

    let html = '<div class="row">';
    variables.forEach((variable, index) => {
        html += `
            <div class="col-md-6 mb-2">
                <label class="form-label small">${variable.label}</label>
                <input type="text" class="form-control form-control-sm"
                       name="var_${variable.name}"
                       value="${variable.value}"
                       placeholder="${variable.placeholder}">
            </div>
        `;
    });
    html += '</div>';

    variablesContainer.innerHTML = html;
}

function sendTemplateEmailNow() {
    const form = document.getElementById('sendTemplateForm');
    const formData = new FormData(form);

    // Get template variables
    const variables = {};
    const varInputs = document.querySelectorAll('[name^="var_"]');
    varInputs.forEach(input => {
        const varName = input.name.replace('var_', '');
        variables[varName] = input.value;
    });

    // Prepare data
    const data = {
        template: document.getElementById('selectedTemplate').value,
        to_emails: document.getElementById('templateToEmails').value.split(',').map(e => e.trim()),
        subject: document.getElementById('templateSubjectSend').value,
        context: variables
    };

    // Show loading
    const sendBtn = event.target;
    const originalText = sendBtn.innerHTML;
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i> Invio...';

    // Send email
    fetch('/email/send-template', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            showAlert('Email inviata con successo!', 'success');
            bootstrap.Modal.getInstance(document.getElementById('sendTemplateModal')).hide();
        } else {
            showAlert('Errore durante l\'invio: ' + result.message, 'danger');
        }
    })
    .catch(error => {
        showAlert('Errore di connessione: ' + error.message, 'danger');
    })
    .finally(() => {
        sendBtn.disabled = false;
        sendBtn.innerHTML = originalText;
    });
}

function deleteTemplate(templateName) {
    if (confirm(`Sei sicuro di voler eliminare il template "${templateName}"?`)) {
        showAlert('Funzionalità di eliminazione non ancora implementata', 'info');
    }
}

function createPredefinedTemplate(type) {
    const templates = {
        welcome: {
            name: 'welcome',
            subject: 'Benvenuto nel sistema!',
            content: `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Benvenuto</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #007bff; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f8f9fa; }
        .footer { padding: 20px; text-align: center; font-size: 12px; color: #666; }
        .button { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Benvenuto {{ user_name }}!</h1>
        </div>
        <div class="content">
            <p>Grazie per esserti registrato al nostro sistema di gestione aste immobiliari.</p>
            <p>Il tuo account è stato creato con successo.</p>
            <p style="text-align: center;">
                <a href="{{ login_url }}" class="button">Accedi al Sistema</a>
            </p>
        </div>
        <div class="footer">
            <p>&copy; {{ current_year }} Sistema Aste Immobiliari</p>
        </div>
    </div>
</body>
</html>`
        },
        auction: {
            name: 'auction_notification',
            subject: 'Notifica Asta',
            content: `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Notifica Asta</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #28a745; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f8f9fa; }
        .highlight { background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }
        .property-details { background: white; padding: 15px; border-left: 4px solid #28a745; }
        .button { display: inline-block; padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Notifica Asta</h1>
        </div>
        <div class="content">
            <p>Ciao {{ user_name }},</p>
            <div class="highlight">
                <h3>⏰ L'asta sta per terminare!</h3>
                <p>Rimangono pochi minuti per fare la tua offerta.</p>
            </div>
            <div class="property-details">
                <h4>Dettagli Proprietà</h4>
                <ul>
                    <li><strong>Indirizzo:</strong> {{ property_address }}</li>
                    <li><strong>Tipo:</strong> {{ property_type }}</li>
                    <li><strong>Offerta attuale:</strong> €{{ current_bid }}</li>
                </ul>
            </div>
            <p style="text-align: center;">
                <a href="{{ auction_url }}" class="button">Visualizza Asta</a>
            </p>
        </div>
    </div>
</body>
</html>`
        },
        reset: {
            name: 'reset_password',
            subject: 'Reset Password',
            content: `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Reset Password</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #dc3545; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f8f9fa; }
        .button { display: inline-block; padding: 10px 20px; background: #dc3545; color: white; text-decoration: none; border-radius: 5px; }
        .warning { background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Reset Password</h1>
        </div>
        <div class="content">
            <p>Ciao {{ user_name }},</p>
            <p>Hai richiesto di reimpostare la password per il tuo account.</p>
            <div class="warning">
                <p><strong>Importante:</strong> Se non hai richiesto questa operazione, ignora questa email.</p>
            </div>
            <p>Clicca sul pulsante qui sotto per reimpostare la password:</p>
            <p style="text-align: center;">
                <a href="{{ reset_url }}" class="button">Reimposta Password</a>
            </p>
            <p>Questo link scadrà tra 24 ore.</p>
        </div>
    </div>
</body>
</html>`
        },
        newsletter: {
            name: 'newsletter',
            subject: 'Newsletter Mensile',
            content: `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Newsletter</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #6f42c1; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f8f9fa; }
        .article { background: white; padding: 15px; margin: 10px 0; border-radius: 5px; }
        .button { display: inline-block; padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Newsletter {{ month_year }}</h1>
        </div>
        <div class="content">
            <p>Ciao {{ user_name }},</p>
            <p>Ecco le ultime novità dal mondo delle aste immobiliari:</p>

            <div class="article">
                <h3>{{ article_title }}</h3>
                <p>{{ article_content }}</p>
            </div>

            <p style="text-align: center;">
                <a href="{{ website_url }}" class="button">Visita il Sito</a>
            </p>
        </div>
    </div>
</body>
</html>`
        }
    };

    const template = templates[type];
    if (template) {
        // Fill the create template modal
        document.getElementById('templateName').value = template.name;
        document.getElementById('templateSubject').value = template.subject;
        document.getElementById('templateContent').value = template.content;

        // Show the modal
        const modal = new bootstrap.Modal(document.getElementById('createTemplateModal'));
        modal.show();
    }
}

function saveTemplate() {
    const name = document.getElementById('templateName').value.trim();
    const subject = document.getElementById('templateSubject').value.trim();
    const content = document.getElementById('templateContent').value.trim();

    if (!name) {
        showAlert('Nome template richiesto', 'warning');
        return;
    }

    if (!content) {
        showAlert('Contenuto template richiesto', 'warning');
        return;
    }

    // For now, just show success message (would need backend implementation)
    showAlert(`Template "${name}" creato con successo! (Funzionalità backend da implementare)`, 'success');

    // Close modal
    bootstrap.Modal.getInstance(document.getElementById('createTemplateModal')).hide();

    // Reset form
    document.getElementById('createTemplateForm').reset();
}

function showAlert(message, type = 'info') {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show position-fixed"
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', alertHtml);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert');
        if (alerts.length > 0) {
            alerts[alerts.length - 1].remove();
        }
    }, 5000);
}