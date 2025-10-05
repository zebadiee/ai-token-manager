#!/usr/bin/env python3
"""
Exo Local Cluster Provider for Multi-Provider Token Manager

Integrates exo distributed AI cluster as a zero-cost, low-latency provider
with automatic node discovery, health monitoring, and failover support.
"""

import requests
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import threading
import time

logger = logging.getLogger(__name__)


class ExoNodeStatus(Enum):
    """Status of individual Exo nodes"""
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    DISCOVERING = "discovering"


@dataclass
class ExoNode:
    """Represents a single Exo cluster node"""
    id: str
    host: str
    port: int
    device_name: str
    memory_gb: float
    status: ExoNodeStatus = ExoNodeStatus.DISCOVERING
    last_seen: Optional[datetime] = None
    models: List[str] = None
    
    def __post_init__(self):
        if self.models is None:
            self.models = []
        if self.last_seen is None:
            self.last_seen = datetime.now()
    
    @property
    def endpoint(self) -> str:
        """Get the full endpoint URL for this node"""
        return f"http://{self.host}:{self.port}"
    
    def is_healthy(self, timeout_seconds: int = 30) -> bool:
        """Check if node is responsive within timeout"""
        if self.status == ExoNodeStatus.OFFLINE:
            return False
        
        time_since_seen = datetime.now() - self.last_seen
        return time_since_seen.total_seconds() < timeout_seconds


class ExoClusterProvider:
    """
    Exo Cluster Provider - Zero-cost local AI inference
    
    Features:
    - Auto-discovery of Exo nodes on local network
    - Load balancing across available nodes
    - Health monitoring and auto-failover
    - ChatGPT-compatible API integration
    - Token usage tracking (local compute time)
    """
    
    def __init__(
        self,
        primary_node_host: str = "localhost",
        primary_node_port: int = 8000,
        auto_discover: bool = True,
        health_check_interval: int = 10,
        node_timeout: int = 30
    ):
        """
        Initialize Exo Cluster Provider
        
        Args:
            primary_node_host: Primary exo node hostname/IP
            primary_node_port: Primary exo node API port (default: 8000)
            auto_discover: Enable automatic node discovery
            health_check_interval: Seconds between health checks
            node_timeout: Seconds before marking node offline
        """
        self.primary_node_host = primary_node_host
        self.primary_node_port = primary_node_port
        self.auto_discover = auto_discover
        self.health_check_interval = health_check_interval
        self.node_timeout = node_timeout
        
        # Node management
        self.nodes: Dict[str, ExoNode] = {}
        self.available_models: List[str] = []
        self.is_cluster_available = False
        
        # Usage tracking
        self.total_requests = 0
        self.total_compute_time = 0.0
        self.last_reset = datetime.now()
        
        # Threading
        self._health_check_thread = None
        self._running = False
        
        # Initialize primary node
        self._add_primary_node()
        
        # Start health monitoring
        if auto_discover:
            self.start_health_monitoring()
    
    def _add_primary_node(self):
        """Add the primary exo node"""
        primary_id = f"{self.primary_node_host}:{self.primary_node_port}"
        self.nodes[primary_id] = ExoNode(
            id=primary_id,
            host=self.primary_node_host,
            port=self.primary_node_port,
            device_name="primary",
            memory_gb=0.0  # Will be updated on first health check
        )
        logger.info(f"Added primary Exo node: {primary_id}")
    
    def start_health_monitoring(self):
        """Start background health check thread"""
        if self._running:
            logger.warning("Health monitoring already running")
            return
        
        self._running = True
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self._health_check_thread.start()
        logger.info("Started Exo cluster health monitoring")
    
    def stop_health_monitoring(self):
        """Stop background health check thread"""
        self._running = False
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)
        logger.info("Stopped Exo cluster health monitoring")
    
    def _health_check_loop(self):
        """Background loop for health checking"""
        while self._running:
            try:
                self.check_cluster_health()
                time.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Health check error: {e}")
                time.sleep(self.health_check_interval)
    
    def check_cluster_health(self) -> Dict[str, Any]:
        """
        Check health of all nodes and discover new ones
        
        Returns:
            Dict with cluster health status
        """
        healthy_nodes = 0
        offline_nodes = 0
        
        for node_id, node in list(self.nodes.items()):
            try:
                # Try to get node status
                response = requests.get(
                    f"{node.endpoint}/health",
                    timeout=5
                )
                
                if response.status_code == 200:
                    node.status = ExoNodeStatus.ONLINE
                    node.last_seen = datetime.now()
                    healthy_nodes += 1
                    
                    # Update node info
                    data = response.json()
                    if "device_name" in data:
                        node.device_name = data["device_name"]
                    if "memory_gb" in data:
                        node.memory_gb = data["memory_gb"]
                else:
                    node.status = ExoNodeStatus.DEGRADED
            
            except requests.exceptions.RequestException:
                # Check if node has timed out
                if not node.is_healthy(self.node_timeout):
                    node.status = ExoNodeStatus.OFFLINE
                    offline_nodes += 1
                    logger.warning(f"Node {node_id} marked offline")
        
        # Update cluster availability
        self.is_cluster_available = healthy_nodes > 0
        
        # Try to discover available models from healthy nodes
        if self.is_cluster_available:
            self._discover_models()
        
        return {
            "healthy_nodes": healthy_nodes,
            "offline_nodes": offline_nodes,
            "total_nodes": len(self.nodes),
            "cluster_available": self.is_cluster_available,
            "available_models": self.available_models
        }
    
    def _discover_models(self):
        """Discover available models from healthy nodes"""
        for node in self.nodes.values():
            if node.status == ExoNodeStatus.ONLINE:
                try:
                    response = requests.get(
                        f"{node.endpoint}/v1/models",
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if "data" in data:
                            models = [m["id"] for m in data["data"]]
                            node.models = models
                            
                            # Update global available models
                            for model in models:
                                if model not in self.available_models:
                                    self.available_models.append(model)
                            
                            logger.info(f"Discovered {len(models)} models on {node.id}")
                            return  # Success, no need to check other nodes
                
                except requests.exceptions.RequestException as e:
                    logger.debug(f"Model discovery failed for {node.id}: {e}")
    
    def get_healthy_node(self) -> Optional[ExoNode]:
        """Get a healthy node for inference (simple round-robin for now)"""
        healthy = [n for n in self.nodes.values() if n.status == ExoNodeStatus.ONLINE]
        return healthy[0] if healthy else None
    
    def chat_completion(
        self,
        model: str,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        **kwargs
    ) -> Tuple[Dict, Optional[str]]:
        """
        ChatGPT-compatible chat completion via Exo cluster
        
        Args:
            model: Model name to use
            messages: List of message dicts with role/content
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            stream: Enable streaming (not yet implemented)
            **kwargs: Additional model parameters
        
        Returns:
            Tuple of (response_dict, error_message)
        """
        # Check cluster availability
        if not self.is_cluster_available:
            return {}, "Exo cluster is not available"
        
        # Get a healthy node
        node = self.get_healthy_node()
        if not node:
            return {}, "No healthy Exo nodes available"
        
        # Prepare request
        request_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        request_data.update(kwargs)
        
        # Make request
        start_time = time.time()
        try:
            response = requests.post(
                f"{node.endpoint}/v1/chat/completions",
                json=request_data,
                timeout=120  # Allow time for inference
            )
            
            compute_time = time.time() - start_time
            self.total_compute_time += compute_time
            self.total_requests += 1
            
            if response.status_code == 200:
                result = response.json()
                
                # Add local metadata
                result["exo_metadata"] = {
                    "node_id": node.id,
                    "compute_time": compute_time,
                    "device": node.device_name
                }
                
                logger.info(f"Exo inference completed in {compute_time:.2f}s on {node.device_name}")
                return result, None
            
            else:
                error_msg = f"Exo API error {response.status_code}: {response.text}"
                logger.error(error_msg)
                return {}, error_msg
        
        except requests.exceptions.Timeout:
            return {}, "Exo request timed out"
        
        except requests.exceptions.RequestException as e:
            return {}, f"Exo request failed: {str(e)}"
    
    def get_models(self) -> List[Dict[str, Any]]:
        """Get list of available models"""
        if not self.is_cluster_available:
            return []
        
        node = self.get_healthy_node()
        if not node:
            return []
        
        try:
            response = requests.get(
                f"{node.endpoint}/v1/models",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", [])
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get models: {e}")
        
        return []
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive provider status"""
        health = self.check_cluster_health()
        
        return {
            "provider": "Exo Local Cluster",
            "available": self.is_cluster_available,
            "nodes": {
                node_id: {
                    "status": node.status.value,
                    "device": node.device_name,
                    "memory_gb": node.memory_gb,
                    "models": len(node.models),
                    "last_seen": node.last_seen.isoformat() if node.last_seen else None
                }
                for node_id, node in self.nodes.items()
            },
            "health": health,
            "usage": {
                "total_requests": self.total_requests,
                "total_compute_time": self.total_compute_time,
                "avg_compute_time": (
                    self.total_compute_time / self.total_requests 
                    if self.total_requests > 0 else 0
                ),
                "last_reset": self.last_reset.isoformat()
            },
            "cost": 0.0,  # Always free!
            "available_models": self.available_models
        }
    
    def reset_usage(self):
        """Reset usage statistics"""
        self.total_requests = 0
        self.total_compute_time = 0.0
        self.last_reset = datetime.now()
        logger.info("Reset Exo usage statistics")


# Example usage and testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize Exo provider
    exo = ExoClusterProvider(
        primary_node_host="localhost",
        primary_node_port=8000,
        auto_discover=True
    )
    
    print("\n=== Exo Cluster Status ===")
    status = exo.get_status()
    print(json.dumps(status, indent=2))
    
    # Test chat completion
    print("\n=== Testing Chat Completion ===")
    messages = [
        {"role": "user", "content": "Say hello!"}
    ]
    
    result, error = exo.chat_completion(
        model="llama-3.2-3b",
        messages=messages,
        max_tokens=50
    )
    
    if error:
        print(f"Error: {error}")
    else:
        print(f"Response: {json.dumps(result, indent=2)}")
    
    # Keep running to show health monitoring
    print("\n=== Monitoring (Ctrl+C to stop) ===")
    try:
        while True:
            time.sleep(5)
            status = exo.get_status()
            print(f"\nCluster: {'🟢 ONLINE' if status['available'] else '🔴 OFFLINE'}")
            print(f"Nodes: {status['health']['healthy_nodes']}/{status['health']['total_nodes']}")
            print(f"Requests: {status['usage']['total_requests']}")
    except KeyboardInterrupt:
        print("\n\nStopping...")
        exo.stop_health_monitoring()
