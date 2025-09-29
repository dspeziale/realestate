// static/js/edit-profile.js - Edit Profile JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('edit-profile-form');
    const firstNameInput = document.getElementById('first_name');
    const lastNameInput = document.getElementById('last_name');
    const emailInput = document.getElementById('email');
    const usernameInput = document.getElementById('username');
    const saveBtn = document.getElementById('save-btn');
    const previewSection = document.getElementById('preview-section');
    const previewName = document.getElementById('preview-name');
    const previewEmail = document.getElementById('preview-email');
    const previewInitials = document.getElementById('preview-initials');

    // Store original values from form inputs
    const originalValues = {
        first_name: firstNameInput.value,
        last_name: lastNameInput.value,
        email: emailInput.value
    };

    // Track changes
    function checkForChanges() {
        const hasChanges =
            firstNameInput.value !== originalValues.first_name ||
            lastNameInput.value !== originalValues.last_name ||
            emailInput.value !== originalValues.email;

        // Update save button
        if (hasChanges) {
            saveBtn.classList.remove('btn-success');
            saveBtn.classList.add('btn-warning');
            saveBtn.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Salva Modifiche';
            showPreview();
        } else {
            saveBtn.classList.remove('btn-warning');
            saveBtn.classList.add('btn-success');
            saveBtn.innerHTML = '<i class="bi bi-check-circle"></i> Salva Modifiche';
            hidePreview();
        }

        // Highlight changed fields
        highlightChangedFields();
    }

    function highlightChangedFields() {
        const fields = [
            { input: firstNameInput, original: originalValues.first_name },
            { input: lastNameInput, original: originalValues.last_name },
            { input: emailInput, original: originalValues.email }
        ];

        fields.forEach(field => {
            if (field.input.value !== field.original) {
                field.input.classList.add('has-changes');
            } else {
                field.input.classList.remove('has-changes');
            }
        });
    }

    function showPreview() {
        updatePreview();
        previewSection.style.display = 'block';
    }

    function hidePreview() {
        previewSection.style.display = 'none';
    }

    function updatePreview() {
        const firstName = firstNameInput.value.trim();
        const lastName = lastNameInput.value.trim();
        const email = emailInput.value.trim();

        // Update preview name
        let displayName = '';
        if (firstName && lastName) {
            displayName = firstName + ' ' + lastName;
        } else if (firstName) {
            displayName = firstName;
        } else if (lastName) {
            displayName = lastName;
        } else {
            displayName = usernameInput.value;
        }

        previewName.textContent = displayName;
        previewEmail.textContent = email;

        // Update preview initials
        let initials = '';
        if (firstName && lastName) {
            initials = (firstName.charAt(0) + lastName.charAt(0)).toUpperCase();
        } else if (firstName) {
            initials = firstName.charAt(0).toUpperCase();
        } else if (lastName) {
            initials = lastName.charAt(0).toUpperCase();
        } else {
            initials = usernameInput.value.substring(0, 2).toUpperCase();
        }

        previewInitials.textContent = initials;
    }

    // Add event listeners
    [firstNameInput, lastNameInput, emailInput].forEach(input => {
        input.addEventListener('input', checkForChanges);
        input.addEventListener('blur', checkForChanges);
    });

    // Reset form function
    window.resetForm = function() {
        firstNameInput.value = originalValues.first_name;
        lastNameInput.value = originalValues.last_name;
        emailInput.value = originalValues.email;
        checkForChanges();
    };

    // Form validation
    emailInput.addEventListener('input', function() {
        const email = this.value.trim();
        if (email && !isValidEmail(email)) {
            this.setCustomValidity('Inserisci un indirizzo email valido');
        } else {
            this.setCustomValidity('');
        }
    });

    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    // Form submission
    form.addEventListener('submit', function(e) {
        const email = emailInput.value.trim();

        if (!email) {
            e.preventDefault();
            alert('L\'email è obbligatoria');
            emailInput.focus();
            return;
        }

        if (!isValidEmail(email)) {
            e.preventDefault();
            alert('Inserisci un indirizzo email valido');
            emailInput.focus();
            return;
        }

        // Check if there are actually changes
        const hasChanges =
            firstNameInput.value !== originalValues.first_name ||
            lastNameInput.value !== originalValues.last_name ||
            emailInput.value !== originalValues.email;

        if (!hasChanges) {
            e.preventDefault();
            alert('Non ci sono modifiche da salvare');
            return;
        }

        // Disable button to prevent double submission
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Salvataggio...';
    });

    // Initial check
    checkForChanges();

    // Focus on first input
    firstNameInput.focus();
});