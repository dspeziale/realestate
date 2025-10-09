import requests
import json
from typing import List, Dict


class OllamaClient:
    """Client per interagire con Ollama in locale"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"

    def generate(self, model: str, prompt: str, stream: bool = False) -> str:
        """Genera una risposta dal modello"""
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
        """Chat con conversazione multi-turno"""
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


class BiomarkerAnalyzer:
    """Analizzatore di biomarker per casi oncologici"""

    def __init__(self, model: str = "gemma3:4b"):
        self.client = OllamaClient()
        self.model = model

    def analyze_biomarkers(self, patient_data: Dict) -> str:
        """Analizza i biomarker rilevanti per un paziente specifico"""

        prompt = f"""Sei un ematologo-oncologo esperto. Analizza questo caso clinico e identifica i biomarker più importanti da monitorare.
          
            CASO CLINICO:
            - ID Paziente: {patient_data['patient_id']}
            - Diagnosi: {patient_data['diagnosis']}
            - Trattamento: {patient_data['treatment']}
            - Esito: {patient_data['outcome']}
            - Tipo di campione: {patient_data['specimen_type']}
            
            Fornisci un'analisi dettagliata che includa:
            
            1. BIOMARKER DIAGNOSTICI (per confermare/caratterizzare la malattia)
            2. BIOMARKER PROGNOSTICI (per valutare l'evoluzione)
            3. BIOMARKER PREDITTIVI (per la risposta al trattamento)
            4. BIOMARKER DI MONITORAGGIO (per seguire la malattia minima residua)
            5. FREQUENZA DI CONTROLLO RACCOMANDATA
            
            Sii specifico e tecnico nella risposta."""

        print(f"\n{'=' * 70}")
        print(f"🔬 ANALISI BIOMARKER - {patient_data['patient_id']}")
        print(f"📋 Diagnosi: {patient_data['diagnosis']}")
        print(f"{'=' * 70}\n")

        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            stream=True
        )

        return response

    def compare_biomarkers(self, patients: List[Dict]) -> str:
        """Confronta i biomarker di più pazienti"""

        cases_summary = "\n".join([
            f"- {p['patient_id']}: {p['diagnosis']}"
            for p in patients
        ])

        prompt = f"""Sei un ematologo-oncologo esperto. Hai questi casi clinici:

{cases_summary}

Fornisci un'analisi comparativa dei biomarker, evidenziando:
1. Biomarker comuni a più patologie
2. Biomarker specifici per ciascuna patologia
3. Panel di biomarker ottimale per screening multi-patologia
4. Tecnologie di analisi raccomandate (citofluorimetria, NGS, PCR, ecc.)"""

        print(f"\n{'=' * 70}")
        print(f"🔬 ANALISI COMPARATIVA BIOMARKER")
        print(f"{'=' * 70}\n")

        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            stream=True
        )

        return response

    def get_monitoring_schedule(self, patient_data: Dict) -> str:
        """Genera un piano di monitoraggio dei biomarker"""

        prompt = f"""Sei un ematologo-oncologo esperto. Per questo paziente:

- Diagnosi: {patient_data['diagnosis']}
- Trattamento: {patient_data['treatment']}
- Esito attuale: {patient_data['outcome']}

Crea un PIANO DI MONITORAGGIO BIOMARKER dettagliato con:

1. FASE INTENSIVA (durante trattamento attivo)
   - Biomarker da controllare
   - Frequenza dei controlli
   - Valori soglia di allarme

2. FASE DI CONSOLIDAMENTO
   - Biomarker da controllare
   - Frequenza dei controlli

3. FASE DI MANTENIMENTO/FOLLOW-UP
   - Biomarker da controllare
   - Frequenza dei controlli

4. CRITERI DI ALLERTA per ripresa di malattia

Formato tabellare chiaro e preciso."""

        print(f"\n{'=' * 70}")
        print(f"📅 PIANO MONITORAGGIO - {patient_data['patient_id']}")
        print(f"{'=' * 70}\n")

        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            stream=True
        )

        return response


def main():
    """Esempio principale con analisi biomarker"""

    # Pazienti di esempio
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

    print("=" * 70)
    print("ANALISI BIOMARKER PER CASI ONCOLOGICI EMATOLOGICI")
    print("Powered by Ollama + Llama 3.1")
    print("=" * 70)

    # Inizializza analyzer
    analyzer = BiomarkerAnalyzer(model="gemma3:4b")

    # Analizza biomarker per ogni paziente
    all_analyses = []

    for patient in sample_patients:
        analysis = analyzer.analyze_biomarkers(patient)
        all_analyses.append({
            'patient_id': patient['patient_id'],
            'diagnosis': patient['diagnosis'],
            'biomarker_analysis': analysis
        })

        # Pausa tra le analisi
        print("\n" + "-" * 70)
        input("Premi ENTER per continuare con il prossimo paziente...")

    # Analisi comparativa
    print("\n\n")
    analyzer.compare_biomarkers(sample_patients)

    # Piano di monitoraggio per un caso specifico
    print("\n\n")
    print("=" * 70)
    print("ESEMPIO: PIANO DI MONITORAGGIO DETTAGLIATO")
    print("=" * 70)

    # Prendi il primo paziente come esempio
    analyzer.get_monitoring_schedule(sample_patients[0])

    # Salva tutte le analisi
    output_file = 'biomarker_analyses.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_analyses, f, indent=2, ensure_ascii=False)

    print(f"\n\n✅ Tutte le analisi salvate in '{output_file}'")
    print("=" * 70)


def interactive_mode():
    """Modalità interattiva per domande specifiche"""

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
            'treatment': 'Immunochemioterapia R-CHOP',
            'outcome': 'Risposta parziale, trattamento in corso',
            'specimen_type': 'Biopsia linfonodale'
        },
        {
            'patient_id': 'PAT003',
            'diagnosis': 'Mieloma Multiplo con coinvolgimento osseo',
            'treatment': 'Terapia con bortezomib, lenalidomide e desametasone',
            'outcome': 'Malattia stabile con riduzione delle plasmacellule',
            'specimen_type': 'Prelievo ematico e biopsia ossea'
        }
    ]

    print("\n" + "=" * 70)
    print("MODALITÀ INTERATTIVA - CONSULTO BIOMARKER")
    print("=" * 70)

    print("\nCasi disponibili:")
    for i, p in enumerate(sample_patients, 1):
        print(f"{i}. {p['patient_id']}: {p['diagnosis']}")

    try:
        choice = int(input("\nScegli un caso (1-3): ")) - 1
        selected_patient = sample_patients[choice]
    except (ValueError, IndexError):
        print("Selezione non valida, uso il primo caso")
        selected_patient = sample_patients[0]

    client = OllamaClient()

    # Setup contesto
    conversation_history = [
        {
            "role": "system",
            "content": "Sei un ematologo-oncologo esperto in biomarker e medicina di laboratorio."
        },
        {
            "role": "user",
            "content": f"Sto seguendo questo paziente: {json.dumps(selected_patient, indent=2, ensure_ascii=False)}"
        },
        {
            "role": "assistant",
            "content": "Ho preso visione del caso. Sono pronto a rispondere alle tue domande sui biomarker e sul monitoraggio clinico."
        }
    ]

    print(f"\n💬 Chat attiva per {selected_patient['patient_id']}")
    print("Digita 'exit' per uscire\n")

    # Domande predefinite
    predefined_questions = [
        "Quali sono i biomarker più importanti da monitorare?",
        "Con che frequenza dovrei controllare questi biomarker?",
        "Quali valori soglia indicano una recidiva?",
        "Ci sono biomarker emergenti per questa patologia?",
        "Quale tecnologia di analisi è più accurata?"
    ]

    print("Domande suggerite:")
    for i, q in enumerate(predefined_questions, 1):
        print(f"{i}. {q}")

    print("\nOppure scrivi la tua domanda personalizzata:")

    while True:
        user_input = input("\n❓ La tua domanda: ").strip()

        if user_input.lower() in ['exit', 'quit', 'esci']:
            print("\n👋 Consulto terminato!")
            break

        # Se l'utente digita un numero, usa la domanda predefinita
        if user_input.isdigit():
            idx = int(user_input) - 1
            if 0 <= idx < len(predefined_questions):
                user_input = predefined_questions[idx]
            else:
                print("Numero non valido")
                continue

        if not user_input:
            continue

        conversation_history.append({
            "role": "user",
            "content": user_input
        })

        print("\n💡 Risposta: ", end='')
        response = client.chat(
            model="gemma3:4b",
            messages=conversation_history,
            stream=True
        )

        conversation_history.append({
            "role": "assistant",
            "content": response
        })

        print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        main()

        print("\n\n💡 Vuoi entrare in modalità interattiva?")
        print("   Riavvia con: python script.py --interactive")