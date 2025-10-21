import re
from bs4 import BeautifulSoup


class LodiParser:
    """Parser per le Lodi Mattutine"""

    @staticmethod
    def clean_text(text):
        """Pulisce il testo da spazi extra"""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def clean_duplicate_lines(testo):
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

    @classmethod
    def parse(cls, html):
        """Estrae la liturgia delle lodi con le 3 antifone e i 3 salmi/cantici"""
        soup = BeautifulSoup(html, 'html.parser')

        # Rimuovi elementi non rilevanti
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'meta']):
            elem.decompose()

        text = soup.get_text()

        # Filtra il testo inutile
        text = re.sub(r'Home\s*–.*?Chiudi', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'Cerca un argomento.*?(?=V\.)', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'Condividi.*?(?=$)', '', text, flags=re.IGNORECASE | re.DOTALL)

        # Estrai solo la parte rilevante
        start_idx = text.find('V.')
        if start_idx == -1:
            return None

        text = text[start_idx:]

        data_info = {
            "tipo": "lodi-mattutine",
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
                "versicolo": cls.clean_text(v),
                "risposta": cls.clean_text(r)
            })

        # Estrai Gloria al Padre
        gloria_match = re.search(r'Gloria al Padre[\s\S]*?nei secoli dei secoli\. Amen\.?\s*(?:Alleluia\.)?', text)
        if gloria_match:
            data_info["gloria_al_padre"] = cls.clean_text(gloria_match.group(0))

        # Estrai INNO
        inno_match = re.search(r'INNO\s*\n(.*?)(?=\d+\s+ant\.)', text, re.DOTALL)
        if inno_match:
            data_info["inno"] = cls.clean_text(inno_match.group(1))

        # ===== NUOVO APPROCCIO: Dividi per antifone =====
        # Trova tutte le posizioni delle antifone (1 ant., 2 ant., 3 ant.)
        ant_positions = []
        for match in re.finditer(r'(\d+)\s+ant\.', text):
            ant_positions.append((match.start(), match.group(1)))

        # Estrai le sezioni di ogni antifona
        for idx, (start_pos, num_ant) in enumerate(ant_positions):
            # La fine della sezione è l'inizio della prossima antifona oppure "LETTURA BREVE"
            if idx + 1 < len(ant_positions):
                end_pos = ant_positions[idx + 1][0]
            else:
                # Trova "LETTURA BREVE" come fine
                lettura_match = re.search(r'LETTURA\s+BREVE', text[start_pos:])
                if lettura_match:
                    end_pos = start_pos + lettura_match.start()
                else:
                    end_pos = len(text)

            sezione = text[start_pos:end_pos]

            # Estrai il testo dell'antifona (da "ant." fino a SALMO/CANTICO, anche su più righe)
            ant_text_match = re.search(r'ant\.\s*\n\s*(.+?)(?=\n\s*(?:SALMO|CANTICO))', sezione, re.DOTALL)
            if ant_text_match:
                testo_ant = cls.clean_text(ant_text_match.group(1))
            else:
                testo_ant = ""

            # Estrai SALMO o CANTICO con numero e titolo
            salmo_cantico_match = re.search(
                r'(SALMO|CANTICO)\s+(.+?)\s+([A-Z][^\n]*)\n(.*?)$',
                sezione,
                re.DOTALL
            )

            if salmo_cantico_match:
                tipo = salmo_cantico_match.group(1)
                numero = cls.clean_text(salmo_cantico_match.group(2))
                titolo = cls.clean_text(salmo_cantico_match.group(3))
                contenuto_raw = salmo_cantico_match.group(4)

                # Pulisci il contenuto
                contenuto_pulito = cls.clean_duplicate_lines(contenuto_raw)

                data_info["salmi_e_antifone"].append({
                    "numero_antifona": num_ant,
                    "testo_antifona": testo_ant,
                    "tipo_salmo_cantico": tipo,
                    "numero_salmo_cantico": numero,
                    "titolo_salmo_cantico": titolo,
                    "contenuto_salmo_cantico": contenuto_pulito[:800]
                })

        # Estrai lettura breve
        lettura_match = re.search(r'LETTURA BREVE\s*([^\n]*)\s*(.*?)(?=RESPONSORIO)', text, re.DOTALL)
        if lettura_match:
            data_info["lettura_breve"] = {
                "riferimento": cls.clean_text(lettura_match.group(1)),
                "contenuto": cls.clean_text(lettura_match.group(2))[:400]
            }

        # Estrai responsorio breve
        responsorio_match = re.search(r'RESPONSORIO\s*(?:BREVE)?\s*(.*?)(?=Ant\.|INVOCAZIONI|CANTICO DI|$)', text,
                                      re.DOTALL)
        if responsorio_match:
            data_info["responsorio_breve"] = {
                "contenuto": cls.clean_text(responsorio_match.group(1))[:400]
            }

        # Estrai antifona Benedicite (al Ben.)
        ant_ben_match = re.search(r'Ant\.\s+al\s+Ben\.\s+([^\n]+)', text)
        if ant_ben_match:
            data_info["antifona_benedicite"] = cls.clean_text(ant_ben_match.group(1))

        # Estrai cantico di Zaccaria
        cantico_match = re.search(
            r'CANTICO DI ZACCARIA\s+(Lc\s+[\d,:\-]+)\s+([^\n]+)\s*(.*?)(?=INVOCAZIONI|Padre nostro|$)',
            text,
            re.DOTALL
        )
        if cantico_match:
            data_info["cantico_benedicite"] = {
                "riferimento": cls.clean_text(cantico_match.group(1)),
                "titolo": cls.clean_text(cantico_match.group(2)),
                "contenuto": cls.clean_text(cantico_match.group(3))[:600]
            }

        # Estrai invocazioni
        invocazioni_match = re.search(r'INVOCAZIONI\s*(.*?)(?=Padre nostro)', text, re.DOTALL)
        if invocazioni_match:
            invocazioni_testo = invocazioni_match.group(1)
            invocazioni_list = re.split(r'\n(?=\s*[–\-])', invocazioni_testo)
            for inv in invocazioni_list:
                inv_pulita = cls.clean_text(inv)
                if inv_pulita and len(inv_pulita) > 5:
                    data_info["invocazioni"].append(inv_pulita)

        # Estrai orazione
        orazione_match = re.search(r'ORAZIONE\s*\n(.*?)(?=(?:Il Signore|Padre nostro|R\.|$))', text,
                                   re.MULTILINE | re.DOTALL)
        if orazione_match:
            data_info["orazione"] = cls.clean_text(orazione_match.group(1))

        return data_info