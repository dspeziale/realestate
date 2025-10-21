import re
from bs4 import BeautifulSoup


class VespriParser:
    """Parser per i Vespri"""

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
        """Estrae la liturgia dei vespri"""
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
            "tipo": "vespri",
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

        # Estrai salmi e antifone
        text_clean = re.sub(r'\s+', ' ', text)

        salmi_matches = re.findall(
            r'(\d+)\s+ant\.\s+([^S]+?)\s*(?:SALMO|CANTICO)\s+([\d,:\-]+)\s+([^\n]+?)\s+(.*?)(?=\d+\s+ant\.|LETTURA\s+BREVE)',
            text_clean,
            re.DOTALL
        )

        for num_ant, testo_ant, num_salmo, titolo_salmo, contenuto_salmo in salmi_matches:
            contenuto_pulito = cls.clean_duplicate_lines(contenuto_salmo)

            data_info["salmi_e_antifone"].append({
                "antifona_numero": num_ant,
                "antifona_testo": cls.clean_text(testo_ant),
                "salmo_numero": cls.clean_text(num_salmo),
                "salmo_titolo": cls.clean_text(titolo_salmo),
                "salmo_contenuto": contenuto_pulito[:600]
            })

        # Estrai lettura breve
        lettura_match = re.search(r'LETTURA BREVE\s*([^\n]*)\s*(.*?)(?=RESPONSORIO)', text, re.DOTALL)
        if lettura_match:
            data_info["lettura_breve"] = {
                "riferimento": cls.clean_text(lettura_match.group(1)),
                "contenuto": cls.clean_text(lettura_match.group(2))[:400]
            }

        # Estrai responsorio breve
        responsorio_match = re.search(r'RESPONSORIO\s*(?:BREVE)?\s*(.*?)(?=Ant\.|INVOCAZIONI|CANTICO|$)', text,
                                      re.DOTALL)
        if responsorio_match:
            data_info["responsorio_breve"] = {
                "contenuto": cls.clean_text(responsorio_match.group(1))[:400]
            }

        # Estrai antifona benedicite (Magnificat)
        ant_ben_match = re.search(r'Ant\.\s+al\s+Magn\.\s+([^\n]+)', text)
        if ant_ben_match:
            data_info["antifona_benedicite"] = cls.clean_text(ant_ben_match.group(1))

        # Estrai cantico della Beata Vergine (Magnificat)
        cantico_match = re.search(
            r'CANTICO DELLA BEATA VERGINE\s+(Lc\s+[\d,:\-]+)\s+(.*?)(?=INTERCESSIONI|Padre nostro|$)', text, re.DOTALL)
        if cantico_match:
            data_info["cantico_benedicite"] = {
                "riferimento": cls.clean_text(cantico_match.group(1)),
                "contenuto": cls.clean_text(cantico_match.group(2))[:600]
            }

        # Estrai intercessioni
        intercessioni_match = re.search(r'INTERCESSIONI\s*(.*?)(?=Padre nostro)', text, re.DOTALL)
        if intercessioni_match:
            intercessioni_testo = intercessioni_match.group(1)
            intercessioni_list = re.split(r'\n(?=\s*[–\-])', intercessioni_testo)
            for inv in intercessioni_list:
                inv_pulita = cls.clean_text(inv)
                if inv_pulita and len(inv_pulita) > 5:
                    data_info["invocazioni"].append(inv_pulita)

        # Estrai orazione
        orazione_match = re.search(r'ORAZIONE\s*\n(.*?)(?=(?:Il Signore|Padre nostro|R\.|$))', text,
                                   re.MULTILINE | re.DOTALL)
        if orazione_match:
            data_info["orazione"] = cls.clean_text(orazione_match.group(1))

        return data_info