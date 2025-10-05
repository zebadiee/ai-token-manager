#!/usr/bin/env python3
"""
Multi-Provider Token Manager - Robust Version
Comprehensive token management and rotation system for multiple AI API providers
Supports OpenRouter, Hugging Face, Together AI with proper error handling and persistence
"""

import os
import sys
import json
import time
import threading
import requests
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from cryptography.fernet import Fernet
import base64

# Setup file logging
log_file = os.path.join(os.path.expanduser('~'), 'token_manager.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
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
    last_reset: Optional[str] = None

    def __post_init__(self):
        if self.last_reset is None:
            self.last_reset = datetime.now().isoformat()

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
    status: str = "active"
    usage: Optional[TokenUsage] = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = TokenUsage()

class EncryptionManager:
    """Handles encryption/decryption of API keys"""
    
    def __init__(self):
        self.key_file = os.path.join(os.path.expanduser('~'), '.token_manager_key')
        self.key = self._get_or_create_key()
        self.cipher = Fernet(self.key)

    def _get_or_create_key(self) -> bytes:
        """Get existing key or create new one"""
        try:
            if os.path.exists(self.key_file):
                with open(self.key_file, 'rb') as f:
                    return f.read()
            else:
                key = Fernet.generate_key()
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                os.chmod(self.key_file, 0o600)  # Read/write for owner only
                return key
        except Exception as e:
            logger.error(f"Error managing encryption key: {e}")
            # Return a default key if file operations fail
            return Fernet.generate_key()

    def encrypt(self, text: str) -> str:
        """Encrypt text and return base64 encoded string"""
        try:
            encrypted = self.cipher.encrypt(text.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return text  # Return plain text as fallback

    def decrypt(self, encrypted_text: str) -> str:
        """Decrypt base64 encoded encrypted text"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_text.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return encrypted_text  # Return as-is if decryption fails

class APIProvider:
    """Base class for AI API providers"""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.last_request_time = 0

    def is_available(self) -> bool:
        """Check if provider is available for requests"""
        if self.config.status != "active":
            return False

        now = datetime.now()
        try:
            last_reset = datetime.fromisoformat(self.config.usage.last_reset)
            hour_ago = now - timedelta(hours=1)

            # Reset counters if hour has passed
            if last_reset < hour_ago:
                self.config.usage = TokenUsage()
        except Exception:
            self.config.usage = TokenUsage()

        # Check rate limits
        if self.config.usage.requests >= self.config.rate_limit:
            return False

        if self.config.usage.total_tokens >= self.config.token_limit:
            return False

        return True

    def make_request(self, endpoint: str, data: Dict = None, method: str = "GET", timeout: int = 60) -> Tuple[Dict, Optional[str]]:
        """Make API request with error handling"""
        try:
            headers = self.config.headers.copy()
            headers['Authorization'] = f"Bearer {self.config.api_key}"

            url = f"{self.config.base_url}/{endpoint}"
            
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=timeout)

            self.config.usage.requests += 1

            logger.info(f"API Request to {self.config.name}: {response.status_code}")

            if response.status_code == 401:
                self.config.status = "error"
                error_msg = "Invalid API key"
                logger.error(f"{self.config.name}: {error_msg}")
                return {}, error_msg

            elif response.status_code in [402, 429]:
                self.config.status = "exhausted"
                error_msg = f"Quota exhausted (HTTP {response.status_code})"
                logger.warning(f"{self.config.name}: {error_msg}")
                return {}, error_msg

            elif response.status_code >= 400:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"{self.config.name}: {error_msg}")
                return {}, error_msg

            try:
                result = response.json()
            except json.JSONDecodeError:
                result = {"text": response.text}

            # Update token usage if available
            if 'usage' in result:
                usage = result['usage']
                self.config.usage.prompt_tokens += usage.get('prompt_tokens', 0)
                self.config.usage.completion_tokens += usage.get('completion_tokens', 0)
                self.config.usage.total_tokens += usage.get('total_tokens', 0)

            return result, None

        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            logger.error(f"{self.config.name}: {error_msg}")
            return {}, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error"
            logger.error(f"{self.config.name}: {error_msg}")
            return {}, error_msg
        except Exception as e:
            error_msg = str(e)
            logger.error(f"{self.config.name}: {error_msg}")
            return {}, error_msg

    def get_models(self) -> Tuple[List[Dict], Optional[str]]:
        """Get available models from provider"""
        try:
            result, error = self.make_request(self.config.models_endpoint, method="GET")
            if error:
                return [], error

            # Handle different response formats
            models = []
            if isinstance(result, dict):
                models = result.get('data', result.get('models', []))
            elif isinstance(result, list):
                models = result

            if not isinstance(models, list):
                return [], "Invalid models response format"

            logger.info(f"{self.config.name}: Found {len(models)} models")
            return models, None

        except Exception as e:
            error_msg = f"Error fetching models: {str(e)}"
            logger.error(f"{self.config.name}: {error_msg}")
            return [], error_msg

    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send chat completion request"""
        data = {
            "model": model_id,
            "messages": messages,
            "max_tokens": 1000
        }
        return self.make_request(self.config.chat_endpoint, data, method="POST")

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
                "HTTP-Referer": "https://localhost:3000",
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
            if pricing:
                # Check if all pricing values are 0 or None
                is_free = all(
                    str(v) == '0' or v is None or v == 0
                    for v in pricing.values()
                )
                if is_free:
                    free_models.append(model)

        logger.info(f"OpenRouter: Found {len(free_models)} free models")
        return free_models, None

class HuggingFaceProvider(APIProvider):
    """Hugging Face API provider"""

    def __init__(self, api_key: str):
        config = ProviderConfig(
            name="Hugging Face",
            api_key=api_key,
            base_url="https://api-inference.huggingface.co",
            models_endpoint="models?pipeline_tag=text-generation&sort=downloads&direction=-1&limit=50",
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
        # Convert messages to prompt for HF
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
                result, error = self.make_request(endpoint, data, method="POST")
                
                if error:
                    if "503" in error and attempt < MAX_RETRIES - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"HF model {model_id} loading, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    return {}, error

                # Convert HF response to standard format
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
                    usage = standardized['usage']
                    self.config.usage.prompt_tokens += usage['prompt_tokens']
                    self.config.usage.completion_tokens += usage['completion_tokens']
                    self.config.usage.total_tokens += usage['total_tokens']

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
        self.config_file = os.path.join(os.path.expanduser('~'), '.token_manager_config.json')
        self.encryption_manager = EncryptionManager()
        self.load_config()

    def add_provider(self, provider: APIProvider):
        """Add a new provider to the rotation"""
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
            if provider.config.status == "active":
                try:
                    models, error = provider.get_models()
                    if not error and models:
                        all_models[provider.config.name] = models
                    elif error:
                        logger.warning(f"Failed to get models from {provider.config.name}: {error}")
                except Exception as e:
                    logger.error(f"Exception getting models from {provider.config.name}: {e}")

        return all_models

    def get_provider_status(self) -> List[Dict]:
        """Get status of all providers"""
        status_list = []
        for provider in self.providers:
            status_list.append({
                'name': provider.config.name,
                'status': provider.config.status,
                'requests': provider.config.usage.requests,
                'tokens': provider.config.usage.total_tokens,
                'rate_limit': provider.config.rate_limit,
                'token_limit': provider.config.token_limit
            })
        return status_list

    def save_config(self):
        """Save configuration to encrypted file"""
        try:
            config_data = {
                'providers': [],
                'current_provider_index': self.current_provider_index
            }

            for provider in self.providers:
                provider_data = {
                    'name': provider.config.name,
                    'api_key_encrypted': self.encryption_manager.encrypt(provider.config.api_key),
                    'base_url': provider.config.base_url,
                    'models_endpoint': provider.config.models_endpoint,
                    'chat_endpoint': provider.config.chat_endpoint,
                    'headers': provider.config.headers,
                    'rate_limit': provider.config.rate_limit,
                    'token_limit': provider.config.token_limit,
                    'status': provider.config.status,
                    'usage': asdict(provider.config.usage)
                }
                config_data['providers'].append(provider_data)

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            
            logger.info(f"Configuration saved with {len(self.providers)} providers")

        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def load_config(self):
        """Load configuration from encrypted file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)

                self.current_provider_index = config_data.get('current_provider_index', 0)

                # Recreate providers
                for provider_data in config_data.get('providers', []):
                    try:
                        api_key = self.encryption_manager.decrypt(provider_data['api_key_encrypted'])
                        
                        # Create appropriate provider instance
                        if provider_data['name'] == "OpenRouter":
                            provider = OpenRouterProvider(api_key)
                        elif provider_data['name'] == "Hugging Face":
                            provider = HuggingFaceProvider(api_key)
                        elif provider_data['name'] == "Together AI":
                            provider = TogetherAIProvider(api_key)
                        else:
                            continue

                        # Restore configuration
                        provider.config.status = provider_data.get('status', 'active')
                        
                        # Restore usage data
                        if 'usage' in provider_data:
                            usage_data = provider_data['usage']
                            provider.config.usage = TokenUsage(
                                prompt_tokens=usage_data.get('prompt_tokens', 0),
                                completion_tokens=usage_data.get('completion_tokens', 0),
                                total_tokens=usage_data.get('total_tokens', 0),
                                requests=usage_data.get('requests', 0),
                                last_reset=usage_data.get('last_reset', datetime.now().isoformat())
                            )

                        self.providers.append(provider)

                    except Exception as e:
                        logger.error(f"Error loading provider {provider_data.get('name', 'unknown')}: {e}")

                logger.info(f"Configuration loaded with {len(self.providers)} providers")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")

class MultiProviderGUI:
    """Main GUI application with robust error handling"""

    def __init__(self):
        self.token_manager = TokenManager()
        self.running = True
        
        self.root = tk.Tk()
        self.root.title("Multi-Provider Token Manager")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Initialize StringVar after Tk root is created
        self.model_var = tk.StringVar()
        
        self.setup_gui()
        self.start_background_tasks()

    def setup_gui(self):
        """Setup the GUI interface"""
        # Create main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Setup tabs
        self.setup_providers_tab()
        self.setup_chat_tab()
        self.setup_status_tab()

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken')
        self.status_bar.pack(side='bottom', fill='x')

    def setup_providers_tab(self):
        """Setup providers management tab"""
        self.providers_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.providers_frame, text="Providers")

        # Left side - Provider list
        list_frame = ttk.Frame(self.providers_frame)
        list_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        ttk.Label(list_frame, text="Configured Providers:", font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')

        self.providers_listbox = tk.Listbox(list_frame)
        self.providers_listbox.pack(fill='both', expand=True, pady=5)

        # Right side - Controls
        controls_frame = ttk.Frame(self.providers_frame)
        controls_frame.pack(side='right', fill='y', padx=5, pady=5)

        ttk.Label(controls_frame, text="Add Provider:", font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')

        # Provider type selection
        ttk.Label(controls_frame, text="Type:").pack(anchor='w')
        self.provider_type_var = tk.StringVar(value="OpenRouter")
        type_combo = ttk.Combobox(controls_frame, textvariable=self.provider_type_var,
                                  values=["OpenRouter", "Hugging Face", "Together AI"], state='readonly')
        type_combo.pack(fill='x', pady=2)

        # API key input
        ttk.Label(controls_frame, text="API Key:").pack(anchor='w', pady=(10, 0))
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(controls_frame, textvariable=self.api_key_var, show='*', width=30)
        self.api_key_entry.pack(fill='x', pady=2)

        # Show/hide key
        self.show_key_var = tk.BooleanVar()
        ttk.Checkbutton(controls_frame, text="Show API Key", variable=self.show_key_var,
                        command=self.toggle_key_visibility).pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(fill='x', pady=10)

        ttk.Button(button_frame, text="Add Provider",
                   command=self.add_provider).pack(fill='x', pady=2)
        ttk.Button(button_frame, text="Remove Selected",
                   command=self.remove_provider).pack(fill='x', pady=2)
        ttk.Button(button_frame, text="Test Connection",
                   command=self.test_provider).pack(fill='x', pady=2)

        # Environment variables section
        env_frame = ttk.LabelFrame(controls_frame, text="Environment Variables")
        env_frame.pack(fill='x', pady=10)

        ttk.Button(env_frame, text="Load from ENV",
                   command=self.load_from_env).pack(fill='x', pady=2)

        self.refresh_providers_list()

    def setup_chat_tab(self):
        """Setup chat interface tab"""
        self.chat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_frame, text="Chat")

        # Top frame for model selection
        top_frame = ttk.Frame(self.chat_frame)
        top_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(top_frame, text="Model:").pack(side='left')
        self.model_combo = ttk.Combobox(top_frame, textvariable=self.model_var, width=50, state='readonly')
        self.model_combo.pack(side='left', padx=5)

        ttk.Button(top_frame, text="Refresh Models",
                   command=self.refresh_models).pack(side='left', padx=5)

        # Current provider display
        self.current_provider_var = tk.StringVar()
        ttk.Label(top_frame, textvariable=self.current_provider_var).pack(side='right')

        # Chat area
        chat_frame = ttk.Frame(self.chat_frame)
        chat_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Messages display
        ttk.Label(chat_frame, text="Conversation:").pack(anchor='w')
        self.messages_text = scrolledtext.ScrolledText(chat_frame, height=20, state='disabled')
        self.messages_text.pack(fill='both', expand=True, pady=2)

        # Input area
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill='x', pady=5)

        ttk.Label(input_frame, text="Your message:").pack(anchor='w')
        self.message_text = tk.Text(input_frame, height=3)
        self.message_text.pack(fill='x', pady=2)

        # Send button
        send_frame = ttk.Frame(input_frame)
        send_frame.pack(fill='x')

        ttk.Button(send_frame, text="Send Message",
                   command=self.send_message).pack(side='right')

        # Token usage display
        self.token_usage_var = tk.StringVar()
        ttk.Label(send_frame, textvariable=self.token_usage_var).pack(side='left')

        # Initialize empty model list
        self.model_combo['values'] = []

    def setup_status_tab(self):
        """Setup status monitoring tab"""
        self.status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.status_frame, text="Status")

        # Provider status
        ttk.Label(self.status_frame, text="Provider Status:",
                  font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', padx=5, pady=5)

        # Status table
        columns = ('Provider', 'Status', 'Requests', 'Tokens', 'Rate Limit', 'Token Limit')
        self.status_tree = ttk.Treeview(self.status_frame, columns=columns, show='headings')

        for col in columns:
            self.status_tree.heading(col, text=col)
            self.status_tree.column(col, width=120)

        self.status_tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Control buttons
        control_frame = ttk.Frame(self.status_frame)
        control_frame.pack(fill='x', padx=5, pady=5)

        ttk.Button(control_frame, text="Refresh Status",
                   command=self.refresh_status).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Reset Usage",
                   command=self.reset_usage).pack(side='left', padx=5)
        ttk.Button(control_frame, text="Exit",
                   command=self.on_closing).pack(side='right', padx=5)

    def toggle_key_visibility(self):
        """Toggle API key visibility"""
        if self.show_key_var.get():
            self.api_key_entry.config(show='')
        else:
            self.api_key_entry.config(show='*')

    def load_from_env(self):
        """Load API keys from environment variables"""
        env_keys = {
            'OPENROUTER_API_KEY': 'OpenRouter',
            'HUGGINGFACE_API_KEY': 'Hugging Face',
            'TOGETHER_API_KEY': 'Together AI'
        }

        loaded_count = 0
        for env_var, provider_name in env_keys.items():
            api_key = os.getenv(env_var)
            if api_key:
                try:
                    if provider_name == "OpenRouter":
                        provider = OpenRouterProvider(api_key)
                    elif provider_name == "Hugging Face":
                        provider = HuggingFaceProvider(api_key)
                    elif provider_name == "Together AI":
                        provider = TogetherAIProvider(api_key)
                    else:
                        continue

                    # Check if provider already exists
                    existing_names = [p.config.name for p in self.token_manager.providers]
                    if provider_name not in existing_names:
                        self.token_manager.add_provider(provider)
                        loaded_count += 1

                except Exception as e:
                    logger.error(f"Error loading {provider_name} from environment: {e}")

        if loaded_count > 0:
            self.refresh_providers_list()
            self.status_var.set(f"Loaded {loaded_count} providers from environment")
            messagebox.showinfo("Success", f"Loaded {loaded_count} providers from environment variables")
        else:
            messagebox.showwarning("No Keys Found", "No API keys found in environment variables")

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

            # Check for duplicates
            existing_names = [p.config.name for p in self.token_manager.providers]
            if provider_type in existing_names:
                messagebox.showwarning("Duplicate", f"{provider_type} provider already exists")
                return

            self.token_manager.add_provider(provider)
            self.api_key_var.set("")
            self.refresh_providers_list()
            self.status_var.set(f"Added {provider_type} provider")

        except Exception as e:
            logger.error(f"Error adding provider: {e}")
            messagebox.showerror("Error", f"Failed to add provider: {e}")

    def remove_provider(self):
        """Remove selected provider"""
        selection = self.providers_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a provider to remove")
            return

        provider_text = self.providers_listbox.get(selection[0])
        provider_name = provider_text.split(' ', 1)[1]  # Remove status icon
        
        if messagebox.askyesno("Confirm", f"Remove {provider_name} provider?"):
            self.token_manager.remove_provider(provider_name)
            self.refresh_providers_list()
            self.status_var.set(f"Removed {provider_name}")

    def test_provider(self):
        """Test connection to selected provider"""
        selection = self.providers_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a provider to test")
            return

        provider_text = self.providers_listbox.get(selection[0])
        provider_name = provider_text.split(' ', 1)[1]  # Remove status icon
        provider = next((p for p in self.token_manager.providers if p.config.name == provider_name), None)

        if provider:
            def test_thread():
                self.root.after(0, lambda: self.status_var.set(f"Testing {provider_name}..."))
                
                models, error = provider.get_models()
                
                if error:
                    self.root.after(0, lambda: messagebox.showerror("Test Failed", 
                                                                   f"Connection test failed: {error}"))
                    self.root.after(0, lambda: self.status_var.set(f"Test failed for {provider_name}"))
                else:
                    self.root.after(0, lambda: messagebox.showinfo("Test Successful", 
                                                                  f"Successfully connected! Found {len(models)} models."))
                    self.root.after(0, lambda: self.status_var.set(f"Test successful for {provider_name}"))

            threading.Thread(target=test_thread, daemon=True).start()

    def refresh_providers_list(self):
        """Refresh the providers list"""
        self.providers_listbox.delete(0, tk.END)
        for provider in self.token_manager.providers:
            status_icon = "✓" if provider.config.status == "active" else "✗"
            self.providers_listbox.insert(tk.END, f"{status_icon} {provider.config.name}")

    def refresh_models(self):
        """Refresh available models"""
        self.status_var.set("Refreshing models...")
        self.model_combo['values'] = ["Loading..."]

        def refresh_thread():
            try:
                all_models = self.token_manager.get_all_models()
                model_options = []
                
                for provider_name, models in all_models.items():
                    for model in models:
                        try:
                            model_id = model.get('id', model.get('name', 'unknown'))
                            if model_id and model_id != 'unknown':
                                display_name = f"[{provider_name}] {model_id}"
                                model_options.append(display_name)
                        except Exception as e:
                            logger.error(f"Error parsing model from {provider_name}: {e}")

                # Update GUI in main thread
                self.root.after(0, lambda: self._update_models_list(model_options))

            except Exception as e:
                logger.error(f"Error during model refresh: {e}")
                self.root.after(0, lambda: self.status_var.set(f"Error refreshing models: {e}"))
                self.root.after(0, lambda: self._update_models_list([]))

        threading.Thread(target=refresh_thread, daemon=True).start()

    def _update_models_list(self, models):
        """Update models list in main thread"""
        self.model_combo['values'] = models
        if models:
            self.model_combo.set(models[0])
        else:
            self.model_combo.set("No models available")
        
        self.status_var.set(f"Found {len(models)} models")

    def send_message(self):
        """Send chat message"""
        model_text = self.model_var.get()
        message = self.message_text.get('1.0', tk.END).strip()

        if not model_text or model_text == "No models available" or not message:
            messagebox.showwarning("Warning", "Please select a model and enter a message")
            return

        # Extract model ID from display text
        try:
            model_id = model_text.split('] ', 1)[1]
        except IndexError:
            messagebox.showerror("Error", "Invalid model selection")
            return

        # Add user message to display
        self.add_message("You", message)
        self.message_text.delete('1.0', tk.END)
        self.status_var.set("Sending message...")

        def send_thread():
            try:
                messages = [{"role": "user", "content": message}]
                response, error, provider_name = self.token_manager.send_request(model_id, messages)

                if error:
                    self.root.after(0, lambda: self.add_message("Error", error))
                    self.root.after(0, lambda: self.status_var.set(f"Error: {error}"))
                else:
                    content = response.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
                    self.root.after(0, lambda: self.add_message(f"AI ({provider_name})", content))

                    # Update token usage
                    usage = response.get('usage', {})
                    if usage:
                        usage_text = f"Tokens: {usage.get('total_tokens', 0)} (prompt: {usage.get('prompt_tokens', 0)}, completion: {usage.get('completion_tokens', 0)})"
                        self.root.after(0, lambda: self.token_usage_var.set(usage_text))

                    self.root.after(0, lambda: self.status_var.set(f"Message sent via {provider_name}"))

            except Exception as e:
                logger.error(f"Error sending message: {e}")
                self.root.after(0, lambda: self.add_message("Error", str(e)))
                self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))

        threading.Thread(target=send_thread, daemon=True).start()

    def add_message(self, sender: str, content: str):
        """Add message to chat display"""
        self.messages_text.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.messages_text.insert(tk.END, f"[{timestamp}] {sender}: {content}\n\n")
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
            self.status_tree.insert('', 'end', values=(
                status['name'],
                status['status'].title(),
                f"{status['requests']}/{status['rate_limit']}",
                f"{status['tokens']}/{status['token_limit']}",
                status['rate_limit'],
                status['token_limit']
            ))

        # Update current provider display
        current_provider = self.token_manager.get_current_provider()
        if current_provider:
            self.current_provider_var.set(f"Current: {current_provider.config.name}")
        else:
            self.current_provider_var.set("No provider available")

    def reset_usage(self):
        """Reset usage statistics for all providers"""
        if messagebox.askyesno("Confirm", "Reset usage statistics for all providers?"):
            for provider in self.token_manager.providers:
                provider.config.usage = TokenUsage()
                provider.config.status = "active"
            
            self.token_manager.save_config()
            self.refresh_status()
            self.status_var.set("Usage statistics reset")

    def start_background_tasks(self):
        """Start background status updates"""
        def update_loop():
            while self.running:
                try:
                    self.root.after(0, self.refresh_status)
                    time.sleep(10)  # Update every 10 seconds
                except Exception as e:
                    logger.error(f"Background update error: {e}")
                    time.sleep(10)

        threading.Thread(target=update_loop, daemon=True).start()

    def run(self):
        """Run the GUI application"""
        try:
            # Initial refresh
            self.refresh_providers_list()
            self.refresh_status()
            
            # Start the GUI
            self.root.mainloop()
        except Exception as e:
            logger.error(f"GUI error: {e}")
            messagebox.showerror("Error", f"Application error: {e}")

    def on_closing(self):
        """Handle application closing"""
        self.running = False
        try:
            self.token_manager.save_config()
            logger.info("Application closing, configuration saved")
        except Exception as e:
            logger.error(f"Error saving on close: {e}")
        finally:
            self.root.destroy()

def main():
    """Main entry point"""
    try:
        print("Starting Multi-Provider Token Manager...")
        logger.info("Application starting")
        
        app = MultiProviderGUI()
        app.run()
        
    except Exception as e:
        logger.error(f"Application startup error: {e}")
        print(f"Error starting application: {e}")
        
        # Show error dialog if possible
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Startup Error", f"Failed to start application:\n{e}")
        except:
            pass

if __name__ == "__main__":
    main()