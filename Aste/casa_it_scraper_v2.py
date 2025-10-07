"""
Casa.it Scraper - Versione Base che FUNZIONA
Approccio: Selenium + BeautifulSoup, parsing HTML diretto
"""

import time
import json
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import re


class CasaItScraperBasic:
    def __init__(self, db_name='aste_casa_it_v2.db'):
        self.db_name = db_name
        self.base_url = "https://www.casa.it"
        self.driver = None
        self.setup_database()

    def setup_database(self):
        """Crea database SQLite"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS immobili (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titolo TEXT,
                citta TEXT,
                zona TEXT,
                prezzo TEXT,
                superficie TEXT,
                locali TEXT,
                url TEXT UNIQUE,
                descrizione TEXT,
                data_inserimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        print("✅ Database creato\n")

    def start_browser(self):
        """Avvia Chrome"""
        print("🌐 Avvio browser...")
        options = Options()
        # options.add_argument('--headless')  # Commenta per vedere il browser
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        self.driver = webdriver.Chrome(options=options)
        self.driver.maximize_window()
        print("✅ Browser avviato\n")

    def scrape_search_page(self, url):
        """Scrape della pagina di ricerca"""
        print(f"📄 Carico: {url}\n")

        self.driver.get(url)
        time.sleep(5)  # Attendi caricamento

        # Salva HTML per debug
        html = self.driver.page_source
        with open('casa_debug.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("💾 HTML salvato: casa_debug.html\n")

        soup = BeautifulSoup(html, 'html.parser')

        # STRATEGIA 1: Cerca tutti i link che contengono /vendita/ o /immobili/
        print("🔍 Cerco annunci...\n")

        # Pattern comuni per link immobili
        links = set()

        # Link diretti
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/vendita/' in href or '/immobili/' in href or '/asta/' in href:
                full_url = href if href.startswith('http') else self.base_url + href
                links.add(full_url)

        print(f"✅ Trovati {len(links)} link\n")

        # Mostra primi 5
        for idx, link in enumerate(list(links)[:5], 1):
            print(f"  {idx}. {link}")

        return list(links)

    def scrape_detail_page(self, url):
        """Scrape pagina dettaglio immobile"""
        print(f"\n{'=' * 60}")
        print(f"📍 Carico dettaglio: {url}")
        print('=' * 60)

        try:
            self.driver.get(url)
            time.sleep(3)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            immobile = {
                'url': url,
                'data_inserimento': datetime.now().isoformat()
            }

            # Estrai TUTTO il testo visibile
            page_text = soup.get_text(separator=' ', strip=True)

            print("\n🔍 Cerco informazioni...\n")

            # Titolo - cerca tag h1 o h2
            title_tags = soup.find_all(['h1', 'h2'])
            if title_tags:
                immobile['titolo'] = title_tags[0].get_text(strip=True)
                print(f"✅ Titolo: {immobile['titolo']}")

            # Prezzo - cerca pattern €
            prezzo_match = re.search(r'€\s*([\d.,]+)', page_text)
            if prezzo_match:
                immobile['prezzo'] = prezzo_match.group(0)
                print(f"✅ Prezzo: {immobile['prezzo']}")

            # Superficie - cerca pattern mq o m²
            superficie_match = re.search(r'(\d+)\s*(?:mq|m²|metri)', page_text, re.IGNORECASE)
            if superficie_match:
                immobile['superficie'] = superficie_match.group(1) + ' mq'
                print(f"✅ Superficie: {immobile['superficie']}")

            # Locali - cerca pattern "X locali" o "X vani"
            locali_match = re.search(r'(\d+)\s*(?:local[ie]|van[ie])', page_text, re.IGNORECASE)
            if locali_match:
                immobile['locali'] = locali_match.group(1)
                print(f"✅ Locali: {immobile['locali']}")

            # Città - cerca pattern comuni
            citta_keywords = ['Roma', 'Milano', 'Napoli', 'Torino', 'Firenze', 'Bologna']
            for citta in citta_keywords:
                if citta in page_text:
                    immobile['citta'] = citta
                    print(f"✅ Città: {immobile['citta']}")
                    break

            # Zona/indirizzo - cerca via/piazza
            zona_match = re.search(r'(?:Via|Piazza|Viale|Corso)\s+([A-Za-z\s]+?)(?:\d|,|\.|\s{2})', page_text,
                                   re.IGNORECASE)
            if zona_match:
                immobile['zona'] = zona_match.group(0).strip()
                print(f"✅ Zona: {immobile['zona']}")

            # Descrizione - prendi primi 500 caratteri
            immobile['descrizione'] = page_text[:500]

            print("\n📊 Dati estratti:")
            print(json.dumps(immobile, indent=2, ensure_ascii=False))

            return immobile

        except Exception as e:
            print(f"❌ Errore: {e}")
            return None

    def save_to_db(self, immobile):
        """Salva in database"""
        if not immobile:
            return False

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR IGNORE INTO immobili 
                (titolo, citta, zona, prezzo, superficie, locali, url, descrizione)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                immobile.get('titolo'),
                immobile.get('citta'),
                immobile.get('zona'),
                immobile.get('prezzo'),
                immobile.get('superficie'),
                immobile.get('locali'),
                immobile.get('url'),
                immobile.get('descrizione')
            ))

            conn.commit()
            print("✅ Salvato in DB\n")
            return True

        except Exception as e:
            print(f"❌ Errore DB: {e}\n")
            return False
        finally:
            conn.close()

    def run(self, search_url, max_immobili=5):
        """Esegue scraping completo"""
        print("\n" + "=" * 60)
        print("🏠 CASA.IT SCRAPER")
        print("=" * 60 + "\n")

        try:
            self.start_browser()

            # Step 1: Pagina ricerca
            links = self.scrape_search_page(search_url)

            if not links:
                print("❌ Nessun link trovato!")
                return

            print(f"\n📋 Procedo con {min(len(links), max_immobili)} immobili\n")

            # Step 2: Scrape dettagli
            count = 0
            for link in links[:max_immobili]:
                immobile = self.scrape_detail_page(link)
                if immobile:
                    self.save_to_db(immobile)
                    count += 1
                time.sleep(2)  # Pausa tra richieste

            print("\n" + "=" * 60)
            print(f"✅ COMPLETATO! Salvati {count} immobili")
            print("=" * 60 + "\n")

        finally:
            if self.driver:
                self.driver.quit()
                print("🔚 Browser chiuso")

    def show_results(self):
        """Mostra risultati database"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM immobili')
        total = cursor.fetchone()[0]

        print(f"\n📊 RISULTATI DATABASE")
        print("=" * 60)
        print(f"Totale immobili: {total}\n")

        cursor.execute('SELECT titolo, citta, prezzo, superficie FROM immobili LIMIT 5')
        rows = cursor.fetchall()

        for idx, row in enumerate(rows, 1):
            print(f"{idx}. {row[0]}")
            print(f"   Città: {row[1]}")
            print(f"   Prezzo: {row[2]}")
            print(f"   Superficie: {row[3]}\n")

        conn.close()


def main():
    """Esempio di utilizzo"""

    # URL di ricerca Casa.it - Roma, aste, min 200mq
    search_url = "https://www.casa.it/vendita/residenziale/roma/?auctionOnly=true&surfaceMin=200"

    scraper = CasaItScraperBasic()

    # Scrape primi 5 immobili
    scraper.run(search_url, max_immobili=5)

    # Mostra risultati
    scraper.show_results()


if __name__ == "__main__":
    main()