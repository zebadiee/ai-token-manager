# AI Token Manager

Multi-provider AI token management system with automatic rotation, encrypted storage, and web-based GUI.

## ✅ Status: All Tests Passing

The repository has been tested and all functionality is working correctly. See [TEST_REPORT.md](TEST_REPORT.md) for details.

## 🚀 Quick Start

### 1. Setup (First Time)
```bash
cd ~/ai-token-manager
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_enhanced.txt
```

### 2. Run the Application
```bash
source venv/bin/activate
streamlit run enhanced_multi_provider_manager.py
```

Then open http://localhost:8501 in your browser.

## 🧪 Running Tests

To verify everything is working:
```bash
./run_all_tests.sh
```

## 📋 Features

- ✅ **Multi-Provider Support**: OpenRouter, HuggingFace, Together AI
- ✅ **Secure Storage**: Encrypted API keys with Fernet encryption
- ✅ **Persistent Config**: Settings saved between sessions
- ✅ **Token Tracking**: Monitor usage across providers
- ✅ **Auto Rotation**: Automatic failover when limits reached
- ✅ **Web Interface**: Streamlit-based GUI (no crashes!)
- ✅ **Environment Variables**: Auto-load keys from env vars

## 🔑 Adding API Keys

### Option 1: Environment Variables
```bash
export OPENROUTER_API_KEY="your_key_here"
export HUGGINGFACE_API_KEY="your_key_here"
export TOGETHER_API_KEY="your_key_here"
```

### Option 2: Via Web UI
1. Run the app: `streamlit run enhanced_multi_provider_manager.py`
2. Go to the Settings tab
3. Add your API keys
4. Click "Save Configuration"

---

## ⚡ Auto-Refresh Feature

The app includes a **non-blocking background auto-refresh** system that keeps your data fresh without interrupting your workflow!

### How It Works
- Runs in background thread (never blocks UI)
- 10-second timeout protection
- Falls back to cached data on failure
- Configurable intervals (1-15 minutes)
- Enable/disable in Settings tab

### Visual Indicators
- 🔄 "Background refresh in progress..."
- ✓ "Auto-refreshed - models up to date"
- ⚠️ "Using cached models - refresh recommended"

### User Control
- Toggle auto-refresh on/off
- Set refresh interval
- Manual refresh always available
- Never interrupts active chat

**Auto-refresh is a quiet assistant, not a gatekeeper!** It enhances your experience without getting in the way.

See [AUTO_REFRESH_DOCS.md](AUTO_REFRESH_DOCS.md) for complete documentation.

---

## 📁 Files

### Main Application
- `enhanced_multi_provider_manager.py` - **Recommended**: Streamlit version with all fixes
- `multi_provider_web_manager.py` - Alternative web interface
- `multi_provider_token_manager.py` - Original Tkinter version

### Tests
- `run_all_tests.sh` - Run complete test suite
- `test_token_manager.py` - Unit tests
- `smoke_test.py` - Quick functionality check
- `diagnose.py` - System diagnostics
- `TEST_REPORT.md` - Detailed test results

### Documentation
- `USAGE_GUIDE.md` - Detailed usage instructions
- `README.md` - This file

## 🔒 Security

- API keys are encrypted using Fernet (symmetric encryption)
- Config files have restricted permissions (600)
- Keys stored at `~/.token_manager_config.json` and `~/.token_manager_key`
- Never stored in plain text

## 🐛 Known Issues (All Fixed!)

All previously reported issues have been resolved in the enhanced version:

- ✅ API keys disappearing - Fixed with encrypted persistent storage
- ✅ HuggingFace 400 errors - Fixed with improved API handling
- ✅ Model loading issues - Fixed with provider-specific endpoints  
- ✅ GUI crashes - Fixed by switching to Streamlit

## 📊 Test Results

```
✅ Unit Tests: PASSED (6/6)
✅ Smoke Test: PASSED (6/6)
✅ Diagnostics: PASSED
```

All core functionality verified and working correctly!

## 🎯 Next Steps

1. Add your API keys (via env vars or UI)
2. Run the application
3. Start using the token manager!

---

**Last tested**: October 5, 2025
**Status**: ✅ All systems operational
