// static/js/admin-create-user.js - Admin Create User JavaScript
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('create-user-form');
    const firstNameInput = document.getElementById('first_name');
    const lastNameInput = document.getElementById('last_name');
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm_password');
    const roleSelect = document.getElementById('role');
    const isActiveCheckbox = document.getElementById('is_active');
    const createBtn = document.getElementById('create-btn');
    const previewSection = document.getElementById('preview-section');

    // Preview elements
    const previewName = document.getElementById('preview-name');
    const previewUsername = document.getElementById('preview-username');
    const previewEmail = document.getElementById('preview-email');
    const previewInitials = document.getElementById('preview-initials');
    const previewRole = document.getElementById('preview-role');
    const previewStatus = document.getElementById('preview-status');

    // Password strength elements
    const strengthFill = document.getElementById('strength-fill');
    const strengthText = document.getElementById('strength-text');
    const matchText = document.getElementById('password-match-text');

    // Password visibility toggles
    setupPasswordToggle('toggle-password', 'password');
    setupPasswordToggle('toggle-confirm', 'confirm_password');

    function setupPasswordToggle(buttonId, inputId) {
        const button = document.getElementById(buttonId);
        const input = document.getElementById(inputId);

        button.addEventListener('click', function() {
            const type = input.getAttribute('type');
            if (type === 'password') {
                input.setAttribute('type', 'text');
                button.innerHTML = '<i class="bi bi-eye-slash"></i>';
            } else {
                input.setAttribute('type', 'password');
                button.innerHTML = '<i class="bi bi-eye"></i>';
            }
        });
    }

    // Username validation
    usernameInput.addEventListener('input', function() {
        const username = this.value.trim();

        if (username.length === 0) {
            this.classList.remove('is-valid', 'is-invalid');
            return;
        }

        if (username.length < 3) {
            this.classList.add('is-invalid');
            this.classList.remove('is-valid');
            this.setCustomValidity('Username deve essere di almeno 3 caratteri');
        } else if (!/^[a-zA-Z0-9_]+$/.test(username)) {
            this.classList.add('is-invalid');
            this.classList.remove('is-valid');
            this.setCustomValidity('Solo lettere, numeri e underscore');
        } else {
            this.classList.add('is-valid');
            this.classList.remove('is-invalid');
            this.setCustomValidity('');
        }

        updatePreview();
        checkFormValidity();
    });

    // Email validation
    emailInput.addEventListener('input', function() {
        const email = this.value.trim();

        if (email.length === 0) {
            this.classList.remove('is-valid', 'is-invalid');
            return;
        }

        if (isValidEmail(email)) {
            this.classList.add('is-valid');
            this.classList.remove('is-invalid');
            this.setCustomValidity('');
        } else {
            this.classList.add('is-invalid');
            this.classList.remove('is-valid');
            this.setCustomValidity('Inserisci un indirizzo email valido');
        }

        updatePreview();
        checkFormValidity();
    });

    // Password strength checker
    passwordInput.addEventListener('input', function() {
        const password = this.value;
        checkPasswordStrength(password);
        checkPasswordMatch();
        updateRequirements(password);
        checkFormValidity();
    });

    // Confirm password checker
    confirmPasswordInput.addEventListener('input', function() {
        checkPasswordMatch();
        checkFormValidity();
    });

    // Other fields for preview
    [firstNameInput, lastNameInput, roleSelect, isActiveCheckbox].forEach(input => {
        input.addEventListener('input', updatePreview);
        input.addEventListener('change', updatePreview);
    });

    function checkPasswordStrength(password) {
        strengthFill.className = 'strength-fill';

        if (password.length === 0) {
            strengthText.textContent = 'Almeno 6 caratteri';
            strengthFill.style.width = '0%';
            return;
        }

        const strength = calculatePasswordStrength(password);

        if (strength === 'weak') {
            strengthFill.classList.add('strength-weak');
            strengthText.textContent = 'Password debole';
        } else if (strength === 'medium') {
            strengthFill.classList.add('strength-medium');
            strengthText.textContent = 'Password media';
        } else if (strength === 'strong') {
            strengthFill.classList.add('strength-strong');
            strengthText.textContent = 'Password forte';
        }
    }

    function calculatePasswordStrength(password) {
        if (password.length < 6) return 'weak';

        let score = 0;
        if (password.length >= 8) score++;
        if (/[a-z]/.test(password)) score++;
        if (/[A-Z]/.test(password)) score++;
        if (/[0-9]/.test(password)) score++;
        if (/[^A-Za-z0-9]/.test(password)) score++;

        if (score < 2) return 'weak';
        if (score < 4) return 'medium';
        return 'strong';
    }

    function updateRequirements(password) {
        const requirements = [
            { id: 'req-length', test: password.length >= 6 },
            { id: 'req-lower', test: /[a-z]/.test(password) },
            { id: 'req-upper', test: /[A-Z]/.test(password) },
            { id: 'req-number', test: /[0-9]/.test(password) },
            { id: 'req-special', test: /[^A-Za-z0-9]/.test(password) }
        ];

        requirements.forEach(req => {
            const element = document.getElementById(req.id);
            if (req.test) {
                element.className = 'requirement-met';
            } else {
                element.className = 'text-muted';
            }
        });
    }

    function checkPasswordMatch() {
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;

        if (confirmPassword.length === 0) {
            matchText.textContent = '';
            matchText.className = 'form-text';
            confirmPasswordInput.classList.remove('is-valid', 'is-invalid');
        } else if (password === confirmPassword) {
            matchText.textContent = '✓ Le password coincidono';
            matchText.className = 'form-text text-success';
            confirmPasswordInput.classList.add('is-valid');
            confirmPasswordInput.classList.remove('is-invalid');
        } else {
            matchText.textContent = '✗ Le password non coincidono';
            matchText.className = 'form-text text-danger';
            confirmPasswordInput.classList.add('is-invalid');
            confirmPasswordInput.classList.remove('is-valid');
        }
    }

    function updatePreview() {
        const firstName = firstNameInput.value.trim();
        const lastName = lastNameInput.value.trim();
        const username = usernameInput.value.trim();
        const email = emailInput.value.trim();
        const role = roleSelect.value;
        const isActive = isActiveCheckbox.checked;

        // Update preview name
        let displayName = '';
        if (firstName && lastName) {
            displayName = firstName + ' ' + lastName;
        } else if (firstName) {
            displayName = firstName;
        } else if (lastName) {
            displayName = lastName;
        } else if (username) {
            displayName = username;
        } else {
            displayName = 'Nome Utente';
        }

        previewName.textContent = displayName;
        previewUsername.textContent = username || 'username';
        previewEmail.textContent = email || 'email';

        // Update preview initials
        let initials = '';
        if (firstName && lastName) {
            initials = (firstName.charAt(0) + lastName.charAt(0)).toUpperCase();
        } else if (firstName) {
            initials = firstName.charAt(0).toUpperCase();
        } else if (lastName) {
            initials = lastName.charAt(0).toUpperCase();
        } else if (username) {
            initials = username.substring(0, 2).toUpperCase();
        } else {
            initials = 'U';
        }

        previewInitials.textContent = initials;

        // Update role badge
        const roleColors = {
            'user': 'bg-primary',
            'admin': 'bg-danger',
            'viewer': 'bg-secondary'
        };

        previewRole.className = 'badge ' + (roleColors[role] || 'bg-secondary');
        previewRole.textContent = role ? role.charAt(0).toUpperCase() + role.slice(1) : 'User';

        // Update status badge
        previewStatus.className = 'badge ' + (isActive ? 'bg-success' : 'bg-warning');
        previewStatus.textContent = isActive ? 'Attivo' : 'Disattivato';

        // Show preview if any field has content
        if (firstName || lastName || username || email) {
            previewSection.style.display = 'block';
        } else {
            previewSection.style.display = 'none';
        }
    }

    function checkFormValidity() {
        const username = usernameInput.value.trim();
        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        const role = roleSelect.value;

        const isValid =
            username.length >= 3 &&
            /^[a-zA-Z0-9_]+$/.test(username) &&
            isValidEmail(email) &&
            password.length >= 6 &&
            password === confirmPassword &&
            role;

        createBtn.disabled = !isValid;
    }

    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    // Generate random password
    window.generatePassword = function() {
        const length = 12;
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
        let password = '';

        // Ensure at least one of each type
        password += 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.charAt(Math.floor(Math.random() * 26));
        password += 'abcdefghijklmnopqrstuvwxyz'.charAt(Math.floor(Math.random() * 26));
        password += '0123456789'.charAt(Math.floor(Math.random() * 10));
        password += '!@#$%^&*'.charAt(Math.floor(Math.random() * 8));

        // Fill the rest
        for (let i = 4; i < length; i++) {
            password += chars.charAt(Math.floor(Math.random() * chars.length));
        }

        // Shuffle the password
        password = password.split('').sort(() => Math.random() - 0.5).join('');

        passwordInput.value = password;
        confirmPasswordInput.value = password;

        checkPasswordStrength(password);
        checkPasswordMatch();
        checkFormValidity();

        // Show password temporarily
        passwordInput.type = 'text';
        confirmPasswordInput.type = 'text';
        document.getElementById('toggle-password').innerHTML = '<i class="bi bi-eye-slash"></i>';
        document.getElementById('toggle-confirm').innerHTML = '<i class="bi bi-eye-slash"></i>';

        // Copy to clipboard if available
        if (navigator.clipboard) {
            navigator.clipboard.writeText(password).then(() => {
                alert('Password generata e copiata negli appunti: ' + password);
            });
        } else {
            alert('Password generata: ' + password);
        }
    };

    // Form submission
    form.addEventListener('submit', function(e) {
        const username = usernameInput.value.trim();
        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;

        if (!username || username.length < 3) {
            e.preventDefault();
            alert('Username deve essere di almeno 3 caratteri');
            usernameInput.focus();
            return;
        }

        if (!isValidEmail(email)) {
            e.preventDefault();
            alert('Inserisci un indirizzo email valido');
            emailInput.focus();
            return;
        }

        if (password.length < 6) {
            e.preventDefault();
            alert('La password deve essere di almeno 6 caratteri');
            passwordInput.focus();
            return;
        }

        if (password !== confirmPassword) {
            e.preventDefault();
            alert('Le password non coincidono');
            confirmPasswordInput.focus();
            return;
        }

        // Disable button to prevent double submission
        createBtn.disabled = true;
        createBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Creazione...';
    });

    // Initial checks
    updatePreview();
    checkFormValidity();

    // Focus on first input
    firstNameInput.focus();
});