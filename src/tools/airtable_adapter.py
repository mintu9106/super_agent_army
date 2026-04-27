# src/tools/airtable_adapter.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

def create_base_with_tables(base_name, tables):
    """
    Creates a new Airtable base. tables: list of dicts with 'name' and 'fields'.
    'fields' can be a list of strings (e.g., ["Name", "Email"])
    or objects (e.g., [{"name": "Name", "type": "singleLineText"}]).
    This function normalizes strings into objects with type 'singleLineText'.
    """
    api_key = os.getenv("AIRTABLE_API_KEY")
    if not api_key:
        return {"status": "error", "message": "AIRTABLE_API_KEY not set in .env"}

    # Normalize fields: ensure each field is an object with name and type
    for table in tables:
        if "fields" in table and isinstance(table["fields"], list):
            normalized = []
            for f in table["fields"]:
                if isinstance(f, str):
                    normalized.append({"name": f, "type": "singleLineText"})
                elif isinstance(f, dict) and "name" in f:
                    if "type" not in f:
                        f["type"] = "singleLineText"
                    normalized.append(f)
                else:
                    # skip invalid
                    pass
            table["fields"] = normalized

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "name": base_name,
        "tables": tables
    }

    resp = None
    try:
        resp = requests.post(
            "https://api.airtable.com/v0/meta/bases",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        base_id = data["id"]
        table_ids = [table["id"] for table in data.get("tables", [])]
        print(f"✅ Real Airtable base '{base_name}' created with ID: {base_id}")
        return {"status": "success", "base_id": base_id, "table_ids": table_ids}
    except Exception as e:
        print(f"❌ Airtable API error: {e}")
        if resp is not None and resp.text:
            print(f"   Response: {resp.text}")
        return {"status": "error", "message": str(e)}