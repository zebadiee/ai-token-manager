# API Key Setup Guide

## Current Status

✅ **Application is working correctly!**

The error you're seeing is expected - you need to configure API keys to use the chat functionality.

## Error Explanation

When you see:
```
Hugging Face API key being used is invalid or missing
```

This means:
- ✅ The app is running correctly
- ✅ It's trying to use Hugging Face provider
- ❌ No valid API key is configured

## Solution: Add API Keys

### Method 1: Via Streamlit UI (Easiest)

1. **Open the app** (should already be running at http://localhost:8501)

2. **In the sidebar**, look for "Provider Management"

3. **Add a provider**:
   - Click "Add New Provider"
   - Select provider type (OpenRouter, HuggingFace, Together AI)
   - Enter your API key
   - Click "Add Provider"

4. **Save**: Go to Settings tab → Click "Save Configuration"

### Method 2: Environment Variables

```bash
# Set your API keys
export OPENROUTER_API_KEY="sk-or-v1-YOUR_KEY_HERE"
export HUGGINGFACE_API_KEY="hf_YOUR_KEY_HERE"
export TOGETHER_API_KEY="YOUR_KEY_HERE"

# Restart the app
cd ~/ai-token-manager
./launch.sh
```

## Where to Get API Keys

### OpenRouter (Recommended - easiest to use)
- **Website**: https://openrouter.ai/keys
- **Free tier**: Yes (with limits)
- **Key format**: `sk-or-v1-...`
- **Models**: Access to many models (GPT, Claude, Llama, etc.)

### HuggingFace
- **Website**: https://huggingface.co/settings/tokens
- **Free tier**: Yes
- **Key format**: `hf_...`
- **Models**: Open source models

### Together AI
- **Website**: https://api.together.xyz/settings/api-keys
- **Free tier**: Trial credits
- **Models**: Open source models

## Testing the Setup

After adding API keys:

1. **Check Provider Status**:
   - Go to "Status" tab in the app
   - You should see your providers listed with "active" status
   - "has_key" should show ✓

2. **Test Chat**:
   - Go to "Chat" tab
   - Select a model from the dropdown
   - Type a message and send

3. **Monitor Usage**:
   - Check "Status" tab for token usage
   - View request counts

## Current System State

```
Location: ~/ai-token-manager
App Status: ✅ Running
Bug Status: ✅ Fixed
Tests: ✅ All passing
Config: ✅ Ready

Missing: 🔑 API Keys (user needs to add)
```

## Quick Verification

To see what providers are currently configured:

```bash
cd ~/ai-token-manager
source venv/bin/activate
python3 << 'EOF'
from enhanced_multi_provider_manager import EnhancedTokenManager
manager = EnhancedTokenManager()
print(f"Configured providers: {len(manager.providers)}")
for p in manager.providers:
    has_key = "✓" if p.api_key else "✗"
    print(f"  {has_key} {p.config.name}")
EOF
```

## Next Steps

1. Choose which provider(s) you want to use
2. Get API key(s) from the provider's website
3. Add them via UI or environment variables
4. Start chatting!

---

**Note**: The application is working perfectly. You just need to add your API credentials to start using it.
