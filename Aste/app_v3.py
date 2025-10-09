from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
import json
from datetime import datetime
import os
from auth import AuthManager, login_required, admin_required

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave-segreta-CHANGE-IN-PRODUCTION')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

DATABASE = 'aste_immobiliari_v2.db'

# Inizializza il sistema di autenticazione
auth_manager = AuthManager('users.json')


def get_db():
    """Connessione al database"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ==================== ROUTE DI AUTENTICAZIONE ====================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Pagina di login"""
    if 'username' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Inserisci username e password', 'error')
            return render_template('login.html')

        success, result = auth_manager.authenticate(username, password)

        if success:
            # Login riuscito
            session['username'] = username
            session['email'] = result['email']
            session['role'] = result['role']

            flash(f'Benvenuto {username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash(result, 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout utente"""
    username = session.get('username', 'Utente')
    session.clear()
    flash(f'Arrivederci {username}!', 'info')
    return redirect(url_for('login'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Cambio password"""
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([old_password, new_password, confirm_password]):
            flash('Compila tutti i campi', 'error')
            return render_template('change_password.html')

        if new_password != confirm_password:
            flash('Le nuove password non coincidono', 'error')
            return render_template('change_password.html')

        if len(new_password) < 6:
            flash('La password deve essere di almeno 6 caratteri', 'error')
            return render_template('change_password.html')

        username = session.get('username')
        success, message = auth_manager.change_password(username, old_password, new_password)

        if success:
            flash(message, 'success')
            return redirect(url_for('index'))
        else:
            flash(message, 'error')

    return render_template('change_password.html')


@app.route('/users')
@admin_required
def users():
    """Gestione utenti (solo admin)"""
    users_data = auth_manager.load_users()
    users_list = []

    for username, data in users_data.items():
        users_list.append({
            'username': username,
            'email': data.get('email'),
            'role': data.get('role'),
            'created_at': data.get('created_at')
        })

    return render_template('users.html', users=users_list)


@app.route('/add-user', methods=['POST'])
@admin_required
def add_user():
    """Aggiunge nuovo utente (solo admin)"""
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    email = request.form.get('email', '').strip()
    role = request.form.get('role', 'user')

    if not all([username, password, email]):
        flash('Compila tutti i campi', 'error')
        return redirect(url_for('users'))

    success, message = auth_manager.add_user(username, password, email, role)

    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('users'))


# ==================== ROUTE PRINCIPALI ====================

@app.route('/')
@login_required
def index():
    """Dashboard con DataTables"""
    return render_template('index_v2.html')


@app.route('/api/aste')
@login_required
def api_aste():
    """API per DataTables - paginazione server-side"""
    conn = get_db()
    cursor = conn.cursor()

    # Parametri DataTables
    draw = request.args.get('draw', type=int, default=1)
    start = request.args.get('start', type=int, default=0)
    length = request.args.get('length', type=int, default=25)
    search_value = request.args.get('search[value]', default='')

    # Ordinamento
    order_column_idx = request.args.get('order[0][column]', type=int, default=0)
    order_dir = request.args.get('order[0][dir]', default='desc')

    columns = ['codice_asta', 'titolo', 'citta', 'data_vendita', 'prezzo_base',
               'tribunale', 'superficie_mq', 'vani']
    order_column = columns[order_column_idx] if order_column_idx < len(columns) else 'data_vendita'

    # Query base
    where_clause = ""
    params = []

    if search_value:
        where_clause = """
            WHERE codice_asta LIKE ? OR titolo LIKE ? OR citta LIKE ? 
            OR tribunale LIKE ? OR indirizzo LIKE ?
        """
        search_pattern = f'%{search_value}%'
        params = [search_pattern] * 5

    # Count totale
    cursor.execute('SELECT COUNT(*) as total FROM aste')
    total_records = cursor.fetchone()['total']

    # Count filtrato
    if where_clause:
        cursor.execute(f'SELECT COUNT(*) as total FROM aste {where_clause}', params)
        filtered_records = cursor.fetchone()['total']
    else:
        filtered_records = total_records

    # Query dati
    query = f"""
        SELECT 
            codice_asta, titolo, tipologia_immobile, citta, provincia,
            indirizzo, data_vendita, prezzo_base, prezzo_base_formatted,
            offerta_minima_formatted, tribunale, superficie_mq, vani, bagni,
            tipo_vendita, stato_immobile
        FROM aste
        {where_clause}
        ORDER BY {order_column} {order_dir}
        LIMIT ? OFFSET ?
    """

    cursor.execute(query, params + [length, start])
    aste = cursor.fetchall()

    # Formatta dati per DataTables
    data = []
    for asta in aste:
        data.append({
            'codice_asta': asta['codice_asta'],
            'titolo': asta['titolo'] or 'N/A',
            'citta': f"{asta['citta'] or 'N/A'} ({asta['provincia'] or ''})",
            'indirizzo': asta['indirizzo'] or 'N/A',
            'data_vendita': asta['data_vendita'] or 'N/A',
            'prezzo_base': asta['prezzo_base_formatted'] or 'N/A',
            'tribunale': asta['tribunale'] or 'N/A',
            'superficie': f"{asta['superficie_mq']} mq" if asta['superficie_mq'] else 'N/A',
            'vani': asta['vani'] or 'N/A',
            'azioni': f'<a href="/dettaglio/{asta["codice_asta"]}" class="btn btn-sm btn-primary">Dettagli</a>'
        })

    conn.close()

    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data
    })


@app.route('/dettaglio/<codice_asta>')
@login_required
def dettaglio(codice_asta):
    """Pagina dettaglio completa"""
    conn = get_db()
    cursor = conn.cursor()

    # Asta principale
    cursor.execute('SELECT * FROM aste WHERE codice_asta = ?', (codice_asta,))
    asta = cursor.fetchone()

    if not asta:
        flash('Asta non trovata', 'error')
        return redirect(url_for('index'))

    # Allegati
    cursor.execute('SELECT * FROM allegati WHERE codice_asta = ?', (codice_asta,))
    allegati = cursor.fetchall()

    # Foto
    cursor.execute('SELECT * FROM foto WHERE codice_asta = ? ORDER BY ordine', (codice_asta,))
    foto = cursor.fetchall()

    # Planimetrie
    cursor.execute('SELECT * FROM planimetrie WHERE codice_asta = ? ORDER BY ordine', (codice_asta,))
    planimetrie = cursor.fetchall()

    # Storico vendite
    cursor.execute('SELECT * FROM storico_vendite WHERE codice_asta = ? ORDER BY data_vendita DESC', (codice_asta,))
    storico = cursor.fetchall()

    conn.close()

    return render_template('dettaglio_v2.html',
                           asta=asta,
                           allegati=allegati,
                           foto=foto,
                           planimetrie=planimetrie,
                           storico=storico)


@app.route('/ricerca')
@login_required
def ricerca():
    """Ricerca avanzata"""
    return render_template('ricerca_v2.html')


@app.route('/api/stats')
@login_required
def api_stats():
    """Statistiche per dashboard"""
    conn = get_db()
    cursor = conn.cursor()

    stats = {}

    # Totali
    cursor.execute('SELECT COUNT(*) as total FROM aste')
    stats['total'] = cursor.fetchone()['total']

    # Per tribunale
    cursor.execute('''
        SELECT tribunale, COUNT(*) as count 
        FROM aste 
        WHERE tribunale IS NOT NULL 
        GROUP BY tribunale 
        ORDER BY count DESC 
        LIMIT 10
    ''')
    stats['per_tribunale'] = dict(cursor.fetchall())

    # Per città
    cursor.execute('''
        SELECT citta, COUNT(*) as count 
        FROM aste 
        WHERE citta IS NOT NULL 
        GROUP BY citta 
        ORDER BY count DESC 
        LIMIT 10
    ''')
    stats['per_citta'] = dict(cursor.fetchall())

    # Range prezzi
    cursor.execute('''
        SELECT 
            MIN(prezzo_base) as min_prezzo,
            MAX(prezzo_base) as max_prezzo,
            AVG(prezzo_base) as avg_prezzo
        FROM aste 
        WHERE prezzo_base IS NOT NULL
    ''')
    result = cursor.fetchone()
    stats['prezzi'] = {
        'minimo': result['min_prezzo'],
        'massimo': result['max_prezzo'],
        'media': result['avg_prezzo']
    }

    conn.close()
    return jsonify(stats)


@app.route('/mappa')
@login_required
def mappa():
    """Visualizzazione mappa con coordinate GPS"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT codice_asta, titolo, citta, indirizzo, 
               latitudine, longitudine, prezzo_base_formatted
        FROM aste 
        WHERE latitudine IS NOT NULL AND longitudine IS NOT NULL
        LIMIT 500
    ''')

    aste_mappa = []
    for row in cursor.fetchall():
        aste_mappa.append({
            'codice': row['codice_asta'],
            'titolo': row['titolo'],
            'citta': row['citta'],
            'indirizzo': row['indirizzo'],
            'lat': row['latitudine'],
            'lng': row['longitudine'],
            'prezzo': row['prezzo_base_formatted']
        })

    conn.close()

    return render_template('mappa.html', aste=json.dumps(aste_mappa))


if __name__ == '__main__':
    print(f"\n{'=' * 60}")
    print("🚀 AVVIO APPLICAZIONE FLASK V2 CON AUTENTICAZIONE")
    print(f"{'=' * 60}")
    print(f"📁 Database: {DATABASE}")
    print(f"👤 Sistema Auth: users.json")
    print(f"🌐 Server: http://localhost:5000")
    print(f"📧 Login default: admin / admin123")
    print(f"{'=' * 60}\n")

    app.run(debug=True, port=5000)