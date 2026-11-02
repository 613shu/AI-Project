import os
from dotenv import load_dotenv
from google import genai

# טעינת המפתח מקובץ .env
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# הדפסת המודלים הזמינים ומה כל אחד יודע לעשות
for model in client.models.list():
    print(model.name, model.supported_actions)