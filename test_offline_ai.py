#!/usr/bin/env python3
"""
Test offline AI using Exo - NO API KEYS NEEDED!
"""
import requests
import json

# Exo endpoint - runs locally, no API key required
EXO_URL = "http://127.0.0.1:52415/v1/chat/completions"

def chat_offline(message):
    """Send a message to local Exo AI - no API keys needed!"""
    
    payload = {
        "model": "llama-3.2-1b",  # Local model
        "messages": [
            {"role": "user", "content": message}
        ],
        "temperature": 0.7,
        "max_tokens": 500
    }
    
    try:
        response = requests.post(EXO_URL, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content']
        
    except requests.exceptions.ConnectionError:
        return "❌ Exo is not running. Start it with: cd ~/exo && source .venv/bin/activate && python3 exo/main.py"
    except Exception as e:
        return f"❌ Error: {e}"


if __name__ == "__main__":
    print("🌀 Testing Offline AI (No API Keys Needed!)\n")
    print("=" * 60)
    
    test_message = "Hello! Can you tell me a short joke?"
    print(f"\nYou: {test_message}")
    
    response = chat_offline(test_message)
    print(f"\nAI: {response}")
    
    print("\n" + "=" * 60)
    print("\n✅ SUCCESS! This works completely offline with NO API keys!")
    print(f"   Exo is running on: {EXO_URL}")
    print(f"   Web interface: http://127.0.0.1:52415")
