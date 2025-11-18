"""
MEDICAL AI - VERSIONE FAST SENZA EMBEDDINGS
Ricerca testuale semplice, niente timeout!
"""

import requests
import json
from pathlib import Path
from typing import List, Dict


# ============================================================================
# 1. CONFIGURAZIONE
# ============================================================================

class Config:
    OLLAMA_HOST = "http://localhost:11434"
    #OLLAMA_MODEL = "gemma3:4b"  # Più veloce e affidabile
    OLLAMA_MODEL = "gpt-oss:120b-cloud"  # Più veloce e affidabile
    PDF_INPUT_PATH = r"C:\logs"


config = Config()


# ============================================================================
# 2. LETTURA PDF
# ============================================================================

def extract_text_from_pdf(pdf_path):
    """Estrae testo da un PDF"""
    try:
        import PyPDF2
    except ImportError:
        print("❌ PyPDF2 non installato!")
        print("   Installa con: pip install PyPDF2")
        return None

    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            print(f"   📄 {pdf_path.name}: {len(pdf_reader.pages)} pagine")

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"

        return text
    except Exception as e:
        print(f"   ❌ Errore lettura {pdf_path.name}: {e}")
        return None


def load_documents_from_directory(directory):
    """Carica tutti i PDF da una directory"""
    pdf_path = Path(directory)

    if not pdf_path.exists():
        print(f"❌ Directory non trovata: {directory}")
        return []

    documents = []
    pdf_files = list(pdf_path.glob("*.pdf"))

    if not pdf_files:
        print(f"❌ Nessun PDF trovato in: {directory}")
        return []

    print(f"\n📂 Trovati {len(pdf_files)} PDF in {directory}")

    for pdf_file in pdf_files:
        print(f"\n📖 Leggo: {pdf_file.name}")
        text = extract_text_from_pdf(pdf_file)

        if text and len(text.strip()) > 50:
            documents.append(text)
            print(f"   ✓ Estratti {len(text)} caratteri")
        else:
            print(f"   ⚠️ PDF vuoto o illeggibile")

    return documents


# ============================================================================
# 3. VERIFICHE
# ============================================================================

def check_ollama():
    """Verifica se OLLAMA è online"""
    try:
        response = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=2)
        if response.status_code == 200:
            print("✅ OLLAMA è ONLINE")
            return True
    except:
        pass

    print("""
    ❌ OLLAMA NON è online!

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

    print(f"⏳ Generando...")

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

        print(f"✅ Completato")
        return result.strip()

    except Exception as e:
        print(f"❌ Errore: {e}")
        raise


# ============================================================================
# 5. RICERCA TESTUALE SEMPLICE (NO EMBEDDINGS!)
# ============================================================================

class SimpleDocumentStore:
    """Store di documenti con ricerca testuale semplice"""

    def __init__(self):
        self.documents = {}
        print("✅ Document Store inizializzato")

    def add_documents(self, patient_id, documents: List[str]):
        """Aggiunge documenti per un paziente"""
        print(f"\n📄 Caricando {len(documents)} documenti...")

        # Combina tutti i documenti
        full_text = "\n\n---NUOVO DOCUMENTO---\n\n".join(documents)

        self.documents[patient_id] = {
            "full_text": full_text,
            "parts": documents,
            "char_count": len(full_text)
        }

        print(f"✅ {len(documents)} documenti caricati ({len(full_text)} caratteri totali)")
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
# 6. MEDICAL SERVICE
# ============================================================================

class MedicalService:
    """Servizio medico di analisi"""

    def __init__(self, store):
        self.store = store

    def summarize(self, patient_id):
        """Riassume la storia medica"""
        print(f"\n📋 Riassumendo storia medica...")

        full_text = self.store.get_all_text(patient_id)

        if not full_text:
            return "❌ Nessun documento trovato"

        prompt = f"""Sei un medico esperto. Basandoti su questa documentazione medica,
fornisci un riassunto STRUTTURATO della storia medica del paziente.

DOCUMENTAZIONE:
{full_text[:4000]}  # Primi 4000 caratteri

Nel riassunto includi:
1. Diagnosi principali
2. Farmaci attuali
3. ALLERGIE (IMPORTANTE!)
4. Fattori di rischio
5. Parametri anomali

Formato: Sii chiaro, conciso e ben strutturato."""

        return generate_text(prompt, max_tokens=1500)

    def find_anomalies(self, patient_id):
        """Trova anomalie nei dati"""
        print(f"\n🔍 Cercando anomalie...")

        full_text = self.store.get_all_text(patient_id)

        if not full_text:
            return "❌ Nessun documento trovato"

        prompt = f"""Analizza questa documentazione medica alla ricerca di ANOMALIE.

DOCUMENTAZIONE:
{full_text[:5000]}

Identifica:
1. Valori fuori range
2. Trend preoccupanti
3. Dati strani o incoerenti
4. Parametri critici

Per ogni anomalia, spiega:
- Cosa è anomalo
- Perché è importante
- Cosa potrebbe significare

Sii conciso."""

        return generate_text(prompt, max_tokens=1500)

    def predict_condition(self, patient_id):
        """Analizza rischi clinici generali"""
        print(f"\n📊 Analizzando rischi clinici...")
        print("⚠️ DISCLAIMER: Questa NON è una diagnosi medica!")

        full_text = self.store.get_all_text(patient_id)

        if not full_text:
            return "❌ Nessun documento trovato"

        prompt = f"""⚠️ QUESTA NON È UNA DIAGNOSI MEDICA - È ANALISI DI SUPPORTO

Analizza il profilo medico della paziente e identifica i principali rischi clinici.

DOCUMENTAZIONE:
{full_text[:6000]}

Analizza:
1. Diagnosi e condizioni presenti
2. Comorbidità (malattie correlate)
3. Fattori di rischio identificabili
4. Trend dei parametri (se migliorano/peggiorano)
5. Possibili complicanze

Fornisci:
1. Quadro clinico generale
2. Fattori di rischio prioritari
3. Cosa monitorare strettamente
4. Possibili evoluzioni cliniche

RICORDA: Questa è ANALISI, non DIAGNOSI! Richiede revisione medica."""

        result = generate_text(prompt, max_tokens=2000)

        return f"""⚠️ DISCLAIMER CRITICO:
Questa è analisi di supporto decisionale, NON è una diagnosi medica.
Richiede SEMPRE revisione medica professionale.

{'=' * 70}

{result}

{'=' * 70}
⚠️ Consultare sempre un medico professionista."""

    def ask_question(self, patient_id, question):
        """Risponde a domande specifiche"""
        print(f"\n❓ Domanda: {question}")

        # Cerca il contesto per la domanda
        context = self.store.search(patient_id, question, context_chars=3000)

        if not context:
            context = self.store.get_all_text(patient_id)[:3000]

        prompt = f"""Rispondi a questa domanda BASANDOTI sulla documentazione fornita.

DOMANDA: {question}

DOCUMENTAZIONE:
{context}

Regole:
1. Rispondi in modo diretto e basato sul documento
2. Se l'informazione non c'è, indicalo chiaramente
3. Sii breve e preciso"""

        return generate_text(prompt, max_tokens=512)


# ============================================================================
# 7. PROGRAMMA PRINCIPALE
# ============================================================================

def main():
    """Programma principale"""

    print("""
╔═══════════════════════════════════════════════════════════════╗
║          🏥 MEDICAL AI - VERSIONE FAST                        ║
║              Niente embeddings, no timeout!                   ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Controlla OLLAMA
    if not check_ollama():
        return

    print("\n✅ Setup inizializzato\n")

    # Carica PDF dalla directory
    print("=" * 70)
    print("CARICAMENTO DOCUMENTI DA DIRECTORY")
    print("=" * 70)

    documents = load_documents_from_directory(config.PDF_INPUT_PATH)

    if not documents:
        print("\n❌ Nessun documento da processare!")
        return

    print(f"\n✅ Caricati {len(documents)} documenti PDF")

    # Crea store e medical service
    store = SimpleDocumentStore()
    medical = MedicalService(store)

    # Carica documenti
    store.add_documents("PAZIENTE", documents)

    # ========================================================================
    # ANALISI COMPLETA
    # ========================================================================

    # 1. RIASSUNTO
    print("\n" + "=" * 70)
    print("1️⃣ RIASSUNTO STORIA MEDICA")
    print("=" * 70)
    summary = medical.summarize("PAZIENTE")
    print(f"\n{summary}")

    # 2. ANOMALIE
    print("\n" + "=" * 70)
    print("2️⃣ ANOMALIE IDENTIFICATE")
    print("=" * 70)
    anomalies = medical.find_anomalies("PAZIENTE")
    print(f"\n{anomalies}")

    # 3. PREDIZIONI
    print("\n" + "=" * 70)
    print("3️⃣ ANALISI RISCHI CLINICI")
    print("=" * 70)
    prediction = medical.predict_condition("PAZIENTE")
    print(f"\n{prediction}")

    # 4. DOMANDE PERSONALIZZATE
    print("\n" + "=" * 70)
    print("4️⃣ DOMANDE PERSONALIZZATE")
    print("=" * 70)

    while True:
        print("\n💬 Inserisci una domanda (o 'esci' per terminare):")
        domanda = input(">>> ").strip()

        if domanda.lower() in ['esci', 'exit', 'quit']:
            break

        if domanda:
            risposta = medical.ask_question("PAZIENTE", domanda)
            print(f"\n{risposta}")

    print("\n" + "=" * 70)
    print("✅ ANALISI COMPLETATA!")
    print("=" * 70)


# ============================================================================
# AVVIA
# ============================================================================

if __name__ == "__main__":
    main()