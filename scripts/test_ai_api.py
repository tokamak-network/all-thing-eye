#!/usr/bin/env python3
"""Test AI API connection."""
import os
import asyncio
import httpx
from dotenv import load_dotenv
load_dotenv()

async def test_ai():
    api_key = os.getenv("AI_API_KEY", "")
    api_url = os.getenv("AI_API_URL", "https://api.ai.tokamak.network")
    
    print(f"AI API URL: {api_url}")
    print(f"AI API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test 1: List models
        print("\n=== Test 1: List Models ===")
        try:
            response = await client.get(f"{api_url}/v1/models", headers=headers)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Available models: {data}")
            else:
                print(f"Error: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 2: Simple chat completion
        print("\n=== Test 2: Chat Completion ===")
        payload = {
            "messages": [
                {"role": "user", "content": "Hello, say 'test passed' in one word"}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        try:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=payload,
                headers=headers
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {data}")
            else:
                print(f"Error response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test 3: With model specified (if model is required)
        print("\n=== Test 3: Chat with model ===")
        payload_with_model = {
            "messages": [
                {"role": "user", "content": "Hello"}
            ],
            "model": "gpt-4o-mini"  # Try common model name
        }
        
        try:
            response = await client.post(
                f"{api_url}/v1/chat/completions",
                json=payload_with_model,
                headers=headers
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response: {data}")
            else:
                print(f"Error response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    asyncio.run(test_ai())
