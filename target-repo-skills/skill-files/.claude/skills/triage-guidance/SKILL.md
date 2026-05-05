---
name: triage-guidance
description: >-
  Project-specific triage rules for this repository. Use when triaging
  GitHub issues to apply the correct labels and priority.
---

# Triage Guidance

When triaging issues in this repository, apply these rules:

## Labels

- Issues mentioning API routes, HTTP handlers, or endpoints: `area:api`
- Issues mentioning database, queries, or connections: `area:data`
- Issues mentioning configuration or environment variables: `area:config`

## Priority

- Any issue describing a crash, panic, or 500 error: `priority:critical`
- Any issue describing incorrect data or wrong responses: `priority:high`
- Any issue requesting a new feature: `priority:medium`

## Classification

- Issues requesting new endpoints or capabilities: `type:feature`
- Issues describing broken existing behavior: `type:bug`
- Issues about performance degradation: `type:performance`
