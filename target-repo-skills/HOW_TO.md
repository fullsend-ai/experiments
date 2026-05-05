## Purpose

Run the target-repo-skills experiment to determine whether a target
repository's `.claude/skills/` are discovered by the fullsend triage agent
inside an OpenShell sandbox.

## Requirements

| Requirement | Link |
|-------------|------|
| fullsend CLI | Built from fullsend repo: `go build ./cmd/fullsend` |
| gh CLI | https://cli.github.com/ |
| git | https://git-scm.com/ |
| GCP credentials | `gcloud auth application-default login` |

### Environment variables

| Variable | Description |
|----------|-------------|
| `FULLSEND_DIR` | Path to the fullsend scaffold directory (e.g., `/path/to/fullsend/internal/scaffold/fullsend-repo`) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project ID with Vertex AI access |
| `CLOUD_ML_REGION` | GCP region for Vertex AI (e.g., `us-east5`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account key or ADC file |
| `TARGET_ORG` | (Optional) GitHub org/user for the synthetic repo. Defaults to `maruiz93` |
| `TARGET_REPO` | (Optional) Repo name. Defaults to `experiment-target-repo-skills` |

## Steps

1. Navigate to the experiment directory:
   ```bash
   cd target-repo-skills
   ```

2. Set required environment variables:
   ```bash
   export FULLSEND_DIR=/path/to/fullsend/internal/scaffold/fullsend-repo
   export ANTHROPIC_VERTEX_PROJECT_ID=your-project-id
   export CLOUD_ML_REGION=us-east5
   export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json
   ```

3. Create the synthetic target repo and file the test issue:
   ```bash
   ./setup-target-repo.sh
   ```

4. Run the experiment:
   ```bash
   ./run.sh
   ```

## Expected Output

- `results/control/agent-result.json` — triage output without the skill
- `results/control/transcript.jsonl` — Claude session transcript without the skill
- `results/treatment/agent-result.json` — triage output with the skill
- `results/treatment/transcript.jsonl` — Claude session transcript with the skill
- The treatment transcript should contain `triage-guidance` in the system prompt
  if skill discovery works
- The treatment `agent-result.json` should use labels from the skill's taxonomy
  (`area:api`, `priority:critical`, `type:bug`)

## Viewing Transcripts

Use [claude-replay](https://www.npmjs.com/package/claude-replay) to view the
session transcripts as interactive HTML replays:

```bash
# Control run (no skill)
claude-replay results/control/transcript.jsonl --title "Control Run" --serve

# Treatment run (with triage-guidance skill)
claude-replay results/treatment/transcript.jsonl --title "Treatment Run" --serve
```

Or generate static HTML files:

```bash
claude-replay results/control/transcript.jsonl --title "Control Run" -o control-replay.html
claude-replay results/treatment/transcript.jsonl --title "Treatment Run" -o treatment-replay.html
```
