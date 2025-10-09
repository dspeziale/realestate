const temperatureInput = document.getElementById('temperature');
const temperatureValue = document.getElementById('temperatureValue');

// Aggiorna il valore visualizzato quando cambia lo slider
temperatureInput.addEventListener('input', function() {
    temperatureValue.textContent = this.value;
});

// Toggle visibilità API Key
document.getElementById('toggleApiKey').addEventListener('click', function() {
    const apiKeyInput = document.getElementById('apiKey');
    const icon = this.querySelector('i');

    if (apiKeyInput.type === 'password') {
        apiKeyInput.type = 'text';
        icon.className = 'bi bi-eye-slash';
    } else {
        apiKeyInput.type = 'password';
        icon.className = 'bi bi-eye';
    }
});

// Salva impostazioni
document.getElementById('settingsForm').addEventListener('submit', async function(e) {
    e.preventDefault();

    const formData = new FormData(this);
    const settings = {
        api_key: formData.get('api_key'),
        model: formData.get('model'),
        temperature: parseFloat(formData.get('temperature')),
        save_history: formData.get('save_history') === 'on',
        dark_mode: formData.get('dark_mode') === 'on'
    };

    try {
        const response = await fetch('/settings/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });

        const data = await response.json();

        if (data.success) {
            // Mostra messaggio di successo
            const alert = document.createElement('div');
            alert.className = 'alert alert-success alert-dismissible fade show';
            alert.innerHTML = `
                <i class="bi bi-check-circle"></i> Impostazioni salvate con successo!
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;

            // Inserisci l'alert all'inizio del container
            const container = document.querySelector('.container-fluid.p-4');
            const firstChild = container.firstChild;
            container.insertBefore(alert, firstChild);

            // Rimuovi alert dopo 3 secondi
            setTimeout(() => {
                alert.remove();
            }, 3000);
        } else {
            alert('Errore: ' + data.error);
        }
    } catch (error) {
        alert('Errore di connessione: ' + error.message);
    }
});

// Ripristina impostazioni predefinite
document.getElementById('resetSettings').addEventListener('click', async function() {
    if (!confirm('Sei sicuro di voler ripristinare le impostazioni predefinite?')) {
        return;
    }

    try {
        const response = await fetch('/settings/reset', {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            // Mostra messaggio di successo prima di ricaricare
            const alert = document.createElement('div');
            alert.className = 'alert alert-success';
            alert.innerHTML = '<i class="bi bi-check-circle"></i> Impostazioni ripristinate! Ricaricamento in corso...';

            const container = document.querySelector('.container-fluid.p-4');
            const firstChild = container.firstChild;
            container.insertBefore(alert, firstChild);

            // Ricarica dopo 1 secondo
            setTimeout(() => {
                location.reload();
            }, 1000);
        } else {
            alert('Errore: ' + data.error);
        }
    } catch (error) {
        alert('Errore di connessione: ' + error.message);
    }
});