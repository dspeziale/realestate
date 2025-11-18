"""
MEDICAL AI - VERSIONE CON LETTURA PDF
Legge PDF da una directory e fa analisi mediche
"""

import requests
import json
import numpy as np
from pathlib import Path
import sys


# ============================================================================
# 1. CONFIGURAZIONE
# ============================================================================

class Config:
    OLLAMA_HOST = "http://localhost:11434"
    OLLAMA_MODEL = "gpt-oss:120b-cloud"  # Oppure: mistral:7b (più veloce)
    OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
    PDF_INPUT_PATH = r"C:\logs"  # Directory dove leggiamo i PDF


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

    $ ollama pull llama2:13b
    $ ollama pull nomic-embed-text

    Infine, avvia:
    $ ollama serve &
    """)
    return False


# ============================================================================
# 4. GENERAZIONE TESTO (LLM)
# ============================================================================

def generate_text(prompt, model=None, max_tokens=2048):
    """
    Genera testo usando OLLAMA
    """
    if model is None:
        model = config.OLLAMA_MODEL

    print(f"⏳ Generando con {model}...")

    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1,  # Basso per medical
            }
        }

        response = requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=300
        )
        response.raise_for_status()

        # Raccogli risposta da stream
        result = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                result += data.get("response", "")

        print(f"✅ Generazione completata")
        return result.strip()

    except Exception as e:
        print(f"❌ Errore: {e}")
        raise


# ============================================================================
# 5. EMBEDDINGS (Per RAG)
# ============================================================================

def create_embeddings(texts):
    """
    Crea embeddings per i testi
    Usato per la ricerca nel RAG
    """

    if isinstance(texts, str):
        texts = [texts]

    print(f"🔄 Creando embeddings per {len(texts)} testi...")

    embeddings = []
    for i, text in enumerate(texts):
        try:
            payload = {
                "model": config.OLLAMA_EMBEDDING_MODEL,
                "prompt": text
            }

            response = requests.post(
                f"{config.OLLAMA_HOST}/api/embeddings",
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding", [])
            embeddings.append(embedding)

            print(f"  ✓ {i + 1}/{len(texts)}")

        except Exception as e:
            print(f"  ❌ Errore per testo {i + 1}: {e}")
            embeddings.append([])

    print(f"✅ Embeddings creati")
    return embeddings


# ============================================================================
# 6. RAG SYSTEM (Vector Store Locale)
# ============================================================================

class RAGSystem:
    """Vector store locale con FAISS"""

    def __init__(self):
        self.vector_stores = {}
        print(f"✅ RAG System inizializzato")

    def add_documents(self, patient_id, documents):
        """Aggiunge documenti per un paziente"""

        print(f"\n📄 Caricando documenti per paziente {patient_id}...")

        # Split in chunks
        chunks = self._split_into_chunks(documents)
        print(f"   • {len(chunks)} chunks creati")

        # Crea embeddings
        embeddings = create_embeddings(chunks)

        if not embeddings or not embeddings[0]:
            print("❌ Errore: embeddings non creati")
            return False

        # Importa FAISS
        try:
            import faiss
        except ImportError:
            print("❌ FAISS non installato: pip install faiss-cpu")
            return False

        # Crea index
        dimension = len(embeddings[0])
        index = faiss.IndexFlatL2(dimension)
        embeddings_array = np.array(embeddings, dtype=np.float32)
        index.add(embeddings_array)

        # Salva
        metadata = [{"text": chunk} for chunk in chunks]

        self.vector_stores[patient_id] = {
            "index": index,
            "metadata": metadata,
            "chunks": chunks
        }

        print(f"✅ {len(chunks)} documenti caricati per {patient_id}")
        return True

    def search(self, patient_id, query, top_k=5):
        """Cerca i documenti più rilevanti"""

        if patient_id not in self.vector_stores:
            print(f"❌ Paziente {patient_id} non trovato")
            return []

        store = self.vector_stores[patient_id]

        # Embedding della query
        query_embedding = create_embeddings([query])[0]
        query_array = np.array([query_embedding], dtype=np.float32)

        # Ricerca
        distances, indices = store["index"].search(query_array, min(top_k, len(store["chunks"])))

        # Risultati
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(store["chunks"]):
                results.append({
                    "text": store["chunks"][idx],
                    "relevance": 1 / (1 + dist)
                })

        return results

    def _split_into_chunks(self, documents):
        """Split documenti in chunks"""
        chunks = []

        for doc in documents:
            paragraphs = doc.split("\n\n")
            for para in paragraphs:
                if len(para) > 100:
                    # Split in chunks di ~1500 token (6000 caratteri)
                    chunk_size = 6000
                    for i in range(0, len(para), chunk_size):
                        chunk = para[i:i + chunk_size].strip()
                        if chunk:
                            chunks.append(chunk)

        return chunks if chunks else [""]


# ============================================================================
# 7. MEDICAL SERVICE - LE 4 CAPABILITIES
# ============================================================================

class MedicalService:
    """Le 4 capabilities mediche"""

    def __init__(self, rag_system):
        self.rag = rag_system

    # ========================================================================
    # CAPABILITY 1: RIASSUNTO
    # ========================================================================
    def summarize(self, patient_id):
        """Riassume la storia medica"""

        print(f"\n📋 Riassumendo storia medica...")

        # Recupera documenti
        query = "storia medica diagnosi allergie farmaci interventi"
        chunks = self.rag.search(patient_id, query, top_k=10)

        if not chunks:
            return "❌ Nessun documento trovato"

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Sei un medico esperto. Basandoti su questa documentazione medica,
fornisci un riassunto STRUTTURATO della storia medica del paziente.

DOCUMENTAZIONE:
{context}

Nel riassunto includi:
1. Diagnosi principali
2. Farmaci attuali
3. ALLERGIE (IMPORTANTE!)
4. Interventi chirurgici
5. Fattori di rischio

Formato: Usa ### per sezioni, sii chiaro e conciso."""

        return generate_text(prompt, max_tokens=1024)

    # ========================================================================
    # CAPABILITY 2: DOMANDE
    # ========================================================================
    def ask_question(self, patient_id, question):
        """Risponde a domande specifiche"""

        print(f"\n❓ Domanda: {question}")

        # Recupera documenti rilevanti
        chunks = self.rag.search(patient_id, question, top_k=5)

        if not chunks:
            return "⚠️ Non ho trovato informazioni rilevanti"

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Rispondi a questa domanda BASANDOTI SOLO sulla documentazione fornita.

DOMANDA: {question}

DOCUMENTAZIONE:
{context}

Regole:
1. Rispondi in modo diretto e chiaro
2. Se l'informazione non c'è, indicalo
3. Cita la fonte
4. Sii breve"""

        return generate_text(prompt, max_tokens=512)

    # ========================================================================
    # CAPABILITY 3: ANOMALIE
    # ========================================================================
    def find_anomalies(self, patient_id):
        """Trova anomalie nei dati"""

        print(f"\n🔍 Cercando anomalie...")

        chunks = self.rag.search(patient_id, "valori anomali fuori range laboratorio", top_k=15)

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Analizza questa documentazione medica alla ricerca di ANOMALIE.

DOCUMENTAZIONE:
{context}

Identifica:
1. Valori fuori range
2. Trend preoccupanti
3. Inconsistenze
4. Dati strani

Per ogni anomalia:
- Descrizione
- Perché è importante
- Cosa potrebbe significare

Formato: Lista numerata, sii conciso."""

        return generate_text(prompt, max_tokens=1024)

    # ========================================================================
    # CAPABILITY 4: PREDIZIONI ⚠️
    # ========================================================================
    def predict_condition(self, patient_id, condition=None):
        """Analizza rischi di condizioni mediche"""

        if condition is None:
            condition = "complicanze mediche generali"

        print(f"\n📊 Analizzando rischi di: {condition}")
        print("⚠️ DISCLAIMER: Questa NON è una diagnosi medica!")

        chunks = self.rag.search(patient_id, f"fattori rischio comorbidità storia medica", top_k=15)

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""⚠️ QUESTA NON È UNA DIAGNOSI MEDICA - È SOLO ANALISI DI SUPPORTO

Analizza il profilo medico generale del paziente e identifica i principali rischi clinici.

DOCUMENTAZIONE:
{context}

Analizza:
1. Diagnosi principali
2. Comorbidità (altre malattie correlate)
3. Fattori di rischio identificabili
4. Trend dei parametri
5. Potenziali complicanze

Fornisci:
1. Diagnosi/Condizioni rilevate
2. Principali fattori di rischio
3. Condizioni di cui monitorare l'evoluzione
4. Raccomandazioni per il monitoraggio
5. Possibili complicanze se non controllate

RICORDA: Questa è ANALISI, non DIAGNOSI! Richiede revisione medica."""

        result = generate_text(prompt, max_tokens=1500)

        return f"""⚠️ DISCLAIMER CRITICO:
Questa è analisi di supporto decisionale, NON è una diagnosi medica.
Richiede SEMPRE revisione medica professionale.

{'=' * 60}

{result}

{'=' * 60}
⚠️ Consultare sempre un medico professionista."""


# ============================================================================
# 8. PROGRAMMA PRINCIPALE
# ============================================================================

def main():
    """Programma principale"""

    print("""
╔═══════════════════════════════════════════════════════════════╗
║          🏥 MEDICAL AI - LETTORE PDF DA DIRECTORY             ║
║                    (Niente API keys!)                        ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Controlla OLLAMA
    if not check_ollama():
        return

    print("\n✅ Setup inizializzato\n")

    # Carica PDF dalla directory
    print("=" * 60)
    print("CARICAMENTO DOCUMENTI DA DIRECTORY")
    print("=" * 60)

    documents = load_documents_from_directory(config.PDF_INPUT_PATH)

    if not documents:
        print("\n❌ Nessun documento da processare!")
        return

    print(f"\n✅ Caricati {len(documents)} documenti PDF")

    # Crea RAG e Medical Service
    rag = RAGSystem()
    medical = MedicalService(rag)

    # Carica documenti nel RAG
    rag.add_documents("PAZIENTE", documents)

    # ========================================================================
    # ANALISI COMPLETA
    # ========================================================================

    # 1. RIASSUNTO
    print("\n" + "=" * 60)
    print("1️⃣ RIASSUNTO STORIA MEDICA")
    print("=" * 60)
    summary = medical.summarize("PAZIENTE")
    print(f"\n{summary}")

    # 2. ANOMALIE
    print("\n" + "=" * 60)
    print("2️⃣ ANOMALIE IDENTIFICATE")
    print("=" * 60)
    anomalies = medical.find_anomalies("PAZIENTE")
    print(f"\n{anomalies}")

    # 3. PREDIZIONI
    print("\n" + "=" * 60)
    print("3️⃣ ANALISI RISCHI CLINICI")
    print("=" * 60)
    prediction = medical.predict_condition("PAZIENTE")
    print(f"\n{prediction}")

    # 4. DOMANDE PERSONALIZZATE
    print("\n" + "=" * 60)
    print("4️⃣ DOMANDE PERSONALIZZATE (OPZIONALE)")
    print("=" * 60)

    while True:
        print("\n💬 Inserisci una domanda sul paziente (o 'esci' per terminare):")
        domanda = input(">>> ").strip()

        if domanda.lower() in ['esci', 'exit', 'quit']:
            break

        if domanda:
            risposta = medical.ask_question("PAZIENTE", domanda)
            print(f"\n{risposta}")

    print("\n" + "=" * 60)
    print("✅ ANALISI COMPLETATA!")
    print("=" * 60)


# ============================================================================
# AVVIA
# ============================================================================

if __name__ == "__main__":
    main()