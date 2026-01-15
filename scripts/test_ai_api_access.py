#!/usr/bin/env python3
"""
Test script to verify AI API access and model availability.

This script tests:
1. API connection to https://api.ai.tokamak.network
2. API key authentication
3. Model list access
4. Specific model (qwen3-235b) access
5. Chat completion with qwen3-235b

Usage:
    python scripts/test_ai_api_access.py
    python scripts/test_ai_api_access.py --model qwen3-235b
    python scripts/test_ai_api_access.py --test-chat
"""

import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
import httpx
from typing import Optional, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)
    print(f"✅ Loaded .env from: {env_path}")
else:
    print(f"⚠️  .env file not found at: {env_path}")

# Configuration
API_BASE_URL = os.getenv("AI_API_URL", "https://api.ai.tokamak.network")
API_KEY = os.getenv("AI_API_KEY", "")

# Allow override via command line
def get_api_key():
    """Get API key from environment or use default test key."""
    return API_KEY or "sk-VAPzM-_A3xhGK6tfr5uvBA"


def test_api_connection() -> bool:
    """Test basic API connection."""
    print("\n" + "="*60)
    print("1️⃣ Testing API Connection")
    print("="*60)
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{API_BASE_URL}/health", follow_redirects=True)
            if response.status_code == 200:
                print(f"✅ API is reachable at {API_BASE_URL}")
                return True
            else:
                print(f"⚠️  API returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Failed to connect to API: {e}")
        return False


def test_api_key() -> bool:
    """Test API key validity."""
    print("\n" + "="*60)
    print("2️⃣ Testing API Key")
    print("="*60)
    
    api_key = get_api_key()
    
    if not api_key:
        print("❌ API key not found")
        return False
    
    # Mask API key for display
    masked_key = f"{api_key[:10]}...{api_key[-4:]}" if len(api_key) > 14 else "***"
    print(f"🔑 API Key: {masked_key} (length: {len(api_key)})")
    print(f"🌐 API URL: {API_BASE_URL}")
    
    if API_KEY:
        print(f"✅ Using API key from environment variable (AI_API_KEY)")
    else:
        print(f"⚠️  Using default test API key (not from environment)")
    
    return True


def test_model_list() -> Optional[Dict[str, Any]]:
    """Test getting model list."""
    print("\n" + "="*60)
    print("3️⃣ Testing Model List Access")
    print("="*60)
    
    api_key = get_api_key()
    if not api_key:
        print("❌ API key not configured")
        return None
    
    try:
        with httpx.Client(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Try /v1/models first
            print(f"📤 Requesting: {API_BASE_URL}/v1/models")
            response = client.get(
                f"{API_BASE_URL}/v1/models",
                headers=headers
            )
            
            if response.status_code == 200:
                models_data = response.json()
                print(f"✅ Successfully retrieved model list (status: {response.status_code})")
                
                # Parse OpenAI format
                if "data" in models_data:
                    models = models_data["data"]
                    print(f"📋 Found {len(models)} models:")
                    for model in models[:10]:  # Show first 10
                        model_id = model.get("id", "unknown")
                        print(f"   - {model_id}")
                    
                    # Check if qwen3-235b is in the list
                    model_ids = [m.get("id", "") for m in models]
                    if "qwen3-235b" in model_ids:
                        print(f"\n✅ qwen3-235b is available in the model list!")
                    else:
                        print(f"\n⚠️  qwen3-235b NOT found in model list")
                        print(f"   Available models containing 'qwen':")
                        qwen_models = [m for m in model_ids if 'qwen' in m.lower()]
                        for m in qwen_models[:5]:
                            print(f"   - {m}")
                    
                    return models_data
                else:
                    print(f"⚠️  Unexpected response format: {json.dumps(models_data, indent=2)[:500]}")
                    return models_data
            else:
                print(f"❌ Failed to get model list (status: {response.status_code})")
                print(f"   Response: {response.text[:500]}")
                return None
                
    except httpx.TimeoutException:
        print("❌ Request timeout")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def test_model_access(model_name: str = "qwen3-235b") -> bool:
    """Test access to a specific model."""
    print("\n" + "="*60)
    print(f"4️⃣ Testing Model Access: {model_name}")
    print("="*60)
    
    api_key = get_api_key()
    if not api_key:
        print("❌ API key not configured")
        return False
    
    try:
        with httpx.Client(timeout=60.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello, this is a test. Please respond with 'OK' if you can read this."
                    }
                ],
                "max_tokens": 50
            }
            
            print(f"📤 Request URL: {API_BASE_URL}/v1/chat/completions")
            print(f"📤 Model: {model_name}")
            print(f"📤 Payload: {json.dumps(payload, indent=2)}")
            
            response = client.post(
                f"{API_BASE_URL}/v1/chat/completions",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Successfully accessed model {model_name}!")
                
                # Extract response content
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    print(f"\n📝 Model Response:")
                    print(f"   {content}")
                
                return True
            else:
                print(f"❌ Failed to access model (status: {response.status_code})")
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                
                if "error" in error_data:
                    error = error_data["error"]
                    print(f"\n❌ Error Details:")
                    print(f"   Type: {error.get('type', 'unknown')}")
                    print(f"   Message: {error.get('message', 'unknown')}")
                    print(f"   Code: {error.get('code', 'unknown')}")
                    
                    # Check for model access denied
                    if "not allowed" in error.get('message', '').lower() or "access" in error.get('type', '').lower():
                        print(f"\n💡 Solution:")
                        print(f"   1. Go to Admin UI: {API_BASE_URL}/ui")
                        print(f"   2. Find your API key")
                        print(f"   3. Add '{model_name}' to allowed models")
                        print(f"   4. Or update API key with models parameter:")
                        print(f"      curl -X POST '{API_BASE_URL}/key/generate' \\")
                        print(f"        -H 'Authorization: Bearer <master-key>' \\")
                        print(f"        -H 'Content-Type: application/json' \\")
                        print(f"        -d '{{\"models\": [\"{model_name}\"]}}'")
                
                print(f"\n   Full Response: {response.text[:1000]}")
                return False
                
    except httpx.TimeoutException:
        print("❌ Request timeout")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chat_completion(model_name: str = "qwen3-235b", test_message: str = "Say hello in one sentence.") -> bool:
    """Test full chat completion."""
    print("\n" + "="*60)
    print(f"5️⃣ Testing Chat Completion: {model_name}")
    print("="*60)
    
    api_key = get_api_key()
    if not api_key:
        print("❌ API key not configured")
        return False
    
    try:
        with httpx.Client(timeout=60.0) as client:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": test_message
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 200
            }
            
            print(f"📤 Sending chat request to {model_name}")
            print(f"📤 Message: {test_message}")
            
            response = client.post(
                f"{API_BASE_URL}/v1/chat/completions",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Chat completion successful!")
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})
                    
                    print(f"\n📝 Response:")
                    print(f"   {content}")
                    print(f"\n📊 Usage:")
                    print(f"   Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                    print(f"   Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                    print(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")
                
                return True
            else:
                print(f"❌ Chat completion failed (status: {response.status_code})")
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error = error_data["error"]
                        print(f"   Error: {error.get('message', 'Unknown error')}")
                except:
                    print(f"   Response: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Test AI API access and model availability")
    parser.add_argument("--model", default="qwen3-235b", help="Model name to test (default: qwen3-235b)")
    parser.add_argument("--test-chat", action="store_true", help="Test full chat completion")
    parser.add_argument("--skip-connection", action="store_true", help="Skip connection test")
    parser.add_argument("--skip-models", action="store_true", help="Skip model list test")
    
    args = parser.parse_args()
    
    print("🚀 AI API Access Test Script")
    print("="*60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Target Model: {args.model}")
    print("="*60)
    
    results = {
        "connection": False,
        "api_key": False,
        "model_list": False,
        "model_access": False,
        "chat_completion": False
    }
    
    # Test 1: API Connection
    if not args.skip_connection:
        results["connection"] = test_api_connection()
    
    # Test 2: API Key
    results["api_key"] = test_api_key()
    if not results["api_key"]:
        print("\n❌ Cannot proceed without API key. Please set AI_API_KEY environment variable.")
        return 1
    
    # Test 3: Model List
    if not args.skip_models:
        models_data = test_model_list()
        results["model_list"] = models_data is not None
    
    # Test 4: Model Access
    results["model_access"] = test_model_access(args.model)
    
    # Test 5: Chat Completion (if requested or if model access succeeded)
    if args.test_chat or results["model_access"]:
        results["chat_completion"] = test_chat_completion(args.model)
    
    # Summary
    print("\n" + "="*60)
    print("📊 Test Summary")
    print("="*60)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:20s}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 All tests passed! API access is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
