#!/usr/bin/env python3
"""
Multi-Provider Token Manager Ultimate - Complete Fixed Version
Comprehensive token management and rotation system for multiple AI API providers
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

# Set up logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('token_manager.log'),
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

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data) if data else cls()

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
    usage: TokenUsage = None

    def __post_init__(self):
        if self.usage is None:
            self.usage = TokenUsage(last_reset=datetime.now().isoformat())

class APIProvider:
    """Base class for AI API providers with robust error handling"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.last_request_time = 0
        self.request_count = 0

    def is_available(self) -> bool:
        """Check if provider is available for requests"""
        if self.config.status != "active":
            return False

        now = datetime.now()
        hour_ago = now - timedelta(hours=1)

        # Reset counters if hour has passed
        if self.config.usage.last_reset:
            try:
                last_reset = datetime.fromisoformat(self.config.usage.last_reset)
                if last_reset < hour_ago:
                    self.config.usage = TokenUsage(last_reset=now.isoformat())
                    self.request_count = 0
            except:
                self.config.usage = TokenUsage(last_reset=now.isoformat())

        # Check rate limits
        if self.config.usage.requests >= self.config.rate_limit:
            return False

        if self.config.usage.total_tokens >= self.config.token_limit:
            return False

        return True

    def get_models(self) -> Tuple[List[Dict], Optional[str]]:
        """Get available models from provider with detailed error handling"""
        try:
            headers = self.config.headers.copy()
            if self.config.api_key:
                headers['Authorization'] = f"Bearer {self.config.api_key}"
            
            url = f"{self.config.base_url}/{self.config.models_endpoint}"
            logger.info(f"Fetching models from {self.config.name}: {url}")
            
            response = requests.get(url, headers=headers, timeout=30)
            
            logger.info(f"Models response for {self.config.name}: Status {response.status_code}")
            
            if response.status_code == 401:
                return [], "Invalid API key - please check your credentials"
            elif response.status_code == 403:
                return [], "Access forbidden - check API permissions or subscription"
            elif response.status_code == 429:
                return [], "Rate limit exceeded - please try again later"
            elif response.status_code != 200:
                error_text = response.text[:300] if response.text else "Unknown error"
                return [], f"HTTP {response.status_code}: {error_text}"

            try:
                data = response.json()
            except json.JSONDecodeError:
                return [], "Invalid JSON response from API"
            
            # Handle different response formats
            if isinstance(data, list):
                models = data
            elif isinstance(data, dict):
                models = data.get('data', data.get('models', []))
            else:
                return [], f"Unexpected response format: {type(data)}"
            
            if not isinstance(models, list):
                return [], f"Models field is not a list: {type(models)}"
                
            logger.info(f"Successfully fetched {len(models)} models from {self.config.name}")
            return models, None
            
        except requests.exceptions.Timeout:
            return [], "Request timeout - API server may be slow"
        except requests.exceptions.ConnectionError:
            return [], "Connection error - check internet connection"
        except Exception as e:
            logger.error(f"Unexpected error fetching models from {self.config.name}: {e}")
            return [], f"Unexpected error: {str(e)}"

    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send chat completion request with error handling"""
        try:
            headers = self.config.headers.copy()
            headers['Authorization'] = f"Bearer {self.config.api_key}"
            
            data = {
                "model": model_id,
                "messages": messages,
                "max_tokens": 150
            }
            
            response = requests.post(
                f"{self.config.base_url}/{self.config.chat_endpoint}",
                headers=headers,
                json=data,
                timeout=60
            )
            
            self.config.usage.requests += 1
            
            if response.status_code == 401:
                self.config.status = "error"
                return {}, "Invalid API key"
            elif response.status_code in [402, 429]:
                self.config.status = "exhausted"
                return {}, f"Quota exhausted (HTTP {response.status_code})"
            elif response.status_code >= 400:
                return {}, f"HTTP {response.status_code}: {response.text[:200]}"

            result = response.json()
            
            # Update token usage if available
            if 'usage' in result:
                usage = result['usage']
                self.config.usage.prompt_tokens += usage.get('prompt_tokens', 0)
                self.config.usage.completion_tokens += usage.get('completion_tokens', 0)
                self.config.usage.total_tokens += usage.get('total_tokens', 0)

            return result, None
            
        except Exception as e:
            logger.error(f"Chat request failed for {self.config.name}: {e}")
            return {}, str(e)

class OpenRouterProvider(APIProvider):
    """OpenRouter API provider with proper headers"""
    
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

class HuggingFaceProvider(APIProvider):
    """Hugging Face API provider with public model listing"""
    
    def __init__(self, api_key: str):
        config = ProviderConfig(
            name="Hugging Face",
            api_key=api_key,
            base_url="https://huggingface.co/api",
            models_endpoint="models?limit=50&filter=text-generation",
            chat_endpoint="models",
            headers={
                "Content-Type": "application/json"
            },
            rate_limit=100,
            token_limit=50000
        )
        super().__init__(config)

    def get_models(self) -> Tuple[List[Dict], Optional[str]]:
        """Get HuggingFace models without authentication for public listing"""
        try:
            # Use public API without auth for model listing
            url = f"{self.config.base_url}/{self.config.models_endpoint}"
            logger.info(f"Fetching HF models from: {url}")
            
            response = requests.get(url, timeout=30)
            
            if response.status_code != 200:
                return [], f"HTTP {response.status_code}: {response.text[:300]}"

            models = response.json()
            
            if not isinstance(models, list):
                return [], f"Expected list, got {type(models)}"
            
            # Filter for text generation models and add required fields
            filtered_models = []
            for model in models[:30]:  # Limit to 30 models
                if isinstance(model, dict):
                    # Ensure model has an id field
                    if 'id' not in model and 'modelId' in model:
                        model['id'] = model['modelId']
                    elif 'id' not in model and 'name' in model:
                        model['id'] = model['name']
                    
                    filtered_models.append(model)
            
            logger.info(f"Found {len(filtered_models)} HuggingFace models")
            return filtered_models, None
            
        except Exception as e:
            logger.error(f"Error fetching HF models: {e}")
            return [], str(e)

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
    """Main token management system with persistence"""
    
    def __init__(self):
        self.providers: List[APIProvider] = []
        self.current_provider_index = 0
        self.config_file = ".token_manager_config.json"
        self.load_config()
        self.load_env_keys()

    def load_env_keys(self):
        """Load API keys from environment variables if available"""
        env_keys = {
            'OPENROUTER_API_KEY': OpenRouterProvider,
            'HUGGINGFACE_API_KEY': HuggingFaceProvider,
            'TOGETHER_API_KEY': TogetherAIProvider
        }
        
        for env_var, provider_class in env_keys.items():
            api_key = os.getenv(env_var)
            if api_key:
                provider_name = provider_class.__name__.replace('Provider', '')
                # Check if provider already exists
                if not any(p.config.name == provider_name for p in self.providers):
                    try:
                        provider = provider_class(api_key)
                        self.providers.append(provider)
                        logger.info(f"Loaded {provider.config.name} from environment variable {env_var}")
                    except Exception as e:
                        logger.error(f"Failed to load {provider_class.__name__} from env: {e}")

    def add_provider(self, provider: APIProvider):
        """Add a new provider to the rotation"""
        # Check if provider already exists
        existing = next((p for p in self.providers if p.config.name == provider.config.name), None)
        if existing:
            # Update existing provider
            existing.config.api_key = provider.config.api_key
            existing.config.status = "active"
            logger.info(f"Updated provider: {provider.config.name}")
        else:
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

    def get_all_models(self) -> Dict[str, List[Dict]]:
        """Get models from all providers with error handling"""
        all_models = {}
        for provider in self.providers:
            if provider.config.status == "active":
                try:
                    models, error = provider.get_models()
                    if not error and models:
                        all_models[provider.config.name] = models
                        logger.info(f"Successfully loaded {len(models)} models from {provider.config.name}")
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
        """Save configuration to file with basic encoding"""
        config_data = {
            'providers': [],
            'current_provider_index': self.current_provider_index,
            'version': '1.0',
            'saved_at': datetime.now().isoformat()
        }

        for provider in self.providers:
            try:
                # Simple base64 encoding for minimal obfuscation
                import base64
                encoded_key = base64.b64encode(provider.config.api_key.encode()).decode()
                
                provider_data = {
                    'name': provider.config.name,
                    'api_key': encoded_key,
                    'base_url': provider.config.base_url,
                    'models_endpoint': provider.config.models_endpoint,
                    'chat_endpoint': provider.config.chat_endpoint,
                    'headers': provider.config.headers,
                    'rate_limit': provider.config.rate_limit,
                    'token_limit': provider.config.token_limit,
                    'status': provider.config.status,
                    'usage': provider.config.usage.to_dict()
                }
                config_data['providers'].append(provider_data)
            except Exception as e:
                logger.error(f"Failed to serialize provider {provider.config.name}: {e}")

        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            logger.info(f"Saved config with {len(self.providers)} providers")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def load_config(self):
        """Load configuration from file"""
        if not os.path.exists(self.config_file):
            return

        try:
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)

            self.current_provider_index = config_data.get('current_provider_index', 0)
            
            # Load providers
            for provider_data in config_data.get('providers', []):
                try:
                    # Decode API key
                    try:
                        import base64
                        api_key = base64.b64decode(provider_data['api_key']).decode()
                    except:
                        # Fallback for unencoded keys
                        api_key = provider_data['api_key']
                    
                    # Create provider based on name
                    if provider_data['name'] == 'OpenRouter':
                        provider = OpenRouterProvider(api_key)
                    elif provider_data['name'] == 'Hugging Face':
                        provider = HuggingFaceProvider(api_key)
                    elif provider_data['name'] == 'Together AI':
                        provider = TogetherAIProvider(api_key)
                    else:
                        continue

                    # Restore configuration
                    provider.config.status = provider_data.get('status', 'active')
                    if 'usage' in provider_data:
                        provider.config.usage = TokenUsage.from_dict(provider_data['usage'])

                    self.providers.append(provider)
                    
                except Exception as e:
                    logger.error(f"Failed to load provider {provider_data.get('name', 'unknown')}: {e}")

            logger.info(f"Loaded {len(self.providers)} providers from config")
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

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

class MultiProviderGUI:
    """Stable GUI application with proper error handling"""
    
    def __init__(self):
        self.token_manager = TokenManager()
        self.running = True
        
        # Initialize Tkinter
        self.root = tk.Tk()
        self.root.title("Multi-Provider Token Manager Ultimate")
        self.root.geometry("1400x900")
        
        # Handle window closing properly
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Initialize all variables first
        self.model_var = tk.StringVar()
        self.provider_type_var = tk.StringVar(value="OpenRouter")
        self.api_key_var = tk.StringVar()
        self.show_key_var = tk.BooleanVar()
        self.status_var = tk.StringVar()
        self.current_provider_var = tk.StringVar()
        self.token_usage_var = tk.StringVar()
        
        # Setup GUI
        self.setup_gui()
        
        # Start background tasks
        self.start_background_tasks()
        
        # Load initial data
        self.refresh_providers_list()
        self.refresh_status()

    def setup_gui(self):
        """Setup the GUI interface"""
        # Create menu bar
        self.setup_menu()
        
        # Create main notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Setup all tabs
        self.setup_providers_tab()
        self.setup_chat_tab()
        self.setup_status_tab()
        self.setup_settings_tab()

        # Status bar
        self.status_var.set("Ready - Load API keys from environment or add manually")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief='sunken')
        self.status_bar.pack(side='bottom', fill='x')

    def setup_menu(self):
        """Setup menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Save Configuration", command=self.save_config)
        file_menu.add_command(label="Load Configuration", command=self.load_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def setup_providers_tab(self):
        """Setup providers management tab"""
        self.providers_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.providers_frame, text="Providers")

        # Create main paned window
        paned = ttk.PanedWindow(self.providers_frame, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=5, pady=5)

        # Left panel - provider list
        left_frame = ttk.LabelFrame(paned, text="Configured Providers")
        paned.add(left_frame, weight=2)

        # Provider list with scrollbar
        list_container = ttk.Frame(left_frame)
        list_container.pack(fill='both', expand=True, padx=5, pady=5)

        self.providers_listbox = tk.Listbox(list_container, font=('Courier', 10))
        scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.providers_listbox.yview)
        self.providers_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.providers_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Right panel - controls
        right_frame = ttk.LabelFrame(paned, text="Provider Management")
        paned.add(right_frame, weight=1)

        # Provider type selection
        ttk.Label(right_frame, text="Provider Type:").pack(anchor='w', padx=5, pady=(10,0))
        type_combo = ttk.Combobox(
            right_frame, 
            textvariable=self.provider_type_var,
            values=["OpenRouter", "Hugging Face", "Together AI"], 
            state='readonly'
        )
        type_combo.pack(fill='x', padx=5, pady=2)

        # API key input
        ttk.Label(right_frame, text="API Key:").pack(anchor='w', padx=5, pady=(10,0))
        self.api_key_entry = ttk.Entry(right_frame, textvariable=self.api_key_var, show='*', width=40)
        self.api_key_entry.pack(fill='x', padx=5, pady=2)

        # Show/hide key checkbox
        ttk.Checkbutton(
            right_frame, 
            text="Show API Key", 
            variable=self.show_key_var,
            command=self.toggle_key_visibility
        ).pack(anchor='w', padx=5, pady=2)

        # Buttons
        buttons_frame = ttk.Frame(right_frame)
        buttons_frame.pack(fill='x', padx=5, pady=10)

        ttk.Button(buttons_frame, text="Add Provider", command=self.add_provider).pack(fill='x', pady=2)
        ttk.Button(buttons_frame, text="Test Connection", command=self.test_provider).pack(fill='x', pady=2)
        ttk.Button(buttons_frame, text="Remove Selected", command=self.remove_provider).pack(fill='x', pady=2)
        ttk.Button(buttons_frame, text="Refresh List", command=self.refresh_providers_list).pack(fill='x', pady=2)

        # Environment info
        env_info = ttk.LabelFrame(right_frame, text="Environment Variables")
        env_info.pack(fill='x', padx=5, pady=5)
        
        env_text = "API keys can be loaded from:\n• OPENROUTER_API_KEY\n• HUGGINGFACE_API_KEY\n• TOGETHER_API_KEY"
        ttk.Label(env_info, text=env_text, font=('TkDefaultFont', 8)).pack(padx=5, pady=5)

    def setup_chat_tab(self):
        """Setup chat interface tab"""
        self.chat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_frame, text="Chat")

        # Top frame for model selection
        top_frame = ttk.Frame(self.chat_frame)
        top_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(top_frame, text="Model:").pack(side='left')
        self.model_combo = ttk.Combobox(top_frame, textvariable=self.model_var, width=60, state='readonly')
        self.model_combo.pack(side='left', padx=5, fill='x', expand=True)

        ttk.Button(top_frame, text="Refresh Models", command=self.refresh_models).pack(side='right', padx=5)

        # Current provider display
        ttk.Label(top_frame, textvariable=self.current_provider_var).pack(side='right', padx=10)

        # Chat area
        chat_frame = ttk.Frame(self.chat_frame)
        chat_frame.pack(fill='both', expand=True, padx=5, pady=5)

        # Messages display
        ttk.Label(chat_frame, text="Conversation:").pack(anchor='w')
        self.messages_text = scrolledtext.ScrolledText(chat_frame, height=20, state='disabled', wrap='word')
        self.messages_text.pack(fill='both', expand=True, pady=2)

        # Input area
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill='x', pady=5)

        ttk.Label(input_frame, text="Your message:").pack(anchor='w')
        self.message_text = tk.Text(input_frame, height=3, wrap='word')
        self.message_text.pack(fill='x', pady=2)

        # Send button and controls
        send_frame = ttk.Frame(input_frame)
        send_frame.pack(fill='x')

        ttk.Button(send_frame, text="Send Message", command=self.send_message).pack(side='right')
        ttk.Button(send_frame, text="Clear Chat", command=self.clear_chat).pack(side='right', padx=5)
        ttk.Label(send_frame, textvariable=self.token_usage_var).pack(side='left')

    def setup_status_tab(self):
        """Setup status monitoring tab"""
        self.status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.status_frame, text="Status")

        # Provider status table
        ttk.Label(self.status_frame, text="Provider Status:", font=('TkDefaultFont', 12, 'bold')).pack(anchor='w', padx=5, pady=5)

        # Create treeview with scrollbar
        tree_frame = ttk.Frame(self.status_frame)
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)

        columns = ('Provider', 'Status', 'Requests', 'Tokens', 'Rate Limit', 'Token Limit')
        self.status_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.status_tree.heading(col, text=col)
            self.status_tree.column(col, width=120, anchor='center')

        # Add scrollbar
        status_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.status_tree.yview)
        self.status_tree.configure(yscrollcommand=status_scrollbar.set)

        self.status_tree.pack(side='left', fill='both', expand=True)
        status_scrollbar.pack(side='right', fill='y')

        # Control buttons
        status_buttons = ttk.Frame(self.status_frame)
        status_buttons.pack(fill='x', padx=5, pady=5)

        ttk.Button(status_buttons, text="Refresh Status", command=self.refresh_status).pack(side='left', padx=5)
        ttk.Button(status_buttons, text="Reset Usage", command=self.reset_usage).pack(side='left', padx=5)

    def setup_settings_tab(self):
        """Setup settings and logs tab"""
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="Settings & Logs")

        # Log viewer
        log_frame = ttk.LabelFrame(self.settings_frame, text="Application Logs")
        log_frame.pack(fill='both', expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, state='disabled', font=('Courier', 9))
        self.log_text.pack(fill='both', expand=True, padx=5, pady=5)

        # Log control buttons
        log_buttons = ttk.Frame(log_frame)
        log_buttons.pack(fill='x', padx=5, pady=5)

        ttk.Button(log_buttons, text="Refresh Logs", command=self.refresh_logs).pack(side='left', padx=5)
        ttk.Button(log_buttons, text="Clear Logs", command=self.clear_logs).pack(side='left', padx=5)

    def start_background_tasks(self):
        """Start background update tasks"""
        def status_loop():
            while self.running:
                try:
                    time.sleep(30)  # Update every 30 seconds
                    if self.running:
                        self.root.after(0, self.refresh_status)
                except:
                    break

        self.status_thread = threading.Thread(target=status_loop, daemon=True)
        self.status_thread.start()

    def toggle_key_visibility(self):
        """Toggle API key visibility"""
        if self.show_key_var.get():
            self.api_key_entry.config(show='')
        else:
            self.api_key_entry.config(show='*')

    def add_provider(self):
        """Add new provider with validation"""
        provider_type = self.provider_type_var.get()
        api_key = self.api_key_var.get().strip()

        if not api_key:
            messagebox.showwarning("Warning", "Please enter an API key")
            return

        if len(api_key) < 10:
            messagebox.showwarning("Warning", "API key seems too short")
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
            self.status_var.set(f"Added {provider_type} provider successfully")

        except Exception as e:
            logger.error(f"Failed to add provider: {e}")
            messagebox.showerror("Error", f"Failed to add provider: {e}")

    def remove_provider(self):
        """Remove selected provider"""
        selection = self.providers_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a provider to remove")
            return

        provider_info = self.providers_listbox.get(selection[0])
        provider_name = provider_info.split(' - ')[0]
        
        result = messagebox.askyesno("Confirm", f"Remove {provider_name}?")
        if result:
            self.token_manager.remove_provider(provider_name)
            self.refresh_providers_list()
            self.status_var.set(f"Removed {provider_name}")

    def test_provider(self):
        """Test connection to selected provider"""
        selection = self.providers_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a provider to test")
            return

        provider_info = self.providers_listbox.get(selection[0])
        provider_name = provider_info.split(' - ')[0]
        provider = next((p for p in self.token_manager.providers if p.config.name == provider_name), None)

        if provider:
            def test_thread():
                try:
                    self.root.after(0, lambda: self.status_var.set(f"Testing {provider_name}..."))
                    models, error = provider.get_models()
                    
                    if error:
                        self.root.after(0, lambda: messagebox.showerror("Test Failed", f"Connection test failed:\n\n{error}"))
                        self.root.after(0, lambda: self.status_var.set(f"Test failed for {provider_name}"))
                    else:
                        self.root.after(0, lambda: messagebox.showinfo("Test Successful", f"Successfully connected to {provider_name}!\n\nFound {len(models)} models available."))
                        self.root.after(0, lambda: self.status_var.set(f"Test successful for {provider_name} - {len(models)} models"))
                except Exception as e:
                    logger.error(f"Test error: {e}")
                    self.root.after(0, lambda: messagebox.showerror("Test Error", f"Unexpected error during test:\n{e}"))

            threading.Thread(target=test_thread, daemon=True).start()

    def refresh_providers_list(self):
        """Refresh the providers list display"""
        try:
            self.providers_listbox.delete(0, tk.END)
            for provider in self.token_manager.providers:
                status_icon = "✓" if provider.config.status == "active" else "✗"
                provider_info = f"{provider.config.name} - {status_icon} {provider.config.status}"
                self.providers_listbox.insert(tk.END, provider_info)
        except Exception as e:
            logger.error(f"Error refreshing providers list: {e}")

    def refresh_models(self):
        """Refresh available models"""
        if not self.token_manager.providers:
            messagebox.showwarning("Warning", "No providers configured. Please add a provider first.")
            return

        self.status_var.set("Refreshing models...")
        self.model_combo['values'] = ["Loading..."]
        self.model_combo.set("Loading...")

        def refresh_thread():
            try:
                all_models = self.token_manager.get_all_models()
                model_options = []
                
                for provider_name, models in all_models.items():
                    provider_count = 0
                    for model in models:
                        if provider_count >= 20:  # Limit per provider
                            break
                        try:
                            # Handle different model ID fields
                            model_id = model.get('id', model.get('name', model.get('modelId', 'unknown')))
                            if model_id and model_id != 'unknown':
                                display_name = f"[{provider_name}] {model_id}"
                                model_options.append(display_name)
                                provider_count += 1
                        except Exception as e:
                            logger.error(f"Error parsing model from {provider_name}: {e}")

                self.root.after(0, lambda: self._update_models_list(model_options))
                
            except Exception as e:
                logger.error(f"Error refreshing models: {e}")
                self.root.after(0, lambda: self.status_var.set(f"Error refreshing models: Check logs"))
                self.root.after(0, lambda: self._update_models_list([]))

        threading.Thread(target=refresh_thread, daemon=True).start()

    def _update_models_list(self, models):
        """Update models list in main thread"""
        try:
            self.model_combo['values'] = models
            if models:
                self.model_combo.set(models[0])
                self.status_var.set(f"Found {len(models)} models across all providers")
            else:
                self.model_combo.set("No models available")
                self.status_var.set("No models available - check provider connections")
        except Exception as e:
            logger.error(f"Error updating models list: {e}")

    def send_message(self):
        """Send chat message"""
        model_text = self.model_var.get()
        message = self.message_text.get('1.0', tk.END).strip()

        if not model_text or model_text in ["Loading...", "No models available"]:
            messagebox.showwarning("Warning", "Please select a valid model first")
            return

        if not message:
            messagebox.showwarning("Warning", "Please enter a message")
            return

        # Extract model ID from display text
        try:
            model_id = model_text.split('] ', 1)[1]
        except:
            messagebox.showerror("Error", "Invalid model selection format")
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
                logger.error(f"Send message error: {e}")
                self.root.after(0, lambda: self.add_message("Error", f"Unexpected error: {str(e)}"))
                self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))

        threading.Thread(target=send_thread, daemon=True).start()

    def add_message(self, sender: str, content: str):
        """Add message to chat display"""
        try:
            self.messages_text.config(state='normal')
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.messages_text.insert(tk.END, f"[{timestamp}] {sender}: {content}\n\n")
            self.messages_text.config(state='disabled')
            self.messages_text.see(tk.END)
        except Exception as e:
            logger.error(f"Error adding message: {e}")

    def clear_chat(self):
        """Clear chat history"""
        try:
            self.messages_text.config(state='normal')
            self.messages_text.delete('1.0', tk.END)
            self.messages_text.config(state='disabled')
            self.status_var.set("Chat cleared")
        except Exception as e:
            logger.error(f"Error clearing chat: {e}")

    def refresh_status(self):
        """Refresh provider status display"""
        try:
            # Clear existing items
            for item in self.status_tree.get_children():
                self.status_tree.delete(item)

            # Add current status
            status_list = self.token_manager.get_provider_status()
            for status in status_list:
                self.status_tree.insert('', 'end', values=(
                    status['name'],
                    status['status'],
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
                
        except Exception as e:
            logger.error(f"Error refreshing status: {e}")

    def reset_usage(self):
        """Reset usage statistics"""
        try:
            for provider in self.token_manager.providers:
                provider.config.usage = TokenUsage(last_reset=datetime.now().isoformat())
            
            self.refresh_status()
            self.status_var.set("Usage statistics reset")
        except Exception as e:
            logger.error(f"Error resetting usage: {e}")

    def refresh_logs(self):
        """Refresh log display"""
        try:
            if os.path.exists('token_manager.log'):
                with open('token_manager.log', 'r') as f:
                    logs = f.read()
                
                # Keep only last 1000 lines
                log_lines = logs.split('\n')
                if len(log_lines) > 1000:
                    logs = '\n'.join(log_lines[-1000:])
                
                self.log_text.config(state='normal')
                self.log_text.delete('1.0', tk.END)
                self.log_text.insert('1.0', logs)
                self.log_text.config(state='disabled')
                self.log_text.see(tk.END)
        except Exception as e:
            logger.error(f"Error refreshing logs: {e}")

    def clear_logs(self):
        """Clear log file and display"""
        try:
            with open('token_manager.log', 'w') as f:
                f.write("")
            
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', tk.END)
            self.log_text.config(state='disabled')
            
            self.status_var.set("Logs cleared")
        except Exception as e:
            logger.error(f"Error clearing logs: {e}")

    def save_config(self):
        """Manual save configuration"""
        try:
            self.token_manager.save_config()
            self.status_var.set("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            self.status_var.set("Error saving configuration")

    def load_config(self):
        """Manual load configuration"""
        try:
            self.token_manager.load_config()
            self.refresh_providers_list()
            self.refresh_status()
            self.status_var.set("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.status_var.set("Error loading configuration")

    def show_about(self):
        """Show about dialog"""
        about_text = """Multi-Provider Token Manager Ultimate

A comprehensive token management system for multiple AI API providers.

Features:
• Secure API key storage with base64 encoding
• Automatic provider rotation and error handling
• Rate limiting and usage tracking
• Support for OpenRouter, Hugging Face, and Together AI
• Environment variable support for API keys
• Comprehensive logging and status monitoring
• Stable GUI with proper error handling

Version 1.0 - Ultimate Fixed Edition

For environment variables, set:
export OPENROUTER_API_KEY="your_key"
export HUGGINGFACE_API_KEY="your_key"  
export TOGETHER_API_KEY="your_key"
"""
        messagebox.showinfo("About", about_text)

    def on_closing(self):
        """Handle application closing gracefully"""
        try:
            self.running = False
            self.token_manager.save_config()
            logger.info("Application closing - config saved")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        self.root.destroy()

    def run(self):
        """Run the GUI application"""
        try:
            logger.info("Starting Multi-Provider Token Manager Ultimate")
            self.refresh_logs()  # Load logs on startup
            self.root.mainloop()
        except Exception as e:
            logger.error(f"GUI error: {e}")
            messagebox.showerror("Critical Error", f"Application error: {e}")

def main():
    """Main entry point with dependency checking"""
    try:
        # Check for required dependencies
        try:
            import requests
        except ImportError:
            print("Missing dependency: requests")
            print("Please install: pip install requests")
            sys.exit(1)

        logger.info("Starting Multi-Provider Token Manager Ultimate...")
        
        # Show startup info
        print("Multi-Provider Token Manager Ultimate")
        print("=====================================")
        print("Starting application...")
        print("Logs will be written to: token_manager.log")
        print("Config will be saved to: .token_manager_config.json")
        print()
        print("Environment variables (optional):")
        print("• OPENROUTER_API_KEY")
        print("• HUGGINGFACE_API_KEY")
        print("• TOGETHER_API_KEY")
        print()
        
        app = MultiProviderGUI()
        app.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"Error starting application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()