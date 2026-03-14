#!/usr/bin/env python
import os
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

api_key = os.environ.get('GEMINI_API_KEY')
print(f"API Key: {api_key[:20]}..." if api_key else "No API key")

genai.configure(api_key=api_key)

# Test if the model exists
print("Testing gemini-2.5-flash...")
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content("Return this JSON: {\"test\": \"value\"}")
    print(f"Response text: {response.text}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
