"""
MEDICAL AI SYSTEM - CONFIGURAZIONE CENTRALIZZATA
Questo file configura TUTTO il sistema
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# PROVIDER LLM DISPONIBILI
# ============================================================================

class Config:
    """Configurazione master del sistema"""

    # OLLAMA (locale, privacy, gratis)
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_ENABLED = True
    #OLLAMA_MODEL = "llama2:13b"
    OLLAMA_MODEL = "gpt-oss:120b-cloud"
    OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"

    # Claude (Anthropic - miglior per medical)
    CLAUDE_ENABLED = True
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
    CLAUDE_MODEL = "claude-3-5-sonnet-20241022"

    # Gemini (Google - optional)
    GEMINI_ENABLED = False
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-2.0-flash-001"

    # OpenAI (GPT - fallback)
    OPENAI_ENABLED = False
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = "gpt-4-turbo"

    # ============================================================================
    # STRATEGIE ROUTING
    # ============================================================================

    ROUTING_STRATEGY = os.getenv("ROUTING_STRATEGY", "auto")
    # Opzioni: "auto", "cost", "speed", "privacy", "quality"

    # ============================================================================
    # COST MANAGEMENT
    # ============================================================================

    MAX_MONTHLY_COST = float(os.getenv("MAX_MONTHLY_COST", "1000"))
    ENABLE_COST_TRACKING = True

    # ============================================================================
    # SECURITY
    # ============================================================================

    API_TOKEN = os.getenv("API_TOKEN", "test-token")
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    # ============================================================================
    # DATABASE
    # ============================================================================

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///./medical_ai.db"
    )

    # ============================================================================
    # STORAGE
    # ============================================================================

    VECTOR_STORE_PATH = "/data/vector_stores"
    DOCUMENT_STORAGE_PATH = "/data/documents"

    # ============================================================================
    # RAG PARAMETERS
    # ============================================================================

    CHUNK_SIZE = 1500
    CHUNK_OVERLAP = 150
    TOP_K_RETRIEVAL = 5