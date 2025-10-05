#!/usr/bin/env python3
"""Test for the enum serialization bug fix"""

import sys
import os

def test_enum_bug_fix():
    """Test that ProviderStatus enum is properly serialized and deserialized"""
    print("=" * 70)
    print("🐛 Bug Fix Test - Enum Serialization Issue")
    print("=" * 70)
    
    from enhanced_multi_provider_manager import (
        EnhancedTokenManager,
        ProviderStatus,
        OpenRouterProvider
    )
    
    print("\n1️⃣  Testing save with enum status...")
    manager = EnhancedTokenManager()
    
    # Ensure we have at least one provider
    if len(manager.providers) == 0:
        provider = OpenRouterProvider("test-key")
        manager.add_provider(provider)
    
    # Check that status is an enum
    for provider in manager.providers:
        print(f"   Provider: {provider.config.name}")
        print(f"   Status type: {type(provider.config.status)}")
        print(f"   Status value: {provider.config.status}")
        assert isinstance(provider.config.status, ProviderStatus), \
            f"Status should be ProviderStatus enum, got {type(provider.config.status)}"
    
    print("   ✓ All providers have ProviderStatus enum")
    
    print("\n2️⃣  Testing save config...")
    manager.save_config()
    print("   ✓ Config saved")
    
    print("\n3️⃣  Testing load config...")
    manager2 = EnhancedTokenManager()
    print(f"   ✓ Loaded {len(manager2.providers)} providers")
    
    print("\n4️⃣  Testing loaded status types...")
    for provider in manager2.providers:
        print(f"   Provider: {provider.config.name}")
        print(f"   Status type: {type(provider.config.status)}")
        print(f"   Status value: {provider.config.status}")
        assert isinstance(provider.config.status, ProviderStatus), \
            f"Status should be ProviderStatus enum after loading, got {type(provider.config.status)}"
    
    print("   ✓ All loaded providers have ProviderStatus enum")
    
    print("\n5️⃣  Testing get_provider_status() - the original error...")
    try:
        status_list = manager2.get_provider_status()
        print(f"   ✓ get_provider_status() succeeded")
        print(f"   ✓ Returned {len(status_list)} statuses")
        
        for status in status_list:
            print(f"     - {status['name']}: {status['status']}")
            # Verify the status is a string value, not enum
            assert isinstance(status['status'], str), \
                f"Status in return should be string, got {type(status['status'])}"
        
        print("   ✓ All status values are strings")
        
    except AttributeError as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("✅ Bug Fix Verified - Enum serialization works correctly!")
    print("=" * 70)
    
    print("\n📋 Summary:")
    print("  • Status saved as enum value string in JSON")
    print("  • Status loaded back as ProviderStatus enum")
    print("  • get_provider_status() returns string values")
    print("  • No 'str' object has no attribute 'value' errors")
    
    return True

if __name__ == "__main__":
    success = test_enum_bug_fix()
    sys.exit(0 if success else 1)
