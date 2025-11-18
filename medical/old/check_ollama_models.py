"""
DIAGNOSTICA OLLAMA
Verifica quali modelli hai e quale è più veloce
"""

import requests
import json
from datetime import datetime

OLLAMA_HOST = "http://localhost:11434"


def list_models():
    """Elenca tutti i modelli disponibili"""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        response.raise_for_status()

        data = response.json()
        models = data.get("models", [])

        if not models:
            print("❌ Nessun modello trovato!")
            return []

        print("\n" + "=" * 70)
        print("📦 MODELLI DISPONIBILI IN OLLAMA")
        print("=" * 70)

        for model in models:
            name = model.get("name", "N/A")
            size = model.get("size", 0)
            size_gb = size / (1024 ** 3)

            print(f"\n🔹 {name}")
            print(f"   Dimensione: {size_gb:.2f} GB")

        return models

    except Exception as e:
        print(f"❌ Errore: {e}")
        return []


def te_embedding_speed(model_name, test_text):
    """Testa la velocità di un modello di embedding"""
    try:
        print(f"\n⏱️  Testando {model_name}...")

        start = datetime.now()

        payload = {
            "model": model_name,
            "prompt": test_text
        }

        response = requests.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json=payload,
            timeout=300
        )
        response.raise_for_status()

        elapsed = (datetime.now() - start).total_seconds()

        data = response.json()
        embedding = data.get("embedding", [])

        print(f"   ✅ Successo in {elapsed:.2f} secondi")
        print(f"   Dimensione embedding: {len(embedding)}")

        return elapsed

    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return None


def te_generation_speed(model_name, prompt):
    """Testa la velocità di un modello di generazione"""
    try:
        print(f"\n⏱️  Testando {model_name}...")

        start = datetime.now()

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 100,
                "temperature": 0.1,
            }
        }

        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=300
        )
        response.raise_for_status()

        elapsed = (datetime.now() - start).total_seconds()

        print(f"   ✅ Successo in {elapsed:.2f} secondi")

        return elapsed

    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return None


def main():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║           🔧 DIAGNOSTICA OLLAMA - VELOCITÀ MODELLI            ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Lista modelli
    models = list_models()

    if not models:
        print("\n❌ Nessun modello disponibile")
        return

    # Dividi modelli per tipo
    embedding_models = [m for m in models if "embed" in m.get("name", "").lower()]
    generation_models = [m for m in models if "embed" not in m.get("name", "").lower()]

    # Test embedding models
    if embedding_models:
        print("\n" + "=" * 70)
        print("🧪 TEST MODELLI DI EMBEDDING")
        print("=" * 70)

        test_text = "Questa è una analisi medica di test per valutare la velocità del modello di embedding in millisecondi e microsecondi"

        embedding_speeds = {}
        for model in embedding_models:
            name = model.get("name")
            speed = te_embedding_speed(name, test_text)
            if speed:
                embedding_speeds[name] = speed

        if embedding_speeds:
            print("\n📊 RISULTATI EMBEDDING (dal più veloce):")
            for name, speed in sorted(embedding_speeds.items(), key=lambda x: x[1]):
                print(f"   {name}: {speed:.2f}s")

    # Test generation models
    if generation_models:
        print("\n" + "=" * 70)
        print("🧪 TEST MODELLI DI GENERAZIONE")
        print("=" * 70)

        test_prompt = "In 50 parole, quali sono i fattori di rischio del diabete?"

        generation_speeds = {}
        for model in generation_models:
            name = model.get("name")
            speed = te_generation_speed(name, test_prompt)
            if speed:
                generation_speeds[name] = speed

        if generation_speeds:
            print("\n📊 RISULTATI GENERAZIONE (dal più veloce):")
            for name, speed in sorted(generation_speeds.items(), key=lambda x: x[1]):
                print(f"   {name}: {speed:.2f}s")

    print("\n" + "=" * 70)
    print("💡 RACCOMANDAZIONI")
    print("=" * 70)

    if embedding_speeds:
        fastest_embed = min(embedding_speeds, key=embedding_speeds.get)
        print(f"\n✅ Usa questo modello di EMBEDDING: {fastest_embed}")
        print(f"   (tempo medio: {embedding_speeds[fastest_embed]:.2f}s)")

    if generation_speeds:
        fastest_gen = min(generation_speeds, key=generation_speeds.get)
        print(f"\n✅ Usa questo modello di GENERAZIONE: {fastest_gen}")
        print(f"   (tempo medio: {generation_speeds[fastest_gen]:.2f}s)")


if __name__ == "__main__":
    main()