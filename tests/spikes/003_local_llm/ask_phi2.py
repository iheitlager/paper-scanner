
import requests


def ask_phi2(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate", json={"model": "phi", "prompt": prompt, "stream": False}
    )
    return response.json()["response"]


# Use it
result = ask_phi2("Extract the title from this paper...")
print(result)
