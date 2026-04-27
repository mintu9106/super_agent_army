# src/tools/n8n_templates.py
import json

NODE_TEMPLATES = {
    "manual_trigger": {
        "name": "Manual Trigger",
        "type": "n8n-nodes-base.manualTrigger",
        "parameters": {}
    },
    "webhook_trigger": {
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "parameters": {
            "path": "webhook",
            "responseMode": "onReceived",
            "options": {}
        }
    },
    "airtable_trigger": {
        "name": "Airtable Trigger",
        "type": "n8n-nodes-base.airtableTrigger",
        "parameters": {
            "base": {"value": "={{$credentials.airtableBaseId}}"},
            "table": {"value": ""},
            "triggerOn": "recordCreated"
        }
    },
    "http_request": {
        "name": "HTTP Request",
        "type": "n8n-nodes-base.httpRequest",
        "parameters": {
            "url": "",
            "method": "GET",
            "authentication": "none",
            "sendBody": False,
            "sendHeaders": False,
            "sendQuery": False,
            "options": {}
        }
    },
    "slack_message": {
        "name": "Slack",
        "type": "n8n-nodes-base.slack",
        "parameters": {
            "resource": "message",
            "operation": "post",
            "channel": "",
            "text": ""
        }
    },
    "if": {
        "name": "IF",
        "type": "n8n-nodes-base.if",
        "parameters": {
            "conditions": {
                "string": [
                    {
                        "value1": "",
                        "operation": "equals",
                        "value2": ""
                    }
                ]
            }
        }
    },
    "function": {
        "name": "Function",
        "type": "n8n-nodes-base.function",
        "parameters": {
            "functionCode": "// Your JavaScript code here\nreturn items;"
        }
    },
    "noop": {
        "name": "No Operation",
        "type": "n8n-nodes-base.noOp",
        "parameters": {}
    }
}

# SPECIAL RULES per node type
# - "stringify": इन फ़ील्ड्स के मान को JSON string में बदलना है (HTTP body, headers आदि)
# - "keep_object": इन फ़ील्ड्स को हमेशा n8n ऑब्जेक्ट/एरे ही रहने देना है (IF की conditions, Slack के विकल्प आदि)
# - "function_code": functionCode हमेशा string होना चाहिए
NODE_PROCESSING_RULES = {
    "n8n-nodes-base.httpRequest": {
        "stringify": ["body", "headers", "queryParameters", "bodyParameters"],
        "keep_object": ["options"]
    },
    "n8n-nodes-base.if": {
        "keep_object": ["conditions"]
    },
    "n8n-nodes-base.function": {
        "function_code": True
    }
    # बाकी नोड्स के लिए कोई विशेष नियम नहीं
}

def sanitize_node_parameters(node_type, params):
    """
    Node type के हिसाब से parameters को ठीक करता है।
    """
    if not isinstance(params, dict):
        return params

    rules = NODE_PROCESSING_RULES.get(node_type, {})

    # ----- Function node: functionCode हमेशा string हो -----
    if rules.get("function_code") and "functionCode" in params:
        if isinstance(params["functionCode"], dict):
            params["functionCode"] = json.dumps(params["functionCode"], ensure_ascii=False)
        elif isinstance(params["functionCode"], list):
            params["functionCode"] = json.dumps(params["functionCode"], ensure_ascii=False)
        # else: पहले से string है, ठीक है

    # ----- stringify वाले फ़ील्ड -----
    for field in rules.get("stringify", []):
        if field in params and isinstance(params[field], (dict, list)):
            params[field] = json.dumps(params[field], ensure_ascii=False)

    # ----- keep_object वाले फ़ील्ड: अगर गलती से string बन गए हों तो उन्हें वापस ऑब्जेक्ट में बदलें -----
    for field in rules.get("keep_object", []):
        if field in params and isinstance(params[field], str):
            try:
                parsed = json.loads(params[field])
                if isinstance(parsed, (dict, list)):
                    params[field] = parsed
            except json.JSONDecodeError:
                # वैध JSON नहीं है, जैसा है रहने दें
                pass

    return params


def build_workflow_from_spec(spec):
    nodes = []
    for i, node_spec in enumerate(spec["nodes"]):
        template_name = node_spec["template"]
        if template_name not in NODE_TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}")
        # Deep copy
        node = json.loads(json.dumps(NODE_TEMPLATES[template_name]))
        node["position"] = [250 + (i * 250), 300]

        # Apply overrides
        if "overrides" in node_spec:
            overrides = node_spec["overrides"]
            for key, value in overrides.items():
                if key == "parameters":
                    # value dict हो, update करें
                    node["parameters"].update(value)
                else:
                    node[key] = value

        # 🔥 अब इस नोड के पैरामीटर को उसके type के अनुसार sanitize करें
        node["parameters"] = sanitize_node_parameters(node["type"], node["parameters"])
        nodes.append(node)

    # Connections बनाएँ
    connections = {}
    for conn in spec.get("connections", []):
        from_idx = conn["from"]
        to_idx = conn["to"]
        output_branch = conn.get("output", 0)
        from_name = nodes[from_idx]["name"]
        to_name = nodes[to_idx]["name"]
        if from_name not in connections:
            connections[from_name] = {"main": []}
        while len(connections[from_name]["main"]) <= output_branch:
            connections[from_name]["main"].append([])
        connections[from_name]["main"][output_branch].append({
            "node": to_name,
            "type": "main",
            "index": 0
        })

    # अगर कोई connection नहीं दी गई तो default linear chain बनाएँ
    if not connections and len(nodes) > 1:
        for i in range(len(nodes) - 1):
            from_name = nodes[i]["name"]
            to_name = nodes[i + 1]["name"]
            if from_name not in connections:
                connections[from_name] = {"main": [[]]}
            connections[from_name]["main"][0].append({"node": to_name, "type": "main", "index": 0})

    return {
        "name": spec["workflow_name"],
        "nodes": nodes,
        "connections": connections,
        "settings": {}
    }