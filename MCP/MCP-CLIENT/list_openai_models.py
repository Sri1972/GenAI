import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env")
openai_api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=openai_api_key)

models = client.models.list()

print("Available OpenAI models:")
for model in models.data:
    # Filter out free-tier models (e.g., gpt-3.5-turbo)
    if not model.id.startswith("gpt-3.5-turbo"):
        print(model.id)
