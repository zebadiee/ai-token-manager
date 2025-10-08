# Deployment Guide - AI Token Manager

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (for cloning the repository)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/zebadiee/ai-token-manager.git
cd ai-token-manager
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Keys

#### Option A: Using Environment Variables (Recommended)

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your API keys
nano .env  # or use your preferred editor
```

#### Option B: Using the Web Interface

Start the application and add keys through the Settings tab.

## Running the Application

### Development Mode

```bash
source venv/bin/activate
streamlit run enhanced_multi_provider_manager.py
```

The application will be available at `http://localhost:8501`

### Production Deployment

#### Option 1: Streamlit Cloud

1. Push your repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repository
4. Add your API keys as secrets in Streamlit Cloud settings
5. Deploy

#### Option 2: Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "enhanced_multi_provider_manager.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:

```bash
docker build -t ai-token-manager .
docker run -p 8501:8501 -e OPENROUTER_API_KEY=your_key ai-token-manager
```

#### Option 3: Cloud Platform (AWS, GCP, Azure)

Deploy using your preferred cloud platform's app service:

**AWS (Elastic Beanstalk):**
```bash
eb init -p python-3.11 ai-token-manager
eb create ai-token-manager-env
eb deploy
```

**Google Cloud (App Engine):**

Create `app.yaml`:
```yaml
runtime: python311
entrypoint: streamlit run enhanced_multi_provider_manager.py --server.port=$PORT --server.address=0.0.0.0
```

Deploy:
```bash
gcloud app deploy
```

**Heroku:**

Create `Procfile`:
```
web: streamlit run enhanced_multi_provider_manager.py --server.port=$PORT --server.address=0.0.0.0
```

Deploy:
```bash
heroku create ai-token-manager
git push heroku main
```

## Environment Variables for Production

When deploying to production, set these environment variables:

```bash
OPENROUTER_API_KEY=your_openrouter_key
HUGGINGFACE_API_KEY=your_huggingface_key
TOGETHER_API_KEY=your_together_key
```

## Security Best Practices

1. **Never commit API keys** - Always use environment variables or secrets management
2. **Use HTTPS** - Ensure your deployment uses SSL/TLS encryption
3. **Restrict access** - Use authentication/authorization if exposing publicly
4. **Regular updates** - Keep dependencies up to date
5. **Secure storage** - API keys are encrypted at rest using Fernet encryption

## Monitoring and Maintenance

### Health Checks

The application provides built-in health monitoring through:
- Provider status indicators
- Token usage tracking
- Error logging

### Logs

Check application logs for debugging:

```bash
# Streamlit logs
tail -f ~/.streamlit/logs/streamlit.log

# Application logs (if configured)
tail -f /var/log/ai-token-manager/app.log
```

### Backup Configuration

Your configuration is stored at:
- Config: `~/.token_manager_config.json`
- Encryption key: `~/.token_manager_key`

**Backup these files regularly!**

```bash
cp ~/.token_manager_config.json ./backup/
cp ~/.token_manager_key ./backup/
```

## Troubleshooting

### Issue: Streamlit won't start

**Solution:**
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Check Python version
python --version  # Should be 3.8+
```

### Issue: API keys not working

**Solution:**
1. Verify keys are correctly set in environment variables
2. Check key permissions on provider websites
3. Review error logs for specific API errors

### Issue: Models not loading

**Solution:**
1. Check internet connectivity
2. Verify API endpoint URLs are correct
3. Ensure provider API is operational (check status pages)

### Issue: Configuration errors after upgrade

**Solution:**
```bash
# Backup and reset configuration
cp ~/.token_manager_config.json ~/.token_manager_config.json.backup
rm ~/.token_manager_config.json
# Restart the application
```

## Performance Optimization

### For Production:

1. **Enable auto-refresh** for better UX (configurable interval)
2. **Set appropriate rate limits** per provider
3. **Use caching** for model lists (built-in)
4. **Monitor token usage** to optimize costs

### Resource Requirements:

- **Minimum:** 512MB RAM, 1 CPU core
- **Recommended:** 1GB RAM, 2 CPU cores
- **Storage:** ~100MB for application + logs

## Updating the Application

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install --upgrade -r requirements.txt

# Restart the application
streamlit run enhanced_multi_provider_manager.py
```

## Support

For issues or questions:
- Check the [README.md](README.md) for usage instructions
- Review [TEST_REPORT.md](TEST_REPORT.md) for test results
- Open an issue on GitHub

## License

See LICENSE file in the repository.
