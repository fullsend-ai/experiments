#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
mkdir -p "$RESULTS_DIR"

BOLD='\033[1m'
CYAN='\033[36m'
GREEN='\033[32m'
DIM='\033[2m'
RESET='\033[0m'

step()  { printf "\n${BOLD}${CYAN}▸ %s${RESET}\n\n" "$1"; }
pass()  { printf "  ${GREEN}✓ %s${RESET}\n" "$1"; }
info()  { printf "  ${DIM}%s${RESET}\n" "$1"; }

PROMPT_ECHO_LS="Run the command 'echo hello' and then run 'ls /tmp'. For each command, report whether it succeeded or failed and include the output."
PROMPT_ECHO="Run the command 'echo hello'. Report whether it succeeded or failed and include the output."
PROMPT_WRITE="Write the text 'hello' to a file called test-adr0022.txt using the Write tool. Do NOT use Bash for this — use the Write tool specifically. Report whether it succeeded or failed."

setup_workdir() {
    local tmpdir
    tmpdir=$(mktemp -d)
    git init "$tmpdir" --quiet
    git -C "$tmpdir" commit --allow-empty -m "init" --quiet
    echo "$tmpdir"
}

install_agent() {
    local workdir="$1"
    local agent_file="$2"
    mkdir -p "$workdir/.claude/agents"
    cp "$SCRIPT_DIR/agents/$agent_file" "$workdir/.claude/agents/"
}

install_settings() {
    local workdir="$1"
    local settings_file="$2"
    mkdir -p "$workdir/.claude"
    cp "$SCRIPT_DIR/settings/$settings_file" "$workdir/.claude/settings.json"
}

run_test() {
    local test_name="$1"
    local agent_file="$2"
    local prompt="$3"
    local skip_permissions="$4"
    local settings_file="${5:-}"

    local agent_name
    agent_name="$(basename "$agent_file" .md)"

    info "$test_name"

    local workdir
    workdir=$(setup_workdir)

    install_agent "$workdir" "$agent_file"

    if [[ -n "$settings_file" ]]; then
        install_settings "$workdir" "$settings_file"
    fi

    local flags=()
    flags+=(--agent "$agent_name")
    flags+=(--output-format json)
    flags+=(--max-turns 5)
    if [[ "$skip_permissions" == "yes" ]]; then
        flags+=(--dangerously-skip-permissions)
    fi

    local output_file="$RESULTS_DIR/$test_name.json"

    (cd "$workdir" && claude -p "$prompt" "${flags[@]}" < /dev/null > "$output_file" 2>&1) || true

    rm -rf "$workdir"
    pass "$test_name"
}

run_subagent_test() {
    local test_name="$1"
    local coordinator_file="$2"
    local subagent_file="$3"
    local prompt="$4"

    local coordinator_name
    coordinator_name="$(basename "$coordinator_file" .md)"

    info "$test_name"

    local workdir
    workdir=$(setup_workdir)

    install_agent "$workdir" "$coordinator_file"
    install_agent "$workdir" "$subagent_file"

    local output_file="$RESULTS_DIR/$test_name.json"

    (cd "$workdir" && claude -p "$prompt" \
        --agent "$coordinator_name" \
        --output-format json \
        --max-turns 10 \
        --dangerously-skip-permissions \
        < /dev/null > "$output_file" 2>&1) || true

    rm -rf "$workdir"
    pass "$test_name"
}

run_frontmatter() {
    step "Frontmatter scoping (tools, disallowedTools)"

    info "-- --agent sessions --"

    run_test "frontmatter-tools-bash" \
        "tools-bash.md" "$PROMPT_WRITE" "no"

    run_test "frontmatter-tools-bash-skip" \
        "tools-bash-skip.md" "$PROMPT_WRITE" "yes"

    run_test "frontmatter-tools-write-try-bash" \
        "tools-write.md" "$PROMPT_ECHO" "no"

    run_test "frontmatter-tools-write-try-write" \
        "tools-write.md" "$PROMPT_WRITE" "no"

    run_test "frontmatter-tools-bash-allow-write" \
        "tools-bash.md" "$PROMPT_WRITE" "no" "allow-write.json"

    run_test "frontmatter-disallowed-bash" \
        "disallowed-bash.md" "$PROMPT_ECHO" "yes"

    info "-- subagents --"

    run_subagent_test "subagent-disallowed-bash" \
        "coordinator-disallowed.md" "subagent-disallowed-bash.md" \
        "Delegate the following task to the subagent-disallowed-bash subagent: run the command 'echo hello' and report whether it succeeded or failed."

    run_subagent_test "subagent-tools-bash" \
        "coordinator-tools.md" "subagent-tools-bash.md" \
        "Delegate the following task to the subagent-tools-bash subagent: write the text 'hello' to a file called test-adr0022.txt using the Write tool. Do NOT use Bash for this — use the Write tool specifically. Report whether it succeeded or failed."
}

run_permissions_deny() {
    step "permissions.deny with --dangerously-skip-permissions"

    run_test "permissions-deny" \
        "deny-test.md" "$PROMPT_ECHO_LS" "yes" "deny-bash-ls.json"
}

run_permissions_allow() {
    step "permissions.allow with dontAsk"

    run_test "permissions-allow" \
        "dontask.md" "$PROMPT_ECHO_LS" "no" "allow-bash-echo.json"
}

run_bypass_permissions() {
    step "bypassPermissions behavior"

    run_test "bypass-no-tools-write" \
        "bypass-no-tools.md" "$PROMPT_WRITE" "no"

    run_test "bypass-allow-write" \
        "bypass-no-tools.md" "$PROMPT_WRITE" "no" "allow-write.json"
}

generate_summary() {
    step "Generating results/summary.yaml"

    python3 - "$RESULTS_DIR" <<'PYEOF'
import json, sys, os, glob, re

results_dir = sys.argv[1]
entries = []

def clean(text):
    """Strip markdown formatting for readability."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'```\w*\n?', '', text)
    text = text.strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    return " ".join(lines)

for path in sorted(glob.glob(os.path.join(results_dir, "*.json"))):
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        entries.append(f"{name}:\n  error: failed to parse JSON\n")
        continue

    result = clean(data.get("result", ""))
    denials = data.get("permission_denials", [])

    if len(result) > 200:
        result = result[:200] + "..."

    entry = f"{name}:\n  result: |\n"
    for line in result.splitlines():
        entry += f"    {line}\n"

    if denials:
        tools = [d.get("tool_name", "unknown") for d in denials]
        entry += f"  permission_denials: [{', '.join(tools)}]\n"
    else:
        entry += "  permission_denials: []\n"

    entries.append(entry)

with open(os.path.join(results_dir, "summary.yaml"), "w") as f:
    f.write("# Auto-generated from JSON results. See *.json for full output.\n\n")
    f.write("\n".join(entries))

print(f"  Wrote {len(entries)} entries to results/summary.yaml")
PYEOF
}

usage() {
    echo "Usage: $0 [frontmatter|deny|allow|bypass|all]"
    echo ""
    echo "  frontmatter  — tools/disallowedTools in --agent vs subagent"
    echo "  deny         — permissions.deny enforcement"
    echo "  allow        — permissions.allow with dontAsk"
    echo "  bypass       — bypassPermissions partial bypass"
    echo "  all          — Run all tests (default)"
    echo ""
    echo "Prerequisites:"
    echo "  - claude CLI installed and authenticated"
    echo "  - git available on PATH"
}

main() {
    local target="${1:-all}"

    if ! command -v claude &>/dev/null; then
        echo "Error: claude CLI not found on PATH" >&2
        exit 1
    fi

    printf "\n${BOLD}ADR 0022 Tool Scoping Experiment${RESET}\n"
    printf "${DIM}Claude CLI: %s | Date: %s${RESET}\n" \
        "$(claude --version 2>/dev/null || echo 'unknown')" \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

    case "$target" in
        frontmatter) run_frontmatter ;;
        deny) run_permissions_deny ;;
        allow) run_permissions_allow ;;
        bypass) run_bypass_permissions ;;
        all)
            run_frontmatter
            run_permissions_deny
            run_permissions_allow
            run_bypass_permissions
            ;;
        -h|--help|help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown target: $target" >&2
            usage
            exit 1
            ;;
    esac

    generate_summary

    printf "\n${BOLD}${GREEN}✓ Done.${RESET} Results in: $RESULTS_DIR/\n\n"
}

main "$@"