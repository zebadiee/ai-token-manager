#!/bin/bash
# Startup script for AI Token Manager

set -e

echo "🚀 Starting AI Token Manager..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/update dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Check for .env file
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ .env file found${NC}"
    # Load environment variables
    export $(cat .env | grep -v '^#' | xargs)
else
    echo -e "${YELLOW}⚠️  No .env file found. You can add API keys through the web interface.${NC}"
fi

# Run tests if requested
if [ "$1" == "--test" ]; then
    echo -e "${YELLOW}Running tests...${NC}"
    python test_token_manager.py
    python smoke_test.py
    echo -e "${GREEN}✓ All tests passed${NC}"
    exit 0
fi

# Start the application
echo -e "${GREEN}✓ Starting Streamlit application...${NC}"
echo -e "${YELLOW}Access the app at: http://localhost:8501${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

streamlit run enhanced_multi_provider_manager.py \
    --server.headless=true \
    --browser.gatherUsageStats=false \
    --server.fileWatcherType=auto
