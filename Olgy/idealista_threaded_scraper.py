#!/usr/bin/env python3
"""
File: idealista_threaded_scraper.py
Scraper multi-thread per Idealista.it - aste giudiziarie Roma
Un thread trova i link, l'altro estrae i dettagli
"""

import sqlite3
import json
import os
import re
import time
import random
import threading
from datetime import datetime
from queue import Queue, Empty
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class IdealistaThreadedScraper:
    def __init__(self):
        self.db_name = "idealista_aste_annunci.db"
        self.immobili_dir = "aste_giudiziarie"

        # Queue per comunicazione tra threads
        self.link_queue = Queue()
        self.processed_count = 0
        self.total_found = 0

        # Lock per thread safety
        self.db_lock = threading.Lock()
        self.stats_lock = threading.Lock()

        # Flag di controllo
        self.stop_flag = threading.Event()
        self.link_finder_done = threading.Event()

        # Crea directory per JSON
        os.makedirs(self.immobili_dir, exist_ok=True)

        # Inizializza database
        self.init_database()

        print("Idealista.it Aste Giudiziarie Multi-threaded Scraper inizializzato")
        print(f"Database: {self.db_name}")
        print(f"JSON Directory: {self.immobili_dir}/")

    def init_database(self):
        """Crea il database SQLite con tutte le colonne necessarie per aste giudiziarie"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aste_annunci (
                id TEXT PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                titolo TEXT,
                descrizione TEXT,
                prezzo_base TEXT,
                prezzo_base_euro INTEGER,
                prezzo_vendita TEXT,
                prezzo_vendita_euro INTEGER,
                tribunale TEXT,
                numero_procedura TEXT,
                numero_lotto TEXT,
                zona TEXT,
                indirizzo TEXT,
                locali TEXT,
                camere TEXT,
                bagni TEXT,
                superficie TEXT,
                mq INTEGER,
                piano TEXT,
                tipo_immobile TEXT,
                stato TEXT,
                anno_costruzione INTEGER,
                classe_energetica TEXT,
                box_auto TEXT,
                giardino TEXT,
                terrazzo TEXT,
                balcone TEXT,
                ascensore TEXT,
                cantina TEXT,
                data_asta TEXT,
                ora_asta TEXT,
                professionista TEXT,
                telefono_professionista TEXT,
                email_professionista TEXT,
                codice_riferimento TEXT,
                rialzo_minimo TEXT,
                deposito_cauzionale TEXT,
                commissioni TEXT,
                spese_vendita TEXT,
                occupato TEXT,
                nota_legali TEXT,
                data_inserimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_aggiornamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def get_existing_ids(self):
        """Recupera tutti gli ID già presenti nel database"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM aste_annunci")
            existing_ids = {row[0] for row in cursor.fetchall()}
            conn.close()
            print(f"ID già presenti nel database: {len(existing_ids)}")
            return existing_ids
        except Exception as e:
            print(f"Errore recupero ID esistenti: {e}")
            return set()

    def setup_selenium(self, headless=True):
        """Configura e avvia Selenium per Idealista"""
        options = Options()

        if headless:
            options.add_argument("--headless")

        # Opzioni anti-detection per Idealista
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # User agent realistico
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)

            # Rimuovi tracce di Selenium
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # Imposta timeouts
            driver.implicitly_wait(10)
            driver.set_page_load_timeout(30)

            return driver
        except Exception as e:
            print(f"Errore configurazione Selenium: {e}")
            return None

    def handle_cookies_and_popups(self, driver):
        """Gestisce cookie banner e popup di Idealista"""
        try:
            # Cookie banner
            cookie_selectors = [
                "#didomi-notice-agree-button",
                ".didomi-continue-without-agreeing",
                "#gdpr-ok",
                ".cookie-accept",
                "button[data-testid='TcfAccept']"
            ]

            for selector in cookie_selectors:
                try:
                    button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    button.click()
                    print("✅ Cookie banner gestito")
                    time.sleep(2)
                    break
                except:
                    continue

            # Popup newsletter/registrazione
            popup_selectors = [
                ".modal-close",
                ".close-modal",
                ".popup-close",
                "[data-testid='modal-close']"
            ]

            for selector in popup_selectors:
                try:
                    close_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    close_btn.click()
                    print("✅ Popup chiuso")
                    time.sleep(1)
                    break
                except:
                    continue

        except Exception as e:
            print(f"Gestione popup: {e}")

    def get_total_pages(self, driver):
        """Rileva automaticamente il numero totale di pagine per aste Idealista"""
        try:
            # Aspetta che la paginazione carichi
            time.sleep(3)

            # Selettori specifici per Idealista
            pagination_selectors = [
                ".pagination .current + a",
                ".pagination a:last-of-type",
                "[data-testid='pagination'] a:last-child",
                ".pagination li:last-child a"
            ]

            max_page = 1

            for selector in pagination_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text.isdigit():
                            max_page = max(max_page, int(text))
                except:
                    continue

            # Fallback: cerca nell'URL dei link di paginazione
            if max_page == 1:
                try:
                    page_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='pagina-']")
                    for link in page_links:
                        href = link.get_attribute('href') or ''
                        match = re.search(r'pagina-(\d+)', href)
                        if match:
                            max_page = max(max_page, int(match.group(1)))
                except:
                    pass

            # Se ancora non trova nulla, usa il numero dalla description
            if max_page == 1:
                try:
                    results_text = driver.find_element(By.CSS_SELECTOR, ".listing-title, .results-summary").text
                    numbers = re.findall(r'(\d+)', results_text)
                    if numbers:
                        total_results = int(numbers[0])
                        max_page = (total_results // 20) + 1  # Assumendo 20 risultati per pagina
                except:
                    pass

            return max_page if max_page > 0 else 500  # Fallback alto per aste

        except Exception as e:
            print(f"Errore rilevazione pagine: {e}")
            return 500  # Fallback alto

    def find_property_links(self, driver):
        """Trova tutti i link alle aste nella pagina corrente - specifica per Idealista basata su analisi HTML"""
        links = []

        try:
            # Scroll per caricare tutti gli elementi in modo progressivo
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

            print(f"   🔍 Cercando link immobili in struttura Idealista...")

            # ANALISI: Dal sorgente vedo che ogni immobile è in un <article> con data-adid
            # e i link sono del tipo href="/immobile/NUMERO/"

            # METODO 1: Cerca gli article con data-adid (struttura principale)
            try:
                articles_with_adid = driver.find_elements(By.CSS_SELECTOR, 'article[data-adid]')
                print(f"   📰 Trovati {len(articles_with_adid)} article con data-adid")

                for article in articles_with_adid:
                    try:
                        # Cerca link all'interno dell'article
                        article_links = article.find_elements(By.TAG_NAME, 'a')
                        for link in article_links:
                            href = link.get_attribute('href')
                            if href and '/immobile/' in href:
                                match = re.search(r'/immobile/(\d+)', href)
                                if match:
                                    property_id = match.group(1)
                                    # Costruisci URL completo se necessario
                                    if not href.startswith('http'):
                                        href = 'https://www.idealista.it' + href
                                    links.append({'id': property_id, 'url': href})
                                    print(f"     ✅ Article method: {property_id}")
                    except Exception as e:
                        continue

            except Exception as e:
                print(f"   ❌ Errore ricerca article: {e}")

            # METODO 2: Cerca direttamente tutti i link che contengono /immobile/
            if len(links) < 5:  # Se non ha trovato abbastanza con il metodo 1
                print(f"   🔄 Fallback: ricerca diretta link /immobile/")
                try:
                    # Dal sorgente vedo link del tipo: href="/immobile/123456789/"
                    immobile_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/immobile/"]')
                    print(f"   🔗 Trovati {len(immobile_links)} link con /immobile/")

                    for link in immobile_links:
                        href = link.get_attribute('href')
                        if href:
                            match = re.search(r'/immobile/(\d+)', href)
                            if match:
                                property_id = match.group(1)
                                # Costruisci URL completo se necessario
                                if not href.startswith('http'):
                                    href = 'https://www.idealista.it' + href
                                # Evita duplicati
                                if not any(l['id'] == property_id for l in links):
                                    links.append({'id': property_id, 'url': href})
                                    print(f"     ✅ Direct method: {property_id}")

                except Exception as e:
                    print(f"   ❌ Errore ricerca diretta: {e}")

            # METODO 3: JavaScript extraction - prova ad estrarre da JSON/script
            if len(links) < 3:  # Se ancora non ha trovato nulla
                print(f"   🔄 Metodo JavaScript: ricerca in script/JSON")
                try:
                    # Cerca script che contengono dati degli immobili
                    scripts = driver.find_elements(By.TAG_NAME, 'script')
                    for script in scripts:
                        script_content = script.get_attribute('innerHTML')
                        if script_content and 'immobile' in script_content:
                            # Cerca pattern di ID immobili nei script
                            id_matches = re.findall(r'"adid"\s*:\s*"?(\d+)"?', script_content, re.IGNORECASE)
                            if not id_matches:
                                id_matches = re.findall(r'/immobile/(\d+)', script_content)

                            for property_id in id_matches:
                                url = f"https://www.idealista.it/immobile/{property_id}/"
                                if not any(l['id'] == property_id for l in links):
                                    links.append({'id': property_id, 'url': url})
                                    print(f"     ✅ Script method: {property_id}")

                            if len(links) > 10:  # Limita per non sovraccaricare
                                break

                except Exception as e:
                    print(f"   ❌ Errore metodo JavaScript: {e}")

            # METODO 4: Ricerca basata su data-adid direttamente
            if len(links) < 2:
                print(f"   🔄 Metodo data-adid: estrazione diretta attributi")
                try:
                    elements_with_adid = driver.find_elements(By.CSS_SELECTOR, '[data-adid]')
                    print(f"   🏷️ Elementi con data-adid: {len(elements_with_adid)}")

                    for element in elements_with_adid:
                        adid = element.get_attribute('data-adid')
                        if adid and adid.isdigit():
                            url = f"https://www.idealista.it/immobile/{adid}/"
                            if not any(l['id'] == adid for l in links):
                                links.append({'id': adid, 'url': url})
                                print(f"     ✅ Data-adid method: {adid}")

                except Exception as e:
                    print(f"   ❌ Errore metodo data-adid: {e}")

            # Debug finale
            if len(links) == 0:
                print(f"   🔬 DEBUG: Nessun link trovato, analizzando pagina...")
                try:
                    page_source = driver.page_source
                    # Cerca pattern nel source
                    immobile_patterns = re.findall(r'/immobile/(\d+)', page_source)
                    adid_patterns = re.findall(r'data-adid["\s]*=["\']\s*(\d+)', page_source)

                    print(f"   📊 Pattern /immobile/ nel source: {len(set(immobile_patterns))}")
                    print(f"   📊 Pattern data-adid nel source: {len(set(adid_patterns))}")

                    # Mostra primi pattern trovati
                    if immobile_patterns:
                        unique_patterns = list(set(immobile_patterns))[:5]
                        print(f"   🔍 Primi ID trovati: {unique_patterns}")

                        for prop_id in unique_patterns:
                            url = f"https://www.idealista.it/immobile/{prop_id}/"
                            links.append({'id': prop_id, 'url': url})

                except Exception as e:
                    print(f"   ❌ Errore debug finale: {e}")

            # Rimuovi duplicati mantenendo l'ordine
            seen = set()
            unique_links = []
            for link in links:
                if link['id'] not in seen:
                    seen.add(link['id'])
                    unique_links.append(link)

            print(f"   📊 RISULTATO: {len(unique_links)} link unici trovati")

            # Mostra primi 3 link trovati per verifica
            if unique_links:
                print(f"   🔗 Primi link estratti:")
                for i, link in enumerate(unique_links[:3]):
                    print(f"     {i + 1}. ID {link['id']}: {link['url']}")

            return unique_links

        except Exception as e:
            print(f"❌ Errore ricerca link: {e}")
            return []

    def debug_page_structure(self, driver):
        """Debug della struttura della pagina per capire i selettori corretti"""
        try:
            print("\n🔬 === DEBUG STRUTTURA PAGINA ===")

            # Controlla titolo pagina
            title = driver.title
            print(f"📄 Titolo: {title}")

            # URL corrente
            current_url = driver.current_url
            print(f"🌐 URL: {current_url}")

            # Cerca classi comuni di Idealista
            common_classes = [
                '.items-container', '.item', '.item-link',
                '.listing-items', '.listing-item',
                '.search-list', '.search-item',
                '.property-item', '.property-link',
                '.auction-item', '.auction-link'
            ]

            for class_name in common_classes:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, class_name)
                    if elements:
                        print(f"✅ {class_name}: {len(elements)} elementi")
                        # Mostra alcuni attributi del primo elemento
                        if elements:
                            elem = elements[0]
                            classes = elem.get_attribute('class')
                            print(f"   Classi primo elemento: {classes}")
                    else:
                        print(f"❌ {class_name}: 0 elementi")
                except:
                    print(f"❌ {class_name}: errore")

            # Cerca tutti i link che contengono 'immobile' o numeri
            all_links = driver.find_elements(By.TAG_NAME, 'a')
            immobile_links = []

            for link in all_links:
                href = link.get_attribute('href')
                if href and ('immobile' in href or re.search(r'/\d+/', href)):
                    immobile_links.append(href)

            print(f"\n🔗 Link con 'immobile' o numeri: {len(immobile_links)}")
            for i, link in enumerate(immobile_links[:5]):  # Primi 5
                print(f"   {i + 1}. {link}")

            # Cerca elementi article (struttura comune di Idealista)
            articles = driver.find_elements(By.TAG_NAME, 'article')
            print(f"\n📰 Elementi <article>: {len(articles)}")

            if articles:
                # Analizza il primo article
                first_article = articles[0]
                article_html = first_article.get_attribute('outerHTML')[:500]
                print(f"   Primo article (primi 500 char):\n{article_html}")

            print("🔬 === FINE DEBUG ===\n")

        except Exception as e:
            print(f"❌ Errore debug: {e}")

    def link_finder_thread(self, headless=True):
        """Thread che trova tutti i link delle aste"""
        print("🔍 Thread Link Finder avviato per Idealista")

        driver = self.setup_selenium(headless)
        if not driver:
            print("❌ Errore configurazione Selenium per Link Finder")
            self.link_finder_done.set()
            return

        base_url = "https://www.idealista.it/vendita-case/roma-roma/con-aste_giudiziarie"
        existing_ids = self.get_existing_ids()

        try:
            # Vai alla prima pagina
            print(f"🌐 Navigando verso: {base_url}")
            driver.get(base_url)
            time.sleep(5)

            # Gestisci cookie e popup
            self.handle_cookies_and_popups(driver)

            # DEBUG: Analizza struttura della prima pagina
            self.debug_page_structure(driver)

            # Rileva numero totale pagine
            total_pages = self.get_total_pages(driver)
            print(f"📄 Pagine totali rilevate: {total_pages}")

            # Scrapa ogni pagina
            for page in range(1, total_pages + 1):
                if self.stop_flag.is_set():
                    break

                try:
                    print(f"🔍 Analizzando pagina {page}/{total_pages}")

                    # Vai alla pagina
                    if page > 1:
                        url = f"{base_url}/pagina-{page}"
                        driver.get(url)
                        time.sleep(4)

                        # Gestisci popup su pagine successive
                        self.handle_cookies_and_popups(driver)

                    # Trova link aste
                    property_links = self.find_property_links(driver)
                    new_links = []

                    for prop in property_links:
                        if prop['id'] not in existing_ids:
                            new_links.append(prop)
                            self.link_queue.put(prop)

                    with self.stats_lock:
                        self.total_found += len(new_links)

                    print(f"   ✅ Pagina {page}: {len(property_links)} totali, {len(new_links)} nuovi")

                    # Se non trova link per diverse pagine consecutive, potrebbe essere finito
                    if len(property_links) == 0:
                        print(f"   ⚠️ Nessun link trovato, potrebbero essere finite le aste")
                        if page > 5:  # Solo se non è una delle prime pagine
                            break

                    # Pausa variabile tra pagine
                    if page < total_pages:
                        pause = random.uniform(3, 6)
                        if page % 15 == 0:  # Pausa più lunga ogni 15 pagine
                            pause = random.uniform(8, 12)
                        time.sleep(pause)

                except Exception as e:
                    print(f"❌ Errore pagina {page}: {e}")
                    continue

        except Exception as e:
            print(f"❌ Errore generale Link Finder: {e}")

        finally:
            driver.quit()
            self.link_finder_done.set()
            print("🔍 Thread Link Finder completato")

    def extract_property_details(self, driver, property_url, property_id):
        """Estrae tutti i dettagli da una singola pagina asta Idealista"""
        try:
            # Vai alla pagina
            driver.get(property_url)
            time.sleep(random.uniform(3, 5))

            # Gestisci popup se necessario
            self.handle_cookies_and_popups(driver)

            # Inizializza dizionario risultato per aste giudiziarie
            data = {
                'id': property_id,
                'url': property_url,
                'titolo': '',
                'descrizione': '',
                'prezzo_base': '',
                'prezzo_base_euro': None,
                'prezzo_vendita': '',
                'prezzo_vendita_euro': None,
                'tribunale': '',
                'numero_procedura': '',
                'numero_lotto': '',
                'zona': '',
                'indirizzo': '',
                'locali': '',
                'camere': '',
                'bagni': '',
                'superficie': '',
                'mq': None,
                'piano': '',
                'tipo_immobile': '',
                'stato': '',
                'anno_costruzione': None,
                'classe_energetica': '',
                'box_auto': '',
                'giardino': '',
                'terrazzo': '',
                'balcone': '',
                'ascensore': '',
                'cantina': '',
                'data_asta': '',
                'ora_asta': '',
                'professionista': '',
                'telefono_professionista': '',
                'email_professionista': '',
                'codice_riferimento': '',
                'rialzo_minimo': '',
                'deposito_cauzionale': '',
                'commissioni': '',
                'spese_vendita': '',
                'occupato': '',
                'nota_legali': ''
            }

            # Attendi caricamento completo
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Estrai dati specifici per aste
            self.extract_title(driver, data)
            self.extract_auction_prices(driver, data)
            self.extract_auction_info(driver, data)
            self.extract_description(driver, data)
            self.extract_location(driver, data)
            self.extract_features(driver, data)
            self.extract_professional_info(driver, data)
            self.extract_legal_info(driver, data)

            return data

        except Exception as e:
            print(f"    ❌ Errore estrazione {property_id}: {e}")
            return None

    def extract_title(self, driver, data):
        """Estrae il titolo dell'asta"""
        selectors = [
            'h1[data-testid="property-title"]',
            '.property-title h1',
            'h1.main-title',
            'h1'
        ]
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.text.strip():
                    data['titolo'] = element.text.strip()
                    break
            except:
                continue

    def extract_auction_prices(self, driver, data):
        """Estrae prezzi specifici delle aste"""
        try:
            page_text = driver.page_source.lower()

            # Prezzo base d'asta
            price_patterns = [
                r'prezzo base[:\s]*€?\s*([\d.,]+)',
                r'base d\'asta[:\s]*€?\s*([\d.,]+)',
                r'importo base[:\s]*€?\s*([\d.,]+)'
            ]

            for pattern in price_patterns:
                match = re.search(pattern, page_text)
                if match:
                    price_str = match.group(1).replace(',', '').replace('.', '')
                    try:
                        data['prezzo_base_euro'] = int(price_str)
                        data['prezzo_base'] = f"€ {data['prezzo_base_euro']:,}".replace(',', '.')
                        break
                    except:
                        continue

            # Prezzo di vendita (se disponibile)
            sale_patterns = [
                r'prezzo vendita[:\s]*€?\s*([\d.,]+)',
                r'venduto a[:\s]*€?\s*([\d.,]+)'
            ]

            for pattern in sale_patterns:
                match = re.search(pattern, page_text)
                if match:
                    price_str = match.group(1).replace(',', '').replace('.', '')
                    try:
                        data['prezzo_vendita_euro'] = int(price_str)
                        data['prezzo_vendita'] = f"€ {data['prezzo_vendita_euro']:,}".replace(',', '.')
                        break
                    except:
                        continue

            # Fallback: cerca prezzi generici
            if not data['prezzo_base']:
                price_selectors = [
                    '.price',
                    '.auction-price',
                    '[data-testid="price"]',
                    '.property-price'
                ]

                for selector in price_selectors:
                    try:
                        element = driver.find_element(By.CSS_SELECTOR, selector)
                        text = element.text.strip()
                        if '€' in text:
                            data['prezzo_base'] = text
                            # Estrai valore numerico
                            numbers = re.findall(r'[\d.]+', text.replace(',', ''))
                            if numbers:
                                try:
                                    data['prezzo_base_euro'] = int(''.join(numbers).replace('.', ''))
                                except:
                                    pass
                            break
                    except:
                        continue

        except Exception as e:
            print(f"    ❌ Errore estrazione prezzi: {e}")

    def extract_auction_info(self, driver, data):
        """Estrae informazioni specifiche dell'asta"""
        try:
            page_text = driver.page_source

            # Tribunale
            tribunal_patterns = [
                r'tribunale[:\s]*([^<\n]+)',
                r'trib\.?\s*([^<\n]+)'
            ]

            for pattern in tribunal_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    data['tribunale'] = match.group(1).strip()[:100]
                    break

            # Numero procedura
            proc_patterns = [
                r'procedura[:\s]*n?[°]?\s*(\d+[/\-]?\d*)',
                r'proc\.?\s*n?[°]?\s*(\d+[/\-]?\d*)',
                r'rg[:\s]*n?[°]?\s*(\d+[/\-]?\d*)'
            ]

            for pattern in proc_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    data['numero_procedura'] = match.group(1).strip()
                    break

            # Numero lotto
            lot_patterns = [
                r'lotto[:\s]*n?[°]?\s*(\d+)',
                r'lotto[:\s]*([^<\n]+)'
            ]

            for pattern in lot_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    data['numero_lotto'] = match.group(1).strip()[:50]
                    break

            # Data e ora asta
            date_patterns = [
                r'data asta[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
                r'asta[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})'
            ]

            for pattern in date_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    data['data_asta'] = match.group(1).strip()
                    break

            # Rialzo minimo
            increment_patterns = [
                r'rialzo minimo[:\s]*€?\s*([\d.,]+)',
                r'rilanci[:\s]*€?\s*([\d.,]+)'
            ]

            for pattern in increment_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    data['rialzo_minimo'] = match.group(1).strip()
                    break

            # Deposito cauzionale
            deposit_patterns = [
                r'deposito[:\s]*€?\s*([\d.,]+)',
                r'cauzione[:\s]*€?\s*([\d.,]+)'
            ]

            for pattern in deposit_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    data['deposito_cauzionale'] = match.group(1).strip()
                    break

        except Exception as e:
            print(f"    ❌ Errore estrazione info asta: {e}")

    def extract_description(self, driver, data):
        """Estrae descrizione"""
        selectors = [
            '[data-testid="property-description"]',
            '.property-description',
            '.description',
            '.detail-description',
            '.expandable-text'
        ]
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.text.strip():
                    data['descrizione'] = element.text.strip()[:5000]  # Limite caratteri
                    break
            except:
                continue

    def extract_location(self, driver, data):
        """Estrae zona e indirizzo"""
        selectors = [
            '[data-testid="property-location"]',
            '.property-location',
            '.address',
            '.location',
            '.property-address'
        ]
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    data['indirizzo'] = text
                    if 'Roma' in text:
                        data['zona'] = text
                    break
            except:
                continue

    def extract_features(self, driver, data):
        """Estrae tutte le caratteristiche dall'intera pagina"""
        try:
            # Prendi tutto il testo della pagina
            page_text = driver.page_source.lower()

            # Pattern per caratteristiche specifiche
            patterns = {
                'locali': [r'(\d+)\s*locali', r'locali\s*(\d+)', r'(\d+)\s*vani'],
                'camere': [r'(\d+)\s*camer[ea]', r'camer[ea]\s*(\d+)'],
                'bagni': [r'(\d+)\s*bagn[io]', r'bagn[io]\s*(\d+)', r'(\d+)\s*servizi'],
                'superficie': [r'(\d+)\s*m[²q2]', r'superficie[:\s]*(\d+)', r'(\d+)\s*mq'],
                'piano': [r'piano\s*(\w+)', r'(\d+)[°º]\s*piano'],
                'anno': [r'anno\s*(\d{4})', r'costruito.*?(\d{4})'],
                'classe': [r'classe\s*energetica[:\s]*([a-g][+\-]?)']
            }

            # Applica pattern
            for key, pattern_list in patterns.items():
                for pattern in pattern_list:
                    match = re.search(pattern, page_text)
                    if match:
                        if key == 'locali':
                            data['locali'] = f"{match.group(1)} locali"
                        elif key == 'camere':
                            data['camere'] = f"{match.group(1)} camere"
                        elif key == 'bagni':
                            data['bagni'] = f"{match.group(1)} bagni"
                        elif key == 'superficie':
                            data['superficie'] = f"{match.group(1)} mq"
                            data['mq'] = int(match.group(1))
                        elif key == 'piano':
                            data['piano'] = f"Piano {match.group(1)}"
                        elif key == 'anno':
                            year = int(match.group(1))
                            if 1800 <= year <= 2030:
                                data['anno_costruzione'] = year
                        elif key == 'classe':
                            data['classe_energetica'] = match.group(1).upper()
                        break

            # Caratteristiche Si/No
            si_no_features = {
                'box_auto': ['box', 'garage', 'posto auto'],
                'giardino': ['giardino'],
                'terrazzo': ['terrazzo', 'terrazza'],
                'balcone': ['balcone'],
                'ascensore': ['ascensore'],
                'cantina': ['cantina']
            }

            for feature, keywords in si_no_features.items():
                for keyword in keywords:
                    if keyword in page_text:
                        data[feature] = 'Si'
                        break

            # Tipo immobile
            tipi = ['appartamento', 'villa', 'villetta', 'casa', 'attico', 'loft', 'monolocale', 'bilocale',
                    'trilocale', 'magazzino', 'ufficio', 'negozio', 'locale commerciale']
            for tipo in tipi:
                if tipo in page_text:
                    data['tipo_immobile'] = tipo.title()
                    break

            # Stato immobile
            stati = {
                'libero': 'Libero',
                'occupato': 'Occupato',
                'nuovo': 'Nuovo',
                'ristrutturato': 'Ristrutturato',
                'da ristrutturare': 'Da ristrutturare',
                'buono stato': 'Buono stato'
            }
            for keyword, stato in stati.items():
                if keyword in page_text:
                    data['stato'] = stato
                    if keyword == 'occupato':
                        data['occupato'] = 'Si'
                    break

        except Exception as e:
            print(f"    ❌ Errore estrazione caratteristiche: {e}")

    def extract_professional_info(self, driver, data):
        """Estrae informazioni del professionista/curatore"""
        try:
            # Nome professionista/curatore
            prof_selectors = [
                '.professional-name',
                '.curator-name',
                '.agent-name',
                '[data-testid="professional-info"]'
            ]

            for selector in prof_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text.strip():
                        data['professionista'] = element.text.strip()
                        break
                except:
                    continue

            # Telefono
            phone_selectors = [
                'a[href^="tel:"]',
                '.phone',
                '.telephone',
                '[data-testid="phone"]'
            ]

            for selector in phone_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    phone = element.text.strip() or element.get_attribute('href', '').replace('tel:', '')
                    if phone and ('+' in phone or phone.replace(' ', '').replace('-', '').isdigit()):
                        data['telefono_professionista'] = phone
                        break
                except:
                    continue

            # Email
            email_selectors = [
                'a[href^="mailto:"]',
                '.email',
                '[data-testid="email"]'
            ]

            for selector in email_selectors:
                try:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                    email = element.text.strip() or element.get_attribute('href', '').replace('mailto:', '')
                    if '@' in email:
                        data['email_professionista'] = email
                        break
                except:
                    continue

        except Exception as e:
            print(f"    ❌ Errore estrazione info professionista: {e}")

    def extract_legal_info(self, driver, data):
        """Estrae informazioni legali e note"""
        try:
            page_text = driver.page_source

            # Note legali
            legal_patterns = [
                r'note[:\s]*([^<]{50,500})',
                r'avvertenze[:\s]*([^<]{50,500})',
                r'condizioni[:\s]*([^<]{50,500})'
            ]

            for pattern in legal_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE | re.DOTALL)
                if match:
                    data['nota_legali'] = match.group(1).strip()[:1000]
                    break

        except Exception as e:
            print(f"    ❌ Errore estrazione info legali: {e}")

    def save_to_database(self, data):
        """Salva nel database SQLite con thread safety"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()

                # Insert o Update
                cursor.execute('''
                    INSERT OR REPLACE INTO aste_annunci (
                        id, url, titolo, descrizione, prezzo_base, prezzo_base_euro,
                        prezzo_vendita, prezzo_vendita_euro, tribunale, numero_procedura,
                        numero_lotto, zona, indirizzo, locali, camere, bagni, superficie,
                        mq, piano, tipo_immobile, stato, anno_costruzione, classe_energetica,
                        box_auto, giardino, terrazzo, balcone, ascensore, cantina,
                        data_asta, ora_asta, professionista, telefono_professionista,
                        email_professionista, codice_riferimento, rialzo_minimo,
                        deposito_cauzionale, commissioni, spese_vendita, occupato,
                        nota_legali, data_aggiornamento
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    data['id'], data['url'], data['titolo'], data['descrizione'],
                    data['prezzo_base'], data['prezzo_base_euro'], data['prezzo_vendita'],
                    data['prezzo_vendita_euro'], data['tribunale'], data['numero_procedura'],
                    data['numero_lotto'], data['zona'], data['indirizzo'], data['locali'],
                    data['camere'], data['bagni'], data['superficie'], data['mq'],
                    data['piano'], data['tipo_immobile'], data['stato'], data['anno_costruzione'],
                    data['classe_energetica'], data['box_auto'], data['giardino'],
                    data['terrazzo'], data['balcone'], data['ascensore'], data['cantina'],
                    data['data_asta'], data['ora_asta'], data['professionista'],
                    data['telefono_professionista'], data['email_professionista'],
                    data['codice_riferimento'], data['rialzo_minimo'], data['deposito_cauzionale'],
                    data['commissioni'], data['spese_vendita'], data['occupato'],
                    data['nota_legali']
                ))

                conn.commit()
                conn.close()

        except Exception as e:
            print(f"    ❌ Errore salvataggio DB: {e}")

    def save_to_json(self, data):
        """Salva file JSON individuale per asta"""
        try:
            filename = os.path.join(self.immobili_dir, f"asta_{data['id']}.json")

            json_data = {
                "id": data['id'],
                "url": data['url'],
                "data_estrazione": datetime.now().isoformat(),
                "fonte": "idealista.it",
                "tipo_vendita": "asta_giudiziaria",
                "asta": {
                    "titolo": data['titolo'],
                    "descrizione": data['descrizione'],
                    "prezzo": {
                        "base_asta": data['prezzo_base'],
                        "base_euro": data['prezzo_base_euro'],
                        "vendita": data['prezzo_vendita'],
                        "vendita_euro": data['prezzo_vendita_euro'],
                        "rialzo_minimo": data['rialzo_minimo'],
                        "deposito_cauzionale": data['deposito_cauzionale']
                    },
                    "info_legali": {
                        "tribunale": data['tribunale'],
                        "numero_procedura": data['numero_procedura'],
                        "numero_lotto": data['numero_lotto'],
                        "data_asta": data['data_asta'],
                        "ora_asta": data['ora_asta'],
                        "occupato": data['occupato'],
                        "note_legali": data['nota_legali']
                    },
                    "localizzazione": {
                        "zona": data['zona'],
                        "indirizzo": data['indirizzo']
                    },
                    "caratteristiche": {
                        "locali": data['locali'],
                        "camere": data['camere'],
                        "bagni": data['bagni'],
                        "superficie": data['superficie'],
                        "mq": data['mq'],
                        "piano": data['piano'],
                        "tipo": data['tipo_immobile'],
                        "stato": data['stato'],
                        "anno_costruzione": data['anno_costruzione'],
                        "classe_energetica": data['classe_energetica']
                    },
                    "comfort": {
                        "box_auto": data['box_auto'],
                        "giardino": data['giardino'],
                        "terrazzo": data['terrazzo'],
                        "balcone": data['balcone'],
                        "ascensore": data['ascensore'],
                        "cantina": data['cantina']
                    },
                    "professionista": {
                        "nome": data['professionista'],
                        "telefono": data['telefono_professionista'],
                        "email": data['email_professionista']
                    }
                }
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"    ❌ Errore salvataggio JSON: {e}")

    def detail_extractor_thread(self, headless=True):
        """Thread che estrae i dettagli delle aste"""
        print("📋 Thread Detail Extractor avviato per Idealista")

        driver = self.setup_selenium(headless)
        if not driver:
            print("❌ Errore configurazione Selenium per Detail Extractor")
            return

        try:
            while True:
                try:
                    # Prova a prendere un link dalla queue
                    prop = self.link_queue.get(timeout=15)

                    if self.stop_flag.is_set():
                        break

                    # Estrai dettagli
                    data = self.extract_property_details(driver, prop['url'], prop['id'])

                    if data:
                        # Salva in DB e JSON
                        self.save_to_database(data)
                        self.save_to_json(data)

                        with self.stats_lock:
                            self.processed_count += 1

                        title = data['titolo'][:40] + "..." if len(data['titolo']) > 40 else data['titolo']
                        price = data['prezzo_base'] or 'N/A'
                        tribunale = data['tribunale'][:20] + "..." if len(data['tribunale']) > 20 else data['tribunale']

                        print(f"   ✅ {self.processed_count}: {prop['id']} - {title}")
                        print(f"      💰 {price} - 🏛️ {tribunale}")

                    # Marca come completato
                    self.link_queue.task_done()

                    # Pausa tra aste
                    time.sleep(random.uniform(2, 4))

                except Empty:
                    # Se la queue è vuota, controlla se il link finder è finito
                    if self.link_finder_done.is_set():
                        print("📋 Nessun nuovo link, Link Finder completato")
                        break
                    else:
                        print("📋 In attesa di nuovi link...")
                        continue

                except Exception as e:
                    print(f"❌ Errore nel Detail Extractor: {e}")
                    continue

        except Exception as e:
            print(f"❌ Errore generale Detail Extractor: {e}")

        finally:
            driver.quit()
            print("📋 Thread Detail Extractor completato")

    def print_progress(self):
        """Thread che stampa statistiche di progresso"""
        while not (self.link_finder_done.is_set() and self.link_queue.empty()):
            if self.stop_flag.is_set():
                break

            with self.stats_lock:
                queue_size = self.link_queue.qsize()
                print(
                    f"📊 PROGRESSO: {self.processed_count} processati, {self.total_found} trovati, {queue_size} in coda")

            time.sleep(30)  # Aggiorna ogni 30 secondi

    def scrape_all(self, headless=True):
        """Avvia scraping con multi-threading"""
        print("\n🚀 Avvio scraping multi-thread Idealista Aste...")
        print("🏛️ Target: Aste giudiziarie Roma")
        print("💡 Premi Ctrl+C per fermare il processo")

        try:
            # Avvia thread progresso
            progress_thread = threading.Thread(target=self.print_progress, daemon=True)
            progress_thread.start()

            # Avvia thread link finder
            link_thread = threading.Thread(target=self.link_finder_thread, args=(headless,))
            link_thread.start()

            # Avvia thread detail extractor
            detail_thread = threading.Thread(target=self.detail_extractor_thread, args=(headless,))
            detail_thread.start()

            # Aspetta che il link finder finisca
            link_thread.join()
            print("🔍 Link Finder completato")

            # Aspetta che tutti i dettagli siano processati
            detail_thread.join()
            print("📋 Detail Extractor completato")

            print(f"\n✅ Scraping completato!")
            print(f"📊 Aste processate: {self.processed_count}")
            self.print_final_stats()

        except KeyboardInterrupt:
            print("\n⚠️ Interruzione richiesta dall'utente...")
            self.stop_flag.set()

            # Aspetta che i thread si chiudano
            link_thread.join(timeout=15)
            detail_thread.join(timeout=15)

            print(f"📊 Aste processate prima dell'interruzione: {self.processed_count}")
            self.print_final_stats()

        except Exception as e:
            print(f"❌ Errore generale: {e}")
            self.stop_flag.set()

    def print_final_stats(self):
        """Stampa statistiche finali"""
        try:
            conn = sqlite3.connect(self.db_name)
            cursor = conn.cursor()

            # Conta totale
            cursor.execute("SELECT COUNT(*) FROM aste_annunci")
            total = cursor.fetchone()[0]

            # Ultime 5 inserite
            cursor.execute("""
                SELECT id, titolo, prezzo_base, tribunale 
                FROM aste_annunci 
                ORDER BY data_inserimento DESC 
                LIMIT 5
            """)
            recent = cursor.fetchall()

            # Statistiche per tribunale
            cursor.execute("""
                SELECT tribunale, COUNT(*) 
                FROM aste_annunci 
                WHERE tribunale IS NOT NULL AND tribunale != ''
                GROUP BY tribunale 
                ORDER BY COUNT(*) DESC 
                LIMIT 5
            """)
            tribunals = cursor.fetchall()

            # File JSON
            json_count = len([f for f in os.listdir(self.immobili_dir) if f.endswith('.json')])

            print(f"\n📊 STATISTICHE FINALI:")
            print(f"   Database: {total} aste")
            print(f"   File JSON: {json_count} file")
            print(f"   Database: {self.db_name}")
            print(f"   Directory JSON: {self.immobili_dir}/")

            if recent:
                print(f"\n🆕 Ultime 5 aste:")
                for row in recent:
                    title = row[1][:40] + "..." if len(row[1]) > 40 else row[1]
                    price = row[2] or 'N/A'
                    tribunal = row[3][:20] + "..." if row[3] and len(row[3]) > 20 else (row[3] or 'N/A')
                    print(f"   {row[0]}: {title}")
                    print(f"      💰 {price} - 🏛️ {tribunal}")

            if tribunals:
                print(f"\n🏛️ Top 5 Tribunali:")
                for tribunal, count in tribunals:
                    tribunal_name = tribunal[:30] + "..." if len(tribunal) > 30 else tribunal
                    print(f"   {tribunal_name}: {count} aste")

            conn.close()

        except Exception as e:
            print(f"❌ Errore statistiche: {e}")


def main():
    """Funzione principale"""
    print("🏠 === IDEALISTA.IT ASTE GIUDIZIARIE SCRAPER === 🏠")
    print("Estrae tutte le aste giudiziarie di Roma da Idealista.it")
    print("• Thread 1: Trova i link delle aste")
    print("• Thread 2: Estrae dettagli e salva in DB + JSON")
    print("• Salta automaticamente gli ID già presenti")
    print("• Specializzato per aste giudiziarie")

    # Configurazione
    headless = input("\nModalità headless (senza finestra browser)? (y/n): ").lower().strip() in ['y', 'yes', 's', 'si',
                                                                                                  '']

    # Avvia scraper
    scraper = IdealistaThreadedScraper()

    try:
        scraper.scrape_all(headless=headless)
    except KeyboardInterrupt:
        print("\n⚠️ Interrotto dall'utente")
    except Exception as e:
        print(f"\n❌ Errore: {e}")


if __name__ == "__main__":
    main()