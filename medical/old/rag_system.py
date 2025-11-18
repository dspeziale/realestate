"""
RAG SYSTEM - Retrieval-Augmented Generation
Memorizza documenti medici e li ritrova quando servono
"""

import json
import os
from pathlib import Path
import numpy as np

try:
    import faiss
except ImportError:
    print("Installa: pip install faiss-cpu")


class RAGSystem:
    """Sistema RAG locale con FAISS - ZERO cloud"""

    def __init__(self, config, llm_interface, storage_path=None):
        self.config = config
        self.llm = llm_interface

        if storage_path is None:
            storage_path = config.VECTOR_STORE_PATH

        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.vector_stores = {}
        print(f"✅ RAG System inizializzato: {self.storage_path}")

    def ingest_documents(self, patient_id, documents):
        """
        Ingesta documenti medici per un paziente

        documents: lista di testi

        Esempio:
            rag.ingest_documents("PAT001", ["documento 1", "documento 2"])
        """

        print(f"📄 Ingestione documenti per paziente {patient_id}...")

        # Split documenti in chunks
        chunks = self._split_into_chunks(documents)
        print(f"   ✓ {len(chunks)} chunks creati")

        # Crea embeddings
        embeddings = self.llm.embed(chunks)
        print(f"   ✓ Embeddings creati")

        # Crea FAISS index
        dimension = len(embeddings[0]) if embeddings else 1536
        index = faiss.IndexFlatL2(dimension)

        embeddings_array = np.array(embeddings, dtype=np.float32)
        index.add(embeddings_array)
        print(f"   ✓ FAISS index creato")

        # Salva metadati
        metadata = [
            {"text": chunk, "chunk_id": i}
            for i, chunk in enumerate(chunks)
        ]

        # Salva su disco
        index_path = self.storage_path / f"{patient_id}.index"
        meta_path = self.storage_path / f"{patient_id}.json"

        faiss.write_index(index, str(index_path))
        with open(meta_path, "w") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # Salva in memoria
        self.vector_stores[patient_id] = {
            "index": index,
            "metadata": metadata,
            "dimension": dimension
        }

        print(f"✅ Documento salvato per {patient_id}")
        return True

    def retrieve(self, patient_id, query, top_k=5):
        """
        Recupera i documenti più rilevanti per una query

        Ritorna lista di chunk rilevanti

        Esempio:
            chunks = rag.retrieve("PAT001", "quali allergie?", top_k=3)
        """

        # Carica store se non in memoria
        if patient_id not in self.vector_stores:
            self._load_store(patient_id)

        store = self.vector_stores.get(patient_id)
        if not store:
            print(f"⚠️ Nessun documento per paziente {patient_id}")
            return []

        # Crea embedding della query
        query_embedding = self.llm.embed([query])[0]
        query_array = np.array([query_embedding], dtype=np.float32)

        # Cerca nel FAISS
        distances, indices = store["index"].search(query_array, min(top_k, len(store["metadata"])))

        # Ritorna chunk rilevanti
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx < len(store["metadata"]):
                chunk = store["metadata"][idx]
                results.append({
                    "text": chunk["text"],
                    "relevance": 1 / (1 + dist)  # Converti distanza in score
                })

        return results

    def _split_into_chunks(self, documents):
        """Split documenti in chunk di ~1500 tokens"""

        chunks = []

        for doc in documents:
            # Split per paragrafi prima
            paragraphs = doc.split("\n\n")

            for para in paragraphs:
                if len(para) < 100:
                    continue

                # Split in chunks da ~1500 token (4 chars ~ 1 token)
                chunk_size = 1500 * 4
                for i in range(0, len(para), chunk_size):
                    chunk = para[i:i + chunk_size].strip()
                    if chunk:
                        chunks.append(chunk)

        return chunks if chunks else [""]

    def _load_store(self, patient_id):
        """Carica vector store da disco"""

        index_path = self.storage_path / f"{patient_id}.index"
        meta_path = self.storage_path / f"{patient_id}.json"

        if not index_path.exists() or not meta_path.exists():
            print(f"⚠️ Store non trovato per {patient_id}")
            return False

        try:
            index = faiss.read_index(str(index_path))
            with open(meta_path) as f:
                metadata = json.load(f)

            self.vector_stores[patient_id] = {
                "index": index,
                "metadata": metadata,
                "dimension": index.d
            }
            print(f"✅ Store caricato per {patient_id}")
            return True

        except Exception as e:
            print(f"❌ Errore caricamento store: {e}")
            return False