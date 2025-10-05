#!/usr/bin/env python3
"""Smoke test - quick functionality check"""

import sys
import os

def smoke_test():
    """Quick smoke test of the token manager"""
    print("=" * 60)
    print("💨 Smoke Test - AI Token Manager")
    print("=" * 60)
    
    # Test 1: Import main module
    print("\n1️⃣  Testing module import...")
    try:
        from enhanced_multi_provider_manager import (
            EnhancedTokenManager,
            OpenRouterProvider,
            HuggingFaceProvider,
            TogetherAIProvider,
            SecureStorage
        )
        print("   ✓ All imports successful")
    except Exception as e:
        print(f"   ✗ Import failed: {e}")
        return False
    
    # Test 2: Initialize manager
    print("\n2️⃣  Testing manager initialization...")
    try:
        manager = EnhancedTokenManager()
        print(f"   ✓ Manager initialized")
        print(f"   ✓ Config file: {manager.config_file}")
        print(f"   ✓ Providers loaded: {len(manager.providers)}")
    except Exception as e:
        print(f"   ✗ Manager init failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 3: Create providers (without API keys)
    print("\n3️⃣  Testing provider creation...")
    try:
        # Test with empty API keys (should work)
        or_provider = OpenRouterProvider("")
        hf_provider = HuggingFaceProvider("")
        ta_provider = TogetherAIProvider("")
        
        print(f"   ✓ OpenRouter: {or_provider.config.name}")
        print(f"   ✓ HuggingFace: {hf_provider.config.name}")
        print(f"   ✓ Together AI: {ta_provider.config.name}")
    except Exception as e:
        print(f"   ✗ Provider creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 4: Encryption
    print("\n4️⃣  Testing encryption...")
    try:
        test_key = "sk-test-1234567890"
        encrypted = SecureStorage.encrypt_api_key(test_key)
        decrypted = SecureStorage.decrypt_api_key(encrypted)
        
        assert decrypted == test_key, "Encryption/decryption mismatch!"
        print(f"   ✓ Encryption works")
        print(f"   ✓ Decryption works")
        print(f"   ✓ Round-trip verified")
    except Exception as e:
        print(f"   ✗ Encryption test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Config persistence
    print("\n5️⃣  Testing config persistence...")
    try:
        # Save config
        manager.save_config()
        print(f"   ✓ Config saved")
        
        # Check file exists
        if os.path.exists(manager.config_file):
            print(f"   ✓ Config file created: {manager.config_file}")
        else:
            print(f"   ⚠  Config file not found")
    except Exception as e:
        print(f"   ✗ Config persistence failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 6: Provider management
    print("\n6️⃣  Testing provider management...")
    try:
        initial_count = len(manager.providers)
        
        # Add a test provider
        test_provider = OpenRouterProvider("sk-test-key")
        manager.add_provider(test_provider)
        
        after_add = len(manager.providers)
        print(f"   ✓ Provider added (count: {initial_count} -> {after_add})")
        
        # Get providers directly from list
        providers = manager.providers
        print(f"   ✓ Retrieved {len(providers)} providers")
        
        for p in providers:
            print(f"     - {p.config.name}")
        
        # Test get current provider
        current = manager.get_current_provider()
        if current:
            print(f"   ✓ Current provider: {current.config.name}")
        
    except Exception as e:
        print(f"   ✗ Provider management failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✅ Smoke Test Complete - All tests passed!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = smoke_test()
    sys.exit(0 if success else 1)
