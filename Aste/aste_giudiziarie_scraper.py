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

            # Attendi che la pagina sia stabile
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
                            # Verifica che sia un campo sensato
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
                return None

            # STEP 2: Inserisci la città
            print(f"\n⌨️  Inserisco '{city}' nel campo...")
            indirizzo_field.clear()
            time.sleep(0.5)
            indirizzo_field.send_keys(city)
            time.sleep(2)  # Attendi suggerimenti autocomplete

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

            # Trova tutti i link che contengono '/vendita-'
            vendita_links = soup.find_all('a', href=re.compile(r'/vendita-', re.I))

            print(f"✅ Trovati {len(vendita_links)} link '/vendita-'")

            # Estrai gli URL univoci e filtra solo quelli validi
            unique_urls = set()
            for link in vendita_links:
                href = link.get('href', '')
                if href and '/vendita-' in href:
                    # Costruisci URL completo
                    if not href.startswith('http'):
                        href = self.base_url + href

                    # FILTRA: accetta SOLO se inizia con https://www.astegiudiziarie.it/vendita-
                    if href.startswith('https://www.astegiudiziarie.it/vendita-'):
                        unique_urls.add(href)

            print(f"✅ {len(unique_urls)} URL unici validi trovati")
            print(f"   (filtrati solo: https://www.astegiudiziarie.it/vendita-*)\n")

            # Mostra i primi 5 per debug
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

    def parse_immobile_list(self, element):
        """Estrae i dati dalla lista annunci"""
        immobile = {}

        try:
            link = element.find('a', href=True)
            if link and 'href' in link.attrs:
                href = link['href']
                if not href.startswith('http'):
                    href = self.base_url + href
                immobile['url'] = href

            title_elem = element.find(['h2', 'h3', 'h4', 'h5'])
            if not title_elem:
                title_elem = element.find('a')
            if title_elem:
                immobile['titolo'] = title_elem.get_text(strip=True)

            full_text = element.get_text()

            city_match = re.search(r'([A-Za-zÀ-ù\s]+)\s*\(([A-Z]{2})\)', full_text)
            if city_match:
                immobile['citta'] = city_match.group(1).strip()

            price_match = re.search(r'€\s*([\d.,]+)', full_text)
            if price_match:
                immobile['prezzo_asta'] = f"€{price_match.group(1)}"

            tribunale_match = re.search(r'Tribunale\s+(?:di\s+)?([A-Za-zÀ-ù\s]+)', full_text, re.I)
            if tribunale_match:
                immobile['tribunale'] = tribunale_match.group(1).strip()

            proc_match = re.search(r'(?:Proc|RGE)[\s\.]*(\d+/\d+)', full_text, re.I)
            if proc_match:
                immobile['rge'] = proc_match.group(1)

            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', full_text)
            if date_match:
                immobile['data_asta'] = date_match.group(1)

            lotto_match = re.search(r'Lotto[\s:]*(\d+)', full_text, re.I)
            if lotto_match:
                immobile['lotto'] = lotto_match.group(1)

            immobile['tipo_immobile'] = 'Immobile'
            immobile['tipo_vendita'] = 'Asta Giudiziaria'
            immobile['data_inserimento'] = datetime.now().isoformat()

            return immobile if immobile.get('url') else None

        except Exception as e:
            print(f"Errore nel parsing: {e}")
            return None

    def scrape_detail_page(self, url):
        """Scarica i dettagli completi (NON USATA - logica spostata in scrape_all)"""
        pass

    def save_to_json(self, immobile, output_dir='immobili_json'):
        """Salva in formato JSON"""
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
                'cap': immobile.get('cap')
            },
            'prezzi': {
                'prezzo_asta': immobile.get('prezzo_asta')
            },
            'caratteristiche': {
                'numero_locali': immobile.get('numero_locali'),
                'numero_bagni': immobile.get('numero_bagni'),
                'piano': immobile.get('piano')
            },
            'informazioni_asta': {
                'data_asta': immobile.get('data_asta'),
                'tribunale': immobile.get('tribunale'),
                'rge': immobile.get('rge'),
                'lotto': immobile.get('lotto')
            },
            'dati_catastali': {
                'foglio': immobile.get('foglio'),
                'particella': immobile.get('particella')
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
        """Salva nel database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO aste (
                    titolo, tipo_immobile, tipo_vendita, url, data_inserimento,
                    indirizzo, citta, cap, prezzo_asta, numero_locali, numero_bagni, piano,
                    data_asta, lotto, foglio, particella, telefono, json_completo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                immobile.get('titolo'), immobile.get('tipo_immobile'), immobile.get('tipo_vendita'),
                immobile.get('url'), immobile.get('data_inserimento'), immobile.get('indirizzo'),
                immobile.get('citta'), immobile.get('cap'), immobile.get('prezzo_asta'),
                immobile.get('numero_locali'), immobile.get('numero_bagni'), immobile.get('piano'),
                immobile.get('data_asta'), immobile.get('lotto'), immobile.get('foglio'),
                immobile.get('particella'), immobile.get('telefono'),
                json.dumps(immobile, ensure_ascii=False)
            ))
            conn.commit()
            print(f"  ✓ DB salvato")
        except Exception as e:
            print(f"  ✗ Errore DB: {e}")
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

                # Controlla se esiste già (senza aprire la pagina)
                check = self.check_immobile_exists(url)

                if check['exists']:
                    print(f"⏭️  SALTATO - Già presente nel DB")
                    print(f"   ID: {check['id']}")
                    print(f"   Titolo: {check['titolo']}")
                    count_skipped += 1
                    continue

                print(f"🆕 NUOVO - Scarico dettagli completi...")

                # Apri nuova finestra per questo immobile
                self.driver.execute_script("window.open('');")
                time.sleep(0.5)

                # Passa alla nuova finestra
                windows = self.driver.window_handles
                detail_window = windows[-1]  # Ultima finestra aperta
                self.driver.switch_to.window(detail_window)

                # Vai alla pagina dettaglio
                try:
                    self.driver.get(url)
                    time.sleep(3)

                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    immobile = {'url': url, 'data_inserimento': datetime.now().isoformat()}

                    # Estrai tutti i dati dalla pagina dettaglio
                    full_text = soup.get_text()

                    # Titolo
                    title_elem = soup.find(['h1', 'h2'], class_=re.compile('title|titolo|heading', re.I))
                    if not title_elem:
                        title_elem = soup.find('h1')
                    if title_elem:
                        immobile['titolo'] = title_elem.get_text(strip=True)
                    else:
                        immobile['titolo'] = f"Asta Immobile {idx}"

                    print(f"📌 Titolo: {immobile['titolo']}")

                    # Città
                    city_match = re.search(r'(?:Comune|Città|Località)[\s:]*([A-Za-zÀ-ù\s]+?)(?:\(([A-Z]{2})\))?',
                                           full_text, re.I)
                    if city_match:
                        immobile['citta'] = city_match.group(1).strip()
                        print(f"📍 Città: {immobile['citta']}")

                    # Indirizzo
                    addr_match = re.search(
                        r'(?:via|viale|piazza|corso|contrada|località|loc\.?|frazione|fraz\.?)\s+[^\n,]{5,80}',
                        full_text, re.I)
                    if addr_match:
                        immobile['indirizzo'] = addr_match.group(0).strip()
                        print(f"🏠 Indirizzo: {immobile['indirizzo']}")

                    # CAP
                    cap_match = re.search(r'\b(\d{5})\b', full_text)
                    if cap_match:
                        immobile['cap'] = cap_match.group(1)

                    # Prezzo base d'asta
                    price_patterns = [
                        r'(?:Prezzo|Base)\s+(?:d[\'i]?\s*)?asta[\s:]*€?\s*([\d.,]+)',
                        r'Base\s+d[\'i]?\s*asta[\s:]*€?\s*([\d.,]+)',
                        r'Prezzo[\s:]*€?\s*([\d.,]+)'
                    ]
                    for pattern in price_patterns:
                        price_match = re.search(pattern, full_text, re.I)
                        if price_match:
                            immobile['prezzo_asta'] = f"€{price_match.group(1)}"
                            print(f"💰 Prezzo: {immobile['prezzo_asta']}")
                            break

                    # Tribunale
                    tribunale_match = re.search(r'Tribunale\s+(?:di\s+)?([A-Za-zÀ-ù\s]+)', full_text, re.I)
                    if tribunale_match:
                        immobile['tribunale'] = tribunale_match.group(1).strip()
                        print(f"⚖️  Tribunale: {immobile['tribunale']}")

                    # RGE/Procedura
                    rge_patterns = [
                        r'(?:RGE|R\.G\.E\.|Proc\.?|Procedura|Esec\.?)[\s\.:n°]*(\d+/\d+)',
                        r'(?:n\.?\s*)?(\d+/\d{4})'
                    ]
                    for pattern in rge_patterns:
                        rge_match = re.search(pattern, full_text, re.I)
                        if rge_match:
                            immobile['rge'] = rge_match.group(1)
                            print(f"📋 RGE: {immobile['rge']}")
                            break

                    # Data asta
                    date_match = re.search(r'(\d{2}/\d{2}/\d{4})', full_text)
                    if date_match:
                        immobile['data_asta'] = date_match.group(1)
                        print(f"📅 Data asta: {immobile['data_asta']}")

                    # Lotto
                    lotto_match = re.search(r'Lotto[\s:n°]*(\d+)', full_text, re.I)
                    if lotto_match:
                        immobile['lotto'] = lotto_match.group(1)
                        print(f"🏷️  Lotto: {immobile['lotto']}")

                    # Caratteristiche immobile
                    locali_match = re.search(r'(\d+)\s*(?:vani|local[ie]|stanze|camere)', full_text, re.I)
                    if locali_match:
                        immobile['numero_locali'] = int(locali_match.group(1))
                        print(f"🚪 Locali: {immobile['numero_locali']}")

                    bagni_match = re.search(r'(\d+)\s*bagn[io]', full_text, re.I)
                    if bagni_match:
                        immobile['numero_bagni'] = int(bagni_match.group(1))
                        print(f"🚿 Bagni: {immobile['numero_bagni']}")

                    piano_match = re.search(r'piano\s*([TtSs0-9]+|terra|primo|secondo|terzo|quarto|quinto)', full_text,
                                            re.I)
                    if piano_match:
                        immobile['piano'] = piano_match.group(1)
                        print(f"🏢 Piano: {immobile['piano']}")

                    # Superficie
                    superficie_match = re.search(r'(?:superficie|mq|m²|metri\s+quadr)[\s:]*(\d+)', full_text, re.I)
                    if superficie_match:
                        immobile['superficie'] = superficie_match.group(1)
                        print(f"📐 Superficie: {immobile['superficie']} mq")

                    # Dati catastali
                    foglio_match = re.search(r'foglio[\s\.:n°]*(\d+)', full_text, re.I)
                    if foglio_match:
                        immobile['foglio'] = foglio_match.group(1)

                    particella_match = re.search(r'(?:particella|part\.?)[\s\.:n°]*(\d+)', full_text, re.I)
                    if particella_match:
                        immobile['particella'] = particella_match.group(1)

                    subalterno_match = re.search(r'(?:subalterno|sub\.?)[\s\.:n°]*(\d+)', full_text, re.I)
                    if subalterno_match:
                        immobile['subalterno'] = subalterno_match.group(1)

                    categoria_match = re.search(r'categoria[\s\.:]*([A-Z]/\d+|[CDE]/\d+)', full_text, re.I)
                    if categoria_match:
                        immobile['categoria'] = categoria_match.group(1)

                    rendita_match = re.search(r'rendita[\s\.:]*€?\s*([\d.,]+)', full_text, re.I)
                    if rendita_match:
                        immobile['rendita'] = rendita_match.group(1)

                    # Descrizione
                    desc_sections = soup.find_all(['div', 'p'], class_=re.compile('desc|text|content', re.I))
                    desc_texts = []
                    for section in desc_sections:
                        text = section.get_text(strip=True)
                        if len(text) > 100:
                            desc_texts.append(text)
                    if desc_texts:
                        immobile['descrizione_completa'] = ' '.join(desc_texts[:2])[:1000]
                        immobile['descrizione_breve'] = desc_texts[0][:500] if desc_texts else None

                    # Telefono/Contatti
                    tel_match = re.search(r'(?:tel|telefono|cell)[\s\.:]*(\+?\d[\d\s\.-]{8,})', full_text, re.I)
                    if tel_match:
                        immobile['telefono'] = tel_match.group(1).strip()

                    # Tipo immobile e vendita
                    immobile['tipo_immobile'] = 'Immobile'
                    immobile['tipo_vendita'] = 'Asta Giudiziaria'

                    # Salva
                    self.save_to_json(immobile)
                    self.save_to_db(immobile)
                    count_new += 1

                    print(f"\n✅ Salvato con successo!")

                except Exception as e:
                    print(f"❌ Errore durante il download: {e}")
                    import traceback
                    traceback.print_exc()

                finally:
                    # CHIUDI la finestra dettagli
                    try:
                        self.driver.close()
                        print(f"🗑️  Finestra dettagli chiusa")
                    except:
                        pass

                    # Torna SEMPRE alla finestra principale
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