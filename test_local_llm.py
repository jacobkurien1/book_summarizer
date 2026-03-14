import requests
import json

url = "http://localhost:11434/api/generate" # Adjust URL and port as per your setup
headers = {"Content-Type": "application/json"}
data = {
    "model": "llama3", # Replace with your loaded model name
    "prompt": "What is the capital of France?"
}

try:
    response = requests.post(url, headers=headers, json=data, stream=True, timeout=120)
    response.raise_for_status() # Raise an exception for bad status codes

    for line in response.iter_lines():
        if line:
            try:
                # Each line is a JSON object, parse it
                json_line = json.loads(line.decode('utf-8'))
                
                # Extract the response part and print it without a newline
                response_piece = json_line.get("response", "")
                print(response_piece, end='', flush=True)
                
                # If the response is done, print a newline and exit the loop
                if json_line.get("done"):
                    print() # Final newline
                    break
            except json.JSONDecodeError:
                print(f"Error decoding JSON: {line.decode('utf-8')}")

except requests.exceptions.RequestException as e:
    print(f"\nError making API call: {e}")