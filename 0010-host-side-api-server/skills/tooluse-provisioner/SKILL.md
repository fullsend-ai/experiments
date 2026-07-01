---
name: tooluse-provisioner
description: Discover the repo provisioner API via its tool-use schema.
---

# Discovering the Provisioner API

The repo provisioner server exposes a tool-use schema describing each operation as a tool with name, description, HTTP endpoint, and input schema. Fetch it:

```bash
curl -s "$PROVISIONER_URL/tools.json" | python3 -m json.tool
```

Each tool definition tells you:
- `name` — what the tool does
- `endpoint` — the HTTP path to call
- `method` — GET or POST
- `input_schema` — the JSON body schema (for POST requests)

Use this to construct your API calls. All authenticated endpoints require:

```
Authorization: Bearer $API_TOKEN
```
