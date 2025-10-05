#!/usr/bin/env python3
"""Diagnose provider and model loading issues"""

import sys
from enhanced_multi_provider_manager import EnhancedTokenManager

print("=" * 70)
print("🔍 Provider & Model Loading Diagnostics")
print("=" * 70)

manager = EnhancedTokenManager()

print(f"\n📊 Providers: {len(manager.providers)}")
print(f"Current provider index: {manager.current_provider_index}")

if not manager.providers:
    print("\n❌ No providers configured!")
    print("Add providers via the UI or environment variables")
    sys.exit(1)

print("\n" + "=" * 70)
print("🔌 Provider Status")
print("=" * 70)

for i, provider in enumerate(manager.providers):
    is_current = " ⭐ CURRENT" if i == manager.current_provider_index else ""
    print(f"\n{i}. {provider.config.name}{is_current}")
    print(f"   Status: {provider.config.status}")
    print(f"   Has API Key: {'✓' if provider.api_key else '✗'}")
    print(f"   Base URL: {provider.config.base_url}")
    print(f"   Models Endpoint: {provider.config.models_endpoint}")
    
    if provider.api_key:
        # Try to get models
        print(f"   Testing model fetch...")
        models, error = provider.get_models()
        
        if error:
            print(f"   ❌ Error: {error}")
        elif models:
            print(f"   ✓ Successfully loaded {len(models)} models")
            if len(models) > 0:
                # Show first few models
                for j, model in enumerate(models[:3]):
                    model_id = model.get('id', model.get('name', 'unknown'))
                    print(f"      - {model_id}")
                if len(models) > 3:
                    print(f"      ... and {len(models) - 3} more")
        else:
            print(f"   ⚠️  No models returned (empty list)")
    else:
        print(f"   ⚠️  No API key - cannot fetch models")

print("\n" + "=" * 70)
print("🔄 Testing get_all_models()")
print("=" * 70)

all_models = manager.get_all_models()

if all_models:
    print(f"\n✓ Successfully got models from {len(all_models)} provider(s)")
    for provider_name, models in all_models.items():
        print(f"\n  {provider_name}: {len(models)} models")
        for model in models[:3]:
            model_id = model.get('id', model.get('name', 'unknown'))
            print(f"    - {model_id}")
        if len(models) > 3:
            print(f"    ... and {len(models) - 3} more")
else:
    print("\n❌ No models loaded from any provider")
    print("\nPossible reasons:")
    print("  1. API keys are invalid or missing")
    print("  2. Network connectivity issues")
    print("  3. Provider API is down")
    print("  4. Rate limits exceeded")

print("\n" + "=" * 70)
print("💡 Recommendations")
print("=" * 70)

current = manager.get_current_provider()
if current:
    if not current.api_key:
        print(f"\n⚠️  Current provider ({current.config.name}) has no API key")
        print("   → Add API key via the UI or switch to a provider with a key")
    else:
        print(f"\n✓ Current provider: {current.config.name}")
        print("   → Try the 'Refresh Models' button in the UI")
else:
    print("\n❌ No current provider set")
    print("   → Add a provider via the UI")

print("\n" + "=" * 70)
