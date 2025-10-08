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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import RAG assistant
try:
    from rag_assistant import SimpleRAG, EnhancedRAGAssistant
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.warning("RAG assistant not available - install required dependencies")

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
        
        # Auto-refresh settings
        self.auto_refresh_enabled = True
        self.auto_refresh_interval = 300  # 5 minutes default
        self.last_auto_refresh = None
        self.refresh_in_progress = False
        self.cached_models = {}
        self.cache_timestamp = None
    
    def should_auto_refresh(self) -> bool:
        """Check if auto-refresh should run (non-blocking check)"""
        if not self.auto_refresh_enabled:
            return False
        
        if self.refresh_in_progress:
            return False
        
        if self.last_auto_refresh is None:
            return True
        
        elapsed = (datetime.now() - self.last_auto_refresh).total_seconds()
        return elapsed >= self.auto_refresh_interval
    
    def background_refresh_models(self) -> Dict[str, List[Dict]]:
        """Background model refresh - non-blocking, returns cached on failure"""
        if self.refresh_in_progress:
            # Return cached data if refresh already in progress
            return self.cached_models or {}
        
        try:
            self.refresh_in_progress = True
            
            # Use ThreadPoolExecutor for timeout capability
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.get_all_models)
                try:
                    # Timeout after 10 seconds to avoid blocking
                    models = future.result(timeout=10)
                    if models:
                        self.cached_models = models
                        self.cache_timestamp = datetime.now()
                        self.last_auto_refresh = datetime.now()
                    return models or self.cached_models or {}
                except FutureTimeoutError:
                    logger.warning("Background model refresh timed out, using cached data")
                    return self.cached_models or {}
        except Exception as e:
            logger.error(f"Background refresh error: {e}")
            return self.cached_models or {}
        finally:
            self.refresh_in_progress = False
    
    def get_cached_models(self) -> Tuple[Dict[str, List[Dict]], bool]:
        """Get cached models with freshness indicator"""
        is_fresh = False
        if self.cache_timestamp:
            age = (datetime.now() - self.cache_timestamp).total_seconds()
            is_fresh = age < 300  # Fresh if less than 5 minutes old
        
        return self.cached_models or {}, is_fresh
    
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
            # Convert enum to string value
            if isinstance(provider_data['status'], ProviderStatus):
                provider_data['status'] = provider_data['status'].value
            elif isinstance(provider_data['status'], str) and '.' in provider_data['status']:
                # Handle already stringified enum like "ProviderStatus.ACTIVE"
                provider_data['status'] = provider_data['status'].split('.')[-1].lower()
            config_data['providers'].append(provider_data)
        
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            os.chmod(self.config_file, 0o600)  # Restrict permissions
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def load_config(self):
        """Load configuration from file with backward compatibility"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                self.current_provider_index = config_data.get('current_provider_index', 0)
                
                # Restore providers
                for provider_data in config_data.get('providers', []):
                    try:
                        # Handle backward compatibility for usage field
                        if 'usage' in provider_data and isinstance(provider_data['usage'], dict):
                            usage_dict = provider_data['usage']
                            
                            # Remove any fields that are not in current TokenUsage dataclass
                            valid_fields = {'prompt_tokens', 'completion_tokens', 'total_tokens', 'requests', 'last_reset'}
                            usage_dict = {k: v for k, v in usage_dict.items() if k in valid_fields}
                            
                            # Convert string back to datetime
                            if usage_dict.get('last_reset'):
                                usage_dict['last_reset'] = datetime.fromisoformat(usage_dict['last_reset'])
                            
                            # Create TokenUsage object
                            provider_data['usage'] = TokenUsage(**usage_dict)
                        
                        # Convert string status to enum with validation
                        if 'status' in provider_data and isinstance(provider_data['status'], str):
                            # Handle both "active" and "ProviderStatus.ACTIVE" formats
                            status_str = provider_data['status'].split('.')[-1] if '.' in provider_data['status'] else provider_data['status']
                            
                            # Validate status value
                            try:
                                provider_data['status'] = ProviderStatus(status_str)
                            except ValueError:
                                # If invalid status, default to ACTIVE
                                logger.warning(f"Invalid status '{status_str}' for provider, defaulting to ACTIVE")
                                provider_data['status'] = ProviderStatus.ACTIVE
                        
                        # Handle backward compatibility for api_key field
                        if 'api_key' in provider_data and 'api_key_encrypted' not in provider_data:
                            provider_data['api_key_encrypted'] = provider_data.pop('api_key')
                        
                        # Ensure api_key_encrypted exists
                        if 'api_key_encrypted' not in provider_data:
                            provider_data['api_key_encrypted'] = ""
                        
                        # Create provider based on name
                        if provider_data['name'] == 'OpenRouter':
                            provider = OpenRouterProvider()
                        elif provider_data['name'] == 'Hugging Face':
                            provider = HuggingFaceProvider()
                        elif provider_data['name'] == 'Together AI':
                            provider = TogetherAIProvider()
                        elif provider_data['name'] == 'Exo Local':
                            # Skip Exo Local if exo_provider is not available
                            logger.info("Skipping Exo Local provider (requires exo_provider module)")
                            continue
                        else:
                            logger.warning(f"Unknown provider type: {provider_data['name']}")
                            continue
                        
                        # Restore config - only include fields that exist in ProviderConfig
                        valid_config_fields = {
                            'name', 'api_key_encrypted', 'base_url', 'models_endpoint', 
                            'chat_endpoint', 'headers', 'rate_limit', 'token_limit', 
                            'status', 'usage'
                        }
                        filtered_data = {k: v for k, v in provider_data.items() if k in valid_config_fields}
                        
                        provider.config = ProviderConfig(**filtered_data)
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
    
    if 'auto_refresh_enabled' not in st.session_state:
        st.session_state.auto_refresh_enabled = True
    
    if 'last_interaction' not in st.session_state:
        st.session_state.last_interaction = datetime.now()
    
    token_manager = st.session_state.token_manager
    token_manager.auto_refresh_enabled = st.session_state.auto_refresh_enabled
    
    # Non-blocking background auto-refresh (runs in background, never blocks UI)
    if token_manager.should_auto_refresh():
        # Trigger background refresh without blocking
        threading.Thread(
            target=token_manager.background_refresh_models,
            daemon=True
        ).start()
    
    st.title("🤖 Enhanced Multi-Provider Token Manager")
    
    # Subtle auto-refresh indicator (non-intrusive)
    if token_manager.auto_refresh_enabled:
        cached_models, is_fresh = token_manager.get_cached_models()
        if token_manager.refresh_in_progress:
            st.caption("🔄 Background refresh in progress...")
        elif is_fresh:
            st.caption("✓ Auto-refreshed - models up to date")
        elif cached_models:
            st.caption("⚠️ Using cached models - refresh recommended")
    
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
        
        if providers:
            # Provider selector
            current_provider = token_manager.get_current_provider()
            current_name = current_provider.config.name if current_provider else None
            
            provider_names = [p['name'] for p in providers]
            if current_name in provider_names:
                current_index = provider_names.index(current_name)
            else:
                current_index = 0
            
            selected_provider = st.selectbox(
                "Active Provider (for chat)",
                provider_names,
                index=current_index,
                key="provider_selector",
                help="Select which provider to use for chat requests"
            )
            
            # Switch provider if changed
            if selected_provider != current_name:
                for i, p in enumerate(token_manager.providers):
                    if p.config.name == selected_provider:
                        token_manager.current_provider_index = i
                        token_manager.save_config()
                        st.success(f"Switched to {selected_provider}")
                        st.rerun()
            
            st.divider()
        
        for idx, provider in enumerate(providers):
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
                    # Show if this is the current provider
                    is_current = (idx == token_manager.current_provider_index)
                    current_marker = " ⭐" if is_current else ""
                    st.write(f"{status_color.get(provider['status'], '⚪')} {key_indicator} **{provider['name']}**{current_marker}")
                
                with col2:
                    st.write(f"Req: {provider['requests']}/{provider['rate_limit']}")
                
                with col3:
                    if st.button("Remove", key=f"remove_{provider['name']}_{idx}"):
                        try:
                            # Find and remove the provider
                            for i, p in enumerate(token_manager.providers):
                                if p.config.name == provider['name']:
                                    token_manager.providers.pop(i)
                                    # Adjust current index if needed
                                    if token_manager.current_provider_index >= len(token_manager.providers):
                                        token_manager.current_provider_index = max(0, len(token_manager.providers) - 1)
                                    token_manager.save_config()
                                    st.success(f"Removed {provider['name']}")
                                    st.rerun()
                                    break
                        except Exception as e:
                            st.error(f"Failed to remove provider: {e}")
        
        # Environment variables info
        st.subheader("Environment Variables")
        st.info("""
        Set these environment variables for automatic loading:
        - `OPENROUTER_API_KEY`
        - `HUGGINGFACE_API_KEY`  
        - `TOGETHER_API_KEY`
        """)
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "📊 Status", "🔧 Settings", "🤖 AI Assistant"])
    
    with tab1:
        st.header("Chat Interface")
        
        # Provider selection and model refresh
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            # Provider selector in chat tab
            current_provider = token_manager.get_current_provider()
            if token_manager.providers:
                provider_names = [p.config.name for p in token_manager.providers]
                current_name = current_provider.config.name if current_provider else provider_names[0]
                
                selected_chat_provider = st.selectbox(
                    "Provider",
                    provider_names,
                    index=provider_names.index(current_name) if current_name in provider_names else 0,
                    key="chat_provider_selector",
                    help="Select provider for chat"
                )
                
                # Switch if changed
                if selected_chat_provider != current_name:
                    for i, p in enumerate(token_manager.providers):
                        if p.config.name == selected_chat_provider:
                            token_manager.current_provider_index = i
                            token_manager.save_config()
                            st.rerun()
        
        with col2:
            # Check for cached models and show freshness
            cached_models, is_fresh = token_manager.get_cached_models()
            
            button_label = "🔄 Refresh Models"
            if cached_models:
                if is_fresh:
                    button_label = "🔄 Refresh (auto-updated)"
                else:
                    button_label = "🔄 Refresh (outdated)"
            
            if st.button(button_label, use_container_width=True):
                with st.spinner("Loading models..."):
                    try:
                        models = token_manager.get_all_models()
                        st.session_state.all_models = models
                        token_manager.cached_models = models
                        token_manager.cache_timestamp = datetime.now()
                        if models:
                            st.success(f"✓ Loaded {sum(len(m) for m in models.values())} models")
                        else:
                            st.warning("No models loaded - check API keys and provider status")
                    except Exception as e:
                        st.error(f"Error loading models: {e}")
            
            # Use cached models if available and no manual refresh
            if 'all_models' not in st.session_state and cached_models:
                st.session_state.all_models = cached_models
        
        with col3:
            # Rotate provider button
            if st.button("🔀 Next", help="Switch to next provider", use_container_width=True):
                token_manager.rotate_provider()
                token_manager.save_config()
                st.rerun()
        
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
            key_status = "🔑 Key configured" if current_provider.api_key else "❌ No API key"
            st.info(f"**Current Provider:** {current_provider.config.name} | {key_status}")
        else:
            st.warning("⚠️ No active providers available - add a provider in the sidebar")
        
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
        
        # Auto-refresh settings
        st.subheader("⚡ Auto-Refresh Settings")
        st.markdown("""
        Auto-refresh runs in the background without interrupting your workflow.
        It keeps model lists and provider status up-to-date automatically.
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            auto_refresh = st.checkbox(
                "Enable Auto-Refresh",
                value=st.session_state.auto_refresh_enabled,
                help="Automatically refresh models and status in background (non-blocking)"
            )
            
            if auto_refresh != st.session_state.auto_refresh_enabled:
                st.session_state.auto_refresh_enabled = auto_refresh
                token_manager.auto_refresh_enabled = auto_refresh
                st.success(f"Auto-refresh {'enabled' if auto_refresh else 'disabled'}")
        
        with col2:
            refresh_interval = st.selectbox(
                "Refresh Interval",
                options=[60, 180, 300, 600, 900],
                index=2,  # Default to 300 (5 minutes)
                format_func=lambda x: f"{x//60} minute{'s' if x//60 != 1 else ''}",
                help="How often to refresh in background"
            )
            
            if refresh_interval != token_manager.auto_refresh_interval:
                token_manager.auto_refresh_interval = refresh_interval
                st.success(f"Interval set to {refresh_interval//60} minutes")
        
        # Show auto-refresh status
        if token_manager.last_auto_refresh:
            time_since = (datetime.now() - token_manager.last_auto_refresh).total_seconds()
            next_refresh_in = max(0, token_manager.auto_refresh_interval - time_since)
            
            st.info(f"""
            **Auto-refresh status:**
            - Last refresh: {int(time_since//60)} minutes ago
            - Next refresh: in {int(next_refresh_in//60)} minutes
            - Cache: {'Fresh ✓' if token_manager.cache_timestamp and (datetime.now() - token_manager.cache_timestamp).total_seconds() < 300 else 'Outdated'}
            """)
        else:
            st.info("Auto-refresh will run soon...")
        
        st.divider()
        
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
    
    with tab4:
        st.header("🤖 AI Documentation Assistant")
        
        if not RAG_AVAILABLE:
            st.warning("⚠️ RAG Assistant not available. The rag_assistant.py module is required.")
            st.info("The assistant uses documentation to answer questions about setup, usage, and troubleshooting.")
        else:
            # Initialize RAG system
            if 'rag_system' not in st.session_state:
                with st.spinner("Loading documentation..."):
                    st.session_state.rag_system = SimpleRAG()
                    st.session_state.rag_system.load_documents()
                    st.session_state.rag_assistant = EnhancedRAGAssistant(
                        st.session_state.rag_system,
                        token_manager
                    )
            
            rag_assistant = st.session_state.rag_assistant
            
            # Quick help buttons
            st.subheader("Quick Help Topics")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📦 Setup & Installation", use_container_width=True):
                    st.session_state.rag_query = "How do I install and setup the application?"
            
            with col2:
                if st.button("🔑 API Keys", use_container_width=True):
                    st.session_state.rag_query = "How do I add and manage API keys?"
            
            with col3:
                if st.button("🚀 Deployment", use_container_width=True):
                    st.session_state.rag_query = "What are my deployment options?"
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🐛 Troubleshooting", use_container_width=True):
                    st.session_state.rag_query = "How do I troubleshoot common errors?"
            
            with col2:
                if st.button("🔒 Security", use_container_width=True):
                    st.session_state.rag_query = "How are API keys secured?"
            
            with col3:
                if st.button("⚡ Auto-Refresh", use_container_width=True):
                    st.session_state.rag_query = "How does auto-refresh work?"
            
            st.divider()
            
            # Question input
            if 'rag_query' not in st.session_state:
                st.session_state.rag_query = ""
            
            question = st.text_input(
                "Ask a question about the AI Token Manager:",
                value=st.session_state.rag_query,
                placeholder="e.g., How do I add API keys? What deployment options are available?",
                key="rag_question_input"
            )
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                use_ai_enhancement = st.checkbox(
                    "🧠 Use AI Enhancement",
                    value=False,
                    help="Use AI provider to enhance answers (requires active provider with API key)"
                )
            
            with col2:
                search_button = st.button("🔍 Search", type="primary", use_container_width=True)
            
            # Display answer
            if search_button and question:
                st.session_state.rag_query = question
                
                with st.spinner("Searching documentation..."):
                    answer = rag_assistant.ask(question, use_ai=use_ai_enhancement)
                
                st.subheader("Answer:")
                st.markdown(answer)
                
                # Show suggestions
                suggestions = rag_assistant.get_suggestions(question)
                if suggestions:
                    st.divider()
                    st.subheader("📌 Related Suggestions:")
                    for i, suggestion in enumerate(suggestions, 1):
                        st.markdown(f"{i}. {suggestion}")
                
                # Show sources
                with st.expander("📚 View Sources"):
                    results = st.session_state.rag_system.search(question, top_k=3)
                    for i, (doc, score) in enumerate(results, 1):
                        st.markdown(f"**Source {i}:** {doc.source} (relevance: {score:.1f})")
                        st.text(doc.content[:300] + "..." if len(doc.content) > 300 else doc.content)
                        st.divider()
            
            elif question and not search_button:
                st.info("👆 Click 'Search' or press Enter to get an answer")
            
            # Documentation stats
            st.divider()
            with st.expander("📊 Documentation Stats"):
                if 'rag_system' in st.session_state:
                    rag = st.session_state.rag_system
                    st.metric("Indexed Documents", len(rag.documents))
                    st.metric("Unique Keywords", len(rag.index))
                    
                    # Show document sources
                    sources = {}
                    for doc in rag.documents:
                        sources[doc.source] = sources.get(doc.source, 0) + 1
                    
                    st.write("**Sources:**")
                    for source, count in sorted(sources.items()):
                        st.write(f"- {source}: {count} chunks")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Application error: {e}")
        logger.error(f"Application error: {e}", exc_info=True)