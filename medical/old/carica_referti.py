"""
CARICA REFERTI MEDICI - Legge PDF, immagini, testi
Analizza con OLLAMA (senza API keys)
"""

import requests
import json
import os
from pathlib import Path

# Per leggere PDF
try:
    import PyPDF2

    HAS_PDF = True
except ImportError:
    HAS_PDF = False
    print("⚠️ PyPDF2 non installato: pip install PyPDF2")

# Per leggere immagini (OCR)
try:
    from PIL import Image
    import pytesseract

    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("⚠️ PIL/pytesseract non installato: pip install pillow pytesseract")

import numpy as np


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

class Config:
    OLLAMA_HOST = "http://localhost:11434"
    OLLAMA_MODEL = "llama2:13b"
    OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
    VECTOR_STORE_PATH = r"C:\logs"


config = Config()


# ============================================================================
# 1. LEGGI REFERTI DA FILE
# ============================================================================

class DocumentReader:
    """Legge referti da PDF, immagini, testi"""

    @staticmethod
    def read_file(file_path):
        """Legge un file e ritorna il testo"""

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File non trovato: {file_path}")

        suffix = file_path.suffix.lower()

        # ====================================================================
        # PDF
        # ====================================================================
        if suffix == ".pdf":
            print(f"📄 Leggendo PDF: {file_path.name}...")
            return DocumentReader._read_pdf(file_path)

        # ====================================================================
        # IMMAGINI (OCR)
        # ====================================================================
        elif suffix in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            print(f"🖼️  Leggendo immagine con OCR: {file_path.name}...")
            return DocumentReader._read_image(file_path)

        # ====================================================================
        # TESTI
        # ====================================================================
        elif suffix in [".txt", ".md"]:
            print(f"📝 Leggendo testo: {file_path.name}...")
            return DocumentReader._read_text(file_path)

        else:
            raise ValueError(f"Formato non supportato: {suffix}")

    @staticmethod
    def _read_pdf(file_path):
        """Legge PDF"""
        if not HAS_PDF:
            raise ImportError("PyPDF2 non installato: pip install PyPDF2")

        text = ""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)

                print(f"   • PDF con {num_pages} pagine")

                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += f"\n[Pagina {page_num + 1}]\n{page_text}"
                    print(f"   ✓ Pagina {page_num + 1}/{num_pages}")

            return text

        except Exception as e:
            raise Exception(f"Errore lettura PDF: {e}")

    @staticmethod
    def _read_image(file_path):
        """Legge immagine con OCR"""
        if not HAS_OCR:
            raise ImportError("PIL/pytesseract non installato: pip install pillow pytesseract")

        try:
            image = Image.open(file_path)
            print(f"   • Immagine {image.size}")
            print(f"   • OCR in corso...")

            # OCR in italiano se disponibile
            text = pytesseract.image_to_string(image, lang='ita+eng')

            return text

        except Exception as e:
            raise Exception(f"Errore OCR: {e}")

    @staticmethod
    def _read_text(file_path):
        """Legge file testo"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            return text
        except Exception as e:
            raise Exception(f"Errore lettura testo: {e}")


# ============================================================================
# 2. EMBEDDING E RAG
# ============================================================================

def create_embeddings(texts):
    """Crea embeddings con OLLAMA"""

    if isinstance(texts, str):
        texts = [texts]

    print(f"🔄 Creando embeddings per {len(texts)} testi...")

    embeddings = []
    for i, text in enumerate(texts):
        try:
            payload = {
                "model": config.OLLAMA_EMBEDDING_MODEL,
                "prompt": text[:2000]  # Limita per velocità
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
            print(f"  ❌ Errore: {e}")
            embeddings.append([])

    print(f"✅ Embeddings creati\n")
    return embeddings


# ============================================================================
# 3. RAG SYSTEM
# ============================================================================

class RAGSystem:
    """Vector store locale con FAISS"""

    def __init__(self):
        self.storage_path = Path(config.VECTOR_STORE_PATH)
        self.storage_path.mkdir(exist_ok=True)
        self.vector_stores = {}
        print(f"✅ RAG System inizializzato\n")

    def add_document(self, patient_id, file_path):
        """Carica un documento da file"""

        # Leggi file
        text = DocumentReader.read_file(file_path)
        print(f"✅ Testo estratto: {len(text)} caratteri\n")

        # Split in chunks
        chunks = self._split_into_chunks(text)
        print(f"✅ {len(chunks)} chunks creati\n")

        # Crea embeddings
        embeddings = create_embeddings(chunks)

        if not embeddings or not embeddings[0]:
            print("❌ Errore: embeddings non creati")
            return False

        # FAISS
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

        print(f"✅ Documento caricato per paziente {patient_id}\n")
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

    def _split_into_chunks(self, text):
        """Split testo in chunks"""
        chunks = []

        paragraphs = text.split("\n\n")
        for para in paragraphs:
            if len(para) > 100:
                chunk_size = 6000
                for i in range(0, len(para), chunk_size):
                    chunk = para[i:i + chunk_size].strip()
                    if chunk:
                        chunks.append(chunk)

        return chunks if chunks else [""]


# ============================================================================
# 4. ANALISI REFERTI
# ============================================================================

def generate_text(prompt, max_tokens=1024):
    """Genera testo con OLLAMA"""

    print("⏳ OLLAMA sta elaborando...")

    try:
        payload = {
            "model": config.OLLAMA_MODEL,
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
            timeout=300
        )
        response.raise_for_status()

        result = ""
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                result += data.get("response", "")

        print(f"✅ Elaborazione completata\n")
        return result.strip()

    except Exception as e:
        print(f"❌ Errore: {e}")
        raise


class MedicalAnalyzer:
    """Analizza referti caricati"""

    def __init__(self, rag):
        self.rag = rag

    def analyze_referral(self, patient_id):
        """Analizza il referto caricato"""

        print("📊 Analizzando referto...\n")

        # Recupera tutto il documento
        chunks = self.rag.search(patient_id, "diagnosi esami valori risultati", top_k=20)

        if not chunks:
            return "❌ Nessun documento trovato"

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Sei un medico esperto. Analizza questo referto medico in dettaglio.

REFERTO:
{context}

Fornisci un'analisi STRUTTURATA con:

1. **DIAGNOSI**: Cosa dice il referto?
2. **ESAMI EFFETTUATI**: Quali esami sono stati fatti?
3. **RISULTATI PRINCIPALI**: Quali sono i risultati?
4. **VALORI ANOMALI**: Ci sono valori fuori range?
5. **OSSERVAZIONI**: Cosa osservi di rilevante?
6. **RACCOMANDAZIONI**: Cosa consigli?

Sii preciso e clinico."""

        return generate_text(prompt, max_tokens=1500)

    def extract_key_data(self, patient_id):
        """Estrae dati chiave dal referto"""

        print("🔍 Estraendo dati chiave...\n")

        chunks = self.rag.search(patient_id, "diagnosi valori risultati", top_k=10)

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Estrai i dati CHIAVE da questo referto in formato strutturato.

REFERTO:
{context}

Estrai e formatta come LISTA:

**DIAGNOSI PRINCIPALE:**
- [diagnosi]

**ESAMI EFFETTUATI:**
- [esame 1]: [risultato]
- [esame 2]: [risultato]

**VALORI IMPORTANTI:**
- [valore 1]: [numero] (range normale: [range])
- [valore 2]: [numero] (range normale: [range])

**ALLERGIE/CONTROINDICAZIONI:**
- [allergia 1]
- [allergia 2]

**FARMACI PRESCRITTI:**
- [farmaco 1]: [dosaggio]
- [farmaco 2]: [dosaggio]

**FOLLOW-UP RACCOMANDATO:**
- [follow-up 1]
- [follow-up 2]"""

        return generate_text(prompt, max_tokens=1024)

    def find_abnormalities(self, patient_id):
        """Identifica anomalie nel referto"""

        print("🔍 Cercando anomalie...\n")

        chunks = self.rag.search(patient_id, "valori anomali fuori range elevato basso", top_k=15)

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Identifica TUTTE le anomalie in questo referto medico.

REFERTO:
{context}

Per ogni anomalia fornisci:

**ANOMALIA:**
- Valore/Risultato anomalo
- Range normale
- Interpretazione clinica
- Possibili cause
- Grado di gravità (LIEVE/MODERATO/GRAVE)

Sii esaustivo."""

        return generate_text(prompt, max_tokens=1500)


# ============================================================================
# 5. PROGRAMMA PRINCIPALE
# ============================================================================

def main():
    """Carica referti e analizza"""

    print("""
╔═══════════════════════════════════════════════════════════════╗
║        🏥 CARICA REFERTI MEDICI - ANALYZA CON OLLAMA         ║
║                                                               ║
║  Supporta: PDF, immagini (JPG, PNG), testi (TXT)            ║
║  Analizza con OLLAMA (senza API keys)                        ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Verifica OLLAMA
    try:
        response = requests.get(f"{config.OLLAMA_HOST}/api/tags", timeout=2)
        if response.status_code != 200:
            raise Exception()
    except:
        print("""
❌ OLLAMA NON è online!

Installa da: https://ollama.ai
Poi esegui:
$ ollama pull llama2:13b
$ ollama pull nomic-embed-text
$ ollama serve &
        """)
        return

    print("✅ OLLAMA è online\n")

    # Crea RAG
    rag = RAGSystem()
    analyzer = MedicalAnalyzer(rag)

    # ========================================================================
    # CARICA UN REFERTO
    # ========================================================================

    print("=" * 60)
    print("CARICA UN REFERTO")
    print("=" * 60)

    # Chiedi il file
    file_path = input("\n📁 Inserisci il percorso del referto (PDF, immagine, testo):\n> ").strip()

    if not file_path:
        print("❌ Nessun file inserito")
        return

    try:
        # Carica
        rag.add_document("PAT001", file_path)

    except Exception as e:
        print(f"❌ Errore: {e}")
        return

    # ========================================================================
    # ANALIZZA
    # ========================================================================

    print("\n" + "=" * 60)
    print("1. ANALISI COMPLETA")
    print("=" * 60)
    analysis = analyzer.analyze_referral("PAT001")
    print(f"\n{analysis}")

    print("\n" + "=" * 60)
    print("2. DATI CHIAVE")
    print("=" * 60)
    key_data = analyzer.extract_key_data("PAT001")
    print(f"\n{key_data}")

    print("\n" + "=" * 60)
    print("3. ANOMALIE")
    print("=" * 60)
    anomalies = analyzer.find_abnormalities("PAT001")
    print(f"\n{anomalies}")

    # ========================================================================
    # DOMANDE LIBERE
    # ========================================================================

    print("\n" + "=" * 60)
    print("DOMANDE LIBERE")
    print("=" * 60)
    print("\nPuoi fare domande sul referto (digita 'esci' per finire):\n")

    while True:
        domanda = input("❓ Domanda: ").strip()

        if domanda.lower() == "esci":
            break

        if not domanda:
            continue

        # Recupera context
        chunks = rag.search("PAT001", domanda, top_k=5)
        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Rispondi a questa domanda basandoti sul referto:

DOMANDA: {domanda}

REFERTO:
{context}

Rispondi in modo chiaro e diretto."""

        risposta = generate_text(prompt, max_tokens=512)
        print(f"\n📝 {risposta}\n")

    print("\n✅ Fine analisi")


# ============================================================================
# AVVIA
# ============================================================================

if __name__ == "__main__":
    main()