import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ ERROR: API Key not found in .env file!")
else:
    print(f"✅ Found API Key: {api_key[:5]}...{api_key[-5:]}")
    
    genai.configure(api_key=api_key)
    
    print("\n🔍 Checking available models...")
    try:
        count = 0
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - {m.name}")
                count += 1
        if count == 0:
            print("⚠️ No models found! Your API Key might be invalid or restricted.")
    except Exception as e:
        print(f"❌ Error listing models: {e}")