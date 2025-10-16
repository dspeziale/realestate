import requests
import json
from typing import List, Dict
from datetime import datetime


class OllamaChat:
    """Client completo per chat interattiva con Ollama"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = None):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.conversation_history: List[Dict] = []

        # Se non specificato, usa il primo modello disponibile
        if model is None:
            models = self._get_available_models()
            if models:
                self.model = models[0]
                print(f"🤖 Modello selezionato automaticamente: {self.model}\n")
            else:
                raise Exception("Nessun modello disponibile!")
        else:
            self.model = model

    def _get_available_models(self) -> List[str]:
        """Ottiene la lista dei modelli disponibili"""
        try:
            response = requests.get(f"{self.api_url}/tags")
            models = response.json().get('models', [])
            return [m['name'] for m in models]
        except:
            return []

    def chat(self, message: str, stream: bool = True) -> str:
        """Invia un messaggio e riceve la risposta"""
        # Aggiungi messaggio utente
        self.conversation_history.append({
            "role": "user",
            "content": message
        })

        url = f"{self.api_url}/chat"
        payload = {
            "model": self.model,
            "messages": self.conversation_history,
            "stream": stream
        }

        try:
            response = requests.post(url, json=payload, stream=stream, timeout=120)

            if stream:
                full_response = ""

                for line in response.iter_lines():
                    if line:
                        json_response = json.loads(line)

                        if 'message' in json_response:
                            chunk = json_response['message'].get('content', '')
                            if chunk:
                                print(chunk, end='', flush=True)
                                full_response += chunk

                print()  # Nuova linea alla fine

                # Aggiungi risposta assistente
                self.conversation_history.append({
                    "role": "assistant",
                    "content": full_response
                })

                return full_response
            else:
                result = response.json()
                assistant_response = result.get('message', {}).get('content', '')

                self.conversation_history.append({
                    "role": "assistant",
                    "content": assistant_response
                })

                print(assistant_response)
                return assistant_response

        except Exception as e:
            print(f"\n❌ Errore: {str(e)}")
            return ""

    def clear_history(self):
        """Pulisce la cronologia"""
        self.conversation_history = []
        print("✅ Cronologia pulita\n")

    def set_system_prompt(self, system_message: str):
        """Imposta un prompt di sistema"""
        # Rimuovi eventuali system prompt precedenti
        self.conversation_history = [
            msg for msg in self.conversation_history
            if msg['role'] != 'system'
        ]

        # Aggiungi il nuovo system prompt all'inizio
        self.conversation_history.insert(0, {
            "role": "system",
            "content": system_message
        })
        print(f"✅ System prompt impostato: {system_message[:50]}...\n")

    def show_history(self):
        """Mostra la cronologia"""
        print("\n" + "=" * 70)
        print("📜 CRONOLOGIA CONVERSAZIONE")
        print("=" * 70 + "\n")

        for i, msg in enumerate(self.conversation_history, 1):
            role = msg['role'].upper()
            content = msg['content']

            if role == "SYSTEM":
                print(f"⚙️  [{role}]: {content}\n")
            elif role == "USER":
                print(f"👤 [{role}]: {content}\n")
            else:
                # Tronca risposte lunghe
                display_content = content[:200] + "..." if len(content) > 200 else content
                print(f"🤖 [{role}]: {display_content}\n")

        print("=" * 70 + "\n")

    def save_conversation(self, filename: str = None):
        """Salva la conversazione"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"chat_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.conversation_history, f, indent=2, ensure_ascii=False)

        print(f"✅ Conversazione salvata in '{filename}'\n")
        return filename

    def load_conversation(self, filename: str):
        """Carica una conversazione"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            print(f"✅ Conversazione caricata da '{filename}'\n")
            return True
        except FileNotFoundError:
            print(f"❌ File '{filename}' non trovato\n")
            return False

    def change_model(self, model_name: str):
        """Cambia il modello in uso"""
        models = self._get_available_models()

        if model_name in models:
            self.model = model_name
            print(f"✅ Modello cambiato in: {model_name}\n")
            return True
        else:
            print(f"❌ Modello '{model_name}' non disponibile")
            print(f"   Modelli disponibili: {', '.join(models)}\n")
            return False

    def list_models(self):
        """Mostra i modelli disponibili"""
        models = self._get_available_models()

        print("\n📋 Modelli disponibili:")
        for i, model in enumerate(models, 1):
            current = " (IN USO)" if model == self.model else ""
            print(f"   {i}. {model}{current}")
        print()

        return models


def print_help():
    """Stampa l'aiuto"""
    print("\n" + "=" * 70)
    print("📖 COMANDI DISPONIBILI")
    print("=" * 70)
    print("""
  /help     - Mostra questo aiuto
  /clear    - Pulisce la cronologia della conversazione
  /history  - Mostra tutta la cronologia
  /save     - Salva la conversazione in un file JSON
  /load     - Carica una conversazione da file
  /system   - Imposta un system prompt personalizzato
  /models   - Mostra i modelli disponibili
  /change   - Cambia il modello in uso
  /exit     - Esci dalla chat (o premi Ctrl+C)

Scrivi normalmente per chattare con l'AI!
    """)
    print("=" * 70 + "\n")


def interactive_chat():
    """Modalità chat interattiva completa"""
    print("=" * 70)
    print("💬 CHAT INTERATTIVA CON OLLAMA")
    print("=" * 70)
    print("\nDigita /help per vedere i comandi disponibili")
    print("Digita /exit per uscire\n")

    try:
        # Inizializza la chat
        chat = OllamaChat()

        # Mostra modelli disponibili
        chat.list_models()

        # Chiedi se vuole impostare un system prompt
        print("Vuoi impostare un system prompt? (s/n, default=n): ", end='')
        if input().strip().lower() == 's':
            print("\nEsempi di system prompt:")
            print("  - Sei un assistente amichevole che risponde sempre in italiano")
            print("  - Sei un esperto di programmazione Python")
            print("  - Sei un tutor paziente che spiega concetti complessi in modo semplice")
            print("\nInserisci il tuo system prompt:")
            print("➤ ", end='')
            system_prompt = input()
            if system_prompt.strip():
                chat.set_system_prompt(system_prompt)

        print("=" * 70)
        print("✅ Chat avviata! Inizia a scrivere...")
        print("=" * 70 + "\n")

        # Loop principale
        while True:
            try:
                # Input utente
                user_input = input("👤 Tu: ").strip()

                if not user_input:
                    continue

                # Gestione comandi
                if user_input.startswith('/'):
                    command = user_input.lower().split()[0]

                    if command == '/exit':
                        # Chiedi se salvare prima di uscire
                        if len(chat.conversation_history) > 0:
                            print("\nVuoi salvare la conversazione prima di uscire? (s/n): ", end='')
                            if input().strip().lower() == 's':
                                filename = chat.save_conversation()
                                print(f"💾 Salvato in: {filename}")

                        print("\n👋 Arrivederci!\n")
                        break

                    elif command == '/help':
                        print_help()

                    elif command == '/clear':
                        chat.clear_history()

                    elif command == '/history':
                        chat.show_history()

                    elif command == '/save':
                        print("Nome file (premi INVIO per nome automatico): ", end='')
                        filename = input().strip()
                        chat.save_conversation(filename if filename else None)

                    elif command == '/load':
                        print("Nome file da caricare: ", end='')
                        filename = input().strip()
                        if filename:
                            chat.load_conversation(filename)

                    elif command == '/system':
                        print("Inserisci il system prompt:")
                        print("➤ ", end='')
                        system_prompt = input().strip()
                        if system_prompt:
                            chat.set_system_prompt(system_prompt)

                    elif command == '/models':
                        chat.list_models()

                    elif command == '/change':
                        models = chat.list_models()
                        print("Inserisci il numero o il nome del modello: ", end='')
                        choice = input().strip()

                        if choice.isdigit():
                            idx = int(choice) - 1
                            if 0 <= idx < len(models):
                                chat.change_model(models[idx])
                        else:
                            chat.change_model(choice)

                    else:
                        print(f"❌ Comando '{command}' non riconosciuto")
                        print("   Digita /help per vedere i comandi disponibili\n")

                    continue

                # Invia il messaggio all'AI
                print("\n🤖 Assistente: ", end='', flush=True)
                chat.chat(user_input, stream=True)
                print()  # Linea vuota dopo la risposta

            except KeyboardInterrupt:
                print("\n\n⚠️  Interruzione da tastiera")
                print("Vuoi uscire? (s/n): ", end='')
                if input().strip().lower() == 's':
                    print("\n👋 Arrivederci!\n")
                    break
                else:
                    print("Continua a chattare...\n")
                    continue

            except Exception as e:
                print(f"\n❌ Errore: {str(e)}\n")

    except Exception as e:
        print(f"\n❌ Errore nell'inizializzazione: {str(e)}")
        print("Assicurati che Ollama sia in esecuzione e che ci siano modelli installati\n")


if __name__ == "__main__":
    interactive_chat()