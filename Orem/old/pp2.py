import re
import json


class LodiTextParser:
    """Parser per estrarre dati dalle Lodi Mattutine da testo grezzo"""

    @staticmethod
    def clean_text(text):
        """Pulisce il testo da spazi extra e caratteri di escape"""
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('Ã ', '').replace('Â', '').replace('â€™', "'")
        text = text.replace('â€œ', '"').replace('â€', '–')
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
    def parse(cls, testo):
        """Estrae la liturgia delle lodi dal testo"""

        data_info = {
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

        # Estrai titolo
        titolo_match = re.search(r'(MARTEDI\'.*?SALTERIO)', testo)
        if titolo_match:
            data_info["titolo"] = cls.clean_text(titolo_match.group(1))

        # Estrai versicoli
        versicoli = re.findall(r'V\.\s*\n\s*([^\n]+)\n\s*R\.\s*\n\s*([^\n]+)', testo)
        for v, r in versicoli[:1]:
            data_info["versicoli"].append({
                "versicolo": cls.clean_text(v),
                "risposta": cls.clean_text(r)
            })

        # Estrai Gloria al Padre
        gloria_match = re.search(
            r'Gloria al Padre[\s\S]*?nei secoli dei secoli\.\s*Amen\.?\s*(?:Alleluia\.)?',
            testo,
            re.IGNORECASE
        )
        if gloria_match:
            data_info["gloria_al_padre"] = cls.clean_text(gloria_match.group(0))

        # Estrai INNO
        inno_match = re.search(r'INNO\s*\n(.*?)(?=\d+\s+ant\.)', testo, re.DOTALL)
        if inno_match:
            data_info["inno"] = cls.clean_text(inno_match.group(1))

        # Estratto la sezione principale (da prima antifona a lettura breve)
        sezione_principale = re.search(r'1\s+ant\..*?(?=LETTURA\s+BREVE)', testo, re.DOTALL)
        if not sezione_principale:
            print("[ERROR] Sezione principale non trovata!")
            return data_info

        testo_principale = sezione_principale.group(0)
        print(f"[DEBUG] Lunghezza testo principale: {len(testo_principale)}")

        # Cerca blocchi: n ant. ... SALMO/CANTICO ... n ant.
        # Pattern: antifona numero N, testo, poi SALMO/CANTICO, poi contenuto fino a "N ant."
        for num_ant in ['1', '2', '3']:
            pattern = rf'({num_ant})\s+ant\.\s*\n\s*([^\n]+(?:\n[^\n]+)*?)\n+(SALMO|CANTICO)\s*([^\s]+(?:\s+[\d,:\-]+)*?)\s+([^\n]+)\n(.*?)\n{num_ant}\s+ant\.'

            match = re.search(pattern, testo_principale, re.DOTALL)

            if match:
                num_ant_found = match.group(1)
                testo_ant = match.group(2)
                tipo = match.group(3)
                num_salmo_raw = match.group(4)
                titolo_salmo = match.group(5)
                contenuto_salmo_raw = match.group(6)

                # Estrai il numero corretto (per CANTICO potrebbe essere "Tb 13, 2-10a")
                if tipo == "CANTICO":
                    cantico_match = re.search(r'(\d+[\d,:\-]*)', num_salmo_raw)
                    if cantico_match:
                        num_salmo = cantico_match.group(1)
                    else:
                        num_salmo = num_salmo_raw
                else:
                    num_salmo = num_salmo_raw

                # Pulisci il contenuto: rimuovi tutto fino a dopo la prima ")"
                # Il contenuto reale inizia dopo la chiusura della citazione della fonte
                contenuto_match = re.search(r'\)\.?\s*(.*)', contenuto_salmo_raw, re.DOTALL)
                if contenuto_match:
                    contenuto_salmo = contenuto_match.group(1)
                else:
                    contenuto_salmo = contenuto_salmo_raw

                contenuto_pulito = cls.clean_duplicate_lines(contenuto_salmo)

                print(f"[DEBUG] ✓ Antifona {num_ant_found} trovata: {tipo} {num_salmo}")

                data_info["antifone_e_salmi"].append({
                    "antifona_numero": num_ant_found,
                    "antifona_testo": cls.clean_text(testo_ant),
                    "tipo": tipo,
                    "numero": cls.clean_text(num_salmo),
                    "titolo": cls.clean_text(titolo_salmo),
                    "contenuto": contenuto_pulito
                })
            else:
                print(f"[DEBUG] ❌ Antifona {num_ant} non trovata con pattern standard")

                # Debug: mostra cosa c'è tra "2 ant." per capire perché non matcha
                debug_pattern = rf'({num_ant})\s+ant\.(.*?)(?=\d+\s+ant\.|LETTURA)'
                debug_match = re.search(debug_pattern, testo_principale, re.DOTALL)
                if debug_match and num_ant == '2':
                    print(f"[DEBUG] Contenuto tra 2 ant.:\n{debug_match.group(2)[:300]}")

        # Estrai LETTURA BREVE
        lettura_match = re.search(
            r'LETTURA\s+BREVE\s*\n\s*([^\n]+)\n(.*?)(?=RESPONSORIO)',
            testo,
            re.DOTALL
        )
        if lettura_match:
            data_info["lettura_breve"] = {
                "riferimento": cls.clean_text(lettura_match.group(1)),
                "contenuto": cls.clean_text(lettura_match.group(2))[:400]
            }

        # Estrai RESPONSORIO BREVE
        responsorio_match = re.search(
            r'RESPONSORIO\s+BREVE\s*\n(.*?)(?=Ant\.\s+al\s+Ben\.)',
            testo,
            re.DOTALL
        )
        if responsorio_match:
            contenuto_resp = responsorio_match.group(1).strip()
            data_info["responsorio_breve"] = {"contenuto": contenuto_resp}

        # Estrai antifona al Cantico (tra "Ant. al Ben." e "INVOCAZIONI")
        ant_match = re.search(r'Ant\.\s+al\s+Ben\.\s*\n\s*([^\n]+(?:\n[^\n]+)*?)\n\s*(?=CANTICO|INVOCAZIONI)', testo)
        if ant_match:
            data_info["antifona_cantico_finale"] = cls.clean_text(ant_match.group(1))

        # Estrai CANTICO DI ZACCARIA (tra titolo e Gloria al Padre)
        cantico_match = re.search(
            r'CANTICO\s+DI\s+ZACCARIA\s*\n\s*(Lc[\s\d,:\-]+)\n(.*?)(?=Gloria al Padre)',
            testo,
            re.DOTALL
        )
        if cantico_match:
            contenuto_raw = cantico_match.group(2)
            # Salta la prima riga (titolo) e prendi il resto
            linee = contenuto_raw.split('\n', 1)
            contenuto_pulito = linee[1].strip() if len(linee) > 1 else contenuto_raw.strip()

            data_info["cantico_finale"] = {
                "riferimento": cls.clean_text(cantico_match.group(1)),
                "contenuto": contenuto_pulito
            }

        # Estrai INVOCAZIONI
        invocazioni_match = re.search(
            r'INVOCAZIONI\s*\n(.*?)(?=Padre\s+nostro)',
            testo,
            re.DOTALL
        )
        if invocazioni_match:
            invocazioni_testo = invocazioni_match.group(1)
            invocazioni_list = re.split(r'\n(?=(?:Re\s|Cristo|Signore|Concedici|Infondi|Fa))', invocazioni_testo)
            for inv in invocazioni_list:
                inv_pulita = cls.clean_text(inv)
                if inv_pulita and len(inv_pulita) > 10:
                    data_info["invocazioni"].append(inv_pulita)

        # Estrai ORAZIONE (da ORAZIONE a Amen.)
        orazione_match = re.search(
            r'ORAZIONE\s*\n(.*?Amen\.)',
            testo,
            re.DOTALL
        )
        if orazione_match:
            data_info["orazione"] = orazione_match.group(1).strip()

        return data_info

class VespriTextParser:
    """Parser per estrarre dati dai Vespri da testo grezzo"""

    @staticmethod
    def clean_text(text):
        """Pulisce il testo da spazi extra e caratteri di escape"""
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('Ãƒ ', '').replace('Ã‚', '').replace('Ã¢â‚¬â„¢', "'")
        text = text.replace('Ã¢â‚¬Å"', '"').replace('Ã¢â‚¬', 'â€"')
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
    def parse(cls, testo):
        """Estrae la liturgia dei vespri dal testo"""

        data_info = {
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

        # Estrai titolo
        titolo_match = re.search(r'(LUNEDI\'.*?SALTERIO)', testo)
        if titolo_match:
            data_info["titolo"] = cls.clean_text(titolo_match.group(1))

        # Estrai versicoli
        versicoli = re.findall(r'V\.\s*\n\s*([^\n]+)\n\s*R\.\s*\n\s*([^\n]+)', testo)
        for v, r in versicoli[:1]:
            data_info["versicoli"].append({
                "versicolo": cls.clean_text(v),
                "risposta": cls.clean_text(r)
            })

        # Estrai Gloria al Padre
        gloria_match = re.search(
            r'Gloria al Padre[\s\S]*?nei secoli dei secoli\.\s*Amen\.?\s*(?:Alleluia\.)?',
            testo,
            re.IGNORECASE
        )
        if gloria_match:
            data_info["gloria_al_padre"] = cls.clean_text(gloria_match.group(0))

        # Estrai INNO
        inno_match = re.search(r'INNO\s*\n(.*?)(?=\d+\s+ant\.)', testo, re.DOTALL)
        if inno_match:
            data_info["inno"] = cls.clean_text(inno_match.group(1))

        # Estratto la sezione principale (da prima antifona a lettura breve)
        sezione_principale = re.search(r'1\s+ant\..*?(?=LETTURA\s+BREVE)', testo, re.DOTALL)
        if not sezione_principale:
            print("[ERROR] Sezione principale non trovata!")
            return data_info

        testo_principale = sezione_principale.group(0)
        print(f"[DEBUG] Lunghezza testo principale: {len(testo_principale)}")

        # Cerca blocchi: n ant. ... SALMO/CANTICO ... n ant.
        for num_ant in ['1', '2', '3']:
            pattern = rf'({num_ant})\s+ant\.\s*\n\s*([^\n]+(?:\n[^\n]+)*?)\n+(SALMO|CANTICO)\s*([^\s]+(?:\s+[\d,:\-]+)*?)\s+([^\n]+)\n(.*?)\n{num_ant}\s+ant\.'

            match = re.search(pattern, testo_principale, re.DOTALL)

            if match:
                num_ant_found = match.group(1)
                testo_ant = match.group(2)
                tipo = match.group(3)
                num_salmo_raw = match.group(4)
                titolo_salmo = match.group(5)
                contenuto_salmo_raw = match.group(6)

                # Estrai il numero corretto (per CANTICO potrebbe essere "Cfr. Ef 1, 3-10")
                if tipo == "CANTICO":
                    cantico_match = re.search(r'(\d+[\d,:\-]*)', num_salmo_raw)
                    if cantico_match:
                        num_salmo = cantico_match.group(1)
                    else:
                        num_salmo = num_salmo_raw
                else:
                    num_salmo = num_salmo_raw

                # Pulisci il contenuto: rimuovi tutto fino a dopo la prima ")"
                contenuto_match = re.search(r'\)\.?\s*(.*)', contenuto_salmo_raw, re.DOTALL)
                if contenuto_match:
                    contenuto_salmo = contenuto_match.group(1)
                else:
                    contenuto_salmo = contenuto_salmo_raw

                contenuto_pulito = cls.clean_duplicate_lines(contenuto_salmo)

                print(f"[DEBUG] ✓ Antifona {num_ant_found} trovata: {tipo} {num_salmo}")

                data_info["antifone_e_salmi"].append({
                    "antifona_numero": num_ant_found,
                    "antifona_testo": cls.clean_text(testo_ant),
                    "tipo": tipo,
                    "numero": cls.clean_text(num_salmo),
                    "titolo": cls.clean_text(titolo_salmo),
                    "contenuto": contenuto_pulito
                })
            else:
                print(f"[DEBUG] ❌ Antifona {num_ant} non trovata")

        # Estrai LETTURA BREVE
        lettura_match = re.search(
            r'LETTURA\s+BREVE\s*\n\s*([^\n]+)\n(.*?)(?=RESPONSORIO)',
            testo,
            re.DOTALL
        )
        if lettura_match:
            data_info["lettura_breve"] = {
                "riferimento": cls.clean_text(lettura_match.group(1)),
                "contenuto": cls.clean_text(lettura_match.group(2))
            }

        # Estrai RESPONSORIO BREVE
        responsorio_match = re.search(
            r'RESPONSORIO\s+BREVE\s*\n(.*?)(?=Ant\.\s+al\s+Magn\.)',
            testo,
            re.DOTALL
        )
        if responsorio_match:
            contenuto_resp = responsorio_match.group(1).strip()
            data_info["responsorio_breve"] = {"contenuto": contenuto_resp}

        # Estrai antifona al Cantico (tra "Ant. al Magn." e "CANTICO")
        ant_match = re.search(r'Ant\.\s+al\s+Magn\.\s*\n\s*([^\n]+(?:\n[^\n]+)*?)\n\s*(?=CANTICO|INTERCESSIONI)', testo)
        if ant_match:
            data_info["antifona_cantico_finale"] = cls.clean_text(ant_match.group(1))

        # Estrai CANTICO DELLA BEATA VERGINE (Magnificat)
        cantico_match = re.search(
            r'CANTICO\s+DELLA\s+BEATA\s+VERGINE\s*\n\s*(Lc[\s\d,:\-]+)\n(.*?)(?=Gloria al Padre)',
            testo,
            re.DOTALL
        )
        if cantico_match:
            contenuto_raw = cantico_match.group(2)
            # Salta la prima riga (titolo) e prendi il resto
            linee = contenuto_raw.split('\n', 1)
            contenuto_pulito = linee[1].strip() if len(linee) > 1 else contenuto_raw.strip()

            data_info["cantico_finale"] = {
                "riferimento": cls.clean_text(cantico_match.group(1)),
                "contenuto": contenuto_pulito
            }

        # Estrai INTERCESSIONI
        intercessioni_match = re.search(
            r'INTERCESSIONI\s*\n(.*?)(?=Padre\s+nostro)',
            testo,
            re.DOTALL
        )
        if intercessioni_match:
            intercessioni_testo = intercessioni_match.group(1)
            intercessioni_list = re.split(r'\n(?=(?:Salva|Raccogli|Benedici|Mostra|Sii))', intercessioni_testo)
            for inter in intercessioni_list:
                inter_pulita = cls.clean_text(inter)
                if inter_pulita and len(inter_pulita) > 10:
                    data_info["intercessioni"].append(inter_pulita)

        # Estrai ORAZIONE (da ORAZIONE a Amen.)
        orazione_match = re.search(
            r'ORAZIONE\s*\n(.*?Amen\.)',
            testo,
            re.DOTALL
        )
        if orazione_match:
            data_info["orazione"] = orazione_match.group(1).strip()

        return data_info

class SantoTextParser:
    """Parser per estrarre dati dai Santi da testo grezzo"""

    @staticmethod
    def clean_text(text):
        """Pulisce il testo da spazi extra e caratteri di escape"""
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('Ãƒ ', '').replace('Ã‚', '').replace('Ã¢â‚¬â„¢', "'")
        text = text.replace('Ã¢â‚¬Å"', '"').replace('Ã¢â‚¬', 'â€"')
        text = text.replace('â€™', "'").replace('â€"', '–')
        return text.strip()

    @classmethod
    def parse(cls, testo_lista):
        """Estrae i santi dal testo (lista di stringhe o stringa)"""

        data_info = {
            "giorno": "",
            "santo_principale": {
                "nome": "",
                "martirologio": ""
            },
            "altri_santi": []
        }

        # Se è una stringa, usala direttamente; altrimenti unisci la lista
        if isinstance(testo_lista, str):
            testo = testo_lista
        else:
            testo = '\n'.join(testo_lista)

        print(f"[DEBUG] Testo ricevuto: {len(testo)} caratteri")

        # Estrai giorno
        giorno_match = re.search(
            r'(\d+)\s+(Gennaio|Febbraio|Marzo|Aprile|Maggio|Giugno|Luglio|Agosto|Settembre|Ottobre|Novembre|Dicembre)',
            testo,
            re.IGNORECASE
        )
        if giorno_match:
            data_info["giorno"] = f"{giorno_match.group(1)} {giorno_match.group(2)}"
            print(f"[DEBUG] Giorno trovato: {data_info['giorno']}")

        # Estrai il santo principale (prima occorrenza)
        primo_santo_match = re.search(
            r'((?:San|Santa|Beato|Beata)[^\n]*)\nDal Martirologio\n(.*?)(?=\nMemoria facoltativa\n(?:San|Santa|Beato|Beata)|$)',
            testo,
            re.DOTALL | re.IGNORECASE
        )

        if primo_santo_match:
            nome_principale = primo_santo_match.group(1).strip()
            martirologio_principale = primo_santo_match.group(2).strip()

            data_info["santo_principale"]["nome"] = cls.clean_text(nome_principale)
            data_info["santo_principale"]["martirologio"] = cls.clean_text(martirologio_principale)
            print(f"[DEBUG] Santo principale: {data_info['santo_principale']['nome']}")

        # Estrai gli altri santi
        # Pattern: nome santo, opzionale "Memoria facoltativa", poi "Dal Martirologio", poi martirologio
        altri_santi_pattern = r'(?:Memoria facoltativa\n)?((?:San|Santa|Beato|Beata)[^\n]*)\nDal Martirologio\n(.*?)(?=\n(?:Memoria facoltativa\n)?(?:San|Santa|Beato|Beata)|$)'

        for match in re.finditer(altri_santi_pattern, testo, re.DOTALL | re.IGNORECASE):
            nome = match.group(1).strip()
            martirologio = match.group(2).strip()

            nome_pulito = cls.clean_text(nome)
            martirologio_pulito = cls.clean_text(martirologio)

            # Salta il santo principale e stringhe vuote
            if (nome_pulito and
                    martirologio_pulito and
                    nome_pulito.lower() != data_info["santo_principale"]["nome"].lower()):
                data_info["altri_santi"].append({
                    "nome": nome_pulito,
                    "martirologio": martirologio_pulito
                })
                print(f"[DEBUG] Santo trovato: {nome_pulito[:50]}...")

        data_info["numero_santi_celebrati"] = 1 + len(data_info["altri_santi"])
        print(f"[DEBUG] Totale santi: {data_info['numero_santi_celebrati']}")

        return data_info

def Process_Lodi(giorno = 20251020):
    with open(f'txt/liturgia_filtrata_lodi_mattutine_{giorno}.txt', 'r', encoding='utf-8') as f:
        testo = f.read()

    # Parsifica il testo
    parser = LodiTextParser()
    dati = parser.parse(testo)

    # Salva in JSON
    with open(f'json/lodi_mattutine_{giorno}.json', 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)

def Process_Vespri(giorno = 20251020):
    # VESPRI
    with open(f'txt/liturgia_filtrata_vespri_{giorno}.txt', 'r', encoding='utf-8') as f:
        testo = f.read()

    # Parsifica il testo Vespri
    print("Parsifica il testo Vespri")
    parser = VespriTextParser()
    dati = parser.parse(testo)

    with open(f'json/vespri_{giorno}.json', 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)

def Process_Santo(giorno = 20251020):
    # SANTO
    with open(f'txt/liturgia_filtrata_santo_{giorno}.txt', 'r', encoding='utf-8') as f:
        testo = f.read()
    parser = SantoTextParser()

    dati = parser.parse(testo)
    print(dati)
    with open(f'json/santo_{giorno}.json', 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)

def main():
    # LODI
    giorno=20251019
    Process_Lodi(giorno)
    Process_Vespri(giorno)
    Process_Santo(giorno)

if __name__ == "__main__":
    main()