# chat.py - Google Gemini AI Sample
# Copyright 2025 TIM SPA
# Author
# Python 3.13 Compatible

from flask import Flask, render_template, request, jsonify, session
from google import genai
from google.genai import types
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-change-this-in-production')

# Configurazione da variabili d'ambiente
API_KEY = os.getenv('GOOGLE_API_KEY')
if not API_KEY:
    raise ValueError("GOOGLE_API_KEY non trovata nel file .env")

client = genai.Client(api_key=API_KEY)

UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
HISTORY_FOLDER = os.getenv('HISTORY_FOLDER', 'history')
KNOWLEDGE_BASE_FOLDER = os.getenv('KNOWLEDGE_BASE_FOLDER', 'knowledge_base')
SETTINGS_FILE = 'settings.json'
CATEGORIES_FILE = 'categories.json'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'csv'}
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE_MB', '10')) * 1024 * 1024

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Crea cartelle se non esistono
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(HISTORY_FOLDER, exist_ok=True)
os.makedirs(KNOWLEDGE_BASE_FOLDER, exist_ok=True)


def load_categories():
    """Carica le categorie dal file JSON"""
    if os.path.exists(CATEGORIES_FILE):
        with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    # Categorie di default se il file non esiste
    # return {
    #     "categories": [
    #         {"id": "generale", "name": "Generale", "description": "Conoscenze generali", "color": "secondary"},
    #         {"id": "medico", "name": "Medico", "description": "Informazioni mediche", "color": "danger"},
    #         {"id": "tecnico", "name": "Tecnico", "description": "Documentazione tecnica", "color": "primary"},
    #         {"id": "business", "name": "Business", "description": "Procedure aziendali", "color": "success"},
    #         {"id": "altro", "name": "Altro", "description": "Altre categorie", "color": "dark"}
    #     ]
    # }


def save_categories(categories_data):
    """Salva le categorie nel file JSON"""
    with open(CATEGORIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(categories_data, f, indent=2, ensure_ascii=False)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def load_settings():
    """Carica le impostazioni dal file JSON"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            # Usa sempre la API key dal .env se disponibile
            if API_KEY:
                settings['api_key'] = API_KEY
            return settings
    return {
        'api_key': API_KEY,
        'model': 'gemini-2.5-flash',
        'temperature': 0.1,
        'save_history': True,
        'dark_mode': False
    }


def save_settings(settings):
    """Salva le impostazioni nel file JSON (esclusa API key)"""
    # Non salvare l'API key nel file settings.json
    settings_to_save = settings.copy()
    if 'api_key' in settings_to_save:
        del settings_to_save['api_key']

    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings_to_save, f, indent=4)


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

    conversations.sort(key=lambda x: x['timestamp'], reverse=True)
    return conversations


def delete_conversation(conversation_id):
    """Elimina una conversazione dalla cronologia"""
    filename = os.path.join(HISTORY_FOLDER, f"{conversation_id}.json")
    if os.path.exists(filename):
        os.remove(filename)
        return True
    return False


# ============================================
# FUNZIONI PER KNOWLEDGE BASE
# ============================================

def load_knowledge_base_files():
    """Carica tutti i file della knowledge base"""
    kb_files = []
    if os.path.exists(KNOWLEDGE_BASE_FOLDER):
        for filename in os.listdir(KNOWLEDGE_BASE_FOLDER):
            if filename.endswith('.json'):
                filepath = os.path.join(KNOWLEDGE_BASE_FOLDER, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    kb_files.append(json.load(f))

    kb_files.sort(key=lambda x: x['created_at'], reverse=True)
    return kb_files


def save_knowledge_base_file(name, description, content, category='generale'):
    """Salva un nuovo file nella knowledge base"""
    timestamp = datetime.now()
    kb_file = {
        'id': timestamp.strftime('%Y%m%d%H%M%S'),
        'name': name,
        'description': description,
        'content': content,
        'category': category,
        'created_at': timestamp.isoformat(),
        'updated_at': timestamp.isoformat()
    }

    filename = os.path.join(KNOWLEDGE_BASE_FOLDER, f"{kb_file['id']}.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(kb_file, f, indent=4, ensure_ascii=False)

    return kb_file['id']


def update_knowledge_base_file(kb_id, name, description, content, category):
    """Aggiorna un file esistente nella knowledge base"""
    filename = os.path.join(KNOWLEDGE_BASE_FOLDER, f"{kb_id}.json")

    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            kb_file = json.load(f)

        kb_file['name'] = name
        kb_file['description'] = description
        kb_file['content'] = content
        kb_file['category'] = category
        kb_file['updated_at'] = datetime.now().isoformat()

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(kb_file, f, indent=4, ensure_ascii=False)

        return True
    return False


def delete_knowledge_base_file(kb_id):
    """Elimina un file dalla knowledge base"""
    filename = os.path.join(KNOWLEDGE_BASE_FOLDER, f"{kb_id}.json")
    if os.path.exists(filename):
        os.remove(filename)
        return True
    return False


def get_knowledge_base_file(kb_id):
    """Ottiene un singolo file dalla knowledge base"""
    filename = os.path.join(KNOWLEDGE_BASE_FOLDER, f"{kb_id}.json")
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def build_knowledge_context(kb_ids):
    """Costruisce il contesto dalle knowledge base selezionate"""
    if not kb_ids:
        return ""

    context_text = "\n\n=== ISTRUZIONI E CONTESTO DALLA KNOWLEDGE BASE ===\n"
    context_text += "Segui attentamente queste istruzioni e usa queste informazioni come base di conoscenza:\n\n"

    for kb_id in kb_ids:
        kb_file = get_knowledge_base_file(kb_id)
        if kb_file:
            context_text += f"--- {kb_file['name']} ---\n"
            context_text += f"Categoria: {kb_file['category']}\n"
            context_text += f"Descrizione: {kb_file['description']}\n\n"
            context_text += f"{kb_file['content']}\n\n"

    context_text += "=== FINE KNOWLEDGE BASE ===\n\n"
    context_text += "Ora rispondi alla seguente richiesta applicando le istruzioni sopra:\n\n"

    return context_text


def build_context_prompt(context_conversations):
    """Costruisce un prompt con il contesto dalle conversazioni precedenti"""
    if not context_conversations:
        return ""

    context_text = "\n\n=== CONTESTO DALLE CONVERSAZIONI PRECEDENTI ===\n"
    context_text += "Usa le seguenti conversazioni come contesto e memoria:\n\n"

    for i, conv in enumerate(context_conversations, 1):
        context_text += f"--- Conversazione {i} ---\n"
        context_text += f"UTENTE: {conv['prompt']}\n"
        context_text += f"ASSISTENTE: {conv['response']}\n\n"

    context_text += "=== FINE CONTESTO ===\n\n"

    return context_text


# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    kb_files = load_knowledge_base_files()
    categories = load_categories()
    return render_template('chat.html', kb_files=kb_files, categories=categories)


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
    # Maschera l'API key per la visualizzazione
    if 'api_key' in settings_data and settings_data['api_key']:
        settings_data['api_key'] = '**********' + settings_data['api_key'][-4:]

    return render_template('settings.html',
                           settings=settings_data,
                           history_folder=os.path.abspath(HISTORY_FOLDER),
                           settings_file=os.path.abspath(SETTINGS_FILE))


@app.route('/settings/save', methods=['POST'])
def save_settings_route():
    try:
        settings_data = request.get_json()

        # Non permettere di modificare l'API key (viene dal .env)
        if 'api_key' in settings_data:
            del settings_data['api_key']

        save_settings(settings_data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/settings/reset', methods=['POST'])
def reset_settings():
    try:
        default_settings = {
            'model': 'gemini-2.5-flash',
            'temperature': 0.1,
            'save_history': True,
            'dark_mode': False
        }
        save_settings(default_settings)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================
# ROUTES PER KNOWLEDGE BASE
# ============================================

@app.route('/knowledge-base')
def knowledge_base():
    """Pagina di gestione della knowledge base"""
    kb_files = load_knowledge_base_files()
    categories = load_categories()
    return render_template('knowledge_base.html', kb_files=kb_files, categories=categories)


@app.route('/knowledge-base/create', methods=['POST'])
def create_knowledge_base():
    """Crea un nuovo file nella knowledge base"""
    try:
        data = request.get_json()

        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        content = data.get('content', '').strip()
        category = data.get('category', 'generale')

        if not name or not content:
            return jsonify({'success': False, 'error': 'Nome e contenuto sono obbligatori'})

        kb_id = save_knowledge_base_file(name, description, content, category)

        return jsonify({
            'success': True,
            'id': kb_id,
            'message': 'Knowledge base creata con successo'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/knowledge-base/update/<kb_id>', methods=['PUT'])
def update_knowledge_base(kb_id):
    """Aggiorna un file esistente nella knowledge base"""
    try:
        data = request.get_json()

        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        content = data.get('content', '').strip()
        category = data.get('category', 'generale')

        if not name or not content:
            return jsonify({'success': False, 'error': 'Nome e contenuto sono obbligatori'})

        if update_knowledge_base_file(kb_id, name, description, content, category):
            return jsonify({'success': True, 'message': 'Knowledge base aggiornata'})
        else:
            return jsonify({'success': False, 'error': 'File non trovato'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/knowledge-base/delete/<kb_id>', methods=['DELETE'])
def delete_knowledge_base(kb_id):
    """Elimina un file dalla knowledge base"""
    try:
        if delete_knowledge_base_file(kb_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'File non trovato'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/knowledge-base/get/<kb_id>', methods=['GET'])
def get_knowledge_base(kb_id):
    """Ottiene i dettagli di un file dalla knowledge base"""
    try:
        kb_file = get_knowledge_base_file(kb_id)
        if kb_file:
            return jsonify({'success': True, 'data': kb_file})
        else:
            return jsonify({'success': False, 'error': 'File non trovato'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/knowledge-base/upload-file', methods=['POST'])
def upload_knowledge_file():
    """Upload di un file di testo da aggiungere alla knowledge base"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Nessun file caricato'})

        file = request.files['file']
        name = request.form.get('name', '')
        description = request.form.get('description', '')
        category = request.form.get('category', 'generale')

        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nome file vuoto'})

        # Leggi il contenuto del file
        content = file.read().decode('utf-8')

        # Usa il nome del file se non specificato
        if not name:
            name = os.path.splitext(file.filename)[0]

        kb_id = save_knowledge_base_file(name, description, content, category)

        return jsonify({
            'success': True,
            'id': kb_id,
            'message': f'File "{file.filename}" caricato con successo'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================
# ROUTES PER GESTIONE CATEGORIE
# ============================================

@app.route('/categories', methods=['GET'])
def get_categories():
    """Ottiene tutte le categorie"""
    try:
        categories = load_categories()
        return jsonify({'success': True, 'data': categories})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/categories/save', methods=['POST'])
def save_categories_route():
    """Salva le categorie modificate"""
    try:
        categories_data = request.get_json()
        save_categories(categories_data)
        return jsonify({'success': True, 'message': 'Categorie salvate con successo'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/categories/reset', methods=['POST'])
def reset_categories():
    """Ripristina le categorie di default"""
    try:
        default_categories = {
            "categories": [
                {"id": "generale", "name": "Generale", "description": "Conoscenze generali", "color": "secondary"},
                {"id": "medico", "name": "Medico", "description": "Informazioni mediche", "color": "danger"},
                {"id": "tecnico", "name": "Tecnico", "description": "Documentazione tecnica", "color": "primary"},
                {"id": "business", "name": "Business", "description": "Procedure aziendali", "color": "success"},
                {"id": "altro", "name": "Altro", "description": "Altre categorie", "color": "dark"}
            ]
        }
        save_categories(default_categories)
        return jsonify({'success': True, 'message': 'Categorie ripristinate'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# ============================================
# ROUTE GENERATE
# ============================================

@app.route('/generate', methods=['POST'])
def generate():
    try:
        user_prompt = request.form.get('prompt', '')

        if not user_prompt:
            return jsonify({'success': False, 'error': 'Prompt vuoto'})

        settings = load_settings()

        # Gestione Knowledge Base
        kb_data = request.form.get('knowledge_base', '')
        kb_context = ""

        if kb_data:
            try:
                kb_ids = json.loads(kb_data)
                kb_context = build_knowledge_context(kb_ids)
            except:
                pass

        # Gestione contesto conversazioni
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
                    current_client = genai.Client(api_key=settings.get('api_key'))
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

        # Combina: Knowledge Base + Contesto conversazioni + Prompt utente
        full_prompt = kb_context + context_prompt + user_prompt + ". Dammi un testo senza formattazione"
        contents.append(full_prompt)

        current_client = genai.Client(api_key=settings.get('api_key'))

        # Chiamata all'API Gemini
        response = current_client.models.generate_content(
            model=settings.get('model', 'gemini-2.5-flash'),
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=settings.get('temperature', 0.1),
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )

        # Salva nella cronologia (salva solo il prompt originale)
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
    app.run(
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        host='0.0.0.0',
        port=5000
    )