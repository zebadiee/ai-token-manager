#!/usr/bin/env python3
"""
Health Check Script for AI Token Manager
Validates system status and dependencies
"""

import sys
import os
import json
from pathlib import Path

def check_python_version():
    """Check Python version compatibility"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        return False, f"Python {version.major}.{version.minor} (requires 3.8+)"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"

def check_dependencies():
    """Check if required packages are installed"""
    required = ['streamlit', 'requests', 'cryptography', 'pandas']
    missing = []
    versions = {}
    
    for package in required:
        try:
            module = __import__(package)
            versions[package] = getattr(module, '__version__', 'unknown')
        except ImportError:
            missing.append(package)
    
    if missing:
        return False, f"Missing packages: {', '.join(missing)}"
    return True, versions

def check_config_files():
    """Check configuration file status"""
    config_file = Path.home() / '.token_manager_config.json'
    key_file = Path.home() / '.token_manager_key'
    
    status = {}
    
    if config_file.exists():
        try:
            with open(config_file) as f:
                data = json.load(f)
                status['config'] = f"Found ({len(data.get('providers', []))} providers)"
        except Exception as e:
            status['config'] = f"Error reading: {e}"
    else:
        status['config'] = "Not found (will be created on first run)"
    
    if key_file.exists():
        status['key'] = "Found"
    else:
        status['key'] = "Not found (will be created on first run)"
    
    return True, status

def check_environment_variables():
    """Check for API key environment variables"""
    env_vars = {
        'OPENROUTER_API_KEY': os.getenv('OPENROUTER_API_KEY'),
        'HUGGINGFACE_API_KEY': os.getenv('HUGGINGFACE_API_KEY'),
        'TOGETHER_API_KEY': os.getenv('TOGETHER_API_KEY'),
    }
    
    found = {k: 'Set' if v else 'Not set' for k, v in env_vars.items()}
    any_set = any(env_vars.values())
    
    return True, found

def check_main_file():
    """Check if main application file exists"""
    main_file = Path('enhanced_multi_provider_manager.py')
    
    if not main_file.exists():
        return False, "Main application file not found"
    
    size = main_file.stat().st_size
    return True, f"Found ({size:,} bytes)"

def main():
    """Run all health checks"""
    print("=" * 60)
    print("🏥 AI Token Manager - Health Check")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Configuration Files", check_config_files),
        ("Environment Variables", check_environment_variables),
        ("Application File", check_main_file),
    ]
    
    all_passed = True
    
    for name, check_func in checks:
        print(f"📋 {name}:")
        try:
            passed, result = check_func()
            
            if isinstance(result, dict):
                for key, value in result.items():
                    status = "✓" if passed else "✗"
                    print(f"   {status} {key}: {value}")
            else:
                status = "✓" if passed else "✗"
                print(f"   {status} {result}")
            
            if not passed:
                all_passed = False
                
        except Exception as e:
            print(f"   ✗ Error: {e}")
            all_passed = False
        
        print()
    
    print("=" * 60)
    if all_passed:
        print("✅ Health Check Passed - System Ready")
        sys.exit(0)
    else:
        print("❌ Health Check Failed - See errors above")
        sys.exit(1)

if __name__ == "__main__":
    main()
