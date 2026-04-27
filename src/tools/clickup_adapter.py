# src/tools/clickup_adapter.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN")
BASE_URL = "https://api.clickup.com/api/v2"

def _headers():
    return {
        "Authorization": CLICKUP_API_TOKEN,
        "Content-Type": "application/json"
    }

def create_space(name, team_id=None):
    """Create a new Space in a ClickUp team. Returns JSON."""
    team_id = team_id or os.getenv("CLICKUP_TEAM_ID")
    if not team_id:
        return {"status": "error", "message": "CLICKUP_TEAM_ID not set"}
    url = f"{BASE_URL}/team/{team_id}/space"
    payload = {"name": name, "multiple_assignees": True}
    resp = requests.post(url, headers=_headers(), json=payload)
    if resp.ok:
        data = resp.json()
        print(f"✅ ClickUp Space created: {data.get('id')}")
        return {"status": "success", "space": data}
    else:
        print(f"❌ ClickUp Space error: {resp.status_code} {resp.text}")
        return {"status": "error", "message": resp.text}

def create_folder(name, space_id):
    """Create a Folder in a Space."""
    url = f"{BASE_URL}/space/{space_id}/folder"
    payload = {"name": name}
    resp = requests.post(url, headers=_headers(), json=payload)
    if resp.ok:
        data = resp.json()
        print(f"✅ ClickUp Folder created: {data.get('id')}")
        return {"status": "success", "folder": data}
    else:
        print(f"❌ ClickUp Folder error: {resp.status_code} {resp.text}")
        return {"status": "error", "message": resp.text}

def create_list(name, space_id=None, folder_id=None):
    """Create a List in a Space or Folder."""
    parent_id = folder_id or space_id
    if not parent_id:
        return {"status": "error", "message": "Neither folder_id nor space_id provided"}
    is_folder = bool(folder_id)
    endpoint = f"folder/{parent_id}/list" if is_folder else f"space/{parent_id}/list"
    url = f"{BASE_URL}/{endpoint}"
    # Removed "status": "Open" to let ClickUp use workspace default
    payload = {
        "name": name,
        "content": ""
    }
    resp = requests.post(url, headers=_headers(), json=payload)
    if resp.ok:
        data = resp.json()
        print(f"✅ ClickUp List created: {data.get('id')}")
        return {"status": "success", "list": data}
    else:
        print(f"❌ ClickUp List error: {resp.status_code} {resp.text}")
        return {"status": "error", "message": resp.text}

def create_task(name, list_id=None, description="", assignee=None, due_date=None):
    """Create a task in a ClickUp list. Returns JSON response."""
    list_id = list_id or os.getenv("CLICKUP_LIST_ID")
    if not list_id:
        return {"status": "error", "message": "CLICKUP_LIST_ID not set and no list_id provided"}
    url = f"{BASE_URL}/list/{list_id}/task"
    payload = {
        "name": name,
        "description": description,
        "status": "to do",
        "due_date": str(int(due_date)) if due_date else None,
        "due_date_time": False,
        "assignees": [assignee] if assignee else []
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    resp = requests.post(url, headers=_headers(), json=payload)
    if resp.ok:
        data = resp.json()
        print(f"✅ ClickUp task created: {data.get('id')}")
        return {"status": "success", "task": data}
    else:
        print(f"❌ ClickUp task error: {resp.status_code} {resp.text}")
        return {"status": "error", "message": resp.text}