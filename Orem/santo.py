import re
from bs4 import BeautifulSoup


class SantoParser:
    """Parser per il Santo del Giorno"""

    @staticmethod
    def clean_text(text):
        """Pulisce il testo da spazi extra"""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def parse(cls, html):
        """Estrae il santo del giorno"""
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()

        # Rimuovi riferimenti
        text = re.sub(r'Home\s*–\s*Santo del Giorno', '', text, flags=re.IGNORECASE)
        text = re.sub(r'Condividi\s+Invia\s+Stampa.*?(?=$)', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = text.strip()

        # Estrai giorno
        giorno = ""
        giorno_match = re.search(
            r'(\d+)\s+(?:OTTOBRE|NOVEMBRE|DICEMBRE|GENNAIO|FEBBRAIO|MARZO|APRILE|MAGGIO|GIUGNO|LUGLIO|AGOSTO|SETTEMBRE)',
            text, re.IGNORECASE)
        if giorno_match:
            giorno = giorno_match.group(1)

        # Estrai titolo principale
        titolo_principale = ""
        titolo_match = re.search(
            r'(\d+)\s+(?:OTTOBRE|NOVEMBRE|DICEMBRE|GENNAIO|FEBBRAIO|MARZO|APRILE|MAGGIO|GIUGNO|LUGLIO|AGOSTO|SETTEMBRE)\s+\d+\s+(.+?)\s*-',
            text, re.IGNORECASE)
        if titolo_match:
            titolo_principale = cls.clean_text(titolo_match.group(2))
            titolo_principale = re.sub(r'Santo del giorno\s+', '', titolo_principale, flags=re.IGNORECASE).strip()

        # Estrai martirologio principale
        martirologio_principale = ""
        mart_match = re.search(r'Dal Martirologio\s*\n(.*?)(?=\n(?:A |Nell\'|Presso|Nel |Commemorazione|^$))', text,
                               re.MULTILINE | re.DOTALL)
        if mart_match:
            martirologio_principale = cls.clean_text(mart_match.group(1))
            martirologio_principale = re.sub(r'Condividi\s+Invia\s+Stampa.*?(?=$)', '', martirologio_principale,
                                             flags=re.IGNORECASE | re.DOTALL)

        # Estrai altri santi
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

            nome_santo = cls.clean_text(prima_linea)
            martirologio = cls.clean_text(frase)

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