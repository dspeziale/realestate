from google import genai
import time

client = genai.Client(api_key='AIzaSyDKxn4lXHrcmELXCjP6xpG1jwGlf9BB_Zc')

# Gemini 2.5 Flash gestisce automaticamente OCR e immagini nel PDF!
uploaded_file = client.files.upload(file="Documentazione_Complex.pdf"
)

while uploaded_file.state == "PROCESSING":
    time.sleep(1)
    uploaded_file = client.files.get(name=uploaded_file.name)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[uploaded_file, "Estrai tutto il testo e le informazioni da questo PDF, anche dalle immagini"]
)
print(response.text)