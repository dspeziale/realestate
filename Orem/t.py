import requests
from bs4 import BeautifulSoup
import json
import os
import re
from datetime import datetime, timedelta


class LiturgiaParser:
    def __init__(self):
        self.base_url = "https://www.chiesacattolica.it"
        self.output_dir = "json"
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

    def clean_text(self, text):
        """Pulisce il testo da spazi extra"""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def clean_duplicate_lines(self, testo):
        """Rimuove righe duplicate mantenendo l'ordine"""
        righe = testo.split('\n')
        righe_pulite = [r.strip() for r in righe if r.strip()]
        viste = set()
        righe_uniche = []

        for riga in righe_pulite:
            if riga not in viste:
                righe_uniche.append(riga)
                viste.add(riga)

        return ' '.join(righe_uniche)

    def parse_liturgia_del_giorno(self, html):
        """Estrae la liturgia del giorno"""
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()

        vangelo_match = re.search(r'Dal Vangelo secondo\s+(\w+)\s*\[([^\]]+)\](.*?)Parola del Signore', text, re.DOTALL)

        if vangelo_match:
            return {
                "tipo": "Vangelo",
                "autore": self.clean_text(vangelo_match.group(1)),
                "riferimento": self.clean_text(vangelo_match.group(2)),
                "testo": self.clean_text(vangelo_match.group(3))[:500]
            }

        return None

    def parse_santo_del_giorno(self, html):
        """Estrae il santo del giorno"""
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()

        # Rimuovi riferimenti
        text = re.sub(r'Home\s*—\s*Santo del Giorno', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Condividi\s+Invia\s+Stampa.*?(?=$)', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = text.strip()

        giorno = ""
        giorno_match = re.search(
            r'(\d+)\s+(?:OTTOBRE|NOVEMBRE|DICEMBRE|GENNAIO|FEBBRAIO|MARZO|APRILE|MAGGIO|GIUGNO|LUGLIO|AGOSTO|SETTEMBRE)',
            text, re.IGNORECASE)
        if giorno_match:
            giorno = giorno_match.group(1)

        titolo_principale = ""
        titolo_match = re.search(
            r'(\d+)\s+(?:OTTOBRE|NOVEMBRE|DICEMBRE|GENNAIO|FEBBRAIO|MARZO|APRILE|MAGGIO|GIUGNO|LUGLIO|AGOSTO|SETTEMBRE)\s+\d+\s+(.+?)\s*-',
            text, re.IGNORECASE)
        if titolo_match:
            titolo_principale = self.clean_text(titolo_match.group(2))
            titolo_principale = re.sub(r'Santo del giorno\s+', '', titolo_principale, flags=re.IGNORECASE).strip()

        martirologio_principale = ""
        mart_match = re.search(r'Dal Martirologio\s*\n(.*?)(?=\n(?:A |Nell\'|Presso|Nel |Commemorazione|^$))', text,
                               re.MULTILINE | re.DOTALL)
        if mart_match:
            martirologio_principale = self.clean_text(mart_match.group(1))
            martirologio_principale = re.sub(r'Condividi\s+Invia\s+Stampa.*?(?=$)', '', martirologio_principale,
                                             flags=re.IGNORECASE | re.DOTALL)

        altri_santi_lista = []
        frasi_santi = re.split(r'(?=^(?:A |Nell\'|Presso|Nel |Nel villaggio|Commemorazione))', text, flags=re.MULTILINE)

        for frase in frasi_santi:
            frase = frase.strip()
            if not frase or len(frase) < 20:
                continue

            frase = re.sub(r'Condividi\s+Invia\s+Stampa.*?(?=$)', '', frase, flags=re.IGNORECASE | re.DOTALL)

            prima_linea = frase.split('\n')[0]

            if not re.search(r'(?:san|santa|beato|beata|santi)', prima_linea, re.IGNORECASE):
                continue

            nome_santo = self.clean_text(prima_linea)
            martirologio = self.clean_text(frase)

            if nome_santo and titolo_principale.lower() not in nome_santo.lower():
                martirologio_pulito = martirologio
                if nome_santo in martirologio:
                    martirologio_pulito = martirologio.replace(nome_santo, '', 1).strip()
                    martirologio_pulito = re.sub(r'^[\s,]+(?:che\s+)?', '', martirologio_pulito).strip()

                altri_santi_lista.append({
                    "nome": nome_santo,
                    "martirologio": martirologio_pulito
                })

        return {
            "giorno": giorno,
            "santo_principale": {
                "nome": titolo_principale,
                "martirologio": martirologio_principale
            },
            "altri_santi": altri_santi_lista,
            "numero_santi_celebrati": 1 + len(altri_santi_lista)
        }

    def parse_liturgia_ore(self, html, ora_type):
        """Estrae la liturgia delle ore (lodi o vespri)"""
        soup = BeautifulSoup(html, 'html.parser')

        # Rimuovi elementi non rilevanti
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'meta']):
            elem.decompose()

        text = soup.get_text()

        # Filtra il testo inutile
        text = re.sub(r'Home\s*—.*?Chiudi', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'Cerca un argomento.*?(?=V\.)', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'Condividi.*?(?=$)', '', text, flags=re.IGNORECASE | re.DOTALL)

        # Estrai solo la parte rilevante
        start_idx = text.find('V.')
        if start_idx == -1:
            return None

        text = text[start_idx:]

        data_info = {
            "tipo": ora_type,
            "versicoli": [],
            "gloria_al_padre": "",
            "inno": "",
            "salmi_e_antifone": [],
            "lettura_breve": {},
            "responsorio_breve": {},
            "antifona_benedicite": "",
            "cantico_benedicite": {},
            "invocazioni": [],
            "orazione": ""
        }

        # Estrai versicoli
        versicoli = re.findall(r'V\.\s*([^\n]+)', text)
        risposte = re.findall(r'R\.\s*([^\n]+)', text)

        for v, r in zip(versicoli[:1], risposte[:1]):
            data_info["versicoli"].append({
                "versicolo": self.clean_text(v),
                "risposta": self.clean_text(r)
            })

        # Estrai Gloria al Padre
        gloria_match = re.search(r'Gloria al Padre[\s\S]*?nei secoli dei secoli\. Amen\.?\s*(?:Alleluia\.)?', text)
        if gloria_match:
            data_info["gloria_al_padre"] = self.clean_text(gloria_match.group(0))

        # Estrai INNO
        inno_match = re.search(r'INNO\s*\n(.*?)(?=\d+\s+ant\.)', text, re.DOTALL)
        if inno_match:
            data_info["inno"] = self.clean_text(inno_match.group(1))

        # Estrai salmi e antifone - pattern più flessibile
        # Sostituisci gli spazi multipli e newline strane
        text_clean = re.sub(r'\s+', ' ', text)

        salmi_matches = re.findall(
            r'(\d+)\s+ant\.\s+([^S]+?)\s*(?:SALMO|CANTICO)\s+([\d,:\-]+)\s+([^\n]+?)\s+(.*?)(?=\d+\s+ant\.|LETTURA\s+BREVE)',
            text_clean,
            re.DOTALL
        )

        print(f"[DEBUG] Dopo normalizzazione spazi - Salmi trovati: {len(salmi_matches)}")

        for num_ant, testo_ant, num_salmo, titolo_salmo, contenuto_salmo in salmi_matches:
            contenuto_pulito = self.clean_duplicate_lines(contenuto_salmo)

            data_info["salmi_e_antifone"].append({
                "antifona_numero": num_ant,
                "antifona_testo": self.clean_text(testo_ant),
                "salmo_numero": self.clean_text(num_salmo),
                "salmo_titolo": self.clean_text(titolo_salmo),
                "salmo_contenuto": contenuto_pulito[:600]
            })

        # Estrai lettura breve
        lettura_match = re.search(r'LETTURA BREVE\s*([^\n]*)\s*(.*?)(?=RESPONSORIO)', text, re.DOTALL)
        if lettura_match:
            data_info["lettura_breve"] = {
                "riferimento": self.clean_text(lettura_match.group(1)),
                "contenuto": self.clean_text(lettura_match.group(2))[:400]
            }

        # Estrai responsorio breve
        responsorio_match = re.search(r'RESPONSORIO\s*(?:BREVE)?\s*(.*?)(?=Ant\.|INVOCAZIONI|CANTICO DI|$)', text,
                                      re.DOTALL)
        if responsorio_match:
            data_info["responsorio_breve"] = {
                "contenuto": self.clean_text(responsorio_match.group(1))[:400]
            }

        # Estrai antifona benedicite e cantico
        ant_ben_match = re.search(r'Ant\.\s+al\s+Ben\.\s+([^\n]+)', text)
        if ant_ben_match:
            data_info["antifona_benedicite"] = self.clean_text(ant_ben_match.group(1))

        cantico_match = re.search(
            r'CANTICO DI ZACCARIA\s+(Lc\s+[\d,:\-]+)\s+([^\n]+)\s*(.*?)(?=INVOCAZIONI|Padre nostro|$)', text, re.DOTALL)
        if cantico_match:
            data_info["cantico_benedicite"] = {
                "riferimento": self.clean_text(cantico_match.group(1)),
                "titolo": self.clean_text(cantico_match.group(2)),
                "contenuto": self.clean_text(cantico_match.group(3))[:600]
            }

        # Estrai invocazioni
        invocazioni_match = re.search(r'INVOCAZIONI\s*(.*?)(?=Padre nostro)', text, re.DOTALL)
        if invocazioni_match:
            invocazioni_testo = invocazioni_match.group(1)
            invocazioni_list = re.split(r'\n(?=\s*[–\-])', invocazioni_testo)
            for inv in invocazioni_list:
                inv_pulita = self.clean_text(inv)
                if inv_pulita and len(inv_pulita) > 5:
                    data_info["invocazioni"].append(inv_pulita)

        # Estrai orazione
        orazione_match = re.search(r'ORAZIONE\s*\n(.*?)(?=(?:Il Signore|Padre nostro|R\.|$))', text,
                                   re.MULTILINE | re.DOTALL)
        if orazione_match:
            data_info["orazione"] = self.clean_text(orazione_match.group(1))

        return data_info

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
            data["santo_del_giorno"] = self.parse_santo_del_giorno(html)

        # Lodi mattutine
        url = f"{self.base_url}/la-liturgia-delle-ore/?data-liturgia={date_str}&ora=lodi-mattutine"
        print(f"  → Scaricando lodi mattutine...")
        html = self.fetch_page(url)
        if html:
            data["lodi_mattutine"] = self.parse_liturgia_ore(html, "lodi-mattutine")

        # Vespri
        url = f"{self.base_url}/la-liturgia-delle-ore/?data-liturgia={date_str}&ora=vespri"
        print(f"  → Scaricando vespri...")
        html = self.fetch_page(url)
        if html:
            data["vespri"] = self.parse_liturgia_ore(html, "vespri")

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

    parser.process_single_date("20251021")

    print("\n" + "=" * 70)
    print("Elaborazione completata!")
    print("=" * 70)


if __name__ == "__main__":
    main()