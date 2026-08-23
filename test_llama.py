# test_llama.py

def print_hello_world():
    """Prints 'hello world' to the console."""
    print('hello world')

if __name__ == "__main__":
    print_hello_world()

import requests
import time

def make_api_call(prompt, api_key, max_retries=3):
    """Make an API call to OpenRouter with retry logic and error handling."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "meta-llama/llama-3.1-8b-instruct",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                print("Error: Unauthorized. Please check your API key.")
                return None
            print(f"HTTP Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            print(f"Request Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    print("Failed to make API call after retries.")
    return None
