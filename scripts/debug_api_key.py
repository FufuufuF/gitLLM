import os
import requests
import json

API_KEY = "sk-5e140475e2e34eb0833d034f87f8581b"

def test_rest_api():
    print(f"Testing API Key: {API_KEY[:5]}...{API_KEY[-4:]}")
    
    # URL for Qwen/Dashscope (OpenAI Compatible)
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "qwen-plus",
        "messages": [
            {"role": "user", "content": "Hello"}
        ]
    }
    
    try:
        print(f"Sending request to {url}...")
        response = requests.post(url, headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            print("SUCCESS: API Key is valid (OpenAI Compatible Endpoint).")
        else:
            print("FAILURE: API Key seems invalid or endpoint incorrect.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_rest_api()
