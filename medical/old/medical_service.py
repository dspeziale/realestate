"""
MEDICAL SERVICE - Le 4 capabilities mediche:
1. Riassunto storia medica
2. Risposta a domande
3. Anomalie
4. Predizioni cliniche
"""


class MedicalService:
    """Le 4 capabilities principali"""

    def __init__(self, config, llm_interface, rag_system):
        self.config = config
        self.llm = llm_interface
        self.rag = rag_system

    # ========================================================================
    # CAPABILITY 1: RIASSUNTO STORIA MEDICA
    # ========================================================================
    def summarize_patient(self, patient_id):
        """
        Riassume la storia medica completa di un paziente

        Cosa ritorna:
        - Diagnosi principali
        - Farmaci attuali
        - Allergie (IMPORTANTE!)
        - Interventi chirurgici
        - Fattori di rischio
        """

        print(f"\n📋 Riassumendo storia medica per paziente {patient_id}...")

        # Recupera documenti dal RAG
        query = "storia medica diagnosi allergie farmaci interventi"
        chunks = self.rag.retrieve(patient_id, query, top_k=10)

        if not chunks:
            return "❌ Nessun documento trovato per questo paziente"

        # Costruisci context
        context = "\n\n".join([c["text"] for c in chunks])

        # Prompt medico
        prompt = f"""Sei un medico. Basandoti su questa documentazione medica,
fornisci un riassunto strutturato della storia medica del paziente.

DOCUMENTAZIONE:
{context}

Nel riassunto includi:
1. Diagnosi principali
2. Farmaci attuali
3. ALLERGIE (IMPORTANTE!)
4. Interventi chirurgici
5. Fattori di rischio

Formato: Usa heading (###) per sezioni."""

        result = self.llm.generate(prompt, use_case="general")

        print(f"✅ Riassunto completato")
        return result

    # ========================================================================
    # CAPABILITY 2: RISPOSTA A DOMANDE
    # ========================================================================
    def ask_question(self, patient_id, question):
        """
        Risponde a domande specifiche sulla documentazione medica

        Esempi:
        - "Quali allergie ha il paziente?"
        - "Che farmaci sta prendendo?"
        - "Ha avuto interventi chirurgici?"
        """

        print(f"\n❓ Domanda per paziente {patient_id}: {question}")

        # Recupera documenti rilevanti
        chunks = self.rag.retrieve(patient_id, question, top_k=5)

        if not chunks:
            return "⚠️ Non ho trovato informazioni rilevanti"

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Rispondi a questa domanda BASANDOTI SOLO sulla documentazione.

DOMANDA: {question}

DOCUMENTAZIONE DISPONIBILE:
{context}

Istruzioni:
1. Rispondi in modo chiaro e specifico
2. Se l'informazione non è disponibile, indicalo
3. Cita la fonte della risposta
4. Sii breve e diretto"""

        result = self.llm.generate(prompt, use_case="fast")

        return result

    # ========================================================================
    # CAPABILITY 3: ANOMALIE
    # ========================================================================
    def find_anomalies(self, patient_id):
        """
        Identifica anomalie e valori strani nei dati medici

        Cerca:
        - Valori di laboratorio fuori range
        - Trend preoccupanti
        - Inconsistenze nei dati
        """

        print(f"\n🔍 Analizzando anomalie per paziente {patient_id}...")

        # Recupera tutti i dati medici
        chunks = self.rag.retrieve(patient_id, "valori laboratorio anomalie fuori range", top_k=15)

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""Analizza questa documentazione medica alla ricerca di ANOMALIE.

DOCUMENTAZIONE:
{context}

Cerca:
1. Valori di laboratorio fuori range (normale, alto, basso)
2. Trend preoccupanti o peggioramenti
3. Inconsistenze tra diverse documentazioni
4. Dati strani o contradditori

Per ogni anomalia fornisci:
- Descrizione
- Perché è preoccupante (se lo è)
- Cosa consigliare

Formato: Lista numerata"""

        result = self.llm.generate(prompt, use_case="general")

        return result

    # ========================================================================
    # CAPABILITY 4: PREDIZIONI CLINICHE ⚠️
    # ========================================================================
    def predict_condition(self, patient_id, condition):
        """
        ANALIZZA RISCHIO di una condizione clinica

        ⚠️ DISCLAIMER IMPORTANTE:
        - Questa è ANALISI DI SUPPORTO, NON è diagnosi medica
        - Richiede SEMPRE revisione di un medico professionista
        - Non usare per decisioni cliniche dirette

        Esempio di uso corretto:
        risk = service.predict_condition("PAT001", "diabetic_complication")
        if risk.confidence > 0.7:
            # Suggerisci al medico di verificare
        """

        print(f"\n📊 Analizzando rischio di {condition} per paziente {patient_id}...")
        print(f"⚠️ DISCLAIMER: Questa NON è una diagnosi medica!")

        chunks = self.rag.retrieve(patient_id, f"fattori rischio {condition}", top_k=10)

        context = "\n\n".join([c["text"] for c in chunks])

        prompt = f"""⚠️ DISCLAIMER CRITICO:
Questa è ANALISI DI SUPPORTO DECISIONALE, NON è una diagnosi medica.
Richiede SEMPRE revisione medica professionale prima di qualsiasi azione.

Analizza il rischio di '{condition}' basandoti su:
{context}

Valuta:
1. Fattori di rischio presenti
2. Comorbidità (altre malattie)
3. Trend storici (migliora/peggiora/stabile)
4. Precedenti episodi simili

Fornisci:
1. Valutazione rischio: BASSO / MEDIO / ALTO / CRITICO
2. Percentuale di probabilità (0-100%)
3. Fattori principali che aumentano il rischio
4. Timeline (quanto tempo prima potrebbe accadere)
5. Cosa il medico dovrebbe monitorare

Ricorda: Questa è ANALISI, non DIAGNOSI!"""

        result = self.llm.generate(prompt, use_case="premium")

        # Aggiungi disclaimer al risultato
        full_result = f"""
⚠️ DISCLAIMER CRITICO:
Questa è analisi di supporto decisionale, NON è una diagnosi medica.
Richiede SEMPRE revisione medica professionale.

{result}

⚠️ Consultare sempre un medico professionista per decisioni cliniche.
"""

        return full_result