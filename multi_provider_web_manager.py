#!/usr/bin/env python3
"""
Multi-Provider Token Manager - Web Interface
Stable web-based GUI using Flask for AI API provider management
Supports OpenRouter, Hugging Face, Together AI with persistent configuration
"""

import os
import json
import time
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import secrets
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProviderStatus(Enum):
    ACTIVE = "active"
    EXHAUSTED = "exhausted" 
    ERROR = "error"
    DISABLED = "disabled"

@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    last_reset: Optional[datetime] = None

@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    models_endpoint: str
    chat_endpoint: str
    headers: Dict[str, str]
    rate_limit: int = 1000
    token_limit: int = 100000
    status: ProviderStatus = ProviderStatus.ACTIVE
    usage: TokenUsage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = TokenUsage(last_reset=datetime.now())

class SecureStorage:
    """Secure storage for API keys using encryption"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = config_dir or os.path.expanduser("~/.token_manager")
        os.makedirs(self.config_dir, exist_ok=True)
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.key_file = os.path.join(self.config_dir, "key.key")
        self._ensure_key()

    def _ensure_key(self):
        """Create or load encryption key"""
        if not os.path.exists(self.key_file):
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
        else:
            with open(self.key_file, 'rb') as f:
                key = f.read()
        self.cipher = Fernet(key)

    def encrypt_key(self, api_key: str) -> str:
        """Encrypt API key"""
        return self.cipher.encrypt(api_key.encode()).decode()

    def decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API key"""
        return self.cipher.decrypt(encrypted_key.encode()).decode()

    def save_config(self, config_data: dict):
        """Save configuration with encrypted keys"""
        # Encrypt API keys before saving
        safe_config = config_data.copy()
        for provider in safe_config.get('providers', []):
            if provider.get('api_key'):
                provider['api_key'] = self.encrypt_key(provider['api_key'])
        
        with open(self.config_file, 'w') as f:
            json.dump(safe_config, f, indent=2, default=str)

    def load_config(self) -> dict:
        """Load configuration and decrypt keys"""
        if not os.path.exists(self.config_file):
            return {}
        
        with open(self.config_file, 'r') as f:
            config_data = json.load(f)
        
        # Decrypt API keys
        for provider in config_data.get('providers', []):
            if provider.get('api_key'):
                try:
                    provider['api_key'] = self.decrypt_key(provider['api_key'])
                except:
                    provider['api_key'] = ""  # Reset if decryption fails
        
        return config_data

class APIProvider:
    """Base class for AI API providers"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.last_request_time = 0
        self.request_count = 0

    def is_available(self) -> bool:
        """Check if provider is available for requests"""
        if self.config.status != ProviderStatus.ACTIVE:
            return False

        now = datetime.now()
        hour_ago = now - timedelta(hours=1)

        # Reset counters if hour has passed
        if self.config.usage.last_reset and self.config.usage.last_reset < hour_ago:
            self.config.usage = TokenUsage(last_reset=now)
            self.request_count = 0

        # Check rate limits
        if self.config.usage.requests >= self.config.rate_limit:
            return False

        if self.config.usage.total_tokens >= self.config.token_limit:
            return False

        return True

    def make_request(self, endpoint: str, data: Dict, timeout: int = 60) -> Tuple[Dict, Optional[str]]:
        """Make API request with error handling"""
        try:
            headers = self.config.headers.copy()
            headers['Authorization'] = f"Bearer {self.config.api_key}"

            response = requests.post(
                f"{self.config.base_url}/{endpoint}",
                headers=headers,
                json=data,
                timeout=timeout
            )

            self.config.usage.requests += 1

            if response.status_code == 401:
                self.config.status = ProviderStatus.ERROR
                return {}, "Invalid API key"

            elif response.status_code in [402, 429]:
                self.config.status = ProviderStatus.EXHAUSTED
                return {}, f"Quota exhausted (HTTP {response.status_code})"

            elif response.status_code >= 400:
                return {}, f"HTTP {response.status_code}: {response.text}"

            result = response.json()

            # Update token usage if available
            if 'usage' in result:
                usage = result['usage']
                self.config.usage.prompt_tokens += usage.get('prompt_tokens', 0)
                self.config.usage.completion_tokens += usage.get('completion_tokens', 0)
                self.config.usage.total_tokens += usage.get('total_tokens', 0)

            return result, None

        except requests.exceptions.Timeout:
            return {}, "Request timeout"
        except requests.exceptions.ConnectionError:
            return {}, "Connection error"
        except Exception as e:
            return {}, str(e)

    def get_models(self) -> Tuple[List[Dict], Optional[str]]:
        """Get available models from provider"""
        try:
            response = requests.get(
                f"{self.config.base_url}/{self.config.models_endpoint}",
                headers={'Authorization': f"Bearer {self.config.api_key}"},
                timeout=30
            )

            if response.status_code != 200:
                return [], f"Failed to fetch models: HTTP {response.status_code}"

            data = response.json()
            models = data.get('models', data.get('data', []))
            
            if not isinstance(models, list):
                return [], "Unexpected model list format"
                
            return models, None

        except Exception as e:
            return [], str(e)

    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send chat completion request"""
        data = {
            "model": model_id,
            "messages": messages
        }
        return self.make_request(self.config.chat_endpoint, data)

class OpenRouterProvider(APIProvider):
    """OpenRouter API provider"""
    
    def __init__(self, api_key: str):
        config = ProviderConfig(
            name="OpenRouter",
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            models_endpoint="models",
            chat_endpoint="chat/completions",
            headers={
                "Content-Type": "application/json",
                "HTTP-Referer": "https://localhost",
                "X-Title": "Multi-Provider Token Manager"
            }
        )
        super().__init__(config)

class HuggingFaceProvider(APIProvider):
    """Hugging Face API provider"""
    
    def __init__(self, api_key: str):
        config = ProviderConfig(
            name="Hugging Face",
            api_key=api_key,
            base_url="https://api-inference.huggingface.co",
            models_endpoint="models",
            chat_endpoint="models",
            headers={
                "Content-Type": "application/json"
            },
            rate_limit=100,
            token_limit=50000
        )
        super().__init__(config)

    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send request to Hugging Face model"""
        prompt = ""
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt += f"{role}: {content}\n"

        data = {"inputs": prompt}
        endpoint = f"models/{model_id}"

        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                headers = self.config.headers.copy()
                headers['Authorization'] = f"Bearer {self.config.api_key}"

                response = requests.post(
                    f"{self.config.base_url}/{endpoint}",
                    headers=headers,
                    json=data,
                    timeout=60
                )

                if response.status_code == 503 and attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue

                if response.status_code != 200:
                    return {}, f"HTTP {response.status_code}: {response.text}"

                result = response.json()
                self.config.usage.requests += 1

                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '')
                    standardized = {
                        'choices': [{
                            'message': {
                                'content': generated_text,
                                'role': 'assistant'
                            }
                        }],
                        'usage': {
                            'prompt_tokens': len(prompt.split()),
                            'completion_tokens': len(generated_text.split()),
                            'total_tokens': len(prompt.split()) + len(generated_text.split())
                        }
                    }

                    # Update usage
                    self.config.usage.prompt_tokens += standardized['usage']['prompt_tokens']
                    self.config.usage.completion_tokens += standardized['usage']['completion_tokens']
                    self.config.usage.total_tokens += standardized['usage']['total_tokens']

                    return standardized, None
                else:
                    return {}, "Unexpected response format"

            except Exception as e:
                return {}, str(e)

        return {}, "Failed after retries"

class TogetherAIProvider(APIProvider):
    """Together AI API provider"""
    
    def __init__(self, api_key: str):
        config = ProviderConfig(
            name="Together AI",
            api_key=api_key,
            base_url="https://api.together.xyz",
            models_endpoint="v1/models",
            chat_endpoint="v1/chat/completions",
            headers={
                "Content-Type": "application/json"
            },
            rate_limit=500,
            token_limit=250000
        )
        super().__init__(config)

class TokenManager:
    """Main token management system"""
    
    def __init__(self):
        self.providers: List[APIProvider] = []
        self.current_provider_index = 0
        self.storage = SecureStorage()
        self.load_config()

    def add_provider(self, provider: APIProvider):
        """Add a new provider to the rotation"""
        self.providers.append(provider)
        self.save_config()
        logger.info(f"Added provider: {provider.config.name}")

    def remove_provider(self, provider_name: str):
        """Remove provider by name"""
        self.providers = [p for p in self.providers if p.config.name != provider_name]
        self.save_config()
        logger.info(f"Removed provider: {provider_name}")

    def get_current_provider(self) -> Optional[APIProvider]:
        """Get currently active provider"""
        if not self.providers:
            return None

        for _ in range(len(self.providers)):
            provider = self.providers[self.current_provider_index]
            if provider.is_available():
                return provider
            else:
                self.rotate_provider()

        return None

    def rotate_provider(self):
        """Rotate to next provider"""
        if len(self.providers) > 1:
            self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)

    def send_request(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str], Optional[str]]:
        """Send request with automatic provider rotation"""
        provider = self.get_current_provider()
        if not provider:
            return {}, "No providers available", None

        response, error = provider.send_chat(model_id, messages)

        if error and ("quota" in error.lower() or "429" in error or "402" in error):
            self.rotate_provider()
            next_provider = self.get_current_provider()
            if next_provider and next_provider != provider:
                response, error = next_provider.send_chat(model_id, messages)
                return response, error, next_provider.config.name

        return response, error, provider.config.name

    def get_all_models(self) -> Dict[str, List[Dict]]:
        """Get models from all providers"""
        all_models = {}
        for provider in self.providers:
            if provider.config.status == ProviderStatus.ACTIVE:
                models, error = provider.get_models()
                if not error:
                    all_models[provider.config.name] = models
        return all_models

    def get_provider_status(self) -> List[Dict]:
        """Get status of all providers"""
        status_list = []
        for provider in self.providers:
            status_list.append({
                'name': provider.config.name,
                'status': provider.config.status.value,
                'requests': provider.config.usage.requests,
                'tokens': provider.config.usage.total_tokens,
                'rate_limit': provider.config.rate_limit,
                'token_limit': provider.config.token_limit
            })
        return status_list

    def save_config(self):
        """Save configuration to secure storage"""
        config_data = {
            'providers': [],
            'current_provider_index': self.current_provider_index
        }

        for provider in self.providers:
            provider_data = asdict(provider.config)
            # Remove usage data for saving
            provider_data['usage'] = None
            config_data['providers'].append(provider_data)

        self.storage.save_config(config_data)

    def load_config(self):
        """Load configuration from secure storage"""
        try:
            config_data = self.storage.load_config()
            self.current_provider_index = config_data.get('current_provider_index', 0)
            
            for provider_data in config_data.get('providers', []):
                provider_type = provider_data.get('name')
                api_key = provider_data.get('api_key')
                
                if not api_key:
                    continue
                    
                if provider_type == "OpenRouter":
                    provider = OpenRouterProvider(api_key)
                elif provider_type == "Hugging Face":
                    provider = HuggingFaceProvider(api_key)
                elif provider_type == "Together AI":
                    provider = TogetherAIProvider(api_key)
                else:
                    continue
                    
                self.providers.append(provider)
                
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

# Flask Web Application
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
token_manager = TokenManager()

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html', 
                         providers=token_manager.get_provider_status(),
                         current_provider=token_manager.get_current_provider())

@app.route('/providers')
def providers():
    """Provider management page"""
    return render_template('providers.html', 
                         providers=token_manager.get_provider_status())

@app.route('/add_provider', methods=['POST'])
def add_provider():
    """Add new provider"""
    try:
        provider_type = request.form.get('provider_type')
        api_key = request.form.get('api_key', '').strip()
        
        if not api_key:
            flash('API key is required', 'error')
            return redirect(url_for('providers'))
        
        if provider_type == "OpenRouter":
            provider = OpenRouterProvider(api_key)
        elif provider_type == "Hugging Face":
            provider = HuggingFaceProvider(api_key)
        elif provider_type == "Together AI":
            provider = TogetherAIProvider(api_key)
        else:
            flash('Unknown provider type', 'error')
            return redirect(url_for('providers'))
        
        token_manager.add_provider(provider)
        flash(f'Added {provider_type} provider successfully', 'success')
        
    except Exception as e:
        flash(f'Failed to add provider: {str(e)}', 'error')
    
    return redirect(url_for('providers'))

@app.route('/remove_provider/<provider_name>')
def remove_provider(provider_name):
    """Remove provider"""
    try:
        token_manager.remove_provider(provider_name)
        flash(f'Removed {provider_name} successfully', 'success')
    except Exception as e:
        flash(f'Failed to remove provider: {str(e)}', 'error')
    
    return redirect(url_for('providers'))

@app.route('/test_provider/<provider_name>')
def test_provider(provider_name):
    """Test provider connection"""
    provider = next((p for p in token_manager.providers if p.config.name == provider_name), None)
    
    if not provider:
        return jsonify({'success': False, 'message': 'Provider not found'})
    
    models, error = provider.get_models()
    
    if error:
        return jsonify({'success': False, 'message': f'Test failed: {error}'})
    else:
        return jsonify({'success': True, 'message': f'Successfully connected! Found {len(models)} models.'})

@app.route('/chat')
def chat():
    """Chat interface"""
    return render_template('chat.html')

@app.route('/get_models')
def get_models():
    """Get all available models"""
    try:
        all_models = token_manager.get_all_models()
        model_options = []
        
        for provider_name, models in all_models.items():
            for model in models:
                model_id = model.get('id', model.get('name', 'unknown'))
                if model_id != 'unknown':
                    model_options.append({
                        'id': model_id,
                        'display': f"[{provider_name}] {model_id}",
                        'provider': provider_name
                    })
        
        return jsonify({'success': True, 'models': model_options})
    
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/send_message', methods=['POST'])
def send_message():
    """Send chat message"""
    try:
        data = request.get_json()
        model_id = data.get('model_id')
        message = data.get('message')
        
        if not model_id or not message:
            return jsonify({'success': False, 'message': 'Model and message are required'})
        
        messages = [{"role": "user", "content": message}]
        response, error, provider_name = token_manager.send_request(model_id, messages)
        
        if error:
            return jsonify({'success': False, 'message': error})
        
        content = response.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
        usage = response.get('usage', {})
        
        return jsonify({
            'success': True,
            'response': content,
            'provider': provider_name,
            'usage': usage
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/status')
def status():
    """Get current status"""
    return jsonify({
        'providers': token_manager.get_provider_status(),
        'current_provider': token_manager.get_current_provider().config.name if token_manager.get_current_provider() else None
    })

if __name__ == '__main__':
    # Create templates directory and files
    os.makedirs('templates', exist_ok=True)
    
    # Create base template
    with open('templates/base.html', 'w') as f:
        f.write("""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Provider Token Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">Token Manager</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Dashboard</a>
                <a class="nav-link" href="/providers">Providers</a>
                <a class="nav-link" href="/chat">Chat</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{% if category == 'error' %}danger{% else %}success{% endif %} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>
</body>
</html>""")

    # Create index template
    with open('templates/index.html', 'w') as f:
        f.write("""{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-8">
        <h2>Dashboard</h2>
        <div class="card">
            <div class="card-header">
                <h5>Provider Status</h5>
            </div>
            <div class="card-body">
                {% if providers %}
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Provider</th>
                                    <th>Status</th>
                                    <th>Requests</th>
                                    <th>Tokens</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for provider in providers %}
                                <tr>
                                    <td>{{ provider.name }}</td>
                                    <td>
                                        <span class="badge bg-{% if provider.status == 'active' %}success{% elif provider.status == 'exhausted' %}warning{% else %}danger{% endif %}">
                                            {{ provider.status }}
                                        </span>
                                    </td>
                                    <td>{{ provider.requests }}/{{ provider.rate_limit }}</td>
                                    <td>{{ provider.tokens }}/{{ provider.token_limit }}</td>
                                    <td>
                                        <button class="btn btn-sm btn-primary" onclick="testProvider('{{ provider.name }}')">Test</button>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <p>No providers configured. <a href="/providers">Add some providers</a> to get started.</p>
                {% endif %}
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card">
            <div class="card-header">
                <h5>Current Provider</h5>
            </div>
            <div class="card-body">
                {% if current_provider %}
                    <p><strong>{{ current_provider.config.name }}</strong></p>
                    <p>Status: <span class="badge bg-{% if current_provider.config.status.value == 'active' %}success{% else %}danger{% endif %}">{{ current_provider.config.status.value }}</span></p>
                {% else %}
                    <p>No provider available</p>
                {% endif %}
            </div>
        </div>
        
        <div class="card mt-3">
            <div class="card-header">
                <h5>Quick Actions</h5>
            </div>
            <div class="card-body">
                <div class="d-grid gap-2">
                    <a href="/providers" class="btn btn-primary">Manage Providers</a>
                    <a href="/chat" class="btn btn-success">Start Chat</a>
                    <button class="btn btn-info" onclick="refreshStatus()">Refresh Status</button>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function testProvider(providerName) {
    fetch(`/test_provider/${providerName}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Test successful: ' + data.message);
            } else {
                alert('Test failed: ' + data.message);
            }
        });
}

function refreshStatus() {
    location.reload();
}
</script>
{% endblock %}""")

    # Create providers template
    with open('templates/providers.html', 'w') as f:
        f.write("""{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-8">
        <h2>Provider Management</h2>
        <div class="card">
            <div class="card-header">
                <h5>Configured Providers</h5>
            </div>
            <div class="card-body">
                {% if providers %}
                    <div class="table-responsive">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Provider</th>
                                    <th>Status</th>
                                    <th>Usage</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for provider in providers %}
                                <tr>
                                    <td>{{ provider.name }}</td>
                                    <td>
                                        <span class="badge bg-{% if provider.status == 'active' %}success{% elif provider.status == 'exhausted' %}warning{% else %}danger{% endif %}">
                                            {{ provider.status }}
                                        </span>
                                    </td>
                                    <td>
                                        <small>
                                            Requests: {{ provider.requests }}/{{ provider.rate_limit }}<br>
                                            Tokens: {{ provider.tokens }}/{{ provider.token_limit }}
                                        </small>
                                    </td>
                                    <td>
                                        <button class="btn btn-sm btn-primary" onclick="testProvider('{{ provider.name }}')">Test</button>
                                        <a href="/remove_provider/{{ provider.name }}" class="btn btn-sm btn-danger" onclick="return confirm('Are you sure?')">Remove</a>
                                    </td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <p>No providers configured yet.</p>
                {% endif %}
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card">
            <div class="card-header">
                <h5>Add New Provider</h5>
            </div>
            <div class="card-body">
                <form method="POST" action="/add_provider">
                    <div class="mb-3">
                        <label for="provider_type" class="form-label">Provider Type</label>
                        <select class="form-select" name="provider_type" id="provider_type" required>
                            <option value="">Select Provider</option>
                            <option value="OpenRouter">OpenRouter</option>
                            <option value="Hugging Face">Hugging Face</option>
                            <option value="Together AI">Together AI</option>
                        </select>
                    </div>
                    
                    <div class="mb-3">
                        <label for="api_key" class="form-label">API Key</label>
                        <div class="input-group">
                            <input type="password" class="form-control" name="api_key" id="api_key" required>
                            <button class="btn btn-outline-secondary" type="button" onclick="toggleKeyVisibility()">
                                <span id="toggle-icon">👁️</span>
                            </button>
                        </div>
                        <div class="form-text">Your API key will be encrypted and stored securely.</div>
                    </div>
                    
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">Add Provider</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>

<script>
function testProvider(providerName) {
    fetch(`/test_provider/${providerName}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('✅ ' + data.message);
            } else {
                alert('❌ ' + data.message);
            }
        });
}

function toggleKeyVisibility() {
    const keyInput = document.getElementById('api_key');
    const toggleIcon = document.getElementById('toggle-icon');
    
    if (keyInput.type === 'password') {
        keyInput.type = 'text';
        toggleIcon.textContent = '🙈';
    } else {
        keyInput.type = 'password';
        toggleIcon.textContent = '👁️';
    }
}
</script>
{% endblock %}""")

    # Create chat template
    with open('templates/chat.html', 'w') as f:
        f.write("""{% extends "base.html" %}

{% block content %}
<div class="row">
    <div class="col-md-12">
        <h2>AI Chat Interface</h2>
        
        <div class="card">
            <div class="card-header">
                <div class="row align-items-center">
                    <div class="col-md-6">
                        <div class="input-group">
                            <label class="input-group-text" for="model-select">Model:</label>
                            <select class="form-select" id="model-select">
                                <option value="">Loading models...</option>
                            </select>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <button class="btn btn-primary" onclick="loadModels()">Refresh Models</button>
                    </div>
                    <div class="col-md-2">
                        <span class="badge bg-info" id="current-provider">No Provider</span>
                    </div>
                </div>
            </div>
            
            <div class="card-body">
                <div id="chat-messages" style="height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 15px; margin-bottom: 15px; background-color: #f8f9fa;">
                    <div class="text-muted">Select a model and start chatting...</div>
                </div>
                
                <div class="input-group">
                    <textarea class="form-control" id="message-input" placeholder="Type your message here..." rows="3"></textarea>
                    <button class="btn btn-success" onclick="sendMessage()" id="send-btn">Send</button>
                </div>
                
                <div class="mt-2">
                    <small class="text-muted" id="token-usage"></small>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
let currentModels = [];

function loadModels() {
    document.getElementById('model-select').innerHTML = '<option value="">Loading models...</option>';
    
    fetch('/get_models')
        .then(response => response.json())
        .then(data => {
            const select = document.getElementById('model-select');
            select.innerHTML = '';
            
            if (data.success) {
                currentModels = data.models;
                if (data.models.length === 0) {
                    select.innerHTML = '<option value="">No models available</option>';
                } else {
                    select.innerHTML = '<option value="">Select a model...</option>';
                    data.models.forEach(model => {
                        const option = document.createElement('option');
                        option.value = model.id;
                        option.textContent = model.display;
                        select.appendChild(option);
                    });
                }
            } else {
                select.innerHTML = '<option value="">Error loading models</option>';
                console.error('Failed to load models:', data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('model-select').innerHTML = '<option value="">Error loading models</option>';
        });
}

function sendMessage() {
    const modelSelect = document.getElementById('model-select');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    
    const modelId = modelSelect.value;
    const message = messageInput.value.trim();
    
    if (!modelId || !message) {
        alert('Please select a model and enter a message');
        return;
    }
    
    // Disable send button and show loading
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending...';
    
    // Add user message to chat
    addMessage('You', message, 'user');
    messageInput.value = '';
    
    // Send request
    fetch('/send_message', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            model_id: modelId,
            message: message
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            addMessage(`AI (${data.provider})`, data.response, 'assistant');
            
            // Update token usage
            if (data.usage) {
                const usage = `Tokens: ${data.usage.total_tokens || 0} (prompt: ${data.usage.prompt_tokens || 0}, completion: ${data.usage.completion_tokens || 0})`;
                document.getElementById('token-usage').textContent = usage;
            }
            
            // Update current provider
            document.getElementById('current-provider').textContent = data.provider;
        } else {
            addMessage('Error', data.message, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        addMessage('Error', 'Failed to send message: ' + error.message, 'error');
    })
    .finally(() => {
        // Re-enable send button
        sendBtn.disabled = false;
        sendBtn.textContent = 'Send';
    });
}

function addMessage(sender, content, type) {
    const chatMessages = document.getElementById('chat-messages');
    const timestamp = new Date().toLocaleTimeString();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `mb-3 p-2 rounded ${type === 'user' ? 'bg-primary text-white ms-5' : type === 'error' ? 'bg-danger text-white' : 'bg-light me-5'}`;
    
    messageDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-start">
            <strong>${sender}</strong>
            <small class="opacity-75">${timestamp}</small>
        </div>
        <div class="mt-1">${content.replace(/\n/g, '<br>')}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Allow Enter to send message (Shift+Enter for new line)
document.getElementById('message-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Load models when page loads
window.addEventListener('load', loadModels);
</script>
{% endblock %}""")

    print("Starting Multi-Provider Token Manager Web Interface...")
    print("📱 Web interface will be available at: http://localhost:8080")
    print("🔐 Your API keys will be encrypted and stored securely")
    print("🔄 Configuration will persist between sessions")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")