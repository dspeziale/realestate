import time

import requests
from bs4 import BeautifulSoup
import re
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class BaseLiturgiaParser:
    """Base parser con metodi comuni"""

    @staticmethod
    def clean_text(text: str) -> str:
        """Pulisce il testo da spazi extra e caratteri di escape UTF-8 doppi"""
        text = re.sub(r'\s+', ' ', text)
        try:
            if isinstance(text, str):
                text = text.encode('utf-8').decode('utf-8', errors='ignore')
        except (UnicodeDecodeError, AttributeError):
            pass

        replacements = {
            '\u2019': "'", '\u201c': '"', '\u201d': '"',
            '\u2013': '–', '\u2014': '—', '\u00e9': 'é',
            '\u00e0': 'à', '\u00ec': 'ì', '\u00f2': 'ò', '\u00f9': 'ù',
        }
        for unicode_char, replacement in replacements.items():
            text = text.replace(unicode_char, replacement)
        return text.strip()

    @staticmethod
    def clean_duplicate_lines(text: str) -> str:
        """Rimuove righe duplicate mantenendo l'ordine"""
        lines = text.split('\n')
        cleaned = [l.strip() for l in lines if l.strip()]
        seen = set()
        unique = []
        for line in cleaned:
            if line not in seen:
                unique.append(line)
                seen.add(line)
        return ' '.join(unique)

    @staticmethod
    def fetch_url(url: str, timeout: int = 10) -> Optional[str]:
        """Recupera il contenuto HTML della pagina"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                response.encoding = 'utf-8'
                return response.text
            print(f"Errore HTTP {response.status_code} per {url}")
            return None
        except Exception as e:
            print(f"Errore nel fetch di {url}: {e}")
            return None

    @staticmethod
    def estrai_testo_filtrato(html: str, marker_start: str, marker_end: str = "Condividi") -> List[str]:
        """Estrae testo filtrato tra due marcatori"""
        soup = BeautifulSoup(html, 'html.parser')
        all_texts = [t.strip() for t in soup.body.find_all(string=True) if t.strip() and len(t.strip()) > 1]

        count = 0
        start_idx = 0
        for i, text in enumerate(all_texts):
            if marker_start in text:
                count += 1
                if count == 2:
                    start_idx = i
                    break

        end_idx = len(all_texts)
        for i in range(start_idx, len(all_texts)):
            if marker_end in all_texts[i]:
                end_idx = i
                break

        texts = all_texts[start_idx:end_idx]
        result = []
        prev = None
        for t in texts:
            if t != prev:
                result.append(t)
            prev = t
        return result


class LodiParser(BaseLiturgiaParser):
    """Parser per Lodi Mattutine"""

    @classmethod
    def parse(cls, text: str) -> Dict:
        data = {
            "tipo": "lodi-mattutine",
            "titolo": "",
            "versicoli": [],
            "gloria_al_padre": "",
            "inno": "",
            "antifone_e_salmi": [],
            "lettura_breve": {},
            "responsorio_breve": {},
            "antifona_cantico_finale": "",
            "cantico_finale": {},
            "invocazioni": [],
            "orazione": ""
        }

        titolo_match = re.search(r'(MARTEDI\'.*?SALTERIO)', text)
        if titolo_match:
            data["titolo"] = cls.clean_text(titolo_match.group(1))

        versicoli = re.findall(r'V\.\s*\n\s*([^\n]+)\n\s*R\.\s*\n\s*([^\n]+)', text)
        for v, r in versicoli[:1]:
            data["versicoli"].append({
                "versicolo": cls.clean_text(v),
                "risposta": cls.clean_text(r)
            })

        gloria_match = re.search(r'Gloria al Padre[\s\S]*?nei secoli dei secoli\.\s*Amen\.?\s*(?:Alleluia\.)?', text,
                                 re.IGNORECASE)
        if gloria_match:
            data["gloria_al_padre"] = cls.clean_text(gloria_match.group(0))

        inno_match = re.search(r'INNO\s*\n(.*?)(?=\d+\s+ant\.)', text, re.DOTALL)
        if inno_match:
            data["inno"] = cls.clean_text(inno_match.group(1))

        sezione = re.search(r'1\s+ant\..*?(?=LETTURA\s+BREVE)', text, re.DOTALL)
        if sezione:
            testo_sezione = sezione.group(0)
            for num in ['1', '2', '3']:
                pattern = rf'({num})\s+ant\.\s*\n\s*([^\n]+(?:\n[^\n]+)*?)\n+(SALMO|CANTICO)\s*([^\s]+(?:\s+[\d,:\-]+)*?)\s+([^\n]+)\n(.*?)\n{num}\s+ant\.'
                match = re.search(pattern, testo_sezione, re.DOTALL)
                if match:
                    contenuto_raw = match.group(6)
                    contenuto_match = re.search(r'\)\.?\s*(.*)', contenuto_raw, re.DOTALL)
                    contenuto = contenuto_match.group(1) if contenuto_match else contenuto_raw
                    contenuto_pulito = cls.clean_duplicate_lines(contenuto)
                    data["antifone_e_salmi"].append({
                        "antifona_numero": match.group(1),
                        "antifona_testo": cls.clean_text(match.group(2)),
                        "tipo": match.group(3),
                        "numero": cls.clean_text(match.group(4)),
                        "titolo": cls.clean_text(match.group(5)),
                        "contenuto": contenuto_pulito
                    })

        lettura_match = re.search(r'LETTURA\s+BREVE\s*\n\s*([^\n]+)\n(.*?)(?=RESPONSORIO)', text, re.DOTALL)
        if lettura_match:
            data["lettura_breve"] = {
                "riferimento": cls.clean_text(lettura_match.group(1)),
                "contenuto": cls.clean_text(lettura_match.group(2))[:400]
            }

        responsorio_match = re.search(r'RESPONSORIO\s+BREVE\s*\n(.*?)(?=Ant\.\s+al\s+Ben\.)', text, re.DOTALL)
        if responsorio_match:
            data["responsorio_breve"] = {"contenuto": responsorio_match.group(1).strip()}

        ant_match = re.search(r'Ant\.\s+al\s+Ben\.\s*\n\s*([^\n]+(?:\n[^\n]+)*?)\n\s*(?=CANTICO|INVOCAZIONI)', text)
        if ant_match:
            data["antifona_cantico_finale"] = cls.clean_text(ant_match.group(1))

        cantico_match = re.search(r'CANTICO\s+DI\s+ZACCARIA\s*\n\s*(Lc[\s\d,:\-]+)\n(.*?)(?=Gloria al Padre)', text,
                                  re.DOTALL)
        if cantico_match:
            linee = cantico_match.group(2).split('\n', 1)
            contenuto = linee[1].strip() if len(linee) > 1 else cantico_match.group(2).strip()
            data["cantico_finale"] = {
                "riferimento": cls.clean_text(cantico_match.group(1)),
                "contenuto": contenuto
            }

        invocazioni_match = re.search(r'INVOCAZIONI\s*\n(.*?)(?=Padre\s+nostro)', text, re.DOTALL)
        if invocazioni_match:
            inv_list = re.split(r'\n(?=(?:Re\s|Cristo|Signore|Concedici|Infondi|Fa))', invocazioni_match.group(1))
            for inv in inv_list:
                inv_pulita = cls.clean_text(inv)
                if inv_pulita and len(inv_pulita) > 10:
                    data["invocazioni"].append(inv_pulita)

        orazione_match = re.search(r'ORAZIONE\s*\n(.*?Amen\.)', text, re.DOTALL)
        if orazione_match:
            data["orazione"] = orazione_match.group(1).strip()

        return data


class VespriParser(BaseLiturgiaParser):
    """Parser per Vespri"""

    @classmethod
    def parse(cls, text: str) -> Dict:
        data = {
            "tipo": "vespri",
            "titolo": "",
            "versicoli": [],
            "gloria_al_padre": "",
            "inno": "",
            "antifone_e_salmi": [],
            "lettura_breve": {},
            "responsorio_breve": {},
            "antifona_cantico_finale": "",
            "cantico_finale": {},
            "intercessioni": [],
            "orazione": ""
        }

        titolo_match = re.search(r'(LUNEDI\'.*?SALTERIO)', text)
        if titolo_match:
            data["titolo"] = cls.clean_text(titolo_match.group(1))

        versicoli = re.findall(r'V\.\s*\n\s*([^\n]+)\n\s*R\.\s*\n\s*([^\n]+)', text)
        for v, r in versicoli[:1]:
            data["versicoli"].append({
                "versicolo": cls.clean_text(v),
                "risposta": cls.clean_text(r)
            })

        gloria_match = re.search(r'Gloria al Padre[\s\S]*?nei secoli dei secoli\.\s*Amen\.?\s*(?:Alleluia\.)?', text,
                                 re.IGNORECASE)
        if gloria_match:
            data["gloria_al_padre"] = cls.clean_text(gloria_match.group(0))

        inno_match = re.search(r'INNO\s*\n(.*?)(?=\d+\s+ant\.)', text, re.DOTALL)
        if inno_match:
            data["inno"] = cls.clean_text(inno_match.group(1))

        sezione = re.search(r'1\s+ant\..*?(?=LETTURA\s+BREVE)', text, re.DOTALL)
        if sezione:
            testo_sezione = sezione.group(0)
            for num in ['1', '2', '3']:
                pattern = rf'({num})\s+ant\.\s*\n\s*([^\n]+(?:\n[^\n]+)*?)\n+(SALMO|CANTICO)\s*([^\s]+(?:\s+[\d,:\-]+)*?)\s+([^\n]+)\n(.*?)\n{num}\s+ant\.'
                match = re.search(pattern, testo_sezione, re.DOTALL)
                if match:
                    contenuto_raw = match.group(6)
                    contenuto_match = re.search(r'\)\.?\s*(.*)', contenuto_raw, re.DOTALL)
                    contenuto = contenuto_match.group(1) if contenuto_match else contenuto_raw
                    contenuto_pulito = cls.clean_duplicate_lines(contenuto)
                    data["antifone_e_salmi"].append({
                        "antifona_numero": match.group(1),
                        "antifona_testo": cls.clean_text(match.group(2)),
                        "tipo": match.group(3),
                        "numero": cls.clean_text(match.group(4)),
                        "titolo": cls.clean_text(match.group(5)),
                        "contenuto": contenuto_pulito
                    })

        lettura_match = re.search(r'LETTURA\s+BREVE\s*\n\s*([^\n]+)\n(.*?)(?=RESPONSORIO)', text, re.DOTALL)
        if lettura_match:
            data["lettura_breve"] = {
                "riferimento": cls.clean_text(lettura_match.group(1)),
                "contenuto": cls.clean_text(lettura_match.group(2))
            }

        responsorio_match = re.search(r'RESPONSORIO\s+BREVE\s*\n(.*?)(?=Ant\.\s+al\s+Magn\.)', text, re.DOTALL)
        if responsorio_match:
            data["responsorio_breve"] = {"contenuto": responsorio_match.group(1).strip()}

        ant_match = re.search(r'Ant\.\s+al\s+Magn\.\s*\n\s*([^\n]+(?:\n[^\n]+)*?)\n\s*(?=CANTICO|INTERCESSIONI)', text)
        if ant_match:
            data["antifona_cantico_finale"] = cls.clean_text(ant_match.group(1))

        cantico_match = re.search(r'CANTICO\s+DELLA\s+BEATA\s+VERGINE\s*\n\s*(Lc[\s\d,:\-]+)\n(.*?)(?=Gloria al Padre)',
                                  text, re.DOTALL)
        if cantico_match:
            linee = cantico_match.group(2).split('\n', 1)
            contenuto = linee[1].strip() if len(linee) > 1 else cantico_match.group(2).strip()
            data["cantico_finale"] = {
                "riferimento": cls.clean_text(cantico_match.group(1)),
                "contenuto": contenuto
            }

        intercessioni_match = re.search(r'INTERCESSIONI\s*\n(.*?)(?=Padre\s+nostro)', text, re.DOTALL)
        if intercessioni_match:
            inter_list = re.split(r'\n(?=(?:Salva|Raccogli|Benedici|Mostra|Sii))', intercessioni_match.group(1))
            for inter in inter_list:
                inter_pulita = cls.clean_text(inter)
                if inter_pulita and len(inter_pulita) > 10:
                    data["intercessioni"].append(inter_pulita)

        orazione_match = re.search(r'ORAZIONE\s*\n(.*?Amen\.)', text, re.DOTALL)
        if orazione_match:
            data["orazione"] = orazione_match.group(1).strip()

        return data


class SantoParser(BaseLiturgiaParser):
    """Parser per Santo del Giorno - VERSIONE CORRETTA"""

    @staticmethod
    def converti_data(date_str: str) -> str:
        """Converte YYYYMMDD in 'DD Mese'"""
        if not date_str:
            return ""
        try:
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            giorno_num = date_obj.strftime("%d").lstrip('0')
            mese = date_obj.strftime("%B")

            mesi_map = {
                'January': 'Gennaio', 'February': 'Febbraio', 'March': 'Marzo',
                'April': 'Aprile', 'May': 'Maggio', 'June': 'Giugno',
                'July': 'Luglio', 'August': 'Agosto', 'September': 'Settembre',
                'October': 'Ottobre', 'November': 'Novembre', 'December': 'Dicembre'
            }
            mese_italiano = mesi_map.get(mese, mese)
            return f"{giorno_num} {mese_italiano}"
        except Exception as e:
            print(f"Errore conversione data: {e}")
            return ""

    @classmethod
    def parse(cls, text: str, data_str: str = None) -> Dict:
        """Parsifica il testo dei santi. data_str deve essere in formato YYYYMMDD"""
        data = {
            "giorno": "",
            "santo_principale": {"nome": "", "martirologio": ""},
            "altri_santi": [],
            "numero_santi_celebrati": 0
        }

        if not text or len(text) < 10:
            return data

        # Usa la data passata per evitare ambiguità
        if data_str:
            data["giorno"] = cls.converti_data(data_str)

        # Dividi il testo per blocchi di santi
        blocchi = re.split(
            r'\n(?=(?:San |Santa |Beato |Beata |Memoria facoltativa|Nel |A |Nel villaggio|Presso|Nell\'))',
            text
        )

        santo_trovato = False
        for blocco in blocchi:
            if not blocco.strip() or len(blocco) < 20:
                continue

            nome_match = re.search(r'((?:San|Santa|Beato|Beata)\s+[^,\n]+)', blocco, re.IGNORECASE)
            if not nome_match:
                continue

            nome = cls.clean_text(nome_match.group(1))
            martirologio = cls.clean_text(blocco)

            # Rimuovi il nome dal martirologio
            martirologio = re.sub(rf'^{re.escape(nome)}\s*[,.]?\s*', '', martirologio, flags=re.IGNORECASE)
            martirologio = martirologio.strip()

            if not santo_trovato:
                data["santo_principale"]["nome"] = nome
                martirologio_pulito = re.sub(
                    r"jQuery\('img\[data-enlargeable\]'\).*?\}\);?\s*\}\);?\s*\}\);",
                    '',
                    martirologio,
                    flags=re.DOTALL | re.IGNORECASE
                )
                data["santo_principale"]["martirologio"] = martirologio_pulito.strip()
                santo_trovato = True
            else:
                if (nome.lower() != data["santo_principale"]["nome"].lower() and nome and martirologio and len(
                        martirologio) > 10):
                    data["altri_santi"].append({"nome": nome, "martirologio": martirologio[:500]})

        data["numero_santi_celebrati"] = 1 + len(data["altri_santi"])
        return data


class LiturgiaManager(BaseLiturgiaParser):
    """Manager principale per la gestione della liturgia"""

    BASE_URL = "https://www.chiesacattolica.it"

    def __init__(self, output_dir: str = "json"):
        self.output_dir = output_dir
        self._create_dirs()

    def _create_dirs(self):
        for d in [self.output_dir]:
            if not os.path.exists(d):
                os.makedirs(d)

    def _fetch_and_parse(self, date_str: str, ora: str, marker: str, parser_class) -> Optional[Dict]:
        url = f"{self.BASE_URL}/la-liturgia-delle-ore/?data-liturgia={date_str}&ora={ora}"
        html = self.fetch_url(url)
        if not html:
            return None
        texts = self.estrai_testo_filtrato(html, marker)
        if not texts:
            return None
        testo_completo = '\n'.join(texts)
        return parser_class.parse(testo_completo)

    def get_single_day(self, date_str: str) -> Dict:
        """Recupera tutti i dati liturgici per una singola data (formato: YYYYMMDD)"""
        try:
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            formatted_date = date_obj.strftime("%d/%m/%Y")
        except ValueError:
            print(f"Errore: formato data non valido {date_str}")
            return {}

        data = {
            "data": formatted_date,
            "data_iso": date_str,
            "giorno_settimana": date_obj.strftime("%A"),
            "lodi_mattutine": None,
            "vespri": None,
            "santo_del_giorno": None
        }

        print(f"\n📅 Elaborazione: {formatted_date}")

        print("  → Scaricando lodi mattutine...")
        data["lodi_mattutine"] = self._fetch_and_parse(date_str, "lodi-mattutine", "Lodi mattutine", LodiParser)

        print("  → Scaricando vespri...")
        data["vespri"] = self._fetch_and_parse(date_str, "vespri", "Vespri", VespriParser)

        print("  → Scaricando santo del giorno...")
        url_santo = f"{self.BASE_URL}/santo-del-giorno/?data-liturgia={date_str}"
        html_santo = self.fetch_url(url_santo)
        if html_santo:
            texts = self.estrai_testo_filtrato(html_santo, "Santo del Giorno")
            texts = self._pulisci_santo_testo(texts)
            testo_santo = '\n'.join(texts)
            data["santo_del_giorno"] = SantoParser.parse(testo_santo, data_str=date_str)

        return data

    def get_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Recupera dati liturgici per un intervallo di date (formato: YYYYMMDD)"""
        try:
            start = datetime.strptime(start_date, "%Y%m%d")
            end = datetime.strptime(end_date, "%Y%m%d")
        except ValueError:
            print("Errore: formato data non valido. Usa YYYYMMDD")
            return []

        results = []
        current = start
        while current <= end:
            date_str = current.strftime("%Y%m%d")
            data = self.get_single_day(date_str)
            if data:
                results.append(data)
                self.save_json(data, f"liturgia_{date_str}.json")
            current += timedelta(days=1)
            time.sleep(1)

        return results

    def save_json(self, data: Dict, filename: str) -> bool:
        filepath = os.path.join(self.output_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ Salvato: {filepath}")
            return True
        except Exception as e:
            print(f"❌ Errore nel salvare {filepath}: {e}")
            return False

    @staticmethod
    def _pulisci_santo_testo(texts: List[str]) -> List[str]:
        filtered = []
        skip = False
        for t in texts:
            if "jQuery('img[data-enlargeable]')" in t:
                skip = True
                continue
            if skip:
                if "Memoria facoltativa" in t:
                    skip = False
                continue
            filtered.append(t)
        return filtered


if __name__ == "__main__":
    manager = LiturgiaManager()

    print("=" * 70)
    print("📖 PARSER LITURGIA CHIESA CATTOLICA")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("📅 Elaborazione intervallo di date...")
    print("=" * 70)
    results = manager.get_date_range("20251001", "20251031")

    print("\n" + "=" * 70)
    print(f"✨ Elaborazione completata! {len(results)} giorni salvati.")
    print("=" * 70)