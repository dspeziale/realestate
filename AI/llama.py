import requests
import json
from typing import List, Dict, Optional


class OllamaClient:
    """
    Client per interagire con Ollama in locale
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"

    def generate(self, model: str, prompt: str, stream: bool = False) -> str:
        """
        Genera una risposta dal modello
        """
        url = f"{self.api_url}/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }

        response = requests.post(url, json=payload)

        if stream:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    json_response = json.loads(line)
                    if 'response' in json_response:
                        chunk = json_response['response']
                        print(chunk, end='', flush=True)
                        full_response += chunk
            print()
            return full_response
        else:
            result = response.json()
            return result.get('response', '')

    def chat(self, model: str, messages: List[Dict], stream: bool = False) -> str:
        """
        Chat con conversazione multi-turno
        """
        url = f"{self.api_url}/chat"

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream
        }

        response = requests.post(url, json=payload)

        if stream:
            full_response = ""
            for line in response.iter_lines():
                if line:
                    json_response = json.loads(line)
                    if 'message' in json_response:
                        chunk = json_response['message'].get('content', '')
                        print(chunk, end='', flush=True)
                        full_response += chunk
            print()
            return full_response
        else:
            result = response.json()
            return result.get('message', {}).get('content', '')

    def list_models(self) -> List[Dict]:
        """
        Lista tutti i modelli disponibili
        """
        url = f"{self.api_url}/tags"
        response = requests.get(url)
        return response.json().get('models', [])

    def pull_model(self, model: str):
        """
        Scarica un modello
        """
        url = f"{self.api_url}/pull"
        payload = {"name": model}

        print(f"Scaricando modello {model}...")
        response = requests.post(url, json=payload, stream=True)

        for line in response.iter_lines():
            if line:
                progress = json.loads(line)
                status = progress.get('status', '')
                print(f"\r{status}", end='', flush=True)
        print("\n✓ Download completato!")

    def embed(self, model: str, text: str) -> List[float]:
        """
        Genera embeddings per un testo
        """
        url = f"{self.api_url}/embeddings"

        payload = {
            "model": model,
            "prompt": text
        }

        response = requests.post(url, json=payload)
        return response.json().get('embedding', [])


class ClinicalAnnotationWithOllama:
    """
    Sistema di annotazione clinica usando Ollama locale
    """

    def __init__(self, model: str = "llama3.1:8b"):
        self.client = OllamaClient()
        self.model = model
        self.conversation_history = []

    def annotate_patient_record(self, patient_data: Dict) -> Dict:
        """
        Annota un record paziente usando Ollama
        """
        prompt = f"""Sei un esperto di annotazione clinica oncologica. 
Analizza questo record paziente e genera un'annotazione strutturata.

RECORD PAZIENTE:
- Diagnosi: {patient_data.get('diagnosis', 'N/A')}
- Trattamento: {patient_data.get('treatment', 'N/A')}
- Esito: {patient_data.get('outcome', 'N/A')}
- Tipo specimen: {patient_data.get('specimen_type', 'N/A')}

Fornisci un'annotazione in formato JSON con questi campi:
- cancer_type: tipo specifico di cancro
- treatment_protocol: protocollo di trattamento
- response_status: stato della risposta al trattamento
- biomarkers: lista di biomarker rilevanti
- clinical_stage: stadio clinico
- prognosis: prognosi

Rispondi SOLO con il JSON, senza altri commenti."""

        print(f"\n🔬 Analizzando paziente {patient_data.get('patient_id', 'N/A')}...")

        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            stream=False
        )

        # Prova a estrarre JSON dalla risposta
        try:
            # Trova il JSON nella risposta
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                annotation = json.loads(json_str)
            else:
                annotation = {"raw_response": response}
        except json.JSONDecodeError:
            annotation = {"raw_response": response}

        return annotation

    def chat_about_case(self, question: str) -> str:
        """
        Fai domande sul caso clinico
        """
        self.conversation_history.append({
            "role": "user",
            "content": question
        })

        response = self.client.chat(
            model=self.model,
            messages=self.conversation_history,
            stream=True
        )

        self.conversation_history.append({
            "role": "assistant",
            "content": response
        })

        return response

    def summarize_multiple_cases(self, cases: List[Dict]) -> str:
        """
        Riassume multipli casi clinici
        """
        cases_text = "\n\n".join([
            f"Caso {i + 1}: {case.get('diagnosis', 'N/A')} - Trattamento: {case.get('treatment', 'N/A')}"
            for i, case in enumerate(cases)
        ])

        prompt = f"""Analizza questi casi oncologici e fornisci un riassunto clinico:

{cases_text}

Fornisci:
1. Pattern comuni identificati
2. Approcci terapeutici prevalenti
3. Raccomandazioni per la ricerca"""

        return self.client.generate(
            model=self.model,
            prompt=prompt,
            stream=True
        )


def main():
    print("=" * 70)
    print("SISTEMA DI ANNOTAZIONE CLINICA CON OLLAMA")
    print("=" * 70)

    # Inizializza client
    client = OllamaClient()

    # Lista modelli disponibili
    print("\n📋 Modelli disponibili:")
    models = client.list_models()
    if models:
        for i, model in enumerate(models, 1):
            print(f"  {i}. {model.get('name', 'N/A')}")
    else:
        print("  Nessun modello trovato. Scaricane uno!")

    # Scegli il modello (o usa uno predefinito)
    # Se non hai llama3.1, puoi scaricare llama3.2 o llama2
    model_to_use = "gemma3:4b"  # Cambia in base a quello che hai

    print(f"\n🤖 Usando modello: {model_to_use}")

    # Inizializza sistema annotazione
    annotator = ClinicalAnnotationWithOllama(model=model_to_use)

    # Casi clinici di esempio
    sample_patients = [
        {
            'patient_id': 'PAT001',
            'diagnosis': 'Leucemia Mieloide Acuta (LMA)',
            'treatment': 'Chemioterapia di induzione con daunorubicina e citarabina',
            'outcome': 'Remissione completa dopo il primo ciclo',
            'specimen_type': 'Aspirato midollare'
        },
        {
            'patient_id': 'PAT002',
            'diagnosis': 'Linfoma Diffuso a Grandi Cellule B',
            'treatment': 'Immunochemioterapia R-CHOP (rituximab, ciclofosfamide, doxorubicina, vincristina, prednisone)',
            'outcome': 'Risposta parziale, trattamento in corso',
            'specimen_type': 'Biopsia linfonodale'
        },
        {
            'patient_id': 'PAT003',
            'diagnosis': 'Mieloma Multiplo con coinvolgimento osseo',
            'treatment': 'Terapia con bortezomib, lenalidomide e desametasone',
            'outcome': 'Malattia stabile con riduzione delle plasmacellule',
            'specimen_type': 'Prelievo ematico e biopsia ossea'
        },
        {
            'patient_id': 'PAT004',
            'diagnosis': 'Leucemia Linfoblastica Acuta (LLA) Ph-positiva',
            'treatment': 'Chemioterapia intensiva con imatinib e regime HyperCVAD',
            'outcome': 'Negatività della malattia minima residua dopo 3 mesi',
            'specimen_type': 'Aspirato midollare e sangue periferico'
        },
        {
            'patient_id': 'PAT005',
            'diagnosis': 'Linfoma di Hodgkin classico, tipo sclerosi nodulare',
            'treatment': 'Chemioterapia ABVD (adriamicina, bleomicina, vinblastina, dacarbazina)',
            'outcome': 'Remissione completa confermata con PET-TC negativa',
            'specimen_type': 'Biopsia linfonodale con immunoistochimica'
        },
        {
            'patient_id': 'PAT006',
            'diagnosis': 'Sindrome Mielodisplastica ad alto rischio',
            'treatment': 'Agente ipometilante azacitidina con supporto trasfusionale',
            'outcome': 'Malattia progressiva con evoluzione in leucemia acuta',
            'specimen_type': 'Aspirato e biopsia osteomidollare'
        }
    ]

    # Annota i pazienti
    print("\n" + "=" * 70)
    print("ANNOTAZIONE AUTOMATICA DEI CASI")
    print("=" * 70)

    annotations = []
    for patient in sample_patients:
        annotation = annotator.annotate_patient_record(patient)
        annotations.append({
            'patient_id': patient['patient_id'],
            'annotation': annotation
        })

        print(f"\n✓ Annotazione completata per {patient['patient_id']}")
        print(json.dumps(annotation, indent=2, ensure_ascii=False))

    # Chat interattiva sul caso
    print("\n" + "=" * 70)
    print("CHAT INTERATTIVA SUL CASO CLINICO")
    print("=" * 70)

    print("\n💬 Puoi fare domande sul primo caso (digita 'exit' per uscire)")

    # Setup contesto iniziale
    annotator.conversation_history = [{
        "role": "system",
        "content": "Sei un oncologo esperto specializzato in leucemia mieloide acuta."
    }, {
        "role": "user",
        "content": f"Ho questo paziente: {json.dumps(sample_patients[0], indent=2)}"
    }]

    # Esempio di domande
    example_questions = [
        "Quali sono i biomarker più importanti da monitorare?",
        "Qual è la prognosi tipica per questo tipo di caso?"
    ]

    for question in example_questions:
        print(f"\n❓ Domanda: {question}")
        print(f"💡 Risposta: ", end='')
        annotator.chat_about_case(question)

    # Riassunto multipli casi
    print("\n" + "=" * 70)
    print("ANALISI AGGREGATA CASI")
    print("=" * 70)
    print("\n📊 Generando riassunto clinico...\n")

    annotator.summarize_multiple_cases(sample_patients)

    # Salva risultati
    output_file = 'ollama_annotations.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)

    print(f"\n\n✓ Annotazioni salvate in '{output_file}'")
    print("=" * 70)


# Funzioni utility extra
def simple_prompt_example():
    """
    Esempio semplice di prompt singolo
    """
    client = OllamaClient()

    print("\n🔹 ESEMPIO SEMPLICE")
    print("-" * 50)

    prompt = "Spiega in 2 frasi cosa sono i biomarker oncologici"
    print(f"Prompt: {prompt}\n")
    print("Risposta: ", end='')

    response = client.generate(
        model="llama3.1:8b",
        prompt=prompt,
        stream=True
    )


def embedding_example():
    """
    Esempio di generazione embeddings
    """
    client = OllamaClient()

    print("\n🔹 ESEMPIO EMBEDDINGS")
    print("-" * 50)

    text = "Leucemia mieloide acuta con mutazione FLT3"
    embeddings = client.embed(model="llama3.1:8b", text=text)

    print(f"Testo: {text}")
    print(f"Dimensione embedding: {len(embeddings)}")
    print(f"Primi 5 valori: {embeddings[:5]}")


if __name__ == "__main__":
    # Esegui esempio principale
    main()

    # Decommentare per altri esempi
    # simple_prompt_example()
    # embedding_example()