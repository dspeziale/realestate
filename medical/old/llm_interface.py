"""
UNIFIED INTERFACE - Interfaccia unificata per TUTTI i provider LLM
Basta cambiare provider, il codice rimane uguale!
"""

import requests
import json
import anthropic
import google.generativeai as genai
from openai import OpenAI


class LLMInterface:
    """Interfaccia unificata per OLLAMA, Claude, Gemini, OpenAI"""

    def __init__(self, config, router):
        self.config = config
        self.router = router
        self.ollama_url = config.OLLAMA_HOST

        # Inizializza client cloud
        if config.CLAUDE_ENABLED and config.CLAUDE_API_KEY:
            self.claude_client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

        if config.GEMINI_ENABLED and config.GEMINI_API_KEY:
            genai.configure(api_key=config.GEMINI_API_KEY)

        if config.OPENAI_ENABLED and config.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=config.OPENAI_API_KEY)

    def generate(self, prompt, use_case="general", max_tokens=2048):
        """
        Genera testo usando il provider migliore

        Esempio:
            response = llm.generate("Riassumi questo documento", use_case="general")
        """

        # Seleziona provider automaticamente
        provider = self.router.select_provider(use_case)
        print(f"📝 Generando con {provider}...")

        # ============================================================================
        # OLLAMA (locale)
        # ============================================================================
        if provider == "ollama":
            return self._generate_ollama(prompt, max_tokens)

        # ============================================================================
        # CLAUDE (Anthropic)
        # ============================================================================
        elif provider == "claude":
            return self._generate_claude(prompt, max_tokens)

        # ============================================================================
        # GEMINI (Google)
        # ============================================================================
        elif provider == "gemini":
            return self._generate_gemini(prompt, max_tokens)

        # ============================================================================
        # OPENAI (GPT)
        # ============================================================================
        elif provider == "openai":
            return self._generate_openai(prompt, max_tokens)

    # ========================================================================
    # OLLAMA - Modelli locali
    # ========================================================================
    def _generate_ollama(self, prompt, max_tokens):
        """Chiama OLLAMA localmente"""
        try:
            payload = {
                "model": self.config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.1,  # Basso per medical
                }
            }

            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=300
            )
            response.raise_for_status()

            # Costruisci risposta da stream
            result = ""
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    result += data.get("response", "")

            return result.strip()

        except Exception as e:
            print(f"❌ Errore OLLAMA: {e}")
            raise

    # ========================================================================
    # CLAUDE - Anthropic API
    # ========================================================================
    def _generate_claude(self, prompt, max_tokens):
        """Chiama Claude API"""
        try:
            response = self.claude_client.messages.create(
                model=self.config.CLAUDE_MODEL,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text

        except Exception as e:
            print(f"❌ Errore Claude: {e}")
            raise

    # ========================================================================
    # GEMINI - Google API
    # ========================================================================
    def _generate_gemini(self, prompt, max_tokens):
        """Chiama Gemini API"""
        try:
            model = genai.GenerativeModel(self.config.GEMINI_MODEL)
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.1,
                )
            )
            return response.text

        except Exception as e:
            print(f"❌ Errore Gemini: {e}")
            raise

    # ========================================================================
    # OPENAI - GPT API
    # ========================================================================
    def _generate_openai(self, prompt, max_tokens):
        """Chiama OpenAI API"""
        try:
            response = self.openai_client.chat.completions.create(
                model=self.config.OPENAI_MODEL,
                max_tokens=max_tokens,
                temperature=0.1,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"❌ Errore OpenAI: {e}")
            raise

    # ========================================================================
    # EMBEDDINGS - Per RAG (vector search)
    # ========================================================================
    def embed(self, texts):
        """Crea embeddings per RAG"""

        if isinstance(texts, str):
            texts = [texts]

        # Usa OLLAMA per embeddings (locale)
        if self._ollama_online():
            return self._embed_ollama(texts)

        # Fallback: OpenAI
        if self.config.OPENAI_ENABLED:
            return self._embed_openai(texts)

        raise Exception("Nessun provider disponibile per embeddings")

    def _embed_ollama(self, texts):
        """Embeddings con OLLAMA"""
        embeddings = []
        for text in texts:
            payload = {
                "model": self.config.OLLAMA_EMBEDDING_MODEL,
                "prompt": text
            }
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json=payload
            )
            data = response.json()
            embeddings.append(data.get("embedding", []))
        return embeddings

    def _embed_openai(self, texts):
        """Embeddings con OpenAI"""
        embeddings = []
        for text in texts:
            response = self.openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            embeddings.append(response.data[0].embedding)
        return embeddings

    def _ollama_online(self):
        """Verifica se OLLAMA è online"""
        try:
            requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return True
        except:
            return False