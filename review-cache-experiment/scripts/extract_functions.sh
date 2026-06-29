#!/bin/bash
#
# Extract function names and code snippets from git files.
#
# Used by save.py to enrich findings before storing.

set -euo pipefail

# Extract function name at a given line
extract_function_name() {
  local file=$1
  local line=$2

  # Get file content from git
  local content
  content=$(git show "HEAD:$file" 2>/dev/null || echo "")

  if [ -z "$content" ]; then
    echo "package"
    return
  fi

  # Search backwards from line for function definition
  # Supports Go, Python, JavaScript, Rust
  local function_name
  function_name=$(echo "$content" | head -n "$line" | tac | \
    grep -m1 -E "^(func |def |function |class |fn |pub fn |impl )" | \
    sed -E 's/^(func |def |function |class |fn |pub fn |impl )([^({\s<]+).*/\2/' || echo "package")

  echo "$function_name"
}

# Extract code snippet (3 lines of context)
extract_code_snippet() {
  local file=$1
  local line=$2

  # Get file content from git
  local content
  content=$(git show "HEAD:$file" 2>/dev/null || echo "")

  if [ -z "$content" ]; then
    echo ""
    return
  fi

  # Get line-1, line, line+1
  local start=$((line - 1))
  local end=$((line + 1))

  # Ensure bounds
  [ $start -lt 1 ] && start=1

  echo "$content" | sed -n "${start},${end}p"
}

# Main: Process JSON findings and add function_name and code_snippet
enrich_findings() {
  local input_json=$1

  # Read JSON, enrich each finding
  jq -c '.findings[]' "$input_json" | while IFS= read -r finding; do
    local file
    local line

    file=$(echo "$finding" | jq -r '.file')
    line=$(echo "$finding" | jq -r '.line')

    # Extract function and snippet
    local function_name
    local code_snippet

    function_name=$(extract_function_name "$file" "$line")
    code_snippet=$(extract_code_snippet "$file" "$line")

    # Add to finding
    echo "$finding" | jq --arg fn "$function_name" --arg cs "$code_snippet" \
      '. + {function_name: $fn, code_snippet: $cs}'
  done | jq -s '{findings: .}'
}

# If run directly, process stdin
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
  if [ $# -eq 0 ]; then
    echo "Usage: $0 <findings.json>" >&2
    echo "" >&2
    echo "Or use as library:" >&2
    echo "  source $0" >&2
    echo "  extract_function_name 'file.go' 42" >&2
    exit 1
  fi

  enrich_findings "$1"
fi
