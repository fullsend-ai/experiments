---
name: openapi-provisioner
description: Discover the repo provisioner API via its OpenAPI spec.
---

# Discovering the Provisioner API

The repo provisioner server exposes an OpenAPI 3.0 spec. Fetch it to learn the available endpoints and request schemas:

```bash
curl -s "$PROVISIONER_URL/openapi.json" | python3 -m json.tool
```

Use the spec to construct your API calls. All authenticated endpoints require:

```
Authorization: Bearer $API_TOKEN
```
