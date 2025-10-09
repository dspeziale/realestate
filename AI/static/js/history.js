const viewModal = new bootstrap.Modal(document.getElementById('viewModal'));

document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', function(e) {
        e.stopPropagation();
        const id = this.dataset.id;
        const conv = conversations.find(c => c.id === id);

        if (conv) {
            document.getElementById('modalPrompt').textContent = conv.prompt;
            document.getElementById('modalResponse').textContent = conv.response;
            document.getElementById('modalTimestamp').innerHTML =
                '<i class="bi bi-calendar3"></i> ' + conv.timestamp;

            const filesDiv = document.getElementById('modalFiles');
            if (conv.files && conv.files.length > 0) {
                filesDiv.innerHTML = '<label class="form-label fw-bold">File allegati:</label><ul class="list-unstyled">';
                conv.files.forEach(file => {
                    filesDiv.innerHTML += '<li><i class="bi bi-paperclip"></i> ' + file + '</li>';
                });
                filesDiv.innerHTML += '</ul>';
            } else {
                filesDiv.innerHTML = '';
            }

            viewModal.show();
        }
    });
});

document.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', async function(e) {
        e.stopPropagation();

        if (!confirm('Sei sicuro di voler eliminare questa conversazione?')) {
            return;
        }

        const id = this.dataset.id;

        try {
            const response = await fetch('/history/delete/' + id, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                location.reload();
            } else {
                alert('Errore durante l\'eliminazione: ' + data.error);
            }
        } catch (error) {
            alert('Errore di connessione: ' + error.message);
        }
    });
});