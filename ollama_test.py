import requests
import json

def query_ollama(prompt):
    url="http://localhost:11434/api/generate"
    data={
        "model":"gemma4:e2b",
        "prompt":prompt
    }
    headers = {
        "Content-Type": "application/json"}
    try:
        response = requests.post(url, data=json.dumps(data), headers=headers, stream=True)
        response.raise_for_status()

        full_response = ""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                json_line = json.loads(decoded_line)
                full_response += json_line.get("response", "")
        return full_response
    except requests.exceptions.RequestException as e:
        return f"Error: {e}"

if __name__ == "__main__":
    prompt = "Compadre, quienes fueron los califas ortodoxos?"
    response = query_ollama(prompt)
    print(f"Prompt: {prompt}\nResponse: {response}")
        