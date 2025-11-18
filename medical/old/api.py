"""
API REST - FastAPI endpoints
Questo è il "telefono" per comunicare col sistema
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from pydantic import BaseModel
import os

# Import moduli nostri
from config import Config
from router import LLMRouter
from llm_interface import LLMInterface
from rag_system import RAGSystem
from medical_service import MedicalService

# ============================================================================
# SETUP
# ============================================================================

config = Config()
router = LLMRouter(config)
llm = LLMInterface(config, router)
rag = RAGSystem(config, llm)
medical = MedicalService(config, llm, rag)

app = FastAPI(
    title="🏥 Medical AI System",
    description="Sistema expert medico con OLLAMA + Cloud LLM"
)

security = HTTPBearer()


# ============================================================================
# REQUEST MODELS
# ============================================================================

class SummarizeRequest(BaseModel):
    patient_id: str


class QuestionRequest(BaseModel):
    patient_id: str
    question: str


class AnomalyRequest(BaseModel):
    patient_id: str


class PredictionRequest(BaseModel):
    patient_id: str
    condition: str


# ============================================================================
# UTILITIES
# ============================================================================

def verify_token(credentials: HTTPAuthCredentials):
    """Verifica API token"""
    if credentials.credentials != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Token non valido")
    return credentials.credentials


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Controlla se il sistema è online"""

    # Verifica OLLAMA
    ollama_online = router._ollama_online()

    # Verifica provider cloud
    providers = []
    if ollama_online:
        providers.append("ollama")
    if config.CLAUDE_ENABLED:
        providers.append("claude")
    if config.GEMINI_ENABLED:
        providers.append("gemini")
    if config.OPENAI_ENABLED:
        providers.append("openai")

    return {
        "status": "🟢 ONLINE" if providers else "🔴 OFFLINE",
        "ollama_online": ollama_online,
        "providers": providers,
        "routing_strategy": config.ROUTING_STRATEGY
    }


# ============================================================================
# UPLOAD DOCUMENTI
# ============================================================================

@app.post("/upload-document")
async def upload_document(
        patient_id: str,
        file: UploadFile = File(...),
        credentials: HTTPAuthCredentials = Depends(security)
):
    """Carica un documento medico per un paziente"""

    verify_token(credentials)

    try:
        # Leggi file
        content = await file.read()
        text = content.decode('utf-8')

        # Ingesta nel RAG
        rag.ingest_documents(patient_id, [text])

        return {
            "status": "✅ Documento caricato",
            "patient_id": patient_id,
            "filename": file.filename
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CAPABILITY 1: RIASSUNTO
# ============================================================================

@app.post("/summarize")
async def summarize(
        request: SummarizeRequest,
        credentials: HTTPAuthCredentials = Depends(security)
):
    """
    Riassume la storia medica di un paziente

    Risponde a:
    - Quali diagnosi ha?
    - Quali allergie?
    - Quali farmaci?
    - Ha avuto interventi?
    """

    verify_token(credentials)

    try:
        result = medical.summarize_patient(request.patient_id)
        return {"patient_id": request.patient_id, "summary": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CAPABILITY 2: DOMANDE
# ============================================================================

@app.post("/ask-question")
async def ask_question(
        request: QuestionRequest,
        credentials: HTTPAuthCredentials = Depends(security)
):
    """
    Risponde a domande specifiche sulla documentazione

    Esempi:
    - "Quali allergie ha?"
    - "Prende insulina?"
    - "Ha il diabete?"
    """

    verify_token(credentials)

    try:
        result = medical.ask_question(request.patient_id, request.question)
        return {
            "patient_id": request.patient_id,
            "question": request.question,
            "answer": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CAPABILITY 3: ANOMALIE
# ============================================================================

@app.post("/find-anomalies")
async def find_anomalies(
        request: AnomalyRequest,
        credentials: HTTPAuthCredentials = Depends(security)
):
    """
    Identifica anomalie e valori strani nei dati medici

    Cerca:
    - Valori fuori range
    - Trend preoccupanti
    - Inconsistenze
    """

    verify_token(credentials)

    try:
        result = medical.find_anomalies(request.patient_id)
        return {
            "patient_id": request.patient_id,
            "anomalies": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CAPABILITY 4: PREDIZIONI
# ============================================================================

@app.post("/predict-condition")
async def predict_condition(
        request: PredictionRequest,
        credentials: HTTPAuthCredentials = Depends(security)
):
    """
    ⚠️ Analizza RISCHIO di una condizione (NON è diagnosi)

    Esempio:
    - condition: "diabetic_complication"
    - condition: "heart_disease"
    - condition: "kidney_disease"
    """

    verify_token(credentials)

    try:
        result = medical.predict_condition(request.patient_id, request.condition)
        return {
            "patient_id": request.patient_id,
            "condition": request.condition,
            "analysis": result,
            "disclaimer": "⚠️ Questa NON è una diagnosi medica"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STATS
# ============================================================================

@app.get("/stats")
async def get_stats(credentials: HTTPAuthCredentials = Depends(security)):
    """Mostra statistiche di utilizzo"""

    verify_token(credentials)

    return {
        "routing_strategy": config.ROUTING_STRATEGY,
        "monthly_cost": f"${router.monthly_cost:.2f}",
        "max_budget": f"${config.MAX_MONTHLY_COST}",
        "ollama_enabled": config.OLLAMA_ENABLED,
        "claude_enabled": config.CLAUDE_ENABLED,
        "rag_patients": len(rag.vector_stores)
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("""
    ╔════════════════════════════════════════════════╗
    ║     🏥 MEDICAL AI SYSTEM - API SERVER         ║
    ║                                                ║
    ║  http://localhost:8000                         ║
    ║  Docs: http://localhost:8000/docs              ║
    ╚════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000
    )