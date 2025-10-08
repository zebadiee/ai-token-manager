#!/usr/bin/env python3
"""
Quick validation script to ensure everything is configured correctly
Run this before deployment to catch common issues
"""

import os
import sys
import json
from pathlib import Path

def validate_structure():
    """Validate project structure"""
    required_files = [
        'enhanced_multi_provider_manager.py',
        'requirements.txt',
        'README.md',
        'DEPLOYMENT.md',
        'Dockerfile',
        'docker-compose.yml',
        '.env.example',
        '.gitignore',
        'health_check.py',
        'start.sh'
    ]
    
    missing = []
    for file in required_files:
        if not Path(file).exists():
            missing.append(file)
    
    if missing:
        print(f"❌ Missing required files: {', '.join(missing)}")
        return False
    
    print("✅ All required files present")
    return True

def validate_dependencies():
    """Check if requirements.txt is valid"""
    try:
        with open('requirements.txt') as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
            
        required_packages = ['streamlit', 'requests', 'cryptography', 'pandas']
        found = []
        
        for line in lines:
            package = line.split('>=')[0].split('==')[0].lower()
            if package in required_packages:
                found.append(package)
        
        missing = set(required_packages) - set(found)
        if missing:
            print(f"❌ Missing required packages in requirements.txt: {', '.join(missing)}")
            return False
        
        print(f"✅ All required packages in requirements.txt ({len(lines)} total)")
        return True
        
    except Exception as e:
        print(f"❌ Error reading requirements.txt: {e}")
        return False

def validate_env_example():
    """Check if .env.example has all required keys"""
    try:
        with open('.env.example') as f:
            content = f.read()
        
        required_keys = ['OPENROUTER_API_KEY', 'HUGGINGFACE_API_KEY', 'TOGETHER_API_KEY']
        
        for key in required_keys:
            if key not in content:
                print(f"❌ Missing {key} in .env.example")
                return False
        
        print("✅ .env.example contains all required keys")
        return True
        
    except Exception as e:
        print(f"❌ Error reading .env.example: {e}")
        return False

def validate_docker():
    """Validate Docker configuration"""
    try:
        with open('Dockerfile') as f:
            content = f.read()
        
        if 'enhanced_multi_provider_manager.py' not in content:
            print("❌ Dockerfile missing main application file")
            return False
        
        if 'streamlit run' not in content:
            print("❌ Dockerfile missing streamlit run command")
            return False
        
        print("✅ Dockerfile configuration valid")
        return True
        
    except Exception as e:
        print(f"❌ Error reading Dockerfile: {e}")
        return False

def validate_gitignore():
    """Check if sensitive files are in .gitignore"""
    try:
        with open('.gitignore') as f:
            content = f.read()
        
        required_ignores = ['.env', '.token_manager_key', 'venv/']
        
        for item in required_ignores:
            if item not in content:
                print(f"❌ .gitignore missing: {item}")
                return False
        
        print("✅ .gitignore properly configured")
        return True
        
    except Exception as e:
        print(f"❌ Error reading .gitignore: {e}")
        return False

def validate_main_app():
    """Basic syntax check of main application"""
    try:
        with open('enhanced_multi_provider_manager.py') as f:
            code = f.read()
        
        # Try to compile
        compile(code, 'enhanced_multi_provider_manager.py', 'exec')
        
        # Check for critical imports
        if 'import streamlit' not in code:
            print("❌ Main app missing streamlit import")
            return False
        
        if 'class EnhancedTokenManager' not in code:
            print("❌ Main app missing EnhancedTokenManager class")
            return False
        
        print("✅ Main application syntax valid")
        return True
        
    except SyntaxError as e:
        print(f"❌ Syntax error in main application: {e}")
        return False
    except Exception as e:
        print(f"❌ Error validating main application: {e}")
        return False

def main():
    """Run all validations"""
    print("=" * 70)
    print("🔍 Pre-Deployment Validation")
    print("=" * 70)
    print()
    
    validations = [
        ("Project Structure", validate_structure),
        ("Dependencies", validate_dependencies),
        ("Environment Template", validate_env_example),
        ("Docker Configuration", validate_docker),
        (".gitignore", validate_gitignore),
        ("Main Application", validate_main_app),
    ]
    
    all_passed = True
    
    for name, validator in validations:
        print(f"📋 Validating {name}...")
        if not validator():
            all_passed = False
        print()
    
    print("=" * 70)
    if all_passed:
        print("✅ All Validations Passed - Ready for Deployment!")
        print()
        print("Next steps:")
        print("  1. Set up environment variables or .env file")
        print("  2. Run: ./start.sh")
        print("  3. Or build Docker: docker-compose up -d")
        sys.exit(0)
    else:
        print("❌ Validation Failed - Fix errors before deploying")
        sys.exit(1)

if __name__ == "__main__":
    main()
