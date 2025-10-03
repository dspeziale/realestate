import sqlite3

DATABASE = 'aste_immobiliari.db'


def fix_database():
    """Aggiunge la colonna created_at se mancante"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    try:
        # Verifica se la colonna esiste
        cursor.execute("PRAGMA table_info(aste)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'created_at' not in columns:
            print("Aggiungo la colonna 'created_at'...")
            cursor.execute('''
                ALTER TABLE aste 
                ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ''')
            conn.commit()
            print("✓ Colonna aggiunta con successo!")
        else:
            print("✓ La colonna 'created_at' esiste già")

    except Exception as e:
        print(f"✗ Errore: {e}")
    finally:
        conn.close()


if __name__ == '__main__':
    fix_database()