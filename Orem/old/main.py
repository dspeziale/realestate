import requests
import json
import os
from datetime import datetime, timedelta
from santo import SantoParser
from lodi import LodiParser
from vespri import VespriParser


class LiturgiaParser:
    """Parser principale per la liturgia"""

    def __init__(self):
        self.base_url = "https://www.chiesacattolica.it"
        self.output_dir = "../json"
        self.create_output_dir()

    def create_output_dir(self):
        """Crea la directory json se non esiste"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"Directory '{self.output_dir}' creata.")

    def fetch_page(self, url):
        """Recupera il contenuto HTML della pagina"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                return response.text
            else:
                print(f"Errore HTTP {response.status_code} per {url}")
                return None
        except Exception as e:
            print(f"Errore nel fetch di {url}: {e}")
            return None

    def parse_liturgia_del_giorno(self, html):
        """Estrae la liturgia del giorno (Vangelo)"""
        import re
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()

        vangelo_match = re.search(r'Dal Vangelo secondo\s+(\w+)\s*\[([^\]]+)\](.*?)Parola del Signore', text, re.DOTALL)

        if vangelo_match:
            return {
                "tipo": "Vangelo",
                "autore": self._clean_text(vangelo_match.group(1)),
                "riferimento": self._clean_text(vangelo_match.group(2)),
                "testo": self._clean_text(vangelo_match.group(3))[:500]
            }

        return None

    @staticmethod
    def _clean_text(text):
        """Pulisce il testo da spazi extra"""
        import re
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def get_liturgy_data(self, date_str):
        """Recupera tutti i dati liturgici per una data"""
        try:
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            formatted_date = date_obj.strftime("%d/%m/%Y")
        except ValueError:
            print(f"Errore: formato data non valido {date_str}")
            return None

        data = {
            "data": formatted_date,
            "data_iso": date_str,
            "giorno_settimana": date_obj.strftime("%A"),
            "liturgia_del_giorno": None,
            "santo_del_giorno": None,
            "lodi_mattutine": None,
            "vespri": None
        }

        print(f"\nElaborazione: {formatted_date}")

        # Liturgia del giorno
        url = f"{self.base_url}/liturgia-del-giorno/?data-liturgia={date_str}"
        print(f"  → Scaricando liturgia del giorno...")
        html = self.fetch_page(url)
        if html:
            data["liturgia_del_giorno"] = self.parse_liturgia_del_giorno(html)

        # Santo del giorno
        url = f"{self.base_url}/santo-del-giorno/?data-liturgia={date_str}"
        print(f"  → Scaricando santo del giorno...")
        html = self.fetch_page(url)
        if html:
            data["santo_del_giorno"] = SantoParser.parse(html)

        # Lodi mattutine
        url = f"{self.base_url}/la-liturgia-delle-ore/?data-liturgia={date_str}&ora=lodi-mattutine"
        print(f"  → Scaricando lodi mattutine...")
        html = self.fetch_page(url)
        if html:
            data["lodi_mattutine"] = LodiParser.parse(html)

        # Vespri
        url = f"{self.base_url}/la-liturgia-delle-ore/?data-liturgia={date_str}&ora=vespri"
        print(f"  → Scaricando vespri...")
        html = self.fetch_page(url)
        if html:
            data["vespri"] = VespriParser.parse(html)

        return data

    def save_to_json(self, data, filename):
        """Salva i dati in un file JSON"""
        filepath = os.path.join(self.output_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✓ Salvato: {filepath}")
            return True
        except Exception as e:
            print(f"✗ Errore nel salvare {filepath}: {e}")
            return False

    def process_single_date(self, date_str):
        """Elabora una singola data"""
        data = self.get_liturgy_data(date_str)
        if data:
            filename = f"liturgia_{date_str}.json"
            return self.save_to_json(data, filename)
        return False

    def process_date_range(self, start_date_str, end_date_str):
        """Elabora un intervallo di date"""
        try:
            start = datetime.strptime(start_date_str, "%Y%m%d")
            end = datetime.strptime(end_date_str, "%Y%m%d")
        except ValueError:
            print("Errore: formato data non valido. Usa YYYYMMDD")
            return False

        current = start

        while current <= end:
            date_str = current.strftime("%Y%m%d")
            data = self.get_liturgy_data(date_str)
            if data:
                filename = f"liturgia_{date_str}.json"
                self.save_to_json(data, filename)
            current += timedelta(days=1)

        return True


def main():
    parser = LiturgiaParser()

    print("=" * 70)
    print("PARSER LITURGIA CHIESA CATTOLICA")
    print("=" * 70)

    # Elabora una singola data
    parser.process_single_date("20251020")

    # Oppure un range di date
    # parser.process_date_range("20251018", "20251031")

    print("\n" + "=" * 70)
    print("Elaborazione completata!")
    print("=" * 70)


if __name__ == "__main__":
    main()