#!/usr/bin/env python3
"""
Multi-Provider Token Manager (Improved Version)
- Fixed API key persistence via environment variables
- Improved error handling for Hugging Face models
- Enhanced GUI stability
- Added proper exit controls
"""

import os
import sys
import json
import time
import threading
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass, asdict
from enum import Enum

# Try importing tkinter, fallback to web interface if not available
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    GUI_AVAILABLE = True
except ImportError:
    print("Tkinter not available, will use web interface...")
    GUI_AVAILABLE = False

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
        if self.config.usage.last_reset < hour_ago:
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
    """Hugging Face API provider with improved error handling"""

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
        """Get popular chat models from Hugging Face"""
        # Since HF has thousands of models, we'll return a curated list of popular chat models
        popular_models = [
            {"id": "microsoft/DialoGPT-medium", "name": "DialoGPT Medium"},
            {"id": "facebook/blenderbot-400M-distill", "name": "BlenderBot 400M"},
            {"id": "microsoft/DialoGPT-large", "name": "DialoGPT Large"},
            {"id": "facebook/blenderbot-1B-distill", "name": "BlenderBot 1B"},
            {"id": "microsoft/DialoGPT-small", "name": "DialoGPT Small"},
        ]
        return popular_models, None

    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send request to Hugging Face model with retry logic"""
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
                        logger.warning(f"HF model {model_id} is loading (503). Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return {}, "Model consistently unavailable after retries (503)"

                if response.status_code == 400:
                    return {}, f"Bad request to model {model_id}. This model may not support chat completion."

                if response.status_code != 200:
                    return {}, f"HTTP {response.status_code}: {response.text}"

                result = response.json()
                self.config.usage.requests += 1

                # Convert HF response to standard format
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '')
                    # Clean up the response to remove the original prompt
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

            except requests.exceptions.Timeout:
                return {}, "Request timeout"
            except requests.exceptions.ConnectionError:
                return {}, "Connection error"
            except Exception as e:
                return {}, str(e)

        return {}, "Failed to send chat after all retries."

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
    """Main token management system with improved persistence"""

    def __init__(self):
        self.providers: List[APIProvider] = []
        self.current_provider_index = 0
        self.config_file = "token_manager_config.json"
        self.env_file = ".env"
        self.load_config()
        self.load_from_env()

    def load_from_env(self):
        """Load API keys from environment variables"""
        # Check for API keys in environment
        openrouter_key = os.getenv('OPENROUTER_API_KEY')
        hf_key = os.getenv('HF_API_KEY') or os.getenv('HUGGINGFACE_API_KEY')
        together_key = os.getenv('TOGETHER_API_KEY')

        # Auto-add providers if keys are found
        if openrouter_key and not any(p.config.name == "OpenRouter" for p in self.providers):
            self.add_provider(OpenRouterProvider(openrouter_key))
            logger.info("Auto-loaded OpenRouter from environment")

        if hf_key and not any(p.config.name == "Hugging Face" for p in self.providers):
            self.add_provider(HuggingFaceProvider(hf_key))
            logger.info("Auto-loaded Hugging Face from environment")

        if together_key and not any(p.config.name == "Together AI" for p in self.providers):
            self.add_provider(TogetherAIProvider(together_key))
            logger.info("Auto-loaded Together AI from environment")

    def save_to_env(self, provider_type: str, api_key: str):
        """Save API key to environment file"""
        env_vars = {}
        
        # Read existing .env file
        if os.path.exists(self.env_file):
            with open(self.env_file, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value

        # Update with new key
        if provider_type == "OpenRouter":
            env_vars['OPENROUTER_API_KEY'] = api_key
        elif provider_type == "Hugging Face":
            env_vars['HF_API_KEY'] = api_key
        elif provider_type == "Together AI":
            env_vars['TOGETHER_API_KEY'] = api_key

        # Write back to .env file
        with open(self.env_file, 'w') as f:
            f.write("# Multi-Provider Token Manager API Keys\n")
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")

        # Also set in current environment
        os.environ[list(env_vars.keys())[-1]] = api_key

    def add_provider(self, provider: APIProvider):
        """Add a new provider to the rotation"""
        # Remove existing provider of same type
        self.providers = [p for p in self.providers if p.config.name != provider.config.name]
        self.providers.append(provider)
        logger.info(f"Added provider: {provider.config.name}")

    def remove_provider(self, provider_name: str):
        """Remove provider by name"""
        self.providers = [p for p in self.providers if p.config.name != provider_name]
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

        if error and ("quota" in error.lower() or "429" in error or "402" in error):
            logger.warning(f"Provider {provider.config.name} quota exhausted, rotating...")
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
                else:
                    logger.warning(f"Failed to get models from {provider.config.name}: {error}")

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
        """Save configuration to file"""
        config_data = {
            'providers': [],
            'current_provider_index': self.current_provider_index
        }

        for provider in self.providers:
            provider_data = asdict(provider.config)
            # Don't save API key for security - use environment variables instead
            provider_data['api_key'] = ""
            config_data['providers'].append(provider_data)

        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                self.current_provider_index = config_data.get('current_provider_index', 0)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

if GUI_AVAILABLE:
    class MultiProviderGUI:
        """Improved GUI with better stability and controls"""

        def __init__(self):
            self.token_manager = TokenManager()
            self.running = True
            
            self.root = tk.Tk()
            self.root.title("Multi-Provider Token Manager v2.0")
            self.root.geometry("1400x900")
            
            # Initialize StringVar after root window is created
            self.model_var = tk.StringVar()
            
            # Add proper window closing protocol
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            
            self.setup_gui()
            self.status_thread = threading.Thread(target=self.update_status_loop, daemon=True)
            self.status_thread.start()

        def setup_gui(self):
            """Setup the GUI interface with improved layout"""
            # Menu bar
            menubar = tk.Menu(self.root)
            self.root.config(menu=menubar)
            
            file_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="File", menu=file_menu)
            file_menu.add_command(label="Save Config", command=self.save_config)
            file_menu.add_command(label="Load Config", command=self.load_config)
            file_menu.add_separator()
            file_menu.add_command(label="Exit", command=self.on_closing)
            
            settings_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label="Settings", menu=settings_menu)
            settings_menu.add_command(label="Environment Variables", command=self.show_env_settings)
            settings_menu.add_command(label="Provider Settings", command=self.show_provider_settings)

            # Create main frames
            self.notebook = ttk.Notebook(self.root)
            self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

            # Providers tab
            self.providers_frame = ttk.Frame(self.notebook)
            self.notebook.add(self.providers_frame, text="Providers")
            self.setup_providers_tab()

            # Chat tab
            self.chat_frame = ttk.Frame(self.notebook)
            self.notebook.add(self.chat_frame, text="Chat")
            self.setup_chat_tab()

            # Status tab
            self.status_frame = ttk.Frame(self.notebook)
            self.notebook.add(self.status_frame, text="Status")
            self.setup_status_tab()

            # Status bar
            self.status_var = tk.StringVar()
            self.status_var.set("Ready - Load API keys from environment or add providers manually")
            status_frame = ttk.Frame(self.root)
            status_frame.pack(side='bottom', fill='x')
            
            self.status_bar = ttk.Label(status_frame, textvariable=self.status_var, relief='sunken')
            self.status_bar.pack(side='left', fill='x', expand=True)
            
            # Exit button in status bar
            ttk.Button(status_frame, text="Exit", command=self.on_closing).pack(side='right', padx=5)

        def setup_providers_tab(self):
            """Setup providers management tab"""
            # Provider list
            list_frame = ttk.Frame(self.providers_frame)
            list_frame.pack(side='left', fill='both', expand=True, padx=5, pady=5)

            ttk.Label(list_frame, text="Configured Providers:", font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')

            # Listbox with scrollbar
            listbox_frame = ttk.Frame(list_frame)
            listbox_frame.pack(fill='both', expand=True, pady=5)
            
            self.providers_listbox = tk.Listbox(listbox_frame)
            scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.providers_listbox.yview)
            self.providers_listbox.configure(yscrollcommand=scrollbar.set)
            
            self.providers_listbox.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Provider controls
            controls_frame = ttk.Frame(self.providers_frame)
            controls_frame.pack(side='right', fill='y', padx=5, pady=5)

            ttk.Label(controls_frame, text="Add Provider:", font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')

            # Provider type selection
            ttk.Label(controls_frame, text="Type:").pack(anchor='w', pady=(10,0))
            self.provider_type_var = tk.StringVar(value="OpenRouter")
            type_combo = ttk.Combobox(controls_frame, textvariable=self.provider_type_var,
                                     values=["OpenRouter", "Hugging Face", "Together AI"], state='readonly', width=25)
            type_combo.pack(fill='x', pady=2)

            # API key input
            ttk.Label(controls_frame, text="API Key:").pack(anchor='w', pady=(10,0))
            self.api_key_var = tk.StringVar()
            
            key_frame = ttk.Frame(controls_frame)
            key_frame.pack(fill='x', pady=2)
            
            self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, show='*', width=30)
            self.api_key_entry.pack(side='left', fill='x', expand=True)
            
            # Show/hide key toggle
            self.show_key_var = tk.BooleanVar()
            show_btn = ttk.Checkbutton(key_frame, text="👁", variable=self.show_key_var,
                                     command=self.toggle_key_visibility, width=3)
            show_btn.pack(side='right', padx=(5,0))

            # Save to environment option
            self.save_to_env_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(controls_frame, text="Save to environment (.env file)", 
                           variable=self.save_to_env_var).pack(anchor='w', pady=5)

            # Buttons
            btn_frame = ttk.Frame(controls_frame)
            btn_frame.pack(fill='x', pady=10)
            
            ttk.Button(btn_frame, text="Add Provider", command=self.add_provider).pack(fill='x', pady=2)
            ttk.Button(btn_frame, text="Remove Selected", command=self.remove_provider).pack(fill='x', pady=2)
            ttk.Button(btn_frame, text="Test Connection", command=self.test_provider).pack(fill='x', pady=2)
            
            ttk.Separator(controls_frame, orient='horizontal').pack(fill='x', pady=10)
            
            ttk.Button(controls_frame, text="Refresh Provider List", 
                      command=self.refresh_providers_list).pack(fill='x', pady=2)

            self.refresh_providers_list()

        def setup_chat_tab(self):
            """Setup chat interface tab"""
            # Top frame for model selection
            top_frame = ttk.Frame(self.chat_frame)
            top_frame.pack(fill='x', padx=5, pady=5)

            ttk.Label(top_frame, text="Model:").pack(side='left')
            self.model_combo = ttk.Combobox(top_frame, textvariable=self.model_var, width=60, state='readonly')
            self.model_combo.pack(side='left', padx=5, fill='x', expand=True)

            ttk.Button(top_frame, text="Refresh Models", command=self.refresh_models).pack(side='left', padx=5)

            # Current provider display
            self.current_provider_var = tk.StringVar()
            provider_label = ttk.Label(top_frame, textvariable=self.current_provider_var, 
                                     font=('TkDefaultFont', 10, 'bold'))
            provider_label.pack(side='right', padx=10)

            # Chat area
            chat_frame = ttk.Frame(self.chat_frame)
            chat_frame.pack(fill='both', expand=True, padx=5, pady=5)

            # Messages display
            ttk.Label(chat_frame, text="Conversation:", font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
            
            messages_frame = ttk.Frame(chat_frame)
            messages_frame.pack(fill='both', expand=True, pady=2)
            
            self.messages_text = scrolledtext.ScrolledText(messages_frame, height=20, state='disabled', wrap='word')
            self.messages_text.pack(fill='both', expand=True)

            # Input area
            input_frame = ttk.Frame(chat_frame)
            input_frame.pack(fill='x', pady=5)

            ttk.Label(input_frame, text="Your message:", font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')
            
            message_frame = ttk.Frame(input_frame)
            message_frame.pack(fill='x', pady=2)
            
            self.message_text = tk.Text(message_frame, height=3, wrap='word')
            message_scroll = ttk.Scrollbar(message_frame, orient="vertical", command=self.message_text.yview)
            self.message_text.configure(yscrollcommand=message_scroll.set)
            
            self.message_text.pack(side='left', fill='both', expand=True)
            message_scroll.pack(side='right', fill='y')

            # Send button and stats
            send_frame = ttk.Frame(input_frame)
            send_frame.pack(fill='x', pady=5)

            send_btn = ttk.Button(send_frame, text="Send Message", command=self.send_message)
            send_btn.pack(side='right', padx=5)
            
            clear_btn = ttk.Button(send_frame, text="Clear Chat", command=self.clear_chat)
            clear_btn.pack(side='right')

            # Token usage display
            self.token_usage_var = tk.StringVar()
            ttk.Label(send_frame, textvariable=self.token_usage_var, font=('TkDefaultFont', 9)).pack(side='left')

            # Initialize empty model list
            self.model_combo['values'] = ["No models loaded - click 'Refresh Models'"]
            self.model_combo.set("No models loaded - click 'Refresh Models'")

        def setup_status_tab(self):
            """Setup status monitoring tab"""
            # Provider status
            ttk.Label(self.status_frame, text="Provider Status:", 
                     font=('TkDefaultFont', 14, 'bold')).pack(anchor='w', padx=5, pady=5)

            # Status table
            table_frame = ttk.Frame(self.status_frame)
            table_frame.pack(fill='both', expand=True, padx=5, pady=5)
            
            columns = ('Provider', 'Status', 'Requests', 'Tokens', 'Rate Limit', 'Token Limit')
            self.status_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=10)

            for col in columns:
                self.status_tree.heading(col, text=col)
                self.status_tree.column(col, width=120, anchor='center')

            # Add scrollbars
            v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.status_tree.yview)
            h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.status_tree.xview)
            self.status_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

            self.status_tree.pack(side='left', fill='both', expand=True)
            v_scrollbar.pack(side='right', fill='y')
            h_scrollbar.pack(side='bottom', fill='x')

            # Control buttons
            btn_frame = ttk.Frame(self.status_frame)
            btn_frame.pack(fill='x', padx=5, pady=5)
            
            ttk.Button(btn_frame, text="Refresh Status", command=self.refresh_status).pack(side='left', padx=5)
            ttk.Button(btn_frame, text="Reset Usage Counters", command=self.reset_usage).pack(side='left', padx=5)

        def show_env_settings(self):
            """Show environment variables settings dialog"""
            env_window = tk.Toplevel(self.root)
            env_window.title("Environment Variables")
            env_window.geometry("600x400")
            env_window.transient(self.root)
            env_window.grab_set()

            ttk.Label(env_window, text="Current Environment Variables:", 
                     font=('TkDefaultFont', 12, 'bold')).pack(padx=10, pady=10)

            # Display current env vars
            env_text = scrolledtext.ScrolledText(env_window, height=15, width=70)
            env_text.pack(padx=10, pady=5, fill='both', expand=True)

            env_content = "# Environment Variables for API Keys\n\n"
            for key in ['OPENROUTER_API_KEY', 'HF_API_KEY', 'HUGGINGFACE_API_KEY', 'TOGETHER_API_KEY']:
                value = os.getenv(key, 'Not set')
                if value != 'Not set' and len(value) > 10:
                    value = value[:8] + "..." + value[-4:]  # Show partial key for security
                env_content += f"{key}={value}\n"

            env_text.insert('1.0', env_content)
            env_text.config(state='disabled')

            ttk.Button(env_window, text="Close", command=env_window.destroy).pack(pady=10)

        def show_provider_settings(self):
            """Show provider-specific settings"""
            messagebox.showinfo("Provider Settings", 
                              "Provider settings can be configured in the Providers tab.\n\n"
                              "Each provider has different rate limits and capabilities:\n"
                              "• OpenRouter: Access to many models, some free\n"
                              "• Hugging Face: Free inference API, limited models\n"
                              "• Together AI: High-performance inference")

        def toggle_key_visibility(self):
            """Toggle API key visibility"""
            if self.show_key_var.get():
                self.api_key_entry.config(show='')
            else:
                self.api_key_entry.config(show='*')

        def add_provider(self):
            """Add new provider with environment saving"""
            provider_type = self.provider_type_var.get()
            api_key = self.api_key_var.get().strip()

            if not api_key:
                messagebox.showwarning("Warning", "Please enter an API key")
                return

            try:
                # Save to environment if requested
                if self.save_to_env_var.get():
                    self.token_manager.save_to_env(provider_type, api_key)

                # Create and add provider
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
                messagebox.showerror("Error", f"Failed to add provider: {e}")
                logger.error(f"Failed to add provider: {e}")

        def remove_provider(self):
            """Remove selected provider"""
            selection = self.providers_listbox.curselection()
            if not selection:
                messagebox.showwarning("Warning", "Please select a provider to remove")
                return

            provider_name = self.providers_listbox.get(selection[0])
            result = messagebox.askyesno("Confirm Removal", 
                                       f"Are you sure you want to remove {provider_name}?")
            
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

            provider_name = self.providers_listbox.get(selection[0])
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
                                       f"Successfully connected to {provider_name}!\n"
                                       f"Found {len(models)} models available."))
                        self.root.after(0, lambda: self.status_var.set(f"Test successful for {provider_name}"))

                threading.Thread(target=test_thread, daemon=True).start()

        def refresh_providers_list(self):
            """Refresh the providers list"""
            self.providers_listbox.delete(0, tk.END)
            for provider in self.token_manager.providers:
                status_indicator = "✅" if provider.config.status == ProviderStatus.ACTIVE else "❌"
                display_text = f"{status_indicator} {provider.config.name}"
                self.providers_listbox.insert(tk.END, display_text)

        def refresh_models(self):
            """Refresh available models"""
            self.status_var.set("Refreshing models...")
            self.model_combo['values'] = ["Loading models..."]
            self.model_combo.set("Loading models...")

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
                    self.root.after(0, lambda: self.status_var.set(f"Error refreshing models: {e}"))
                    self.root.after(0, lambda: self._update_models_list([]))

            threading.Thread(target=refresh_thread, daemon=True).start()

        def _update_models_list(self, models):
            """Update models list in main thread"""
            if models:
                self.model_combo['values'] = models
                self.model_combo.set(models[0])
                self.status_var.set(f"Found {len(models)} models across all providers")
            else:
                self.model_combo['values'] = ["No models available"]
                self.model_combo.set("No models available")
                self.status_var.set("No models found - check your providers and API keys")

        def send_message(self):
            """Send chat message"""
            model_text = self.model_var.get()
            message = self.message_text.get('1.0', tk.END).strip()

            if not model_text or model_text in ["No models available", "Loading models...", "No models loaded - click 'Refresh Models'"]:
                messagebox.showwarning("Warning", "Please refresh and select a model first")
                return

            if not message:
                messagebox.showwarning("Warning", "Please enter a message")
                return

            # Extract model ID from display text
            if '] ' in model_text:
                model_id = model_text.split('] ', 1)[-1]
            else:
                model_id = model_text

            # Add user message to display
            self.add_message("You", message)
            self.message_text.delete('1.0', tk.END)
            self.status_var.set("Sending message...")

            def send_thread():
                try:
                    messages = [{"role": "user", "content": message}]
                    response, error, provider_name = self.token_manager.send_request(model_id, messages)

                    if error:
                        self.root.after(0, lambda: self.add_message("❌ Error", error))
                        self.root.after(0, lambda: self.status_var.set(f"Error: {error}"))
                    else:
                        content = response.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
                        self.root.after(0, lambda: self.add_message(f"🤖 AI ({provider_name})", content))

                        # Update token usage
                        usage = response.get('usage', {})
                        if usage:
                            usage_text = (f"Tokens: {usage.get('total_tokens', 0)} "
                                        f"(prompt: {usage.get('prompt_tokens', 0)}, "
                                        f"completion: {usage.get('completion_tokens', 0)})")
                            self.root.after(0, lambda: self.token_usage_var.set(usage_text))

                        self.root.after(0, lambda: self.status_var.set(f"Message sent via {provider_name}"))

                except Exception as e:
                    self.root.after(0, lambda: self.add_message("❌ Error", str(e)))
                    self.root.after(0, lambda: self.status_var.set(f"Error: {e}"))

            threading.Thread(target=send_thread, daemon=True).start()

        def add_message(self, sender: str, content: str):
            """Add message to chat display"""
            self.messages_text.config(state='normal')
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            # Add some formatting
            separator = "=" * 50
            self.messages_text.insert(tk.END, f"\n[{timestamp}] {sender}:\n")
            self.messages_text.insert(tk.END, f"{content}\n")
            self.messages_text.insert(tk.END, f"{'-' * 30}\n")
            
            self.messages_text.config(state='disabled')
            self.messages_text.see(tk.END)

        def clear_chat(self):
            """Clear the chat messages"""
            self.messages_text.config(state='normal')
            self.messages_text.delete('1.0', tk.END)
            self.messages_text.config(state='disabled')
            self.token_usage_var.set("")

        def refresh_status(self):
            """Refresh provider status display"""
            # Clear existing items
            for item in self.status_tree.get_children():
                self.status_tree.delete(item)

            # Add current status
            status_list = self.token_manager.get_provider_status()
            for status in status_list:
                # Color coding for status
                status_display = status['status']
                if status['status'] == 'active':
                    status_display = "✅ Active"
                elif status['status'] == 'error':
                    status_display = "❌ Error"
                elif status['status'] == 'exhausted':
                    status_display = "⚠️ Exhausted"

                self.status_tree.insert('', 'end', values=(
                    status['name'],
                    status_display,
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
            """Reset usage counters for all providers"""
            result = messagebox.askyesno("Confirm Reset", 
                                       "Reset usage counters for all providers?")
            if result:
                for provider in self.token_manager.providers:
                    provider.config.usage = TokenUsage(last_reset=datetime.now())
                    provider.config.status = ProviderStatus.ACTIVE
                self.refresh_status()
                self.status_var.set("Usage counters reset")

        def update_status_loop(self):
            """Background status update loop"""
            while self.running:
                try:
                    if self.root.winfo_exists():
                        self.root.after(0, self.refresh_status)
                    time.sleep(30)  # Update every 30 seconds
                except:
                    break

        def save_config(self):
            """Save current configuration"""
            self.token_manager.save_config()
            messagebox.showinfo("Config Saved", "Configuration saved successfully!")

        def load_config(self):
            """Load configuration"""
            self.token_manager.load_config()
            self.token_manager.load_from_env()
            self.refresh_providers_list()
            messagebox.showinfo("Config Loaded", "Configuration loaded successfully!")

        def run(self):
            """Run the GUI application"""
            try:
                self.root.mainloop()
            except KeyboardInterrupt:
                self.on_closing()

        def on_closing(self):
            """Handle application closing properly"""
            self.running = False
            self.token_manager.save_config()
            
            # Stop all background threads
            for thread in threading.enumerate():
                if thread != threading.current_thread() and thread.daemon:
                    # Let daemon threads finish naturally
                    pass
            
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass
            
            sys.exit(0)

def main():
    """Main entry point"""
    print("🚀 Starting Multi-Provider Token Manager v2.0...")
    
    if GUI_AVAILABLE:
        try:
            app = MultiProviderGUI()
            print("✅ GUI loaded successfully!")
            print("💡 Tip: Add your API keys as environment variables for automatic loading:")
            print("   export OPENROUTER_API_KEY='your_key'")
            print("   export HF_API_KEY='your_key'")
            print("   export TOGETHER_API_KEY='your_key'")
            app.run()
        except Exception as e:
            print(f"❌ Error starting GUI application: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠️  GUI not available. Install tkinter for GUI support.")
        print("📝 You can still use the TokenManager class programmatically.")
        
        # Create a simple CLI interface
        manager = TokenManager()
        print(f"📊 Loaded {len(manager.providers)} providers from environment")
        
        if manager.providers:
            print("Available providers:")
            for provider in manager.providers:
                print(f"  - {provider.config.name}")
        else:
            print("No providers loaded. Set environment variables:")
            print("  OPENROUTER_API_KEY, HF_API_KEY, TOGETHER_API_KEY")

if __name__ == "__main__":
    main()