import json
import uuid
import os

def gen_id():
    return str(uuid.uuid4())

nodes = []
connections = {}

def add_node(node_def):
    nodes.append(node_def)
    if node_def['name'] not in connections:
        connections[node_def['name']] = {"main": [[]]}

def connect(from_name, to_name, output_idx=0, input_idx=0, conn_type="main"):
    if from_name not in connections:
        connections[from_name] = {}
    if conn_type not in connections[from_name]:
        connections[from_name][conn_type] = []
    
    while len(connections[from_name][conn_type]) <= output_idx:
        connections[from_name][conn_type].append([])
        
    connections[from_name][conn_type][output_idx].append({
        "node": to_name,
        "type": conn_type,
        "index": input_idx
    })

# 1. Webhook
add_node({
    "parameters": {
        "httpMethod": "POST",
        "path": "audio-submission",
        "responseMode": "onReceived",
        "options": {}
    },
    "id": gen_id(),
    "name": "Webhook Trigger",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 1.1,
    "position": [0, 0],
    "webhookId": gen_id()
})

# 2. Config
add_node({
    "parameters": {
        "assignments": {
            "assignments": [
                {
                    "id": "cfg-api",
                    "name": "apiBaseUrl",
                    "value": "https://jump-bishop-initially-striking.trycloudflare.com",
                    "type": "string"
                }
            ]
        },
        "options": {}
    },
    "id": gen_id(),
    "name": "Run Config",
    "type": "n8n-nodes-base.set",
    "typeVersion": 3.4,
    "position": [200, 0]
})
connect("Webhook Trigger", "Run Config")

# 3. HTTP Request - Fetch History
add_node({
    "parameters": {
        "url": "={{ $('Run Config').first().json.apiBaseUrl }}/api/worker-history",
        "sendQuery": True,
        "queryParameters": {
            "parameters": [
                {
                    "name": "phone",
                    "value": "={{ $('Webhook Trigger').first().json.body.phone }}"
                }
            ]
        },
        "options": {
            "response": {
                "response": {
                    "responseFormat": "json"
                }
            }
        }
    },
    "id": gen_id(),
    "name": "Fetch Worker History",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [400, 0]
})
connect("Run Config", "Fetch Worker History")

# 4. IF - Noisy?
add_node({
    "parameters": {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "strict",
                "version": 2
            },
            "conditions": [
                {
                    "id": "is-noisy",
                    "leftValue": "={{ $('Webhook Trigger').first().json.body.noise_quality }}",
                    "rightValue": "Noisy",
                    "operator": {
                        "type": "string",
                        "operation": "equals"
                    }
                }
            ],
            "combinator": "and"
        }
    },
    "id": gen_id(),
    "name": "Is Noisy?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [600, 0]
})
connect("Fetch Worker History", "Is Noisy?")

# 4a. Log Accepted
add_node({
    "parameters": {
        "jsCode": "return [{ json: { action: 'accepted', message: 'Audio quality acceptable.' } }];"
    },
    "id": gen_id(),
    "name": "Log Accepted",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [800, 200]
})
connect("Is Noisy?", "Log Accepted", 1, 0)

# 4b. IF - Repeat?
add_node({
    "parameters": {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "strict",
                "version": 2
            },
            "conditions": [
                {
                    "id": "is-repeat",
                    "leftValue": "={{ $json.is_repeat_offender }}",
                    "rightValue": "",
                    "operator": {
                        "type": "boolean",
                        "operation": "true",
                        "singleValue": True
                    }
                }
            ],
            "combinator": "and"
        }
    },
    "id": gen_id(),
    "name": "Is Repeat Offender?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2.2,
    "position": [800, -100]
})
connect("Is Noisy?", "Is Repeat Offender?", 0, 0)

# 5a. LLM Node
add_node({
    "parameters": {
        "promptType": "define",
        "text": "=You are a friendly assistant helping gig workers improve their audio recordings.\n\nWorker name: {{ $('Webhook Trigger').first().json.body.name }}\nRecording duration: {{ $('Webhook Trigger').first().json.body.duration_seconds }} seconds\nThis is their noisy submission number: {{ $('Fetch Worker History').first().json.noisy_count }}\n\nWrite a short, encouraging 2-sentence message:\n- Acknowledge the submission was received\n- Give ONE practical tip to get cleaner audio next time (quieter room, closer mic, etc.)\n\nKeep it warm and brief. No greetings, no sign-off needed.",
    },
    "id": gen_id(),
    "name": "Generate Tip Message",
    "type": "@n8n/n8n-nodes-langchain.chainLlm",
    "typeVersion": 1.9,
    "position": [1050, 0]
})
connect("Is Repeat Offender?", "Generate Tip Message", 1, 0)

add_node({
    "parameters": {
        "projectId": {
            "__rl": True,
            "mode": "id",
            "value": "third-expanse-504110-i1"
        },
        "options": {
            "temperature": 0.7
        }
    },
    "id": gen_id(),
    "name": "Google Vertex Chat Model",
    "type": "@n8n/n8n-nodes-langchain.lmChatGoogleVertex",
    "typeVersion": 1,
    "position": [1050, 200],
    "credentials": {
        "googleApi": {
            "id": "mjFmKO7NFTUdEClj",
            "name": "Google Service Account account"
        }
    }
})
connect("Google Vertex Chat Model", "Generate Tip Message", 0, 0, "ai_languageModel")

# 5a cont. Send Email (Mocked to Code Node)
add_node({
    "parameters": {
        "jsCode": "const workerName = $('Webhook Trigger').first().json.body.name || 'Worker';\nconst tip = $json.text || 'Tip generated';\nconsole.log(`[EMAIL SENT TO ${workerName}]: ${tip}`);\nreturn [{ json: { action: 'tip_sent', message: tip } }];"
    },
    "id": gen_id(),
    "name": "Send Tip Email (Mocked)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1300, 0]
})
connect("Generate Tip Message", "Send Tip Email (Mocked)")

# 5b. HTTP POST Flag
add_node({
    "parameters": {
        "method": "POST",
        "url": "={{ $('Run Config').first().json.apiBaseUrl }}/api/worker-flag",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {
                    "name": "candidate_id",
                    "value": "={{ $('Webhook Trigger').first().json.body.candidate_id }}"
                },
                {
                    "name": "reason",
                    "value": "={{ $('Fetch Worker History').first().json.noisy_count }} noisy submissions"
                }
            ]
        },
        "options": {
            "response": {
                "response": {
                    "responseFormat": "json"
                }
            }
        }
    },
    "id": gen_id(),
    "name": "Flag Worker in DB",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [1050, -250]
})
connect("Is Repeat Offender?", "Flag Worker in DB", 0, 0)

add_node({
    "parameters": {
        "jsCode": "return [{ json: { action: 'flagged_for_review', message: `Worker flagged in DB.` } }];"
    },
    "id": gen_id(),
    "name": "Log Flagged",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1300, -250]
})
connect("Flag Worker in DB", "Log Flagged")

# 6. Audit Log (Mock Google Sheets)
add_node({
    "parameters": {
        "jsCode": "const action = $json.action || 'unknown';\nconst msg = $json.message || '';\nconst worker = $('Webhook Trigger').first().json.body.name || 'Unknown';\nconsole.log(`[GOOGLE SHEETS ROW ADDED]: ${new Date().toISOString()} | ${worker} | ${action} | ${msg}`);\nreturn [{ json: { success: true, logged_action: action } }];"
    },
    "id": gen_id(),
    "name": "Log to Google Sheets (Mocked)",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [1600, -100]
})
connect("Send Tip Email (Mocked)", "Log to Google Sheets (Mocked)")
connect("Log Flagged", "Log to Google Sheets (Mocked)")
connect("Log Accepted", "Log to Google Sheets (Mocked)")

workflow = {
    "name": "ConsultBae — Audio Quality Watchdog (Task 2C)",
    "nodes": nodes,
    "connections": connections,
    "active": False,
    "settings": {
        "executionOrder": "v1"
    },
    "versionId": gen_id(),
    "tags": [
        {
            "name": "task2c-watchdog"
        }
    ]
}

os.makedirs('n8n', exist_ok=True)
with open('n8n/audio_quality_watchdog.json', 'w') as f:
    json.dump(workflow, f, indent=2)

print("Workflow JSON generated at n8n/audio_quality_watchdog.json")
