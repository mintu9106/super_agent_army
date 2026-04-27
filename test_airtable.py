import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("AIRTABLE_API_KEY")
if not api_key:
    print("AIRTABLE_API_KEY not set")
    exit(1)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "name": "Test Base",
    "tables": [
        {
            "name": "Leads",
            "fields": [
                {"name": "Name", "type": "singleLineText"},
                {"name": "Email", "type": "email"}
            ]
        }
    ]
}

print("Sending payload:")
print(payload)
resp = requests.post("https://api.airtable.com/v0/meta/bases", headers=headers, json=payload)
print(f"Status: {resp.status_code}")
print("Response:")
print(resp.text)