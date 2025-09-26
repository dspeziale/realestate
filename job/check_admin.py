# check_admin.py - Verifica e ripara l'utente admin
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash


def check_and_fix_admin():
    """Verifica e corregge l'utente admin"""

    print("🔍 VERIFICA UTENTE ADMIN")
    print("=" * 30)

    if not os.path.exists('timesheet.db'):
        print("❌ Database timesheet.db non trovato!")
        return False

    conn = sqlite3.connect('timesheet.db')
    cursor = conn.cursor()

    try:
        # Verifica se la tabella users esiste
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cursor.fetchone():
            print("❌ Tabella users non trovata!")
            return False

        print("✅ Tabella users trovata")

        # Cerca tutti gli utenti
        cursor.execute("SELECT id, username, email, password_hash, role FROM users")
        users = cursor.fetchall()

        print(f"👥 Utenti nel database: {len(users)}")

        if len(users) == 0:
            print("⚠️  Nessun utente trovato! Creazione admin...")
            create_admin_user(cursor)
            conn.commit()
        else:
            for user in users:
                user_id, username, email, password_hash, role = user
                print(f"   ID: {user_id}, Username: {username}, Email: {email}, Role: {role}")

                # Verifica password per admin
                if username == 'admin':
                    print(f"🔐 Testando password per admin...")
                    if password_hash and check_password_hash(password_hash, 'admin123'):
                        print("✅ Password admin123 funziona!")
                    else:
                        print("❌ Password admin123 NON funziona!")
                        print("🔧 Aggiornamento password...")

                        new_hash = generate_password_hash('admin123')
                        cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?",
                                       (new_hash, 'admin'))
                        conn.commit()
                        print("✅ Password admin aggiornata!")

        # Test finale
        print("\n🧪 TEST FINALE CREDENZIALI")
        print("-" * 25)

        cursor.execute("SELECT username, email, password_hash FROM users WHERE username = 'admin'")
        admin = cursor.fetchone()

        if admin:
            username, email, password_hash = admin
            print(f"Username: {username}")
            print(f"Email: {email}")

            # Test password
            if check_password_hash(password_hash, 'admin123'):
                print("✅ Password: admin123 - FUNZIONA!")
            else:
                print("❌ Password: admin123 - NON FUNZIONA!")
                return False

            print("\n🎯 CREDENZIALI CORRETTE:")
            print("   Username: admin")
            print("   Password: admin123")
            print(f"   Email: {email}")
        else:
            print("❌ Utente admin non trovato!")
            return False

        return True

    except Exception as e:
        print(f"❌ Errore: {e}")
        return False
    finally:
        conn.close()


def create_admin_user(cursor):
    """Crea l'utente admin"""
    from datetime import datetime

    admin_password = generate_password_hash('admin123')
    cursor.execute('''
        INSERT INTO users (username, email, password_hash, first_name, last_name, role, created_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('admin', 'admin@timesheet.app', admin_password, 'Admin', 'User', 'admin', datetime.now(), 1))

    print("✅ Utente admin creato!")


def check_flask_login_setup():
    """Verifica che Flask-Login sia configurato correttamente"""

    print("\n🔍 VERIFICA FLASK-LOGIN")
    print("=" * 25)

    try:
        from flask_login import UserMixin
        print("✅ Flask-Login importato")

        from models import User
        print("✅ Classe User importata")

        # Verifica che User erediti da UserMixin
        if issubclass(User, UserMixin):
            print("✅ User eredita da UserMixin")
        else:
            print("❌ User NON eredita da UserMixin!")
            return False

        return True

    except ImportError as e:
        print(f"❌ Errore importazione: {e}")
        return False


def main():
    """Funzione principale"""

    print("🔐 DIAGNOSTICA SISTEMA LOGIN")
    print("=" * 40)

    # Verifica Flask-Login
    if not check_flask_login_setup():
        print("\n❌ Problema con Flask-Login setup")
        return 1

    # Verifica admin user
    if not check_and_fix_admin():
        print("\n❌ Problema con utente admin")
        return 1

    print("\n" + "=" * 50)
    print("🎉 SISTEMA LOGIN VERIFICATO E RIPARATO!")
    print("=" * 50)
    print("🔑 Usa queste credenziali:")
    print("   Username: admin")
    print("   Password: admin123")
    print("🌐 URL: http://localhost:5000/auth/login")
    print("=" * 50)

    return 0


if __name__ == '__main__':
    import sys

    sys.exit(main())