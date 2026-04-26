"""
Module for interacting with a local LLM API.
"""

import json
import requests


def generate_response(prompt: str, model: str = "llama3"):
    """
    Sends a prompt to the local LLM API and prints the streaming response.
    """
    url = "http://localhost:11434/api/generate"  # Adjust URL and port as per your setup
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model,
        "prompt": prompt,
    }

    try:
        response = requests.post(
            url, headers=headers, json=data, stream=True, timeout=120
        )
        response.raise_for_status()  # Raise an exception for bad status codes

        for line in response.iter_lines():
            if line:
                try:
                    # Each line is a JSON object, parse it
                    json_line = json.loads(line.decode("utf-8"))

                    # Extract the response part and print it without a newline
                    response_piece = json_line.get("response", "")
                    print(response_piece, end="", flush=True)

                    # If the response is done, print a newline and exit the loop
                    if json_line.get("done"):
                        print()  # Final newline
                        break
                except json.JSONDecodeError:
                    print(f"Error decoding JSON: {line.decode('utf-8')}")

    except requests.exceptions.RequestException as exc:
        print(f"\nError making API call: {exc}")

if __name__ == "__main__":
    generate_response("What is the capital of France?")
