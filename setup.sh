#!/bin/bash
# Complete Setup Script for AI Token Manager
# This script sets up everything needed for first-time deployment

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  AI Token Manager - Complete Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Check Prerequisites
echo -e "${YELLOW}📋 Step 1: Checking Prerequisites...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; v=sys.version_info; print(f"{v.major}.{v.minor}")')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}❌ pip3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ pip3 found${NC}"

# Check git (optional)
if command -v git &> /dev/null; then
    echo -e "${GREEN}✓ git found${NC}"
else
    echo -e "${YELLOW}⚠️  git not found (optional)${NC}"
fi

echo ""

# Step 2: Create Virtual Environment
echo -e "${YELLOW}📦 Step 2: Setting Up Virtual Environment...${NC}"

if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists${NC}"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf venv
        python3 -m venv venv
        echo -e "${GREEN}✓ Virtual environment recreated${NC}"
    else
        echo -e "${GREEN}✓ Using existing virtual environment${NC}"
    fi
else
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate venv
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Step 3: Install Dependencies
echo -e "${YELLOW}📥 Step 3: Installing Dependencies...${NC}"

pip install --quiet --upgrade pip
echo -e "${GREEN}✓ pip upgraded${NC}"

if [ -f "requirements.txt" ]; then
    pip install --quiet -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed from requirements.txt${NC}"
elif [ -f "requirements_enhanced.txt" ]; then
    pip install --quiet -r requirements_enhanced.txt
    echo -e "${GREEN}✓ Dependencies installed from requirements_enhanced.txt${NC}"
else
    echo -e "${RED}❌ No requirements file found${NC}"
    exit 1
fi

echo ""

# Step 4: Configure Environment
echo -e "${YELLOW}🔧 Step 4: Configuring Environment...${NC}"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file from template${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env file and add your API keys${NC}"
    else
        echo -e "${YELLOW}⚠️  No .env.example found, skipping${NC}"
        echo -e "${YELLOW}   You can add API keys through the web interface${NC}"
    fi
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

echo ""

# Step 5: Run Health Checks
echo -e "${YELLOW}🏥 Step 5: Running Health Checks...${NC}"

if [ -f "health_check.py" ]; then
    if python health_check.py > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Health check passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Some health checks failed (non-critical)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  health_check.py not found, skipping${NC}"
fi

echo ""

# Step 6: Run Tests (optional)
echo -e "${YELLOW}🧪 Step 6: Running Tests...${NC}"

read -p "Do you want to run tests? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    TEST_FAILED=0
    
    if [ -f "test_token_manager.py" ]; then
        if python test_token_manager.py > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Unit tests passed${NC}"
        else
            echo -e "${RED}✗ Unit tests failed${NC}"
            TEST_FAILED=1
        fi
    fi
    
    if [ -f "smoke_test.py" ]; then
        if python smoke_test.py > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Smoke tests passed${NC}"
        else
            echo -e "${RED}✗ Smoke tests failed${NC}"
            TEST_FAILED=1
        fi
    fi
    
    if [ $TEST_FAILED -eq 1 ]; then
        echo -e "${YELLOW}⚠️  Some tests failed, but you can still proceed${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Tests skipped${NC}"
fi

echo ""

# Step 7: Deployment Choice
echo -e "${YELLOW}🚀 Step 7: Choose Deployment Method${NC}"
echo ""
echo "Select how you want to run the application:"
echo "  1) Local (streamlit run)"
echo "  2) Docker (docker-compose)"
echo "  3) Setup only (configure manually later)"
echo ""
read -p "Enter choice (1-3): " -n 1 -r DEPLOY_CHOICE
echo ""
echo ""

case $DEPLOY_CHOICE in
    1)
        echo -e "${GREEN}Starting application locally...${NC}"
        echo -e "${BLUE}========================================${NC}"
        echo -e "${BLUE}  Application will start shortly${NC}"
        echo -e "${BLUE}  Access at: http://localhost:8501${NC}"
        echo -e "${BLUE}  Press Ctrl+C to stop${NC}"
        echo -e "${BLUE}========================================${NC}"
        echo ""
        sleep 2
        streamlit run enhanced_multi_provider_manager.py
        ;;
    2)
        if ! command -v docker &> /dev/null; then
            echo -e "${RED}❌ Docker is not installed${NC}"
            echo "Please install Docker first: https://docs.docker.com/get-docker/"
            exit 1
        fi
        
        if ! command -v docker-compose &> /dev/null; then
            echo -e "${RED}❌ docker-compose is not installed${NC}"
            echo "Please install docker-compose first"
            exit 1
        fi
        
        echo -e "${GREEN}Starting with Docker...${NC}"
        docker-compose up -d
        echo ""
        echo -e "${GREEN}✓ Application started in Docker${NC}"
        echo -e "${BLUE}Access at: http://localhost:8501${NC}"
        echo ""
        echo "Useful commands:"
        echo "  docker-compose logs -f    # View logs"
        echo "  docker-compose down       # Stop application"
        echo "  docker-compose restart    # Restart application"
        ;;
    3)
        echo -e "${GREEN}✓ Setup complete!${NC}"
        echo ""
        echo "To run the application later:"
        echo "  ./start.sh"
        echo "  OR"
        echo "  source venv/bin/activate && streamlit run enhanced_multi_provider_manager.py"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Display next steps
echo -e "${YELLOW}📚 Next Steps:${NC}"
echo ""

if [ ! -f ".env" ] || ! grep -q "your_.*_key" .env 2>/dev/null; then
    echo "1. Add your API keys:"
    echo "   - Edit .env file with your API keys"
    echo "   - OR add them via the web interface (Settings tab)"
    echo ""
fi

echo "2. Explore the features:"
echo "   - 💬 Chat: Test AI providers"
echo "   - 📊 Status: Monitor usage"
echo "   - 🔧 Settings: Configure options"
echo "   - 🤖 AI Assistant: Get help with setup"
echo ""

echo "3. Documentation:"
echo "   - README.md - Overview and quick start"
echo "   - DEPLOYMENT.md - Deployment guide"
echo "   - DEPLOYMENT_CHECKLIST.md - Step-by-step deployment"
echo ""

echo -e "${GREEN}Happy coding! 🚀${NC}"
