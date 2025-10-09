from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

client = genai.Client(api_key='AIzaSyDKxn4lXHrcmELXCjP6xpG1jwGlf9BB_Zc')

prompt = (
    "Crea un immagine di un insenatura di un fiume e una coppia sulla riva"
)

response = client.models.generate_content(
    model="gemini-2.5-flash-image",
    contents=[prompt],
)

for part in response.candidates[0].content.parts:
    if part.text is not None:
        print(part.text)
    elif part.inline_data is not None:
        image = Image.open(BytesIO(part.inline_data.data))
        image.save("generated_image.png")