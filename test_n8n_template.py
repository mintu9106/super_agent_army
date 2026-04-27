# test_n8n_template.py
import json
import sys
sys.path.append('src')
from tools.n8n_templates import build_workflow_from_spec

spec = {
    "workflow_name": "Test Workflow",
    "nodes": [
        {"template": "manual_trigger"},
        {"template": "http_request", "overrides": {"parameters": {"url": "https://httpbin.org/get"}}},
        {"template": "slack_message", "overrides": {"parameters": {"channel": "#test", "text": "Done"}}}
    ],
    "connections": [{"from": 0, "to": 1}, {"from": 1, "to": 2}]
}

workflow_json = build_workflow_from_spec(spec)
print(json.dumps(workflow_json, indent=2))

with open('test_workflow.json', 'w') as f:
    json.dump(workflow_json, f, indent=2)

print("\n✅ Workflow JSON saved to test_workflow.json")