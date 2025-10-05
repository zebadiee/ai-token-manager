#!/usr/bin/env python3
"""
Exo Provider API Examples

Demonstrates how to use Exo as a provider in your applications
with automatic failover and unified provider interface.
"""

import json
import logging
from typing import List, Dict, Optional
from exo_integration import ExoTokenManagerIntegration, ExoReliakitProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UnifiedLLMClient:
    """
    Unified LLM client that uses Exo first, falls back to cloud
    
    Example of how to integrate into your applications.
    """
    
    def __init__(
        self,
        exo_host: str = "localhost",
        exo_port: int = 8000,
        cloud_providers: Optional[List] = None
    ):
        """
        Initialize unified client
        
        Args:
            exo_host: Exo cluster host
            exo_port: Exo cluster port
            cloud_providers: List of cloud provider objects (OpenRouter, HF, etc.)
        """
        self.exo = ExoTokenManagerIntegration(
            exo_host=exo_host,
            exo_port=exo_port,
            enable_auto_failover=True
        )
        self.cloud_providers = cloud_providers or []
        self.exo.start()
        
        logger.info("Unified LLM client initialized")
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "llama-3.2-3b",
        temperature: float = 0.7,
        max_tokens: int = 512,
        prefer_local: bool = True,
        **kwargs
    ) -> Dict:
        """
        Send chat completion request
        
        Args:
            messages: List of message dicts
            model: Model name
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            prefer_local: Try Exo first if True
            **kwargs: Additional parameters
        
        Returns:
            Response dictionary with metadata
        """
        # Define cloud fallback
        def cloud_fallback(model, messages, **kwargs):
            if not self.cloud_providers:
                return {}, "No cloud providers configured"
            
            # Try each cloud provider
            for provider in self.cloud_providers:
                try:
                    response = provider.chat_completion(
                        model=model,
                        messages=messages,
                        **kwargs
                    )
                    return response, None
                except Exception as e:
                    logger.warning(f"Cloud provider {provider} failed: {e}")
                    continue
            
            return {}, "All cloud providers failed"
        
        # Route request
        if prefer_local:
            response, error, provider_used = self.exo.route_request(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                cloud_provider_callback=cloud_fallback,
                **kwargs
            )
        else:
            # Force cloud
            response, error = cloud_fallback(model, messages, **kwargs)
            provider_used = "Cloud (Forced)"
        
        # Add metadata
        result = {
            "response": response,
            "error": error,
            "provider": provider_used,
            "cost": 0.0 if "Exo" in provider_used else None  # Calculate for cloud
        }
        
        return result
    
    def get_status(self) -> Dict:
        """Get status of all providers"""
        return self.exo.get_unified_status()
    
    def close(self):
        """Cleanup"""
        self.exo.stop()


# Example 1: Basic chat completion
def example_basic_chat():
    """Basic chat completion with automatic failover"""
    print("\n" + "="*60)
    print("Example 1: Basic Chat Completion")
    print("="*60)
    
    client = UnifiedLLMClient()
    
    # Simple chat
    result = client.chat(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the capital of France?"}
        ],
        model="llama-3.2-3b",
        max_tokens=100
    )
    
    print(f"\nProvider used: {result['provider']}")
    print(f"Cost: ${result['cost']}" if result['cost'] else "Cost: FREE (local)")
    
    if result['error']:
        print(f"Error: {result['error']}")
    else:
        # Extract response text
        response_text = result['response'].get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f"\nResponse:\n{response_text}")
    
    client.close()


# Example 2: Streaming conversation
def example_conversation():
    """Multi-turn conversation"""
    print("\n" + "="*60)
    print("Example 2: Multi-Turn Conversation")
    print("="*60)
    
    client = UnifiedLLMClient()
    
    conversation = []
    
    # Turn 1
    conversation.append({"role": "user", "content": "Tell me a joke about AI"})
    result = client.chat(messages=conversation, max_tokens=150)
    
    if not result['error']:
        response = result['response']['choices'][0]['message']['content']
        print(f"\nAssistant: {response}")
        conversation.append({"role": "assistant", "content": response})
        
        # Turn 2
        conversation.append({"role": "user", "content": "Explain why that's funny"})
        result = client.chat(messages=conversation, max_tokens=200)
        
        if not result['error']:
            response = result['response']['choices'][0]['message']['content']
            print(f"\nAssistant: {response}")
    
    client.close()


# Example 3: Batch processing with status monitoring
def example_batch_processing():
    """Process multiple requests with monitoring"""
    print("\n" + "="*60)
    print("Example 3: Batch Processing with Monitoring")
    print("="*60)
    
    client = UnifiedLLMClient()
    
    prompts = [
        "Write a haiku about programming",
        "What is 2+2?",
        "Name three colors",
        "What is the speed of light?"
    ]
    
    results = []
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\nProcessing {i}/{len(prompts)}: {prompt[:50]}...")
        
        result = client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        
        results.append({
            "prompt": prompt,
            "provider": result['provider'],
            "success": not result['error']
        })
    
    # Summary
    print("\n" + "-"*60)
    print("Batch Summary:")
    exo_count = sum(1 for r in results if "Exo" in r['provider'])
    cloud_count = len(results) - exo_count
    success_count = sum(1 for r in results if r['success'])
    
    print(f"Total requests: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Exo (local): {exo_count}")
    print(f"Cloud: {cloud_count}")
    
    # Get detailed status
    status = client.get_status()
    print(f"\nExo cluster status: {status['recommendation']}")
    
    client.close()


# Example 4: With reliakit self-healing
def example_reliakit_integration():
    """Demonstrate reliakit-compatible self-healing"""
    print("\n" + "="*60)
    print("Example 4: Reliakit Self-Healing Integration")
    print("="*60)
    
    # Setup
    integration = ExoTokenManagerIntegration()
    reliakit_provider = ExoReliakitProvider(integration)
    
    # Health check
    health = reliakit_provider.health_check()
    print(f"\nHealth Check:")
    print(json.dumps(health, indent=2))
    
    if health['healthy']:
        print("\n✅ Exo cluster is healthy")
    else:
        print("\n⚠️ Exo cluster unhealthy - attempting recovery...")
        
        if reliakit_provider.attempt_recovery():
            print("✅ Recovery successful")
        else:
            print("❌ Recovery failed - using cloud failover")
            reliakit_provider.on_failure()
    
    integration.stop()


# Example 5: Custom provider selection
def example_custom_routing():
    """Custom provider selection logic"""
    print("\n" + "="*60)
    print("Example 5: Custom Provider Routing")
    print("="*60)
    
    client = UnifiedLLMClient()
    
    # Get status to make informed decision
    status = client.get_status()
    exo_available = status['exo']['available']
    
    prompts = [
        ("Fast query - prefer local", "What is 1+1?", True),
        ("Complex query - use cloud", "Write a detailed essay about AI", False),
        ("Auto-select", "Hello world", True)
    ]
    
    for description, prompt, prefer_local in prompts:
        print(f"\n{description}")
        print(f"Prompt: {prompt}")
        print(f"Strategy: {'Local first' if prefer_local else 'Cloud only'}")
        
        result = client.chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50,
            prefer_local=prefer_local and exo_available
        )
        
        print(f"Used: {result['provider']}")
    
    client.close()


# Example 6: Error handling and retries
def example_error_handling():
    """Robust error handling"""
    print("\n" + "="*60)
    print("Example 6: Error Handling and Retries")
    print("="*60)
    
    client = UnifiedLLMClient()
    
    def safe_chat(messages, max_retries=3):
        """Chat with automatic retries"""
        for attempt in range(max_retries):
            try:
                result = client.chat(messages=messages)
                
                if not result['error']:
                    return result
                
                logger.warning(f"Attempt {attempt + 1} failed: {result['error']}")
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} exception: {e}")
        
        return {"error": "All retries failed", "response": {}, "provider": "None"}
    
    # Test with retry
    result = safe_chat([{"role": "user", "content": "Hello!"}])
    
    if result['error']:
        print(f"❌ Failed after retries: {result['error']}")
    else:
        print(f"✅ Success with provider: {result['provider']}")
    
    client.close()


# Main execution
if __name__ == "__main__":
    print("\n" + "="*60)
    print("EXO PROVIDER API EXAMPLES")
    print("="*60)
    print("\nThese examples demonstrate integrating Exo into your applications")
    print("with automatic failover, health monitoring, and unified APIs.")
    print("\nPrerequisites:")
    print("  • Exo cluster running at localhost:8000")
    print("  • Run: python3 ~/exo/main.py")
    print("\n" + "="*60)
    
    try:
        # Run examples
        example_basic_chat()
        example_conversation()
        example_batch_processing()
        example_reliakit_integration()
        example_custom_routing()
        example_error_handling()
        
        print("\n" + "="*60)
        print("✅ All examples completed!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()
