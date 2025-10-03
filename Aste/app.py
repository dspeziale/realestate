from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import json
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import bleach

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave-segreta-per-sessioni-CHANGE-IN-PRODUCTION')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

DATABASE = 'aste_immobiliari.db'
ALLOWED_EXTENSIONS = {'json'}


def allowed_file(filename):
    """Verifica se il file ha estensione permessa"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_input(text):
    """Sanifica input utente per prevenire XSS"""
    if not text:
        return None
    return bleach.clean(str(text).strip())


def validate_json_structure(data):
    """Valida la struttura del JSON caricato"""
    required_keys = ['info_generali']
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Chiave mancante nel JSON: {key}")
    return True


def get_db():
    """Ottiene connessione al database con gestione errori"""
    try:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        flash(f'Errore connessione database: {str(e)}', 'error')
        raise


def init_db():
    """Inizializza il database con indici per performance"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aste (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titolo TEXT NOT NULL,
            tipo_immobile TEXT,
            tipo_vendita TEXT DEFAULT 'Asta',
            url TEXT,
            data_inserimento TEXT NOT NULL,
            indirizzo TEXT,
            indirizzo_completo TEXT,
            zona TEXT,
            citta TEXT,
            cap TEXT,
            prezzo_asta TEXT,
            numero_locali INTEGER,
            numero_bagni INTEGER,
            piano TEXT,
            descrizione_breve TEXT,
            descrizione_completa TEXT,
            data_asta TEXT,
            lotto TEXT,
            foglio TEXT,
            particella TEXT,
            categoria TEXT,
            rendita TEXT,
            telefono TEXT,
            json_completo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Crea indici per migliorare le performance delle ricerche
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_citta ON aste(citta)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tipo_immobile ON aste(tipo_immobile)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_asta ON aste(data_asta)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON aste(created_at DESC)')

    conn.commit()
    conn.close()


@app.route('/')
def index():
    """Pagina principale con lista aste e paginazione"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    conn = get_db()
    cursor = conn.cursor()

    # Conta totale
    cursor.execute('SELECT COUNT(*) as total FROM aste')
    total = cursor.fetchone()['total']

    # Ottieni aste paginate
    cursor.execute('''
        SELECT * FROM aste 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    ''', (per_page, offset))
    aste = cursor.fetchall()
    conn.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template('index.html',
                           aste=aste,
                           page=page,
                           total_pages=total_pages,
                           total=total)


@app.route('/carica', methods=['GET', 'POST'])
def carica():
    """Pagina per caricare JSON con validazione migliorata"""
    if request.method == 'POST':
        try:
            caricati = 0
            errori = []

            # Caricamento da file
            if 'files' in request.files:
                files = request.files.getlist('files')

                for file in files:
                    if file and file.filename:
                        if not allowed_file(file.filename):
                            errori.append(f'{file.filename}: formato non valido')
                            continue

                        try:
                            filename = secure_filename(file.filename)
                            data = json.load(file)
                            validate_json_structure(data)
                            inserisci_asta(data)
                            caricati += 1
                        except json.JSONDecodeError:
                            errori.append(f'{file.filename}: JSON non valido')
                        except ValueError as e:
                            errori.append(f'{file.filename}: {str(e)}')
                        except Exception as e:
                            errori.append(f'{file.filename}: errore imprevisto - {str(e)}')

            # Caricamento da textarea
            elif 'json_text' in request.form:
                try:
                    json_text = request.form['json_text'].strip()
                    if not json_text:
                        flash('Il contenuto JSON è vuoto', 'error')
                        return render_template('carica.html')

                    data = json.loads(json_text)
                    validate_json_structure(data)
                    inserisci_asta(data)
                    caricati += 1
                except json.JSONDecodeError as e:
                    flash(f'JSON non valido: {str(e)}', 'error')
                    return render_template('carica.html')
                except ValueError as e:
                    flash(str(e), 'error')
                    return render_template('carica.html')

            # Messaggi di feedback
            if caricati > 0:
                flash(f'✓ {caricati} asta/e caricata/e con successo!', 'success')

            if errori:
                for errore in errori[:5]:  # Mostra max 5 errori
                    flash(f'✗ {errore}', 'warning')
                if len(errori) > 5:
                    flash(f'...e altri {len(errori) - 5} errori', 'warning')

            if caricati > 0 or errori:
                return redirect(url_for('index'))

        except Exception as e:
            flash(f'Errore nel caricamento: {str(e)}', 'error')

    return render_template('carica.html')


@app.route('/inserisci', methods=['GET', 'POST'])
def inserisci():
    """Pagina per inserire manualmente una nuova asta con validazione"""
    if request.method == 'POST':
        try:
            # Validazione titolo obbligatorio
            titolo = sanitize_input(request.form.get('titolo'))
            if not titolo:
                flash('Il titolo è obbligatorio', 'error')
                return render_template('inserisci.html')

            # Validazione numeri
            numero_locali = request.form.get('numero_locali')
            numero_bagni = request.form.get('numero_bagni')

            if numero_locali:
                try:
                    numero_locali = int(numero_locali)
                    if numero_locali < 0:
                        flash('Il numero di locali non può essere negativo', 'error')
                        return render_template('inserisci.html')
                except ValueError:
                    flash('Numero locali non valido', 'error')
                    return render_template('inserisci.html')
            else:
                numero_locali = None

            if numero_bagni:
                try:
                    numero_bagni = int(numero_bagni)
                    if numero_bagni < 0:
                        flash('Il numero di bagni non può essere negativo', 'error')
                        return render_template('inserisci.html')
                except ValueError:
                    flash('Numero bagni non valido', 'error')
                    return render_template('inserisci.html')
            else:
                numero_bagni = None

            # Costruisci l'oggetto dati sanificato
            data = {
                'info_generali': {
                    'titolo': titolo,
                    'tipo_immobile': sanitize_input(request.form.get('tipo_immobile')),
                    'tipo_vendita': sanitize_input(request.form.get('tipo_vendita', 'Asta')),
                    'url': sanitize_input(request.form.get('url')),
                    'data_inserimento': datetime.now().isoformat()
                },
                'localizzazione': {
                    'indirizzo': sanitize_input(request.form.get('indirizzo')),
                    'indirizzo_completo': sanitize_input(request.form.get('indirizzo_completo')),
                    'zona': sanitize_input(request.form.get('zona')),
                    'citta': sanitize_input(request.form.get('citta')),
                    'cap': sanitize_input(request.form.get('cap'))
                },
                'prezzi': {
                    'prezzo_asta': sanitize_input(request.form.get('prezzo_asta'))
                },
                'caratteristiche': {
                    'numero_locali': numero_locali,
                    'numero_bagni': numero_bagni,
                    'piano': sanitize_input(request.form.get('piano'))
                },
                'descrizione': {
                    'breve': sanitize_input(request.form.get('descrizione_breve')),
                    'completa': sanitize_input(request.form.get('descrizione_completa'))
                },
                'informazioni_asta': {
                    'data_asta': sanitize_input(request.form.get('data_asta')),
                    'lotto': sanitize_input(request.form.get('lotto'))
                },
                'dati_catastali': {
                    'foglio': sanitize_input(request.form.get('foglio')),
                    'particella': sanitize_input(request.form.get('particella')),
                    'categoria': sanitize_input(request.form.get('categoria')),
                    'rendita': sanitize_input(request.form.get('rendita'))
                },
                'contatti': {
                    'telefono': sanitize_input(request.form.get('telefono'))
                }
            }

            inserisci_asta(data)
            flash('✓ Asta inserita con successo!', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            flash(f'Errore nell\'inserimento: {str(e)}', 'error')
            print(f"❌ ERRORE INSERIMENTO: {e}")
            import traceback
            traceback.print_exc()

    return render_template('inserisci.html')


@app.route('/modifica/<int:id>', methods=['GET', 'POST'])
def modifica(id):
    """Pagina per modificare un'asta esistente"""
    if request.method == 'POST':
        conn = None
        try:
            print(f"\n{'=' * 60}")
            print(f"DEBUG MODIFICA ASTA ID: {id}")
            print(f"{'=' * 60}")

            # Validazione titolo obbligatorio
            titolo = sanitize_input(request.form.get('titolo'))
            if not titolo:
                flash('Il titolo è obbligatorio', 'error')
                return redirect(url_for('modifica', id=id))

            print(f"Titolo: {titolo}")
            print(f"Città: {request.form.get('citta')}")
            print(f"Prezzo: {request.form.get('prezzo_asta')}")

            # Validazione e conversione numeri
            numero_locali = request.form.get('numero_locali', '').strip()
            numero_bagni = request.form.get('numero_bagni', '').strip()

            try:
                numero_locali = int(numero_locali) if numero_locali else None
            except ValueError:
                flash('Numero locali non valido', 'error')
                return redirect(url_for('modifica', id=id))

            try:
                numero_bagni = int(numero_bagni) if numero_bagni else None
            except ValueError:
                flash('Numero bagni non valido', 'error')
                return redirect(url_for('modifica', id=id))

            print(f"Numero locali: {numero_locali}")
            print(f"Numero bagni: {numero_bagni}")

            # Connessione al database
            conn = get_db()
            cursor = conn.cursor()

            # Verifica che l'asta esista
            cursor.execute('SELECT id FROM aste WHERE id = ?', (id,))
            if not cursor.fetchone():
                flash('Asta non trovata', 'error')
                conn.close()
                return redirect(url_for('index'))

            # Aggiorna i dati nel database
            cursor.execute('''
                UPDATE aste SET
                    titolo = ?,
                    tipo_immobile = ?,
                    tipo_vendita = ?,
                    url = ?,
                    indirizzo = ?,
                    indirizzo_completo = ?,
                    zona = ?,
                    citta = ?,
                    cap = ?,
                    prezzo_asta = ?,
                    numero_locali = ?,
                    numero_bagni = ?,
                    piano = ?,
                    descrizione_breve = ?,
                    descrizione_completa = ?,
                    data_asta = ?,
                    lotto = ?,
                    foglio = ?,
                    particella = ?,
                    categoria = ?,
                    rendita = ?,
                    telefono = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                titolo,
                sanitize_input(request.form.get('tipo_immobile')),
                sanitize_input(request.form.get('tipo_vendita')),
                sanitize_input(request.form.get('url')),
                sanitize_input(request.form.get('indirizzo')),
                sanitize_input(request.form.get('indirizzo_completo')),
                sanitize_input(request.form.get('zona')),
                sanitize_input(request.form.get('citta')),
                sanitize_input(request.form.get('cap')),
                sanitize_input(request.form.get('prezzo_asta')),
                numero_locali,
                numero_bagni,
                sanitize_input(request.form.get('piano')),
                sanitize_input(request.form.get('descrizione_breve')),
                sanitize_input(request.form.get('descrizione_completa')),
                sanitize_input(request.form.get('data_asta')),
                sanitize_input(request.form.get('lotto')),
                sanitize_input(request.form.get('foglio')),
                sanitize_input(request.form.get('particella')),
                sanitize_input(request.form.get('categoria')),
                sanitize_input(request.form.get('rendita')),
                sanitize_input(request.form.get('telefono')),
                id
            ))

            rows_affected = cursor.rowcount
            conn.commit()

            print(f"✅ Righe modificate: {rows_affected}")
            print(f"{'=' * 60}\n")

            if rows_affected > 0:
                flash('✓ Asta modificata con successo!', 'success')
            else:
                flash('⚠ Nessuna modifica effettuata', 'warning')

            conn.close()
            return redirect(url_for('dettaglio', id=id))

        except sqlite3.Error as e:
            if conn:
                conn.rollback()
                conn.close()
            flash(f'Errore database: {str(e)}', 'error')
            print(f"❌ ERRORE DATABASE: {e}")
            import traceback
            traceback.print_exc()
            return redirect(url_for('modifica', id=id))

        except Exception as e:
            if conn:
                conn.close()
            flash(f'Errore nella modifica: {str(e)}', 'error')
            print(f"❌ ERRORE MODIFICA: {e}")
            import traceback
            traceback.print_exc()
            return redirect(url_for('modifica', id=id))

    # GET - Mostra il form precompilato
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM aste WHERE id = ?', (id,))
    asta = cursor.fetchone()
    conn.close()

    if asta:
        return render_template('modifica.html', asta=asta)
    else:
        flash('Asta non trovata', 'error')
        return redirect(url_for('index'))


@app.route('/dettaglio/<int:id>')
def dettaglio(id):
    """Pagina dettaglio asta"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM aste WHERE id = ?', (id,))
    asta = cursor.fetchone()
    conn.close()

    if asta:
        return render_template('dettaglio.html', asta=asta)
    else:
        flash('Asta non trovata', 'error')
        return redirect(url_for('index'))


@app.route('/elimina/<int:id>', methods=['POST'])
def elimina(id):
    """Elimina asta con controllo esistenza"""
    conn = get_db()
    cursor = conn.cursor()

    # Verifica esistenza
    cursor.execute('SELECT id FROM aste WHERE id = ?', (id,))
    if not cursor.fetchone():
        flash('Asta non trovata', 'error')
        conn.close()
        return redirect(url_for('index'))

    cursor.execute('DELETE FROM aste WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('✓ Asta eliminata con successo', 'success')
    return redirect(url_for('index'))


@app.route('/ricerca')
def ricerca():
    """Pagina ricerca aste con ricerca full-text migliorata"""
    query = request.args.get('q', '').strip()
    conn = get_db()
    cursor = conn.cursor()

    if query:
        search_term = f'%{query}%'
        cursor.execute('''
            SELECT * FROM aste 
            WHERE titolo LIKE ? 
               OR citta LIKE ? 
               OR indirizzo LIKE ?
               OR zona LIKE ?
               OR tipo_immobile LIKE ?
            ORDER BY created_at DESC
        ''', (search_term, search_term, search_term, search_term, search_term))
    else:
        cursor.execute('SELECT * FROM aste ORDER BY created_at DESC LIMIT 50')

    aste = cursor.fetchall()
    conn.close()
    return render_template('ricerca.html', aste=aste, query=query)


@app.route('/api/stats')
def api_stats():
    """API endpoint per statistiche"""
    conn = get_db()
    cursor = conn.cursor()

    stats = {}

    # Totali
    cursor.execute('SELECT COUNT(*) as total FROM aste')
    stats['total'] = cursor.fetchone()['total']

    # Per tipo
    cursor.execute('''
        SELECT tipo_immobile, COUNT(*) as count 
        FROM aste 
        WHERE tipo_immobile IS NOT NULL 
        GROUP BY tipo_immobile
    ''')
    stats['per_tipo'] = dict(cursor.fetchall())

    # Per città (top 10)
    cursor.execute('''
        SELECT citta, COUNT(*) as count 
        FROM aste 
        WHERE citta IS NOT NULL 
        GROUP BY citta 
        ORDER BY count DESC 
        LIMIT 10
    ''')
    stats['top_citta'] = dict(cursor.fetchall())

    conn.close()
    return jsonify(stats)


def inserisci_asta(data):
    """Inserisce asta nel database con gestione errori migliorata"""
    conn = get_db()
    cursor = conn.cursor()

    try:
        info = data.get('info_generali', {})
        loc = data.get('localizzazione', {})
        prezzi = data.get('prezzi', {})
        car = data.get('caratteristiche', {})
        desc = data.get('descrizione', {})
        asta_info = data.get('informazioni_asta', {})
        dati_cat = data.get('dati_catastali', {})
        contatti = data.get('contatti', {})

        cursor.execute('''
            INSERT INTO aste (
                titolo, tipo_immobile, tipo_vendita, url, data_inserimento,
                indirizzo, indirizzo_completo, zona, citta, cap,
                prezzo_asta, numero_locali, numero_bagni, piano,
                descrizione_breve, descrizione_completa,
                data_asta, lotto,
                foglio, particella, categoria, rendita,
                telefono, json_completo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            info.get('titolo'),
            info.get('tipo_immobile'),
            info.get('tipo_vendita'),
            info.get('url'),
            info.get('data_inserimento', datetime.now().isoformat()),
            loc.get('indirizzo'),
            loc.get('indirizzo_completo'),
            loc.get('zona'),
            loc.get('citta'),
            loc.get('cap'),
            prezzi.get('prezzo_asta'),
            car.get('numero_locali'),
            car.get('numero_bagni'),
            car.get('piano'),
            desc.get('breve'),
            desc.get('completa'),
            asta_info.get('data_asta'),
            asta_info.get('lotto'),
            dati_cat.get('foglio'),
            dati_cat.get('particella'),
            dati_cat.get('categoria'),
            dati_cat.get('rendita'),
            contatti.get('telefono'),
            json.dumps(data, ensure_ascii=False)
        ))

        conn.commit()
        print(f"✅ Asta inserita con successo! ID: {cursor.lastrowid}")

    except sqlite3.Error as e:
        conn.rollback()
        print(f"❌ ERRORE DATABASE: {e}")
        raise Exception(f"Errore database: {str(e)}")
    finally:
        conn.close()


@app.errorhandler(404)
def not_found(e):
    """Gestione errore 404"""
    flash('Pagina non trovata', 'error')
    return redirect(url_for('index'))


@app.errorhandler(500)
def server_error(e):
    """Gestione errore 500"""
    flash('Errore interno del server', 'error')
    return redirect(url_for('index'))


if __name__ == '__main__':
    # Crea cartella uploads se non esiste
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Inizializza database
    init_db()

    print(f"\n{'=' * 60}")
    print("🚀 AVVIO APPLICAZIONE FLASK")
    print(f"{'=' * 60}")
    print(f"📁 Database: {DATABASE}")
    print(f"🌐 Server: http://localhost:5000")
    print(f"📊 Debug: ON")
    print(f"{'=' * 60}\n")

    # Avvia app
    app.run(debug=True, port=5000)