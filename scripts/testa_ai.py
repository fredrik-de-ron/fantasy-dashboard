import httpx
import json
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    print("Fel: ANTHROPIC_API_KEY hittades inte i .env")
    exit()

print("API-nyckel hittad, testar anslutning...")

svar = httpx.post(
    "https://api.anthropic.com/v1/messages",
    headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    },
    json={
        "model": "claude-sonnet-4-6",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user",
                "content": "Svara bara: API-anslutningen fungerar!"
            }
        ]
    }
)

if svar.status_code == 200:
    data = svar.json()
    print(data["content"][0]["text"])
else:
    print(f"Fel: {svar.status_code}")
    print(svar.text)