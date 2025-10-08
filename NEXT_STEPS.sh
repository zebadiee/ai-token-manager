#!/bin/bash
# Quick action script for immediate next steps

echo "🚀 AI Token Manager - Quick Actions"
echo "==================================="
echo ""

PS3="Choose an action: "
options=(
    "Push to GitHub (recommended first)"
    "Create v2.0 release tag"
    "Test deployment locally"
    "Deploy with Docker"
    "Add GitHub badges to README"
    "Create CONTRIBUTING.md"
    "Setup issue templates"
    "Show cloud deployment options"
    "Exit"
)

select opt in "${options[@]}"
do
    case $opt in
        "Push to GitHub (recommended first)")
            echo ""
            echo "Pushing to GitHub..."
            git push origin master
            echo ""
            echo "✅ Done! Check: https://github.com/zebadiee/ai-token-manager"
            break
            ;;
        "Create v2.0 release tag")
            echo ""
            echo "Creating release tag..."
            git tag -a v2.0 -m "Production-ready v2.0 with RAG assistant"
            git push origin v2.0
            echo ""
            echo "✅ Done! Create GitHub release at:"
            echo "   https://github.com/zebadiee/ai-token-manager/releases/new?tag=v2.0"
            break
            ;;
        "Test deployment locally")
            echo ""
            echo "Testing local deployment..."
            ./setup.sh
            break
            ;;
        "Deploy with Docker")
            echo ""
            echo "Deploying with Docker..."
            docker-compose up -d
            echo ""
            echo "✅ Done! Access at: http://localhost:8501"
            echo "View logs: docker-compose logs -f"
            break
            ;;
        "Add GitHub badges to README")
            echo ""
            cat << 'BADGES'
Add these badges to the top of README.md:

[![GitHub release](https://img.shields.io/github/v/release/zebadiee/ai-token-manager)](https://github.com/zebadiee/ai-token-manager/releases)
[![Build Status](https://github.com/zebadiee/ai-token-manager/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/zebadiee/ai-token-manager/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
BADGES
            break
            ;;
        "Create CONTRIBUTING.md")
            echo ""
            echo "Creating CONTRIBUTING.md..."
            cat > CONTRIBUTING.md << 'CONTRIB'
# Contributing to AI Token Manager

Thank you for your interest in contributing! 🎉

## How to Contribute

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`python test_token_manager.py && python smoke_test.py`)
5. Commit your changes (`git commit -m 'Add some amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Development Setup

```bash
git clone https://github.com/zebadiee/ai-token-manager.git
cd ai-token-manager
./setup.sh
```

## Code Style

- Follow PEP 8
- Add docstrings to functions
- Include type hints where possible
- Run linters before committing

## Testing

All PRs must pass:
- Unit tests
- Smoke tests
- Health checks

## Reporting Bugs

Use GitHub Issues and include:
- Steps to reproduce
- Expected behavior
- Actual behavior
- System info

## Feature Requests

Open an issue with:
- Use case description
- Proposed solution
- Alternative solutions considered

## Questions?

Use GitHub Discussions for questions and ideas.

Thank you! 🚀
CONTRIB
            echo "✅ CONTRIBUTING.md created!"
            break
            ;;
        "Setup issue templates")
            echo ""
            echo "Creating issue templates..."
            mkdir -p .github/ISSUE_TEMPLATE
            
            cat > .github/ISSUE_TEMPLATE/bug_report.md << 'BUGTEMPLATE'
---
name: Bug Report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''
---

**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
 - OS: [e.g. macOS, Linux, Windows]
 - Python Version: [e.g. 3.11]
 - Deployment: [e.g. Docker, Local]

**Additional context**
Any other context about the problem.
BUGTEMPLATE

            cat > .github/ISSUE_TEMPLATE/feature_request.md << 'FEATTEMPLATE'
---
name: Feature Request
about: Suggest an idea
title: '[FEATURE] '
labels: enhancement
assignees: ''
---

**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution you'd like**
What you want to happen.

**Describe alternatives you've considered**
Alternative solutions or features.

**Additional context**
Any other context or screenshots.
FEATTEMPLATE
            
            echo "✅ Issue templates created!"
            break
            ;;
        "Show cloud deployment options")
            echo ""
            cat << 'CLOUD'
☁️  CLOUD DEPLOYMENT OPTIONS:

1. STREAMLIT CLOUD (Easiest - Free Tier)
   → https://share.streamlit.io
   Steps:
   - Sign in with GitHub
   - New app → Select repo: ai-token-manager
   - Add secrets (API keys)
   - Deploy!

2. HEROKU
   Commands:
   heroku create ai-token-manager
   git push heroku master
   heroku config:set OPENROUTER_API_KEY=xxx

3. AWS (EC2 + Docker)
   - Launch t2.micro instance
   - Install Docker: sudo yum install docker -y
   - Clone repo and run: docker-compose up -d

4. RAILWAY.APP
   → https://railway.app
   - Connect GitHub
   - Deploy from repo
   - Add environment variables

5. RENDER
   → https://render.com
   - New Web Service
   - Connect repo
   - Deploy

Choose based on:
- Budget (Streamlit/Railway have free tiers)
- Control (EC2 for full control)
- Simplicity (Streamlit is easiest)
CLOUD
            break
            ;;
        "Exit")
            echo "Goodbye! 🚀"
            break
            ;;
        *) 
            echo "Invalid option"
            ;;
    esac
done
