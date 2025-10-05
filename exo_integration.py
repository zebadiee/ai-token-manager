#!/usr/bin/env python3
"""
Exo Integration Module for Multi-Provider Token Manager

Seamlessly integrates Exo local cluster as a provider alongside
OpenRouter, Hugging Face, and other cloud providers.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from exo_provider import ExoClusterProvider, ExoNodeStatus

logger = logging.getLogger(__name__)


class ExoTokenManagerIntegration:
    """
    Integrates Exo cluster into the Multi-Provider Token Manager
    
    Features:
    - Treats Exo as a zero-cost provider
    - Automatic failover to cloud providers when Exo is unavailable
    - Priority routing: Exo first, then cloud providers
    - Unified provider interface
    """
    
    def __init__(
        self,
        config_path: str = None,
        exo_host: str = "localhost",
        exo_port: int = 8000,
        enable_auto_failover: bool = True,
        exo_priority: int = 0  # 0 = highest priority
    ):
        """
        Initialize Exo integration
        
        Args:
            config_path: Path to token manager config
            exo_host: Exo primary node host
            exo_port: Exo primary node port
            enable_auto_failover: Auto-failover to cloud when Exo fails
            exo_priority: Provider priority (0 = first choice)
        """
        self.config_path = config_path or "~/.token_manager_config.json"
        self.exo_host = exo_host
        self.exo_port = exo_port
        self.enable_auto_failover = enable_auto_failover
        self.exo_priority = exo_priority
        
        # Initialize Exo provider
        self.exo_provider = ExoClusterProvider(
            primary_node_host=exo_host,
            primary_node_port=exo_port,
            auto_discover=True
        )
        
        logger.info(f"Initialized Exo integration at {exo_host}:{exo_port}")
    
    def get_provider_config(self) -> Dict[str, Any]:
        """
        Get Exo provider configuration in token manager format
        
        Returns:
            Provider config dict compatible with token manager
        """
        return {
            "name": "Exo Local",
            "api_key": "local-no-key-required",
            "api_key_encrypted": "",  # No encryption needed for local
            "base_url": f"http://{self.exo_host}:{self.exo_port}",
            "models_endpoint": "v1/models",
            "chat_endpoint": "v1/chat/completions",
            "headers": {
                "Content-Type": "application/json"
            },
            "rate_limit": 999999,  # Effectively unlimited for local
            "token_limit": 999999,  # No token limits
            "status": "active" if self.exo_provider.is_cluster_available else "disabled",
            "usage": {
                "prompt_tokens": 0,  # We track compute time instead
                "completion_tokens": 0,
                "total_tokens": 0,
                "requests": self.exo_provider.total_requests,
                "compute_time": self.exo_provider.total_compute_time,
                "last_reset": self.exo_provider.last_reset.isoformat()
            },
            "cost": 0.0,
            "priority": self.exo_priority,
            "type": "local",
            "capabilities": {
                "streaming": False,  # TODO: Add streaming support
                "function_calling": False,
                "vision": True,  # Exo supports vision models
                "embeddings": False
            }
        }
    
    def add_to_config(self) -> bool:
        """
        Add Exo provider to token manager configuration
        
        Returns:
            True if successfully added, False otherwise
        """
        try:
            # Load existing config
            import os
            config_file = os.path.expanduser(self.config_path)
            
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
            else:
                config = {"providers": [], "current_provider_index": 0}
            
            # Check if Exo already exists
            exo_exists = any(
                p.get("name") == "Exo Local" 
                for p in config.get("providers", [])
            )
            
            if exo_exists:
                logger.info("Exo provider already exists in config")
                # Update existing entry
                for i, p in enumerate(config["providers"]):
                    if p.get("name") == "Exo Local":
                        config["providers"][i] = self.get_provider_config()
                        break
            else:
                # Add Exo as first provider (highest priority)
                exo_config = self.get_provider_config()
                config["providers"].insert(0, exo_config)
                logger.info("Added Exo provider to config")
            
            # Save updated config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to add Exo to config: {e}")
            return False
    
    def remove_from_config(self) -> bool:
        """Remove Exo provider from configuration"""
        try:
            import os
            config_file = os.path.expanduser(self.config_path)
            
            if not os.path.exists(config_file):
                return True
            
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Remove Exo provider
            config["providers"] = [
                p for p in config.get("providers", [])
                if p.get("name") != "Exo Local"
            ]
            
            # Save updated config
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info("Removed Exo provider from config")
            return True
        
        except Exception as e:
            logger.error(f"Failed to remove Exo from config: {e}")
            return False
    
    def route_request(
        self,
        model: str,
        messages: List[Dict],
        cloud_provider_callback = None,
        **kwargs
    ) -> Tuple[Dict, Optional[str], str]:
        """
        Intelligent request routing with auto-failover
        
        Routes to Exo first, falls back to cloud providers if needed
        
        Args:
            model: Model name
            messages: Chat messages
            cloud_provider_callback: Function to call cloud provider if Exo fails
            **kwargs: Additional parameters
        
        Returns:
            Tuple of (response, error, provider_used)
        """
        # Try Exo first
        if self.exo_provider.is_cluster_available:
            logger.info(f"Routing to Exo cluster for model: {model}")
            response, error = self.exo_provider.chat_completion(
                model=model,
                messages=messages,
                **kwargs
            )
            
            if not error:
                return response, None, "Exo Local"
            
            logger.warning(f"Exo inference failed: {error}")
        
        # Failover to cloud provider
        if self.enable_auto_failover and cloud_provider_callback:
            logger.info("Failing over to cloud provider")
            try:
                response, error = cloud_provider_callback(
                    model=model,
                    messages=messages,
                    **kwargs
                )
                return response, error, "Cloud (Failover)"
            except Exception as e:
                return {}, str(e), "Failed"
        
        return {}, "No providers available", "None"
    
    def get_unified_status(self) -> Dict[str, Any]:
        """
        Get unified status of Exo and integration
        
        Returns:
            Comprehensive status dictionary
        """
        exo_status = self.exo_provider.get_status()
        
        return {
            "integration": {
                "enabled": True,
                "auto_failover": self.enable_auto_failover,
                "priority": self.exo_priority
            },
            "exo": exo_status,
            "recommendation": self._get_recommendation(exo_status)
        }
    
    def _get_recommendation(self, status: Dict) -> str:
        """Generate recommendation based on status"""
        if not status["available"]:
            return "⚠️ Exo cluster offline. Using cloud providers."
        
        healthy = status["health"]["healthy_nodes"]
        total = status["health"]["total_nodes"]
        
        if healthy == total:
            return "✅ All Exo nodes healthy. Using local inference."
        elif healthy > 0:
            return f"⚡ {healthy}/{total} Exo nodes online. Partial cluster active."
        else:
            return "🔴 All Exo nodes offline. Check cluster status."
    
    def start(self):
        """Start Exo integration (health monitoring, etc.)"""
        self.exo_provider.start_health_monitoring()
        self.add_to_config()
        logger.info("Exo integration started")
    
    def stop(self):
        """Stop Exo integration"""
        self.exo_provider.stop_health_monitoring()
        logger.info("Exo integration stopped")


# Reliakit-TL15 compatible wrapper
class ExoReliakitProvider:
    """
    Wrapper for Exo provider with reliakit-tl15 self-healing compatibility
    
    Implements the interface expected by reliakit for automatic recovery
    and distributed coordination.
    """
    
    def __init__(self, exo_integration: ExoTokenManagerIntegration):
        self.exo = exo_integration
        self.failed_attempts = 0
        self.max_failures = 3
        self.recovery_timeout = 60  # seconds
        self.last_failure_time = None
    
    def health_check(self) -> Dict[str, Any]:
        """Health check compatible with reliakit"""
        status = self.exo.exo_provider.get_status()
        
        return {
            "healthy": status["available"],
            "provider": "exo_local",
            "nodes": status["health"]["healthy_nodes"],
            "total_nodes": status["health"]["total_nodes"],
            "latency_ms": 0,  # Local, effectively zero latency
            "error_rate": self.failed_attempts / max(1, self.exo.exo_provider.total_requests),
            "last_check": datetime.now().isoformat()
        }
    
    def attempt_recovery(self) -> bool:
        """Attempt to recover failed Exo cluster"""
        logger.info("Attempting Exo cluster recovery...")
        
        # Re-check cluster health
        health = self.exo.exo_provider.check_cluster_health()
        
        if health["cluster_available"]:
            self.failed_attempts = 0
            logger.info("✅ Exo cluster recovered")
            return True
        
        logger.warning("⚠️ Exo cluster still unavailable")
        return False
    
    def on_failure(self):
        """Handle provider failure"""
        self.failed_attempts += 1
        self.last_failure_time = datetime.now()
        
        if self.failed_attempts >= self.max_failures:
            logger.error(f"Exo cluster failed {self.failed_attempts} times")
            # Trigger recovery after timeout
            # (reliakit will handle this automatically)
    
    def reset_failure_count(self):
        """Reset failure tracking"""
        self.failed_attempts = 0
        self.last_failure_time = None


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize integration
    integration = ExoTokenManagerIntegration(
        exo_host="localhost",
        exo_port=8000,
        enable_auto_failover=True
    )
    
    # Add to config
    integration.add_to_config()
    
    # Get status
    status = integration.get_unified_status()
    print(json.dumps(status, indent=2))
    
    # Test routing
    def mock_cloud_provider(model, messages, **kwargs):
        return {"mock": "cloud response"}, None
    
    response, error, provider = integration.route_request(
        model="llama-3.2-3b",
        messages=[{"role": "user", "content": "Hello!"}],
        cloud_provider_callback=mock_cloud_provider
    )
    
    print(f"\nUsed provider: {provider}")
    print(f"Response: {json.dumps(response, indent=2)[:200]}...")
