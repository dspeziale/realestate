# emergency_migrate.py - Migrazione di Emergenza Database
# Risolve l'errore "no such column: projects.user_id"

import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash


def emergency_migration():
    """Migrazione di emergenza per aggiungere le colonne mancanti"""

    db_path = 'timesheet.db'

    if not os.path.exists(db_path):
        print("❌ Database timesheet.db non trovato!")
        return False

    # Backup automatico
    backup_path = f'timesheet_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backup creato: {backup_path}")
    except Exception as e:
        print(f"⚠️  Errore durante backup: {e}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔧 Avvio migrazione di emergenza...")

        # 1. Creare tabella users se non esiste
        print("1️⃣ Creando tabella users...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(80) UNIQUE NOT NULL,
                email VARCHAR(120) UNIQUE NOT NULL,
                password_hash VARCHAR(255),
                first_name VARCHAR(80),
                last_name VARCHAR(80),
                role VARCHAR(20) DEFAULT 'user' NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                provider VARCHAR(50) DEFAULT 'local',
                provider_id VARCHAR(100),
                profile_picture VARCHAR(500),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login DATETIME
            )
        ''')

        # 2. Verificare se l'admin esiste, altrimenti crearlo
        print("2️⃣ Verificando utente admin...")
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_user = cursor.fetchone()

        if not admin_user:
            print("   Creando utente admin...")
            admin_password = generate_password_hash('admin123')
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, first_name, last_name, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ('admin', 'admin@timesheet.app', admin_password, 'Admin', 'User', 'admin', datetime.now()))
            admin_user_id = cursor.lastrowid
            print(f"   ✅ Admin creato con ID: {admin_user_id}")
        else:
            admin_user_id = admin_user[0]
            print(f"   ✅ Admin già esistente con ID: {admin_user_id}")

        # 3. Aggiungere user_id a projects se non esiste
        print("3️⃣ Controllando colonna user_id in projects...")
        cursor.execute("PRAGMA table_info(projects)")
        projects_columns = [col[1] for col in cursor.fetchall()]

        if 'user_id' not in projects_columns:
            print("   Aggiungendo colonna user_id a projects...")
            cursor.execute('ALTER TABLE projects ADD COLUMN user_id INTEGER')
            print("   ✅ Colonna user_id aggiunta a projects")
        else:
            print("   ✅ Colonna user_id già presente in projects")

        # 4. Aggiungere user_id a time_entries se non esiste
        print("4️⃣ Controllando colonna user_id in time_entries...")
        cursor.execute("PRAGMA table_info(time_entries)")
        entries_columns = [col[1] for col in cursor.fetchall()]

        if 'user_id' not in entries_columns:
            print("   Aggiungendo colonna user_id a time_entries...")
            cursor.execute('ALTER TABLE time_entries ADD COLUMN user_id INTEGER')
            print("   ✅ Colonna user_id aggiunta a time_entries")
        else:
            print("   ✅ Colonna user_id già presente in time_entries")

        # 5. Assegnare tutti i dati orfani all'admin
        print("5️⃣ Assegnando dati esistenti all'admin...")
        cursor.execute('UPDATE projects SET user_id = ? WHERE user_id IS NULL', (admin_user_id,))
        projects_updated = cursor.rowcount

        cursor.execute('UPDATE time_entries SET user_id = ? WHERE user_id IS NULL', (admin_user_id,))
        entries_updated = cursor.rowcount

        print(f"   ✅ {projects_updated} progetti assegnati all'admin")
        print(f"   ✅ {entries_updated} voci temporali assegnate all'admin")

        # 6. Commit delle modifiche
        conn.commit()

        print("\n" + "=" * 60)
        print("🎉 MIGRAZIONE COMPLETATA CON SUCCESSO!")
        print("=" * 60)
        print(f"💾 Backup salvato in: {backup_path}")
        print("\n📋 Credenziali di accesso:")
        print("   Username: admin")
        print("   Password: admin123")
        print("   Email: admin@timesheet.app")
        print("\n🚀 Ora puoi avviare l'app con: python app.py")
        print("=" * 60)

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRORE durante la migrazione: {str(e)}")
        print(f"💾 Il tuo backup è salvato in: {backup_path}")
        print("🔄 Puoi ripristinarlo con: copy {} timesheet.db".format(backup_path))
        return False

    finally:
        conn.close()


def main():
    print("🚨 MIGRAZIONE DI EMERGENZA DATABASE TIMESHEET")
    print("=" * 50)
    print("Questo script risolverà l'errore 'no such column: projects.user_id'")
    print()

    try:
        success = emergency_migration()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️  Operazione interrotta dall'utente")
        return 1
    except Exception as e:
        print(f"\n💥 Errore imprevisto: {e}")
        return 1


if __name__ == '__main__':
    import sys

    sys.exit(main())