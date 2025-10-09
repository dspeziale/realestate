import json
import hashlib
import secrets
from pathlib import Path
from functools import wraps
from flask import session, redirect, url_for, flash


class AuthManager:
    """Gestisce l'autenticazione degli utenti tramite file JSON"""

    def __init__(self, users_file='users.json'):
        self.users_file = users_file
        self.init_users_file()

    def init_users_file(self):
        """Inizializza il file utenti se non esiste"""
        if not Path(self.users_file).exists():
            # Crea utente admin di default
            default_users = {
                "admin": {
                    "password_hash": self.hash_password("admin123"),
                    "email": "admin@aste.local",
                    "role": "admin",
                    "created_at": "2025-01-01T00:00:00"
                }
            }
            self.save_users(default_users)
            print(f"✅ File utenti creato: {self.users_file}")
            print("📧 Utente default: admin / admin123")

    def hash_password(self, password):
        """Genera hash sicuro della password con salt"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return f"{salt}${pwd_hash.hex()}"

    def verify_password(self, password, password_hash):
        """Verifica la password contro l'hash"""
        try:
            salt, stored_hash = password_hash.split('$')
            pwd_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            )
            return pwd_hash.hex() == stored_hash
        except:
            return False

    def load_users(self):
        """Carica gli utenti dal file JSON"""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}

    def save_users(self, users):
        """Salva gli utenti nel file JSON"""
        with open(self.users_file, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=2, ensure_ascii=False)

    def authenticate(self, username, password):
        """Autentica un utente"""
        users = self.load_users()

        if username not in users:
            return False, "Utente non trovato"

        user = users[username]

        if not self.verify_password(password, user['password_hash']):
            return False, "Password errata"

        return True, user

    def add_user(self, username, password, email, role='user'):
        """Aggiunge un nuovo utente"""
        users = self.load_users()

        if username in users:
            return False, "Utente già esistente"

        from datetime import datetime
        users[username] = {
            "password_hash": self.hash_password(password),
            "email": email,
            "role": role,
            "created_at": datetime.now().isoformat()
        }

        self.save_users(users)
        return True, "Utente creato con successo"

    def change_password(self, username, old_password, new_password):
        """Cambia la password di un utente"""
        users = self.load_users()

        if username not in users:
            return False, "Utente non trovato"

        if not self.verify_password(old_password, users[username]['password_hash']):
            return False, "Password attuale errata"

        users[username]['password_hash'] = self.hash_password(new_password)
        self.save_users(users)
        return True, "Password modificata con successo"

    def get_user_info(self, username):
        """Ottiene informazioni utente"""
        users = self.load_users()
        if username in users:
            user_info = users[username].copy()
            user_info.pop('password_hash', None)  # Non restituire l'hash
            return user_info
        return None


def login_required(f):
    """Decorator per proteggere le route"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Devi effettuare il login per accedere a questa pagina', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """Decorator per route riservate agli admin"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Devi effettuare il login', 'warning')
            return redirect(url_for('login'))

        if session.get('role') != 'admin':
            flash('Accesso negato: privilegi amministratore richiesti', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function