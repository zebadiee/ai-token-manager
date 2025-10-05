#!/bin/bash
# Quick launcher for AI Token Manager

echo "🚀 Launching AI Token Manager..."
echo ""

# Navigate to directory
cd ~/ai-token-manager

# Activate virtual environment
source venv/bin/activate

# Run Streamlit app
streamlit run enhanced_multi_provider_manager.py
