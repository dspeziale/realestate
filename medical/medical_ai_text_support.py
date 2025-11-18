"""
MEDICAL AI - VERSIONE AVANZATA CON REPORT PDF
Domande strutturate per il medico + Report PDF professionale
"""

import requests
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime
# Import ReportLab rimossi - usiamo JSON!


# ============================================================================
# 1. CONFIGURAZIONE
# ============================================================================

class Config:
    OLLAMA_HOST = "http://localhost:11434"
    OLLAMA_MODEL = "gpt-oss:120b-cloud"
    PDF_INPUT_PATH = r"C:\logs\daniele"
    PDF_OUTPUT_PATH = r"C:\logs\reports"


config = Config()


# ============================================================================
# 2. LETTURA PDF
# ============================================================================

def extract_text_from_pdf(pdf_path):
    """Estrae testo da un PDF"""
    try:
        import PyPDF2
    except ImportError:
        print(" PyPDF2 non installato!")
        print("   Installa con: pip install PyPDF2")
        return None

    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            print(f"    {pdf_path.name}: {len(pdf_reader.pages)} pagine")

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"

        return text
    except Exception as e:
        print(f"    Errore lettura {pdf_path.name}: {e}")
        return None


def estrai_nome_paziente(documents: List[str]) -> str:
    """Estrae il nome del paziente dalla documentazione"""
    import re

    if not documents:
        return None

    # Combina tutti i documenti
    full_text = "\n".join(documents)

    # Pattern comuni per il nome del paziente
    pattern_nomi = [
        r'(?:Paziente|PAZIENTE|Patient|PATIENT)[\s:]*([A-Za-z\s\-àèéìòùÀÈÉÌÒÙ]{3,50}?)(?:\n|$)',
        r'(?:Nome|NOME|Name|NAME)[\s:]*([A-Za-z\s\-àèéìòùÀÈÉÌÒÙ]{3,50}?)(?:\n|$)',
        r'(?:Sig\.|Sig|Signora|Signore|Dr|Dott)[\s\.]*([A-Za-z\s\-àèéìòùÀÈÉÌÒÙ]{3,50}?)(?:\n|,)',
        r'^([A-Z][a-z]+[\s]+[A-Z][a-z]+)(?:\n|$)',  # Inizio linea: Nome Cognome
        r'(?:ref|REFERTO|referenza|Nominativo).*?(?:[\n]?)([A-Z][a-z]+[\s]+[A-Z][a-z]+)',
    ]

    for pattern in pattern_nomi:
        match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if match:
            nome = match.group(1).strip()
            # Filtra risultati troppo generici
            if nome and len(nome) > 3 and nome.lower() not in ['di', 'da', 'la', 'le', 'del', 'dei', 'per']:
                # Limita a max 2 parole (nome + cognome)
                parole = nome.split()
                if len(parole) <= 3:
                    print(f" Nome paziente trovato: {nome}")
                    return nome

    return None


def extract_text_from_txt(txt_path):
    """Estrae testo da un file TXT"""
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            text = file.read()
        return text
    except UnicodeDecodeError:
        # Prova con encoding diverso
        try:
            with open(txt_path, 'r', encoding='latin-1') as file:
                text = file.read()
            return text
        except Exception as e:
            print(f"    Errore lettura {txt_path.name}: {e}")
            return None
    except Exception as e:
        print(f"    Errore lettura {txt_path.name}: {e}")
        return None


def load_documents_from_directory(directory):
    """Carica tutti i PDF e TXT da una directory"""
    base_path = Path(directory)

    if not base_path.exists():
        print(f" Directory non trovata: {directory}")
        return [], None

    documents = []

    # Carica file PDF
    pdf_files = list(base_path.glob("*.pdf"))
    txt_files = list(base_path.glob("*.txt"))

    total_files = len(pdf_files) + len(txt_files)

    if not total_files:
        print(f" Nessun file (PDF/TXT) trovato in: {directory}")
        return [], None

    print(f"\n Trovati {len(pdf_files)} PDF e {len(txt_files)} TXT in {directory}")

    # Leggi i PDF
    for pdf_file in pdf_files:
        print(f"\n 📄 Leggo PDF: {pdf_file.name}")
        text = extract_text_from_pdf(pdf_file)

        if text and len(text.strip()) > 50:
            documents.append(text)
            print(f"    ✅ Estratti {len(text)} caratteri")
        else:
            print(f"   ⚠️ AVVISO: PDF vuoto o illeggibile")

    # Leggi i TXT
    for txt_file in txt_files:
        print(f"\n 📝 Leggo TXT: {txt_file.name}")
        text = extract_text_from_txt(txt_file)

        if text and len(text.strip()) > 20:
            documents.append(text)
            print(f"    ✅ Estratti {len(text)} caratteri")
        else:
            print(f"   ⚠️ AVVISO: TXT vuoto o illeggibile")

    # Estrai il nome del paziente dalla documentazione
    paziente_nome = estrai_nome_paziente(documents)

    return documents, paziente_nome


# ============================================================================
# 3. VERIFICHE
# ============================================================================

def check_ollama():
    """Verifica se OLLAMA è online"""
    try:
        response = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=2)
        if response.status_code == 200:
            print(" OLLAMA è ONLINE")
            return True
    except:
        pass

    print("""
     OLLAMA NON è online!

    Installa OLLAMA da: https://ollama.ai
    Poi scarica i modelli:

    $ ollama pull mistral:7b
    $ ollama pull neural-chat:7b

    Infine, avvia:
    $ ollama serve &
    """)
    return False


# ============================================================================
# 4. GENERAZIONE TESTO (LLM)
# ============================================================================

def generate_text(prompt, model=None, max_tokens=1024):
    """Genera testo usando OLLAMA"""
    if model is None:
        model = config.OLLAMA_MODEL

    print(f"Generando...")

    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1,
            }
        }

        response = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=600  # 10 minuti
        )
        response.raise_for_status()

        result = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                result += data.get("response", "")

        print(f" Completato")
        return result.strip()

    except Exception as e:
        print(f" Errore: {e}")
        raise


# ============================================================================
# 5. RICERCA TESTUALE SEMPLICE (NO EMBEDDINGS!)
# ============================================================================

class SimpleDocumentStore:
    """Store di documenti con ricerca testuale semplice"""

    def __init__(self):
        self.documents = {}
        print(" Document Store inizializzato")

    def add_documents(self, patient_id, documents: List[str]):
        """Aggiunge documenti per un paziente"""
        print(f"\n Caricando {len(documents)} documenti...")

        # Combina tutti i documenti
        full_text = "\n\n---NUOVO DOCUMENTO---\n\n".join(documents)

        self.documents[patient_id] = {
            "full_text": full_text,
            "parts": documents,
            "char_count": len(full_text)
        }

        print(f" {len(documents)} documenti caricati ({len(full_text)} caratteri totali)")
        return True

    def search(self, patient_id: str, query: str, context_chars=2000) -> str:
        """Cerca nel testo e ritorna il contesto"""

        if patient_id not in self.documents:
            return ""

        doc_data = self.documents[patient_id]
        full_text = doc_data["full_text"]

        # Ricerca case-insensitive
        query_lower = query.lower()
        full_text_lower = full_text.lower()

        # Trova la prima occorrenza
        idx = full_text_lower.find(query_lower)

        if idx == -1:
            # Se non trova la query esatta, ritorna l'inizio del testo
            return full_text[:context_chars * 3]

        # Ritorna il contesto attorno alla query
        start = max(0, idx - context_chars)
        end = min(len(full_text), idx + context_chars)

        return full_text[start:end]

    def get_all_text(self, patient_id: str) -> str:
        """Ritorna tutto il testo per il paziente"""
        if patient_id not in self.documents:
            return ""
        return self.documents[patient_id]["full_text"]


# ============================================================================
# 6. DOMANDE STRUTTURATE PER IL MEDICO
# ============================================================================

DOMANDE_MEDICO = [
    {
        "id": "anamnesi",
        "categoria": "ANAMNESI",
        "domanda": "Qual è la storia medica principale del paziente? Elenca le diagnosi principali, i farmaci in uso e le allergie.",
        "max_tokens": 1500,
        "istruzioni": """TASK: Estrai la storia medica del paziente dai documenti forniti.

RISPONDI CON QUESTA STRUTTURA:

DATI DEMOGRAFICI:
- Età:
- Sesso:
- Data ultimo esame:

DIAGNOSI PRINCIPALI:
- [se presenti nel documento]

FARMACI IN USO:
- [se presenti nel documento]

ALLERGIE:
- [se presenti nel documento]

NOTE CLINICHE IMPORTANTI:
- [sintesi dei dati rilevanti]

Se un'informazione non è disponibile nel documento, indica chiaramente "NON DISPONIBILE"."""
    },
    {
        "id": "sintomi",
        "categoria": "SINTOMI ATTUALI",
        "domanda": "Quali sono i sintomi principali presentati dal paziente? Descrivine l'insorgenza, la durata e la gravità.",
        "max_tokens": 800,
        "istruzioni": """TASK: Identifica e descrivi i sintomi del paziente.

RISPONDI CON QUESTA STRUTTURA:

SINTOMI SEGNALATI:
1. [sintomo]:
   - Insorgenza: [data/modalità]
   - Durata: [giorni/settimane/mesi]
   - Gravità: [scala 1-10 se disponibile]

CORRELAZIONI CLINICHE:
- [Collegamento tra sintomi e reperti oggettivi se documentati]

LIMITAZIONI DEL DOCUMENTO:
- [Specificare se il documento contiene solo esami oggettivi senza segnalazione di sintomi soggettivi]

Se nessun sintomo è documentato, indicalo chiaramente."""
    },
    {
        "id": "esami",
        "categoria": "ESAMI E PARAMETRI",
        "domanda": "Quali sono i principali parametri di laboratorio e gli esami diagnostici? Sono normali o anomali?",
        "max_tokens": 1500,
        "istruzioni": """TASK: Compila un elenco strutturato degli esami e parametri di laboratorio.

RISPONDI SOLO CON TABELLA:

| Categoria | Esame | Valore | Riferimento | Stato |
|-----------|-------|--------|-------------|-------|
| [categoria] | [nome esame] | [valore] | [range normale] | NORMALE/ANOMALO |

ESEMPI DI CATEGORIE: Ematologia, Biochimica, Coagulazione, Ormonale, Funzione Renale, Funzione Epatica, Lipidi, Glicemia

PER OGNI PARAMETRO ANOMALO, AGGIUNGI UNA RIGA DI COMMENTO:
- [Nome parametro]: [valore] [direzione anomalia] → [interpretazione clinica concisa]

Sii conciso e usa solo i dati documentati."""
    },
    {
        "id": "anomalie",
        "categoria": "ANOMALIE IDENTIFICATE",
        "domanda": "Identifica qualsiasi dato anomalo, valore fuori range o incoerenza nella documentazione medica.",
        "max_tokens": 1000,
        "istruzioni": """TASK: Identifica SOLO le anomalie presenti nel documento.

RISPONDI CON QUESTA STRUTTURA:

PARAMETRI FUORI RANGE:
1. [Parametro]
   - Valore: [valore documentato]
   - Intervallo normale: [range]
   - Tipo anomalia: ELEVATO / RIDOTTO / ALTERATO
   - Significato clinico: [1-2 righe concise]

INCOERENZE RILEVATE:
- [Se ci sono contraddizioni nei dati]

PARAMETRI DA SOTTOLINEARE:
- [Valori borderline o casi limite che meritano attenzione]

Se non ci sono anomalie, indicalo chiaramente."""
    },
    {
        "id": "comorbidita",
        "categoria": "COMORBIDITÀ E FATTORI DI RISCHIO",
        "domanda": "Quali sono le comorbidità (malattie associate) e i fattori di rischio rilevanti per questo paziente?",
        "max_tokens": 1200,
        "istruzioni": """TASK: Identifica comorbidità e fattori di rischio dal profilo del paziente.

RISPONDI CON QUESTA STRUTTURA:

COMORBIDITÀ EVIDENTI (da documenti):
1. [Condizione]:
   - Evidenza: [parametri/risultati che la supportano]
   - Implicazioni: [effetti clinici]

FATTORI DI RISCHIO IDENTIFICABILI:
1. [Fattore]:
   - Tipo: BIOLOGICO / GENETICO / COMPORTAMENTALE / AMBIENTALE
   - Livello: BASSO / MODERATO / ALTO
   - Base: [dati che lo supportano]

PROFILO DI RISCHIO COMPLESSIVO:
- [Sommario della situazione clinica complessiva]

Basa le risposte SOLO su ciò che è documentato."""
    },
    {
        "id": "rischi",
        "categoria": "VALUTAZIONE DEI RISCHI",
        "domanda": "Quali sono i principali rischi clinici identificabili? Quali complicanze potrebbero verificarsi?",
        "max_tokens": 1300,
        "istruzioni": """TASK: Valuta i rischi clinici e complicanze potenziali.

RISPONDI CON QUESTA STRUTTURA:

RISCHI CLINICI PRINCIPALI:
1. [Rischio]:
   - Probabilità: [ALTO / MODERATO / BASSO]
   - Fattori scatenanti: [da documenti]
   - Timeline: [immediato / breve termine / lungo termine]

COMPLICANZE POTENZIALI:
1. [Complicanza]:
   - Correlazione: [legame con anomalie identificate]
   - Preventabilità: SÌ / PARZIALE / NO
   - Monitoraggio: [come controllarla]

SCENARIO PEGGIORE:
- [Ipotesi peggiore senza intervento]

SCENARIO MIGLIORE:
- [Con intervento appropriato]

Usa sempre il disclaimer che è una analisi AI, non una diagnosi medica."""
    },
    {
        "id": "monitoraggio",
        "categoria": "MONITORAGGIO RACCOMANDATO",
        "domanda": "Cosa dovrebbe essere monitorato strettamente? Quali parametri richiedono follow-up frequente?",
        "max_tokens": 1000,
        "istruzioni": """TASK: Definisci il piano di monitoraggio.

RISPONDI CON QUESTA STRUTTURA:

PARAMETRI CON MONITORAGGIO PRIORITARIO:
1. [Parametro]:
   - Frequenza: [ogni 1-2 settimane / mensilmente / trimestralmente]
   - Range target: [valori da raggiungere]
   - Azioni se anomalo: [cosa fare se fuori range]

ESAMI CONSIGLIATI A FOLLOW-UP:
- [Esame]: [frequenza] | Motivo: [perché è importante]

PARAMETRI IN ZONA GRIGIA (non critica ma da osservare):
- [Parametro]: monitorare trend ogni [frequenza]

SOGLIE DI ALLARME:
- Se [parametro] > [valore], fare [azione]
- Se [parametro] < [valore], fare [azione]

Sii specifico e misurabile."""
    },
    {
        "id": "trend",
        "categoria": "TREND E PROGRESSIONE",
        "domanda": "Ci sono trend nei dati disponibili? I parametri stanno migliorando, peggiorando o rimanendo stabili?",
        "max_tokens": 900,
        "istruzioni": """TASK: Analizza trend nei dati (se disponibili).

RISPONDI CON QUESTA STRUTTURA:

DISPONIBILITÀ DATI SERIALI:
- Numero di prelievi: [numero]
- Intervallo temporale: [da data a data]
- Completezza: [%]

TREND IDENTIFICATI:
1. [Parametro]:
   - Andamento: MIGLIORAMENTO / PEGGIORAMENTO / STABILE / OSCILLANTE
   - Variazione: [incremento/decremento con numeri]
   - Velocità: LENTA / MODERATA / RAPIDA
   - Preoccupazione: [se rilevante]

SE DATI INSUFFICIENTI:
- Indicare chiaramente che con un singolo dato non si possono valutare trend
- Consigliare follow-up seriale

PREVISIONI:
- Se il trend continua così: [scenario]

Non speculare oltre i dati disponibili."""
    }
]


# ============================================================================
# 7. MEDICAL SERVICE AVANZATO
# ============================================================================

class MedicalService:
    """Servizio medico di analisi avanzato"""

    def __init__(self, store):
        self.store = store
        self.risposte = {}
        self.paziente_id = None

    def set_patient(self, patient_id):
        """Imposta l'ID del paziente"""
        self.paziente_id = patient_id
        self.risposte = {}

    def rispondi_a_domanda(self, domanda_info: Dict) -> str:
        """Risponde a una domanda strutturata"""

        domanda_id = domanda_info["id"]
        domanda_testo = domanda_info["domanda"]
        categoria = domanda_info["categoria"]
        max_tokens = domanda_info["max_tokens"]
        istruzioni = domanda_info.get("istruzioni", "")

        print(f"\n{'='*70}")
        print(f" {categoria}")
        print(f"{'='*70}")
        print(f"Domanda: {domanda_testo}\n")

        # Ottieni il contesto dai documenti
        full_text = self.store.get_all_text(self.paziente_id)

        if not full_text:
            return " Nessun documento trovato"

        # Cerca contesto specifico per la domanda
        context = self.store.search(self.paziente_id, domanda_testo[:30], context_chars=5000)

        prompt = f"""Sei un medico esperto specializzato in analisi medica strutturata.

{istruzioni}

DOCUMENTAZIONE DISPONIBILE:
{context[:6000]}

ISTRUZIONI GENERALI:
- Rispondi ESATTAMENTE come indicato nella struttura
- Basa la risposta SOLO sulla documentazione fornita
- Se un'informazione non è disponibile, indicalo chiaramente
- Sii conciso ma completo
- Non speculare oltre i dati disponibili
- Ricorda che questa è un'analisi AI di supporto, non una diagnosi medica"""

        risposta = generate_text(prompt, max_tokens=max_tokens)
        self.risposte[domanda_id] = {
            "categoria": categoria,
            "domanda": domanda_testo,
            "risposta": risposta
        }

        print(f"\n RISPOSTA:\n{risposta}")

        return risposta

    def rispondi_a_tutte_le_domande(self):
        """Risponde a tutte le domande strutturate"""
        print(f"\n{'='*70}")
        print(f" INIZIO ANALISI STRUTTURATA - PAZIENTE: {self.paziente_id}")
        print(f"{'='*70}")

        for domanda in DOMANDE_MEDICO:
            self.rispondi_a_domanda(domanda)
            print("\n")

        return self.risposte

    def domanda_personalizzata(self, domanda):
        """Risponde a una domanda personalizzata"""
        print(f"\n Domanda: {domanda}\n")

        full_text = self.store.get_all_text(self.paziente_id)

        if not full_text:
            return " Nessun documento trovato"

        context = self.store.search(self.paziente_id, domanda[:50], context_chars=3000)

        prompt = f"""Rispondi a questa domanda BASANDOTI sulla documentazione fornita.

DOMANDA: {domanda}

DOCUMENTAZIONE:
{context}

Sii diretto, chiaro e basato sul documento."""

        return generate_text(prompt, max_tokens=800)


# ============================================================================
# 8. GENERATORE REPORT PDF
# ============================================================================

class ReportGenerator:
    """Genera report JSON professionali"""

    def __init__(self, output_path):
        Path(output_path).mkdir(parents=True, exist_ok=True)
        self.output_path = output_path

    def genera_report(self, paziente_id: str, risposte: Dict, documents_text: str) -> str:
        """Genera un report JSON completo e strutturato"""

        # Struttura principale del report
        report_data = {
            "metadata": {
                "versione": "1.0",
                "timestamp": datetime.now().isoformat(),
                "data_ora": datetime.now().strftime("%d/%m/%Y alle %H:%M:%S"),
                "paziente_id": paziente_id,
                "numero_domande": len(risposte),
                "numero_documenti_analizzati": len(documents_text.split("---NUOVO DOCUMENTO---")) if documents_text else 0
            },
            "avvertenze": {
                "avviso_1": "Questo report è stato generato con supporto di AI. È ESCLUSIVAMENTE uno strumento di supporto decisionale.",
                "avviso_2": "NON sostituisce il giudizio medico professionale.",
                "avviso_3": "Ogni conclusione riportata DEVE essere verificata e approvata da un professionista medico qualificato prima di qualsiasi utilizzo clinico.",
                "avviso_4": "Questo documento contiene informazioni mediche confidenziali e deve essere gestito secondo le norme sulla privacy (GDPR, normative locali)."
            },
            "analisi_strutturata": []
        }

        # Aggiungere tutte le risposte
        for i, (domanda, info_risposta) in enumerate(risposte.items(), 1):
            # Gestisci sia risposte semplici che strutturate
            if isinstance(info_risposta, dict):
                risposta = info_risposta.get('risposta', str(info_risposta))
                categoria = info_risposta.get('categoria', 'Generale')
            else:
                risposta = str(info_risposta)
                categoria = 'Generale'

            item = {
                "numero": i,
                "categoria": categoria,
                "domanda": domanda,
                "risposta": risposta,
                "estratti_documenti": self._estrai_contesto(domanda, documents_text) if documents_text else []
            }
            report_data["analisi_strutturata"].append(item)

        # Aggiungere informazioni finali
        report_data["informazioni_finali"] = {
            "paziente_analizzato": paziente_id,
            "data_completamento": datetime.now().strftime("%d/%m/%Y alle %H:%M:%S"),
            "numero_domande_elaborate": len(risposte),
            "lunghezza_documenti_caratteri": len(documents_text) if documents_text else 0
        }

        # Salvare il JSON
        filepath = Path(self.output_path) / f"report_{paziente_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            print(f" Report JSON generato con successo: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f" Errore nella generazione del JSON: {e}")
            return None

    def _estrai_contesto(self, query: str, documents_text: str, max_chars=300) -> list:
        """Estrae brevi contesti dai documenti correlati alla query"""
        estratti = []
        if not documents_text:
            return estratti

        # Cerca frasi correlate alla query nei documenti
        query_words = set(word for word in query.lower().split() if len(word) > 3)
        paragrafi = documents_text.split('\n\n')

        for paragrafo in paragrafi[:5]:  # Massimo 5 paragrafi
            matches = sum(1 for word in query_words if word in paragrafo.lower())
            if matches > 0:  # Se almeno una parola della query è nel paragrafo
                estratti.append({
                    "testo": paragrafo[:max_chars] + "..." if len(paragrafo) > max_chars else paragrafo,
                    "rilevanza": "alta" if matches > 2 else "media" if matches > 1 else "bassa"
                })
                if len(estratti) >= 3:
                    break

        return estratti
        """Rimuove tag HTML e markdown incompatibili con ReportLab"""
        import re

        # Rimuovi tag <br> e <br/>
        testo = re.sub(r'<br\s*/?>', ' ', testo, flags=re.IGNORECASE)

        # Rimuovi tabelle markdown (tutto tra | e |)
        testo = re.sub(r'\|.*?\|', '\n', testo)

        # Rimuovi linee di separazione markdown (---)
        testo = re.sub(r'-{3,}', '', testo)

        # Rimuovi heading markdown (#, ##, etc)
        testo = re.sub(r'^#+\s+', '', testo, flags=re.MULTILINE)

        # Rimuovi doppi spazi multipli
        testo = re.sub(r'\s{3,}', '  ', testo)

        # Rimuovi caratteri unicode problematici
        testo = testo.replace('↓', 'RIDOTTO').replace('↑', 'ELEVATO')
        testo = testo.replace('–', '-').replace('—', '-')

        return testo.strip()


# ============================================================================
# 9. PROGRAMMA PRINCIPALE
# ============================================================================

def main():
    """Programma principale"""

    print("""

           MEDICAL AI - VERSIONE AVANZATA CON REPORT JSON
              Analisi Strutturata + Relazione JSON Professionale

    """)

    # Controlla OLLAMA
    if not check_ollama():
        return

    print("\n Setup inizializzato\n")

    # Carica PDF dalla directory
    print("=" * 70)
    print("CARICAMENTO DOCUMENTI DA DIRECTORY")
    print("=" * 70)

    documents, paziente_estratto = load_documents_from_directory(config.PDF_INPUT_PATH)

    if not documents:
        print("\n Nessun documento da processare!")
        return

    print(f"\n Caricati {len(documents)} documenti PDF")

    # Crea store e medical service
    store = SimpleDocumentStore()
    medical = MedicalService(store)
    report_gen = ReportGenerator(config.PDF_OUTPUT_PATH)

    # IDENTIFICAZIONE PAZIENTE
    print("\n" + "=" * 70)
    print("IDENTIFICAZIONE PAZIENTE")
    print("=" * 70)

    print("\nInserire il nome del paziente per iniziare l'analisi.")
    paziente_id = input("Nome del paziente: ").strip()

    if not paziente_id:
        paziente_id = "PAZIENTE"
        print(f"Nessun nome inserito. Utilizzo il valore di default: {paziente_id}")

    print(f"\nPaziente selezionato: {paziente_id}")

    medical.set_patient(paziente_id)

    # Carica documenti
    store.add_documents(paziente_id, documents)

    print(f"\n Paziente: {paziente_id}")
    print(f" Documenti caricati e pronti per l'analisi")

    # ========================================================================
    # ANALISI STRUTTURATA
    # ========================================================================

    risposte = medical.rispondi_a_tutte_le_domande()

    # ========================================================================
    # DOMANDE PERSONALIZZATE
    # ========================================================================

    print("\n" + "=" * 70)
    print("DOMANDE PERSONALIZZATE AGGIUNTIVE")
    print("=" * 70)

    while True:
        print(f"\nInserisci una domanda per il paziente '{paziente_id}'")
        print("   (o 'fine' per procedere con la generazione del report):")

        domanda = input(">>> ").strip()

        if domanda.lower() in ['fine', 'exit', 'quit']:
            break

        if domanda:
            risposta = medical.domanda_personalizzata(domanda)
            print(f"\nRISPOSTA:\n{risposta}")
            print("\n" + "-" * 70)

    # ========================================================================
    # GENERAZIONE REPORT JSON
    # ========================================================================

    print("\n" + "=" * 70)
    print("GENERAZIONE REPORT JSON FINALE")
    print("=" * 70)

    # Ottieni tutto il testo dei documenti
    full_documents_text = store.get_all_text(paziente_id)

    # Genera il report
    json_path = report_gen.genera_report(paziente_id, risposte, full_documents_text)

    if json_path:
        print("\n" + "=" * 70)
        print("ANALISI COMPLETATA CON SUCCESSO!")
        print("=" * 70)

        # Tabella riepilogativa
        print("\nRIEPILOGO DELL'ELABORAZIONE:")
        print("-" * 70)
        print(f"{'Paziente:':<30} {paziente_id}")
        print(f"{'Domande elaborate:':<30} {len(risposte)}")
        print(f"{'Report JSON generato:':<30} {json_path}")
        print(f"{'Data/Ora:':<30} {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("-" * 70)
        print("\nRICORDARE: Il report richiede sempre verifica medica professionale!")
    else:
        print("\nErrore nella generazione del report JSON")

    print("\n" + "=" * 70 + "\n")


# ============================================================================
# AVVIA
# ============================================================================

if __name__ == "__main__":
    main()