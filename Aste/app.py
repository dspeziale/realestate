from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'chiave-segreta-per-sessioni'

DATABASE = 'aste_immobiliari.db'


def get_db():
    """Ottiene connessione al database"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/modifica/<int:id>', methods=['GET', 'POST'])
def modifica(id):
    """Pagina per modificare un'asta esistente"""
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        try:
            # Aggiorna i dati nel database
            cursor.execute('''
                UPDATE aste SET
                    titolo = ?, tipo_immobile = ?, tipo_vendita = ?, url = ?,
                    indirizzo = ?, indirizzo_completo = ?, zona = ?, citta = ?, cap = ?,
                    prezzo_asta = ?, numero_locali = ?, numero_bagni = ?, piano = ?,
                    descrizione_breve = ?, descrizione_completa = ?,
                    data_asta = ?, lotto = ?,
                    foglio = ?, particella = ?, categoria = ?, rendita = ?,
                    telefono = ?
                WHERE id = ?
            ''', (
                request.form.get('titolo'),
                request.form.get('tipo_immobile'),
                request.form.get('tipo_vendita'),
                request.form.get('url'),
                request.form.get('indirizzo'),
                request.form.get('indirizzo_completo'),
                request.form.get('zona'),
                request.form.get('citta'),
                request.form.get('cap'),
                request.form.get('prezzo_asta'),
                int(request.form.get('numero_locali')) if request.form.get('numero_locali') else None,
                int(request.form.get('numero_bagni')) if request.form.get('numero_bagni') else None,
                request.form.get('piano'),
                request.form.get('descrizione_breve'),
                request.form.get('descrizione_completa'),
                request.form.get('data_asta'),
                request.form.get('lotto'),
                request.form.get('foglio'),
                request.form.get('particella'),
                request.form.get('categoria'),
                request.form.get('rendita'),
                request.form.get('telefono'),
                id
            ))
            conn.commit()
            flash('Asta modificata con successo!', 'success')
            return redirect(url_for('dettaglio', id=id))

        except Exception as e:
            flash(f'Errore nella modifica: {str(e)}', 'error')
        finally:
            conn.close()

    # GET - Mostra il form precompilato
    cursor.execute('SELECT * FROM aste WHERE id = ?', (id,))
    asta = cursor.fetchone()
    conn.close()

    if asta:
        return render_template('modifica.html', asta=asta)
    else:
        flash('Asta non trovata', 'error')
        return redirect(url_for('index'))

@app.route('/inserisci', methods=['GET', 'POST'])
def inserisci():
    """Pagina per inserire manualmente una nuova asta"""
    if request.method == 'POST':
        try:
            # Costruisci l'oggetto dati dalla form
            data = {
                'info_generali': {
                    'titolo': request.form.get('titolo'),
                    'tipo_immobile': request.form.get('tipo_immobile'),
                    'tipo_vendita': request.form.get('tipo_vendita'),
                    'url': request.form.get('url'),
                    'data_inserimento': datetime.now().isoformat()
                },
                'localizzazione': {
                    'indirizzo': request.form.get('indirizzo'),
                    'indirizzo_completo': request.form.get('indirizzo_completo'),
                    'zona': request.form.get('zona'),
                    'citta': request.form.get('citta'),
                    'cap': request.form.get('cap')
                },
                'prezzi': {
                    'prezzo_asta': request.form.get('prezzo_asta')
                },
                'caratteristiche': {
                    'numero_locali': int(request.form.get('numero_locali')) if request.form.get(
                        'numero_locali') else None,
                    'numero_bagni': int(request.form.get('numero_bagni')) if request.form.get('numero_bagni') else None,
                    'piano': request.form.get('piano')
                },
                'descrizione': {
                    'breve': request.form.get('descrizione_breve'),
                    'completa': request.form.get('descrizione_completa')
                },
                'informazioni_asta': {
                    'data_asta': request.form.get('data_asta'),
                    'lotto': request.form.get('lotto')
                },
                'dati_catastali': {
                    'foglio': request.form.get('foglio'),
                    'particella': request.form.get('particella'),
                    'categoria': request.form.get('categoria'),
                    'rendita': request.form.get('rendita')
                },
                'contatti': {
                    'telefono': request.form.get('telefono')
                }
            }

            inserisci_asta(data)
            flash('Asta inserita con successo!', 'success')
            return redirect(url_for('index'))

        except Exception as e:
            flash(f'Errore nell\'inserimento: {str(e)}', 'error')

    return render_template('inserisci.html')

def init_db():
    """Inizializza il database"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS aste (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titolo TEXT,
            tipo_immobile TEXT,
            tipo_vendita TEXT,
            url TEXT,
            data_inserimento TEXT,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()


@app.route('/')
def index():
    """Pagina principale con lista aste"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM aste ORDER BY created_at DESC')
    aste = cursor.fetchall()
    conn.close()
    return render_template('index.html', aste=aste)


@app.route('/carica', methods=['GET', 'POST'])
def carica():
    """Pagina per caricare JSON"""
    if request.method == 'POST':
        try:
            if 'files' in request.files:
                files = request.files.getlist('files')
                caricati = 0
                errori = 0

                for file in files:
                    if file and file.filename:
                        if file.filename.endswith('.json'):
                            try:
                                data = json.load(file)
                                inserisci_asta(data)
                                caricati += 1
                            except Exception as e:
                                errori += 1
                                flash(f'Errore nel file {file.filename}: {str(e)}', 'warning')
                        else:
                            errori += 1
                            flash(f'File {file.filename} non è un JSON valido', 'warning')

                if caricati > 0:
                    flash(f'{caricati} asta/e caricata/e con successo!', 'success')
                if errori > 0 and caricati == 0:
                    flash('Nessuna asta caricata. Controlla i file selezionati.', 'error')

            elif 'json_text' in request.form:
                data = json.loads(request.form['json_text'])
                inserisci_asta(data)
                flash('Asta caricata con successo!', 'success')

            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Errore nel caricamento: {str(e)}', 'error')

    return render_template('carica.html')


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
    """Elimina asta"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM aste WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Asta eliminata con successo', 'success')
    return redirect(url_for('index'))


@app.route('/ricerca')
def ricerca():
    """Pagina ricerca aste"""
    query = request.args.get('q', '')
    conn = get_db()
    cursor = conn.cursor()

    if query:
        cursor.execute('''
            SELECT * FROM aste 
            WHERE titolo LIKE ? OR citta LIKE ? OR indirizzo LIKE ?
            ORDER BY created_at DESC
        ''', (f'%{query}%', f'%{query}%', f'%{query}%'))
    else:
        cursor.execute('SELECT * FROM aste ORDER BY created_at DESC')

    aste = cursor.fetchall()
    conn.close()
    return render_template('ricerca.html', aste=aste, query=query)


def inserisci_asta(data):
    """Inserisce asta nel database"""
    conn = get_db()
    cursor = conn.cursor()

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
        info.get('data_inserimento'),
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
    conn.close()


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)