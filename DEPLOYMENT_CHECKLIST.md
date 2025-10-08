# 🚀 Deployment Checklist - AI Token Manager

## Pre-Deployment Validation

### ✅ Step 1: Run Validation Scripts

```bash
# 1. Health check
python health_check.py

# 2. Run tests
python test_token_manager.py
python smoke_test.py

# 3. Validate deployment readiness
python validate_deployment.py
```

All checks should pass before proceeding.

### ✅ Step 2: Configuration

- [ ] Copy `.env.example` to `.env` and add your API keys
- [ ] Review `requirements.txt` - all dependencies listed
- [ ] Check `.gitignore` - sensitive files excluded
- [ ] Verify Docker configuration (if using Docker)

### ✅ Step 3: Security Check

- [ ] API keys stored as environment variables (not hardcoded)
- [ ] `.env` file in `.gitignore`
- [ ] Config files have restricted permissions (600)
- [ ] No secrets in git history

### ✅ Step 4: Choose Deployment Method

## Deployment Options

### Option 1: Local Deployment (Development/Testing)

```bash
# Quick start
./start.sh

# Or manual:
source venv/bin/activate
streamlit run enhanced_multi_provider_manager.py
```

**Best for:** Development, testing, personal use

### Option 2: Docker Deployment (Recommended for Production)

```bash
# Build and run
docker-compose up -d

# Check logs
docker-compose logs -f

# Stop
docker-compose down
```

**Best for:** Production, consistent environments, easy updates

### Option 3: Cloud Deployment

#### Streamlit Cloud (Easiest)
1. Push to GitHub
2. Visit [share.streamlit.io](https://share.streamlit.io)
3. Connect repository
4. Add secrets (API keys)
5. Deploy

#### Heroku
```bash
# Create Procfile
echo "web: streamlit run enhanced_multi_provider_manager.py --server.port=\$PORT --server.address=0.0.0.0" > Procfile

# Deploy
heroku create ai-token-manager
git push heroku main
heroku config:set OPENROUTER_API_KEY=your_key
```

#### AWS/GCP/Azure
See [DEPLOYMENT.md](DEPLOYMENT.md) for platform-specific instructions.

## Post-Deployment Checklist

### ✅ Step 5: Verify Deployment

- [ ] Application accessible at expected URL
- [ ] All tabs load without errors (Chat, Status, Settings, AI Assistant)
- [ ] Can add/remove providers
- [ ] Chat functionality works
- [ ] Settings save correctly
- [ ] RAG Assistant responds to queries

### ✅ Step 6: Configure Providers

- [ ] Add at least one provider (OpenRouter, HuggingFace, or Together AI)
- [ ] Test API connection
- [ ] Verify model loading
- [ ] Test chat completion

### ✅ Step 7: Setup Monitoring (Production)

- [ ] Configure logging (check logs directory)
- [ ] Setup health checks (if using cloud platform)
- [ ] Configure alerts for failures
- [ ] Monitor token usage and costs

### ✅ Step 8: Documentation

- [ ] Share access URL with team
- [ ] Document API key setup process
- [ ] Create backup of configuration
- [ ] Note any custom settings

## Quick Test Commands

```bash
# Test RAG Assistant
python rag_assistant.py

# Test main application syntax
python -m py_compile enhanced_multi_provider_manager.py

# Check Docker build
docker build -t ai-token-manager:test .

# Run full test suite
./run_all_tests.sh  # If available
```

## Rollback Plan

If deployment fails:

1. **Docker**: `docker-compose down && docker-compose up -d`
2. **Local**: Restore from git: `git checkout main`
3. **Cloud**: Redeploy previous version
4. **Config**: Restore from backup: `cp ~/.token_manager_config.json.backup ~/.token_manager_config.json`

## Performance Tuning

### For High Traffic:

1. **Increase resources:**
   - Docker: Update `docker-compose.yml` resource limits
   - Cloud: Scale up instance size

2. **Optimize settings:**
   - Adjust auto-refresh interval (increase for less load)
   - Enable model caching
   - Use rate limiting per provider

3. **Load balancing:**
   - Deploy multiple instances
   - Use reverse proxy (nginx/traefik)
   - Implement session affinity

## Security Hardening

### Production Security:

1. **Environment:**
   ```bash
   # Use secrets management
   export OPENROUTER_API_KEY=$(vault read -field=value secret/openrouter)
   ```

2. **Network:**
   - Enable HTTPS/TLS
   - Use firewall rules
   - Implement rate limiting

3. **Access Control:**
   - Add authentication (Streamlit auth or reverse proxy)
   - Implement role-based access
   - Log all API calls

## Maintenance Schedule

### Daily:
- [ ] Check error logs
- [ ] Monitor token usage
- [ ] Verify all providers active

### Weekly:
- [ ] Review and rotate API keys if needed
- [ ] Check for dependency updates
- [ ] Backup configuration

### Monthly:
- [ ] Update dependencies: `pip install --upgrade -r requirements.txt`
- [ ] Review security advisories
- [ ] Performance optimization

## Support & Troubleshooting

### Common Issues:

1. **Import Error:** `pip install -r requirements.txt`
2. **Permission Denied:** `chmod +x start.sh`
3. **Port Conflict:** Change port in config or use Docker
4. **API Errors:** Check API key validity and rate limits

### Getting Help:

- 📚 Check [README.md](README.md) for usage
- 🔧 Review [DEPLOYMENT.md](DEPLOYMENT.md) for detailed setup
- 🤖 Use the AI Assistant tab in the app
- 🐛 Check GitHub issues

## Success Criteria

✅ **Deployment is successful when:**

1. ✓ All validation scripts pass
2. ✓ Application loads without errors
3. ✓ At least one provider configured and working
4. ✓ Chat completions work
5. ✓ Settings persist across restarts
6. ✓ RAG Assistant provides helpful answers
7. ✓ Health checks pass
8. ✓ No security warnings

---

**Last Updated:** 2025-01-08  
**Version:** 2.0 (with RAG Assistant)
