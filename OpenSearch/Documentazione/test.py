"""
Debug script per capire cosa c'è nel markdown
"""

import os
from pathlib import Path

md_file = 'ai_soc_stack_guide.md'

if not Path(md_file).exists():
    print(f"❌ File non trovato: {md_file}")
    exit(1)

with open(md_file, 'r', encoding='utf-8') as f:
    content = f.read()

print("=" * 70)
print("DEBUG MARKDOWN")
print("=" * 70)

print(f"\n📄 File: {md_file}")
print(f"📊 Dimensione: {len(content)} caratteri")
print(f"📝 Righe totali: {len(content.split(chr(10)))}")

# Cerca i backtick
backtick_count = content.count('```')
print(f"\n🔍 Backtick (```): {backtick_count} trovati")

if backtick_count == 0:
    print("   ❌ NESSUN BACKTICK TROVATO!")
    print("   Potrebbe esserci un encoding issue...")

    # Prova altri possibili backtick
    if '´´´' in content:
        print("   ⚠️  Trovati: ´´´ (accenti acuti)")
    if '```' in content:
        print("   ⚠️  Trovati: ``` (veri backtick)")
    if '‛‛‛' in content:
        print("   ⚠️  Trovati: ‛‛‛ (apostrofi modificati)")

# Traccia i blocchi di codice
print("\n" + "=" * 70)
print("BLOCCHI DI CODICE TROVATI")
print("=" * 70)

lines = content.split('\n')
in_code = False
code_block_num = 0
code_start_line = 0

for line_num, line in enumerate(lines, 1):

    # Cerca apertura/chiusura blocco codice
    if '```' in line:
        if not in_code:
            in_code = True
            code_block_num += 1
            code_start_line = line_num
            language = line.replace('```', '').strip()
            print(f"\n📍 BLOCCO #{code_block_num}")
            print(f"   Linea: {line_num}")
            print(f"   Linguaggio: '{language}' (len={len(language)})")
            print(f"   Contenuto linea: {repr(line)}")
        else:
            in_code = False
            lines_in_block = line_num - code_start_line - 1
            print(f"   Chiusura: linea {line_num}")
            print(f"   Righe codice: {lines_in_block}")
            print(f"   Contenuto linea: {repr(line)}")

# Estrai i contenuti dei blocchi
print("\n" + "=" * 70)
print("CONTENUTO DEI BLOCCHI")
print("=" * 70)

blocks = content.split('```')
if len(blocks) > 1:
    for idx in range(1, len(blocks), 2):
        if idx < len(blocks):
            code_content = blocks[idx]
            lines_in_block = code_content.count('\n')
            first_100_chars = code_content[:100].replace('\n', '\\n')

            print(f"\n🔹 BLOCCO {(idx + 1) // 2}:")
            print(f"   Righe: {lines_in_block}")
            print(f"   Prime 100 caratteri: {repr(first_100_chars)}")

            # Se contiene "Isolation Forest", è il blocco Python!
            if 'IsolationForest' in code_content:
                print("   ✅ TROVATO IL BLOCCO PYTHON CON IsolationForest!")
                print(f"   Lunghezza totale: {len(code_content)} caratteri")

print("\n" + "=" * 70)
print("RIEPILOGO")
print("=" * 70)

if backtick_count >= 2:
    print(f"✅ Trovati {backtick_count // 2} blocchi di codice")
    print("✓ Il markdown dovrebbe avere codice")
else:
    print("❌ Nessun blocco di codice trovato!")
    print("\n💡 SOLUZIONI:")
    print("   1. Il file markdown potrebbe avere codifica sbagliata")
    print("   2. I backtick potrebbero essere sostituiti con caratteri simili")
    print("   3. Riprova a copiare il contenuto da zero")