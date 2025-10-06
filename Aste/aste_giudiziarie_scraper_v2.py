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
        print(f"Database '{self.db_name}' inizializzato\n")

    def init_selenium(self):
        """Inizializza Selenium"""
        try:
            print("Inizializzo il browser...")
            options = Options()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("Browser avviato\n")
            return True
        except Exception as e:
            print(f"Errore: {e}")
            return False

    def login(self):
        """Login al sito"""
        try:
            print("Login in corso...")
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
            print("Login completato\n")
            return True

        except Exception as e:
            print(f"Errore login: {e}")
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

    def extract_price_advanced(self, soup, label_text):
        """Estrazione ROBUSTA dei prezzi con debug"""
        page_text = soup.get_text()

        print(f"  === Cerco '{label_text}' ===")

        # Metodo 1: attributi data-pvp
        attr_mapping = {
            'Prezzo base': 'data-pvp-datiVendita-prezzoValoreBase',
            'Offerta minima': 'data-pvp-datiVendita-offertaMinima',
            'Rialzo minimo': 'data-pvp-datiVendita-rialzoMinimo'
        }

        if label_text in attr_mapping:
            elems = soup.find_all(attrs={attr_mapping[label_text]: True})
            print(f"  [data-pvp] Trovati {len(elems)} elementi")
            for elem in elems:
                value = elem.get(attr_mapping[label_text], '').strip()
                if value:
                    print(f"  [Metodo 1] {label_text}: {value}")
                    return value

        # Metodo 2: Regex ampio nel testo
        patterns = [
            rf'{re.escape(label_text)}[:\s]*€\s*([\d.,]+)',
            rf'{label_text}.*?€\s*([\d.,]+)',
            rf'€\s*([\d.,]+).*?{label_text}',
            rf'{re.escape(label_text)}[:\s]*€?\s*([\d]+\.[\d]+,[\d]+)',
            rf'{re.escape(label_text)}[:\s]*€?\s*([\d]+,[\d]+)',
        ]

        for idx, pattern in enumerate(patterns, 1):
            match = re.search(pattern, page_text, re.I)
            if match:
                value = f"€ {match.group(1)}"
                print(f"  [Regex {idx}] {label_text}: {value}")
                return value

        # Metodo 3: Cerca elementi contenenti label e €
        label_variations = [label_text, label_text.replace(' ', ''), label_text.lower()]
        for variation in label_variations:
            elems = soup.find_all(string=re.compile(variation, re.I))
            for elem in elems[:3]:
                parent = elem.find_parent()
                if parent:
                    full_text = parent.get_text(strip=True)
                    idx = full_text.find(variation)
                    if idx != -1:
                        nearby = full_text[idx:idx + 100]
                        price_match = re.search(r'€\s*([\d.,]+)', nearby)
                        if price_match:
                            value = f"€ {price_match.group(1)}"
                            print(f"  [Nearby] {label_text}: {value}")
                            return value

        print(f"  [NON TROVATO] {label_text}")
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
                value = match.group(1).replace(',', '.')
                print(f"  [Regex] {label_text}: {value}{unit}")
                return value

        label_elem = soup.find(['dt', 'strong', 'label'], string=re.compile(re.escape(label_text), re.I))
        if label_elem:
            dd_elem = label_elem.find_next_sibling('dd')
            if dd_elem:
                text = dd_elem.get_text(strip=True)
                num_match = re.search(r'(\d+(?:[.,]\d+)?)', text)
                if num_match:
                    value = num_match.group(1).replace(',', '.')
                    print(f"  [HTML] {label_text}: {value}{unit}")
                    return value

            parent = label_elem.find_parent()
            if parent:
                text = parent.get_text(strip=True).replace(label_text, '').strip()
                num_match = re.search(r'(\d+(?:[.,]\d+)?)', text)
                if num_match:
                    value = num_match.group(1).replace(',', '.')
                    print(f"  [Parent] {label_text}: {value}{unit}")
                    return value

        print(f"  [NON TROVATO] {label_text}")
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

        print("\nPARSING DETTAGLIATO")
        print("-" * 60)

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

        data['codice_asta'] = data['codice_asta'] or 'N/A'
        print(f"Codice: {data['codice_asta']}")

        # === INFO GENERALI ===
        h1 = soup.find('h1')
        data['titolo'] = h1.get_text(strip=True) if h1 else None

        data['tipologia_immobile'] = self.extract_text(soup, '[data-pvp-bene-categoria]',
                                                       attribute='data-pvp-bene-categoria')
        data['genere'] = self.extract_text(soup, '[data-pvp-lotto-genere]', attribute='data-pvp-lotto-genere')
        data['categoria'] = self.extract_text(soup, '[data-pvp-lotto-categoria]', attribute='data-pvp-lotto-categoria')

        # === LOCALIZZAZIONE - VERSIONE POTENZIATA ===
        print("\nLocalizzazione:")

        # === INDIRIZZO ===
        # Metodo 1: Attributi data-pvp
        data['indirizzo'] = self.extract_text(soup, '[data-pvp-lotto-indirizzo]', attribute='data-pvp-lotto-indirizzo')
        if not data['indirizzo']:
            data['indirizzo'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-indirizzo]',
                                                  attribute='data-pvp-bene-ubicazione-indirizzo')

        # Metodo 2: Cerca in h2/h3/strong con pattern "Via/Viale/Piazza"
        if not data['indirizzo']:
            for tag in soup.find_all(['h2', 'h3', 'h4', 'strong', 'span', 'div']):
                text = tag.get_text(strip=True)
                if re.match(r'(?:Via|Viale|Piazza|Corso|Contrada|Località|Loc\.|Lungomare|Strada)\s+', text, re.I):
                    if 5 < len(text) < 150:
                        data['indirizzo'] = text
                        print(f"  [Tag HTML] Indirizzo: {data['indirizzo']}")
                        break

        # Metodo 3: Regex nel testo completo
        if not data['indirizzo']:
            indirizzo_patterns = [
                r'(?:Via|Viale|Piazza|Corso|Contrada|Località|Loc\.|Frazione|Fraz\.|Lungomare|Strada)\s+[A-Za-zÀ-ù\s\d\',.-]{5,80}(?:\s+\d+)?',
                r'Indirizzo[:\s]+([^,\n]{5,100})',
                r'Ubicazione[:\s]+([^,\n]{5,100})',
            ]
            for pattern in indirizzo_patterns:
                match = re.search(pattern, page_text, re.I)
                if match:
                    addr = match.group(1) if match.groups() else match.group(0)
                    data['indirizzo'] = addr.strip()
                    print(f"  [Regex] Indirizzo: {data['indirizzo']}")
                    break

        if data['indirizzo']:
            print(f"  ✓ Indirizzo: {data['indirizzo']}")
        else:
            print(f"  ✗ Indirizzo NON TROVATO")

        # === CITTÀ ===
        # Metodo 1: Attributi data-pvp
        data['citta'] = self.extract_text(soup, '[data-pvp-lotto-citta]', attribute='data-pvp-lotto-citta')
        if not data['citta']:
            data['citta'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-citta]',
                                              attribute='data-pvp-bene-ubicazione-citta')

        # Metodo 2: Cerca "Comune:" o "Città:" nel testo
        if not data['citta']:
            citta_patterns = [
                r'Comune[:\s]+([A-Za-zÀ-ù\s]+?)(?:\(|,|-|\n|$)',
                r'Città[:\s]+([A-Za-zÀ-ù\s]+?)(?:\(|,|-|\n|$)',
                r'Località[:\s]+([A-Za-zÀ-ù\s]+?)(?:\(|,|-|\n|$)',
            ]
            for pattern in citta_patterns:
                match = re.search(pattern, page_text, re.I)
                if match:
                    citta = match.group(1).strip()
                    # Pulisci parole comuni che non sono città
                    if citta and len(citta) > 2 and citta.lower() not in ['di', 'del', 'della', 'dei']:
                        data['citta'] = citta
                        print(f"  [Regex] Città: {data['citta']}")
                        break

        # Metodo 3: Cerca nei tag con classi comuni
        if not data['citta']:
            for elem in soup.find_all(['span', 'div', 'p'], class_=re.compile('city|citta|comune|locality', re.I)):
                text = elem.get_text(strip=True)
                # Verifica che sia un nome plausibile di città (2-50 caratteri, solo lettere e spazi)
                if text and 2 < len(text) < 50 and re.match(r'^[A-Za-zÀ-ù\s\'-]+$', text):
                    data['citta'] = text
                    print(f"  [HTML class] Città: {data['citta']}")
                    break

        # Metodo 4: Estrai dalla URL (esempio: ...roma-via-...)
        if not data['citta']:
            url_match = re.search(r'/([a-z-]+)-(?:via|viale|piazza|corso)', url, re.I)
            if url_match:
                citta_url = url_match.group(1).replace('-', ' ').title()
                data['citta'] = citta_url
                print(f"  [URL] Città: {data['citta']}")

        if data['citta']:
            print(f"  ✓ Città: {data['citta']}")
        else:
            print(f"  ✗ Città NON TROVATA")

        # === CAP ===
        data['cap'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-capZipCode]',
                                        attribute='data-pvp-bene-ubicazione-capZipCode')

        if not data['cap']:
            # Cerca 5 cifre consecutive (CAP italiano)
            cap_matches = re.findall(r'\b(\d{5})\b', page_text)
            # Prendi il primo CAP valido (00000-99999)
            for cap in cap_matches:
                if '00000' <= cap <= '99999':
                    data['cap'] = cap
                    print(f"  [Regex] CAP: {data['cap']}")
                    break

        # === PROVINCIA ===
        data['provincia'] = self.extract_text(soup, '[data-pvp-bene-ubicazione-provincia]',
                                              attribute='data-pvp-bene-ubicazione-provincia')

        # Fallback: cerca sigla tra parentesi dopo città o CAP
        if not data['provincia']:
            prov_patterns = [
                r'\(([A-Z]{2})\)',  # (RM), (MI), ecc.
                r'Provincia[:\s]+([A-Z]{2})',
            ]
            for pattern in prov_patterns:
                match = re.search(pattern, page_text)
                if match:
                    data['provincia'] = match.group(1)
                    print(f"  [Regex] Provincia: {data['provincia']}")
                    break

        # Fallback provincia: cerca sigla tra parentesi dopo città
        if not data['provincia'] and data['citta']:
            prov_match = re.search(rf"{re.escape(data['citta'])}\s*\(([A-Z]{{2}})\)", page_text)
            if prov_match:
                data['provincia'] = prov_match.group(1)
                print(f"  [Regex] Provincia: {data['provincia']}")

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

        # === DATI LOTTO ===
        data['codice_lotto'] = self.extract_text(soup, '[data-pvp-lotto-codice]', attribute='data-pvp-lotto-codice')

        desc_elem = soup.select_one('#collapseLotto .accordion-body > p')
        if desc_elem:
            data['descrizione_lotto'] = desc_elem.get_text(strip=True)

        num_beni_match = re.search(r'Numero beni[:\s]+(\d+)', page_text, re.I)
        if num_beni_match:
            try:
                data['numero_beni_lotto'] = int(num_beni_match.group(1))
            except:
                pass

        # === CARATTERISTICHE IMMOBILE ===
        print("\nCaratteristiche immobile:")

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
        if not superficie_str:
            superficie_str = self.extract_number_advanced(soup, 'Superficie', 'mq')
        if superficie_str:
            try:
                data['superficie_mq'] = float(superficie_str)
            except:
                pass

        piano_match = re.search(r'Piano[:\s]+([^\n]+)', page_text, re.I)
        if piano_match:
            data['piano'] = piano_match.group(1).strip()[:50]

        # === DATI VENDITA ===
        data_vendita_elem = soup.find('[data-pvp-datiVendita-dataOraVendita]')
        if data_vendita_elem:
            data['data_vendita'] = data_vendita_elem.get('data-pvp-datiVendita-dataOraVendita')

        if not data['data_vendita']:
            data_match = re.search(r'Data vendita[:\s]+(\d{2}/\d{2}/\d{4}.*?\d{2}:\d{2})', page_text, re.I)
            if data_match:
                data['data_vendita'] = data_match.group(1)

        data['tipo_vendita'] = self.extract_text(soup, '[data-pvp-datiVendita-tipologiaVendita]',
                                                 attribute='data-pvp-datiVendita-tipologiaVendita')
        data['modalita_vendita'] = self.extract_text(soup, '[data-pvp-datiVendita-modalitaVendita]',
                                                     attribute='data-pvp-datiVendita-modalitaVendita')

        # === PREZZI ===
        print("\nPrezzi:")

        prezzo_base_text = self.extract_price_advanced(soup, 'Prezzo base')
        if not prezzo_base_text:
            prezzo_base_text = self.extract_price_advanced(soup, "Base d'asta")

        data['prezzo_base_formatted'] = prezzo_base_text
        data['prezzo_base'] = self.clean_price(prezzo_base_text)

        offerta_min_text = self.extract_price_advanced(soup, 'Offerta minima')
        data['offerta_minima_formatted'] = offerta_min_text
        data['offerta_minima'] = self.clean_price(offerta_min_text)

        rialzo_text = self.extract_price_advanced(soup, 'Rialzo minimo')
        data['rialzo_minimo_formatted'] = rialzo_text
        data['rialzo_minimo'] = self.clean_price(rialzo_text)

        # === PROCEDURA ===
        tribunale_match = re.search(r'Tribunale[:\s]+([^\n]+)', page_text, re.I)
        if tribunale_match:
            data['tribunale'] = tribunale_match.group(1).strip()[:100]

        ruolo_match = re.search(r'Ruolo[:\s]+(\d+)/(\d+)', page_text, re.I)
        if ruolo_match:
            data['numero_rge'] = ruolo_match.group(1)
            data['anno_rge'] = ruolo_match.group(2)

        # === PROFESSIONISTI ===
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

            elif 'Custode' in tipo_text:
                data['custode_cognome'] = self.extract_text(soggetto, '[data-pvp-soggetto-cognome]',
                                                            attribute='data-pvp-soggetto-cognome')
                data['custode_nome'] = self.extract_text(soggetto, '[data-pvp-soggetto-nome]',
                                                         attribute='data-pvp-soggetto-nome')
                data['custode_telefono'] = self.extract_text(soggetto, '[data-pvp-soggetto-telefono]',
                                                             attribute='data-pvp-soggetto-telefono')
                data['custode_email'] = self.extract_text(soggetto, '[data-pvp-soggetto-email]',
                                                          attribute='data-pvp-soggetto-email')

        # === DESCRIZIONE ===
        desc_breve_elem = soup.find('[data-pvp-bene-descrizioneIT]')
        if desc_breve_elem:
            data['descrizione_breve'] = desc_breve_elem.get_text(strip=True)

        print(f"\nParsing completato - {len([v for v in data.values() if v])} campi estratti")

        # RIEPILOGO
        print(f"\nRIEPILOGO VALORI NUMERICI:")
        print(f"  Prezzo Base: {data['prezzo_base_formatted']} -> {data['prezzo_base']}")
        print(f"  Offerta Minima: {data['offerta_minima_formatted']} -> {data['offerta_minima']}")
        print(f"  Rialzo Minimo: {data['rialzo_minimo_formatted']} -> {data['rialzo_minimo']}")
        print(f"  Superficie: {data['superficie_mq']} mq")
        print(f"  Vani: {data['vani']}")
        print(f"  Bagni: {data['bagni']}")

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
                data.get('codice_asta'), data.get('url'), data.get('titolo'),
                data.get('tipologia_immobile'), data.get('categoria'), data.get('genere'),
                data.get('indirizzo'), data.get('indirizzo'), data.get('citta'),
                data.get('provincia'), data.get('cap'), data.get('zona'),
                data.get('latitudine'), data.get('longitudine'),
                data.get('piano'), data.get('vani'), data.get('bagni'), data.get('superficie_mq'),
                data.get('disponibilita'), data.get('classe_energetica'),
                data.get('codice_lotto'), data.get('numero_beni_lotto'), data.get('descrizione_lotto'), None,
                data.get('data_vendita'), data.get('tipo_vendita'), data.get('modalita_vendita'),
                data.get('indirizzo_luogo_vendita'), data.get('citta_luogo_vendita'), data.get('cap_luogo_vendita'),
                data.get('termine_offerte'),
                data.get('prezzo_base'), data.get('prezzo_base_formatted'),
                data.get('offerta_minima'), data.get('offerta_minima_formatted'),
                data.get('rialzo_minimo'), data.get('rialzo_minimo_formatted'),
                data.get('deposito_cauzionale'), None,
                data.get('tribunale'), data.get('tipo_procedura'), data.get('numero_rge'), data.get('anno_rge'),
                data.get('delegato_nome'), data.get('delegato_cognome'), data.get('delegato_telefono'),
                data.get('delegato_email'), data.get('delegato_procede_vendita'),
                data.get('custode_nome'), data.get('custode_cognome'), data.get('custode_telefono'),
                data.get('custode_email'), data.get('custode_gestisce_visite'),
                data.get('descrizione_breve'), None,
                data.get('data_pubblicazione'), json.dumps(data, ensure_ascii=False)
            ))

            codice = data.get('codice_asta')

            cursor.execute('DELETE FROM allegati WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM foto WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM planimetrie WHERE codice_asta = ?', (codice,))
            cursor.execute('DELETE FROM storico_vendite WHERE codice_asta = ?', (codice,))

            for alleg in allegati:
                cursor.execute('''
                    INSERT INTO allegati (codice_asta, tipo_allegato, nome_file, url_download)
                    VALUES (?, ?, ?, ?)
                ''', (alleg['codice_asta'], alleg['tipo_allegato'], alleg['nome_file'], alleg['url_download']))

            for f in foto:
                cursor.execute('''
                    INSERT INTO foto (codice_asta, url_foto, ordine)
                    VALUES (?, ?, ?)
                ''', (f['codice_asta'], f['url_foto'], f['ordine']))

            for p in planimetrie:
                cursor.execute('''
                    INSERT INTO planimetrie (codice_asta, url_planimetria, ordine)
                    VALUES (?, ?, ?)
                ''', (p['codice_asta'], p['url_planimetria'], p['ordine']))

            for s in storico:
                cursor.execute('''
                    INSERT INTO storico_vendite (codice_asta, data_vendita, prezzo_base, prezzo_base_formatted)
                    VALUES (?, ?, ?, ?)
                ''', (s['codice_asta'], s['data_vendita'], s['prezzo_base'], s['prezzo_base_formatted']))

            conn.commit()
            print(f"\nSalvato nel DB: {codice}")
            print(f"  Allegati: {len(allegati)}")
            print(f"  Foto: {len(foto)}")
            print(f"  Planimetrie: {len(planimetrie)}")
            print(f"  Storico: {len(storico)}")

        except Exception as e:
            conn.rollback()
            print(f"Errore DB: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

    def search_by_city(self, city="Roma"):
        """Esegue la ricerca"""
        try:
            print(f"RICERCA IMMOBILI A {city.upper()}")
            print("-" * 60)
            time.sleep(3)

            print(f"\nCerco il campo 'Indirizzo'...")
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
                                print(f"Campo trovato: {selector}")
                                break
                    if indirizzo_field:
                        break
                except:
                    continue

            if not indirizzo_field:
                print("Campo indirizzo non trovato!")
                return None, []

            print(f"\nInserisco '{city}'...")
            indirizzo_field.clear()
            time.sleep(0.5)
            indirizzo_field.send_keys(city)
            time.sleep(2)

            print(f"\nCerco il pulsante 'Cerca'...")
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
                            print(f"Pulsante trovato: {selector}")
                            break
                    if cerca_button:
                        break
                except:
                    continue

            if cerca_button:
                print("Clicco su 'Cerca'...")
                try:
                    cerca_button.click()
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", cerca_button)
                    except:
                        indirizzo_field.send_keys(Keys.RETURN)
            else:
                print("Pulsante 'Cerca' non trovato, premo INVIO...")
                indirizzo_field.send_keys(Keys.RETURN)

            print(f"\nAttendo caricamento risultati...")
            time.sleep(5)

            print(f"\nCerco link con '/vendita-'...")
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

            print(f"{len(unique_urls)} URL unici trovati\n")
            return self.driver.page_source, list(unique_urls)

        except Exception as e:
            print(f"Errore durante la ricerca: {e}")
            import traceback
            traceback.print_exc()
            return None, []

    def scroll_and_load_more(self, main_window, all_urls):
        """Esegue scroll per caricare più risultati"""
        try:
            self.driver.switch_to.window(main_window)
            print(f"\nEseguo scroll per caricare più risultati...")

            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            for i in range(3):
                scroll_position = (i + 1) * (self.driver.execute_script("return document.body.scrollHeight") // 4)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                time.sleep(1)

            time.sleep(2)

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
                print(f"   Trovati {new_found} nuovi immobili (Totale: {after_count})")
            else:
                print(f"   Nessun nuovo immobile trovato (Totale: {after_count})")

            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)

        except Exception as e:
            print(f"Errore durante lo scroll: {e}")

    def check_immobile_exists(self, url):
        """Controlla se immobile esiste già"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT codice_asta, titolo, data_inserimento FROM aste WHERE url = ?', (url,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {'exists': True, 'codice': result[0], 'titolo': result[1], 'data_inserimento': result[2]}
        return {'exists': False}

    def scrape_all(self, city="Roma", max_aste=None):
        """Scraping completo"""
        print(f"\n{'=' * 60}")
        print(f"SCRAPER ASTEGIUDIZIARIE.IT V2")
        print(f"Città: {city}")
        if max_aste:
            print(f"Limite: {max_aste} aste")
        print(f"{'=' * 60}\n")

        if not self.email or not self.password:
            print("Credenziali mancanti! Crea file .env con ASTE_EMAIL e ASTE_PASSWORD")
            return

        if not self.init_selenium():
            return

        try:
            if not self.login():
                return

            result = self.search_by_city(city)

            if not result:
                print("Ricerca fallita!")
                return

            html, vendita_urls = result

            if not vendita_urls:
                print("Nessun link '/vendita-' trovato!")
                return

            print(f"\n{'=' * 60}")
            print(f"INIZIO DOWNLOAD DETTAGLI CON SCROLL AUTOMATICO")
            print(f"{'=' * 60}\n")

            main_window = self.driver.current_window_handle

            count_new = 0
            count_skipped = 0
            all_urls = set(vendita_urls)

            idx = 0
            while idx < len(list(all_urls)):
                if max_aste and count_new >= max_aste:
                    print(f"\nRaggiunto limite di {max_aste} aste")
                    break

                current_urls = list(all_urls)
                url = current_urls[idx]
                idx += 1

                print(f"\n{'=' * 60}")
                print(f"Immobile {idx}/{len(current_urls)}")
                print(f"URL: {url}")
                print(f"{'=' * 60}")

                check = self.check_immobile_exists(url)

                if check['exists']:
                    print(f"SALTATO - Già presente nel DB")
                    print(f"   Codice: {check['codice']}")
                    print(f"   Titolo: {check['titolo']}")
                    count_skipped += 1
                    self.scroll_and_load_more(main_window, all_urls)
                    continue

                print(f"NUOVO - Scarico dettagli completi...")

                self.driver.execute_script("window.open('');")
                time.sleep(0.5)

                windows = self.driver.window_handles
                detail_window = windows[-1]
                self.driver.switch_to.window(detail_window)

                try:
                    self.driver.get(url)
                    time.sleep(3)

                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                    # DEBUG: Salva HTML
                    with open(f'debug_dettaglio_latest.html', 'w', encoding='utf-8') as f:
                        f.write(soup.prettify())

                    immobile = self.parse_detail_page_v2(soup, url)
                    allegati = self.extract_allegati(soup, immobile['codice_asta'])
                    foto = self.extract_foto(soup, immobile['codice_asta'])
                    planimetrie = self.extract_planimetrie(soup, immobile['codice_asta'])
                    storico = self.extract_storico_vendite(soup, immobile['codice_asta'])

                    self.save_to_db(immobile, allegati, foto, planimetrie, storico)
                    count_new += 1

                    print(f"\nSalvato con successo!")
                    print(f"   Titolo: {immobile.get('titolo', 'N/A')}")
                    print(f"   Città: {immobile.get('citta', 'N/A')}")
                    print(f"   Prezzo: {immobile.get('prezzo_base_formatted', 'N/A')}")

                except Exception as e:
                    print(f"Errore durante il download: {e}")
                    import traceback
                    traceback.print_exc()

                finally:
                    try:
                        self.driver.close()
                    except:
                        pass

                    try:
                        self.driver.switch_to.window(main_window)
                    except:
                        pass

                    self.scroll_and_load_more(main_window, all_urls)

            print(f"\n{'=' * 60}")
            print(f"COMPLETATO!")
            print(f"{'=' * 60}")
            print(f"Statistiche:")
            print(f"   Totale URL trovati: {len(all_urls)}")
            print(f"   Nuovi scaricati: {count_new}")
            print(f"   Già presenti: {count_skipped}")
            print(f"Database: {self.db_name}")
            print(f"{'=' * 60}\n")

        finally:
            if self.driver:
                print("Chiudo il browser...")
                self.driver.quit()


def main():
    db_file = 'aste_immobiliari_v2.db'
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"Database esistente rimosso\n")

    scraper = AsteGiudiziarieScraperV2()
    scraper.scrape_all("Roma")


if __name__ == "__main__":
    main()