"""
ROUTER INTELLIGENTE - Sceglie quale provider usare
"""

import requests
import logging

logger = logging.getLogger(__name__)


class LLMRouter:
    """Sceglie automaticamente il miglior provider LLM"""

    def __init__(self, config):
        self.config = config
        self.monthly_cost = 0.0

    def select_provider(self, use_case="general"):
        """
        Seleziona il provider migliore

        use_case: "general", "fast", "embedding", "premium"
        """

        strategy = self.config.ROUTING_STRATEGY

        # ============================================================================
        # STRATEGIA: COST (minimizza spese)
        # ============================================================================
        if strategy == "cost":
            # OLLAMA è gratis!
            if self._ollama_online():
                logger.info("💰 COST mode: usando OLLAMA (gratis)")
                return "ollama"
            # Altrimenti cloud provider più economico
            if self.config.CLAUDE_ENABLED:
                return "claude"  # Più economico di Gemini

        # ============================================================================
        # STRATEGIA: SPEED (velocità massima)
        # ============================================================================
        elif strategy == "speed":
            # OLLAMA è locale = più veloce
            if self._ollama_online():
                logger.info("⚡ SPEED mode: usando OLLAMA (locale)")
                return "ollama"
            # Fallback: Cloud providers sono comunque veloci
            if self.config.CLAUDE_ENABLED:
                return "claude"

        # ============================================================================
        # STRATEGIA: PRIVACY (GDPR mode - OLLAMA ONLY)
        # ============================================================================
        elif strategy == "privacy":
            if self._ollama_online():
                logger.info("🔒 PRIVACY mode: OLLAMA (dati non escono dal server)")
                return "ollama"
            else:
                logger.error("❌ PRIVACY mode ma OLLAMA offline!")
                raise Exception("OLLAMA required per privacy mode")

        # ============================================================================
        # STRATEGIA: QUALITY (accuratezza massima)
        # ============================================================================
        elif strategy == "quality":
            # Claude è il migliore per medical
            if self.config.CLAUDE_ENABLED:
                logger.info("🎯 QUALITY mode: usando CLAUDE (migliore)")
                return "claude"
            if self.config.GEMINI_ENABLED:
                return "gemini"
            if self.config.OPENAI_ENABLED:
                return "openai"

        # ============================================================================
        # STRATEGIA: AUTO (default - intelligente)
        # ============================================================================
        else:  # auto
            # Se budget è quasi finito, usa OLLAMA (gratis)
            if self.monthly_cost > self.config.MAX_MONTHLY_COST * 0.9:
                logger.warning(f"⚠️ Budget quasi esaurito, usando OLLAMA")
                if self._ollama_online():
                    return "ollama"

            # Usa OLLAMA per query veloci
            if use_case in ["fast", "embedding"]:
                if self._ollama_online():
                    logger.info("📍 AUTO: query veloce → OLLAMA")
                    return "ollama"

            # Usa CLAUDE per analisi importanti
            if use_case in ["general", "premium"]:
                if self.config.CLAUDE_ENABLED:
                    logger.info("📍 AUTO: analisi importante → CLAUDE")
                    return "claude"

            # Fallback: primo disponibile
            if self._ollama_online():
                return "ollama"
            if self.config.CLAUDE_ENABLED:
                return "claude"
            if self.config.GEMINI_ENABLED:
                return "gemini"
            if self.config.OPENAI_ENABLED:
                return "openai"

        raise Exception("❌ Nessun provider disponibile!")

    def _ollama_online(self):
        """Verifica se OLLAMA è online"""
        try:
            response = requests.get(
                f"{self.config.OLLAMA_HOST}/api/tags",
                timeout=2
            )
            return response.status_code == 200
        except:
            return False

    def track_cost(self, provider, input_tokens, output_tokens):
        """Traccia i costi delle API"""

        costs = {
            "claude": {
                "input": 0.003,  # $ per 1000 tokens
                "output": 0.015
            },
            "gemini": {
                "input": 0.075,
                "output": 0.3
            },
            "openai": {
                "input": 0.01,
                "output": 0.03
            },
            "ollama": {
                "input": 0,
                "output": 0
            }
        }

        cost_info = costs.get(provider, {"input": 0, "output": 0})
        cost = (input_tokens / 1000) * cost_info["input"] + \
               (output_tokens / 1000) * cost_info["output"]

        self.monthly_cost += cost
        logger.info(f"💰 Costo: ${cost:.4f} (totale mese: ${self.monthly_cost:.2f})")

        return cost