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
        load_dotenv()
        self.email = os.getenv('ASTE_EMAIL')
        self.password = os.getenv('ASTE_PASSWORD')
        self.setup_database()

    def setup_database(self):
        """Crea database con struttura completa"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aste (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice_asta TEXT UNIQUE NOT NULL,
                url TEXT UNIQUE,
                titolo TEXT,
                tipologia_immobile TEXT,
                categoria TEXT,
                genere TEXT,
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
                piano TEXT,
                vani REAL,
                bagni INTEGER,
                superficie_mq REAL,
                disponibilita TEXT,
                classe_energetica TEXT,
                stato_immobile TEXT,
                codice_lotto TEXT,
                numero_beni_lotto INTEGER,
                descrizione_lotto TEXT,
                valore_stima TEXT,
                data_vendita DATETIME,
                ora_vendita TEXT,
                tipo_vendita TEXT,
                modalita_vendita TEXT,
                luogo_vendita TEXT,
                indirizzo_luogo_vendita TEXT,
                citta_luogo_vendita TEXT,
                cap_luogo_vendita TEXT,
                termine_offerte DATETIME,
                prezzo_base REAL,
                prezzo_base_formatted TEXT,
                offerta_minima REAL,
                offerta_minima_formatted TEXT,
                rialzo_minimo REAL,
                rialzo_minimo_formatted TEXT,
                deposito_cauzionale TEXT,
                deposito_spese TEXT,
                tribunale TEXT,
                tipo_procedura TEXT,
                numero_rge TEXT,
                anno_rge TEXT,
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
                descrizione_breve TEXT,
                descrizione_completa TEXT,
                data_pubblicazione DATE,
                data_inserimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                json_completo TEXT
            )
        ''')

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

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS foto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice_asta TEXT NOT NULL,
                url_foto TEXT,
                ordine INTEGER,
                FOREIGN KEY (codice_asta) REFERENCES aste(codice_asta)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS planimetrie (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice_asta TEXT NOT NULL,
                url_planimetria TEXT,
                ordine INTEGER,
                FOREIGN KEY (codice_asta) REFERENCES aste(codice_asta)
            )
        ''')

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

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_codice_asta ON aste(codice_asta)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_citta ON aste(citta)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_vendita ON aste(data_vendita)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_prezzo ON aste(prezzo_base)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tribunale ON aste(tribunale)')

        conn.commit()
        conn.close()
        print(f"✅ Database '{self.db_name}' inizializzato\n")

    def init_selenium(self):
        """Inizializza Selenium"""
        try:
            print("🔧 Inizializzo il browser...")
            options = Options()
            # RIMOSSO --headless per vedere il browser
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✅ Browser avviato e VISIBILE\n")
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

            accedi_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accedi')]")
            accedi_btn.click()
            time.sleep(2)

            try:
                privati_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Privati')]")
                privati_btn.click()
                time.sleep(2)
            except:
                pass

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

    def extract_codice_from_url(self, url):
        """Estrae il codice asta dall'URL prima di aprire la pagina"""
        # Pattern: https://www.astegiudiziarie.it/vendita-CODICE-descrizione
        match = re.search(r'/vendita-([A-Z0-9]+)', url, re.I)
        if match:
            return match.group(1)
        return None

    def check_codice_exists(self, codice_asta):
        """Controlla se un codice asta esiste già nel database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT codice_asta, titolo, citta, data_inserimento FROM aste WHERE codice_asta = ?',
                       (codice_asta,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'exists': True,
                'codice': result[0],
                'titolo': result[1],
                'citta': result[2],
                'data_inserimento': result[3]
            }
        return {'exists': False}

    def check_immobile_exists(self, url):
        """Controlla se immobile esiste già (fallback)"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT codice_asta, titolo, data_inserimento FROM aste WHERE url = ?', (url,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {'exists': True, 'codice': result[0], 'titolo': result[1], 'data_inserimento': result[2]}
        return {'exists': False}

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

    def extract_price_advanced(self, soup, label_text):
        """Estrazione ROBUSTA dei prezzi"""
        page_text = soup.get_text()

        # Metodo 1: attributi data-pvp
        attr_mapping = {
            'Prezzo base': 'data-pvp-datiVendita-prezzoValoreBase',
            'Offerta minima': 'data-pvp-datiVendita-offertaMinima',
            'Rialzo minimo': 'data-pvp-datiVendita-rialzoMinimo'
        }

        if label_text in attr_mapping:
            elems = soup.find_all(attrs={attr_mapping[label_text]: True})
            for elem in elems:
                value = elem.get(attr_mapping[label_text], '').strip()
                if value:
                    return value

        # Metodo 2: Regex nel testo
        patterns = [
            rf'{re.escape(label_text)}[:\s]*€\s*([\d.,]+)',
            rf'{label_text}.*?€\s*([\d.,]+)',
            rf'€\s*([\d.,]+).*?{label_text}',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                return f"€ {match.group(1)}"

        return None

    def extract_number_advanced(self, soup, label_text, unit=''):
        """Estrazione ROBUSTA di numeri"""
        page_text = soup.get_text()

        patterns = [
            rf'{re.escape(label_text)}[\s:]+(\d+(?:[.,]\d+)?)\s*{unit}',
            rf'{re.escape(label_text)}[\s:]+(\d+(?:[.,]\d+)?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                return match.group(1).replace(',', '.')

        return None

    def clean_price(self, price_text):
        """Converte prezzo in float"""
        if not price_text:
            return None
        clean = re.sub(r'[€\s]', '', str(price_text))
        clean = clean.replace('.', '').replace(',', '.')
        try:
            return float(clean)
        except:
            return None

    def parse_detail_page_v2(self, soup, url):
        """Parsing completo della pagina dettaglio"""
        data = {
            'url': url,
            'codice_asta': None,
            'titolo': None,
            'tipologia_immobile': None,
            'indirizzo': None,
            'citta': None,
            'provincia': None,
            'cap': None,
            'latitudine': None,
            'longitudine': None,
            'vani': None,
            'bagni': None,
            'superficie_mq': None,
            'piano': None,
            'data_vendita': None,
            'tipo_vendita': None,
            'prezzo_base_formatted': None,
            'prezzo_base': None,
            'offerta_minima_formatted': None,
            'offerta_minima': None,
            'rialzo_minimo_formatted': None,
            'rialzo_minimo': None,
            'tribunale': None,
            'numero_rge': None,
            'anno_rge': None,
            'delegato_cognome': None,
            'delegato_nome': None,
            'delegato_telefono': None,
            'delegato_email': None,
            'custode_cognome': None,
            'custode_nome': None,
            'custode_telefono': None,
            'custode_email': None,
            'descrizione_breve': None,
        }

        page_text = soup.get_text()

        # === CODICE ASTA ===
        codice_patterns = [
            r'Codice asta[:\s]+([A-Z0-9]+)',
            r'Codice[:\s]+([A-Z0-9]+)',
            r'COD\.\s+([A-Z0-9]+)'
        ]
        for pattern in codice_patterns:
            match = re.search(pattern, page_text, re.I)
            if match:
                data['codice_asta'] = match.group(1)
                break

        if not data['codice_asta']:
            badge = soup.find('span', class_='badge', string=re.compile(r'[A-Z0-9]{7,}'))
            if badge:
                data['codice_asta'] = badge.get_text(strip=True)

        # Fallback: estrai dall'URL
        if not data['codice_asta']:
            data['codice_asta'] = self.extract_codice_from_url(url)

        data['codice_asta'] = data['codice_asta'] or 'N/A'

        # === INFO GENERALI ===
        h1 = soup.find('h1')
        data['titolo'] = h1.get_text(strip=True) if h1 else None

        data['tipologia_immobile'] = self.extract_text(soup, '[data-pvp-bene-categoria]',
                                                       attribute='data-pvp-bene-categoria')

        # === LOCALIZZAZIONE ===
        data['indirizzo'] = self.extract_text(soup, '[data-pvp-lotto-indirizzo]', attribute='data-pvp-lotto-indirizzo')
        if not data['indirizzo']:
            for tag in soup.find_all(['h2', 'h3', 'strong', 'span']):
                text = tag.get_text(strip=True)
                if re.match(r'(?:Via|Viale|Piazza|Corso)\s+', text, re.I):
                    if 5 < len(text) < 150:
                        data['indirizzo'] = text
                        break

        data['citta'] = self.extract_text(soup, '[data-pvp-lotto-citta]', attribute='data-pvp-lotto-citta')
        if not data['citta']:
            citta_match = re.search(r'Comune[:\s]+([A-Za-zÀ-ù\s]+?)(?:\(|,|-|\n|$)', page_text, re.I)
            if citta_match:
                data['citta'] = citta_match.group(1).strip()

        data['cap'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-capZipCode]',
                                        attribute='data-pvp-bene-ubicazione-capZipCode')
        if not data['cap']:
            cap_match = re.search(r'\b(\d{5})\b', page_text)
            if cap_match:
                data['cap'] = cap_match.group(1)

        data['provincia'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-provincia]',
                                              attribute='data-pvp-bene-ubicazione-provincia')

        # GPS
        lat_input = soup.find('input', id='lat')
        lng_input = soup.find('input', id='lng')
        if lat_input and lat_input.get('value'):
            try:
                data['latitudine'] = float(lat_input['value'])
            except:
                pass
        if lng_input and lng_input.get('value'):
            try:
                data['longitudine'] = float(lng_input['value'])
            except:
                pass

        # === CARATTERISTICHE ===
        vani_str = self.extract_number_advanced(soup, 'Vani')
        if vani_str:
            try:
                data['vani'] = float(vani_str)
            except:
                pass

        bagni_str = self.extract_number_advanced(soup, 'Bagni')
        if bagni_str:
            try:
                data['bagni'] = int(float(bagni_str))
            except:
                pass

        superficie_str = self.extract_number_advanced(soup, 'Metri quadri', 'mq')
        if superficie_str:
            try:
                data['superficie_mq'] = float(superficie_str)
            except:
                pass

        # === PREZZI ===
        prezzo_base_text = self.extract_price_advanced(soup, 'Prezzo base')
        data['prezzo_base_formatted'] = prezzo_base_text
        data['prezzo_base'] = self.clean_price(prezzo_base_text)

        offerta_min_text = self.extract_price_advanced(soup, 'Offerta minima')
        data['offerta_minima_formatted'] = offerta_min_text
        data['offerta_minima'] = self.clean_price(offerta_min_text)

        rialzo_text = self.extract_price_advanced(soup, 'Rialzo minimo')
        data['rialzo_minimo_formatted'] = rialzo_text
        data['rialzo_minimo'] = self.clean_price(rialzo_text)

        # === DATA VENDITA ===
        data['data_vendita'] = self.extract_text(soup, '[data-pvp-datiVendita-dataOraVendita]',
                                                 attribute='data-pvp-datiVendita-dataOraVendita')

        # === TRIBUNALE ===
        tribunale_match = re.search(r'Tribunale[:\s]+([^\n]+)', page_text, re.I)
        if tribunale_match:
            data['tribunale'] = tribunale_match.group(1).strip()[:100]

        return data

    def extract_allegati(self, soup, codice_asta):
        """Estrae allegati"""
        allegati = []
        links = soup.select('.list-group-modulistica a[href*="/allegato/"]')
        for link in links:
            allegati.append({
                'codice_asta': codice_asta,
                'tipo_allegato': link.get_text(strip=True),
                'url_download': self.base_url + link['href'] if not link['href'].startswith('http') else link['href'],
                'nome_file': link['href'].split('/')[-2] if '/' in link['href'] else ''
            })
        return allegati

    def extract_foto(self, soup, codice_asta):
        """Estrae foto"""
        foto_list = []
        foto_links = soup.select('a[data-fslightbox="galleryFoto"]')
        for idx, link in enumerate(foto_links, 1):
            foto_list.append({
                'codice_asta': codice_asta,
                'url_foto': self.base_url + link['href'] if not link['href'].startswith('http') else link['href'],
                'ordine': idx
            })
        return foto_list

    def extract_planimetrie(self, soup, codice_asta):
        """Estrae planimetrie"""
        plani_list = []
        plani_links = soup.select('a[data-fslightbox="galleryPlani"]')
        for idx, link in enumerate(plani_links, 1):
            plani_list.append({
                'codice_asta': codice_asta,
                'url_planimetria': self.base_url + link['href'] if not link['href'].startswith('http') else link[
                    'href'],
                'ordine': idx
            })
        return plani_list

    def extract_storico_vendite(self, soup, codice_asta):
        """Estrae storico vendite"""
        storico = []
        rows = soup.select('.table tbody tr')
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 2:
                storico.append({
                    'codice_asta': codice_asta,
                    'data_vendita': cells[0].get_text(strip=True),
                    'prezzo_base_formatted': cells[1].get_text(strip=True),
                    'prezzo_base': self.clean_price(cells[1].get_text(strip=True))
                })
        return storico

    def save_to_db(self, data, allegati, foto, planimetrie, storico):
        """Salva nel database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO aste (
                    codice_asta, url, titolo, tipologia_immobile,
                    indirizzo, citta, provincia, cap,
                    latitudine, longitudine,
                    vani, bagni, superficie_mq, piano,
                    data_vendita, tipo_vendita,
                    prezzo_base, prezzo_base_formatted, 
                    offerta_minima, offerta_minima_formatted,
                    rialzo_minimo, rialzo_minimo_formatted,
                    tribunale, numero_rge, anno_rge,
                    delegato_nome, delegato_cognome, delegato_telefono, delegato_email,
                    custode_nome, custode_cognome, custode_telefono, custode_email,
                    descrizione_breve, json_completo
                ) VALUES (?,?,?,?, ?,?,?,?, ?,?, ?,?,?,?, ?,?, ?,?, ?,?, ?,?, ?,?,?, ?,?,?,?, ?,?,?,?, ?,?)
            ''', (
                data.get('codice_asta'), data.get('url'), data.get('titolo'), data.get('tipologia_immobile'),
                data.get('indirizzo'), data.get('citta'), data.get('provincia'), data.get('cap'),
                data.get('latitudine'), data.get('longitudine'),
                data.get('vani'), data.get('bagni'), data.get('superficie_mq'), data.get('piano'),
                data.get('data_vendita'), data.get('tipo_vendita'),
                data.get('prezzo_base'), data.get('prezzo_base_formatted'),
                data.get('offerta_minima'), data.get('offerta_minima_formatted'),
                data.get('rialzo_minimo'), data.get('rialzo_minimo_formatted'),
                data.get('tribunale'), data.get('numero_rge'), data.get('anno_rge'),
                data.get('delegato_nome'), data.get('delegato_cognome'), data.get('delegato_telefono'),
                data.get('delegato_email'),
                data.get('custode_nome'), data.get('custode_cognome'), data.get('custode_telefono'),
                data.get('custode_email'),
                data.get('descrizione_breve'), json.dumps(data, ensure_ascii=False)
            ))

            codice = data.get('codice_asta')

            cursor.execute('DELETE FROM allegati WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM foto WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM planimetrie WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM storico_vendite WHERE codice_asta = ?', (codice,))

            for alleg in allegati:
                cursor.execute(
                    'INSERT INTO allegati (codice_asta, tipo_allegato, nome_file, url_download) VALUES (?,?,?,?)',
                    (alleg['codice_asta'], alleg['tipo_allegato'], alleg['nome_file'], alleg['url_download']))

            for f in foto:
                cursor.execute('INSERT INTO foto (codice_asta, url_foto, ordine) VALUES (?,?,?)',
                               (f['codice_asta'], f['url_foto'], f['ordine']))

            for p in planimetrie:
                cursor.execute('INSERT INTO planimetrie (codice_asta, url_planimetria, ordine) VALUES (?,?,?)',
                               (p['codice_asta'], p['url_planimetria'], p['ordine']))

            for s in storico:
                cursor.execute(
                    'INSERT INTO storico_vendite (codice_asta, data_vendita, prezzo_base, prezzo_base_formatted) VALUES (?,?,?,?)',
                    (s['codice_asta'], s['data_vendita'], s['prezzo_base'], s['prezzo_base_formatted']))

            conn.commit()
            print(f"✅ Salvato: {codice}")

        except Exception as e:
            conn.rollback()
            print(f"❌ Errore DB: {e}")
        finally:
            conn.close()

    def search_by_city(self, city="Roma"):
        """Esegue la ricerca"""
        try:
            print(f"🔍 RICERCA: {city.upper()}\n")
            time.sleep(3)

            indirizzo_field = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder*='indirizzo']")
            indirizzo_field.clear()
            indirizzo_field.send_keys(city)
            time.sleep(2)

            cerca_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Cerca')]")
            cerca_button.click()
            time.sleep(5)

            # ⚡ PGDOWN 50 VOLTE PER CARICARE TUTTI GLI IMMOBILI
            print(f"⌨️  Premo PgDown 50 volte per caricare tutti gli immobili...")
            print(f"👁️  GUARDA IL BROWSER!\n")

            from selenium.webdriver.common.keys import Keys

            # Trova l'elemento body per inviare i tasti
            body = self.driver.find_element(By.TAG_NAME, 'body')

            for i in range(1, 500):
                # Premi PgDown
                body.send_keys(Keys.PAGE_DOWN)

                # Mostra progresso ogni 10 pressioni
                if i % 10 == 0:
                    current_pos = self.driver.execute_script("return window.pageYOffset")
                    page_height = self.driver.execute_script("return document.body.scrollHeight")
                    progress = (current_pos / page_height * 100) if page_height > 0 else 0
                    print(f"   ⌨️  PgDown: {i}/50 | Posizione: {current_pos}px | Progresso: {progress:.1f}%")

                # Pausa per permettere il caricamento
                time.sleep(0.2)

            print(f"\n✅ Completate 50 pressioni di PgDown!")

            # Aspetta un attimo per ultimi caricamenti
            print(f"⏳ Attendo 3 secondi per caricamenti finali...")
            time.sleep(3)

            final_height = self.driver.execute_script("return document.body.scrollHeight")
            final_pos = self.driver.execute_script("return window.pageYOffset")
            print(f"📊 Altezza pagina: {final_height}px | Posizione finale: {final_pos}px")
            print(f"📊 Estraggo tutti i link...\n")

            # Estrai tutti i link dopo lo scroll
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

            print(f"✅ Trovati {len(unique_urls)} URL unici\n")
            return list(unique_urls)

        except Exception as e:
            print(f"❌ Errore ricerca: {e}")
            return []

    def scrape_all(self, city="Roma", max_aste=None):
        """Scraping completo con check preventivo del codice"""
        print(f"\n{'=' * 60}")
        print(f"🚀 SCRAPER ASTEGIUDIZIARIE.IT V2 - OTTIMIZZATO")
        print(f"📍 Città: {city}")
        if max_aste:
            print(f"📊 Limite: {max_aste} aste")
        print(f"{'=' * 60}\n")

        if not self.init_selenium():
            return

        try:
            if not self.login():
                return

            vendita_urls = self.search_by_city(city)

            if not vendita_urls:
                print("❌ Nessun risultato trovato!")
                return

            print(f"{'=' * 60}")
            print(f"⚡ INIZIO DOWNLOAD CON CHECK PREVENTIVO")
            print(f"{'=' * 60}\n")

            count_new = 0
            count_skipped = 0

            for idx, url in enumerate(vendita_urls, 1):
                if max_aste and count_new >= max_aste:
                    print(f"\n✅ Raggiunto limite di {max_aste} aste")
                    break

                print(f"\n{'─' * 60}")
                print(f"📋 Asta {idx}/{len(vendita_urls)}")
                print(f"🔗 {url}")

                # ⚡ STEP 1: ESTRAI CODICE DALL'URL
                codice_url = self.extract_codice_from_url(url)

                if codice_url:
                    print(f"🔑 Codice estratto dall'URL: {codice_url}")

                    # ⚡ STEP 2: CHECK SE ESISTE GIÀ
                    check = self.check_codice_exists(codice_url)

                    if check['exists']:
                        print(f"⏭️  SALTATO - Già presente!")
                        print(f"   📌 Titolo: {check['titolo']}")
                        print(f"   📍 Città: {check['citta']}")
                        print(f"   📅 Inserito: {check['data_inserimento']}")
                        count_skipped += 1
                        continue

                # ⚡ STEP 3: SCARICA SOLO SE NUOVO
                print(f"🆕 NUOVO - Scarico dettagli...")

                try:
                    self.driver.get(url)
                    time.sleep(3)

                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                    immobile = self.parse_detail_page_v2(soup, url)

                    # Double-check con codice estratto dalla pagina
                    if immobile['codice_asta'] != 'N/A':
                        final_check = self.check_codice_exists(immobile['codice_asta'])
                        if final_check['exists']:
                            print(f"⚠️  Codice {immobile['codice_asta']} già presente - SALTO")
                            count_skipped += 1
                            continue

                    allegati = self.extract_allegati(soup, immobile['codice_asta'])
                    foto = self.extract_foto(soup, immobile['codice_asta'])
                    planimetrie = self.extract_planimetrie(soup, immobile['codice_asta'])
                    storico = self.extract_storico_vendite(soup, immobile['codice_asta'])

                    self.save_to_db(immobile, allegati, foto, planimetrie, storico)
                    count_new += 1

                    print(f"✅ SALVATO!")
                    print(f"   📌 {immobile.get('titolo', 'N/A')}")
                    print(f"   📍 {immobile.get('citta', 'N/A')}")
                    print(f"   💰 {immobile.get('prezzo_base_formatted', 'N/A')}")

                except Exception as e:
                    print(f"❌ Errore: {e}")

            print(f"\n{'=' * 60}")
            print(f"🏁 COMPLETATO!")
            print(f"{'=' * 60}")
            print(f"📊 Statistiche:")
            print(f"   🆕 Nuovi scaricati: {count_new}")
            print(f"   ⏭️  Già presenti: {count_skipped}")
            print(f"   📈 Totale processati: {count_new + count_skipped}")
            print(f"   💾 Database: {self.db_name}")
            print(f"{'=' * 60}\n")

        finally:
            if self.driver:
                print("🔚 Chiudo il browser...")
                self.driver.quit()


def main():
    """Esempio di utilizzo"""
    scraper = AsteGiudiziarieScraperV2()

    # Scraping di Roma, max 50 aste
    scraper.scrape_all("Roma", max_aste=50)

    # Per altre città:
    # scraper.scrape_all("Milano", max_aste=30)
    # scraper.scrape_all("Napoli", max_aste=20)


if __name__ == "__main__":
    main()