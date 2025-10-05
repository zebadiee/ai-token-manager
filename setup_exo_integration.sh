#!/bin/bash
# Exo Integration Setup Script
# Automated installation and configuration for Exo + Token Manager integration

set -e  # Exit on error

echo "🌀 Exo Integration Setup for AI Token Manager"
echo "=============================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EXO_DIR="$HOME/exo"
TOKEN_MANAGER_DIR="$SCRIPT_DIR"

echo -e "${YELLOW}Step 1: Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.12.0"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.12.0 or higher is required${NC}"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"
echo ""

echo -e "${YELLOW}Step 2: Checking Exo installation...${NC}"
if [ ! -d "$EXO_DIR" ]; then
    echo "Exo not found. Installing..."
    cd "$HOME"
    git clone https://github.com/exo-explore/exo.git
    cd "$EXO_DIR"
    pip install -e .
    echo -e "${GREEN}✓ Exo installed${NC}"
else
    echo -e "${GREEN}✓ Exo already installed at $EXO_DIR${NC}"
fi
echo ""

echo -e "${YELLOW}Step 3: Installing Python dependencies...${NC}"
cd "$TOKEN_MANAGER_DIR"

# Create requirements file if not exists
cat > exo_requirements.txt << EOF
requests>=2.31.0
streamlit>=1.28.0
plotly>=5.17.0
aiohttp>=3.9.0
numpy>=1.24.0
EOF

pip install -r exo_requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

echo -e "${YELLOW}Step 4: Configuring Exo integration...${NC}"

# Test if Exo is running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Exo cluster is running${NC}"
    
    # Add to token manager config
    python3 << 'PYTHON_SCRIPT'
import sys
sys.path.insert(0, '.')
from exo_integration import ExoTokenManagerIntegration

try:
    integration = ExoTokenManagerIntegration()
    if integration.add_to_config():
        print("✓ Exo provider added to token manager config")
    else:
        print("⚠ Failed to add Exo to config")
except Exception as e:
    print(f"⚠ Error adding to config: {e}")
PYTHON_SCRIPT

else
    echo -e "${YELLOW}⚠ Exo cluster not running (optional)${NC}"
    echo "  Start it later with: python3 $EXO_DIR/main.py"
fi
echo ""

echo -e "${YELLOW}Step 5: Creating launch scripts...${NC}"

# Create Exo start script
cat > start_exo.sh << 'EOF'
#!/bin/bash
# Start Exo cluster node

echo "🚀 Starting Exo cluster node..."
cd ~/exo

# Check if already running
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠ Exo is already running"
    exit 0
fi

# Start Exo
python3 main.py
EOF

chmod +x start_exo.sh

# Create HUD start script
cat > start_hud.sh << 'EOF'
#!/bin/bash
# Start Spiral Codex HUD

echo "🌀 Starting Spiral Codex HUD..."
cd "$(dirname "$0")"

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "⚠ Installing Streamlit..."
    pip install streamlit plotly
fi

# Start HUD
streamlit run spiral_codex_hud.py --server.port 8501
EOF

chmod +x start_hud.sh

# Create combined launcher
cat > start_all.sh << 'EOF'
#!/bin/bash
# Start Exo cluster and HUD

echo "🚀 Starting complete Exo integration..."

# Start Exo in background
./start_exo.sh &
EXO_PID=$!

# Wait for Exo to be ready
echo "Waiting for Exo cluster to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "✓ Exo cluster is ready"
        break
    fi
    sleep 1
    echo -n "."
done
echo ""

# Start HUD
./start_hud.sh
EOF

chmod +x start_all.sh

echo -e "${GREEN}✓ Launch scripts created${NC}"
echo ""

echo -e "${YELLOW}Step 6: Testing integration...${NC}"

# Quick test
python3 << 'PYTHON_SCRIPT'
import sys
sys.path.insert(0, '.')

try:
    from exo_provider import ExoClusterProvider
    from exo_integration import ExoTokenManagerIntegration
    print("✓ Import test passed")
    
    # Test provider initialization
    provider = ExoClusterProvider(
        primary_node_host="localhost",
        primary_node_port=8000,
        auto_discover=False  # Don't start threads for test
    )
    print("✓ Provider initialization test passed")
    
except Exception as e:
    print(f"⚠ Test failed: {e}")
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Integration tests passed${NC}"
else
    echo -e "${RED}✗ Integration tests failed${NC}"
    exit 1
fi
echo ""

echo -e "${GREEN}=============================================="
echo "✓ Exo Integration Setup Complete!"
echo "==============================================
"${NC}

echo "Next steps:"
echo ""
echo "1. Start Exo cluster:"
echo "   ${YELLOW}./start_exo.sh${NC}"
echo ""
echo "2. Start Spiral Codex HUD:"
echo "   ${YELLOW}./start_hud.sh${NC}"
echo ""
echo "3. Or start everything:"
echo "   ${YELLOW}./start_all.sh${NC}"
echo ""
echo "4. Access HUD at:"
echo "   ${YELLOW}http://localhost:8501${NC}"
echo ""
echo "5. Test the integration:"
echo "   ${YELLOW}python3 exo_integration.py${NC}"
echo ""

echo "Documentation:"
echo "  • Exo README: $EXO_DIR/README.md"
echo "  • Integration docs: ./EXO_INTEGRATION_GUIDE.md"
echo ""

# Create integration guide
cat > EXO_INTEGRATION_GUIDE.md << 'EOF'
# Exo Integration Guide

## Overview

This integration seamlessly connects your Exo local AI cluster with the Multi-Provider Token Manager, providing zero-cost, low-latency AI inference with automatic failover to cloud providers.

## Architecture

```
┌─────────────────┐
│  Applications   │
└────────┬────────┘
         │
┌────────▼────────────────────────┐
│ Multi-Provider Token Manager    │
│  • OpenRouter                   │
│  • Hugging Face                 │
│  • Exo Local (Priority 0)       │
└────────┬────────────────────────┘
         │
┌────────▼────────┐
│ Exo Integration │
│  • Auto-failover│
│  • Health check │
│  • Load balance │
└────────┬────────┘
         │
┌────────▼────────────────────────┐
│     Exo Local Cluster           │
│  ┌──────┐ ┌──────┐ ┌──────┐    │
│  │Node 1│ │Node 2│ │Node 3│    │
│  └──────┘ └──────┘ └──────┘    │
└─────────────────────────────────┘
```

## Components

### 1. ExoClusterProvider (`exo_provider.py`)
- Direct interface to Exo cluster
- Health monitoring and node discovery
- ChatGPT-compatible API wrapper

### 2. ExoTokenManagerIntegration (`exo_integration.py`)
- Integrates Exo into token manager
- Automatic failover logic
- Priority routing (Exo first, cloud backup)

### 3. Spiral Codex HUD (`spiral_codex_hud.py`)
- Real-time monitoring dashboard
- Manual model selection and testing
- Visual health status

## Usage

### Basic Usage

```python
from exo_integration import ExoTokenManagerIntegration

# Initialize
integration = ExoTokenManagerIntegration(
    exo_host="localhost",
    exo_port=8000,
    enable_auto_failover=True
)

# Add to config
integration.add_to_config()

# Route requests (Exo first, cloud failover)
response, error, provider = integration.route_request(
    model="llama-3.2-3b",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### With Reliakit Self-Healing

```python
from exo_integration import ExoReliakitProvider

# Create reliakit-compatible wrapper
reliakit_provider = ExoReliakitProvider(integration)

# Health check
health = reliakit_provider.health_check()

# Automatic recovery
if not health["healthy"]:
    reliakit_provider.attempt_recovery()
```

### HUD Dashboard

```bash
# Start the dashboard
./start_hud.sh

# Access at http://localhost:8501
```

## Configuration

### Provider Priority

Exo is configured as priority 0 (highest). Requests route to Exo first, then cloud providers if Exo is unavailable.

### Health Monitoring

- Check interval: 10 seconds (configurable)
- Node timeout: 30 seconds
- Auto-discovery: Enabled by default

### Failover Behavior

1. Request arrives
2. Check Exo cluster availability
3. If available → Use Exo (zero cost)
4. If unavailable → Automatic failover to cloud provider
5. Background: Continuously monitor for Exo recovery
6. When recovered → Resume using Exo

## Advanced Features

### Multi-Node Clustering

Run Exo on multiple devices for distributed inference:

```bash
# Device 1 (primary)
cd ~/exo
python3 main.py

# Device 2 (auto-discovers Device 1)
cd ~/exo
python3 main.py

# Device 3 (auto-discovers cluster)
cd ~/exo
python3 main.py
```

The integration automatically discovers and load balances across all nodes.

### Cost Tracking

Exo usage is tracked as compute time rather than tokens, since it's running locally (zero cost).

```python
status = integration.get_unified_status()
print(f"Total requests: {status['exo']['usage']['total_requests']}")
print(f"Compute time: {status['exo']['usage']['total_compute_time']}s")
print(f"Cost: ${status['exo']['cost']}")  # Always $0.00
```

## Troubleshooting

### Exo cluster not detected

```bash
# Check if Exo is running
curl http://localhost:8000/health

# Check logs
cd ~/exo
python3 main.py --debug
```

### Integration not working

```bash
# Test provider directly
python3 exo_provider.py

# Test integration
python3 exo_integration.py
```

### HUD not loading

```bash
# Check Streamlit installation
pip install streamlit plotly

# Start with verbose logging
streamlit run spiral_codex_hud.py --logger.level=debug
```

## Performance Tips

1. **Use local models**: Download models to local cache for faster startup
2. **Add more nodes**: More devices = faster inference for large models
3. **Memory allocation**: Ensure each node has enough RAM for model shards
4. **Network speed**: Use wired connections for multi-node clusters

## Security Notes

- Exo runs locally - no data leaves your network
- No API keys required for Exo provider
- Cloud failover uses encrypted keys from token manager config

## Support

- Exo GitHub: https://github.com/exo-explore/exo
- Exo Discord: https://discord.gg/EUnjGpsmWw
- Token Manager: See main README.md

## License

This integration follows the same license as the Multi-Provider Token Manager.
EOF

echo -e "${GREEN}Integration guide created: EXO_INTEGRATION_GUIDE.md${NC}"
