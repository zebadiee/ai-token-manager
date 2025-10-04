#!/usr/bin/env python3
"""Enhanced Multi-Provider Token Manager

Improved version with better persistence, environment variable support,
streamlit GUI for better stability, and enhanced error handling.
"""

import os
import sys
import json
import time
import threading
import requests
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import dataclass, asdict
from enum import Enum
import base64
from cryptography.fernet import Fernet
import hashlib

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
    api_key_encrypted: str  # Store encrypted version
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
    
    @staticmethod
    def _get_key() -> bytes:
        """Generate or retrieve encryption key"""
        key_file = os.path.expanduser("~/.token_manager_key")
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
            return key
    
    @staticmethod
    def encrypt_api_key(api_key: str) -> str:
        """Encrypt API key for storage"""
        if not api_key:
            return ""
        key = SecureStorage._get_key()
        fernet = Fernet(key)
        encrypted = fernet.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    @staticmethod
    def decrypt_api_key(encrypted_key: str) -> str:
        """Decrypt API key for use"""
        if not encrypted_key:
            return ""
        try:
            key = SecureStorage._get_key()
            fernet = Fernet(key)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_key.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            return ""

class APIProvider:
    """Base class for AI API providers"""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self._decrypted_key = None
    
    @property
    def api_key(self) -> str:
        """Get decrypted API key"""
        if self._decrypted_key is None:
            self._decrypted_key = SecureStorage.decrypt_api_key(self.config.api_key_encrypted)
        return self._decrypted_key
    
    def set_api_key(self, api_key: str):
        """Set and encrypt API key"""
        self.config.api_key_encrypted = SecureStorage.encrypt_api_key(api_key)
        self._decrypted_key = api_key
    
    def is_available(self) -> bool:
        """Check if provider is available for requests"""
        if self.config.status != ProviderStatus.ACTIVE:
            return False
        
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Reset counters if hour has passed
        if self.config.usage.last_reset and self.config.usage.last_reset < hour_ago:
            self.config.usage = TokenUsage(last_reset=now)
        
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
            headers['Authorization'] = f"Bearer {self.api_key}"
            
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
            headers = {'Authorization': f"Bearer {self.api_key}"}
            headers.update(self.config.headers)
            
            response = requests.get(
                f"{self.config.base_url}/{self.config.models_endpoint}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Provider {self.config.name} failed to fetch models: HTTP {response.status_code}")
                return [], f"Failed to fetch models: HTTP {response.status_code} - {response.text}"
            
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
    
    def __init__(self, api_key: str = ""):
        config = ProviderConfig(
            name="OpenRouter",
            api_key_encrypted="",
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
        if api_key:
            self.set_api_key(api_key)

class HuggingFaceProvider(APIProvider):
    """Hugging Face API provider with improved model handling"""
    
    def __init__(self, api_key: str = ""):
        config = ProviderConfig(
            name="Hugging Face",
            api_key_encrypted="",
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
        if api_key:
            self.set_api_key(api_key)
    
    def get_models(self) -> Tuple[List[Dict], Optional[str]]:
        """Get available text generation models from HuggingFace"""
        try:
            headers = {'Authorization': f"Bearer {self.api_key}"}
            
            response = requests.get(
                f"{self.config.base_url}/{self.config.models_endpoint}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code != 200:
                return [], f"Failed to fetch models: HTTP {response.status_code} - {response.text}"
            
            models_data = response.json()
            
            # Transform HF model format to standard format
            models = []
            for model in models_data:
                if isinstance(model, dict):
                    models.append({
                        'id': model.get('id', model.get('modelId', 'unknown')),
                        'name': model.get('id', model.get('modelId', 'unknown')),
                        'description': f"Downloads: {model.get('downloads', 0)}, Likes: {model.get('likes', 0)}"
                    })
            
            return models, None
            
        except Exception as e:
            logger.error(f"Error fetching HF models: {e}")
            return [], str(e)
    
    def send_chat(self, model_id: str, messages: List[Dict]) -> Tuple[Dict, Optional[str]]:
        """Send request to Hugging Face model with improved error handling"""
        # Convert messages to prompt for HF
        prompt = ""
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt += f"{role}: {content}\n"
        
        data = {"inputs": prompt, "parameters": {"max_new_tokens": 100, "return_full_text": False}}
        endpoint = f"models/{model_id}"
        
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                headers = self.config.headers.copy()
                headers['Authorization'] = f"Bearer {self.api_key}"
                
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
                
                if response.status_code != 200:
                    return {}, f"HTTP {response.status_code}: {response.text}"
                
                result = response.json()
                self.config.usage.requests += 1
                
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
    
    def __init__(self, api_key: str = ""):
        config = ProviderConfig(
            name="Together AI",
            api_key_encrypted="",
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
        if api_key:
            self.set_api_key(api_key)

class EnhancedTokenManager:
    """Enhanced token management system with persistence"""
    
    def __init__(self):
        self.providers: List[APIProvider] = []
        self.current_provider_index = 0
        self.config_file = os.path.expanduser("~/.token_manager_config.json")
        self.load_config()
        self.load_from_env()
    
    def load_from_env(self):
        """Load API keys from environment variables"""
        env_keys = {
            'OPENROUTER_API_KEY': OpenRouterProvider,
            'HUGGINGFACE_API_KEY': HuggingFaceProvider,
            'TOGETHER_API_KEY': TogetherAIProvider
        }
        
        for env_var, provider_class in env_keys.items():
            api_key = os.getenv(env_var)
            if api_key:
                # Check if provider already exists
                existing = next((p for p in self.providers if isinstance(p, provider_class)), None)
                if not existing:
                    provider = provider_class(api_key)
                    self.providers.append(provider)
                    logger.info(f"Loaded {provider.config.name} from environment variable {env_var}")
    
    def add_provider(self, provider: APIProvider):
        """Add a new provider to the rotation"""
        # Remove existing provider of same type
        self.providers = [p for p in self.providers if type(p) != type(provider)]
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
            if provider.config.status == ProviderStatus.ACTIVE and provider.api_key:
                models, error = provider.get_models()
                if not error:
                    all_models[provider.config.name] = models
                else:
                    logger.warning(f"Failed to get models for {provider.config.name}: {error}")
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
                'token_limit': provider.config.token_limit,
                'has_key': bool(provider.api_key)
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
            # Convert datetime objects to strings
            if provider_data['usage'] and provider_data['usage']['last_reset']:
                provider_data['usage']['last_reset'] = provider_data['usage']['last_reset'].isoformat()
            config_data['providers'].append(provider_data)
        
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            os.chmod(self.config_file, 0o600)  # Restrict permissions
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def load_config(self):
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                self.current_provider_index = config_data.get('current_provider_index', 0)
                
                # Restore providers
                for provider_data in config_data.get('providers', []):
                    try:
                        # Convert string back to datetime
                        if provider_data['usage'] and provider_data['usage']['last_reset']:
                            provider_data['usage']['last_reset'] = datetime.fromisoformat(provider_data['usage']['last_reset'])
                        
                        # Create provider based on name
                        if provider_data['name'] == 'OpenRouter':
                            provider = OpenRouterProvider()
                        elif provider_data['name'] == 'Hugging Face':
                            provider = HuggingFaceProvider()
                        elif provider_data['name'] == 'Together AI':
                            provider = TogetherAIProvider()
                        else:
                            continue
                        
                        # Restore config
                        provider.config = ProviderConfig(**provider_data)
                        self.providers.append(provider)
                        
                    except Exception as e:
                        logger.error(f"Failed to restore provider {provider_data.get('name', 'unknown')}: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to load config: {e}")

# Streamlit GUI
def main():
    """Streamlit GUI for the Enhanced Multi-Provider Token Manager"""
    
    st.set_page_config(
        page_title="Enhanced Multi-Provider Token Manager",
        page_icon="🤖",
        layout="wide"
    )
    
    # Initialize session state
    if 'token_manager' not in st.session_state:
        st.session_state.token_manager = EnhancedTokenManager()
    
    token_manager = st.session_state.token_manager
    
    st.title("🤖 Enhanced Multi-Provider Token Manager")
    
    # Sidebar for provider management
    with st.sidebar:
        st.header("Provider Management")
        
        # Add provider section
        with st.expander("Add New Provider", expanded=False):
            provider_type = st.selectbox(
                "Provider Type",
                ["OpenRouter", "Hugging Face", "Together AI"]
            )
            
            api_key = st.text_input(
                "API Key",
                type="password",
                help="Enter your API key for the selected provider"
            )
            
            if st.button("Add Provider", type="primary"):
                if api_key:
                    try:
                        if provider_type == "OpenRouter":
                            provider = OpenRouterProvider(api_key)
                        elif provider_type == "Hugging Face":
                            provider = HuggingFaceProvider(api_key)
                        elif provider_type == "Together AI":
                            provider = TogetherAIProvider(api_key)
                        
                        token_manager.add_provider(provider)
                        st.success(f"Added {provider_type} provider successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to add provider: {e}")
                else:
                    st.warning("Please enter an API key")
        
        # List current providers
        st.subheader("Current Providers")
        providers = token_manager.get_provider_status()
        
        for provider in providers:
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    status_color = {
                        'active': '🟢',
                        'exhausted': '🟡',
                        'error': '🔴',
                        'disabled': '⚪'
                    }
                    key_indicator = "🔑" if provider['has_key'] else "❌"
                    st.write(f"{status_color.get(provider['status'], '⚪')} {key_indicator} **{provider['name']}**")
                
                with col2:
                    st.write(f"Req: {provider['requests']}/{provider['rate_limit']}")
                
                with col3:
                    if st.button("Remove", key=f"remove_{provider['name']}"):
                        token_manager.remove_provider(provider['name'])
                        st.rerun()
        
        # Environment variables info
        st.subheader("Environment Variables")
        st.info("""
        Set these environment variables for automatic loading:
        - `OPENROUTER_API_KEY`
        - `HUGGINGFACE_API_KEY`  
        - `TOGETHER_API_KEY`
        """)
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Status", "🔧 Settings"])
    
    with tab1:
        st.header("Chat Interface")
        
        # Model selection
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button("🔄 Refresh Models"):
                with st.spinner("Loading models..."):
                    models = token_manager.get_all_models()
                    st.session_state.all_models = models
        
        # Model dropdown
        all_models = getattr(st.session_state, 'all_models', {})
        model_options = []
        for provider_name, models in all_models.items():
            for model in models:
                model_id = model.get('id', model.get('name', 'unknown'))
                model_options.append(f"[{provider_name}] {model_id}")
        
        selected_model = st.selectbox(
            "Select Model",
            model_options if model_options else ["No models available - click Refresh Models"],
            help="Select a model to chat with"
        )
        
        # Current provider info
        current_provider = token_manager.get_current_provider()
        if current_provider:
            st.info(f"Current Provider: **{current_provider.config.name}**")
        else:
            st.warning("No active providers available")
        
        # Chat interface
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                if "metadata" in message:
                    st.caption(message["metadata"])
        
        # Chat input
        if prompt := st.chat_input("Type your message here..."):
            if selected_model and not selected_model.startswith("No models"):
                # Extract model ID
                model_id = selected_model.split('] ', 1)[-1]
                
                # Add user message to history
                st.session_state.chat_history.append({
                    "role": "user", 
                    "content": prompt
                })
                
                # Display user message
                with st.chat_message("user"):
                    st.write(prompt)
                
                # Get AI response
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        messages = [{"role": "user", "content": prompt}]
                        response, error, provider_name = token_manager.send_request(model_id, messages)
                        
                        if error:
                            st.error(f"Error: {error}")
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": f"Error: {error}",
                                "metadata": f"Provider: {provider_name or 'Unknown'}"
                            })
                        else:
                            content = response.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
                            usage = response.get('usage', {})
                            
                            st.write(content)
                            
                            metadata = f"Provider: {provider_name}"
                            if usage:
                                metadata += f" | Tokens: {usage.get('total_tokens', 0)}"
                            
                            st.caption(metadata)
                            
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": content,
                                "metadata": metadata
                            })
            else:
                st.warning("Please select a valid model first")
        
        # Clear chat button
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()
    
    with tab2:
        st.header("Provider Status")
        
        # Refresh button
        if st.button("🔄 Refresh Status"):
            st.rerun()
        
        # Status table
        providers = token_manager.get_provider_status()
        
        if providers:
            import pandas as pd
            
            df = pd.DataFrame(providers)
            df['usage_percent'] = (df['tokens'] / df['token_limit'] * 100).round(2)
            df['request_percent'] = (df['requests'] / df['rate_limit'] * 100).round(2)
            
            st.dataframe(
                df[['name', 'status', 'has_key', 'requests', 'rate_limit', 'tokens', 'token_limit', 'usage_percent', 'request_percent']],
                use_container_width=True
            )
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Token Usage")
                st.bar_chart(df.set_index('name')['usage_percent'])
            
            with col2:
                st.subheader("Request Usage") 
                st.bar_chart(df.set_index('name')['request_percent'])
        else:
            st.info("No providers configured")
    
    with tab3:
        st.header("Settings")
        
        # Configuration file location
        st.subheader("Configuration")
        st.code(f"Config file: {token_manager.config_file}")
        
        # Export/Import functionality
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Save Configuration"):
                token_manager.save_config()
                st.success("Configuration saved!")
        
        with col2:
            if st.button("🔄 Reload Configuration"):
                token_manager.load_config()
                token_manager.load_from_env()
                st.success("Configuration reloaded!")
        
        # Debug info
        st.subheader("Debug Information")
        with st.expander("View Raw Configuration"):
            try:
                if os.path.exists(token_manager.config_file):
                    with open(token_manager.config_file, 'r') as f:
                        config_data = json.load(f)
                    st.json(config_data)
                else:
                    st.info("No configuration file found")
            except Exception as e:
                st.error(f"Error reading config: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
        logger.error(f"Application error: {e}", exc_info=True)