#!/usr/bin/env python3
"""Check current API key configuration status"""

import os
from enhanced_multi_provider_manager import EnhancedTokenManager

print("=" * 70)
print("🔑 API Key Configuration Status")
print("=" * 70)

# Check environment variables
print("\n📋 Environment Variables:")
env_vars = {
    'OPENROUTER_API_KEY': 'OpenRouter',
    'HUGGINGFACE_API_KEY': 'HuggingFace',
    'TOGETHER_API_KEY': 'Together AI'
}

for env_var, name in env_vars.items():
    value = os.getenv(env_var)
    if value:
        # Show first/last 4 chars for security
        masked = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
        print(f"  ✓ {name:20} {masked}")
    else:
        print(f"  ✗ {name:20} Not set")

# Check configured providers
print("\n📋 Configured Providers:")
manager = EnhancedTokenManager()

if len(manager.providers) == 0:
    print("  ℹ️  No providers configured yet")
    print()
    print("  To add providers:")
    print("  1. Use the Streamlit UI (sidebar → Add New Provider)")
    print("  2. OR set environment variables and restart")
else:
    for provider in manager.providers:
        has_key = "✓" if provider.api_key else "✗"
        key_status = "Has key" if provider.api_key else "No key"
        print(f"  {has_key} {provider.config.name:20} {key_status}")

# Recommendations
print("\n" + "=" * 70)
print("💡 Recommendations:")
print("=" * 70)

if len(manager.providers) == 0:
    print("""
🔑 No providers configured!

Quick start options:

1. Via Streamlit UI (Easiest):
   - App should be running at http://localhost:8501
   - Click "Add New Provider" in sidebar
   - Enter your API key
   - Save configuration

2. Via Environment Variables:
   export OPENROUTER_API_KEY="your_key_here"
   ./launch.sh

3. Get free API keys:
   - OpenRouter: https://openrouter.ai/keys (recommended)
   - HuggingFace: https://huggingface.co/settings/tokens
""")
else:
    providers_with_keys = sum(1 for p in manager.providers if p.api_key)
    if providers_with_keys == 0:
        print("\n⚠️  Providers configured but no API keys set!")
        print("   Add keys via the UI or environment variables")
    else:
        print(f"\n✅ {providers_with_keys} provider(s) with API keys configured")
        print("   You should be able to use the chat functionality now!")

print("=" * 70)
