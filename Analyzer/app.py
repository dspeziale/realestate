from llama_cpp import Llama

# Carica modello LLAMA localmente
model = Llama(model_path="path/a/llama_model.bin")

# Dati di esempio sul traffico da analizzare (esempio sintetico)
log_traffic = """
Pacchetto 1: IP sorgente 192.168.1.10, destinazione 8.8.8.8, protocollo TCP, porta 443
Pacchetto 2: IP sorgente 192.168.1.15, destinazione 192.168.1.20, protocollo UDP, porta 53
Pacchetto 3: IP sorgente 192.168.1.10, destinazione 10.0.0.5, protocollo ICMP
"""

# Prompt per chiedere a LLAMA un'analisi
prompt = f"Analizza questo traffico di rete e indica presenze sospette o anomalie:\n{log_traffic}"

# Genera la risposta dal modello
response = model(prompt, max_tokens=150)

print("Analisi traffico LLAMA:")
print(response['choices'][0]['text'])
