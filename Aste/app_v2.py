from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import json
from datetime import datetime
import os
import re
import bleach

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave-segreta-CHANGE-IN-PRODUCTION')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

DATABASE = 'aste_immobiliari_v2.db'


def sanitize_input(text):
    """Sanifica input per prevenire XSS"""
    if not text:
        return None
    return bleach.clean(str(text).strip())


def get_db():
    """Connessione al database"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """Dashboard con DataTables"""
    return render_template('index_v2.html')


@app.route('/api/aste')
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
            'azioni': f'''
                <div class="btn-group btn-group-sm">
                    <a href="/dettaglio/{asta['codice_asta']}" class="btn btn-primary">
                        <i class="bi bi-eye"></i>
                    </a>
                    <a href="/modifica/{asta['codice_asta']}" class="btn btn-warning">
                        <i class="bi bi-pencil"></i>
                    </a>
                    <button class="btn btn-danger" onclick="confermaElimina('{asta['codice_asta']}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            '''
        })

    conn.close()

    return jsonify({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': filtered_records,
        'data': data
    })


@app.route('/dettaglio/<codice_asta>')
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


@app.route('/inserisci', methods=['GET', 'POST'])
def inserisci():
    """Inserimento manuale nuova asta"""
    if request.method == 'POST':
        try:
            # Validazione
            codice_asta = sanitize_input(request.form.get('codice_asta', '').strip())
            titolo = sanitize_input(request.form.get('titolo', '').strip())

            if not codice_asta:
                flash('Il codice asta è obbligatorio', 'error')
                return render_template('inserisci_v2.html')

            if not titolo:
                flash('Il titolo è obbligatorio', 'error')
                return render_template('inserisci_v2.html')

            # Verifica duplicato
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT codice_asta FROM aste WHERE codice_asta = ?', (codice_asta,))
            if cursor.fetchone():
                flash(f'Codice asta {codice_asta} già esistente!', 'error')
                conn.close()
                return render_template('inserisci_v2.html')

            # Converti numeri
            superficie_mq = request.form.get('superficie_mq', '').strip()
            superficie_mq = float(superficie_mq) if superficie_mq else None

            vani = request.form.get('vani', '').strip()
            vani = float(vani) if vani else None

            bagni = request.form.get('bagni', '').strip()
            bagni = int(bagni) if bagni else None

            prezzo_base = request.form.get('prezzo_base', '').strip()
            prezzo_base = float(
                prezzo_base.replace('€', '').replace('.', '').replace(',', '.').strip()) if prezzo_base else None

            # Inserimento
            cursor.execute('''
                INSERT INTO aste (
                    codice_asta, url, titolo, tipologia_immobile, categoria,
                    indirizzo, citta, provincia, cap, piano,
                    vani, bagni, superficie_mq, disponibilita, classe_energetica, stato_immobile,
                    data_vendita, tipo_vendita, modalita_vendita,
                    prezzo_base, prezzo_base_formatted,
                    offerta_minima, offerta_minima_formatted,
                    rialzo_minimo, rialzo_minimo_formatted,
                    tribunale, tipo_procedura, numero_rge, anno_rge,
                    delegato_nome, delegato_cognome, delegato_telefono, delegato_email,
                    custode_nome, custode_cognome, custode_telefono, custode_email,
                    descrizione_breve, descrizione_completa,
                    data_inserimento
                ) VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?,?, ?,?,?, ?,?, ?,?, ?,?, ?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?, ?)
            ''', (
                codice_asta,
                sanitize_input(request.form.get('url')),
                titolo,
                sanitize_input(request.form.get('tipologia_immobile')),
                sanitize_input(request.form.get('categoria')),
                sanitize_input(request.form.get('indirizzo')),
                sanitize_input(request.form.get('citta')),
                sanitize_input(request.form.get('provincia')),
                sanitize_input(request.form.get('cap')),
                sanitize_input(request.form.get('piano')),
                vani,
                bagni,
                superficie_mq,
                sanitize_input(request.form.get('disponibilita')),
                sanitize_input(request.form.get('classe_energetica')),
                sanitize_input(request.form.get('stato_immobile')),
                sanitize_input(request.form.get('data_vendita')),
                sanitize_input(request.form.get('tipo_vendita', 'Asta giudiziaria')),
                sanitize_input(request.form.get('modalita_vendita')),
                prezzo_base,
                sanitize_input(request.form.get('prezzo_base_formatted')),
                None,  # offerta_minima
                None,  # offerta_minima_formatted
                None,  # rialzo_minimo
                None,  # rialzo_minimo_formatted
                sanitize_input(request.form.get('tribunale')),
                sanitize_input(request.form.get('tipo_procedura')),
                sanitize_input(request.form.get('numero_rge')),
                sanitize_input(request.form.get('anno_rge')),
                sanitize_input(request.form.get('delegato_nome')),
                sanitize_input(request.form.get('delegato_cognome')),
                sanitize_input(request.form.get('delegato_telefono')),
                sanitize_input(request.form.get('delegato_email')),
                sanitize_input(request.form.get('custode_nome')),
                sanitize_input(request.form.get('custode_cognome')),
                sanitize_input(request.form.get('custode_telefono')),
                sanitize_input(request.form.get('custode_email')),
                sanitize_input(request.form.get('descrizione_breve')),
                sanitize_input(request.form.get('descrizione_completa')),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

            conn.commit()
            conn.close()

            flash(f'✅ Asta {codice_asta} inserita con successo!', 'success')
            return redirect(url_for('dettaglio', codice_asta=codice_asta))

        except Exception as e:
            flash(f'Errore: {str(e)}', 'error')
            print(f"❌ ERRORE INSERIMENTO: {e}")
            import traceback
            traceback.print_exc()

    return render_template('inserisci_v2.html')


@app.route('/modifica/<codice_asta>', methods=['GET', 'POST'])
def modifica(codice_asta):
    """Modifica asta esistente"""
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            titolo = sanitize_input(request.form.get('titolo', '').strip())

            if not titolo:
                flash('Il titolo è obbligatorio', 'error')
                return redirect(url_for('modifica', codice_asta=codice_asta))

            # Converti numeri
            superficie_mq = request.form.get('superficie_mq', '').strip()
            superficie_mq = float(superficie_mq) if superficie_mq else None

            vani = request.form.get('vani', '').strip()
            vani = float(vani) if vani else None

            bagni = request.form.get('bagni', '').strip()
            bagni = int(bagni) if bagni else None

            prezzo_base = request.form.get('prezzo_base', '').strip()
            prezzo_base = float(
                prezzo_base.replace('€', '').replace('.', '').replace(',', '.').strip()) if prezzo_base else None

            cursor.execute('''
                UPDATE aste SET
                    url = ?,
                    titolo = ?,
                    tipologia_immobile = ?,
                    categoria = ?,
                    indirizzo = ?,
                    citta = ?,
                    provincia = ?,
                    cap = ?,
                    piano = ?,
                    vani = ?,
                    bagni = ?,
                    superficie_mq = ?,
                    disponibilita = ?,
                    classe_energetica = ?,
                    stato_immobile = ?,
                    data_vendita = ?,
                    tipo_vendita = ?,
                    modalita_vendita = ?,
                    prezzo_base = ?,
                    prezzo_base_formatted = ?,
                    tribunale = ?,
                    tipo_procedura = ?,
                    numero_rge = ?,
                    anno_rge = ?,
                    delegato_nome = ?,
                    delegato_cognome = ?,
                    delegato_telefono = ?,
                    delegato_email = ?,
                    custode_nome = ?,
                    custode_cognome = ?,
                    custode_telefono = ?,
                    custode_email = ?,
                    descrizione_breve = ?,
                    descrizione_completa = ?,
                    data_aggiornamento = ?
                WHERE codice_asta = ?
            ''', (
                sanitize_input(request.form.get('url')),
                titolo,
                sanitize_input(request.form.get('tipologia_immobile')),
                sanitize_input(request.form.get('categoria')),
                sanitize_input(request.form.get('indirizzo')),
                sanitize_input(request.form.get('citta')),
                sanitize_input(request.form.get('provincia')),
                sanitize_input(request.form.get('cap')),
                sanitize_input(request.form.get('piano')),
                vani,
                bagni,
                superficie_mq,
                sanitize_input(request.form.get('disponibilita')),
                sanitize_input(request.form.get('classe_energetica')),
                sanitize_input(request.form.get('stato_immobile')),
                sanitize_input(request.form.get('data_vendita')),
                sanitize_input(request.form.get('tipo_vendita')),
                sanitize_input(request.form.get('modalita_vendita')),
                prezzo_base,
                sanitize_input(request.form.get('prezzo_base_formatted')),
                sanitize_input(request.form.get('tribunale')),
                sanitize_input(request.form.get('tipo_procedura')),
                sanitize_input(request.form.get('numero_rge')),
                sanitize_input(request.form.get('anno_rge')),
                sanitize_input(request.form.get('delegato_nome')),
                sanitize_input(request.form.get('delegato_cognome')),
                sanitize_input(request.form.get('delegato_telefono')),
                sanitize_input(request.form.get('delegato_email')),
                sanitize_input(request.form.get('custode_nome')),
                sanitize_input(request.form.get('custode_cognome')),
                sanitize_input(request.form.get('custode_telefono')),
                sanitize_input(request.form.get('custode_email')),
                sanitize_input(request.form.get('descrizione_breve')),
                sanitize_input(request.form.get('descrizione_completa')),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                codice_asta
            ))

            conn.commit()
            conn.close()

            flash('✅ Asta modificata con successo!', 'success')
            return redirect(url_for('dettaglio', codice_asta=codice_asta))

        except Exception as e:
            conn.close()
            flash(f'Errore: {str(e)}', 'error')
            return redirect(url_for('modifica', codice_asta=codice_asta))

    # GET - Mostra form
    cursor.execute('SELECT * FROM aste WHERE codice_asta = ?', (codice_asta,))
    asta = cursor.fetchone()
    conn.close()

    if not asta:
        flash('Asta non trovata', 'error')
        return redirect(url_for('index'))

    return render_template('modifica_v2.html', asta=asta)


@app.route('/elimina/<codice_asta>', methods=['POST'])
def elimina(codice_asta):
    """Elimina asta"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        # Elimina dati correlati
        cursor.execute('DELETE FROM allegati WHERE codice_asta = ?', (codice_asta,))
        cursor.execute('DELETE FROM foto WHERE codice_asta = ?', (codice_asta,))
        cursor.execute('DELETE FROM planimetrie WHERE codice_asta = ?', (codice_asta,))
        cursor.execute('DELETE FROM storico_vendite WHERE codice_asta = ?', (codice_asta,))

        # Elimina asta
        cursor.execute('DELETE FROM aste WHERE codice_asta = ?', (codice_asta,))

        conn.commit()
        flash('✅ Asta eliminata con successo', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Errore: {str(e)}', 'error')
    finally:
        conn.close()

    return redirect(url_for('index'))


@app.route('/ricerca')
def ricerca():
    """Pagina ricerca avanzata"""
    return render_template('ricerca_v2.html')


@app.route('/api/stats')
def api_stats():
    """API endpoint per statistiche"""
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


@app.errorhandler(404)
def not_found(e):
    """Gestione 404"""
    flash('Pagina non trovata', 'error')
    return redirect(url_for('index'))


@app.errorhandler(500)
def server_error(e):
    """Gestione 500"""
    flash('Errore interno del server', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    print(f"\n{'=' * 60}")
    print("🚀 AVVIO APPLICAZIONE FLASK V2")
    print(f"{'=' * 60}")
    print(f"📁 Database: {DATABASE}")
    print(f"🌐 Server: http://localhost:5000")
    print(f"{'=' * 60}\n")

    app.run(debug=True, port=5000)