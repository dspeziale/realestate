import os
import zipfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

# Configurazione
WATCH_DIR = "C:\logs"
EXTRACT_DIR = "C:\logs\extracted"

# Configurazione SMTP (Exchange on-premises)
SMTP_SERVER = "smtp.telecomitalia.it"  # Server Exchange interno
SMTP_PORT = 587  # Oppure 25 se non usa TLS
SMTP_USER = "X1090405@guest.telecomitalia.it"
SMTP_PASSWORD = "Capeds159!"
USE_TLS = True  # False se il server non richiede TLS


def extract_zip(zip_path, extract_to):
    """Estrae il contenuto di un file ZIP"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

        extracted_files = list(Path(extract_to).rglob('*'))
        file_count = len([f for f in extracted_files if f.is_file()])

        print(f"✓ Estratti {file_count} file in: {extract_to}")
        return True, file_count
    except Exception as e:
        print(f"✗ Errore nell'estrazione: {e}")
        return False, 0


def send_email_smtp(recipient, subject, body_html, attachment_paths=None):
    """Invia email tramite SMTP (Exchange on-premises)"""
    try:
        # Crea il messaggio
        msg = MIMEMultipart('alternative')
        msg['From'] = SMTP_USER
        msg['To'] = recipient
        msg['Subject'] = subject

        # Corpo HTML
        html_part = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(html_part)

        # Aggiungi allegati se specificati
        if attachment_paths:
            for file_path in attachment_paths:
                if os.path.exists(file_path):
                    with open(file_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename={os.path.basename(file_path)}'
                        )
                        msg.attach(part)

        # Connessione al server SMTP
        if USE_TLS:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)

        # Autenticazione
        server.login(SMTP_USER, SMTP_PASSWORD)

        # Invio
        server.send_message(msg)
        server.quit()

        print(f"✓ Email inviata a: {recipient}")
        return True

    except Exception as e:
        print(f"✗ Errore nell'invio email: {e}")
        return False


def process_zip_files():
    """Processa tutti i file ZIP nella directory"""
    watch_path = Path(WATCH_DIR)

    # Verifica che la directory esista
    if not watch_path.exists():
        print(f"✗ Directory non trovata: {WATCH_DIR}")
        return

    # Trova tutti i file ZIP
    zip_files = list(watch_path.glob("*.zip"))

    if not zip_files:
        print("ℹ Nessun file ZIP trovato")
        return

    print(f"Trovati {len(zip_files)} file ZIP da processare\n")

    for zip_file in zip_files:
        print(f"Processando: {zip_file.name}")

        # Crea directory di estrazione
        extract_path = Path(EXTRACT_DIR) / zip_file.stem
        extract_path.mkdir(parents=True, exist_ok=True)

        # Estrai il file
        success, file_count = extract_zip(str(zip_file), str(extract_path))

        if success:
            # Prepara lista file estratti (primi 10)
            extracted_files = list(extract_path.rglob('*'))
            file_list = [f.name for f in extracted_files if f.is_file()][:10]
            file_list_html = "<ul>" + "".join([f"<li>{f}</li>" for f in file_list]) + "</ul>"

            if len(file_list) < file_count:
                file_list_html += f"<p><em>... e altri {file_count - len(file_list)} file</em></p>"

            # Invia email di notifica
            body_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #0078d4;">File ZIP Processato</h2>
                <p>Il file <strong>{zip_file.name}</strong> è stato estratto con successo.</p>

                <table style="border-collapse: collapse; margin: 20px 0;">
                    <tr>
                        <td style="padding: 8px; background-color: #f3f2f1;"><strong>File ZIP:</strong></td>
                        <td style="padding: 8px;">{zip_file.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; background-color: #f3f2f1;"><strong>Dimensione:</strong></td>
                        <td style="padding: 8px;">{zip_file.stat().st_size / 1024:.2f} KB</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; background-color: #f3f2f1;"><strong>File estratti:</strong></td>
                        <td style="padding: 8px;">{file_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; background-color: #f3f2f1;"><strong>Percorso:</strong></td>
                        <td style="padding: 8px;">{extract_path}</td>
                    </tr>
                </table>

                <h3>File estratti (anteprima):</h3>
                {file_list_html}

                <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
                <p style="color: #666; font-size: 12px;">
                    Questo è un messaggio automatico generato dal sistema di automazione.
                </p>
            </body>
            </html>
            """

            send_email_smtp(
                recipient="dspeziale@gmail.com",
                subject=f"✓ File ZIP processato: {zip_file.name}",
                body_html=body_html
            )

            # Sposta il file ZIP in una cartella "processati"
            processed_dir = watch_path / "processed"
            processed_dir.mkdir(exist_ok=True)

            new_path = processed_dir / zip_file.name
            zip_file.rename(new_path)
            print(f"✓ File spostato in: {new_path}\n")
        else:
            print(f"✗ Elaborazione fallita per: {zip_file.name}\n")


def main():
    """Funzione principale"""
    print("=" * 60)
    print("AUTOMAZIONE ESTRAZIONE ZIP E INVIO EMAIL")
    print("=" * 60)
    print()

    process_zip_files()

    print()
    print("=" * 60)
    print("Elaborazione completata")
    print("=" * 60)


if __name__ == "__main__":
    main()