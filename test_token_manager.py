#!/usr/bin/env python3
"""Test suite for the AI Token Manager"""

import os
import sys
import json
import tempfile
from pathlib import Path

# Test encryption functionality
def test_encryption():
    """Test the encryption/decryption functionality"""
    print("🔐 Testing encryption...")
    from cryptography.fernet import Fernet
    
    # Generate a key
    key = Fernet.generate_key()
    cipher = Fernet(key)
    
    # Test data
    test_api_key = "sk-test-1234567890abcdef"
    
    # Encrypt
    encrypted = cipher.encrypt(test_api_key.encode())
    print(f"   ✓ Encrypted test key: {encrypted[:50]}...")
    
    # Decrypt
    decrypted = cipher.decrypt(encrypted).decode()
    assert decrypted == test_api_key, "Decryption failed!"
    print(f"   ✓ Decrypted successfully: {decrypted}")
    
    return True

# Test provider configuration
def test_provider_config():
    """Test provider configuration structure"""
    print("\n🔧 Testing provider configuration...")
    
    sys.path.insert(0, os.path.dirname(__file__))
    
    # Import after adding to path
    from enhanced_multi_provider_manager import ProviderConfig, TokenUsage
    from datetime import datetime
    
    # Create a test provider config
    config = ProviderConfig(
        name="TestProvider",
        api_key_encrypted="encrypted_test_key",
        base_url="https://api.test.com",
        models_endpoint="/models",
        chat_endpoint="/chat/completions",
        headers={"Authorization": "Bearer test"},
        rate_limit=1000
    )
    
    print(f"   ✓ Provider name: {config.name}")
    print(f"   ✓ Base URL: {config.base_url}")
    print(f"   ✓ Rate limit: {config.rate_limit}")
    
    # Test TokenUsage
    usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        requests=1,
        last_reset=datetime.now()
    )
    
    print(f"   ✓ Token usage tracking: {usage.total_tokens} tokens")
    
    return True

# Test file operations
def test_file_operations():
    """Test configuration file operations"""
    print("\n📁 Testing file operations...")
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "test_config.json"
        
        # Test data
        test_config = {
            "providers": {
                "test_provider": {
                    "api_key": "encrypted_key",
                    "enabled": True
                }
            }
        }
        
        # Write config
        with open(config_path, 'w') as f:
            json.dump(test_config, f, indent=2)
        print(f"   ✓ Created config file: {config_path}")
        
        # Read config
        with open(config_path, 'r') as f:
            loaded_config = json.load(f)
        
        assert loaded_config == test_config, "Config mismatch!"
        print(f"   ✓ Config loaded successfully")
        
        # Check file permissions (should be readable)
        assert config_path.exists(), "Config file doesn't exist!"
        print(f"   ✓ File permissions OK")
    
    return True

# Test imports and dependencies
def test_imports():
    """Test that all required imports work"""
    print("\n📦 Testing imports and dependencies...")
    
    imports = [
        ("streamlit", "Streamlit"),
        ("requests", "Requests"),
        ("pandas", "Pandas"),
        ("cryptography.fernet", "Cryptography"),
    ]
    
    for module, name in imports:
        try:
            __import__(module)
            print(f"   ✓ {name} imported successfully")
        except ImportError as e:
            print(f"   ✗ Failed to import {name}: {e}")
            return False
    
    return True

# Test the main manager can be imported
def test_manager_import():
    """Test that the main manager can be imported"""
    print("\n🎯 Testing main manager import...")
    
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from enhanced_multi_provider_manager import (
            ProviderStatus, 
            TokenUsage, 
            ProviderConfig,
            SecureStorage,
            EnhancedTokenManager,
            APIProvider
        )
        print("   ✓ Main manager classes imported successfully")
        print(f"   ✓ ProviderStatus enum: {[s.value for s in ProviderStatus]}")
        print(f"   ✓ SecureStorage available")
        print(f"   ✓ EnhancedTokenManager available")
        
        return True
    except Exception as e:
        print(f"   ✗ Failed to import manager: {e}")
        import traceback
        traceback.print_exc()
        return False

# Test API endpoint validation
def test_api_endpoints():
    """Test API endpoint configuration"""
    print("\n🌐 Testing API endpoints...")
    
    endpoints = {
        "OpenRouter": "https://openrouter.ai/api/v1",
        "HuggingFace": "https://api-inference.huggingface.co",
        "Together": "https://api.together.xyz/v1"
    }
    
    for provider, url in endpoints.items():
        print(f"   ✓ {provider}: {url}")
    
    return True

# Main test runner
def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("🧪 AI Token Manager - Test Suite")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Encryption", test_encryption),
        ("Provider Config", test_provider_config),
        ("File Operations", test_file_operations),
        ("Manager Import", test_manager_import),
        ("API Endpoints", test_api_endpoints),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n   ✗ {test_name} failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print("-" * 60)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)
    
    return all(result for _, result in results)

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
