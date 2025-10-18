import google.generativeai as genai
import os

# Configure the API key. It's recommended to load it from an environment variable.
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    print("Error: GOOGLE_API_KEY environment variable not set.")
    print("Please set the GOOGLE_API_KEY environment variable with your actual API key.")
    exit()

print("Fetching available Generative AI models...\n")

found_models = False
for m in genai.list_models():
    # Filter for models that support 'generateContent'
    # This is the method typically used for conversational or text generation tasks.
    if "generateContent" in m.supported_generation_methods:
        print(f"  Model Name: {m.name}")
        print(f"  Description: {m.description}")
        print(f"  Input Token Limit: {m.input_token_limit}")
        print(f"  Output Token Limit: {m.output_token_limit}")
        print(f"  Supported Methods: {m.supported_generation_methods}")
        print("-" * 40) # Separator for readability
        found_models = True

if not found_models:
    print("No models supporting 'generateContent' were found. Please check your API key and project settings.")
else:
    print("List of available models that support generateContent has been printed above.")
    print("\nPick one of the 'Model Name' values (e.g., 'models/gemini-pro') to use in your client.")