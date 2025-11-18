"""
ESEMPIO DI UTILIZZO - Come usare il sistema
"""

from config import Config
from router import LLMRouter
from llm_interface import LLMInterface
from rag_system import RAGSystem
from medical_service import MedicalService

# ============================================================================
# SETUP INIZIALE
# ============================================================================

print("🚀 Initializing Medical AI System...")

config = Config()
router = LLMRouter(config)
llm = LLMInterface(config, router)
rag = RAGSystem(config, llm)
medical = MedicalService(config, llm, rag)

print("✅ Sistema inizializzato\n")

# ============================================================================
# ESEMPIO 1: UPLOAD DOCUMENTI
# ============================================================================

print("=" * 60)
print("ESEMPIO 1: Upload documenti medici")
print("=" * 60)

# Simula un documento medico
documento_1 = """
REFERTI LABORATORIO - Data: 15/01/2024
Paziente: Mario Rossi

Esami effettuati:
- Glicemia: 145 mg/dL (normale: 70-100)
- Emoglobina glicata: 7.2% (normale: <5.7%)
- Colesterolo totale: 220 mg/dL (normale: <200)
- HDL: 35 mg/dL (normale: >40)
- LDL: 150 mg/dL (normale: <100)

Allergie documentate:
- Penicillina
- Arachidi

Diagnosi precedenti:
- Diabete tipo 2 dal 2018
- Ipertensione
- Dislipidemia

Farmaci attuali:
- Metformina 1000mg 2 volte al giorno
- Lisinopril 10mg 1 volta al giorno
- Atorvastatina 20mg 1 volta al giorno
"""

documento_2 = """
CARTELLA CLINICA - Data: 10/01/2024
Paziente: Mario Rossi

Visita cardiologica:
- Pressione: 145/92 mmHg (elevata)
- Frequenza cardiaca: 78 bpm (normale)
- ECG: ritmo sinusale regolare
- Ecocardiogramma: nessuna anomalia

Osservazioni:
Paziente con anamnesi di diabete e ipertensione.
Buona aderenza alla terapia.
Consigliato controllo stretto dei valori glicemici.
"""

# Upload documenti per paziente
print("\n📤 Caricando documenti per paziente PAT001...")
rag.ingest_documents("PAT001", [documento_1, documento_2])
print("✅ Documenti caricati\n")

# ============================================================================
# ESEMPIO 2: RIASSUNTO STORIA MEDICA
# ============================================================================

print("=" * 60)
print("ESEMPIO 2: Riassunto storia medica")
print("=" * 60)

summary = medical.summarize_patient("PAT001")
print(f"\n{summary}\n")

# ============================================================================
# ESEMPIO 3: RISPONDERE A DOMANDE
# ============================================================================

print("=" * 60)
print("ESEMPIO 3: Rispondere a domande specifiche")
print("=" * 60)

domande = [
    "Quali allergie ha il paziente?",
    "Prende metformina?",
    "Qual è la pressione del paziente?",
    "Ha il diabete?"
]

for domanda in domande:
    print(f"\n❓ Domanda: {domanda}")
    risposta = medical.ask_question("PAT001", domanda)
    print(f"📝 Risposta: {risposta}\n")

# ============================================================================
# ESEMPIO 4: IDENTIFICARE ANOMALIE
# ============================================================================

print("=" * 60)
print("ESEMPIO 4: Identificare anomalie")
print("=" * 60)

anomalie = medical.find_anomalies("PAT001")
print(f"\n{anomalie}\n")

# ============================================================================
# ESEMPIO 5: PREDIZIONI CLINICHE
# ==========================================================================

print("=" * 60)
print("ESEMPIO 5: Analizzare rischio di complicazioni")
print("=" * 60)

condizioni = [
    "diabetic_complication",
    "heart_disease",
    "kidney_disease"
]

for condizione in condizioni:
    print(f"\n📊 Analizzando rischio: {condizione}")
    prediction = medical.predict_condition("PAT001", condizione)
    print(f"{prediction}\n")

# ============================================================================
# ESEMPIO 6: ROUTING INTELLIGENTE
# ============================================================================

print("=" * 60)
print("ESEMPIO 6: Routing intelligente")
print("=" * 60)

print("\n🧠 Provider selezionato per diverse use case:\n")

for use_case in ["fast", "general", "embedding", "premium"]:
    provider = router.select_provider(use_case)
    print(f"  Use case '{use_case}' → {provider.upper()}")

# ============================================================================
# STATISTICHE
# ============================================================================

print("\n" + "=" * 60)
print("STATISTICHE")
print("=" * 60)

print(f"\n💰 Costo mese corrente: ${router.monthly_cost:.2f}")
print(f"💰 Budget massimo: ${config.MAX_MONTHLY_COST}")
print(f"🎯 Strategia routing: {config.ROUTING_STRATEGY}")
print(f"🏢 Pazienti indexati: {len(rag.vector_stores)}")

print("\n" + "=" * 60)
print("✅ ESEMPIO COMPLETATO")
print("=" * 60)