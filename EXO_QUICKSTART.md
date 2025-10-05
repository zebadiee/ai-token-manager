# 🌀 Exo Integration for AI Token Manager

**Complete Exo local cluster integration with automatic failover, health monitoring, and universal HUD dashboard.**

---

## 🚀 Quick Start (5 Minutes)

### 1. Run Setup Script

```bash
cd ~/ai-token-manager
./setup_exo_integration.sh
```

This will:
- ✓ Check Python version (3.12+ required)
- ✓ Install/verify Exo cluster
- ✓ Install dependencies
- ✓ Configure integration
- ✓ Create launch scripts
- ✓ Run tests

### 2. Start Exo Cluster

```bash
./start_exo.sh
```

Or manually:
```bash
cd ~/exo
python3 main.py
```

### 3. Launch Spiral Codex HUD

```bash
./start_hud.sh
```

Access at: **http://localhost:8501**

### 4. Or Start Everything Together

```bash
./start_all.sh
```

---

## 📦 What's Included

### Core Components

| File | Description |
|------|-------------|
| `exo_provider.py` | Exo cluster provider with health monitoring |
| `exo_integration.py` | Token manager integration with auto-failover |
| `spiral_codex_hud.py` | Streamlit monitoring dashboard |
| `exo_api_examples.py` | Usage examples and patterns |
| `setup_exo_integration.sh` | Automated setup script |
| `EXO_INTEGRATION_GUIDE.md` | Comprehensive documentation |

### Generated Scripts

- `start_exo.sh` - Start Exo cluster
- `start_hud.sh` - Start monitoring dashboard
- `start_all.sh` - Start everything together

---

## 🎯 Core Features

### 1. **Zero-Cost Local Inference**
- Run AI models on your own hardware
- No API costs
- Complete data privacy
- Ultra-low latency

### 2. **Automatic Failover**
```python
# Routes to Exo first, cloud backup automatically
response, error, provider = integration.route_request(
    model="llama-3.2-3b",
    messages=[{"role": "user", "content": "Hello!"}]
)
# Provider used: "Exo Local" or "Cloud (Failover)"
```

### 3. **Multi-Node Clustering**
```bash
# Device 1
python3 ~/exo/main.py

# Device 2 (auto-discovers Device 1)
python3 ~/exo/main.py

# Device 3 (joins cluster automatically)
python3 ~/exo/main.py
```

All devices combine processing power automatically!

### 4. **Real-Time Monitoring**
- Live cluster status
- Node health visualization
- Request metrics and history
- Manual model testing

### 5. **Reliakit Self-Healing**
```python
from exo_integration import ExoReliakitProvider

reliakit = ExoReliakitProvider(integration)
health = reliakit.health_check()

if not health['healthy']:
    reliakit.attempt_recovery()
```

---

## 💻 Usage Examples

### Basic Chat Completion

```python
from exo_integration import ExoTokenManagerIntegration

# Initialize
integration = ExoTokenManagerIntegration()
integration.start()

# Send request
response, error, provider = integration.route_request(
    model="llama-3.2-3b",
    messages=[
        {"role": "user", "content": "What is AI?"}
    ],
    temperature=0.7,
    max_tokens=512
)

print(f"Provider: {provider}")  # "Exo Local" or "Cloud (Failover)"
print(f"Cost: $0.00")  # Always free for local!
```

### Unified Client (Recommended)

```python
from exo_api_examples import UnifiedLLMClient

# Create client with automatic failover
client = UnifiedLLMClient(
    exo_host="localhost",
    exo_port=8000
)

# Use like any other LLM API
result = client.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    model="llama-3.2-3b"
)

print(result['response'])
print(f"Cost: {result['cost']}")  # $0.00 if local
```

### Check Status

```python
status = integration.get_unified_status()

print(f"Cluster available: {status['exo']['available']}")
print(f"Healthy nodes: {status['exo']['health']['healthy_nodes']}")
print(f"Available models: {status['exo']['available_models']}")
print(f"Recommendation: {status['recommendation']}")
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│         Your Application                 │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│    Multi-Provider Token Manager          │
│  ┌────────────────────────────────────┐  │
│  │ Priority 0: Exo Local (FREE)       │  │
│  │ Priority 1: OpenRouter             │  │
│  │ Priority 2: Hugging Face           │  │
│  └────────────────────────────────────┘  │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│      Exo Integration Layer               │
│  • Auto-failover                         │
│  • Health monitoring                     │
│  • Load balancing                        │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│         Exo Local Cluster                │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐ │
│  │ Mac  │  │iPhone│  │ iPad │  │ RPi  │ │
│  │16GB  │  │ 8GB  │  │ 4GB  │  │ 8GB  │ │
│  └──────┘  └──────┘  └──────┘  └──────┘ │
│      Auto-discovery & Partitioning       │
└──────────────────────────────────────────┘
```

---

## 📊 Spiral Codex HUD

The **Spiral Codex HUD** is your command center for all AI providers.

### Features

✓ **Real-time cluster monitoring**
- Node status and health
- Request metrics
- Compute time tracking

✓ **Visual node display**
- Online/offline/degraded status
- Memory and device info
- Last seen timestamps

✓ **Interactive testing**
- Model selection
- Temperature/token controls
- Live response display

✓ **Auto-refresh**
- Configurable interval
- Manual refresh option
- Request history charts

### Screenshots

```
🌀 SPIRAL CODEX HUD
AI Command Bridge - Universal Provider Monitor & Control
─────────────────────────────────────────────────────────

🟢 Cluster Status: ONLINE     🖥️ Active Nodes: 3/3
🤖 Available Models: 5         💰 Cost: $0.00

📡 Node Details
┌─────────────────────────────────────────────┐
│ 🟢 MacBook Pro                              │
│ ID: localhost:8000                          │
│ Status: ONLINE                              │
│ Memory: 16.0 GB                             │
│ Models: 5                                   │
│ Last Seen: 2025-10-05 16:05:23             │
└─────────────────────────────────────────────┘
```

---

## 🔧 Configuration

### Provider Configuration

Exo is added to your token manager config at `~/.token_manager_config.json`:

```json
{
  "providers": [
    {
      "name": "Exo Local",
      "base_url": "http://localhost:8000",
      "status": "active",
      "rate_limit": 999999,
      "token_limit": 999999,
      "cost": 0.0,
      "priority": 0
    },
    // ... other providers
  ]
}
```

### Health Monitoring Settings

```python
integration = ExoTokenManagerIntegration(
    exo_host="localhost",
    exo_port=8000,
    enable_auto_failover=True  # Auto-switch to cloud when Exo fails
)
```

### Node Discovery

```python
from exo_provider import ExoClusterProvider

provider = ExoClusterProvider(
    primary_node_host="localhost",
    primary_node_port=8000,
    auto_discover=True,           # Auto-find nodes
    health_check_interval=10,     # Check every 10s
    node_timeout=30               # Mark offline after 30s
)
```

---

## 🧪 Testing

### Quick Test

```bash
python3 exo_provider.py
```

### Full Integration Test

```bash
python3 exo_integration.py
```

### Run Examples

```bash
python3 exo_api_examples.py
```

### Test with HUD

1. Start HUD: `./start_hud.sh`
2. Connect to Exo cluster
3. Select a model
4. Enter prompt and send
5. View response and metadata

---

## 🔍 Troubleshooting

### Exo cluster not starting

```bash
# Check Python version
python3 --version  # Must be 3.12+

# Install Exo
cd ~/exo
pip install -e .

# Start with debug
python3 main.py --debug
```

### Integration not detecting Exo

```bash
# Verify Exo is running
curl http://localhost:8000/health

# Check if port is correct
lsof -i :8000

# Test provider manually
python3 -c "from exo_provider import ExoClusterProvider; p = ExoClusterProvider(); print(p.get_status())"
```

### HUD not loading

```bash
# Install dependencies
pip install streamlit plotly requests

# Start with debug
streamlit run spiral_codex_hud.py --logger.level=debug
```

### No models available

```bash
# Exo downloads models on first use
# Trigger a request to download:
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"llama-3.2-3b","messages":[{"role":"user","content":"hi"}]}'
```

---

## 📈 Performance Tips

### 1. Use Local Model Cache
```bash
# Pre-download models for faster startup
cd ~/exo
python3 -c "from exo.download.hf.hf_shard_download import HFShardDownloader; HFShardDownloader().download('llama-3.2-3b')"
```

### 2. Multi-Device Clustering
- More devices = faster inference
- Use wired connections for best performance
- Each device auto-discovers others on LAN

### 3. Memory Optimization
```bash
# Check available memory per node
free -h

# Ensure enough RAM for model:
# llama-3.2-3b = 6GB
# llama-3.1-8b = 16GB
```

### 4. Network Optimization
- Wired > WiFi for multi-node
- Same subnet for auto-discovery
- Low latency = better performance

---

## 🔐 Security

- ✅ All inference is local - no data leaves your network
- ✅ No API keys required for Exo
- ✅ Cloud failover uses encrypted keys from token manager
- ✅ HUD runs locally on localhost
- ⚠️ Don't expose Exo ports to public internet without authentication

---

## 🛣️ Roadmap

### Planned Features
- [ ] Streaming support
- [ ] Function calling integration
- [ ] Embedding models
- [ ] Advanced load balancing strategies
- [ ] Geographic distribution support
- [ ] Prometheus metrics export
- [ ] Docker compose deployment
- [ ] Kubernetes orchestration

---

## 📚 Documentation

- **Integration Guide**: `EXO_INTEGRATION_GUIDE.md`
- **Exo Official Docs**: https://github.com/exo-explore/exo
- **Token Manager Docs**: `README.md`
- **API Examples**: `exo_api_examples.py`

---

## 🆘 Support

### Exo Issues
- GitHub: https://github.com/exo-explore/exo/issues
- Discord: https://discord.gg/EUnjGpsmWw

### Integration Issues
- Check integration guide
- Run test scripts
- Review logs

### Community
- Exo Discord for cluster questions
- GitHub Issues for integration bugs

---

## 📝 License

This integration follows the same license as the Multi-Provider Token Manager.

Exo is licensed under GPL v3.

---

## 🙏 Credits

- **Exo Team** for the amazing distributed AI platform
- **Multi-Provider Token Manager** for the robust provider framework
- **Reliakit-TL15** for self-healing patterns
- **Streamlit** for the HUD framework

---

## ⚡ Quick Reference

```bash
# Setup
./setup_exo_integration.sh

# Start Exo
./start_exo.sh

# Start HUD
./start_hud.sh

# Start Everything
./start_all.sh

# Test
python3 exo_api_examples.py

# Check Status
curl http://localhost:8000/health
```

---

**Made with ❤️ for the local AI community**

*Run AI on your own terms. Own your data. Own your compute.*
