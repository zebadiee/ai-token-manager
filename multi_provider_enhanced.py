#!/usr/bin/env python3
"""Enhanced Multi-Provider Token Manager

Improved version with better GUI, persistence, and error handling
Supports OpenRouter, Hugging Face, Together AI, and environment variable loading
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
import sqlite3
from pathlib import Path

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

class PersistenceManager:
    """Handles database persistence for providers and conversations"""
    
    def __init__(self, db_path: str = "token_manager.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS providers (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    api_key TEXT NOT NULL,
                    provider_type TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY,
                    model_name TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    ai_response TEXT,
                    provider_name TEXT,
                    token_usage INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def save_provider(self, name: str, api_key: str, provider_type: str):
        """Save provider to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO providers (name, api_key, provider_type) VALUES (?, ?, ?)",
                (name, api_key, provider_type)
            )
            conn.commit()
    
    def load_providers(self) -> List[Dict]:
        """Load providers from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT name, api_key, provider_type, status FROM providers")
            return [{"name": row[0], "api_key": row[1], "type": row[2], "status": row[3]} 
                   for row in cursor.fetchall()]
    
    def delete_provider(self, name: str):
        """Delete provider from database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM providers WHERE name = ?", (name,))
            conn.commit()
    
    def save_conversation(self, model: str, user_msg: str, ai_response: str, 
                         provider: str, tokens: int):
        """Save conversation to database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (model_name, user_message, ai_response, provider_name, token_usage) VALUES (?, ?, ?, ?, ?)",
                (model, user_msg, ai_response, provider, tokens)
            )
            conn.commit()

class APIProvider:
    """Enhanced base class for AI API providers"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.last_request_time = 0
        self.request_count = 0
        self.session = requests.Session()
        
    def is_available(self) -> bool:
        """Check if provider is available for requests"""
        if self.config.status != ProviderStatus.ACTIVE:
            return False
            
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        if self.config.usage.last_reset < hour_ago:
            self.config.usage = TokenUsage(last_reset=now)
            self.request_count = 0
            
        if self.config.usage.requests >= self.config.rate_limit:
            return False
            
        if self.config.usage.total_tokens >= self.config.token_limit:
            return False
            
        return True
    
    def get_models(self) -> Tuple[List[Dict], Optional[str]]:
        """Get available models from provider with better error handling"""
        try:
            headers = self.config.headers.copy()
            headers['Authorization'] = f"Bearer {self.config.api_key}"
            
            response = self.session.get(
                f"{self.config.base_url}/{self.config.models_endpoint}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 401:
                return [], "Invalid API key"
            elif response.status_code != 200:
                return [], f"HTTP {response.status_code}: {response.text[:200]}"
                
            data = response.json()
            models = data.get('models', data.get('data', []))
            
            if not isinstance(models, list):
                return [], "Unexpected response format"
                
            return models, None
            
        except requests.exceptions.Timeout:
            return [], "Request timeout"
        except requests.exceptions.ConnectionError:
            return [], "Connection error"
        except Exception as e:
            return [], str(e)
    
    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send chat completion request"""
        data = {"model": model_id, "messages": messages}
        
        try:
            headers = self.config.headers.copy()
            headers['Authorization'] = f"Bearer {self.config.api_key}"
            
            response = self.session.post(
                f"{self.config.base_url}/{self.config.chat_endpoint}",
                headers=headers,
                json=data,
                timeout=60
            )
            
            self.config.usage.requests += 1
            
            if response.status_code == 401:
                self.config.status = ProviderStatus.ERROR
                return {}, "Invalid API key"
            elif response.status_code in [402, 429]:
                self.config.status = ProviderStatus.EXHAUSTED
                return {}, f"Quota exhausted (HTTP {response.status_code})"
            elif response.status_code >= 400:
                return {}, f"HTTP {response.status_code}: {response.text[:200]}"
                
            result = response.json()
            
            if 'usage' in result:
                usage = result['usage']
                self.config.usage.prompt_tokens += usage.get('prompt_tokens', 0)
                self.config.usage.completion_tokens += usage.get('completion_tokens', 0)
                self.config.usage.total_tokens += usage.get('total_tokens', 0)
                
            return result, None
            
        except Exception as e:
            return {}, str(e)

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
                "X-Title": "Enhanced Multi-Provider Token Manager"
            }
        )
        super().__init__(config)

class HuggingFaceProvider(APIProvider):
    """Hugging Face API provider with retry logic"""
    
    def __init__(self, api_key: str):
        config = ProviderConfig(
            name="Hugging Face",
            api_key=api_key,
            base_url="https://api-inference.huggingface.co",
            models_endpoint="models",
            chat_endpoint="models",
            headers={"Content-Type": "application/json"},
            rate_limit=100,
            token_limit=50000
        )
        super().__init__(config)
    
    def get_models(self) -> Tuple[List[Dict], Optional[str]]:
        """Get popular HF models since the API doesn't provide a simple list"""
        popular_models = [
            {"id": "microsoft/DialoGPT-medium", "name": "DialoGPT Medium"},
            {"id": "microsoft/DialoGPT-large", "name": "DialoGPT Large"},
            {"id": "facebook/blenderbot-400M-distill", "name": "BlenderBot 400M"},
            {"id": "google/flan-t5-large", "name": "FLAN-T5 Large"},
            {"id": "EleutherAI/gpt-neo-2.7B", "name": "GPT-Neo 2.7B"}
        ]
        return popular_models, None
    
    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send request with retry logic for model loading"""
        prompt = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in messages])
        data = {"inputs": prompt}
        
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                headers = self.config.headers.copy()
                headers['Authorization'] = f"Bearer {self.config.api_key}"
                
                response = self.session.post(
                    f"{self.config.base_url}/models/{model_id}",
                    headers=headers,
                    json=data,
                    timeout=60
                )
                
                if response.status_code == 503 and attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                    
                if response.status_code != 200:
                    return {}, f"HTTP {response.status_code}: {response.text[:200]}"
                    
                result = response.json()
                self.config.usage.requests += 1
                
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get('generated_text', '')
                    return {
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
                    }, None
                else:
                    return {}, "Unexpected response format"
                    
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    return {}, str(e)
                time.sleep(2 ** attempt)
                
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
            headers={"Content-Type": "application/json"},
            rate_limit=500,
            token_limit=250000
        )
        super().__init__(config)

class EnhancedTokenManager:
    """Enhanced token management with persistence"""
    
    def __init__(self):
        self.providers: List[APIProvider] = []
        self.current_provider_index = 0
        self.persistence = PersistenceManager()
        self.load_providers_from_db()
        self.load_env_variables()
    
    def load_env_variables(self):
        """Load API keys from environment variables"""
        env_providers = {
            'OPENROUTER_API_KEY': 'OpenRouter',
            'HUGGINGFACE_API_KEY': 'Hugging Face',
            'TOGETHER_API_KEY': 'Together AI'
        }
        
        for env_var, provider_type in env_providers.items():
            api_key = os.getenv(env_var)
            if api_key:
                try:
                    self.add_provider_by_type(provider_type, api_key)
                    logger.info(f"Loaded {provider_type} from environment variable")
                except Exception as e:
                    logger.error(f"Failed to load {provider_type} from env: {e}")
    
    def add_provider_by_type(self, provider_type: str, api_key: str):
        """Add provider by type"""
        if provider_type == "OpenRouter":
            provider = OpenRouterProvider(api_key)
        elif provider_type == "Hugging Face":
            provider = HuggingFaceProvider(api_key)
        elif provider_type == "Together AI":
            provider = TogetherAIProvider(api_key)
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
        
        # Check if provider already exists
        existing = next((p for p in self.providers if p.config.name == provider.config.name), None)
        if existing:
            existing.config.api_key = api_key
            existing.config.status = ProviderStatus.ACTIVE
        else:
            self.providers.append(provider)
        
        # Save to database
        self.persistence.save_provider(provider.config.name, api_key, provider_type)
    
    def load_providers_from_db(self):
        """Load providers from database"""
        saved_providers = self.persistence.load_providers()
        for prov_data in saved_providers:
            try:
                self.add_provider_by_type(prov_data['type'], prov_data['api_key'])
            except Exception as e:
                logger.error(f"Failed to load provider {prov_data['name']}: {e}")
    
    def remove_provider(self, provider_name: str):
        """Remove provider"""
        self.providers = [p for p in self.providers if p.config.name != provider_name]
        self.persistence.delete_provider(provider_name)
    
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
        """Send request with provider rotation"""
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

class EnhancedGUI:
    """Enhanced GUI with better UX"""
    
    def __init__(self):
        self.token_manager = EnhancedTokenManager()
        self.root = tk.Tk()
        self.root.title("Enhanced Multi-Provider Token Manager")
        self.root.geometry("1400x900")
        self.root.configure(bg='#f0f0f0')
        
        # Styling
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.setup_menu()
        self.setup_gui()
        self.auto_refresh_models()
        
        # Auto-save on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_menu(self):
        """Setup menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import Config", command=self.import_config)
        file_menu.add_command(label="Export Config", command=self.export_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Preferences", command=self.show_preferences)
        settings_menu.add_command(label="Clear Database", command=self.clear_database)
    
    def setup_gui(self):
        """Setup main GUI"""
        # Create notebook with better styling
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Providers tab
        self.providers_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.providers_frame, text="🔑 Providers")
        self.setup_providers_tab()
        
        # Chat tab
        self.chat_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.chat_frame, text="💬 Chat")
        self.setup_chat_tab()
        
        # Status tab
        self.status_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.status_frame, text="📊 Status")
        self.setup_status_tab()
        
        # Conversations tab
        self.conversations_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.conversations_frame, text="📝 History")
        self.setup_conversations_tab()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - Enhanced Multi-Provider Token Manager")
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side='bottom', fill='x', padx=10, pady=5)
        
        self.status_bar = ttk.Label(status_frame, textvariable=self.status_var, relief='sunken')
        self.status_bar.pack(side='left', fill='x', expand=True)
        
        # Close button
        ttk.Button(status_frame, text="Exit", command=self.on_closing).pack(side='right', padx=5)
    
    def setup_providers_tab(self):
        """Enhanced providers tab"""
        main_frame = ttk.Frame(self.providers_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left side - Provider list
        left_frame = ttk.LabelFrame(main_frame, text="Configured Providers", padding=10)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))
        
        # Provider listbox with scrollbar
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill='both', expand=True)
        
        self.providers_listbox = tk.Listbox(list_frame, font=('Consolas', 11))
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.providers_listbox.yview)
        self.providers_listbox.configure(yscrollcommand=scrollbar.set)
        
        self.providers_listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Provider buttons
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(fill='x', pady=5)
        
        ttk.Button(button_frame, text="🔄 Refresh", command=self.refresh_providers_list).pack(side='left', padx=2)
        ttk.Button(button_frame, text="🗑️ Remove", command=self.remove_provider).pack(side='left', padx=2)
        ttk.Button(button_frame, text="🧪 Test", command=self.test_provider).pack(side='left', padx=2)
        
        # Right side - Add provider
        right_frame = ttk.LabelFrame(main_frame, text="Add New Provider", padding=10)
        right_frame.pack(side='right', fill='y', padx=(5, 0))
        
        # Provider type
        ttk.Label(right_frame, text="Provider Type:").pack(anchor='w')
        self.provider_type_var = tk.StringVar(value="OpenRouter")
        type_combo = ttk.Combobox(right_frame, textvariable=self.provider_type_var,
                                 values=["OpenRouter", "Hugging Face", "Together AI"], 
                                 state='readonly', width=25)
        type_combo.pack(fill='x', pady=2)
        
        # API key
        ttk.Label(right_frame, text="API Key:", anchor='w').pack(anchor='w', pady=(10,0))
        self.api_key_var = tk.StringVar()
        
        key_frame = ttk.Frame(right_frame)
        key_frame.pack(fill='x', pady=2)
        
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, show='*', width=25)
        self.api_key_entry.pack(side='left', fill='x', expand=True)
        
        self.show_key_var = tk.BooleanVar()
        ttk.Checkbutton(key_frame, text="👁️", variable=self.show_key_var, 
                       command=self.toggle_key_visibility, width=3).pack(side='right', padx=2)
        
        # Paste button
        ttk.Button(right_frame, text="📋 Paste from Clipboard", 
                  command=self.paste_api_key).pack(fill='x', pady=5)
        
        # Add button
        ttk.Button(right_frame, text="➕ Add Provider", 
                  command=self.add_provider).pack(fill='x', pady=10)
        
        # Load from environment
        ttk.Button(right_frame, text="🌍 Load from Environment", 
                  command=self.load_from_env).pack(fill='x', pady=2)
        
        self.refresh_providers_list()
    
    def setup_chat_tab(self):
        """Enhanced chat interface"""
        main_frame = ttk.Frame(self.chat_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Model selection frame
        model_frame = ttk.LabelFrame(main_frame, text="Model Selection", padding=5)
        model_frame.pack(fill='x', pady=(0, 10))
        
        # Model dropdown
        left_model_frame = ttk.Frame(model_frame)
        left_model_frame.pack(side='left', fill='x', expand=True)
        
        ttk.Label(left_model_frame, text="Model:").pack(side='left', padx=(0, 5))
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(left_model_frame, textvariable=self.model_var, 
                                       state='readonly', width=50)
        self.model_combo.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        # Buttons
        button_frame = ttk.Frame(model_frame)
        button_frame.pack(side='right')
        
        ttk.Button(button_frame, text="🔄 Refresh Models", 
                  command=self.refresh_models).pack(side='left', padx=2)
        
        # Current provider display
        self.current_provider_var = tk.StringVar()
        ttk.Label(button_frame, textvariable=self.current_provider_var, 
                 font=('TkDefaultFont', 9)).pack(side='left', padx=10)
        
        # Chat area
        chat_frame = ttk.LabelFrame(main_frame, text="Conversation", padding=5)
        chat_frame.pack(fill='both', expand=True)
        
        # Messages display
        self.messages_text = scrolledtext.ScrolledText(chat_frame, height=15, 
                                                      font=('Consolas', 10), 
                                                      state='disabled',
                                                      wrap='word')
        self.messages_text.pack(fill='both', expand=True, pady=(0, 10))
        
        # Input area
        input_frame = ttk.Frame(chat_frame)
        input_frame.pack(fill='x')
        
        # Message input
        self.message_text = tk.Text(input_frame, height=3, font=('TkDefaultFont', 10))
        self.message_text.pack(fill='x', pady=(0, 5))
        
        # Send controls
        send_frame = ttk.Frame(input_frame)
        send_frame.pack(fill='x')
        
        # Token usage
        self.token_usage_var = tk.StringVar()
        ttk.Label(send_frame, textvariable=self.token_usage_var, 
                 font=('TkDefaultFont', 9)).pack(side='left')
        
        # Send button
        ttk.Button(send_frame, text="📤 Send Message", 
                  command=self.send_message).pack(side='right', padx=5)
        
        # Clear chat button
        ttk.Button(send_frame, text="🗑️ Clear Chat", 
                  command=self.clear_chat).pack(side='right')
    
    def setup_status_tab(self):
        """Enhanced status monitoring"""
        main_frame = ttk.Frame(self.status_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Provider status
        status_frame = ttk.LabelFrame(main_frame, text="Provider Status", padding=10)
        status_frame.pack(fill='both', expand=True)
        
        columns = ('Provider', 'Status', 'Requests', 'Tokens', 'Rate Limit', 'Token Limit', 'Last Reset')
        self.status_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=10)
        
        # Column configuration
        widths = [120, 80, 100, 100, 100, 100, 150]
        for i, (col, width) in enumerate(zip(columns, widths)):
            self.status_tree.heading(col, text=col)
            self.status_tree.column(col, width=width, anchor='center')
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(status_frame, orient='vertical', command=self.status_tree.yview)
        h_scrollbar = ttk.Scrollbar(status_frame, orient='horizontal', command=self.status_tree.xview)
        self.status_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        self.status_tree.pack(side='left', fill='both', expand=True)
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill='x', pady=10)
        
        ttk.Button(control_frame, text="🔄 Refresh Status", 
                  command=self.refresh_status).pack(side='left', padx=5)
        ttk.Button(control_frame, text="🔄 Reset Usage", 
                  command=self.reset_usage).pack(side='left', padx=5)
        
        # Auto-refresh toggle
        self.auto_refresh_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Auto-refresh (10s)", 
                       variable=self.auto_refresh_var).pack(side='left', padx=20)
        
        # Start auto-refresh
        self.start_auto_refresh()
    
    def setup_conversations_tab(self):
        """Conversation history tab"""
        main_frame = ttk.Frame(self.conversations_frame)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Controls
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill='x', pady=(0, 10))
        
        ttk.Button(control_frame, text="🔄 Refresh", 
                  command=self.refresh_conversations).pack(side='left', padx=5)
        ttk.Button(control_frame, text="🗑️ Clear History", 
                  command=self.clear_conversations).pack(side='left', padx=5)
        
        # Conversations list
        self.conversations_text = scrolledtext.ScrolledText(main_frame, height=25, 
                                                           font=('Consolas', 9), 
                                                           state='disabled')
        self.conversations_text.pack(fill='both', expand=True)
    
    def toggle_key_visibility(self):
        """Toggle API key visibility"""
        if self.show_key_var.get():
            self.api_key_entry.config(show='')
        else:
            self.api_key_entry.config(show='*')
    
    def paste_api_key(self):
        """Paste API key from clipboard"""
        try:
            clipboard_content = self.root.clipboard_get()
            self.api_key_var.set(clipboard_content)
        except Exception:
            messagebox.showwarning("Warning", "No text found in clipboard")
    
    def add_provider(self):
        """Add new provider"""
        provider_type = self.provider_type_var.get()
        api_key = self.api_key_var.get().strip()
        
        if not api_key:
            messagebox.showwarning("Warning", "Please enter an API key")
            return
        
        try:
            self.token_manager.add_provider_by_type(provider_type, api_key)
            self.api_key_var.set("")
            self.refresh_providers_list()
            self.status_var.set(f"✅ Added {provider_type} provider")
            messagebox.showinfo("Success", f"{provider_type} provider added successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add provider: {e}")
    
    def remove_provider(self):
        """Remove selected provider"""
        selection = self.providers_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a provider to remove")
            return
        
        provider_name = self.providers_listbox.get(selection[0]).split(' ')[0]
        
        if messagebox.askyesno("Confirm", f"Remove {provider_name} provider?"):
            self.token_manager.remove_provider(provider_name)
            self.refresh_providers_list()
            self.status_var.set(f"🗑️ Removed {provider_name}")
    
    def test_provider(self):
        """Test selected provider connection"""
        selection = self.providers_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a provider to test")
            return
        
        provider_name = self.providers_listbox.get(selection[0]).split(' ')[0]
        provider = next((p for p in self.token_manager.providers if p.config.name == provider_name), None)
        
        if provider:
            def test_thread():
                self.root.after(0, lambda: self.status_var.set(f"🧪 Testing {provider_name}..."))
                models, error = provider.get_models()
                
                if error:
                    self.root.after(0, lambda: messagebox.showerror("Test Failed", f"❌ {error}"))
                    self.root.after(0, lambda: self.status_var.set(f"❌ Test failed for {provider_name}"))
                else:
                    self.root.after(0, lambda: messagebox.showinfo("Test Successful", 
                                                                  f"✅ Connected! Found {len(models)} models."))
                    self.root.after(0, lambda: self.status_var.set(f"✅ Test successful for {provider_name}"))
            
            threading.Thread(target=test_thread, daemon=True).start()
    
    def load_from_env(self):
        """Load providers from environment variables"""
        old_count = len(self.token_manager.providers)
        self.token_manager.load_env_variables()
        new_count = len(self.token_manager.providers)
        
        if new_count > old_count:
            self.refresh_providers_list()
            self.status_var.set(f"🌍 Loaded {new_count - old_count} providers from environment")
        else:
            messagebox.showinfo("Environment Variables", "No new providers found in environment variables")
    
    def refresh_providers_list(self):
        """Refresh providers list display"""
        self.providers_listbox.delete(0, tk.END)
        for provider in self.token_manager.providers:
            status_icon = "🟢" if provider.config.status == ProviderStatus.ACTIVE else "🔴"
            display_text = f"{provider.config.name} {status_icon}"
            self.providers_listbox.insert(tk.END, display_text)
    
    def auto_refresh_models(self):
        """Auto-refresh models when providers are loaded"""
        if self.token_manager.providers:
            self.refresh_models()
    
    def refresh_models(self):
        """Refresh available models"""
        self.status_var.set("🔄 Refreshing models...")
        self.model_combo['values'] = ["Loading..."]
        self.model_combo.set("Loading...")
        
        def refresh_thread():
            try:
                all_models = self.token_manager.get_all_models()
                model_options = []
                
                for provider_name, models in all_models.items():
                    for model in models:
                        model_id = model.get('id', model.get('name', 'unknown'))
                        if model_id != 'unknown':
                            display_name = f"[{provider_name}] {model_id}"
                            model_options.append(display_name)
                
                self.root.after(0, lambda: self._update_models_list(model_options))
                
            except Exception as e:
                logger.error(f"Error refreshing models: {e}")
                self.root.after(0, lambda: self.status_var.set(f"❌ Error refreshing models"))
                self.root.after(0, lambda: self._update_models_list([]))
        
        threading.Thread(target=refresh_thread, daemon=True).start()
    
    def _update_models_list(self, models):
        """Update models list in main thread"""
        self.model_combo['values'] = models
        if models:
            self.model_combo.set(models[0])
            self.status_var.set(f"✅ Found {len(models)} models")
        else:
            self.model_combo.set("No models available")
            self.status_var.set("❌ No models found")
    
    def send_message(self):
        """Send chat message"""
        model_text = self.model_var.get()
        message = self.message_text.get('1.0', tk.END).strip()
        
        if not model_text or model_text in ["Loading...", "No models available"]:
            messagebox.showwarning("Warning", "Please select a valid model")
            return
            
        if not message:
            messagebox.showwarning("Warning", "Please enter a message")
            return
        
        # Extract model ID
        model_id = model_text.split('] ', 1)[-1]
        
        # Add user message
        self.add_message("👤 You", message)
        self.message_text.delete('1.0', tk.END)
        self.status_var.set("📤 Sending message...")
        
        def send_thread():
            try:
                messages = [{"role": "user", "content": message}]
                response, error, provider_name = self.token_manager.send_request(model_id, messages)
                
                if error:
                    self.root.after(0, lambda: self.add_message("❌ Error", error))
                    self.root.after(0, lambda: self.status_var.set(f"❌ Error: {error}"))
                else:
                    content = response.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
                    self.root.after(0, lambda: self.add_message(f"🤖 AI ({provider_name})", content))
                    
                    # Update token usage
                    usage = response.get('usage', {})
                    if usage:
                        total_tokens = usage.get('total_tokens', 0)
                        prompt_tokens = usage.get('prompt_tokens', 0)
                        completion_tokens = usage.get('completion_tokens', 0)
                        usage_text = f"Tokens: {total_tokens} (prompt: {prompt_tokens}, completion: {completion_tokens})"
                        self.root.after(0, lambda: self.token_usage_var.set(usage_text))
                        
                        # Save conversation
                        self.token_manager.persistence.save_conversation(
                            model_id, message, content, provider_name, total_tokens
                        )
                    
                    self.root.after(0, lambda: self.status_var.set(f"✅ Message sent via {provider_name}"))
                    
            except Exception as e:
                self.root.after(0, lambda: self.add_message("❌ Error", str(e)))
                self.root.after(0, lambda: self.status_var.set(f"❌ Error: {e}"))
        
        threading.Thread(target=send_thread, daemon=True).start()
    
    def add_message(self, sender: str, content: str):
        """Add message to chat display"""
        self.messages_text.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.messages_text.insert(tk.END, f"[{timestamp}] {sender}:\n{content}\n\n")
        self.messages_text.config(state='disabled')
        self.messages_text.see(tk.END)
    
    def clear_chat(self):
        """Clear chat messages"""
        if messagebox.askyesno("Confirm", "Clear current conversation?"):
            self.messages_text.config(state='normal')
            self.messages_text.delete('1.0', tk.END)
            self.messages_text.config(state='disabled')
            self.token_usage_var.set("")
    
    def refresh_status(self):
        """Refresh provider status"""
        # Clear existing items
        for item in self.status_tree.get_children():
            self.status_tree.delete(item)
        
        # Add current status
        for provider in self.token_manager.providers:
            last_reset = provider.config.usage.last_reset
            reset_str = last_reset.strftime("%H:%M:%S") if last_reset else "Never"
            
            self.status_tree.insert('', 'end', values=(
                provider.config.name,
                provider.config.status.value,
                f"{provider.config.usage.requests}/{provider.config.rate_limit}",
                f"{provider.config.usage.total_tokens}/{provider.config.token_limit}",
                provider.config.rate_limit,
                provider.config.token_limit,
                reset_str
            ))
        
        # Update current provider display
        current_provider = self.token_manager.get_current_provider()
        if current_provider:
            self.current_provider_var.set(f"Current: {current_provider.config.name}")
        else:
            self.current_provider_var.set("No provider available")
    
    def reset_usage(self):
        """Reset usage statistics"""
        if messagebox.askyesno("Confirm", "Reset usage statistics for all providers?"):
            for provider in self.token_manager.providers:
                provider.config.usage = TokenUsage(last_reset=datetime.now())
            self.refresh_status()
            self.status_var.set("✅ Usage statistics reset")
    
    def start_auto_refresh(self):
        """Start automatic status refresh"""
        def auto_refresh_loop():
            while True:
                if self.auto_refresh_var.get():
                    try:
                        self.root.after(0, self.refresh_status)
                    except:
                        break
                time.sleep(10)
        
        threading.Thread(target=auto_refresh_loop, daemon=True).start()
    
    def refresh_conversations(self):
        """Refresh conversation history"""
        # This would load from database in a real implementation
        self.conversations_text.config(state='normal')
        self.conversations_text.delete('1.0', tk.END)
        self.conversations_text.insert(tk.END, "Conversation history feature coming soon...\n")
        self.conversations_text.config(state='disabled')
    
    def clear_conversations(self):
        """Clear conversation history"""
        if messagebox.askyesno("Confirm", "Clear all conversation history?"):
            # Clear database in real implementation
            self.refresh_conversations()
            self.status_var.set("🗑️ Conversation history cleared")
    
    def import_config(self):
        """Import configuration from file"""
        filename = filedialog.askopenfilename(
            title="Import Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r') as f:
                    config = json.load(f)
                
                # Import providers
                for prov_data in config.get('providers', []):
                    self.token_manager.add_provider_by_type(
                        prov_data['type'], prov_data['api_key']
                    )
                
                self.refresh_providers_list()
                messagebox.showinfo("Success", "Configuration imported successfully!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import configuration: {e}")
    
    def export_config(self):
        """Export configuration to file"""
        filename = filedialog.asksaveasfilename(
            title="Export Configuration",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            try:
                config = {
                    'providers': [
                        {
                            'name': p.config.name,
                            'type': type(p).__name__.replace('Provider', ''),
                            'api_key': p.config.api_key
                        }
                        for p in self.token_manager.providers
                    ],
                    'exported_at': datetime.now().isoformat()
                }
                
                with open(filename, 'w') as f:
                    json.dump(config, f, indent=2)
                
                messagebox.showinfo("Success", "Configuration exported successfully!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export configuration: {e}")
    
    def show_preferences(self):
        """Show preferences dialog"""
        pref_window = tk.Toplevel(self.root)
        pref_window.title("Preferences")
        pref_window.geometry("400x300")
        pref_window.resizable(False, False)
        
        # Center the window
        pref_window.transient(self.root)
        pref_window.grab_set()
        
        ttk.Label(pref_window, text="Preferences", 
                 font=('TkDefaultFont', 14, 'bold')).pack(pady=10)
        
        # Auto-refresh setting
        auto_frame = ttk.LabelFrame(pref_window, text="Auto-refresh", padding=10)
        auto_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Checkbutton(auto_frame, text="Enable auto-refresh of status", 
                       variable=self.auto_refresh_var).pack(anchor='w')
        
        # Close button
        ttk.Button(pref_window, text="Close", 
                  command=pref_window.destroy).pack(pady=20)
    
    def clear_database(self):
        """Clear all database data"""
        if messagebox.askyesno("Confirm", 
                              "This will delete all saved providers and conversation history. Continue?"):
            try:
                # Clear providers
                for provider in self.token_manager.providers[:]:
                    self.token_manager.remove_provider(provider.config.name)
                
                # Clear database tables
                with sqlite3.connect(self.token_manager.persistence.db_path) as conn:
                    conn.execute("DELETE FROM providers")
                    conn.execute("DELETE FROM conversations")
                    conn.commit()
                
                self.refresh_providers_list()
                self.refresh_conversations()
                messagebox.showinfo("Success", "Database cleared successfully!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear database: {e}")
    
    def on_closing(self):
        """Handle application closing"""
        if messagebox.askyesno("Exit", "Exit Enhanced Multi-Provider Token Manager?"):
            self.root.destroy()
    
    def run(self):
        """Run the application"""
        self.root.mainloop()

def main():
    """Main entry point"""
    try:
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('token_manager.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        logger.info("Starting Enhanced Multi-Provider Token Manager...")
        
        # Create and run the application
        app = EnhancedGUI()
        app.run()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")

if __name__ == "__main__":
    main()