from google import genai
from google.genai import types


client = genai.Client(api_key='AIzaSyDKxn4lXHrcmELXCjP6xpG1jwGlf9BB_Zc')

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=["parlami di TIM, VODAFONE ed ILIAD. Dammi un testo senza formattazione"],
    config=types.GenerateContentConfig(
        temperature=0.1,
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )
)

print(response.text)