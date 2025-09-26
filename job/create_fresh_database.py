# create_fresh_database.py - Crea un database fresco con sistema utenti
# Copyright 2025 SILICONDEV SPA

import os
import sys
from datetime import datetime


def create_fresh_database():
    """Crea un database completamente nuovo con sistema utenti"""

    print("🔨 CREAZIONE DATABASE TIMESHEET DA ZERO")
    print("=" * 50)

    # Importa il sistema Flask dopo aver verificato le dipendenze
    try:
        from flask import Flask
        from models import db, init_db, User, UserRole
        print("✅ Importazioni Flask e models riuscite")
    except ImportError as e:
        print(f"❌ Errore importazione: {e}")
        print("\n💡 Assicurati di aver:")
        print("   1. Sostituito models.py con la nuova versione")
        print("   2. Installato Flask-Login: pip install Flask-Login==0.6.3")
        return False

    try:
        # Crea app Flask temporanea
        app = Flask(__name__)
        app.config['SECRET_KEY'] = 'temp-key-for-db-creation'
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timesheet.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        print("📊 Configurazione Flask completata")

        # Inizializza database
        print("🗄️  Creando database e tabelle...")
        init_db(app)

        with app.app_context():
            # Verifica che tutto sia stato creato
            users_count = User.query.count()
            print(f"👥 Utenti creati: {users_count}")

            if users_count > 0:
                admin = User.query.filter_by(username='admin').first()
                if admin:
                    print(f"🔑 Admin user: {admin.username} ({admin.email})")
                    print(f"🛡️  Ruolo: {admin.role.value}")

        print("\n" + "=" * 60)
        print("🎉 DATABASE CREATO CON SUCCESSO!")
        print("=" * 60)
        print("📁 File database: timesheet.db")
        print("\n📋 Credenziali di accesso:")
        print("   Username: admin")
        print("   Password: admin123")
        print("   Email: admin@timesheet.app")
        print("\n🚀 Ora puoi avviare l'app con: python app.py")
        print("🌐 E accedere a: http://localhost:5000")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ ERRORE durante la creazione: {str(e)}")

        # Diagnostica più dettagliata
        if "cannot import name" in str(e):
            print("\n🔍 DIAGNOSI:")
            print("   Il file models.py non è stato aggiornato correttamente")
            print("   Verifica di aver sostituito tutto il contenuto del file")
        elif "No module named" in str(e):
            print("\n🔍 DIAGNOSI:")
            print("   Dipendenza mancante. Installa con:")
            print("   pip install Flask-Login==0.6.3")

        return False


def check_environment():
    """Controlla che l'ambiente sia pronto"""

    print("🔍 CONTROLLO AMBIENTE")
    print("-" * 30)

    # Controlla se models.py esiste
    if not os.path.exists('models.py'):
        print("❌ File models.py non trovato!")
        return False

    # Controlla se models.py contiene le nuove classi
    with open('models.py', 'r', encoding='utf-8') as f:
        content = f.read()

    checks = [
        ('Flask-Login UserMixin', 'from flask_login import UserMixin'),
        ('Classe User', 'class User(db.Model, UserMixin)'),
        ('Istanza db', 'db = SQLAlchemy()'),
        ('UserRole enum', 'class UserRole(enum.Enum)'),
        ('init_user_system', 'def init_user_system()')
    ]

    all_good = True
    for name, check in checks:
        if check in content:
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - MANCANTE!")
            all_good = False

    if not all_good:
        print("\n⚠️  Il file models.py non è aggiornato!")
        print("   Sostituisci tutto il contenuto con la nuova versione")
        return False

    print("✅ Ambiente verificato correttamente")
    return True


def main():
    """Funzione principale"""

    # Prima controlla l'ambiente
    if not check_environment():
        print("\n❌ Ambiente non pronto. Correggi i problemi e riprova.")
        return 1

    # Poi crea il database
    success = create_fresh_database()
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())