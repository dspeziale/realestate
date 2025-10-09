from flask import Flask, render_template, request, jsonify, session
from google import genai
from google.genai import types
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Configurazione
API_KEY = 'AIzaSyDKxn4lXHrcmELXCjP6xpG1jwGlf9BB_Zc'
client = genai.Client(api_key=API_KEY)

UPLOAD_FOLDER = 'uploads'
HISTORY_FOLDER = 'history'
SETTINGS_FILE = 'settings.json'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'csv'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Crea cartelle se non esistono
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(HISTORY_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def load_settings():
    """Carica le impostazioni dal file JSON"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {
        'api_key': API_KEY,
        'model': 'gemini-2.5-flash',
        'temperature': 0.1,
        'save_history': True,
        'dark_mode': False
    }


def save_settings(settings):
    """Salva le impostazioni nel file JSON"""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=4)


def save_conversation(prompt, response, files=[]):
    """Salva una conversazione nella cronologia"""
    settings = load_settings()
    if not settings.get('save_history', True):
        return

    timestamp = datetime.now()
    conversation = {
        'id': timestamp.strftime('%Y%m%d%H%M%S'),
        'timestamp': timestamp.isoformat(),
        'prompt': prompt,
        'response': response,
        'files': files
    }

    filename = os.path.join(HISTORY_FOLDER, f"{conversation['id']}.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(conversation, f, indent=4, ensure_ascii=False)


def load_conversations():
    """Carica tutte le conversazioni dalla cronologia"""
    conversations = []
    if os.path.exists(HISTORY_FOLDER):
        for filename in os.listdir(HISTORY_FOLDER):
            if filename.endswith('.json'):
                filepath = os.path.join(HISTORY_FOLDER, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    conversations.append(json.load(f))

    # Ordina per timestamp decrescente (più recenti prima)
    conversations.sort(key=lambda x: x['timestamp'], reverse=True)
    return conversations


def delete_conversation(conversation_id):
    """Elimina una conversazione dalla cronologia"""
    filename = os.path.join(HISTORY_FOLDER, f"{conversation_id}.json")
    if os.path.exists(filename):
        os.remove(filename)
        return True
    return False


def build_context_prompt(context_conversations):
    """Costruisce un prompt con il contesto dalle conversazioni precedenti"""
    if not context_conversations:
        return ""

    context_text = "\n\n=== CONTESTO DALLE CONVERSAZIONI PRECEDENTI ===\n"
    context_text += "Usa le seguenti conversazioni come contesto e memoria per comprendere meglio le richieste:\n\n"

    for i, conv in enumerate(context_conversations, 1):
        context_text += f"--- Conversazione {i} ---\n"
        context_text += f"UTENTE: {conv['prompt']}\n"
        context_text += f"ASSISTENTE: {conv['response']}\n\n"

    context_text += "=== FINE CONTESTO ===\n\n"
    context_text += "Ora rispondi alla seguente nuova richiesta tenendo conto del contesto sopra:\n\n"

    return context_text


# Routes
@app.route('/')
def index():
    return render_template('chat.html')


@app.route('/history')
def history():
    conversations = load_conversations()
    return render_template('history.html', conversations=conversations)


@app.route('/history/delete/<conversation_id>', methods=['DELETE'])
def delete_history(conversation_id):
    try:
        if delete_conversation(conversation_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Conversazione non trovata'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/history/delete-all', methods=['DELETE'])
def delete_all_history():
    try:
        deleted_count = 0
        if os.path.exists(HISTORY_FOLDER):
            for filename in os.listdir(HISTORY_FOLDER):
                if filename.endswith('.json'):
                    filepath = os.path.join(HISTORY_FOLDER, filename)
                    os.remove(filepath)
                    deleted_count += 1

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'{deleted_count} conversazioni eliminate'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/settings')
def settings():
    settings_data = load_settings()
    return render_template('settings.html',
                           settings=settings_data,
                           history_folder=os.path.abspath(HISTORY_FOLDER),
                           settings_file=os.path.abspath(SETTINGS_FILE))


@app.route('/settings/save', methods=['POST'])
def save_settings_route():
    try:
        settings_data = request.get_json()
        save_settings(settings_data)

        # Aggiorna client con nuova API key se cambiata
        global client
        if settings_data.get('api_key'):
            client = genai.Client(api_key=settings_data['api_key'])

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/settings/reset', methods=['POST'])
def reset_settings():
    try:
        default_settings = {
            'api_key': API_KEY,
            'model': 'gemini-2.5-flash',
            'temperature': 0.1,
            'save_history': True,
            'dark_mode': False
        }
        save_settings(default_settings)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/generate', methods=['POST'])
def generate():
    try:
        user_prompt = request.form.get('prompt', '')

        if not user_prompt:
            return jsonify({'success': False, 'error': 'Prompt vuoto'})

        # Carica impostazioni
        settings = load_settings()

        # Gestione contesto
        context_data = request.form.get('context', '')
        context_prompt = ""

        if context_data:
            try:
                context_conversations = json.loads(context_data)
                context_prompt = build_context_prompt(context_conversations)
            except:
                pass

        # Gestione file
        uploaded_files = request.files.getlist('files')
        file_parts = []
        file_names = []

        for file in uploaded_files:
            if file and file.filename:
                if not allowed_file(file.filename):
                    return jsonify({'success': False, 'error': f'Tipo di file non supportato: {file.filename}'})

                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                file_names.append(filename)

                try:
                    current_client = genai.Client(api_key=settings.get('api_key', API_KEY))
                    uploaded_file = current_client.files.upload(file=filepath)
                    file_parts.append(uploaded_file)
                    os.remove(filepath)
                except Exception as e:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    return jsonify({'success': False, 'error': f'Errore upload file: {str(e)}'})

        # Prepara contenuto per Gemini
        contents = []
        for file_part in file_parts:
            contents.append(file_part)

        # Combina contesto + prompt utente
        print(context_prompt)
        print(user_prompt)
        full_prompt = context_prompt + user_prompt + ". Dammi un testo senza formattazione"
        contents.append(full_prompt)

        # Usa il client con le impostazioni correnti
        current_client = genai.Client(api_key=settings.get('api_key', API_KEY))

        # Chiamata all'API Gemini
        response = current_client.models.generate_content(
            model=settings.get('model', 'gemini-2.5-flash'),
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=settings.get('temperature', 0.1),
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )

        # Salva nella cronologia se abilitato (salva solo il prompt originale, non il contesto)
        save_conversation(user_prompt, response.text, file_names)

        return jsonify({
            'success': True,
            'response': response.text
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)