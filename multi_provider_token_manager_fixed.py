#!/usr/bin/env python3
"""Multi-Provider Token Manager - Enhanced Version

Comprehensive token management and rotation system for multiple AI API providers
Supports OpenRouter, Hugging Face, Together AI, and extensible architecture for others

Features:
- Persistent API key storage (encrypted)
- Environment variable loading
- Improved error handling
- Better GUI stability
- Graceful shutdown controls
"""
import os
import sys
import json
import time
import threading
import requests
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass, asdict
from enum import Enum
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
    rate_limit: int = 1000  # requests per hour
    token_limit: int = 100000  # tokens per hour
    status: ProviderStatus = ProviderStatus.ACTIVE
    usage: TokenUsage = None
    
    def __post_init__(self):
        if self.usage is None:
            self.usage = TokenUsage(last_reset=datetime.now())

class SecurityManager:
    """Handles encryption/decryption of API keys"""
    
    def __init__(self):
        self.key_file = ".token_manager_key"
        self.key = self._get_or_create_key()
        
    def _get_or_create_key(self) -> bytes:
        """Get existing key or create new one"""
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key
            password = "token_manager_default_key".encode()
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            
            # Save key
            with open(self.key_file, 'wb') as f:
                f.write(key)
            return key
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        try:
            f = Fernet(self.key)
            encrypted = f.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception:
            return data  # Return as-is if encryption fails
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        try:
            f = Fernet(self.key)
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = f.decrypt(decoded)
            return decrypted.decode()
        except Exception:
            return encrypted_data  # Return as-is if decryption fails

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
                return {}, f"HTTP {response.status_code}: {response.text[:200]}..."
            
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
            
            if response.status_code == 401:
                return [], "Invalid API key"
            elif response.status_code != 200:
                logger.error(f"Provider {self.config.name} failed to fetch models: HTTP {response.status_code}")
                return [], f"Failed to fetch models: HTTP {response.status_code}"
            
            data = response.json()
            models = data.get('models', data.get('data', []))
            
            if not isinstance(models, list):
                logger.error(f"Provider {self.config.name} returned unexpected model format: {type(models)}")
                return [], "Unexpected model list format"
            
            return models, None
            
        except Exception as e:
            logger.error(f"Error fetching models from {self.config.name}: {e}")
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
    
    def get_free_models(self) -> Tuple[List[Dict], Optional[str]]:
        """Get only free models from OpenRouter"""
        models, error = self.get_models()
        if error:
            return [], error
        
        free_models = []
        for model in models:
            pricing = model.get('pricing', {})
            if pricing and all(str(v) == '0' for v in pricing.values()):
                free_models.append(model)
        
        return free_models, None

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

    def get_models(self) -> Tuple[List[Dict], Optional[str]]:
        """HuggingFace has different model API structure"""
        try:
            # Get popular text generation models
            response = requests.get(
                "https://api-inference.huggingface.co/models",
                headers={'Authorization': f"Bearer {self.config.api_key}"},
                params={
                    'pipeline_tag': 'text-generation',
                    'library': 'transformers',
                    'sort': 'downloads',
                    'limit': 50
                },
                timeout=30
            )
            
            if response.status_code == 401:
                return [], "Invalid API key"
            elif response.status_code != 200:
                return [], f"Failed to fetch models: HTTP {response.status_code}"
            
            models = response.json()
            
            # Filter for models that are likely to work with chat
            chat_models = []
            for model in models:
                model_id = model.get('id', '')
                # Look for chat/instruct models
                if any(keyword in model_id.lower() for keyword in ['chat', 'instruct', 'alpaca', 'vicuna']):
                    chat_models.append({
                        'id': model_id,
                        'name': model.get('id', 'Unknown'),
                        'description': f"HF Model: {model_id}"
                    })
            
            return chat_models[:20], None  # Limit to first 20
            
        except Exception as e:
            return [], str(e)

    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send request to Hugging Face model with retry logic"""
        # Convert messages to prompt
        prompt = ""
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt += f"{role}: {content}\n"
        
        data = {"inputs": prompt, "parameters": {"max_new_tokens": 200}}
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

                if response.status_code == 503:
                    if attempt < MAX_RETRIES - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"HF model {model_id} loading. Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return {}, "Model unavailable after retries"
                
                if response.status_code != 200:
                    return {}, f"HTTP {response.status_code}: {response.text[:200]}..."

                result = response.json()
                self.config.usage.requests += 1
                
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '')
                    # Clean up the response
                    if prompt in generated_text:
                        generated_text = generated_text.replace(prompt, '').strip()
                    
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
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                    continue
                return {}, str(e)
        
        return {}, "Failed after all retries"

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
        self.config_file = "token_manager_config.json"
        self.security = SecurityManager()
        self.load_config()
        self.load_from_env()

    def load_from_env(self):
        """Load API keys from environment variables"""
        env_providers = [
            ("OPENROUTER_API_KEY", OpenRouterProvider),
            ("HUGGINGFACE_API_KEY", HuggingFaceProvider),
            ("TOGETHER_API_KEY", TogetherAIProvider)
        ]
        
        for env_key, provider_class in env_providers:
            api_key = os.getenv(env_key)
            if api_key:
                # Check if provider already exists
                provider_name = provider_class.__name__.replace('Provider', '')
                existing = any(p.config.name == provider_name for p in self.providers)
                if not existing:
                    try:
                        provider = provider_class(api_key)
                        self.providers.append(provider)
                        logger.info(f"Loaded {provider_name} from environment")
                    except Exception as e:
                        logger.error(f"Failed to load {provider_name} from env: {e}")

    def add_provider(self, provider: APIProvider):
        """Add a new provider to the rotation"""
        # Check for duplicates
        existing = any(p.config.name == provider.config.name for p in self.providers)
        if existing:
            # Replace existing
            self.providers = [p for p in self.providers if p.config.name != provider.config.name]
        
        self.providers.append(provider)
        logger.info(f"Added provider: {provider.config.name}")
        self.save_config()

    def remove_provider(self, provider_name: str):
        """Remove provider by name"""
        self.providers = [p for p in self.providers if p.config.name != provider_name]
        logger.info(f"Removed provider: {provider_name}")
        self.save_config()

    def get_current_provider(self) -> Optional[APIProvider]:
        """Get currently active provider"""
        if not self.providers:
            return None
        
        # Find next available provider
        for _ in range(len(self.providers)):
            provider = self.providers[self.current_provider_index]
            if provider.is_available():
                return provider
            else:
                logger.info(f"Provider {provider.config.name} unavailable, trying next...")
                self.rotate_provider()
        
        return None

    def rotate_provider(self):
        """Rotate to next provider"""
        if len(self.providers) > 1:
            self.current_provider_index = (self.current_provider_index + 1) % len(self.providers)
            current = self.providers[self.current_provider_index]
            logger.info(f"Rotated to provider: {current.config.name}")

    def send_request(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str], Optional[str]]:
        """Send request with automatic provider rotation"""
        provider = self.get_current_provider()
        if not provider:
            return {}, "No providers available", None
        
        response, error = provider.send_chat(model_id, messages)
        
        # If quota exhausted or error, try rotating
        if error and ("quota" in error.lower() or "429" in error or "402" in error):
            logger.warning(f"Provider {provider.config.name} quota exhausted, rotating...")
            self.rotate_provider()
            
            # Try with next provider
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
                if not error and models:
                    all_models[provider.config.name] = models
                elif error:
                    logger.warning(f"Could not fetch models from {provider.config.name}: {error}")
        
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
        """Save configuration to file with encrypted keys"""
        config_data = {
            'providers': [],
            'current_provider_index': self.current_provider_index
        }
        
        for provider in self.providers:
            provider_data = asdict(provider.config)
            # Encrypt API key
            provider_data['api_key'] = self.security.encrypt(provider.config.api_key)
            config_data['providers'].append(provider_data)
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def load_config(self):
        """Load configuration from file with decrypted keys"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                self.current_provider_index = config_data.get('current_provider_index', 0)
                
                # Load providers
                for provider_data in config_data.get('providers', []):
                    try:
                        # Decrypt API key
                        encrypted_key = provider_data.get('api_key', '')
                        if encrypted_key:
                            decrypted_key = self.security.decrypt(encrypted_key)
                            
                            # Create provider based on name
                            provider_name = provider_data.get('name', '')
                            if provider_name == "OpenRouter":
                                provider = OpenRouterProvider(decrypted_key)
                            elif provider_name == "Hugging Face":
                                provider = HuggingFaceProvider(decrypted_key)
                            elif provider_name == "Together AI":
                                provider = TogetherAIProvider(decrypted_key)
                            else:
                                continue
                            
                            # Restore usage data
                            if 'usage' in provider_data and provider_data['usage']:
                                usage_data = provider_data['usage']
                                provider.config.usage = TokenUsage(
                                    prompt_tokens=usage_data.get('prompt_tokens', 0),
                                    completion_tokens=usage_data.get('completion_tokens', 0),
                                    total_tokens=usage_data.get('total_tokens', 0),
                                    requests=usage_data.get('requests', 0),
                                    last_reset=datetime.fromisoformat(usage_data['last_reset']) if usage_data.get('last_reset') else datetime.now()
                                )
                            
                            self.providers.append(provider)
                            logger.info(f"Loaded provider: {provider_name}")
                    
                    except Exception as e:
                        logger.error(f"Failed to load provider {provider_data.get('name', 'unknown')}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

class MultiProviderGUI:
    """Enhanced GUI application with better stability"""
    
    def __init__(self):
        self.token_manager = TokenManager()
        self.running = True
        self.model_var = tk.StringVar()
        
        self.root = tk.Tk()
        self.root.title("Multi-Provider Token Manager v2.0")
        self.root.geometry("1400x900")
        
        # Configure close protocol
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.setup_gui()
        self.setup_menu()
        
        # Start status thread
        self.status_thread = threading.Thread(target=self.update_status_loop, daemon=True)
        self.status_thread.start()
        
        # Initial refresh
        self.refresh_providers_list()
        if self.token_manager.providers:
            self.refresh_models()

    def setup_menu(self):
        """Setup application menu"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export Config", command=self.export_config)
        file_menu.add_command(label="Import Config", command=self.import_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Clear All Data", command=self.clear_all_data)
        settings_menu.add_command(label="Reload from Environment", command=self.reload_from_env)

    def setup_gui(self):
        """Setup the GUI interface"""
        # Create main frames
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Providers tab
        self.providers_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.providers_frame, text="🔧 Providers")
        self.setup_providers_tab()
        
        # Chat tab
        self.chat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_frame, text="💬 Chat")
        self.setup_chat_tab()
        
        # Status tab
        self.status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.status_frame, text="📊 Status")
        self.setup_status_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - Load API keys to begin")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken')
        self.status_bar.pack(side='bottom', fill='x')

    def setup_providers_tab(self):
        """Setup providers management tab"""
        main_frame = ttk.Frame(self.providers_frame)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Left side - Provider list
        left_frame = ttk.LabelFrame(main_frame, text="Configured Providers", padding=5)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        self.providers_listbox = tk.Listbox(left_frame, height=15)
        self.providers_listbox.pack(fill='both', expand=True, pady=5)
        
        # Provider actions
        action_frame = ttk.Frame(left_frame)
        action_frame.pack(fill='x', pady=5)
        
        ttk.Button(action_frame, text="🗑️ Remove", command=self.remove_provider).pack(side='left', padx=2)
        ttk.Button(action_frame, text="🔍 Test", command=self.test_provider).pack(side='left', padx=2)
        ttk.Button(action_frame, text="🔄 Refresh List", command=self.refresh_providers_list).pack(side='left', padx=2)
        
        # Right side - Add provider
        right_frame = ttk.LabelFrame(main_frame, text="Add New Provider", padding=5)
        right_frame.pack(side='right', fill='y', padx=(5, 0))
        
        # Provider type
        ttk.Label(right_frame, text="Provider Type:").pack(anchor='w')
        self.provider_type_var = tk.StringVar(value="OpenRouter")
        type_combo = ttk.Combobox(right_frame, textvariable=self.provider_type_var,
                                 values=["OpenRouter", "Hugging Face", "Together AI"], 
                                 state='readonly', width=20)
        type_combo.pack(fill='x', pady=2)
        
        # API key input
        ttk.Label(right_frame, text="API Key:", font=('TkDefaultFont', 9, 'bold')).pack(anchor='w', pady=(10,0))
        
        # Key input frame
        key_frame = ttk.Frame(right_frame)
        key_frame.pack(fill='x', pady=2)
        
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, show='*', width=25)
        self.api_key_entry.pack(side='left', fill='x', expand=True)
        
        # Show/hide toggle
        self.show_key_var = tk.BooleanVar()
        show_btn = ttk.Checkbutton(key_frame, text="👁️", variable=self.show_key_var,
                                  command=self.toggle_key_visibility, width=3)
        show_btn.pack(side='right', padx=(2,0))
        
        # Paste button
        ttk.Button(right_frame, text="📋 Paste from Clipboard", 
                  command=self.paste_api_key).pack(fill='x', pady=2)
        
        # Add button
        ttk.Button(right_frame, text="➕ Add Provider", 
                  command=self.add_provider).pack(fill='x', pady=10)
        
        # Environment info
        env_frame = ttk.LabelFrame(right_frame, text="Environment Variables", padding=5)
        env_frame.pack(fill='x', pady=10)
        
        env_info = ttk.Label(env_frame, text="Supported environment variables:\n• OPENROUTER_API_KEY\n• HUGGINGFACE_API_KEY\n• TOGETHER_API_KEY", 
                           justify='left', font=('TkDefaultFont', 8))
        env_info.pack(anchor='w')

    def setup_chat_tab(self):
        """Setup chat interface tab"""
        # Top frame
        top_frame = ttk.Frame(self.chat_frame)
        top_frame.pack(fill='x', padx=5, pady=5)
        
        # Model selection
        model_frame = ttk.LabelFrame(top_frame, text="Model Selection", padding=5)
        model_frame.pack(fill='x', pady=2)
        
        ttk.Label(model_frame, text="Model:").pack(side='left')
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, 
                                       width=60, state='readonly')
        self.model_combo.pack(side='left', padx=5, fill='x', expand=True)
        
        ttk.Button(model_frame, text="🔄 Refresh Models", 
                  command=self.refresh_models).pack(side='left', padx=5)
        
        # Current provider
        self.current_provider_var = tk.StringVar()
        provider_label = ttk.Label(model_frame, textvariable=self.current_provider_var, 
                                  font=('TkDefaultFont', 9, 'italic'))
        provider_label.pack(side='right', padx=5)
        
        # Chat area
        chat_frame = ttk.LabelFrame(self.chat_frame, text="Conversation", padding=5)
        chat_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Messages display
        self.messages_text = scrolledtext.ScrolledText(chat_frame, height=20, state='disabled', wrap='word')
        self.messages_text.pack(fill='both', expand=True, pady=2)
        
        # Configure text tags for better formatting
        self.messages_text.tag_configure("user", foreground="blue")
        self.messages_text.tag_configure("assistant", foreground="green")
        self.messages_text.tag_configure("error", foreground="red")
        self.messages_text.tag_configure("system", foreground="gray")
        
        # Input area
        input_frame = ttk.LabelFrame(chat_frame, text="Your Message", padding=5)
        input_frame.pack(fill='x', pady=5)
        
        self.message_text = tk.Text(input_frame, height=3, wrap='word')
        self.message_text.pack(fill='x', pady=2)
        
        # Bind Enter key for sending
        self.message_text.bind('<Control-Return>', lambda e: self.send_message())
        
        # Send controls
        send_frame = ttk.Frame(input_frame)
        send_frame.pack(fill='x', pady=2)
        
        ttk.Button(send_frame, text="📤 Send (Ctrl+Enter)", 
                  command=self.send_message).pack(side='right')
        
        ttk.Button(send_frame, text="🗑️ Clear Chat", 
                  command=self.clear_chat).pack(side='right', padx=(0,5))
        
        # Token usage
        self.token_usage_var = tk.StringVar()
        ttk.Label(send_frame, textvariable=self.token_usage_var, 
                 font=('TkDefaultFont', 8)).pack(side='left')

    def setup_status_tab(self):
        """Setup status monitoring tab"""
        # Provider status
        status_frame = ttk.LabelFrame(self.status_frame, text="Provider Status", padding=5)
        status_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Status table
        columns = ('Provider', 'Status', 'Requests', 'Tokens', 'Rate Limit', 'Token Limit')
        self.status_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.status_tree.heading(col, text=col)
            self.status_tree.column(col, width=120)
        
        # Scrollbar for status tree
        status_scroll = ttk.Scrollbar(status_frame, orient='vertical', command=self.status_tree.yview)
        self.status_tree.configure(yscrollcommand=status_scroll.set)
        
        self.status_tree.pack(side='left', fill='both', expand=True)
        status_scroll.pack(side='right', fill='y')
        
        # Control buttons
        control_frame = ttk.Frame(self.status_frame)
        control_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Button(control_frame, text="🔄 Refresh Status", 
                  command=self.refresh_status).pack(side='left', padx=2)
        ttk.Button(control_frame, text="🔄 Reset Usage Counters", 
                  command=self.reset_usage_counters).pack(side='left', padx=2)
        ttk.Button(control_frame, text="💾 Save Configuration", 
                  command=self.save_configuration).pack(side='left', padx=2)

    def paste_api_key(self):
        """Paste API key from clipboard"""
        try:
            clipboard_content = self.root.clipboard_get()
            self.api_key_var.set(clipboard_content.strip())
            self.status_var.set("API key pasted from clipboard")
        except tk.TclError:
            messagebox.showwarning("Warning", "No text found in clipboard")

    def toggle_key_visibility(self):
        """Toggle API key visibility"""
        if self.show_key_var.get():
            self.api_key_entry.config(show='')
        else:
            self.api_key_entry.config(show='*')

    def add_provider(self):
        """Add new provider"""
        provider_type = self.provider_type_var.get()
        api_key = self.api_key_var.get().strip()
        
        if not api_key:
            messagebox.showwarning("Warning", "Please enter an API key")
            return
        
        try:
            if provider_type == "OpenRouter":
                provider = OpenRouterProvider(api_key)
            elif provider_type == "Hugging Face":
                provider = HuggingFaceProvider(api_key)
            elif provider_type == "Together AI":
                provider = TogetherAIProvider(api_key)
            else:
                messagebox.showerror("Error", "Unknown provider type")
                return
            
            self.token_manager.add_provider(provider)
            self.api_key_var.set("")
            self.refresh_providers_list()
            self.status_var.set(f"✅ Added {provider_type} provider")
            
            # Automatically refresh models if this is the first provider
            if len(self.token_manager.providers) == 1:
                self.refresh_models()
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add provider: {e}")

    def remove_provider(self):
        """Remove selected provider"""
        selection = self.providers_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a provider to remove")
            return
        
        provider_name = self.providers_listbox.get(selection[0])
        
        if messagebox.askyesno("Confirm", f"Remove provider '{provider_name}'?"):
            self.token_manager.remove_provider(provider_name)
            self.refresh_providers_list()
            self.status_var.set(f"🗑️ Removed {provider_name}")

    def test_provider(self):
        """Test connection to selected provider"""
        selection = self.providers_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a provider to test")
            return
        
        provider_name = self.providers_listbox.get(selection[0])
        provider = next((p for p in self.token_manager.providers if p.config.name == provider_name), None)
        
        if provider:
            def test_thread():
                self.root.after(0, lambda: self.status_var.set(f"🔍 Testing {provider_name}..."))
                
                models, error = provider.get_models()
                
                if error:
                    self.root.after(0, lambda: messagebox.showerror("Test Failed", f"Connection test failed:\n{error}"))
                    self.root.after(0, lambda: self.status_var.set(f"❌ Test failed for {provider_name}"))
                else:
                    self.root.after(0, lambda: messagebox.showinfo("Test Successful", f"✅ Successfully connected to {provider_name}!\n\nFound {len(models)} models available."))
                    self.root.after(0, lambda: self.status_var.set(f"✅ Test successful for {provider_name}"))
            
            threading.Thread(target=test_thread, daemon=True).start()

    def refresh_providers_list(self):
        """Refresh the providers list"""
        self.providers_listbox.delete(0, tk.END)
        for provider in self.token_manager.providers:
            status_icon = "🟢" if provider.config.status == ProviderStatus.ACTIVE else "🔴"
            display_name = f"{status_icon} {provider.config.name}"
            self.providers_listbox.insert(tk.END, display_name)

    def refresh_models(self):
        """Refresh available models"""
        if not self.token_manager.providers:
            self.model_combo['values'] = ["No providers configured"]
            self.model_var.set("No providers configured")
            return
        
        self.status_var.set("🔄 Refreshing models...")
        self.model_combo['values'] = ["Loading models..."]
        self.model_var.set("Loading models...")
        
        def refresh_thread():
            try:
                all_models = self.token_manager.get_all_models()
                model_options = []
                
                for provider_name, models in all_models.items():
                    for model in models:
                        try:
                            model_id = model.get('id', model.get('name', 'unknown'))
                            if model_id != 'unknown':
                                display_name = f"[{provider_name}] {model_id}"
                                model_options.append(display_name)
                        except Exception as e:
                            logger.error(f"Error parsing model from {provider_name}: {e}")
                
                # Update GUI in main thread
                self.root.after(0, lambda: self._update_models_list(model_options))
                
            except Exception as e:
                logger.error(f"Critical error during model refresh: {e}")
                self.root.after(0, lambda: self.status_var.set(f"❌ Error refreshing models"))
                self.root.after(0, lambda: self._update_models_list([]))
        
        threading.Thread(target=refresh_thread, daemon=True).start()

    def _update_models_list(self, models):
        """Update models list in main thread"""
        if models:
            self.model_combo['values'] = models
            self.model_var.set(models[0])
            self.status_var.set(f"✅ Found {len(models)} models")
        else:
            self.model_combo['values'] = ["No models available"]
            self.model_var.set("No models available")
            self.status_var.set("❌ No models found")

    def clear_chat(self):
        """Clear chat messages"""
        self.messages_text.config(state='normal')
        self.messages_text.delete('1.0', tk.END)
        self.messages_text.config(state='disabled')
        self.token_usage_var.set("")

    def send_message(self):
        """Send chat message"""
        model_text = self.model_var.get()
        message = self.message_text.get('1.0', tk.END).strip()
        
        if not model_text or model_text in ["No providers configured", "No models available", "Loading models..."]:
            messagebox.showwarning("Warning", "Please configure providers and select a model first")
            return
        
        if not message:
            messagebox.showwarning("Warning", "Please enter a message")
            return
        
        # Extract model ID from display text
        model_id = model_text.split('] ', 1)[-1] if '] ' in model_text else model_text
        
        # Add user message to display
        self.add_message("You", message, "user")
        self.message_text.delete('1.0', tk.END)
        
        self.status_var.set("📤 Sending message...")
        
        def send_thread():
            try:
                messages = [{"role": "user", "content": message}]
                response, error, provider_name = self.token_manager.send_request(model_id, messages)
                
                if error:
                    self.root.after(0, lambda: self.add_message("Error", error, "error"))
                    self.root.after(0, lambda: self.status_var.set(f"❌ Error: {error[:50]}..."))
                else:
                    content = response.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
                    self.root.after(0, lambda: self.add_message(f"AI ({provider_name})", content, "assistant"))
                    
                    # Update token usage
                    usage = response.get('usage', {})
                    if usage:
                        usage_text = f"Tokens: {usage.get('total_tokens', 0)} (prompt: {usage.get('prompt_tokens', 0)}, completion: {usage.get('completion_tokens', 0)})"
                        self.root.after(0, lambda: self.token_usage_var.set(usage_text))
                    
                    self.root.after(0, lambda: self.status_var.set(f"✅ Message sent via {provider_name}"))
                    
            except Exception as e:
                self.root.after(0, lambda: self.add_message("Error", str(e), "error"))
                self.root.after(0, lambda: self.status_var.set(f"❌ Error: {e}"))
        
        threading.Thread(target=send_thread, daemon=True).start()

    def add_message(self, sender: str, content: str, tag: str = "system"):
        """Add message to chat display with formatting"""
        self.messages_text.config(state='normal')
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        header = f"[{timestamp}] {sender}:\n"
        
        # Insert header
        self.messages_text.insert(tk.END, header, tag)
        
        # Insert content
        self.messages_text.insert(tk.END, f"{content}\n\n")
        
        self.messages_text.config(state='disabled')
        self.messages_text.see(tk.END)

    def refresh_status(self):
        """Refresh provider status display"""
        # Clear existing items
        for item in self.status_tree.get_children():
            self.status_tree.delete(item)
        
        # Add current status
        status_list = self.token_manager.get_provider_status()
        for status in status_list:
            status_icon = "🟢" if status['status'] == 'active' else "🔴"
            
            self.status_tree.insert('', 'end', values=(
                f"{status_icon} {status['name']}",
                status['status'].title(),
                f"{status['requests']}/{status['rate_limit']}",
                f"{status['tokens']}/{status['token_limit']}",
                f"{status['rate_limit']}/hour",
                f"{status['token_limit']}/hour"
            ))
        
        # Update current provider display
        current_provider = self.token_manager.get_current_provider()
        if current_provider:
            self.current_provider_var.set(f"Current: {current_provider.config.name}")
        else:
            self.current_provider_var.set("No provider available")

    def reset_usage_counters(self):
        """Reset usage counters for all providers"""
        if messagebox.askyesno("Confirm", "Reset usage counters for all providers?"):
            for provider in self.token_manager.providers:
                provider.config.usage = TokenUsage(last_reset=datetime.now())
            
            self.refresh_status()
            self.status_var.set("🔄 Usage counters reset")

    def save_configuration(self):
        """Manually save configuration"""
        self.token_manager.save_config()
        self.status_var.set("💾 Configuration saved")

    def export_config(self):
        """Export configuration to file"""
        filename = filedialog.asksaveasfilename(
            title="Export Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                self.token_manager.save_config()
                # Copy config file
                import shutil
                shutil.copy2(self.token_manager.config_file, filename)
                messagebox.showinfo("Success", f"Configuration exported to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export configuration: {e}")

    def import_config(self):
        """Import configuration from file"""
        filename = filedialog.askopenfilename(
            title="Import Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Backup current config
                backup_file = f"{self.token_manager.config_file}.backup"
                if os.path.exists(self.token_manager.config_file):
                    import shutil
                    shutil.copy2(self.token_manager.config_file, backup_file)
                
                # Copy new config
                import shutil
                shutil.copy2(filename, self.token_manager.config_file)
                
                # Reload
                self.token_manager.providers = []
                self.token_manager.load_config()
                self.refresh_providers_list()
                
                messagebox.showinfo("Success", f"Configuration imported from {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import configuration: {e}")

    def clear_all_data(self):
        """Clear all configuration data"""
        if messagebox.askyesno("Confirm", "Clear all providers and configuration data?\n\nThis action cannot be undone."):
            try:
                self.token_manager.providers = []
                if os.path.exists(self.token_manager.config_file):
                    os.remove(self.token_manager.config_file)
                
                self.refresh_providers_list()
                self.model_combo['values'] = ["No providers configured"]
                self.model_var.set("No providers configured")
                self.status_var.set("🗑️ All data cleared")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear data: {e}")

    def reload_from_env(self):
        """Reload providers from environment variables"""
        self.token_manager.load_from_env()
        self.refresh_providers_list()
        self.status_var.set("🔄 Reloaded from environment variables")

    def update_status_loop(self):
        """Background status update loop"""
        while self.running:
            try:
                if self.running:
                    self.root.after(0, self.refresh_status)
                time.sleep(30)  # Update every 30 seconds
            except:
                break

    def run(self):
        """Run the GUI application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.on_closing()

    def on_closing(self):
        """Handle application closing"""
        self.running = False
        
        try:
            self.token_manager.save_config()
            logger.info("Configuration saved on exit")
        except Exception as e:
            logger.error(f"Failed to save config on exit: {e}")
        
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass

def main():
    """Main entry point"""
    print("🚀 Starting Multi-Provider Token Manager v2.0...")
    
    try:
        app = MultiProviderGUI()
        app.run()
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()