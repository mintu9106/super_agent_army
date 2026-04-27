# src/agent_orchestrator.py
import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools.n8n_templates import build_workflow_from_spec, NODE_TEMPLATES
from tools.airtable_adapter import create_base_with_tables

load_dotenv()

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)

# ========== TOOL DEFINITIONS ==========
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "build_n8n_workflow",
            "description": "Create an n8n workflow using predefined node templates. Available templates: " + ", ".join(NODE_TEMPLATES.keys()),
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_name": {"type": "string", "description": "Name of the workflow"},
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "template": {"type": "string", "enum": list(NODE_TEMPLATES.keys())},
                                "overrides": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "parameters": {"type": "object"}
                                    }
                                }
                            },
                            "required": ["template"]
                        }
                    },
                    "connections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "integer", "description": "Index of source node"},
                                "to": {"type": "integer", "description": "Index of target node"},
                                "output": {"type": "integer", "default": 0, "description": "Output branch number (0 for main)"}
                            },
                            "required": ["from", "to"]
                        }
                    }
                },
                "required": ["workflow_name", "nodes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "setup_airtable_base",
            "description": "Create Airtable base and tables. USE ONLY when client explicitly mentions Airtable and requires a new base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "base_name": {"type": "string"},
                    "tables": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "fields": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "type": {"type": "string", "description": "Airtable field type (singleLineText, email, phoneNumber, checkbox, number, dateTime, etc.)"}
                                        },
                                        "required": ["name", "type"]
                                    }
                                }
                            },
                            "required": ["name", "fields"]
                        }
                    }
                },
                "required": ["base_name", "tables"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_ghl_automation",
            "description": "Setup GoHighLevel automation. USE ONLY when client explicitly mentions GoHighLevel or GHL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "trigger_type": {"type": "string"},
                    "actions": {"type": "array"}
                },
                "required": ["name", "trigger_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_slack_notification",
            "description": "Send a Slack message to a channel. Use only when Slack is mentioned or clearly needed for notifications.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "message": {"type": "string"}
                },
                "required": ["channel", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_clickup_task",
            "description": "Create a new task in ClickUp. Only use when ClickUp is explicitly mentioned.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Task name"},
                    "list_id": {"type": "string", "description": "ClickUp list ID (default from env if not provided)"},
                    "description": {"type": "string", "default": ""},
                    "assignee": {"type": "string", "description": "Assignee user ID"},
                    "due_date": {"type": "integer", "description": "Due date as Unix timestamp (milliseconds)"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "call_make_webhook",
            "description": "Trigger a Make.com scenario webhook. Only use when Make.com is explicitly mentioned.",
            "parameters": {
                "type": "object",
                "properties": {
                    "webhook_url": {"type": "string", "description": "The webhook URL to call"},
                    "data": {"type": "object", "description": "JSON payload to send"}
                },
                "required": ["webhook_url", "data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_clickup_space",
            "description": "Create a new Space in ClickUp. Use when the job requires setting up a ClickUp workspace structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the space"},
                    "team_id": {"type": "string", "description": "ClickUp Team ID (default from env)"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_clickup_folder",
            "description": "Create a new Folder in a ClickUp Space.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the folder"},
                    "space_id": {"type": "string", "description": "ID of the parent Space"}
                },
                "required": ["name", "space_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_clickup_list",
            "description": "Create a new List in a ClickUp Space or Folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the list"},
                    "space_id": {"type": "string", "description": "Space ID (required if no folder)"},
                    "folder_id": {"type": "string", "description": "Folder ID (optional, takes priority over space)"}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_n8n_credential",
            "description": "Create a credential in n8n for a specific node type. Use this before building a workflow that relies on these credentials. Only create credentials that are explicitly needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Display name for the credential"},
                    "credential_type": {
                        "type": "string",
                        "description": "n8n credential type",
                        "enum": ["slackApi", "clickUpApi", "httpHeaderAuth", "openAiApi"]
                    },
                    "data": {
                        "type": "object",
                        "description": "Credential data. For slackApi: {accessToken: 'xoxb-...'}; for clickUpApi: {apiToken: 'pk_...'}; for httpHeaderAuth: {name: 'Header Auth', value: 'Bearer xxx'}; for openAiApi: {apiKey: 'sk-...'}"
                    }
                },
                "required": ["name", "credential_type", "data"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_make_scenario",
            "description": "Create a Make.com scenario directly via API. Only use if API permissions are available; if 403 error, automatically use save_make_scenario_file instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Scenario name"},
                    "blueprint": {
                        "type": "object",
                        "description": "Scenario blueprint containing 'flow', 'scheduling', and 'metadata'. Use 'flow' array, not 'modules'. Scheduling type must be 'indefinitely' for instant triggers."
                    }
                },
                "required": ["name", "blueprint"]
            }
        }
    },
    # ---- NEW TOOL ----
    {
        "type": "function",
        "function": {
            "name": "save_make_scenario_file",
            "description": "Save a Make.com scenario blueprint as an importable JSON file. Use this when the API fails with 403 or when you are on a free plan. The file will be stored in the 'make_scenarios' folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Name of the JSON file (without extension). Use a descriptive name."},
                    "blueprint": {
                        "type": "object",
                        "description": "The complete scenario blueprint containing 'flow' (array of module objects), 'scheduling' (e.g., {\"type\":\"indefinitely\"}), and 'metadata'."
                    }
                },
                "required": ["filename", "blueprint"]
            }
        }
    }
]

# ========== TOOL IMPLEMENTATIONS ==========
def build_n8n_workflow(workflow_name, nodes, connections=None):
    """Build and create n8n workflow from template spec."""
    print(f"\n🔧 [n8n] Building workflow: '{workflow_name}'")
    spec = {"workflow_name": workflow_name, "nodes": nodes, "connections": connections or []}
    try:
        workflow_json = build_workflow_from_spec(spec)
    except Exception as e:
        print(f"❌ Failed to build workflow from spec: {e}")
        return {"status": "error", "message": str(e)}
    base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        return {"status": "error", "message": "N8N_API_KEY missing in .env"}
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    print("📤 Final Payload to n8n:")
    print(json.dumps(workflow_json, indent=2))
    try:
        resp = requests.post(f"{base_url}/workflows", headers=headers, json=workflow_json)
        resp.raise_for_status()
        created = resp.json()
        print(f"✅ Workflow created! ID: {created.get('id')}")
        print(f"   URL: http://localhost:5678/workflow/{created.get('id')}")
        if not created.get('nodes'):
            print("⚠️ Workflow created but nodes empty – possible schema mismatch.")
            return {"status": "partial", "message": "Nodes missing in created workflow", "workflow": created}
        print(f"   Nodes count: {len(created.get('nodes'))}")
        return {"status": "success", "workflow": created}
    except requests.exceptions.RequestException as e:
        print(f"❌ n8n API Error: {e}")
        if e.response is not None:
            print(f"   Response: {e.response.text}")
        return {"status": "error", "message": str(e)}

def setup_airtable_base(base_name, tables):
    print(f"\n🗂️ [Airtable] Client will use their existing base '{base_name}' with table(s): {tables}")
    return {"status": "success", "message": "Airtable base creation is not performed. Use existing base."}

def create_ghl_automation(name, trigger_type, actions):
    print(f"\n📈 [GHL] Mock: Automation '{name}' ({trigger_type}) created.")
    return {"status": "success", "automation_id": "mock-ghl-789"}

def send_slack_notification(channel, message):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL not set"}
    payload = {"text": f"[#{channel}] {message}"}
    try:
        resp = requests.post(webhook_url, json=payload)
        resp.raise_for_status()
        print(f"✅ Slack message sent to {channel}")
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Slack error: {e}")
        return {"status": "error", "message": str(e)}

def create_clickup_task(name, list_id=None, description="", assignee=None, due_date=None):
    from tools.clickup_adapter import create_task as clickup_create
    return clickup_create(name, list_id, description, assignee, due_date)

def call_make_webhook(webhook_url, data):
    from tools.make_adapter import call_make_webhook as make_call
    return make_call(webhook_url, data)

def create_clickup_space(name, team_id=None):
    from tools.clickup_adapter import create_space
    return create_space(name, team_id)

def create_clickup_folder(name, space_id):
    from tools.clickup_adapter import create_folder
    return create_folder(name, space_id)

def create_clickup_list(name, space_id=None, folder_id=None):
    from tools.clickup_adapter import create_list
    return create_list(name, space_id, folder_id)

def create_n8n_credential(name, credential_type, data):
    base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        return {"status": "error", "message": "N8N_API_KEY missing"}
    headers = {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"}
    payload = {"name": name, "type": credential_type, "data": data}
    try:
        resp = requests.post(f"{base_url}/credentials", headers=headers, json=payload)
        resp.raise_for_status()
        created = resp.json()
        print(f"✅ Credential '{name}' of type '{credential_type}' created (ID: {created.get('id')})")
        return {"status": "success", "id": created.get("id")}
    except Exception as e:
        print(f"❌ Credential creation failed: {e}")
        return {"status": "error", "message": str(e)}

def create_make_scenario(name, blueprint):
    from tools.make_adapter import create_scenario
    return create_scenario(name, blueprint)

def save_make_scenario_file(filename, blueprint):
    """Save a Make.com scenario blueprint as an importable JSON file."""
    folder = os.path.join(os.path.dirname(__file__), "..", "make_scenarios")
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, f"{filename}.json")
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(blueprint, f, indent=2)
        print(f"✅ Make scenario saved to {filepath}")
        return {"status": "success", "file_path": filepath}
    except Exception as e:
        print(f"❌ Failed to save Make scenario file: {e}")
        return {"status": "error", "message": str(e)}

TOOL_FUNCTIONS = {
    "build_n8n_workflow": build_n8n_workflow,
    "setup_airtable_base": setup_airtable_base,
    "create_ghl_automation": create_ghl_automation,
    "send_slack_notification": send_slack_notification,
    "create_clickup_task": create_clickup_task,
    "call_make_webhook": call_make_webhook,
    "create_clickup_space": create_clickup_space,
    "create_clickup_folder": create_clickup_folder,
    "create_clickup_list": create_clickup_list,
    "create_n8n_credential": create_n8n_credential,
    "create_make_scenario": create_make_scenario,
    "save_make_scenario_file": save_make_scenario_file
}

# ========== ORCHESTRATOR ==========
def analyze_job_and_execute(job_description: str):
    system_prompt = """You are a super‑agent that receives job descriptions and instantly builds the requested automation solution.
You NEVER respond as a freelancer or write a cover letter. Even if the description contains screening questions, you ignore them and proceed to design the solution.

**PLATFORM DETECTION:**
- If the job explicitly asks for a **Make.com scenario**, you MUST design the scenario and then save it using the `save_make_scenario_file` tool. The user will import the file manually. Do NOT call `create_make_scenario` unless the user specifically requests API creation.
- If the job asks for an **n8n workflow**, build it using the template system.
- If the job does not specify a platform, default to n8n workflow.

**Make.com Scenario Creation (CRITICAL):**
- Because of Make.com API restrictions on free plans, always use `save_make_scenario_file` to save the blueprint to the `make_scenarios` folder. The user can then import the file via Make.com's "Import from file" feature.
- The blueprint must be a complete, import‑ready JSON object containing:
  - **"flow"**: an array of module objects. Each module must have:
    - `"id"` (integer, starting from 1)
    - `"module"` (exact Make.com module type string, e.g., `"jotform:watchForSubmissions"`, `"clickup:createTaskInList"`, `"xero:CreateContact"`, `"slack:CreateMessage"`)
    - `"version"` (1)
    - `"parameters"` (object, e.g., connection placeholders, or `{__IMTCONN__: null}` if not known)
    - `"mapper"` (object, field mappings using Make.com variable syntax, e.g., `{"name": "{{1.request.q3_q3_fullname1.first}} {{1.request.q3_q3_fullname1.last}}"}`)
    - `"metadata"` (object, can be empty)
  - **"scheduling"**: `{"type": "indefinitely"}` for instant/webhook‑triggered scenarios
  - **"metadata"**: `{"instant": true, "version": 1, "scenario": {...}}` (standard structure)
- Always include correct field mappings based on the client's form fields (e.g., from JotForm: `q3_q3_fullname1.first`, `q6_q6_email4`, `q10_q10_radio8`, etc.). Use the exact custom field IDs from the client's ClickUp (e.g., `"eb1d2f27-cb13-41ff-b370-b11b623e27b9"` for Email).
- Provide the file path after saving so the user knows where to find it.

**n8n WORKFLOW CREATION RULES:**
You MUST design workflows using the template system. Available templates: """ + ", ".join(NODE_TEMPLATES.keys()) + """
...

**CLIENT-FIRST MINIMALISM (CRITICAL):**
1. ONLY use tools and platforms that are EXPLICITLY named in the job description.
2. For idempotency / duplicate prevention, prefer lightweight solutions inside n8n or rely on Make.com's deduplication features.
3. Before calling any tool, verify it is explicitly needed.

**PRODUCTION QUALITY:**
- Include error handling branches where applicable.
- Keep the workflow as simple as possible.

**Reference Blueprint Example (JotForm → ClickUp → Xero → Slack):**
```json
{
  "flow": [
    {
      "id": 1,
      "module": "jotform:watchForSubmissions",
      "version": 1,
      "parameters": { "__IMTHOOK__": null },
      "mapper": {},
      "metadata": {}
    },
    {
      "id": 2,
      "module": "clickup:createTaskInList",
      "version": 2,
      "parameters": { "__IMTCONN__": null },
      "mapper": {
        "name": "{{1.request.q3_q3_fullname1.first}} {{1.request.q3_q3_fullname1.last}}",
        "list_id": "901817007752",
        "team_id": "90182197585",
        "space_id": "901810406212",
        "folder_id": "901813116461",
        "notify_all": false,
        "custom_fields": {
          "eb1d2f27-cb13-41ff-b370-b11b623e27b9": "{{1.request.q6_q6_email4}}",
          "e509e11c-6a4a-422c-b0c0-bc09141b1d0c": "{{1.request.q5_q5_textbox3}}",
          "4ff308be-5e4d-4af0-9209-21e056cac760": "{{1.request.q10_q10_radio8}}",
          "be5573d6-fe6d-499d-a608-ebace4b51f43": "{{1.request.q7_q7_textbox5}}",
          "1144103c-59a3-49fd-918d-6cfb8671458b": "{{1.request.q8_q8_address6.addr_line1}}{{1.request.q8_q8_address6.addr_line2}}{{1.request.q8_q8_address6.city}}{{1.request.q8_q8_address6.state}}{{1.request.q8_q8_address6.postal}}{{1.request.q8_q8_address6.country}}",
          "33e7dd6a-0c2f-42bd-9c2a-d9ddfc58a446": "{{1.request.q27_phoneNumber.area}}{{1.request.q27_phoneNumber.phone}}",
          "4f04c455-c23f-4f4a-828d-f740886b4a0f": "{{1.request.q14_q14_textbox12}}",
          "f077aa14-d35d-4fcd-9010-fe9d86258bf6": "{{1.request.q13_q13_textbox11}}",
          "f4a4c9f1-3d27-413d-9c54-4c6bdb8da062": "{{1.request.q12_q12_dropdown10}}"
        },
        "due_date_time": false,
        "start_date_time": false
      },
      "metadata": {}
    },
    {
      "id": 4,
      "module": "xero:CreateContact",
      "version": 2,
      "parameters": { "__IMTCONN__": null },
      "mapper": {
        "Name": "{{1.request.q3_q3_fullname1.first}} {{1.request.q3_q3_fullname1.last}}",
        "EmailAddress": "{{1.request.q6_q6_email4}}",
        "ContactNumber": "{{1.request.q27_phoneNumber.area}}{{1.request.q27_phoneNumber.phone}}",
        "tenantId": "af454e20-21ef-4fdb-92e2-ca998769a431"
      },
      "metadata": {}
    },
    {
      "id": 7,
      "module": "slack:CreateMessage",
      "version": 4,
      "parameters": { "__IMTCONN__": null },
      "mapper": {
        "text": "🚀 New Client Alert! 🚀\n\nA new lead just entered the system!\n\n👤 Name: {{4.Name}}\n📧 Email: {{4.EmailAddress}}\n\n🔗 Open in ClickUp: {{2.url}}\n\n✅ Xero Contact Created Successfully!\n\nLet's close this deal! 🔥\n\n",
        "parse": false,
        "mrkdwn": true,
        "channel": "C0AP0QU82HM",
        "channelType": "public",
        "channelWType": "list"
      },
      "metadata": {}
    }
  ],
  "scheduling": { "type": "indefinitely" },
  "metadata": { "instant": true, "version": 1, "scenario": { "roundtrips": 1, "maxErrors": 3, "autoCommit": true, "autoCommitTriggerLast": true, "sequential": false, "confidential": false, "dataloss": false, "dlq": false, "freshVariables": false } }
}

"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Job Description:\n{job_description}\n\nAnalyze and take only the necessary actions. Do not add any tool or platform not mentioned in the job."}
    ]

    max_iterations = 8
    for i in range(max_iterations):
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.1
        )
        msg = response.choices[0].message
        messages.append(msg)
        
        if msg.content:
            print(f"\n💭 Agent: {msg.content}")
        
        if not msg.tool_calls:
            print("\n✅ Agent finished actions.")
            break
        
        for tc in msg.tool_calls:
            fname = tc.function.name
            try:
                fargs = json.loads(tc.function.arguments)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in arguments: {e}"
                print(f"❌ {error_msg}")
                print(f"   Raw arguments: {tc.function.arguments[:200]}...")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps({"status": "error", "message": error_msg})
                })
                continue

            print(f"\n⚡ Calling {fname}")
            func = TOOL_FUNCTIONS.get(fname)
            if func:
                result = func(**fargs)
            else:
                result = {"error": f"Unknown function {fname}"}
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result)
            })
    else:
        print("\n⚠️ Max iterations reached.")


def process_job_from_text(job_text: str):
    """Entry point for text-based job descriptions (Telegram, etc.)."""
    analyze_job_and_execute(job_text)


if __name__ == "__main__":
    job_file = input("Enter job description file path: ").strip()
    if not os.path.exists(job_file):
        print("File not found.")
        exit(1)
    with open(job_file, 'r', encoding='utf-8') as f:
        job_text = f.read()
    print(f"\n📄 Loaded: {job_text[:200]}...\n")
    analyze_job_and_execute(job_text)