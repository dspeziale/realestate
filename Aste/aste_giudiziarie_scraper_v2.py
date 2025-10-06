import requests
from bs4 import BeautifulSoup
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import os
from dotenv import load_dotenv


class AsteGiudiziarieScraperV2:
    def __init__(self, db_name='aste_immobiliari_v2.db'):
        self.db_name = db_name
        self.base_url = "https://www.astegiudiziarie.it"
        self.driver = None

        # Carica credenziali
        load_dotenv()
        self.email = os.getenv('ASTE_EMAIL')
        self.password = os.getenv('ASTE_PASSWORD')

        # Inizializza database
        self.setup_database()

    def setup_database(self):
        """Crea database con struttura completa"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        # Tabella principale ASTE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aste (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Identificativi
                codice_asta TEXT UNIQUE NOT NULL,
                url TEXT UNIQUE,

                -- Info Generali
                titolo TEXT,
                tipologia_immobile TEXT,
                categoria TEXT,
                genere TEXT,

                -- Localizzazione
                indirizzo TEXT,
                indirizzo_completo TEXT,
                civico TEXT,
                citta TEXT,
                provincia TEXT,
                cap TEXT,
                regione TEXT,
                zona TEXT,
                latitudine REAL,
                longitudine REAL,

                -- Caratteristiche Immobile
                piano TEXT,
                vani REAL,
                bagni INTEGER,
                superficie_mq REAL,
                disponibilita TEXT,
                classe_energetica TEXT,
                stato_immobile TEXT,

                -- Dati Lotto
                codice_lotto TEXT,
                numero_beni_lotto INTEGER,
                descrizione_lotto TEXT,
                valore_stima TEXT,

                -- Dati Vendita
                data_vendita DATETIME,
                ora_vendita TEXT,
                tipo_vendita TEXT,
                modalita_vendita TEXT,
                luogo_vendita TEXT,
                indirizzo_luogo_vendita TEXT,
                citta_luogo_vendita TEXT,
                cap_luogo_vendita TEXT,
                termine_offerte DATETIME,

                -- Prezzi
                prezzo_base REAL,
                prezzo_base_formatted TEXT,
                offerta_minima REAL,
                offerta_minima_formatted TEXT,
                rialzo_minimo REAL,
                rialzo_minimo_formatted TEXT,
                deposito_cauzionale TEXT,
                deposito_spese TEXT,

                -- Procedura
                tribunale TEXT,
                tipo_procedura TEXT,
                numero_rge TEXT,
                anno_rge TEXT,

                -- Professionisti
                delegato_nome TEXT,
                delegato_cognome TEXT,
                delegato_telefono TEXT,
                delegato_email TEXT,
                delegato_procede_vendita BOOLEAN,

                custode_nome TEXT,
                custode_cognome TEXT,
                custode_telefono TEXT,
                custode_email TEXT,
                custode_gestisce_visite BOOLEAN,

                -- Descrizioni
                descrizione_breve TEXT,
                descrizione_completa TEXT,

                -- Metadata
                data_pubblicazione DATE,
                data_inserimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                -- JSON completo
                json_completo TEXT
            )
        ''')

        # Tabella ALLEGATI
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS allegati (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice_asta TEXT NOT NULL,
                tipo_allegato TEXT,
                nome_file TEXT,
                url_download TEXT,
                FOREIGN KEY (codice_asta) REFERENCES aste(codice_asta)
            )
        ''')

        # Tabella FOTO
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS foto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice_asta TEXT NOT NULL,
                url_foto TEXT,
                ordine INTEGER,
                FOREIGN KEY (codice_asta) REFERENCES aste(codice_asta)
            )
        ''')

        # Tabella PLANIMETRIE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS planimetrie (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice_asta TEXT NOT NULL,
                url_planimetria TEXT,
                ordine INTEGER,
                FOREIGN KEY (codice_asta) REFERENCES aste(codice_asta)
            )
        ''')

        # Tabella STORICO_VENDITE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS storico_vendite (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice_asta TEXT NOT NULL,
                data_vendita DATE,
                prezzo_base REAL,
                prezzo_base_formatted TEXT,
                FOREIGN KEY (codice_asta) REFERENCES aste(codice_asta)
            )
        ''')

        # Indici per performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_codice_asta ON aste(codice_asta)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_citta ON aste(citta)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_vendita ON aste(data_vendita)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_prezzo ON aste(prezzo_base)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tribunale ON aste(tribunale)')

        conn.commit()
        conn.close()
        print(f"✅ Database '{self.db_name}' inizializzato con struttura completa\n")

    def init_selenium(self):
        """Inizializza Selenium"""
        try:
            print("🔧 Inizializzo il browser...")
            options = Options()
            # options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✓ Browser avviato\n")
            return True
        except Exception as e:
            print(f"❌ Errore: {e}")
            return False

    def login(self):
        """Login al sito"""
        try:
            print("🔐 Login in corso...")
            self.driver.get(self.base_url)
            time.sleep(3)

            # Click Accedi/Registrati
            accedi_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accedi')]")
            accedi_btn.click()
            time.sleep(2)

            # Click Privati
            try:
                privati_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Privati')]")
                privati_btn.click()
                time.sleep(2)
            except:
                pass

            # Inserisci credenziali
            email_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='email']")
            email_field.send_keys(self.email)

            password_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_field.send_keys(self.password)
            password_field.send_keys(Keys.RETURN)

            time.sleep(5)
            print("✅ Login completato\n")
            return True

        except Exception as e:
            print(f"❌ Errore login: {e}")
            return False

    def extract_text(self, soup, selector, default='', attribute=None):
        """Estrae testo da un selettore CSS o attributo"""
        try:
            elem = soup.select_one(selector)
            if elem:
                if attribute:
                    return elem.get(attribute, default)
                return elem.get_text(strip=True)
        except:
            pass
        return default

    def find_text_after(self, soup, search_text):
        """Trova testo dopo una stringa specifica"""
        elem = soup.find(string=re.compile(search_text, re.I))
        if elem:
            parent = elem.find_parent()
            if parent:
                # Cerca il prossimo elemento con testo
                next_elem = parent.find_next_sibling()
                if next_elem:
                    return next_elem.get_text(strip=True)
                # Oppure cerca nel parent stesso
                text = parent.get_text(strip=True)
                # Rimuovi la label e prendi il resto
                return text.replace(search_text, '').strip().strip(':').strip()
        return ''

    def extract_price(self, text):
        """Estrae valore numerico da stringa prezzo"""
        if not text:
            return None
        # Rimuovi € e spazi, converti
        clean = re.sub(r'[€\s]', '', text)
        clean = clean.replace('.', '').replace(',', '.')
        try:
            return float(clean)
        except:
            return None

    def parse_detail_page_v2(self, soup, url):
        """Parsing completo della pagina dettaglio - VERSIONE ROBUSTA"""
        # Inizializza tutti i campi con valori di default
        data = {
            'url': url,
            'codice_asta': None,
            'titolo': None,
            'tipologia_immobile': None,
            'categoria': None,
            'genere': None,
            'indirizzo': None,
            'citta': None,
            'provincia': None,
            'cap': None,
            'latitudine': None,
            'longitudine': None,
            'codice_lotto': None,
            'descrizione_lotto': None,
            'numero_beni_lotto': None,
            'vani': None,
            'bagni': None,
            'superficie_mq': None,
            'piano': None,
            'disponibilita': None,
            'classe_energetica': None,
            'data_vendita': None,
            'tipo_vendita': None,
            'modalita_vendita': None,
            'indirizzo_luogo_vendita': None,
            'citta_luogo_vendita': None,
            'cap_luogo_vendita': None,
            'termine_offerte': None,
            'prezzo_base_formatted': None,
            'prezzo_base': None,
            'offerta_minima_formatted': None,
            'offerta_minima': None,
            'rialzo_minimo_formatted': None,
            'rialzo_minimo': None,
            'deposito_cauzionale': None,
            'tribunale': None,
            'tipo_procedura': None,
            'numero_rge': None,
            'anno_rge': None,
            'delegato_cognome': None,
            'delegato_nome': None,
            'delegato_telefono': None,
            'delegato_email': None,
            'delegato_procede_vendita': False,
            'custode_cognome': None,
            'custode_nome': None,
            'custode_telefono': None,
            'custode_email': None,
            'custode_gestisce_visite': False,
            'descrizione_breve': None,
            'data_pubblicazione': None
        }

        print("\n📋 PARSING DETTAGLIATO")
        print("-" * 60)

        # === CODICE ASTA ===
        # Cerca in vari modi
        codice = None

        # Metodo 1: cerca nel testo della pagina
        codice_patterns = [
            r'Codice asta[:\s]+([A-Z0-9]+)',
            r'Codice[:\s]+([A-Z0-9]+)',
            r'COD\.\s+([A-Z0-9]+)'
        ]
        page_text = soup.get_text()
        for pattern in codice_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                codice = match.group(1)
                break

        # Metodo 2: cerca nei badge
        if not codice:
            badge = soup.find('span', class_='badge', string=re.compile(r'[A-Z0-9]{7,}'))
            if badge:
                codice = badge.get_text(strip=True)

        data['codice_asta'] = codice or 'N/A'
        print(f"✓ Codice: {data['codice_asta']}")

        # === INFO GENERALI ===
        # Titolo
        h1 = soup.find('h1')
        data['titolo'] = h1.get_text(strip=True) if h1 else None

        # Cerca nei data attributes
        data['tipologia_immobile'] = self.extract_text(soup, '[data-pvp-bene-categoria]',
                                                       attribute='data-pvp-bene-categoria')
        if not data['tipologia_immobile']:
            data['tipologia_immobile'] = self.extract_text(soup, '.titoloBene')

        data['genere'] = self.extract_text(soup, '[data-pvp-lotto-genere]', attribute='data-pvp-lotto-genere')
        data['categoria'] = self.extract_text(soup, '[data-pvp-lotto-categoria]', attribute='data-pvp-lotto-categoria')

        # === LOCALIZZAZIONE ===
        data['indirizzo'] = self.extract_text(soup, '[data-pvp-lotto-indirizzo]', attribute='data-pvp-lotto-indirizzo')
        if not data['indirizzo']:
            data['indirizzo'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-indirizzo]',
                                                  attribute='data-pvp-bene-ubicazione-indirizzo')

        data['citta'] = self.extract_text(soup, '[data-pvp-lotto-citta]', attribute='data-pvp-lotto-citta')
        if not data['citta']:
            data['citta'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-citta]',
                                              attribute='data-pvp-bene-ubicazione-citta')

        data['cap'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-capZipCode]',
                                        attribute='data-pvp-bene-ubicazione-capZipCode')
        data['provincia'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-provincia]',
                                              attribute='data-pvp-bene-ubicazione-provincia')

        # Coordinate GPS
        lat_input = soup.find('input', id='lat')
        lng_input = soup.find('input', id='lng')
        if lat_input and lat_input.get('value'):
            try:
                data['latitudine'] = float(lat_input['value'])
            except:
                data['latitudine'] = None
        if lng_input and lng_input.get('value'):
            try:
                data['longitudine'] = float(lng_input['value'])
            except:
                data['longitudine'] = None

        # === DATI LOTTO ===
        data['codice_lotto'] = self.extract_text(soup, '[data-pvp-lotto-codice]', attribute='data-pvp-lotto-codice')

        # Descrizione lotto - cerca nel primo accordion
        desc_elem = soup.select_one('#collapseLotto .accordion-body > p')
        if desc_elem:
            data['descrizione_lotto'] = desc_elem.get_text(strip=True)

        # Numero beni - cerca con regex
        num_beni_match = re.search(r'Numero beni[:\s]+(\d+)', page_text, re.I)
        if num_beni_match:
            try:
                data['numero_beni_lotto'] = int(num_beni_match.group(1))
            except:
                pass

        # === CARATTERISTICHE IMMOBILE ===
        # Cerca vani, superficie, bagni con regex nel testo
        vani_match = re.search(r'Vani[:\s]+([\d,\.]+)', page_text, re.I)
        if vani_match:
            try:
                data['vani'] = float(vani_match.group(1).replace(',', '.'))
            except:
                pass

        bagni_match = re.search(r'Bagni[:\s]+(\d+)', page_text, re.I)
        if bagni_match:
            try:
                data['bagni'] = int(bagni_match.group(1))
            except:
                pass

        superficie_match = re.search(r'Metri quadri[:\s]+([\d,\.]+)', page_text, re.I)
        if superficie_match:
            try:
                data['superficie_mq'] = float(superficie_match.group(1).replace(',', '.'))
            except:
                pass

        piano_match = re.search(r'Piano[:\s]+([^\n]+)', page_text, re.I)
        if piano_match:
            data['piano'] = piano_match.group(1).strip()[:50]

        disponibilita_match = re.search(r'Disponibilità[:\s]+([^\n]+)', page_text, re.I)
        if disponibilita_match:
            data['disponibilita'] = disponibilita_match.group(1).strip()[:100]

        classe_match = re.search(r'Certificazione energetica[:\s]+([^\n]+)', page_text, re.I)
        if classe_match:
            data['classe_energetica'] = classe_match.group(1).strip()[:50]

        # === DATI VENDITA ===
        # Data vendita da attributo
        data['data_vendita'] = None
        data_vendita_elem = soup.find('[data-pvp-datiVendita-dataOraVendita]')
        if data_vendita_elem:
            data['data_vendita'] = data_vendita_elem.get('data-pvp-datiVendita-dataOraVendita')

        # Oppure cerca nel testo
        if not data['data_vendita']:
            data_match = re.search(r'Data vendita[:\s]+(\d{2}/\d{2}/\d{4}.*?\d{2}:\d{2})', page_text, re.I)
            if data_match:
                data['data_vendita'] = data_match.group(1)

        data['tipo_vendita'] = self.extract_text(soup, '[data-pvp-datiVendita-tipologiaVendita]',
                                                 attribute='data-pvp-datiVendita-tipologiaVendita')
        data['modalita_vendita'] = self.extract_text(soup, '[data-pvp-datiVendita-modalitaVendita]',
                                                     attribute='data-pvp-datiVendita-modalitaVendita')

        # Luogo vendita
        data['indirizzo_luogo_vendita'] = self.extract_text(soup, '[data-pvp-datiVendita-luogoVendita-indirizzo]',
                                                            attribute='data-pvp-datiVendita-luogoVendita-indirizzo')
        data['citta_luogo_vendita'] = self.extract_text(soup, '[data-pvp-datiVendita-luogoVendita-citta]',
                                                        attribute='data-pvp-datiVendita-luogoVendita-citta')
        data['cap_luogo_vendita'] = self.extract_text(soup, '[data-pvp-datiVendita-luogoVendita-capZipCode]',
                                                      attribute='data-pvp-datiVendita-luogoVendita-capZipCode')

        # Termine offerte
        termine_elem = soup.find('[data-pvp-datiVendita-terminePresentazioneOfferte]')
        if termine_elem:
            data['termine_offerte'] = termine_elem.get('data-pvp-datiVendita-terminePresentazioneOfferte')

        # === PREZZI ===
        prezzo_base_text = self.extract_text(soup, '[data-pvp-datiVendita-prezzoValoreBase]',
                                             attribute='data-pvp-datiVendita-prezzoValoreBase')
        data['prezzo_base_formatted'] = prezzo_base_text
        data['prezzo_base'] = self.extract_price(prezzo_base_text)

        offerta_min_text = self.extract_text(soup, '[data-pvp-datiVendita-offertaMinima]',
                                             attribute='data-pvp-datiVendita-offertaMinima')
        data['offerta_minima_formatted'] = offerta_min_text
        data['offerta_minima'] = self.extract_price(offerta_min_text)

        rialzo_text = self.extract_text(soup, '[data-pvp-datiVendita-rialzoMinimo]',
                                        attribute='data-pvp-datiVendita-rialzoMinimo')
        data['rialzo_minimo_formatted'] = rialzo_text
        data['rialzo_minimo'] = self.extract_price(rialzo_text)

        # Deposito cauzionale - cerca nel testo
        deposito_match = re.search(r'Deposito cauzionale[:\s]+([^\n]+)', page_text, re.I)
        if deposito_match:
            data['deposito_cauzionale'] = deposito_match.group(1).strip()[:100]

        # === PROCEDURA ===
        tribunale_match = re.search(r'Tribunale[:\s]+([^\n]+)', page_text, re.I)
        if tribunale_match:
            data['tribunale'] = tribunale_match.group(1).strip()[:100]

        tipo_proc_match = re.search(r'Tipo di procedura[:\s]+([^\n]+)', page_text, re.I)
        if tipo_proc_match:
            data['tipo_procedura'] = tipo_proc_match.group(1).strip()[:100]

        # RGE
        ruolo_match = re.search(r'Ruolo[:\s]+(\d+)/(\d+)', page_text, re.I)
        if ruolo_match:
            data['numero_rge'] = ruolo_match.group(1)
            data['anno_rge'] = ruolo_match.group(2)

        # === PROFESSIONISTI ===
        # Cerca sezioni professionisti
        soggetti = soup.find_all('[data-pvp-soggetto]')
        for soggetto in soggetti:
            tipo_text = soggetto.get_text()

            if 'Delegato' in tipo_text:
                data['delegato_cognome'] = self.extract_text(soggetto, '[data-pvp-soggetto-cognome]',
                                                             attribute='data-pvp-soggetto-cognome')
                data['delegato_nome'] = self.extract_text(soggetto, '[data-pvp-soggetto-nome]',
                                                          attribute='data-pvp-soggetto-nome')
                data['delegato_telefono'] = self.extract_text(soggetto, '[data-pvp-soggetto-telefono]',
                                                              attribute='data-pvp-soggetto-telefono')
                data['delegato_email'] = self.extract_text(soggetto, '[data-pvp-soggetto-email]',
                                                           attribute='data-pvp-soggetto-email')
                data['delegato_procede_vendita'] = bool(soggetto.find('[data-pvp-soggetto-procedeOpVendita]'))

            elif 'Custode' in tipo_text:
                data['custode_cognome'] = self.extract_text(soggetto, '[data-pvp-soggetto-cognome]',
                                                            attribute='data-pvp-soggetto-cognome')
                data['custode_nome'] = self.extract_text(soggetto, '[data-pvp-soggetto-nome]',
                                                         attribute='data-pvp-soggetto-nome')
                data['custode_telefono'] = self.extract_text(soggetto, '[data-pvp-soggetto-telefono]',
                                                             attribute='data-pvp-soggetto-telefono')
                data['custode_email'] = self.extract_text(soggetto, '[data-pvp-soggetto-email]',
                                                          attribute='data-pvp-soggetto-email')
                data['custode_gestisce_visite'] = bool(soggetto.find('[data-pvp-soggetto-soggVisitaBene]'))

        # === DESCRIZIONI ===
        desc_breve_elem = soup.find('[data-pvp-bene-descrizioneIT]')
        if desc_breve_elem:
            data['descrizione_breve'] = desc_breve_elem.get_text(strip=True)

        # === DATA PUBBLICAZIONE ===
        pubblicazione_match = re.search(r'Pubblicata dal (\d{2}/\d{2}/\d{4})', page_text)
        if pubblicazione_match:
            data['data_pubblicazione'] = pubblicazione_match.group(1)

        print(f"✅ Parsing completato - {len([v for v in data.values() if v])} campi estratti")
        return data

    def extract_allegati(self, soup, codice_asta):
        """Estrae tutti gli allegati"""
        allegati = []

        links = soup.select('.list-group-modulistica a[href*="/allegato/"]')
        for link in links:
            allegato = {
                'codice_asta': codice_asta,
                'tipo_allegato': link.get_text(strip=True),
                'url_download': self.base_url + link['href'] if not link['href'].startswith('http') else link['href'],
                'nome_file': link['href'].split('/')[-2] if '/' in link['href'] else ''
            }
            allegati.append(allegato)

        return allegati

    def extract_foto(self, soup, codice_asta):
        """Estrae tutte le foto"""
        foto_list = []

        foto_links = soup.select('a[data-fslightbox="galleryFoto"]')
        for idx, link in enumerate(foto_links, 1):
            foto = {
                'codice_asta': codice_asta,
                'url_foto': self.base_url + link['href'] if not link['href'].startswith('http') else link['href'],
                'ordine': idx
            }
            foto_list.append(foto)

        return foto_list

    def extract_planimetrie(self, soup, codice_asta):
        """Estrae planimetrie"""
        plani_list = []

        plani_links = soup.select('a[data-fslightbox="galleryPlani"]')
        for idx, link in enumerate(plani_links, 1):
            plani = {
                'codice_asta': codice_asta,
                'url_planimetria': self.base_url + link['href'] if not link['href'].startswith('http') else link[
                    'href'],
                'ordine': idx
            }
            plani_list.append(plani)

        return plani_list

    def extract_storico_vendite(self, soup, codice_asta):
        """Estrae storico vendite precedenti"""
        storico = []

        rows = soup.select('.table tbody tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                vendita = {
                    'codice_asta': codice_asta,
                    'data_vendita': cells[0].get_text(strip=True),
                    'prezzo_base_formatted': cells[1].get_text(strip=True),
                    'prezzo_base': self.extract_price(cells[1].get_text(strip=True))
                }
                storico.append(vendita)

        return storico

    def save_to_db(self, data, allegati, foto, planimetrie, storico):
        """Salva tutto nel database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            # Salva asta principale - AGGIORNATO con tutti i campi corretti
            cursor.execute('''
                INSERT OR REPLACE INTO aste (
                    codice_asta, url, titolo, tipologia_immobile, categoria, genere,
                    indirizzo, indirizzo_completo, citta, provincia, cap, zona,
                    latitudine, longitudine,
                    piano, vani, bagni, superficie_mq, disponibilita, classe_energetica,
                    codice_lotto, numero_beni_lotto, descrizione_lotto, valore_stima,
                    data_vendita, tipo_vendita, modalita_vendita,
                    indirizzo_luogo_vendita, citta_luogo_vendita, cap_luogo_vendita, 
                    termine_offerte,
                    prezzo_base, prezzo_base_formatted, 
                    offerta_minima, offerta_minima_formatted,
                    rialzo_minimo, rialzo_minimo_formatted, 
                    deposito_cauzionale, deposito_spese,
                    tribunale, tipo_procedura, numero_rge, anno_rge,
                    delegato_nome, delegato_cognome, delegato_telefono, 
                    delegato_email, delegato_procede_vendita,
                    custode_nome, custode_cognome, custode_telefono, 
                    custode_email, custode_gestisce_visite,
                    descrizione_breve, descrizione_completa,
                    data_pubblicazione, json_completo
                ) VALUES (?,?,?,?,?,?, ?,?,?,?,?,?, ?,?, ?,?,?,?,?,?, 
                         ?,?,?,?, ?,?,?, ?,?,?,?, ?,?, ?,?, ?,?, ?,?, 
                         ?,?,?,?, ?,?,?,?,?, ?,?,?,?,?, ?,?, ?,?)
            ''', (
                data.get('codice_asta'),
                data.get('url'),
                data.get('titolo'),
                data.get('tipologia_immobile'),
                data.get('categoria'),
                data.get('genere'),
                data.get('indirizzo'),
                data.get('indirizzo'),  # indirizzo_completo
                data.get('citta'),
                data.get('provincia'),
                data.get('cap'),
                data.get('zona'),
                data.get('latitudine'),
                data.get('longitudine'),
                data.get('piano'),
                data.get('vani'),
                data.get('bagni'),
                data.get('superficie_mq'),
                data.get('disponibilita'),
                data.get('classe_energetica'),
                data.get('codice_lotto'),
                data.get('numero_beni_lotto'),
                data.get('descrizione_lotto'),
                None,  # valore_stima
                data.get('data_vendita'),
                data.get('tipo_vendita'),
                data.get('modalita_vendita'),
                data.get('indirizzo_luogo_vendita'),
                data.get('citta_luogo_vendita'),
                data.get('cap_luogo_vendita'),
                data.get('termine_offerte'),
                data.get('prezzo_base'),
                data.get('prezzo_base_formatted'),
                data.get('offerta_minima'),
                data.get('offerta_minima_formatted'),
                data.get('rialzo_minimo'),
                data.get('rialzo_minimo_formatted'),
                data.get('deposito_cauzionale'),
                None,  # deposito_spese
                data.get('tribunale'),
                data.get('tipo_procedura'),
                data.get('numero_rge'),
                data.get('anno_rge'),
                data.get('delegato_nome'),
                data.get('delegato_cognome'),
                data.get('delegato_telefono'),
                data.get('delegato_email'),
                data.get('delegato_procede_vendita'),
                data.get('custode_nome'),
                data.get('custode_cognome'),
                data.get('custode_telefono'),
                data.get('custode_email'),
                data.get('custode_gestisce_visite'),
                data.get('descrizione_breve'),
                None,  # descrizione_completa
                data.get('data_pubblicazione'),
                json.dumps(data, ensure_ascii=False)
            ))

            codice = data.get('codice_asta')

            # Elimina vecchi allegati/foto/plani/storico
            cursor.execute('DELETE FROM allegati WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM foto WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM planimetrie WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM storico_vendite WHERE codice_asta = ?', (codice,))

            # Salva allegati
            for alleg in allegati:
                cursor.execute('''
                    INSERT INTO allegati (codice_asta, tipo_allegato, nome_file, url_download)
                    VALUES (?, ?, ?, ?)
                ''', (alleg['codice_asta'], alleg['tipo_allegato'], alleg['nome_file'], alleg['url_download']))

            # Salva foto
            for f in foto:
                cursor.execute('''
                    INSERT INTO foto (codice_asta, url_foto, ordine)
                    VALUES (?, ?, ?)
                ''', (f['codice_asta'], f['url_foto'], f['ordine']))

            # Salva planimetrie
            for p in planimetrie:
                cursor.execute('''
                    INSERT INTO planimetrie (codice_asta, url_planimetria, ordine)
                    VALUES (?, ?, ?)
                ''', (p['codice_asta'], p['url_planimetria'], p['ordine']))

            # Salva storico
            for s in storico:
                cursor.execute('''
                    INSERT INTO storico_vendite (codice_asta, data_vendita, prezzo_base, prezzo_base_formatted)
                    VALUES (?, ?, ?, ?)
                ''', (s['codice_asta'], s['data_vendita'], s['prezzo_base'], s['prezzo_base_formatted']))

            conn.commit()
            print(f"✅ Salvato nel DB: {codice}")
            print(f"   • Allegati: {len(allegati)}")
            print(f"   • Foto: {len(foto)}")
            print(f"   • Planimetrie: {len(planimetrie)}")
            print(f"   • Storico: {len(storico)}")

        except Exception as e:
            conn.rollback()
            print(f"❌ Errore DB: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

    def search_by_city(self, city="Roma"):
        """Esegue la ricerca dopo il login"""
        try:
            print(f"🔍 RICERCA IMMOBILI A {city.upper()}")
            print("-" * 60)

            time.sleep(3)

            # Cerca il campo indirizzo
            print(f"\n📍 Cerco il campo 'Indirizzo'...")
            indirizzo_field = None
            indirizzo_selectors = [
                "input[name*='indirizzo']",
                "input[placeholder*='indirizzo']",
                "input[placeholder*='Indirizzo']",
                "input[name*='address']",
                "input[name*='location']",
                "input[name*='city']",
                "input[id*='search']",
                "input[type='search']",
                "input[type='text']"
            ]

            for selector in indirizzo_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            placeholder = elem.get_attribute('placeholder') or ''
                            name = elem.get_attribute('name') or ''
                            if any(keyword in (placeholder + name).lower() for keyword in
                                   ['indirizzo', 'città', 'dove', 'location', 'address', 'cerca']):
                                indirizzo_field = elem
                                print(f"✓ Campo trovato: {selector}")
                                break
                    if indirizzo_field:
                        break
                except:
                    continue

            if not indirizzo_field:
                print("❌ Campo indirizzo non trovato!")
                return None, []

            # Inserisci la città
            print(f"\n⌨️  Inserisco '{city}'...")
            indirizzo_field.clear()
            time.sleep(0.5)
            indirizzo_field.send_keys(city)
            time.sleep(2)

            # Cerca il pulsante Cerca
            print(f"\n🔘 Cerco il pulsante 'Cerca'...")
            cerca_selectors = [
                "//button[contains(text(), 'Cerca')]",
                "//button[contains(text(), 'CERCA')]",
                "//input[@value='Cerca']",
                "//button[@type='submit']",
                "button[type='submit']",
            ]

            cerca_button = None
            for selector in cerca_selectors:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for elem in elements:
                        if elem.is_displayed():
                            cerca_button = elem
                            print(f"✓ Pulsante trovato: {selector}")
                            break
                    if cerca_button:
                        break
                except:
                    continue

            # Clicca o premi INVIO
            if cerca_button:
                print("🖱️  Clicco su 'Cerca'...")
                try:
                    cerca_button.click()
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", cerca_button)
                    except:
                        indirizzo_field.send_keys(Keys.RETURN)
            else:
                print("⚠️ Pulsante 'Cerca' non trovato, premo INVIO...")
                indirizzo_field.send_keys(Keys.RETURN)

            # Attendi risultati
            print(f"\n⏳ Attendo caricamento risultati...")
            time.sleep(5)

            # Cerca i link con /vendita-
            print(f"\n🔗 Cerco link con '/vendita-'...")
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            vendita_links = soup.find_all('a', href=re.compile(r'/vendita-', re.I))

            unique_urls = set()
            for link in vendita_links:
                href = link.get('href', '')
                if href and '/vendita-' in href:
                    if not href.startswith('http'):
                        href = self.base_url + href
                    if href.startswith('https://www.astegiudiziarie.it/vendita-'):
                        unique_urls.add(href)

            print(f"✅ {len(unique_urls)} URL unici trovati\n")
            return self.driver.page_source, list(unique_urls)

        except Exception as e:
            print(f"❌ Errore durante la ricerca: {e}")
            import traceback
            traceback.print_exc()
            return None, []

    def scroll_and_load_more(self, main_window, all_urls):
        """Esegue scroll sulla pagina principale e carica nuovi immobili"""
        try:
            self.driver.switch_to.window(main_window)
            print(f"\n📜 Eseguo scroll per caricare più risultati...")

            initial_count = len(all_urls)

            # Scroll verso il basso
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Scroll graduale
            for i in range(3):
                scroll_position = (i + 1) * (self.driver.execute_script("return document.body.scrollHeight") // 4)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                time.sleep(1)

            time.sleep(2)

            # Cerca nuovi link
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            vendita_links = soup.find_all('a', href=re.compile(r'/vendita-', re.I))

            new_urls = set()
            for link in vendita_links:
                href = link.get('href', '')
                if href and '/vendita-' in href:
                    if not href.startswith('http'):
                        href = self.base_url + href
                    if href.startswith('https://www.astegiudiziarie.it/vendita-'):
                        new_urls.add(href)

            before_count = len(all_urls)
            all_urls.update(new_urls)
            after_count = len(all_urls)

            new_found = after_count - before_count
            if new_found > 0:
                print(f"   ✅ Trovati {new_found} nuovi immobili (Totale: {after_count})")
            else:
                print(f"   ℹ️  Nessun nuovo immobile trovato (Totale: {after_count})")

            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)

        except Exception as e:
            print(f"⚠️ Errore durante lo scroll: {e}")

    def check_immobile_exists(self, url):
        """Controlla se un immobile è già presente nel database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT codice_asta, titolo, data_inserimento FROM aste WHERE url = ?', (url,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {'exists': True, 'codice': result[0], 'titolo': result[1], 'data_inserimento': result[2]}
        return {'exists': False}

    def scrape_all(self, city="Roma", max_aste=None):
        """Scraping completo con scorrimento automatico delle pagine"""
        print(f"\n{'=' * 60}")
        print(f"SCRAPER ASTEGIUDIZIARIE.IT V2")
        print(f"Città: {city}")
        if max_aste:
            print(f"Limite: {max_aste} aste")
        print(f"{'=' * 60}\n")

        if not self.email or not self.password:
            print("❌ Credenziali mancanti! Crea file .env con ASTE_EMAIL e ASTE_PASSWORD")
            return

        if not self.init_selenium():
            return

        try:
            if not self.login():
                return

            # Esegui ricerca
            result = self.search_by_city(city)

            if not result:
                print("❌ Ricerca fallita!")
                return

            html, vendita_urls = result

            if not vendita_urls:
                print("❌ Nessun link '/vendita-' trovato!")
                return

            print(f"\n{'=' * 60}")
            print(f"INIZIO DOWNLOAD DETTAGLI CON SCROLL AUTOMATICO")
            print(f"{'=' * 60}\n")

            # Salva finestra principale
            main_window = self.driver.current_window_handle

            count_new = 0
            count_skipped = 0
            all_urls = set(vendita_urls)

            idx = 0
            while idx < len(list(all_urls)):
                if max_aste and count_new >= max_aste:
                    print(f"\n⚠️ Raggiunto limite di {max_aste} aste")
                    break

                current_urls = list(all_urls)
                url = current_urls[idx]
                idx += 1

                print(f"\n{'=' * 60}")
                print(f"Immobile {idx}/{len(current_urls)}")
                print(f"🔗 URL: {url}")
                print(f"{'=' * 60}")

                # Controlla se esiste già
                check = self.check_immobile_exists(url)

                if check['exists']:
                    print(f"⏭️  SALTATO - Già presente nel DB")
                    print(f"   Codice: {check['codice']}")
                    print(f"   Titolo: {check['titolo']}")
                    count_skipped += 1

                    # Scroll per caricare più risultati
                    self.scroll_and_load_more(main_window, all_urls)
                    continue

                print(f"🆕 NUOVO - Scarico dettagli completi...")

                # Apri nuova finestra
                self.driver.execute_script("window.open('');")
                time.sleep(0.5)

                windows = self.driver.window_handles
                detail_window = windows[-1]
                self.driver.switch_to.window(detail_window)

                try:
                    self.driver.get(url)
                    time.sleep(3)

                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                    # Parse completo
                    immobile = self.parse_detail_page_v2(soup, url)

                    # Estrai allegati, foto, planimetrie, storico
                    allegati = self.extract_allegati(soup, immobile['codice_asta'])
                    foto = self.extract_foto(soup, immobile['codice_asta'])
                    planimetrie = self.extract_planimetrie(soup, immobile['codice_asta'])
                    storico = self.extract_storico_vendite(soup, immobile['codice_asta'])

                    # Salva tutto
                    self.save_to_db(immobile, allegati, foto, planimetrie, storico)
                    count_new += 1

                    print(f"\n✅ Salvato con successo!")
                    print(f"   📌 Titolo: {immobile.get('titolo', 'N/A')}")
                    print(f"   📍 Città: {immobile.get('citta', 'N/A')}")
                    print(f"   💰 Prezzo: {immobile.get('prezzo_base_formatted', 'N/A')}")

                except Exception as e:
                    print(f"❌ Errore durante il download: {e}")
                    import traceback
                    traceback.print_exc()

                finally:
                    # Chiudi finestra dettagli
                    try:
                        self.driver.close()
                    except:
                        pass

                    # Torna alla finestra principale
                    try:
                        self.driver.switch_to.window(main_window)
                    except:
                        pass

                    # Scroll per caricare più risultati
                    self.scroll_and_load_more(main_window, all_urls)

            print(f"\n{'=' * 60}")
            print(f"COMPLETATO!")
            print(f"{'=' * 60}")
            print(f"📊 Statistiche:")
            print(f"   • Totale URL trovati: {len(all_urls)}")
            print(f"   • Nuovi scaricati: {count_new}")
            print(f"   • Già presenti: {count_skipped}")
            print(f"💾 Database: {self.db_name}")
            print(f"{'=' * 60}\n")

        finally:
            if self.driver:
                print("🔚 Chiudo il browser...")
                self.driver.quit()


def main():
    # Reset database
    db_file = 'aste_immobiliari_v2.db'
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"🗑️  Database esistente rimosso\n")

    scraper = AsteGiudiziarieScraperV2()

    # Parametri di scraping
    city = "Roma"
    max_aste = 50  # Limita a 50 per test, rimuovi per scaricare tutto

    scraper.scrape_all(city, max_aste=max_aste)


if __name__ == "__main__":
    main()