#!/usr/bin/env python3
"""
File: casa_it_threaded_scraper.py
Scraper multi-thread per Casa.it - un thread trova i link, l'altro estrae i dettagli
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


class CasaItThreadedScraper:
    def __init__(self):
        self.db_name = "casa_it_annunci.db"
        self.immobili_dir = "immobili"

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

        print("Casa.it Multi-threaded Scraper inizializzato")
        print(f"Database: {self.db_name}")
        print(f"JSON Directory: {self.immobili_dir}/")

    def init_database(self):
        """Crea il database SQLite con tutte le colonne necessarie"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS annunci (
                id TEXT PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                titolo TEXT,
                descrizione TEXT,
                prezzo TEXT,
                prezzo_euro INTEGER,
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
                spese_condominio TEXT,
                riscaldamento TEXT,
                climatizzazione TEXT,
                box_auto TEXT,
                giardino TEXT,
                terrazzo TEXT,
                balcone TEXT,
                ascensore TEXT,
                cantina TEXT,
                agenzia TEXT,
                telefono TEXT,
                codice_riferimento TEXT,
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
            cursor.execute("SELECT id FROM annunci")
            existing_ids = {row[0] for row in cursor.fetchall()}
            conn.close()
            print(f"ID già presenti nel database: {len(existing_ids)}")
            return existing_ids
        except Exception as e:
            print(f"Errore recupero ID esistenti: {e}")
            return set()

    def setup_selenium(self, headless=True):
        """Configura e avvia Selenium"""
        options = Options()

        if headless:
            options.add_argument("--headless")

        # Opzioni anti-detection
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
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

            return driver
        except Exception as e:
            print(f"Errore configurazione Selenium: {e}")
            return None

    def get_total_pages(self, driver):
        """Rileva automaticamente il numero totale di pagine"""
        try:
            # Cerca elementi di paginazione
            pagination_elements = driver.find_elements(By.CSS_SELECTOR,
                                                       ".pagination a, .paging a, .page-numbers a")

            max_page = 1
            for elem in pagination_elements:
                text = elem.text.strip()
                if text.isdigit():
                    max_page = max(max_page, int(text))

            # Se non trova nulla, cerca nell'URL
            if max_page == 1:
                page_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'pag=')]")
                for link in page_links:
                    href = link.get_attribute('href')
                    match = re.search(r'pag=(\d+)', href)
                    if match:
                        max_page = max(max_page, int(match.group(1)))

            return max_page if max_page > 0 else 1000  # Fallback alto

        except Exception as e:
            print(f"Errore rilevazione pagine: {e}")
            return 1000  # Fallback alto

    def find_property_links(self, driver):
        """Trova tutti i link agli immobili nella pagina corrente"""
        links = []

        try:
            # Scroll per caricare tutto
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Cerca link con pattern /immobili/
            selectors = [
                'a[href*="/immobili/"]',
                'a[href*="/immobile/"]'
            ]

            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    href = elem.get_attribute('href')
                    if href and 'casa.it' in href:
                        # Estrai ID
                        match = re.search(r'/immobili?/(\d+)', href)
                        if match:
                            property_id = match.group(1)
                            links.append({'id': property_id, 'url': href})

            # Rimuovi duplicati
            seen = set()
            unique_links = []
            for link in links:
                if link['id'] not in seen:
                    seen.add(link['id'])
                    unique_links.append(link)

            return unique_links

        except Exception as e:
            print(f"Errore ricerca link: {e}")
            return []

    def link_finder_thread(self, headless=True):
        """Thread che trova tutti i link degli immobili"""
        print("🔍 Thread Link Finder avviato")

        driver = self.setup_selenium(headless)
        if not driver:
            print("❌ Errore configurazione Selenium per Link Finder")
            self.link_finder_done.set()
            return

        base_url = "https://www.casa.it/vendita/residenziale/roma-provincia/"
        existing_ids = self.get_existing_ids()

        try:
            # Vai alla prima pagina
            driver.get(base_url)
            time.sleep(3)

            # Gestisci cookie
            try:
                cookie_btn = driver.find_element(By.CSS_SELECTOR,
                                                 ".cookie-accept, #cookie-accept, button[data-cy='gdpr-accept']")
                cookie_btn.click()
                time.sleep(2)
            except:
                pass

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
                        url = f"{base_url}?pag={page}"
                        driver.get(url)
                        time.sleep(3)

                    # Trova link immobili
                    property_links = self.find_property_links(driver)
                    new_links = []

                    for prop in property_links:
                        if prop['id'] not in existing_ids:
                            new_links.append(prop)
                            self.link_queue.put(prop)

                    with self.stats_lock:
                        self.total_found += len(new_links)

                    print(f"   ✅ Pagina {page}: {len(property_links)} totali, {len(new_links)} nuovi")

                    # Pausa tra pagine
                    if page < total_pages:
                        pause = random.uniform(2, 4)
                        if page % 20 == 0:
                            pause = random.uniform(5, 8)
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
        """Estrae tutti i dettagli da una singola pagina immobile"""
        try:
            # Vai alla pagina
            driver.get(property_url)
            time.sleep(random.uniform(2, 4))

            # Inizializza dizionario risultato
            data = {
                'id': property_id,
                'url': property_url,
                'titolo': '',
                'descrizione': '',
                'prezzo': '',
                'prezzo_euro': None,
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
                'spese_condominio': '',
                'riscaldamento': '',
                'climatizzazione': '',
                'box_auto': '',
                'giardino': '',
                'terrazzo': '',
                'balcone': '',
                'ascensore': '',
                'cantina': '',
                'agenzia': '',
                'telefono': '',
                'codice_riferimento': ''
            }

            # Attendi caricamento
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Estrai dati specifici
            self.extract_title(driver, data)
            self.extract_price(driver, data)
            self.extract_description(driver, data)
            self.extract_location(driver, data)
            self.extract_features(driver, data)
            self.extract_agency_info(driver, data)

            return data

        except Exception as e:
            print(f"    ❌ Errore estrazione {property_id}: {e}")
            return None

    def extract_title(self, driver, data):
        """Estrae il titolo"""
        selectors = ['h1', '.property-title', '.listing-title', '.page-title']
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.text.strip():
                    data['titolo'] = element.text.strip()
                    break
            except:
                continue

    def extract_price(self, driver, data):
        """Estrae prezzo e valore numerico"""
        selectors = ['.price', '.property-price', '*[class*="price"]', '*[class*="prezzo"]']
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if '€' in text or 'EUR' in text:
                    data['prezzo'] = text
                    # Estrai valore numerico
                    numbers = re.findall(r'[\d.]+', text.replace(',', '').replace('.', ''))
                    if numbers:
                        try:
                            data['prezzo_euro'] = int(''.join(numbers))
                        except:
                            pass
                    break
            except:
                continue

    def extract_description(self, driver, data):
        """Estrae descrizione"""
        selectors = ['.description', '.property-description', '.content', '.details']
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.text.strip():
                    data['descrizione'] = element.text.strip()[:3000]  # Limite caratteri
                    break
            except:
                continue

    def extract_location(self, driver, data):
        """Estrae zona e indirizzo"""
        selectors = ['.address', '.location', '.zone', '.property-address']
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
                'superficie': [r'(\d+)\s*m[²q2]', r'superficie[:\s]*(\d+)'],
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
                'cantina': ['cantina'],
                'climatizzazione': ['aria condizionata', 'climatizzazione', 'condizionatore']
            }

            for feature, keywords in si_no_features.items():
                for keyword in keywords:
                    if keyword in page_text:
                        data[feature] = 'Si'
                        break

            # Tipo immobile
            tipi = ['appartamento', 'villa', 'villetta', 'casa', 'attico', 'loft', 'monolocale', 'bilocale',
                    'trilocale']
            for tipo in tipi:
                if tipo in page_text:
                    data['tipo_immobile'] = tipo.title()
                    break

            # Stato immobile
            stati = {
                'nuovo': 'Nuovo',
                'ristrutturato': 'Ristrutturato',
                'da ristrutturare': 'Da ristrutturare',
                'buono stato': 'Buono stato'
            }
            for keyword, stato in stati.items():
                if keyword in page_text:
                    data['stato'] = stato
                    break

        except Exception as e:
            print(f"    ❌ Errore estrazione caratteristiche: {e}")

    def extract_agency_info(self, driver, data):
        """Estrae informazioni agenzia"""
        # Nome agenzia
        selectors = ['.agency', '.agent', '.broker', '.realtor']
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.text.strip():
                    data['agenzia'] = element.text.strip()
                    break
            except:
                continue

        # Telefono
        selectors = ['.phone', '.tel', 'a[href^="tel:"]', '.contact-phone']
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                phone = element.text.strip() or element.get_attribute('href', '').replace('tel:', '')
                if phone and ('+' in phone or phone.replace(' ', '').replace('-', '').isdigit()):
                    data['telefono'] = phone
                    break
            except:
                continue

    def save_to_database(self, data):
        """Salva nel database SQLite con thread safety"""
        try:
            with self.db_lock:
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()

                # Insert o Update
                cursor.execute('''
                    INSERT OR REPLACE INTO annunci (
                        id, url, titolo, descrizione, prezzo, prezzo_euro, zona, indirizzo,
                        locali, camere, bagni, superficie, mq, piano, tipo_immobile, stato,
                        anno_costruzione, classe_energetica, spese_condominio, riscaldamento,
                        climatizzazione, box_auto, giardino, terrazzo, balcone, ascensore,
                        cantina, agenzia, telefono, codice_riferimento, data_aggiornamento
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    data['id'], data['url'], data['titolo'], data['descrizione'], data['prezzo'],
                    data['prezzo_euro'], data['zona'], data['indirizzo'], data['locali'], data['camere'],
                    data['bagni'], data['superficie'], data['mq'], data['piano'], data['tipo_immobile'],
                    data['stato'], data['anno_costruzione'], data['classe_energetica'], data['spese_condominio'],
                    data['riscaldamento'], data['climatizzazione'], data['box_auto'], data['giardino'],
                    data['terrazzo'], data['balcone'], data['ascensore'], data['cantina'], data['agenzia'],
                    data['telefono'], data['codice_riferimento']
                ))

                conn.commit()
                conn.close()

        except Exception as e:
            print(f"    ❌ Errore salvataggio DB: {e}")

    def save_to_json(self, data):
        """Salva file JSON individuale"""
        try:
            filename = os.path.join(self.immobili_dir, f"{data['id']}.json")

            json_data = {
                "id": data['id'],
                "url": data['url'],
                "data_estrazione": datetime.now().isoformat(),
                "fonte": "casa.it",
                "immobile": {
                    "titolo": data['titolo'],
                    "descrizione": data['descrizione'],
                    "prezzo": {
                        "testo": data['prezzo'],
                        "euro": data['prezzo_euro']
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
                        "riscaldamento": data['riscaldamento'],
                        "climatizzazione": data['climatizzazione'],
                        "box_auto": data['box_auto'],
                        "giardino": data['giardino'],
                        "terrazzo": data['terrazzo'],
                        "balcone": data['balcone'],
                        "ascensore": data['ascensore'],
                        "cantina": data['cantina']
                    },
                    "agenzia": {
                        "nome": data['agenzia'],
                        "telefono": data['telefono'],
                        "codice_riferimento": data['codice_riferimento']
                    }
                }
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"    ❌ Errore salvataggio JSON: {e}")

    def detail_extractor_thread(self, headless=True):
        """Thread che estrae i dettagli degli immobili"""
        print("📋 Thread Detail Extractor avviato")

        driver = self.setup_selenium(headless)
        if not driver:
            print("❌ Errore configurazione Selenium per Detail Extractor")
            return

        try:
            while True:
                try:
                    # Prova a prendere un link dalla queue
                    prop = self.link_queue.get(timeout=10)

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
                        print(f"   ✅ {self.processed_count}: {prop['id']} - {title} - {data['prezzo']}")

                    # Marca come completato
                    self.link_queue.task_done()

                    # Pausa tra immobili
                    time.sleep(random.uniform(1, 2))

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
        print("\n🚀 Avvio scraping multi-thread Casa.it...")
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
            print(f"📊 Immobili processati: {self.processed_count}")
            self.print_final_stats()

        except KeyboardInterrupt:
            print("\n⚠️ Interruzione richiesta dall'utente...")
            self.stop_flag.set()

            # Aspetta che i thread si chiudano
            link_thread.join(timeout=10)
            detail_thread.join(timeout=10)

            print(f"📊 Immobili processati prima dell'interruzione: {self.processed_count}")
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
            cursor.execute("SELECT COUNT(*) FROM annunci")
            total = cursor.fetchone()[0]

            # Ultimi 5 inseriti
            cursor.execute("SELECT id, titolo, prezzo FROM annunci ORDER BY data_inserimento DESC LIMIT 5")
            recent = cursor.fetchall()

            # File JSON
            json_count = len([f for f in os.listdir(self.immobili_dir) if f.endswith('.json')])

            print(f"\n📊 STATISTICHE FINALI:")
            print(f"   Database: {total} annunci")
            print(f"   File JSON: {json_count} file")
            print(f"   Database: {self.db_name}")
            print(f"   Directory JSON: {self.immobili_dir}/")

            if recent:
                print(f"\n🆕 Ultimi 5 annunci:")
                for row in recent:
                    title = row[1][:50] + "..." if len(row[1]) > 50 else row[1]
                    print(f"   {row[0]}: {title} - {row[2]}")

            conn.close()

        except Exception as e:
            print(f"❌ Errore statistiche: {e}")


def main():
    """Funzione principale"""
    print("🏠 === CASA.IT MULTI-THREADED SCRAPER === 🏠")
    print("Estrae tutti gli annunci immobiliari da Casa.it con multi-threading")
    print("• Thread 1: Trova i link degli immobili")
    print("• Thread 2: Estrae dettagli e salva in DB + JSON")
    print("• Salta automaticamente gli ID già presenti")

    # Configurazione
    headless = input("\nModalità headless (senza finestra browser)? (y/n): ").lower().strip() in ['y', 'yes', 's', 'si',
                                                                                                  '']

    # Avvia scraper
    scraper = CasaItThreadedScraper()

    try:
        scraper.scrape_all(headless=headless)
    except KeyboardInterrupt:
        print("\n⚠️ Interrotto dall'utente")
    except Exception as e:
        print(f"\n❌ Errore: {e}")


if __name__ == "__main__":
    main()