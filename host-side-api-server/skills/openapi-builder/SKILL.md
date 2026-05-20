---
name: openapi-builder
description: Discover the container builder API via its OpenAPI spec.
---

# Discovering the Builder API

The container builder server exposes an OpenAPI 3.0 spec. Fetch it to learn the available endpoints and request schemas:

```bash
curl -s "$BUILDER_URL/openapi.json" | python3 -m json.tool
```

Use the spec to construct your API calls. All authenticated endpoints require:

```
Authorization: Bearer $API_TOKEN
```
