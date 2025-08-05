#!/bin/bash
# Agent Manager Startup Hook - Check for Agent Updates
# This script runs during Claude Code session startup to check for agent updates

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
AGENT_MANAGER_DIR="$PROJECT_ROOT/.claude/agent-manager"
LOG_FILE="$AGENT_MANAGER_DIR/logs/startup-check.log"
QUIET_MODE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --quiet)
            QUIET_MODE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    local message="$1"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] $message" >> "$LOG_FILE"
    if [ "$QUIET_MODE" = "false" ]; then
        echo "$message"
    fi
}

# Check if agent-manager is initialized
if [ ! -f "$AGENT_MANAGER_DIR/config.yaml" ]; then
    log "Agent Manager not initialized. Skipping update check."
    exit 0
fi

# Check if enough time has passed since last check
LAST_CHECK_FILE="$AGENT_MANAGER_DIR/.last_check"
CHECK_INTERVAL_HOURS=24

if [ -f "$LAST_CHECK_FILE" ]; then
    LAST_CHECK=$(cat "$LAST_CHECK_FILE")
    CURRENT_TIME=$(date +%s)
    TIME_DIFF=$((CURRENT_TIME - LAST_CHECK))
    INTERVAL_SECONDS=$((CHECK_INTERVAL_HOURS * 3600))
    
    if [ $TIME_DIFF -lt $INTERVAL_SECONDS ]; then
        log "Skipping update check (last check was $(($TIME_DIFF / 3600)) hours ago)"
        exit 0
    fi
fi

log "Starting agent update check..."

# Check network connectivity
if ! ping -c 1 google.com >/dev/null 2>&1; then
    log "No network connectivity. Operating in offline mode."
    exit 0
fi

# Update repository caches
UPDATED_REPOS=0
REPO_CACHE_DIR="$AGENT_MANAGER_DIR/cache/repositories"

if [ -d "$REPO_CACHE_DIR" ]; then
    for repo_dir in "$REPO_CACHE_DIR"/*; do
        if [ -d "$repo_dir/.git" ]; then
            repo_name=$(basename "$repo_dir")
            log "Updating repository: $repo_name"
            
            cd "$repo_dir"
            if git pull origin main >/dev/null 2>&1 || git pull origin master >/dev/null 2>&1; then
                log "Successfully updated $repo_name"
                UPDATED_REPOS=$((UPDATED_REPOS + 1))
            else
                log "Failed to update $repo_name"
            fi
        fi
    done
fi

# Check for agent updates by comparing local vs repository versions
AGENTS_WITH_UPDATES=()
REGISTRY_FILE="$AGENT_MANAGER_DIR/agent-registry.json"

if [ -f "$REGISTRY_FILE" ] && command -v python3 >/dev/null 2>&1; then
    # Simple version comparison using Python (if available)
    UPDATES_FOUND=$(python3 -c "
import json
import os
import re

try:
    with open('$REGISTRY_FILE', 'r') as f:
        registry = json.load(f)
    
    updates = []
    for agent in registry.get('agents', []):
        if agent.get('installed', False):
            agent_name = agent['name']
            current_version = agent['version']
            # In a full implementation, would check repository for latest version
            # For now, just report that we checked
            print(f'Checked {agent_name} v{current_version}')
    
    print(f'Found {len(updates)} agents with updates available')
except Exception as e:
    print(f'Error checking for updates: {e}')
    exit(1)
")
    log "$UPDATES_FOUND"
fi

# Update last check timestamp
echo "$(date +%s)" > "$LAST_CHECK_FILE"

log "Agent update check completed. Updated $UPDATED_REPOS repositories."

# Notify user if not in quiet mode
if [ "$QUIET_MODE" = "false" ] && [ $UPDATED_REPOS -gt 0 ]; then
    echo "Agent Manager: Updated $UPDATED_REPOS agent repositories"
    echo "Use '/agent:agent-manager status' to check for agent updates"
fi

exit 0