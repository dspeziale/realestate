"""
MEDICAL AI - VERSIONE SEMPLICE CON SOLO OLLAMA
Niente API keys, tutto locale!
"""

import requests
import json
import numpy as np
from pathlib import Path


# ============================================================================
# 1. CONFIGURAZIONE
# ============================================================================

class Config:
    OLLAMA_HOST = "http://localhost:11434"
    OLLAMA_MODEL = "gpt-oss:120b-cloud"  # Oppure: mistral:7b (più veloce)
    OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
    VECTOR_STORE_PATH = "C:\logs"


config = Config()


# ============================================================================
# 2. VERIFICHE
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
# 3. GENERAZIONE TESTO (LLM)
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
# 4. EMBEDDINGS (Per RAG)
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
# 5. RAG SYSTEM (Vector Store Locale)
# ============================================================================

class RAGSystem:
    """Vector store locale con FAISS"""

    def __init__(self):
        self.storage_path = Path(config.VECTOR_STORE_PATH)
        self.storage_path.mkdir(exist_ok=True)
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
# 6. MEDICAL SERVICE - LE 4 CAPABILITIES
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
    def predict_condition(self, patient_id, condition):
        """Analizza rischio di una condizione"""

        print(f"\n📊 Analizzando rischio di: {condition}")
        print("⚠️ DISCLAIMER: Questa NON è una diagnosi medica!")

        chunks = self.rag.search(patient_id, f"fattori rischio {condition}", top_k=10)

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""⚠️ QUESTA NON È UNA DIAGNOSI MEDICA - È SOLO ANALISI DI SUPPORTO

Analizza il rischio di '{condition}' basandoti su:
{context}

Valuta:
1. Fattori di rischio presenti
2. Comorbidità (altre malattie)
3. Trend (migliora/peggiora/stabile)
4. Precedenti episodi simili

Fornisci:
1. Rischio: BASSO / MEDIO / ALTO / CRITICO
2. Percentuale (0-100%)
3. Fattori principali
4. Timeline (quando potrebbe accadere)
5. Cosa monitorare

RICORDA: Questa è ANALISI, non DIAGNOSI! Richiede revisione medica."""

        result = generate_text(prompt, max_tokens=768)

        return f"""⚠️ DISCLAIMER CRITICO:
Questa è analisi di supporto decisionale, NON è una diagnosi medica.
Richiede SEMPRE revisione medica professionale.

{result}

⚠️ Consultare sempre un medico professionista."""


# ============================================================================
# 7. PROGRAMMA PRINCIPALE - PROVA SUBITO!
# ============================================================================

def main():
    """Prova il sistema"""

    print("""
╔═══════════════════════════════════════════════════════════════╗
║          🏥 MEDICAL AI - VERSIONE OLLAMA SOLO                ║
║                    (Niente API keys!)                        ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Controlla OLLAMA
    if not check_ollama():
        return

    print("\n✅ Setup inizializzato\n")

    # Crea RAG e Medical Service
    rag = RAGSystem()
    medical = MedicalService(rag)

    # ========================================================================
    # DOCUMENTO DI PROVA
    # ========================================================================

    documento = """
REFERTI LABORATORIO - Data: 15/01/2024
Paziente: Mario Rossi, 55 anni

ESAMI EFFETTUATI:
- Glicemia: 145 mg/dL (ALTO - normale: 70-100)
- Emoglobina glicata: 7.2% (ELEVATA - normale: <5.7%)
- Colesterolo totale: 220 mg/dL (ALTO - normale: <200)
- HDL: 35 mg/dL (BASSO - normale: >40)
- LDL: 150 mg/dL (ALTO - normale: <100)
- Trigliceridi: 180 mg/dL (ELEVATI)

ALLERGIE DOCUMENTATE:
- Penicillina (reazione: rash cutaneo)
- Arachidi (reazione: edema)

DIAGNOSI PRECEDENTI:
- Diabete tipo 2 dal 2018
- Ipertensione dal 2015
- Dislipidemia

FARMACI ATTUALI:
- Metformina 1000mg mattina e sera
- Lisinopril 10mg mattina
- Atorvastatina 20mg sera

STORIA MEDICA:
- 2018: Diagnosi diabete dopo glicemia 185 mg/dL
- 2015: Inizio ipertensione, pressione 165/100
- 2023: Visita cardiologica, ECG normale
- 2024: Controllo annuale con esami laboratorio

OSSERVAZIONI MEDICHE:
Paziente con diabete ben controllato da metformina.
Pressione arteriosa attualmente 145/92 (lievemente elevata).
Colesterolo non completamente controllato, potrebbe beneficiare di aumento terapia.
BMI: 28.5 (sovrappeso).
Consigliato: Esercizio fisico, dieta ipocalorica, aumento dosi statina.
"""

    print("=" * 60)
    print("CARICAMENTO DOCUMENTO DI PROVA")
    print("=" * 60)

    # Upload documento
    rag.add_documents("PAT001", [documento])

    # ========================================================================
    # PROVA LE 4 CAPABILITIES
    # ========================================================================

    # 1. RIASSUNTO
    print("\n" + "=" * 60)
    print("1️⃣ CAPABILITY: RIASSUNTO STORIA MEDICA")
    print("=" * 60)
    summary = medical.summarize("PAT001")
    print(f"\n{summary}")

    # 2. DOMANDE
    print("\n" + "=" * 60)
    print("2️⃣ CAPABILITY: RISPONDI A DOMANDE")
    print("=" * 60)

    domande = [
        "Quali allergie ha il paziente?",
        "Prende metformina?",
        "Ha il diabete?",
        "Quale è il BMI?"
    ]

    for domanda in domande:
        print(f"\n❓ {domanda}")
        risposta = medical.ask_question("PAT001", domanda)
        print(f"📝 {risposta}")

    # 3. ANOMALIE
    print("\n" + "=" * 60)
    print("3️⃣ CAPABILITY: IDENTIFICA ANOMALIE")
    print("=" * 60)
    anomalies = medical.find_anomalies("PAT001")
    print(f"\n{anomalies}")

    # 4. PREDIZIONI
    print("\n" + "=" * 60)
    print("4️⃣ CAPABILITY: PREDIZIONI CLINICHE")
    print("=" * 60)
    prediction = medical.predict_condition("PAT001", "diabetic complication")
    print(f"\n{prediction}")

    print("\n" + "=" * 60)
    print("✅ PROVA COMPLETATA!")
    print("=" * 60)


# ============================================================================
# AVVIA
# ============================================================================

if __name__ == "__main__":
    main()