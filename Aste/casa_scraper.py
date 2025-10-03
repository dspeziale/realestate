import requests
from bs4 import BeautifulSoup
import json
import sqlite3
import re
from pathlib import Path
from datetime import datetime
import time


class CasaItScraper:
    def __init__(self, db_name='aste_immobiliari.db'):
        self.db_name = db_name
        self.base_url = "https://www.casa.it"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.setup_database()

    def setup_database(self):
        """Crea il database SQLite con la tabella immobili"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS immobili (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titolo TEXT,
                indirizzo TEXT,
                indirizzo_completo TEXT,
                zona TEXT,
                citta TEXT,
                cap TEXT,
                prezzo_asta TEXT,
                prezzo_numerico REAL,
                superficie INTEGER,
                numero_locali INTEGER,
                numero_bagni INTEGER,
                piano TEXT,
                tipo_immobile TEXT,
                descrizione TEXT,
                descrizione_completa TEXT,
                stato TEXT,
                anno_costruzione INTEGER,
                classe_energetica TEXT,
                riscaldamento TEXT,
                box_auto BOOLEAN,
                tribunale TEXT,
                rge TEXT,
                lotto TEXT,
                tipo_asta TEXT,
                base_asta TEXT,
                rilancio_minimo TEXT,
                data_asta TEXT,
                foglio TEXT,
                particella TEXT,
                subalterno TEXT,
                categoria_catastale TEXT,
                rendita TEXT,
                email_contatto TEXT,
                telefono_contatto TEXT,
                caratteristiche TEXT,
                immagini TEXT,
                url TEXT UNIQUE,
                data_inserimento TIMESTAMP,
                data_ultimo_aggiornamento TIMESTAMP,
                tipo_vendita TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def check_immobile_exists(self, url):
        """Controlla se un immobile è già presente nel database tramite URL"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('SELECT id, titolo, data_inserimento FROM immobili WHERE url = ?', (url,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'exists': True,
                'id': result[0],
                'titolo': result[1],
                'data_inserimento': result[2]
            }
        return {'exists': False}

    def extract_price(self, price_text):
        """Estrae il prezzo numerico dal testo"""
        if not price_text:
            return None
        numbers = re.findall(r'[\d.]+', price_text.replace('.', '').replace(',', '.'))
        return float(numbers[0]) if numbers else None

    def extract_superficie(self, superficie_text):
        """Estrae la superficie in metri quadri"""
        if not superficie_text:
            return None
        numbers = re.findall(r'\d+', superficie_text)
        return int(numbers[0]) if numbers else None

    def scrape_page(self, url):
        """Effettua lo scraping di una singola pagina"""
        try:
            # Prima visita la homepage per ottenere i cookie
            print("Ottengo i cookie dal sito...")
            self.session.get(self.base_url, timeout=10)
            time.sleep(2)

            # Poi accedi alla pagina target
            print("Carico la pagina degli annunci...")
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            return BeautifulSoup(response.content, 'html.parser')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                print(f"\n❌ Errore 403: Il sito blocca l'accesso automatico")
                print("Provo con metodo alternativo...")
                return self.scrape_with_selenium(url)
            else:
                print(f"Errore HTTP {e.response.status_code}: {e}")
                return None
        except Exception as e:
            print(f"Errore nel caricamento della pagina: {e}")
            return None

    def scrape_with_selenium(self, url):
        """Metodo alternativo usando Selenium se disponibile"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            print("Uso Selenium per bypassare il blocco...")

            options = Options()
            options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            driver = webdriver.Chrome(options=options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            driver.get(url)
            time.sleep(3)

            # Attendi che la pagina carichi
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            html = driver.page_source
            driver.quit()

            return BeautifulSoup(html, 'html.parser')

        except ImportError:
            print("\n❌ Selenium non installato.")
            print("Installa con: pip install selenium")
            print("\nAlternativamente, salva manualmente la pagina HTML e passala allo script.")
            return None
        except Exception as e:
            print(f"Errore con Selenium: {e}")
            return None

    def parse_immobile(self, element):
        """Estrae i dati di un singolo immobile dalla lista"""
        immobile = {}

        try:
            # Titolo e URL
            link = element.find('a', href=True)
            if link:
                immobile['url'] = self.base_url + link['href'] if link['href'].startswith('/') else link['href']
                immobile['titolo'] = link.get_text(strip=True) or 'N/A'

            # Zona/Località
            zona_elem = element.find(class_=re.compile('zona|location|locality', re.I))
            immobile['zona'] = zona_elem.get_text(strip=True) if zona_elem else 'N/A'

            # Prezzo
            prezzo_elem = element.find(string=re.compile(r'€|euro', re.I))
            if prezzo_elem:
                prezzo_text = prezzo_elem.strip()
                immobile['prezzo_asta'] = prezzo_text
                immobile['prezzo_numerico'] = self.extract_price(prezzo_text)
            else:
                immobile['prezzo_asta'] = 'N/A'
                immobile['prezzo_numerico'] = None

            # Superficie
            superficie_elem = element.find(string=re.compile(r'm²|mq', re.I))
            if superficie_elem:
                superficie_text = superficie_elem.strip()
                immobile['superficie'] = self.extract_superficie(superficie_text)
            else:
                immobile['superficie'] = None

            # Tipo immobile e vendita
            immobile['tipo_immobile'] = 'Commerciale'
            immobile['tipo_vendita'] = 'Asta'

            immobile['data_inserimento'] = datetime.now().isoformat()

            return immobile

        except Exception as e:
            print(f"Errore nel parsing dell'immobile: {e}")
            return None

    def scrape_detail_page(self, url):
        """Scrape della pagina dettaglio immobile"""
        print(f"  → Carico dettagli da: {url}")

        try:
            time.sleep(1)  # Pausa per evitare ban
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            dettagli = {}

            # Descrizione completa
            desc_elem = soup.find(['div', 'section'], class_=re.compile('description|desc|testo', re.I))
            if desc_elem:
                dettagli['descrizione_completa'] = desc_elem.get_text(strip=True)

            # Caratteristiche (cerca tabelle o liste di caratteristiche)
            caratteristiche = {}

            # Pattern 1: Tabelle con caratteristiche
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        value = cells[1].get_text(strip=True)
                        if key and value:
                            caratteristiche[key] = value

            # Pattern 2: Liste di caratteristiche
            feature_sections = soup.find_all(['ul', 'dl', 'div'],
                                             class_=re.compile('feature|caratteristic|detail', re.I))
            for section in feature_sections:
                items = section.find_all(['li', 'dt', 'dd', 'span'])
                for item in items:
                    text = item.get_text(strip=True)
                    if ':' in text:
                        parts = text.split(':', 1)
                        caratteristiche[parts[0].strip()] = parts[1].strip()

            # Estrai informazioni specifiche
            dettagli['caratteristiche'] = caratteristiche

            # Indirizzo completo
            indirizzo_elem = soup.find(string=re.compile('indirizzo|via|viale|piazza', re.I))
            if indirizzo_elem:
                indirizzo_parent = indirizzo_elem.find_parent()
                if indirizzo_parent:
                    dettagli['indirizzo_completo'] = indirizzo_parent.get_text(strip=True)

            # CAP e Città
            cap_match = re.search(r'\b\d{5}\b', soup.get_text())
            if cap_match:
                dettagli['cap'] = cap_match.group(0)

            citta_elem = soup.find(string=re.compile('città|comune|locality', re.I))
            if citta_elem:
                citta_parent = citta_elem.find_parent()
                if citta_parent:
                    dettagli['citta'] = citta_parent.get_text(strip=True)

            # Numero locali
            locali_match = re.search(r'(\d+)\s*local[ie]', soup.get_text(), re.I)
            if locali_match:
                dettagli['numero_locali'] = int(locali_match.group(1))

            # Bagni
            bagni_match = re.search(r'(\d+)\s*bagn[io]', soup.get_text(), re.I)
            if bagni_match:
                dettagli['numero_bagni'] = int(bagni_match.group(1))

            # Piano
            piano_match = re.search(r'piano\s*([TtSs0-9]+)', soup.get_text(), re.I)
            if piano_match:
                dettagli['piano'] = piano_match.group(1)

            # Stato/Condizioni
            stato_keywords = ['nuovo', 'ristrutturato', 'da ristrutturare', 'buono stato', 'ottimo stato']
            for keyword in stato_keywords:
                if re.search(keyword, soup.get_text(), re.I):
                    dettagli['stato'] = keyword
                    break

            # Anno costruzione
            anno_match = re.search(r'anno\s*(?:di\s*)?costruzione[:\s]*(\d{4})', soup.get_text(), re.I)
            if anno_match:
                dettagli['anno_costruzione'] = int(anno_match.group(1))

            # Classe energetica
            classe_match = re.search(r'classe\s*energetica[:\s]*([A-G][\+]*)', soup.get_text(), re.I)
            if classe_match:
                dettagli['classe_energetica'] = classe_match.group(1).upper()

            # Riscaldamento
            risc_keywords = ['autonomo', 'centralizzato', 'metano', 'gpl', 'pompa di calore']
            for keyword in risc_keywords:
                if re.search(keyword, soup.get_text(), re.I):
                    dettagli['riscaldamento'] = keyword
                    break

            # Box/Posto auto
            box_match = re.search(r'(box|garage|posto\s*auto)', soup.get_text(), re.I)
            if box_match:
                dettagli['box_auto'] = True

            # Informazioni asta
            asta_info = {}

            # Data asta
            data_asta_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', soup.get_text())
            if data_asta_match:
                asta_info['data_asta'] = data_asta_match.group(1)

            # Tribunale
            tribunale_match = re.search(r'tribunale\s+(?:di\s+)?([A-Za-z\s]+)', soup.get_text(), re.I)
            if tribunale_match:
                asta_info['tribunale'] = tribunale_match.group(1).strip()

            # Numero RGE
            rge_match = re.search(r'RGE[:\s]*(\d+/\d+)', soup.get_text(), re.I)
            if rge_match:
                asta_info['rge'] = rge_match.group(1)

            # Lotto
            lotto_match = re.search(r'lotto[:\s]*(\d+)', soup.get_text(), re.I)
            if lotto_match:
                asta_info['lotto'] = lotto_match.group(1)

            # Tipo asta (sincrona/asincrona)
            if re.search(r'asincrona', soup.get_text(), re.I):
                asta_info['tipo_asta'] = 'Asincrona'
            elif re.search(r'sincrona', soup.get_text(), re.I):
                asta_info['tipo_asta'] = 'Sincrona'

            # Base d'asta
            base_match = re.search(r'base\s*(?:d[\'i]\s*)?asta[:\s]*€?\s*([\d.,]+)', soup.get_text(), re.I)
            if base_match:
                asta_info['base_asta'] = base_match.group(1)

            # Rilancio minimo
            rilancio_match = re.search(r'rilancio\s*minimo[:\s]*€?\s*([\d.,]+)', soup.get_text(), re.I)
            if rilancio_match:
                asta_info['rilancio_minimo'] = rilancio_match.group(1)

            dettagli['info_asta'] = asta_info

            # Immagini
            images = soup.find_all('img', src=re.compile(r'\.jpg|\.jpeg|\.png', re.I))
            dettagli['immagini'] = [img['src'] for img in images if 'src' in img.attrs][:10]  # Max 10 immagini

            # Contatti (se presenti)
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', soup.get_text())
            if email_match:
                dettagli['email_contatto'] = email_match.group(0)

            tel_match = re.search(r'(\+?\d{2,3}[\s.-]?\d{2,4}[\s.-]?\d{4,6})', soup.get_text())
            if tel_match:
                dettagli['telefono_contatto'] = tel_match.group(1)

            # Dati catastali
            catasto = {}

            foglio_match = re.search(r'foglio[:\s]*(\d+)', soup.get_text(), re.I)
            if foglio_match:
                catasto['foglio'] = foglio_match.group(1)

            particella_match = re.search(r'particella[:\s]*(\d+)', soup.get_text(), re.I)
            if particella_match:
                catasto['particella'] = particella_match.group(1)

            subalterno_match = re.search(r'subalterno[:\s]*(\d+)', soup.get_text(), re.I)
            if subalterno_match:
                catasto['subalterno'] = subalterno_match.group(1)

            categoria_match = re.search(r'categoria[:\s]*([A-Z]/\d+|[CDE]/\d+)', soup.get_text(), re.I)
            if categoria_match:
                catasto['categoria'] = categoria_match.group(1)

            rendita_match = re.search(r'rendita[:\s]*€?\s*([\d.,]+)', soup.get_text(), re.I)
            if rendita_match:
                catasto['rendita'] = rendita_match.group(1)

            dettagli['dati_catastali'] = catasto

            print(f"  ✓ Dettagli estratti con successo")
            return dettagli

        except Exception as e:
            print(f"  ✗ Errore nell'estrazione dettagli: {e}")
            return {}

    def save_to_json(self, immobile, output_dir='immobili_json'):
        """Salva un immobile in un file JSON"""
        Path(output_dir).mkdir(exist_ok=True)

        # Crea nome file più leggibile
        titolo_safe = re.sub(r'[^\w\s-]', '', immobile.get('titolo', 'immobile'))[:50]
        titolo_safe = re.sub(r'[-\s]+', '_', titolo_safe)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/{titolo_safe}_{timestamp}.json"

        # Prepara il JSON con struttura organizzata
        json_data = {
            'info_generali': {
                'titolo': immobile.get('titolo'),
                'tipo_immobile': immobile.get('tipo_immobile'),
                'tipo_vendita': immobile.get('tipo_vendita'),
                'url': immobile.get('url'),
                'data_inserimento': immobile.get('data_inserimento')
            },
            'localizzazione': {
                'indirizzo': immobile.get('indirizzo'),
                'indirizzo_completo': immobile.get('indirizzo_completo'),
                'zona': immobile.get('zona'),
                'citta': immobile.get('citta'),
                'cap': immobile.get('cap')
            },
            'prezzi': {
                'prezzo_asta': immobile.get('prezzo_asta'),
                'prezzo_numerico': immobile.get('prezzo_numerico'),
                'base_asta': immobile.get('base_asta'),
                'rilancio_minimo': immobile.get('rilancio_minimo')
            },
            'caratteristiche': {
                'superficie': immobile.get('superficie'),
                'numero_locali': immobile.get('numero_locali'),
                'numero_bagni': immobile.get('numero_bagni'),
                'piano': immobile.get('piano'),
                'stato': immobile.get('stato'),
                'anno_costruzione': immobile.get('anno_costruzione'),
                'classe_energetica': immobile.get('classe_energetica'),
                'riscaldamento': immobile.get('riscaldamento'),
                'box_auto': immobile.get('box_auto'),
                'altre_caratteristiche': immobile.get('caratteristiche', {})
            },
            'descrizione': {
                'breve': immobile.get('descrizione'),
                'completa': immobile.get('descrizione_completa')
            },
            'informazioni_asta': {
                'data_asta': immobile.get('data_asta'),
                'tribunale': immobile.get('tribunale'),
                'rge': immobile.get('rge'),
                'lotto': immobile.get('lotto'),
                'tipo_asta': immobile.get('tipo_asta'),
                'info_asta': immobile.get('info_asta', {})
            },
            'dati_catastali': {
                'foglio': immobile.get('foglio'),
                'particella': immobile.get('particella'),
                'subalterno': immobile.get('subalterno'),
                'categoria': immobile.get('categoria_catastale'),
                'rendita': immobile.get('rendita'),
                'dati_completi': immobile.get('dati_catastali', {})
            },
            'contatti': {
                'email': immobile.get('email_contatto'),
                'telefono': immobile.get('telefono_contatto')
            },
            'media': {
                'immagini': immobile.get('immagini', [])
            }
        }

        # Rimuovi campi vuoti/None per JSON più pulito
        json_data = self._remove_empty_fields(json_data)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"  ✓ JSON salvato: {filename}")
        return filename

    def _remove_empty_fields(self, data):
        """Rimuove ricorsivamente campi vuoti, None o dizionari vuoti"""
        if isinstance(data, dict):
            return {
                k: self._remove_empty_fields(v)
                for k, v in data.items()
                if v is not None and v != '' and v != {} and v != []
            }
        elif isinstance(data, list):
            return [self._remove_empty_fields(item) for item in data if item is not None]
        else:
            return data

    def save_to_db(self, immobile):
        """Salva un immobile nel database SQLite"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            # Converti le liste/dict in JSON string
            caratteristiche_json = json.dumps(immobile.get('caratteristiche', {}), ensure_ascii=False)
            immagini_json = json.dumps(immobile.get('immagini', []), ensure_ascii=False)

            # Aggiungi data ultimo aggiornamento
            immobile['data_ultimo_aggiornamento'] = datetime.now().isoformat()

            cursor.execute('''
                INSERT OR REPLACE INTO immobili 
                (titolo, indirizzo, indirizzo_completo, zona, citta, cap, prezzo_asta, prezzo_numerico, 
                 superficie, numero_locali, numero_bagni, piano, tipo_immobile, descrizione, 
                 descrizione_completa, stato, anno_costruzione, classe_energetica, riscaldamento,
                 box_auto, tribunale, rge, lotto, tipo_asta, base_asta, rilancio_minimo, data_asta,
                 foglio, particella, subalterno, categoria_catastale, rendita,
                 email_contatto, telefono_contatto, caratteristiche, immagini,
                 url, data_inserimento, data_ultimo_aggiornamento, tipo_vendita)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                immobile.get('titolo'),
                immobile.get('indirizzo'),
                immobile.get('indirizzo_completo'),
                immobile.get('zona'),
                immobile.get('citta'),
                immobile.get('cap'),
                immobile.get('prezzo_asta'),
                immobile.get('prezzo_numerico'),
                immobile.get('superficie'),
                immobile.get('numero_locali'),
                immobile.get('numero_bagni'),
                immobile.get('piano'),
                immobile.get('tipo_immobile'),
                immobile.get('descrizione'),
                immobile.get('descrizione_completa'),
                immobile.get('stato'),
                immobile.get('anno_costruzione'),
                immobile.get('classe_energetica'),
                immobile.get('riscaldamento'),
                immobile.get('box_auto'),
                immobile.get('tribunale'),
                immobile.get('rge'),
                immobile.get('lotto'),
                immobile.get('tipo_asta'),
                immobile.get('base_asta'),
                immobile.get('rilancio_minimo'),
                immobile.get('data_asta'),
                immobile.get('foglio'),
                immobile.get('particella'),
                immobile.get('subalterno'),
                immobile.get('categoria_catastale'),
                immobile.get('rendita'),
                immobile.get('email_contatto'),
                immobile.get('telefono_contatto'),
                caratteristiche_json,
                immagini_json,
                immobile.get('url'),
                immobile.get('data_inserimento'),
                immobile.get('data_ultimo_aggiornamento'),
                immobile.get('tipo_vendita')
            ))
            conn.commit()
            print(f"  ✓ Salvato in DB")
        except sqlite3.IntegrityError:
            print(f"  ℹ Immobile già presente nel DB - Aggiornato")
        finally:
            conn.close()

    def scrape_all(self, url, html_file=None):
        """Esegue lo scraping completo"""
        print(f"Inizio scraping di: {url}\n")

        if html_file:
            # Carica da file HTML locale
            print(f"Carico il file HTML: {html_file}")
            with open(html_file, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
        else:
            soup = self.scrape_page(url)

        if not soup:
            return

        # Salva l'HTML per debug
        with open('debug_page.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("HTML salvato in 'debug_page.html' per analisi\n")

        # Cerca tutti gli elementi che contengono immobili
        immobili_elements = soup.find_all(['article', 'div'], class_=re.compile('listing|card|property|result', re.I))

        if not immobili_elements:
            # Fallback: cerca link che contengono /immobili/
            immobili_elements = soup.find_all('a', href=re.compile(r'/immobili/\d+'))
            immobili_elements = [elem.parent.parent for elem in immobili_elements if elem.parent]

        print(f"Trovati {len(immobili_elements)} elementi immobiliari\n")

        count_new = 0
        count_skipped = 0

        for idx, element in enumerate(immobili_elements, 1):
            print(f"\n{'=' * 60}")
            print(f"Immobile {idx}/{len(immobili_elements)}")
            print(f"{'=' * 60}")

            # Estrai dati base dalla lista
            immobile = self.parse_immobile(element)

            if immobile and immobile.get('url'):
                # CONTROLLA SE L'IMMOBILE È GIÀ STATO SCARICATO
                check_result = self.check_immobile_exists(immobile['url'])

                if check_result['exists']:
                    print(f"⏭️  SALTATO - Immobile già presente nel database")
                    print(f"   Titolo: {check_result['titolo']}")
                    print(f"   Data inserimento: {check_result['data_inserimento']}")
                    print(f"   ID database: {check_result['id']}")
                    count_skipped += 1
                    continue

                # Se non esiste, procedi con il download completo
                print(f"🆕 NUOVO - Procedo con il download completo")

                # Scarica e aggiungi dettagli dalla pagina dell'immobile
                dettagli = self.scrape_detail_page(immobile['url'])

                # Unisci i dati
                immobile.update(dettagli)

                # Estrai info dai dettagli se non già presenti
                if 'indirizzo' not in immobile or immobile['indirizzo'] == 'N/A':
                    if 'indirizzo_completo' in dettagli:
                        immobile['indirizzo'] = dettagli['indirizzo_completo']

                if 'descrizione' not in immobile or not immobile['descrizione']:
                    if 'descrizione_completa' in dettagli:
                        immobile['descrizione'] = dettagli['descrizione_completa'][:500]

                # Aggiungi info asta ai campi principali
                if 'info_asta' in dettagli:
                    for key, value in dettagli['info_asta'].items():
                        immobile[key] = value

                # Aggiungi dati catastali ai campi principali
                if 'dati_catastali' in dettagli:
                    for key, value in dettagli['dati_catastali'].items():
                        if key == 'categoria':
                            immobile['categoria_catastale'] = value
                        else:
                            immobile[key] = value

                # Salva in JSON e DB
                self.save_to_json(immobile)
                self.save_to_db(immobile)
                count_new += 1

                print(f"\n✓ Elaborato completo: {count_new} nuovi, {count_skipped} saltati")
            else:
                print(f"✗ Impossibile estrarre URL dall'elemento")

        print(f"\n{'=' * 60}")
        print(f"SCRAPING COMPLETATO!")
        print(f"{'=' * 60}")
        print(f"📊 Statistiche:")
        print(f"   • Immobili trovati: {len(immobili_elements)}")
        print(f"   • Nuovi scaricati: {count_new}")
        print(f"   • Già presenti (saltati): {count_skipped}")
        print(f"💾 Database: {self.db_name}")
        print(f"📁 File JSON: cartella 'immobili_json/'")
        print(f"{'=' * 60}")

        return count_new

    def get_statistics(self):
        """Restituisce statistiche dal database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        stats = {}

        # Totale immobili
        cursor.execute('SELECT COUNT(*) FROM immobili')
        stats['totale'] = cursor.fetchone()[0]

        # Per tipo immobile
        cursor.execute('SELECT tipo_immobile, COUNT(*) FROM immobili GROUP BY tipo_immobile')
        stats['per_tipo'] = dict(cursor.fetchall())

        # Per città
        cursor.execute(
            'SELECT citta, COUNT(*) FROM immobili WHERE citta IS NOT NULL GROUP BY citta ORDER BY COUNT(*) DESC LIMIT 10')
        stats['per_citta'] = dict(cursor.fetchall())

        # Range prezzi
        cursor.execute(
            'SELECT MIN(prezzo_numerico), MAX(prezzo_numerico), AVG(prezzo_numerico) FROM immobili WHERE prezzo_numerico IS NOT NULL')
        result = cursor.fetchone()
        stats['prezzi'] = {
            'minimo': result[0],
            'massimo': result[1],
            'media': result[2]
        }

        # Immobili con data asta
        cursor.execute('SELECT COUNT(*) FROM immobili WHERE data_asta IS NOT NULL')
        stats['con_data_asta'] = cursor.fetchone()[0]

        conn.close()
        return stats

    def print_statistics(self):
        """Stampa statistiche dal database"""
        stats = self.get_statistics()

        print(f"\n{'=' * 60}")
        print(f"📊 STATISTICHE DATABASE")
        print(f"{'=' * 60}")
        print(f"Totale immobili: {stats['totale']}")

        if stats['per_tipo']:
            print(f"\nPer tipo:")
            for tipo, count in stats['per_tipo'].items():
                print(f"  • {tipo}: {count}")

        if stats['per_citta']:
            print(f"\nTop 10 città:")
            for citta, count in stats['per_citta'].items():
                print(f"  • {citta}: {count}")

        if stats['prezzi']['minimo']:
            print(f"\nPrezzi:")
            print(f"  • Minimo: €{stats['prezzi']['minimo']:,.2f}")
            print(f"  • Massimo: €{stats['prezzi']['massimo']:,.2f}")
            print(f"  • Media: €{stats['prezzi']['media']:,.2f}")

        print(f"\nImmobili con data asta: {stats['con_data_asta']}")
        print(f"{'=' * 60}\n")


def main():
    # URL di ricerca per immobili all'asta a Roma (min 200mq)
    url = "https://www.casa.it/srp/?tr=vendita&mqMin=200&sortType=price_asc&geobounds={%22bbox%22:[[41.97261768278087%2C12.464675081765128]%2C[41.86813559005047%2C12.585524691140128]]}&only_auction=true&propertyTypeGroup=case"

    scraper = CasaItScraper()

    # Mostra statistiche pre-scraping
    print("\n🔍 Controllo database esistente...")
    scraper.print_statistics()

    # Opzione 1: Scraping automatico
    print("\n🚀 Avvio scraping...\n")
    scraper.scrape_all(url)

    # Mostra statistiche post-scraping
    scraper.print_statistics()

    # Opzione 2: Se hai salvato l'HTML manualmente, usa:
    # scraper.scrape_all(url, html_file='casa_page.html')


if __name__ == "__main__":
    main()