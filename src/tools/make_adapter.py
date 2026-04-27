# src/tools/make_adapter.py
import os
import json
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

def _get_env(key, default=None):
    value = os.getenv(key, default)
    if value is None or value == "":
        raise ValueError(f"Environment variable '{key}' is not set.")
    return value

def _headers():
    return {
        "Authorization": f"Token {_get_env('MAKE_API_KEY')}",
        "Content-Type": "application/json"
    }

MODULE_TYPE_MAP = {
    "webhook": "webhook:Webhook",
    "jotformTrigger": "jotform:watchForSubmissions",
    "clickUpCreateTask": "clickup:createTaskInList",
    "xeroCreateContact": "xero:CreateContact",
    "slackSendMessage": "slack:CreateMessage",
}

def _build_flow(blueprint):
    flow = blueprint.get("flow")
    if not flow:
        modules = blueprint.get("modules", [])
        if not modules:
            raise ValueError("Blueprint must contain 'flow' or 'modules'.")
        flow = []
        for idx, mod in enumerate(modules, start=1):
            module_type = mod.get("type", "unknown")
            if module_type in MODULE_TYPE_MAP:
                module_type = MODULE_TYPE_MAP[module_type]
            flow.append({
                "id": idx,
                "module": module_type,
                "version": 1,
                "parameters": mod.get("parameters", {}),
                "mapper": mod.get("mapper", {}),
                "metadata": {}
            })
    return flow

def create_scenario(name: str, blueprint: dict) -> dict:
    try:
        org_id = _get_env("MAKE_ORG_ID")
        team_id = os.getenv("MAKE_TEAM_ID") or None
        base_url = os.getenv("MAKE_BASE_URL", "https://eu1.make.com/api/v2")

        flow = _build_flow(blueprint)

        # Blueprint string: no scheduling inside
        scenario_blueprint = {
            "name": name,
            "flow": flow,
            "metadata": {
                "instant": True,
                "version": 1,
                "scenario": {
                    "roundtrips": 1,
                    "maxErrors": 3,
                    "autoCommit": True,
                    "autoCommitTriggerLast": True,
                    "sequential": False,
                    "confidential": False,
                    "dataloss": False,
                    "dlq": False,
                    "freshVariables": False
                }
            }
        }

        # Scheduling as a JSON string – "indefinitely" for webhook/instant triggers
        scheduling = json.dumps({"type": "indefinitely"})

        payload = {
            "blueprint": json.dumps(scenario_blueprint),
            "scheduling": scheduling,
            "orgId": org_id,
            "teamId": team_id
        }

        print(f"📤 Creating Make scenario '{name}' with {len(flow)} module(s)…")

        resp = requests.post(
            f"{base_url}/scenarios",
            headers=_headers(),
            json=payload
        )

        if not resp.ok:
            detail = resp.text[:500]
            print(f"❌ Make API returned {resp.status_code}")
            print(f"   Response: {detail}")
            resp.raise_for_status()

        created = resp.json()
        scenario_id = created.get("id")
        print(f"✅ Make scenario created! ID: {scenario_id}")
        return {"status": "success", "scenario_id": scenario_id}

    except Exception as e:
        print(f"❌ Make scenario creation failed: {e}")
        return {"status": "error", "message": str(e)}


def call_make_webhook(webhook_url, data):
    try:
        resp = requests.post(webhook_url, json=data)
        resp.raise_for_status()
        print("✅ Make webhook called successfully")
        return {"status": "success", "response": resp.text}
    except Exception as e:
        print(f"❌ Make webhook error: {e}")
        return {"status": "error", "message": str(e)}