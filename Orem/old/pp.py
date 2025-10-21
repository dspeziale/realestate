import requests
from bs4 import BeautifulSoup

def estrai_lodi_filtrata(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    texts = []
    body = soup.body
    if not body:
        body = soup  # fallback

    # Prendiamo tutto il testo visibile
    all_texts = []
    for elem in body.find_all(string=True):
        t = elem.strip()
        if len(t) > 1:
            all_texts.append(t)

    # Trova la seconda occorrenza di "Lodi mattutine"
    count_lodi = 0
    start_index = 0
    for i, text in enumerate(all_texts):
        if "Lodi mattutine" in text:
            count_lodi += 1
            if count_lodi == 2:
                start_index = i
                break

    # Trova l'indice di "Condividi" dopo il start_index
    end_index = len(all_texts)
    for i in range(start_index, len(all_texts)):
        if "Condividi" in all_texts[i]:
            end_index = i
            break

    # Prendi solo il testo tra start_index e end_index
    texts = all_texts[start_index:end_index]

    # Rimuovi duplicati immediati per pulizia
    liturgia_testo = []
    prev = None
    for t in texts:
        if t != prev:
            liturgia_testo.append(t)
        prev = t

    return liturgia_testo

def estrai_vespri_filtrata(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    texts = []
    body = soup.body
    if not body:
        body = soup  # fallback

    # Prendiamo tutto il testo visibile
    all_texts = []
    for elem in body.find_all(string=True):
        t = elem.strip()
        if len(t) > 1:
            all_texts.append(t)

    # Trova la seconda occorrenza di "Lodi mattutine"
    count_lodi = 0
    start_index = 0
    for i, text in enumerate(all_texts):
        if "Vespri" in text:
            count_lodi += 1
            if count_lodi == 2:
                start_index = i
                break

    # Trova l'indice di "Condividi" dopo il start_index
    end_index = len(all_texts)
    for i in range(start_index, len(all_texts)):
        if "Condividi" in all_texts[i]:
            end_index = i
            break

    # Prendi solo il testo tra start_index e end_index
    texts = all_texts[start_index:end_index]

    # Rimuovi duplicati immediati per pulizia
    liturgia_testo = []
    prev = None
    for t in texts:
        if t != prev:
            liturgia_testo.append(t)
        prev = t

    return liturgia_testo

def pulisci_santo_testo(testo_lista):
    """
    Elimina da una lista di stringhe il blocco jQuery fino a "Memoria facoltativa" incluso
    """
    filtered_texts = []
    skip_mode = False

    for t in testo_lista:
        # Attiva skip_mode quando trovi jQuery
        if "jQuery('img[data-enlargeable]')" in t:
            skip_mode = True
            continue

        # Se siamo in skip_mode, continua a saltare
        if skip_mode:
            # Quando trovi "Memoria facoltativa", disattiva e salta anche questa riga
            if "Memoria facoltativa" in t:
                skip_mode = False
            continue

        # Aggiungi il testo solo se non siamo in skip_mode
        filtered_texts.append(t)

    return filtered_texts

def estrai_santo_filtrata(url):
    response = requests.get(url)
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')

    body = soup.body
    if not body:
        body = soup  # fallback

    # Prendiamo tutto il testo visibile
    all_texts = []
    for elem in body.find_all(string=True):
        t = elem.strip()
        if len(t) > 1:
            all_texts.append(t)

    # Trova la seconda occorrenza di "Santo del Giorno"
    count_santo = 1
    start_index = 0
    for i, text in enumerate(all_texts):
        if "Santo del Giorno" in text:
            count_santo += 1
            if count_santo == 2:
                start_index = i
                break

    # Trova l'indice di "Condividi" dopo il start_index
    end_index = len(all_texts)
    for i in range(start_index, len(all_texts)):
        if "Condividi" in all_texts[i]:
            end_index = i
            break

    # Prendi solo il testo tra start_index e end_index
    texts = all_texts[start_index:end_index]

    # Rimuovi duplicati immediati per pulizia
    liturgia_testo = []
    prev = None
    for t in texts:
        if t != prev:
            liturgia_testo.append(t)
        prev = t

    # Pulisci il blocco jQuery e "Memoria facoltativa"
    liturgia_testo = pulisci_santo_testo(liturgia_testo)

    return liturgia_testo

def salva_testo(lista_testo, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        for par in lista_testo:
            f.write(par + "\n")

if __name__ == "__main__":
    giorno='20251019'
    urlLodi = f"https://www.chiesacattolica.it/la-liturgia-delle-ore/?data-liturgia={giorno}&ora=lodi-mattutine"
    testo_lodi = estrai_lodi_filtrata(urlLodi)
    salva_testo(testo_lodi, f"txt/liturgia_filtrata_lodi_mattutine_{giorno}.txt")

    urlVespri = f"https://www.chiesacattolica.it/la-liturgia-delle-ore/?data-liturgia={giorno}&ora=vespri"
    testo_vespri = estrai_vespri_filtrata(urlVespri)
    salva_testo(testo_vespri, f"txt/liturgia_filtrata_vespri_{giorno}.txt")

    urlSanto = f"https://www.chiesacattolica.it/santo-del-giorno/?data-liturgia={giorno}"
    testo_santo = estrai_santo_filtrata(urlSanto)
    salva_testo(testo_santo, f"txt/liturgia_filtrata_santo_{giorno}.txt")

