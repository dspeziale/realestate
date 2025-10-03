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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import os
from dotenv import load_dotenv


class AsteGiudiziarieItScraper:
    def __init__(self, db_name='aste_immobiliari.db'):
        self.db_name = db_name
        self.base_url = "https://www.astegiudiziarie.it"
        self.driver = None

        # Carica credenziali da .env
        load_dotenv()
        self.email = os.getenv('ASTE_EMAIL')
        self.password = os.getenv('ASTE_PASSWORD')

        # Inizializza database
        self.setup_database()

    def setup_database(self):
        """Crea il database SQLite con la tabella aste"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aste (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titolo TEXT,
                tipo_immobile TEXT,
                tipo_vendita TEXT DEFAULT 'Asta',
                url TEXT UNIQUE,
                data_inserimento TEXT NOT NULL,
                indirizzo TEXT,
                indirizzo_completo TEXT,
                zona TEXT,
                citta TEXT,
                cap TEXT,
                prezzo_asta TEXT,
                superficie TEXT,
                numero_locali INTEGER,
                numero_bagni INTEGER,
                piano TEXT,
                stato TEXT,
                descrizione_breve TEXT,
                descrizione_completa TEXT,
                data_asta TEXT,
                ora_asta TEXT,
                tipo_asta TEXT,
                rilancio_minimo TEXT,
                lotto TEXT,
                foglio TEXT,
                particella TEXT,
                subalterno TEXT,
                categoria TEXT,
                rendita TEXT,
                tribunale TEXT,
                rge TEXT,
                giudice TEXT,
                custode TEXT,
                delegato TEXT,
                telefono TEXT,
                email TEXT,
                json_completo TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Crea indici per migliorare le performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_citta ON aste(citta)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tipo_immobile ON aste(tipo_immobile)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_asta ON aste(data_asta)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON aste(url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON aste(created_at DESC)')

        conn.commit()
        conn.close()
        print(f"✅ Database '{self.db_name}' inizializzato\n")

    def init_selenium(self):
        """Inizializza Selenium WebDriver"""
        try:
            print("🔧 Inizializzo il browser...")
            options = Options()
            # Commenta la riga sotto se vuoi vedere il browser in azione
            # options.add_argument('--headless')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✓ Browser avviato\n")
            return True
        except Exception as e:
            print(f"❌ Errore inizializzazione browser: {e}")
            return False

    def login(self):
        """Esegue il login completo seguendo il flusso corretto"""
        try:
            print(f"🔐 Inizio procedura di login...")

            # STEP 1: Vai alla home page
            print(f"📍 Step 1: Carico la home page {self.base_url}")
            self.driver.get(self.base_url)
            time.sleep(3)

            self.driver.save_screenshot('debug_1_homepage.png')
            print("📸 Screenshot: debug_1_homepage.png")

            # STEP 2: Cerca e clicca "Accedi/Registrati"
            print(f"\n📍 Step 2: Cerco il pulsante 'Accedi/Registrati'...")

            accedi_selectors = [
                "//a[contains(text(), 'Accedi')]",
                "//button[contains(text(), 'Accedi')]",
                "//a[contains(text(), 'Registrati')]",
                "//div[contains(text(), 'Accedi')]",
                "//span[contains(text(), 'Accedi')]"
            ]

            accedi_button = None
            for selector in accedi_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            accedi_button = elem
                            print(f"✓ Trovato 'Accedi/Registrati': {selector}")
                            break
                    if accedi_button:
                        break
                except:
                    continue

            if not accedi_button:
                print("❌ Pulsante 'Accedi/Registrati' non trovato!")
                print("Salvo HTML per debug...")
                with open('debug_1_homepage.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                return False

            print("🖱️  Clicco su 'Accedi/Registrati'...")
            try:
                accedi_button.click()
            except:
                self.driver.execute_script("arguments[0].click();", accedi_button)

            time.sleep(2)
            self.driver.save_screenshot('debug_2_login_dialog.png')
            print("📸 Screenshot: debug_2_login_dialog.png")

            # STEP 3: Seleziona "Privati"
            print(f"\n📍 Step 3: Cerco e seleziono 'Privati'...")

            privati_selectors = [
                "//a[contains(text(), 'Privati')]",
                "//button[contains(text(), 'Privati')]",
                "//div[contains(text(), 'Privati')]",
                "//span[contains(text(), 'Privati')]",
                "//label[contains(text(), 'Privati')]"
            ]

            privati_button = None
            for selector in privati_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            privati_button = elem
                            print(f"✓ Trovato 'Privati': {selector}")
                            break
                    if privati_button:
                        break
                except:
                    continue

            if privati_button:
                print("🖱️  Clicco su 'Privati'...")
                try:
                    privati_button.click()
                except:
                    self.driver.execute_script("arguments[0].click();", privati_button)
                time.sleep(2)
                self.driver.save_screenshot('debug_3_privati_selected.png')
                print("📸 Screenshot: debug_3_privati_selected.png")
            else:
                print("⚠️ Pulsante 'Privati' non trovato, continuo comunque...")

            # STEP 4: Inserisci email
            print(f"\n📍 Step 4: Cerco il campo email...")

            email_field = None
            email_selectors = [
                "input[type='email']",
                "input[name*='email']",
                "input[name*='mail']",
                "input[id*='email']",
                "input[placeholder*='email']",
                "input[placeholder*='Email']",
                "input[placeholder*='E-mail']"
            ]

            for selector in email_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            email_field = elem
                            print(f"✓ Campo email trovato: {selector}")
                            break
                    if email_field:
                        break
                except:
                    continue

            if not email_field:
                print("❌ Campo email non trovato!")
                with open('debug_3_privati_selected.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                return False

            print(f"⌨️  Inserisco email: {self.email}")
            email_field.clear()
            email_field.send_keys(self.email)
            time.sleep(0.5)

            # STEP 5: Inserisci password
            print(f"\n📍 Step 5: Cerco il campo password...")

            password_field = None
            password_selectors = [
                "input[type='password']",
                "input[name*='password']",
                "input[name*='pass']",
                "input[id*='password']"
            ]

            for selector in password_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            password_field = elem
                            print(f"✓ Campo password trovato: {selector}")
                            break
                    if password_field:
                        break
                except:
                    continue

            if not password_field:
                print("❌ Campo password non trovato!")
                return False

            print(f"⌨️  Inserisco password: {'*' * len(self.password)}")
            password_field.clear()
            password_field.send_keys(self.password)
            time.sleep(0.5)

            self.driver.save_screenshot('debug_4_credentials_filled.png')
            print("📸 Screenshot: debug_4_credentials_filled.png")

            # STEP 6: Clicca "Accedi"
            print(f"\n📍 Step 6: Cerco il pulsante 'Accedi' finale...")

            submit_selectors = [
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//button[contains(text(), 'Accedi')]",
                "//button[contains(text(), 'Login')]",
                "//button[contains(text(), 'Entra')]",
                "//a[contains(text(), 'Accedi')]"
            ]

            submit_button = None
            for selector in submit_selectors:
                try:
                    if selector.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, selector)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                    for elem in elements:
                        if elem.is_displayed():
                            submit_button = elem
                            print(f"✓ Pulsante submit trovato: {selector}")
                            break
                    if submit_button:
                        break
                except:
                    continue

            if submit_button:
                print("🖱️  Clicco su 'Accedi'...")
                try:
                    submit_button.click()
                except:
                    try:
                        self.driver.execute_script("arguments[0].click();", submit_button)
                    except:
                        print("⚠️ Click fallito, provo con INVIO...")
                        password_field.send_keys(Keys.RETURN)
            else:
                print("⚠️ Pulsante submit non trovato, provo con INVIO...")
                password_field.send_keys(Keys.RETURN)

            # STEP 7: Attendi e verifica login
            print(f"\n📍 Step 7: Attendo completamento login...")
            time.sleep(5)

            self.driver.save_screenshot('debug_5_post_login.png')
            print("📸 Screenshot: debug_5_post_login.png")

            # Verifica se il login è riuscito
            current_url = self.driver.current_url
            page_source = self.driver.page_source.lower()

            success_indicators = [
                'logout' in page_source,
                'esci' in page_source,
                'profilo' in page_source,
                'account' in page_source,
                self.email.split('@')[0].lower() in page_source
            ]

            if any(success_indicators):
                print("✅ Login completato con successo!\n")
                return True
            else:
                print("⚠️ Login potrebbe non essere riuscito, ma procedo...\n")
                return True

        except Exception as e:
            print(f"❌ Errore durante il login: {e}")
            import traceback
            traceback.print_exc()
            return False

    def search_by_city(self, city="Roma"):
        """Esegue la ricerca dopo il login"""
        try:
            print(f"🔍 RICERCA IMMOBILI A {city.upper()}")
            print("-" * 60)

            time.sleep(3)

            # STEP 1: Cerca il campo indirizzo
            print(f"\n📍 Cerco il campo 'Indirizzo'...")

            indirizzo_field = None
            indirizzo_selectors = [
                "input[name*='indirizzo']",
                "input[placeholder*='indirizzo']",
                "input[placeholder*='Indirizzo']",
                "input[name*='address']",
                "input[name*='location']",
                "input[name*='city']",
                "input[name*='citta']",
                "input[id*='indirizzo']",
                "input[id*='search']",
                "input.search-location",
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
                                print(f"   placeholder: {placeholder}")
                                print(f"   name: {name}")
                                break
                    if indirizzo_field:
                        break
                except:
                    continue

            if not indirizzo_field:
                print("❌ Campo indirizzo non trovato!")
                print("\n🔍 Cerco TUTTI gli input visibili...")
                all_inputs = self.driver.find_elements(By.TAG_NAME, "input")
                visible_inputs = [inp for inp in all_inputs if inp.is_displayed()]
                print(f"Trovati {len(visible_inputs)} input visibili:")
                for idx, inp in enumerate(visible_inputs[:10], 1):
                    print(
                        f"{idx}. type={inp.get_attribute('type')}, name={inp.get_attribute('name')}, placeholder={inp.get_attribute('placeholder')}")

                self.driver.save_screenshot('debug_6_search_page.png')
                with open('debug_6_search_page.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                return None, []

            # STEP 2: Inserisci la città
            print(f"\n⌨️  Inserisco '{city}' nel campo...")
            indirizzo_field.clear()
            time.sleep(0.5)
            indirizzo_field.send_keys(city)
            time.sleep(2)

            self.driver.save_screenshot('debug_7_city_typed.png')
            print("📸 Screenshot: debug_7_city_typed.png")

            # STEP 3: Cerca il pulsante "Cerca"
            print(f"\n🔘 Cerco il pulsante 'Cerca'...")

            cerca_button = None
            cerca_selectors = [
                "//button[contains(text(), 'Cerca')]",
                "//button[contains(text(), 'CERCA')]",
                "//input[@value='Cerca']",
                "//button[@type='submit']",
                "button[type='submit']",
                "button.search-button",
                "button.btn-search"
            ]

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

            # STEP 4: Clicca o premi INVIO
            if cerca_button:
                print("🖱️  Clicco su 'Cerca'...")
                try:
                    cerca_button.click()
                except Exception as e1:
                    print(f"⚠️ Click normale fallito: {e1}")
                    try:
                        self.driver.execute_script("arguments[0].click();", cerca_button)
                        print("✓ JavaScript click riuscito")
                    except Exception as e2:
                        print(f"⚠️ JavaScript click fallito: {e2}")
                        print("⚠️ Uso INVIO...")
                        indirizzo_field.send_keys(Keys.RETURN)
            else:
                print("⚠️ Pulsante 'Cerca' non trovato, premo INVIO...")
                indirizzo_field.send_keys(Keys.RETURN)

            # STEP 5: Attendi risultati
            print(f"\n⏳ Attendo caricamento risultati...")
            time.sleep(5)

            self.driver.save_screenshot('debug_8_results.png')
            print("📸 Screenshot: debug_8_results.png")

            with open('debug_8_results.html', 'w', encoding='utf-8') as f:
                f.write(self.driver.page_source)
            print("📄 HTML salvato: debug_8_results.html")

            # STEP 6: Cerca i link con /vendita-
            print(f"\n🔗 Cerco link con '/vendita-' nell'HTML...")
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            vendita_links = soup.find_all('a', href=re.compile(r'/vendita-', re.I))

            print(f"✅ Trovati {len(vendita_links)} link '/vendita-'")

            unique_urls = set()
            for link in vendita_links:
                href = link.get('href', '')
                if href and '/vendita-' in href:
                    if not href.startswith('http'):
                        href = self.base_url + href

                    if href.startswith('https://www.astegiudiziarie.it/vendita-'):
                        unique_urls.add(href)

            print(f"✅ {len(unique_urls)} URL unici validi trovati")
            print(f"   (filtrati solo: https://www.astegiudiziarie.it/vendita-*)\n")

            if unique_urls:
                print("📋 Primi 5 URL trovati:")
                for idx, url in enumerate(list(unique_urls)[:5], 1):
                    print(f"   {idx}. {url}")
                print()

            print("\n✅ Ricerca completata!\n")
            return self.driver.page_source, list(unique_urls)

        except Exception as e:
            print(f"❌ Errore durante la ricerca: {e}")
            import traceback
            traceback.print_exc()
            return None, []

    def check_immobile_exists(self, url):
        """Controlla se un immobile è già presente nel database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT id, titolo, data_inserimento FROM aste WHERE url = ?', (url,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return {'exists': True, 'id': result[0], 'titolo': result[1], 'data_inserimento': result[2]}
        return {'exists': False}

    def extract_section_data(self, soup, section_title):
        """Estrae i dati da una sezione specifica (Dati del lotto, Dati dei beni, ecc.)"""
        data = {}

        # Cerca l'intestazione della sezione
        section_headers = soup.find_all(['h2', 'h3', 'h4', 'div', 'span'],
                                        string=re.compile(section_title, re.I))

        for header in section_headers:
            # Trova il contenitore della sezione
            section_container = header.find_parent(['div', 'section', 'article'])

            if section_container:
                # Cerca tutti i campi chiave-valore
                # Pattern 1: <dt>Chiave</dt><dd>Valore</dd>
                dts = section_container.find_all('dt')
                for dt in dts:
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        key = dt.get_text(strip=True).replace(':', '')
                        value = dd.get_text(strip=True)
                        if key and value:
                            data[key] = value

                # Pattern 2: <label>Chiave:</label> <span>Valore</span>
                labels = section_container.find_all('label')
                for label in labels:
                    key = label.get_text(strip=True).replace(':', '')
                    value_elem = label.find_next_sibling(['span', 'div', 'p'])
                    if value_elem:
                        value = value_elem.get_text(strip=True)
                        if key and value:
                            data[key] = value

                # Pattern 3: <div class="field"><strong>Chiave:</strong> Valore</div>
                fields = section_container.find_all(['div', 'p'], class_=re.compile('field|item|row', re.I))
                for field in fields:
                    strong = field.find('strong')
                    if strong:
                        key = strong.get_text(strip=True).replace(':', '')
                        value = field.get_text(strip=True).replace(key, '').strip().replace(':', '').strip()
                        if key and value:
                            data[key] = value

                # Pattern 4: Testo con pattern "Chiave: Valore"
                text_content = section_container.get_text()
                patterns = re.findall(r'([A-Za-zÀ-ù\s]+):\s*([^\n]+)', text_content)
                for key, value in patterns:
                    key = key.strip()
                    value = value.strip()
                    if key and value and len(key) < 50:
                        data[key] = value

                break

        return data

    def parse_detail_page(self, soup, url):
        """Analizza la pagina dettaglio ed estrae tutti i dati strutturati"""
        immobile = {'url': url, 'data_inserimento': datetime.now().isoformat()}

        print(f"\n📋 ANALISI SEZIONI STRUTTURATE")
        print("-" * 60)

        # **Dati del lotto**
        print("\n🏷️  Estrazione: Dati del lotto...")
        dati_lotto = self.extract_section_data(soup, r'Dati\s+del\s+lotto')
        if dati_lotto:
            print(f"   ✓ Trovati {len(dati_lotto)} campi")
            for key, value in list(dati_lotto.items())[:3]:
                print(f"     • {key}: {value}")

            # Mappa i dati del lotto
            if 'Lotto' in dati_lotto or 'Numero lotto' in dati_lotto:
                immobile['lotto'] = dati_lotto.get('Lotto') or dati_lotto.get('Numero lotto')
            if 'Descrizione' in dati_lotto:
                immobile['descrizione_breve'] = dati_lotto['Descrizione'][:500]
            if 'Categoria' in dati_lotto or 'Tipologia' in dati_lotto:
                immobile['tipo_immobile'] = dati_lotto.get('Categoria') or dati_lotto.get('Tipologia')

        # **Dati dei beni**
        print("\n🏠 Estrazione: Dati dei beni...")
        dati_beni = self.extract_section_data(soup, r'Dati\s+dei\s+beni')
        if dati_beni:
            print(f"   ✓ Trovati {len(dati_beni)} campi")
            for key, value in list(dati_beni.items())[:3]:
                print(f"     • {key}: {value}")

            # Mappa i dati dei beni
            if 'Indirizzo' in dati_beni or 'Via' in dati_beni:
                immobile['indirizzo'] = dati_beni.get('Indirizzo') or dati_beni.get('Via')
            if 'Città' in dati_beni or 'Comune' in dati_beni:
                immobile['citta'] = dati_beni.get('Città') or dati_beni.get('Comune')
            if 'CAP' in dati_beni or 'Codice Postale' in dati_beni:
                immobile['cap'] = dati_beni.get('CAP') or dati_beni.get('Codice Postale')
            if 'Superficie' in dati_beni or 'Mq' in dati_beni:
                immobile['superficie'] = dati_beni.get('Superficie') or dati_beni.get('Mq')
            if 'Locali' in dati_beni or 'Vani' in dati_beni:
                try:
                    locali_str = dati_beni.get('Locali') or dati_beni.get('Vani')
                    immobile['numero_locali'] = int(re.search(r'\d+', locali_str).group())
                except:
                    pass
            if 'Bagni' in dati_beni:
                try:
                    immobile['numero_bagni'] = int(re.search(r'\d+', dati_beni['Bagni']).group())
                except:
                    pass
            if 'Piano' in dati_beni:
                immobile['piano'] = dati_beni['Piano']
            if 'Stato' in dati_beni or 'Condizioni' in dati_beni:
                immobile['stato'] = dati_beni.get('Stato') or dati_beni.get('Condizioni')

            # Dati catastali dai beni
            if 'Foglio' in dati_beni:
                immobile['foglio'] = dati_beni['Foglio']
            if 'Particella' in dati_beni or 'Mappale' in dati_beni:
                immobile['particella'] = dati_beni.get('Particella') or dati_beni.get('Mappale')
            if 'Subalterno' in dati_beni or 'Sub' in dati_beni:
                immobile['subalterno'] = dati_beni.get('Subalterno') or dati_beni.get('Sub')
            if 'Categoria' in dati_beni or 'Categoria catastale' in dati_beni:
                immobile['categoria'] = dati_beni.get('Categoria') or dati_beni.get('Categoria catastale')
            if 'Rendita' in dati_beni or 'Rendita catastale' in dati_beni:
                immobile['rendita'] = dati_beni.get('Rendita') or dati_beni.get('Rendita catastale')

        # **Dati della vendita**
        print("\n💰 Estrazione: Dati della vendita...")
        dati_vendita = self.extract_section_data(soup, r'Dati\s+della\s+vendita')
        if dati_vendita:
            print(f"   ✓ Trovati {len(dati_vendita)} campi")
            for key, value in list(dati_vendita.items())[:3]:
                print(f"     • {key}: {value}")

            # Mappa i dati della vendita
            if 'Prezzo base' in dati_vendita or 'Base d\'asta' in dati_vendita or 'Prezzo' in dati_vendita:
                immobile['prezzo_asta'] = (dati_vendita.get('Prezzo base') or
                                           dati_vendita.get('Base d\'asta') or
                                           dati_vendita.get('Prezzo'))
            if 'Data asta' in dati_vendita or 'Data vendita' in dati_vendita:
                immobile['data_asta'] = dati_vendita.get('Data asta') or dati_vendita.get('Data vendita')
            if 'Ora' in dati_vendita or 'Orario' in dati_vendita:
                immobile['ora_asta'] = dati_vendita.get('Ora') or dati_vendita.get('Orario')
            if 'Tipo asta' in dati_vendita or 'Modalità' in dati_vendita:
                immobile['tipo_asta'] = dati_vendita.get('Tipo asta') or dati_vendita.get('Modalità')
            if 'Rilancio minimo' in dati_vendita or 'Offerta minima' in dati_vendita:
                immobile['rilancio_minimo'] = dati_vendita.get('Rilancio minimo') or dati_vendita.get('Offerta minima')

        # **Dettaglio della procedura e contatti**
        print("\n⚖️  Estrazione: Dettaglio procedura e contatti...")
        dati_procedura = self.extract_section_data(soup, r'Dettaglio\s+della\s+procedura')
        if dati_procedura:
            print(f"   ✓ Trovati {len(dati_procedura)} campi")
            for key, value in list(dati_procedura.items())[:3]:
                print(f"     • {key}: {value}")

            # Mappa i dati della procedura
            if 'Tribunale' in dati_procedura:
                immobile['tribunale'] = dati_procedura['Tribunale']
            if 'RGE' in dati_procedura or 'Numero RGE' in dati_procedura or 'Proc. Esec.' in dati_procedura:
                immobile['rge'] = (dati_procedura.get('RGE') or
                                   dati_procedura.get('Numero RGE') or
                                   dati_procedura.get('Proc. Esec.'))
            if 'Giudice' in dati_procedura or 'Giudice delegato' in dati_procedura:
                immobile['giudice'] = dati_procedura.get('Giudice') or dati_procedura.get('Giudice delegato')
            if 'Custode' in dati_procedura or 'Custode giudiziario' in dati_procedura:
                immobile['custode'] = dati_procedura.get('Custode') or dati_procedura.get('Custode giudiziario')
            if 'Professionista delegato' in dati_procedura or 'Delegato' in dati_procedura:
                immobile['delegato'] = dati_procedura.get('Professionista delegato') or dati_procedura.get('Delegato')
            if 'Telefono' in dati_procedura or 'Tel' in dati_procedura:
                immobile['telefono'] = dati_procedura.get('Telefono') or dati_procedura.get('Tel')
            if 'Email' in dati_procedura or 'E-mail' in dati_procedura:
                immobile['email'] = dati_procedura.get('Email') or dati_procedura.get('E-mail')

        # Estrazione aggiuntiva da testo libero (fallback)
        full_text = soup.get_text()

        # Titolo
        if 'titolo' not in immobile:
            title_elem = soup.find(['h1', 'h2'], class_=re.compile('title|titolo|heading', re.I))
            if not title_elem:
                title_elem = soup.find('h1')
            if title_elem:
                immobile['titolo'] = title_elem.get_text(strip=True)

        # Città (se non trovata)
        if 'citta' not in immobile:
            city_match = re.search(r'(?:Comune|Città|Località)[\s:]*([A-Za-zÀ-ù\s]+?)(?:\(([A-Z]{2})\))?', full_text,
                                   re.I)
            if city_match:
                immobile['citta'] = city_match.group(1).strip()

        # Indirizzo (se non trovato)
        if 'indirizzo' not in immobile:
            addr_match = re.search(
                r'(?:via|viale|piazza|corso|contrada|località|loc\.?|frazione|fraz\.?)\s+[^\n,]{5,80}', full_text, re.I)
            if addr_match:
                immobile['indirizzo'] = addr_match.group(0).strip()

        # CAP (se non trovato)
        if 'cap' not in immobile:
            cap_match = re.search(r'\b(\d{5})\b', full_text)
            if cap_match:
                immobile['cap'] = cap_match.group(1)

        # Prezzo (se non trovato)
        if 'prezzo_asta' not in immobile:
            price_patterns = [
                r'(?:Prezzo|Base)\s+(?:d[\'i]?\s*)?asta[\s:]*€?\s*([\d.,]+)',
                r'Base\s+d[\'i]?\s*asta[\s:]*€?\s*([\d.,]+)',
                r'Prezzo[\s:]*€?\s*([\d.,]+)'
            ]
            for pattern in price_patterns:
                price_match = re.search(pattern, full_text, re.I)
                if price_match:
                    immobile['prezzo_asta'] = f"€{price_match.group(1)}"
                    break

        # Descrizione completa
        if 'descrizione_completa' not in immobile:
            desc_sections = soup.find_all(['div', 'p'], class_=re.compile('desc|text|content', re.I))
            desc_texts = []
            for section in desc_sections:
                text = section.get_text(strip=True)
                if len(text) > 100:
                    desc_texts.append(text)
            if desc_texts:
                immobile['descrizione_completa'] = ' '.join(desc_texts[:2])[:1000]

        # Tipo immobile e vendita
        if 'tipo_immobile' not in immobile:
            immobile['tipo_immobile'] = 'Immobile'
        immobile['tipo_vendita'] = 'Asta Giudiziaria'

        print(f"\n✅ Estrazione dati completata")
        print(f"   📊 Campi estratti: {len([k for k, v in immobile.items() if v])}")

        return immobile

    def save_to_json(self, immobile, output_dir='immobili_json'):
        """Salva in formato JSON strutturato"""
        Path(output_dir).mkdir(exist_ok=True)

        titolo_safe = re.sub(r'[^\w\s-]', '', immobile.get('titolo', 'immobile'))[:50]
        titolo_safe = re.sub(r'[-\s]+', '_', titolo_safe)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/{titolo_safe}_{timestamp}.json"

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
                'citta': immobile.get('citta'),
                'cap': immobile.get('cap'),
                'zona': immobile.get('zona')
            },
            'prezzi': {
                'prezzo_asta': immobile.get('prezzo_asta'),
                'rilancio_minimo': immobile.get('rilancio_minimo')
            },
            'caratteristiche': {
                'superficie': immobile.get('superficie'),
                'numero_locali': immobile.get('numero_locali'),
                'numero_bagni': immobile.get('numero_bagni'),
                'piano': immobile.get('piano'),
                'stato': immobile.get('stato')
            },
            'descrizione': {
                'breve': immobile.get('descrizione_breve'),
                'completa': immobile.get('descrizione_completa')
            },
            'informazioni_asta': {
                'data_asta': immobile.get('data_asta'),
                'ora_asta': immobile.get('ora_asta'),
                'tipo_asta': immobile.get('tipo_asta'),
                'tribunale': immobile.get('tribunale'),
                'rge': immobile.get('rge'),
                'lotto': immobile.get('lotto')
            },
            'dati_catastali': {
                'foglio': immobile.get('foglio'),
                'particella': immobile.get('particella'),
                'subalterno': immobile.get('subalterno'),
                'categoria': immobile.get('categoria'),
                'rendita': immobile.get('rendita')
            },
            'procedura': {
                'giudice': immobile.get('giudice'),
                'custode': immobile.get('custode'),
                'delegato': immobile.get('delegato')
            },
            'contatti': {
                'telefono': immobile.get('telefono'),
                'email': immobile.get('email')
            }
        }

        json_data = self._remove_empty_fields(json_data)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f"  ✓ JSON: {filename}")
        return filename

    def _remove_empty_fields(self, data):
        """Rimuove campi vuoti"""
        if isinstance(data, dict):
            return {k: self._remove_empty_fields(v) for k, v in data.items() if v not in [None, '', {}, []]}
        elif isinstance(data, list):
            return [self._remove_empty_fields(item) for item in data if item]
        return data

    def save_to_db(self, immobile):
        """Salva nel database con tutti i nuovi campi"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            # Verifica/crea colonne aggiuntive se non esistono
            cursor.execute("PRAGMA table_info(aste)")
            existing_columns = [row[1] for row in cursor.fetchall()]

            new_columns = {
                'superficie': 'TEXT',
                'stato': 'TEXT',
                'ora_asta': 'TEXT',
                'tipo_asta': 'TEXT',
                'rilancio_minimo': 'TEXT',
                'subalterno': 'TEXT',
                'tribunale': 'TEXT',
                'rge': 'TEXT',
                'giudice': 'TEXT',
                'custode': 'TEXT',
                'delegato': 'TEXT',
                'email': 'TEXT',
                'zona': 'TEXT'
            }

            for col_name, col_type in new_columns.items():
                if col_name not in existing_columns:
                    cursor.execute(f'ALTER TABLE aste ADD COLUMN {col_name} {col_type}')
                    print(f"  📝 Colonna '{col_name}' aggiunta al database")

            cursor.execute('''
                INSERT OR REPLACE INTO aste (
                    titolo, tipo_immobile, tipo_vendita, url, data_inserimento,
                    indirizzo, indirizzo_completo, zona, citta, cap, 
                    prezzo_asta, superficie, numero_locali, numero_bagni, piano, stato,
                    descrizione_breve, descrizione_completa,
                    data_asta, ora_asta, tipo_asta, rilancio_minimo, lotto,
                    foglio, particella, subalterno, categoria, rendita,
                    tribunale, rge, giudice, custode, delegato,
                    telefono, email, json_completo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                immobile.get('titolo'),
                immobile.get('tipo_immobile'),
                immobile.get('tipo_vendita'),
                immobile.get('url'),
                immobile.get('data_inserimento'),
                immobile.get('indirizzo'),
                immobile.get('indirizzo'),  # indirizzo_completo
                immobile.get('zona'),
                immobile.get('citta'),
                immobile.get('cap'),
                immobile.get('prezzo_asta'),
                immobile.get('superficie'),
                immobile.get('numero_locali'),
                immobile.get('numero_bagni'),
                immobile.get('piano'),
                immobile.get('stato'),
                immobile.get('descrizione_breve'),
                immobile.get('descrizione_completa'),
                immobile.get('data_asta'),
                immobile.get('ora_asta'),
                immobile.get('tipo_asta'),
                immobile.get('rilancio_minimo'),
                immobile.get('lotto'),
                immobile.get('foglio'),
                immobile.get('particella'),
                immobile.get('subalterno'),
                immobile.get('categoria'),
                immobile.get('rendita'),
                immobile.get('tribunale'),
                immobile.get('rge'),
                immobile.get('giudice'),
                immobile.get('custode'),
                immobile.get('delegato'),
                immobile.get('telefono'),
                immobile.get('email'),
                json.dumps(immobile, ensure_ascii=False)
            ))

            conn.commit()
            print(f"  ✓ DB salvato (ID: {cursor.lastrowid})")
        except Exception as e:
            print(f"  ✗ Errore DB: {e}")
            import traceback
            traceback.print_exc()
        finally:
            conn.close()

    def scrape_all(self, city="Roma"):
        """Esegue lo scraping completo"""
        print(f"\n{'=' * 60}")
        print(f"SCRAPER ASTEGIUDIZIARIE.IT")
        print(f"Ricerca: {city}")
        print(f"{'=' * 60}\n")

        if not self.email or not self.password:
            print("❌ Credenziali mancanti!")
            print("Crea un file .env con:")
            print("ASTE_EMAIL=tua@email.com")
            print("ASTE_PASSWORD=tuapassword")
            return

        if not self.init_selenium():
            return

        try:
            # Login
            if not self.login():
                print("❌ Login fallito!")
                return

            # Ricerca
            result = self.search_by_city(city)

            if not result:
                print("❌ Ricerca fallita!")
                return

            html, vendita_urls = result

            if not vendita_urls:
                print("❌ Nessun link '/vendita-' trovato!")
                return

            print(f"\n{'=' * 60}")
            print(f"INIZIO DOWNLOAD DETTAGLI")
            print(f"{'=' * 60}\n")

            # Salva la finestra principale
            main_window = self.driver.current_window_handle
            print(f"💼 Finestra principale salvata")

            count_new = 0
            count_skipped = 0

            for idx, url in enumerate(vendita_urls, 1):
                print(f"\n{'=' * 60}")
                print(f"Immobile {idx}/{len(vendita_urls)}")
                print(f"🔗 URL: {url}")
                print(f"{'=' * 60}")

                # Controlla se esiste già
                check = self.check_immobile_exists(url)

                if check['exists']:
                    print(f"⏭️  SALTATO - Già presente nel DB")
                    print(f"   ID: {check['id']}")
                    print(f"   Titolo: {check['titolo']}")
                    count_skipped += 1
                    continue

                print(f"🆕 NUOVO - Scarico dettagli completi...")

                # Apri nuova finestra
                self.driver.execute_script("window.open('');")
                time.sleep(0.5)

                # Passa alla nuova finestra
                windows = self.driver.window_handles
                detail_window = windows[-1]
                self.driver.switch_to.window(detail_window)

                try:
                    self.driver.get(url)
                    time.sleep(3)

                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                    # Usa il nuovo parser strutturato
                    immobile = self.parse_detail_page(soup, url)

                    # Salva
                    self.save_to_json(immobile)
                    self.save_to_db(immobile)
                    count_new += 1

                    print(f"\n✅ Salvato con successo!")
                    print(f"   📌 Titolo: {immobile.get('titolo', 'N/A')}")
                    print(f"   📍 Città: {immobile.get('citta', 'N/A')}")
                    print(f"   💰 Prezzo: {immobile.get('prezzo_asta', 'N/A')}")

                except Exception as e:
                    print(f"❌ Errore durante il download: {e}")
                    import traceback
                    traceback.print_exc()

                finally:
                    # Chiudi finestra dettagli
                    try:
                        self.driver.close()
                        print(f"🗑️  Finestra dettagli chiusa")
                    except:
                        pass

                    # Torna alla finestra principale
                    try:
                        self.driver.switch_to.window(main_window)
                        print(f"↩️  Tornato alla finestra principale")
                    except:
                        pass

            print(f"\n{'=' * 60}")
            print(f"COMPLETATO!")
            print(f"{'=' * 60}")
            print(f"📊 Statistiche:")
            print(f"   • Totale URL: {len(vendita_urls)}")
            print(f"   • Nuovi scaricati: {count_new}")
            print(f"   • Già presenti: {count_skipped}")
            print(f"💾 Database: {self.db_name}")
            print(f"📁 JSON: immobili_json/")
            print(f"{'=' * 60}\n")

        finally:
            if self.driver:
                print("🔚 Chiudo il browser...")
                self.driver.quit()


def main():
    scraper = AsteGiudiziarieItScraper()

    # Città da cercare
    city = "Roma"
    # city = "Milano"
    # city = "Napoli"

    scraper.scrape_all(city)


if __name__ == "__main__":
    main()