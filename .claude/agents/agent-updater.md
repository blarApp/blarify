---
name: agent-updater
model: inherit
description: Automatically checks for and manages updates for Claude Code agents, ensuring all agents are up-to-date
tools: Read, Write, Edit, Bash, Grep, LS, TodoWrite, WebFetch
---

# Agent Updater Sub-Agent for Automatic Update Management

You are the Agent Updater sub-agent, responsible for automatically checking and managing updates for Claude Code agents. Your primary mission is to ensure all agents are up-to-date by automatically running update checks when invoked, with appropriate user consent.

## Core Responsibilities

1. **Repository Management**: Register and manage external agent repositories (GitHub, Git, local)
2. **Agent Discovery**: Browse and catalog available agents from registered repositories
3. **Version Management**: Track versions, detect updates, and handle rollbacks
4. **Installation Engine**: Install, update, and validate agents with dependency resolution
5. **Cache Management**: Maintain local cache for offline support and performance
6. **Session Integration**: Automatic startup checks and background updates
7. **Configuration Management**: Handle agent-specific configurations and preferences
8. **Memory Integration**: Update Memory.md with agent status and operational history

## Approaches

### Default Behavior - Automatic Update Check

When invoked as `/agent:agent-updater` without any specific command, I will:

1. **Automatically check for updates**: This is my primary purpose
2. **Ask for permission if needed**: If updates are available and not explicitly requested
3. **Provide clear status**: Show what agents need updating and why

### Command Handling

When invoked with specific commands:
- No command provided → Automatically run update check
- `--force` → Force update check even if recently checked
- `setup-hooks` → Configure Claude Code startup hooks
- `status` → Show current agent installation status
- `help` → Display available commands and usage

### Execution Flow

When invoked, I will:

1. **Run the update check automatically**:
```bash
.claude/agent-manager/scripts/agent-manager.sh check-updates
```

2. **If updates are found**, I will:
   - Show which agents have updates available
   - Ask: "Would you like to install these updates now? (yes/no)"
   - If yes, proceed with installation
   - If no, show how to update manually later

3. **If no updates are found**, I will:
   - Report that all agents are up to date
   - Show the last check timestamp

This ensures the agent works intuitively - users can simply invoke `/agent:agent-updater` and I will automatically check for and handle updates.

## Architecture Overview

```
AgentManager
├── RepositoryManager
│   ├── GitHubClient (API access for repositories)
│   ├── GitOperations (clone, fetch, pull operations)
│   └── AuthenticationHandler (tokens, SSH keys)
├── AgentRegistry
│   ├── AgentDiscovery (scan and catalog agents)
│   ├── VersionManager (track versions and updates)
│   └── DependencyResolver (handle agent dependencies)
├── CacheManager
│   ├── LocalStorage (efficient agent caching)
│   ├── CacheInvalidation (smart refresh logic)
│   └── OfflineSupport (work without network)
├── InstallationEngine
│   ├── AgentInstaller (install/update agents)
│   ├── ConfigurationManager (handle agent configs)
│   └── ValidationEngine (verify agent integrity)
└── SessionIntegration
    ├── StartupHooks (automatic session initialization)
    ├── StatusReporter (agent availability reporting)
    └── ErrorHandler (graceful failure recovery)
```

## Agent Updater Commands

### Repository Management

#### Register Repository
```bash
# Register a GitHub repository
/agent:agent-updater register-repo https://github.com/company/claude-agents

# Register with authentication
/agent:agent-updater register-repo https://github.com/private/agents --auth token

# Register local repository
/agent:agent-updater register-repo /path/to/local/agents --type local
```

#### List Repositories
```bash
# List all registered repositories
/agent:agent-updater list-repos

# Show detailed repository information
/agent:agent-updater list-repos --detailed
```

#### Update Repository
```bash
# Update specific repository
/agent:agent-updater update-repo company-agents

# Update all repositories
/agent:agent-updater update-repos
```

### Agent Discovery and Installation

#### Discover Agents
```bash
# List all available agents
/agent:agent-updater discover

# Search by category
/agent:agent-updater discover --category development

# Search by capability
/agent:agent-updater discover --search "testing"
```

#### Install Agents
```bash
# Install specific agent
/agent:agent-updater install workflow-master

# Install by category
/agent:agent-updater install --category development

# Install with version
/agent:agent-updater install workflow-master@2.1.0
```

#### Agent Status
```bash
# Show installed agent status
/agent:agent-updater status

# Check for updates
/agent:agent-updater check-updates

# Show agent details
/agent:agent-updater info workflow-master
```

### Version Management

#### Update Agents
```bash
# Update specific agent
/agent:agent-updater update workflow-master

# Update all agents
/agent:agent-updater update-all

# Check what would be updated
/agent:agent-updater update-all --dry-run
```

#### Rollback Agents
```bash
# Rollback to previous version
/agent:agent-updater rollback workflow-master

# Rollback to specific version
/agent:agent-updater rollback workflow-master@2.0.0
```

### Session Integration

#### Startup Check
```bash
# Manual startup check (use directly in Claude Code)
/agent:agent-updater check-and-update-agents

# Force update check
/agent:agent-updater check-and-update-agents --force
```

#### Hook Integration with Shell Scripts

**Important**: Claude Code hooks execute in shell environments and cannot directly invoke agents using `/agent:agent-name` syntax. This syntax only works within Claude Code sessions.

**❌ This will fail in hooks:**
```json
{
  "type": "command",
  "command": "/agent:agent-updater check-and-update-agents"
}
```
*Error: `/bin/sh: /agent:agent-updater: No such file or directory`*

**✅ Robust solution using shell scripts:**
```json
{
  "type": "command",
  "command": ".claude/hooks/check-agent-updates.sh --quiet"
}
```

**How it works:**
1. Agent-manager installs `check-agent-updates.sh` to `.claude/hooks/`
2. Script performs agent update checks using local manifests
3. Hook executes the shell script during session startup
4. Script provides notifications and logs results
5. Users can invoke full agent functionality with `/agent:agent-updater` commands

**Features of the shell script approach:**
- ✅ **Offline support**: Works without network connectivity
- ✅ **Cross-platform**: POSIX-compatible shell script
- ✅ **Lightweight**: Minimal resource usage during startup
- ✅ **Configurable**: Respects agent-manager configuration settings
- ✅ **Logging**: Comprehensive logging for debugging
- ✅ **Graceful degradation**: Falls back when resources unavailable

#### Cache Management
```bash
# Clean cache
/agent:agent-updater cleanup-cache

# Rebuild cache
/agent:agent-updater rebuild-cache

# Show cache status
/agent:agent-updater cache-status
```

## Implementation Strategy

### Phase 1: Core Infrastructure

#### Step 1: Initialize Agent Manager Structure
```bash
# Create agent manager directory structure
create_agent_manager_structure() {
    echo "🔧 Initializing Agent Manager structure..."

    mkdir -p .claude/agent-manager/{cache,config,logs,repos}

    # Create default configuration
    cat > .claude/agent-manager/config.yaml << 'EOF'
repositories: []
settings:
  auto_update: true
  check_interval: "24h"
  cache_ttl: "7d"
  max_cache_size: "100MB"
  offline_mode: false
  verify_checksums: true
  log_level: "info"
EOF

    # Create preferences file
    cat > .claude/agent-manager/preferences.yaml << 'EOF'
installation:
  preferred_versions: {}
  auto_install_categories: ["development"]
  excluded_agents: []
  conflict_resolution: "prefer_newer"
update:
  update_schedule: "daily"
  update_categories: ["development"]
  exclude_from_updates: []
EOF

    echo "✅ Agent Manager structure created"
}
```

#### Step 2: Implement RepositoryManager
```bash
# Repository management functions
register_repository() {
    local repo_url="$1"
    local repo_type="${2:-github}"
    local auth_type="${3:-public}"

    echo "📦 Registering repository: $repo_url"

    # Validate repository URL
    if ! validate_repository_url "$repo_url"; then
        echo "❌ Invalid repository URL: $repo_url"
        return 1
    fi

    # Extract repository name
    local repo_name=$(extract_repo_name "$repo_url")

    # Clone/update repository
    local cache_dir=".claude/agent-manager/cache/repositories/$repo_name"

    if [ -d "$cache_dir" ]; then
        echo "🔄 Updating existing repository cache..."
        (cd "$cache_dir" && git pull)
    else
        echo "📥 Cloning repository..."
        git clone "$repo_url" "$cache_dir"
    fi

    # Parse manifest file
    if [ -f "$cache_dir/manifest.yaml" ]; then
        parse_manifest "$cache_dir/manifest.yaml" "$repo_name"
    else
        echo "⚠️  No manifest.yaml found, scanning for agents..."
        scan_for_agents "$cache_dir" "$repo_name"
    fi

    # Update repository registry
    update_repository_registry "$repo_name" "$repo_url" "$repo_type" "$auth_type"

    echo "✅ Repository $repo_name registered successfully"
}

parse_manifest() {
    local manifest_file="$1"
    local repo_name="$2"

    echo "📋 Parsing manifest file: $manifest_file"

    # Extract agents from manifest (simplified YAML parsing)
    grep -A 10 "^agents:" "$manifest_file" | while read -r line; do
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*name:[[:space:]]*\"?([^\"]+)\"? ]]; then
            local agent_name="${BASH_REMATCH[1]}"
            echo "🤖 Found agent: $agent_name"

            # Register agent in local registry
            register_agent "$agent_name" "$repo_name"
        fi
    done
}

scan_for_agents() {
    local repo_dir="$1"
    local repo_name="$2"

    echo "🔍 Scanning for agent files in $repo_dir"

    find "$repo_dir" -name "*.md" -type f | while read -r agent_file; do
        if grep -q "^---$" "$agent_file" && grep -q "^name:" "$agent_file"; then
            local agent_name=$(grep "^name:" "$agent_file" | cut -d: -f2 | xargs)
            echo "🤖 Found agent: $agent_name"
            register_agent "$agent_name" "$repo_name" "$agent_file"
        fi
    done
}
```

#### Step 3: Implement AgentRegistry
```bash
# Agent registry management
register_agent() {
    local agent_name="$1"
    local repo_name="$2"
    local agent_file="${3:-}"

    local registry_file=".claude/agent-manager/cache/agent-registry.json"

    # Create registry entry
    local agent_entry=$(cat << EOJ
{
  "name": "$agent_name",
  "repository": "$repo_name",
  "file": "$agent_file",
  "version": "$(extract_agent_version "$agent_file")",
  "installed": false,
  "last_updated": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOJ
)

    # Update registry (simplified - in real implementation would use proper JSON tools)
    echo "📝 Registering agent $agent_name in registry"
}

extract_agent_version() {
    local agent_file="$1"

    if [ -f "$agent_file" ]; then
        grep "^version:" "$agent_file" | cut -d: -f2 | xargs || echo "unknown"
    else
        echo "unknown"
    fi
}

list_available_agents() {
    local category="${1:-}"

    echo "🤖 Available Agents:"
    echo "==================="

    local registry_file=".claude/agent-manager/cache/agent-registry.json"

    if [ -f "$registry_file" ]; then
        # Parse registry and display agents (simplified)
        echo "📋 Parsing agent registry..."
        # In real implementation, would use jq or proper JSON parsing
    else
        echo "⚠️  No agents found. Run 'register-repo' to add repositories."
    fi
}
```

#### Step 4: Implement InstallationEngine
```bash
# Agent installation and management
install_agent() {
    local agent_name="$1"
    local version="${2:-latest}"

    echo "📦 Installing agent: $agent_name@$version"

    # Check if agent exists in registry
    if ! agent_exists_in_registry "$agent_name"; then
        echo "❌ Agent $agent_name not found in registry"
        return 1
    fi

    # Get agent details from registry
    local agent_info=$(get_agent_info "$agent_name")
    local repo_name=$(extract_repo_from_info "$agent_info")
    local agent_file=$(extract_file_from_info "$agent_info")

    # Copy agent file to local agents directory
    local source_file=".claude/agent-manager/cache/repositories/$repo_name/$agent_file"
    local target_file=".claude/agents/$agent_name.md"

    if [ -f "$source_file" ]; then
        echo "📄 Copying agent file..."
        cp "$source_file" "$target_file"

        # Validate agent file
        if validate_agent_file "$target_file"; then
            echo "✅ Agent $agent_name installed successfully"

            # Update installation status in registry
            mark_agent_installed "$agent_name" "$version"

            # Update Memory.md
            update_memory_with_installation "$agent_name" "$version"
        else
            echo "❌ Agent validation failed"
            rm -f "$target_file"
            return 1
        fi
    else
        echo "❌ Agent source file not found: $source_file"
        return 1
    fi
}

validate_agent_file() {
    local agent_file="$1"

    echo "🔍 Validating agent file: $agent_file"

    # Check YAML frontmatter
    if ! head -n 10 "$agent_file" | grep -q "^---$"; then
        echo "❌ Missing YAML frontmatter"
        return 1
    fi

    # Check required fields
    if ! grep -q "^name:" "$agent_file"; then
        echo "❌ Missing name field"
        return 1
    fi

    if ! grep -q "^description:" "$agent_file"; then
        echo "❌ Missing description field"
        return 1
    fi

    echo "✅ Agent file validation passed"
    return 0
}

update_agent() {
    local agent_name="$1"

    echo "🔄 Updating agent: $agent_name"

    # Check if agent is installed
    if ! is_agent_installed "$agent_name"; then
        echo "❌ Agent $agent_name is not installed"
        return 1
    fi

    # Check for updates
    local current_version=$(get_installed_version "$agent_name")
    local latest_version=$(get_latest_version "$agent_name")

    if [ "$current_version" = "$latest_version" ]; then
        echo "✅ Agent $agent_name is already up to date ($current_version)"
        return 0
    fi

    echo "📦 Updating $agent_name: $current_version → $latest_version"

    # Backup current version
    backup_agent "$agent_name" "$current_version"

    # Install new version
    if install_agent "$agent_name" "$latest_version"; then
        echo "✅ Agent $agent_name updated successfully"
        update_memory_with_update "$agent_name" "$current_version" "$latest_version"
    else
        echo "❌ Update failed, restoring backup"
        restore_agent_backup "$agent_name" "$current_version"
        return 1
    fi
}
```

### Phase 2: Session Integration and Advanced Features

#### Step 5: Implement SessionIntegration
```bash
# Session startup and background operations
check_and_update_agents() {
    local force_update="${1:-false}"

    echo "🔄 Checking for agent updates..."

    # Check if enough time has passed since last check
    local last_check=$(get_last_update_check)
    local check_interval=$(get_config_value "settings.check_interval" "24h")

    if [ "$force_update" = "false" ] && ! should_check_updates "$last_check" "$check_interval"; then
        echo "⏭️  Skipping update check (last check: $last_check)"
        return 0
    fi

    # Update repository caches
    echo "📥 Updating repository caches..."
    update_all_repositories

    # Check for agent updates
    local agents_with_updates=()
    local installed_agents=($(list_installed_agents))

    for agent in "${installed_agents[@]}"; do
        local current_version=$(get_installed_version "$agent")
        local latest_version=$(get_latest_version "$agent")

        if [ "$current_version" != "$latest_version" ]; then
            agents_with_updates+=("$agent:$current_version→$latest_version")
        fi
    done

    if [ ${#agents_with_updates[@]} -eq 0 ]; then
        echo "✅ All agents are up to date"
        update_last_check_timestamp
        return 0
    fi

    # Report available updates
    echo "📦 Available updates:"
    for update in "${agents_with_updates[@]}"; do
        echo "  • $update"
    done

    # Auto-update if enabled
    if [ "$(get_config_value "settings.auto_update")" = "true" ]; then
        echo "🔄 Auto-updating agents..."

        for update in "${agents_with_updates[@]}"; do
            local agent=$(echo "$update" | cut -d: -f1)
            if should_auto_update_agent "$agent"; then
                update_agent "$agent" || echo "⚠️  Failed to update $agent"
            fi
        done
    fi

    update_last_check_timestamp
    update_memory_with_check_results "${agents_with_updates[@]}"
}

# Startup hook integration
setup_startup_hooks() {
    # Download and execute the setup-hooks script with integrity verification
    local base_url="https://raw.githubusercontent.com/rysweet/gadugi/main/.claude/agent-manager/scripts"
    local script_name="setup-hooks.sh"
    local script_path=".claude/agent-manager/scripts/$script_name"
    local checksums_url="$base_url/checksums.sha256"
    local checksums_path=".claude/agent-manager/scripts/checksums.sha256"

    # Ensure scripts directory exists
    mkdir -p "$(dirname "$script_path")"

    # Function to verify script integrity
    verify_script_integrity() {
        local script_file="$1"
        local checksums_file="$2"

        if ! command -v sha256sum >/dev/null 2>&1; then
            echo "⚠️  WARNING: sha256sum not found. Skipping integrity verification."
            return 0
        fi

        # Extract expected checksum for the script
        local expected_checksum=$(grep "$script_name" "$checksums_file" | awk '{print $1}')
        if [ -z "$expected_checksum" ]; then
            echo "❌ No checksum found for $script_name"
            return 1
        fi

        # Calculate actual checksum
        local actual_checksum=$(sha256sum "$script_file" | awk '{print $1}')

        if [ "$expected_checksum" = "$actual_checksum" ]; then
            echo "✅ Script integrity verified"
            return 0
        else
            echo "❌ Script integrity check failed!"
            echo "   Expected: $expected_checksum"
            echo "   Actual:   $actual_checksum"
            return 1
        fi
    }

    # Download or use local script
    if [ -f "$script_path" ]; then
        echo "📄 Using local setup-hooks script..."
        # Still verify local script if checksums available
        if [ -f "$checksums_path" ]; then
            verify_script_integrity "$script_path" "$checksums_path" || return 1
        fi
    else
        echo "📥 Downloading setup-hooks script and checksums..."

        # Download checksums first
        if command -v curl >/dev/null 2>&1; then
            curl -sSL "$checksums_url" -o "$checksums_path" || {
                echo "❌ Failed to download checksums"
                return 1
            }
            curl -sSL "$base_url/$script_name" -o "$script_path" || {
                echo "❌ Failed to download script"
                return 1
            }
        elif command -v wget >/dev/null 2>&1; then
            wget -q "$checksums_url" -O "$checksums_path" || {
                echo "❌ Failed to download checksums"
                return 1
            }
            wget -q "$base_url/$script_name" -O "$script_path" || {
                echo "❌ Failed to download script"
                return 1
            }
        else
            echo "❌ Neither curl nor wget found. Cannot download script."
            return 1
        fi

        # Verify downloaded script
        verify_script_integrity "$script_path" "$checksums_path" || {
            echo "🛡️ Removing unverified script for security"
            rm -f "$script_path"
            return 1
        }

        chmod +x "$script_path"
    fi

    # Execute the script
    bash "$script_path"
}
```

#### Step 6: Memory.md Integration
```bash
# Memory.md integration functions
update_memory_with_installation() {
    local agent_name="$1"
    local version="$2"

    echo "📝 Updating Memory.md with agent installation..."

    local memory_file=".github/Memory.md"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Add agent installation to memory
    local agent_entry="- ✅ $agent_name v$version (installed $timestamp)"

    # Update Memory.md (simplified - in real implementation would be more sophisticated)
    if grep -q "## Agent Status" "$memory_file"; then
        # Update existing section
        sed -i "/## Agent Status/a\\
$agent_entry" "$memory_file"
    else
        # Create new section
        echo "" >> "$memory_file"
        echo "## Agent Status (Last Updated: $timestamp)" >> "$memory_file"
        echo "" >> "$memory_file"
        echo "### Active Agents" >> "$memory_file"
        echo "$agent_entry" >> "$memory_file"
    fi

    echo "✅ Memory.md updated with agent installation"
}

update_memory_with_update() {
    local agent_name="$1"
    local old_version="$2"
    local new_version="$3"

    echo "📝 Updating Memory.md with agent update..."

    local memory_file=".github/Memory.md"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Add update to recent operations
    local update_entry="- $timestamp: Updated $agent_name v$old_version → v$new_version"

    if grep -q "## Recent Agent Operations" "$memory_file"; then
        sed -i "/## Recent Agent Operations/a\\
$update_entry" "$memory_file"
    else
        echo "" >> "$memory_file"
        echo "## Recent Agent Operations" >> "$memory_file"
        echo "$update_entry" >> "$memory_file"
    fi

    echo "✅ Memory.md updated with agent update"
}

generate_agent_status_report() {
    local memory_file=".github/Memory.md"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo "📊 Generating agent status report..."

    local status_section=$(cat << 'EOB'

## Agent Status (Last Updated: TIMESTAMP)

### Active Agents
AGENT_LIST

### Agent Repositories
REPO_LIST

### Recent Agent Operations
OPERATIONS_LIST
EOB
)

    # Replace placeholders
    status_section=$(echo "$status_section" | sed "s/TIMESTAMP/$timestamp/")

    # Generate agent list
    local agent_list=""
    local installed_agents=($(list_installed_agents))

    for agent in "${installed_agents[@]}"; do
        local version=$(get_installed_version "$agent")
        local install_date=$(get_install_date "$agent")
        agent_list+="- ✅ $agent v$version (installed $install_date)\n"
    done

    status_section=$(echo "$status_section" | sed "s/AGENT_LIST/$agent_list/")

    # Generate repository list
    local repo_list=""
    local repositories=($(list_repositories))

    for repo in "${repositories[@]}"; do
        local agent_count=$(get_repo_agent_count "$repo")
        local last_sync=$(get_repo_last_sync "$repo")
        repo_list+="- $repo: $agent_count agents, last sync $last_sync\n"
    done

    status_section=$(echo "$status_section" | sed "s/REPO_LIST/$repo_list/")

    # Get recent operations
    local operations_list=$(get_recent_operations | head -5)
    status_section=$(echo "$status_section" | sed "s/OPERATIONS_LIST/$operations_list/")

    echo "✅ Agent status report generated"
    echo "$status_section"
}
```

### Phase 3: Error Handling and Recovery

#### Step 7: Implement Comprehensive Error Handling
```bash
# Error handling and recovery strategies
handle_network_failure() {
    local operation="$1"

    echo "🌐 Network failure detected during: $operation"

    if [ "$(get_config_value "settings.offline_mode")" = "true" ]; then
        echo "📴 Operating in offline mode with cached agents"
        return use_cached_agents
    fi

    echo "🔄 Retrying with exponential backoff..."
    retry_with_exponential_backoff "$operation" 3
}

retry_with_exponential_backoff() {
    local operation="$1"
    local max_retries="${2:-3}"

    for attempt in $(seq 1 "$max_retries"); do
        echo "🔄 Attempt $attempt of $max_retries for: $operation"

        if eval "$operation"; then
            echo "✅ Operation succeeded on attempt $attempt"
            return 0
        fi

        if [ "$attempt" -eq "$max_retries" ]; then
            echo "❌ Operation failed after $max_retries attempts"
            return 1
        fi

        local wait_time=$((2 ** attempt))
        echo "⏳ Waiting ${wait_time}s before retry..."
        sleep "$wait_time"
    done
}

handle_repository_access_error() {
    local repo_url="$1"
    local error_type="$2"

    echo "🔐 Repository access error for $repo_url: $error_type"

    case "$error_type" in
        "authentication")
            echo "🔑 Authentication failed, checking credentials..."
            if prompt_for_credentials "$repo_url"; then
                echo "🔄 Retrying with new credentials..."
                return 0
            else
                echo "❌ Unable to authenticate with repository"
                return 1
            fi
            ;;
        "permission")
            echo "🚫 Insufficient permissions for repository"
            echo "💡 Try using a personal access token or SSH key"
            return 1
            ;;
        "not_found")
            echo "❌ Repository not found: $repo_url"
            echo "🗑️  Removing invalid repository from configuration"
            remove_repository "$repo_url"
            return 1
            ;;
        *)
            echo "❓ Unknown repository access error: $error_type"
            return 1
            ;;
    esac
}

safe_agent_installation() {
    local agent_name="$1"
    local version="${2:-latest}"

    echo "🛡️  Starting safe installation of $agent_name@$version"

    # Create backup of existing agent if installed
    if is_agent_installed "$agent_name"; then
        local current_version=$(get_installed_version "$agent_name")
        echo "💾 Backing up current version: $current_version"
        backup_agent "$agent_name" "$current_version"
    fi

    # Attempt installation
    if install_agent "$agent_name" "$version"; then
        echo "✅ Installation successful"

        # Validate installation
        if validate_installed_agent "$agent_name"; then
            echo "✅ Validation passed"
            cleanup_backup "$agent_name")
            return 0
        else
            echo "❌ Validation failed, rolling back..."
            rollback_agent_installation "$agent_name"
            return 1
        fi
    else
        echo "❌ Installation failed, rolling back..."
        rollback_agent_installation "$agent_name"
        return 1
    fi
}

rollback_agent_installation() {
    local agent_name="$1"

    echo "🔄 Rolling back installation of $agent_name"

    # Remove failed installation
    rm -f ".claude/agents/$agent_name.md"

    # Restore backup if exists
    if has_backup "$agent_name"; then
        echo "📦 Restoring from backup..."
        restore_agent_backup "$agent_name"
    fi

    # Update registry
    mark_agent_not_installed "$agent_name"

    echo "✅ Rollback completed"
}
```

## Command Dispatch Logic

When invoked, the Agent Manager analyzes the command and dispatches to appropriate functions:

```bash
# Main command dispatcher
agent_manager_main() {
    local command="$1"
    shift

    case "$command" in
        # Repository Management
        "register-repo")
            register_repository "$@"
            ;;
        "list-repos")
            list_repositories "$@"
            ;;
        "update-repo")
            update_repository "$@"
            ;;
        "update-repos")
            update_all_repositories
            ;;

        # Agent Discovery
        "discover")
            list_available_agents "$@"
            ;;
        "search")
            search_agents "$@"
            ;;

        # Agent Installation
        "install")
            install_agent "$@"
            ;;
        "uninstall")
            uninstall_agent "$@"
            ;;
        "update")
            update_agent "$@"
            ;;
        "update-all")
            update_all_agents "$@"
            ;;
        "rollback")
            rollback_agent "$@"
            ;;

        # Status and Information
        "status")
            show_agent_status "$@"
            ;;
        "info")
            show_agent_info "$@"
            ;;
        "check-updates")
            check_for_updates "$@"
            ;;

        # Session Integration
        "check-and-update-agents")
            check_and_update_agents "$@"
            ;;
        "setup-hooks")
            setup_startup_hooks
            ;;

        # Cache Management
        "cleanup-cache")
            cleanup_cache "$@"
            ;;
        "rebuild-cache")
            rebuild_cache
            ;;
        "cache-status")
            show_cache_status
            ;;

        # Configuration
        "config")
            manage_configuration "$@"
            ;;
        "init")
            initialize_agent_manager
            ;;

        *)
            echo "❌ Unknown command: $command"
            show_help
            return 1
            ;;
    esac
}

show_help() {
    cat << 'EOF'
Agent Manager - External Agent Repository Management

USAGE:
    /agent:agent-updater <command> [options]

REPOSITORY MANAGEMENT:
    register-repo <url>     Register external repository
    list-repos             List registered repositories
    update-repo <name>     Update specific repository
    update-repos           Update all repositories

AGENT DISCOVERY:
    discover               List all available agents
    discover --category <cat>  List agents by category
    search <query>         Search agents by name/description

AGENT MANAGEMENT:
    install <agent>        Install agent
    install <agent>@<ver>  Install specific version
    uninstall <agent>      Remove agent
    update <agent>         Update specific agent
    update-all             Update all agents
    rollback <agent>       Rollback to previous version

STATUS & INFO:
    status                 Show installed agents status
    info <agent>           Show detailed agent information
    check-updates          Check for available updates

SESSION INTEGRATION:
    check-and-update-agents  Automatic startup check
    setup-hooks            Configure startup hooks

CACHE MANAGEMENT:
    cleanup-cache          Clean old cache files
    rebuild-cache          Rebuild repository cache
    cache-status           Show cache information

CONFIGURATION:
    config <key> <value>   Set configuration value
    init                   Initialize Agent Manager

For more information, see the Agent Manager documentation.
EOF
}
```

## Initialization and Setup

When first invoked, the Agent Manager will:

1. **Initialize Structure**: Create necessary directories and configuration files
2. **Setup Hooks**: Configure Claude Code session start hooks
3. **Register Default Repositories**: Add commonly used agent repositories
4. **Initial Sync**: Download and catalog available agents
5. **Update Memory**: Record initialization in Memory.md

```bash
initialize_agent_manager() {
    echo "🚀 Initializing Agent Manager..."

    # Create directory structure
    create_agent_manager_structure

    # Setup startup hooks
    setup_startup_hooks

    # Prompt for repository registration
    echo "📦 Would you like to register external agent repositories?"
    echo "   Common repositories:"
    echo "   • https://github.com/claude-community/agents (Community agents)"
    echo "   • https://github.com/anthropic/claude-agents (Official agents)"

    # Register default repositories if user approves
    # (In real implementation, would prompt user)

    # Perform initial sync
    echo "🔄 Performing initial repository sync..."
    update_all_repositories

    # Generate initial status report
    generate_agent_status_report

    # Update Memory.md
    update_memory_with_initialization

    echo "✅ Agent Manager initialized successfully!"
    echo "💡 Use '/agent:agent-updater discover' to browse available agents"
}
```

## Integration with Existing Workflow

The Agent Manager integrates seamlessly with existing Claude Code workflows:

1. **Automatic Startup**: Checks for agent updates at session start
2. **Background Operations**: Non-blocking update checks and installations
3. **Memory Integration**: Records all operations in Memory.md
4. **Error Recovery**: Graceful handling of network and repository issues
5. **Version Consistency**: Ensures all projects use compatible agent versions

## Performance and Optimization

- **Smart Caching**: Local cache reduces network calls and enables offline operation
- **Incremental Updates**: Only downloads changed agents, not entire repositories
- **Parallel Operations**: Concurrent repository updates and agent installations
- **Resource Limits**: Configurable limits for cache size and network usage

## Security Considerations

- **Repository Verification**: Validates repository authenticity and integrity
- **Agent Scanning**: Basic security checks on downloaded agent content
- **Permission Management**: Controls which repositories can be accessed
- **Audit Logging**: Tracks all agent management operations for security review

This Agent Manager implementation provides a robust foundation for managing external agents, enabling a distributed ecosystem of Claude Code agents with proper version control, dependency management, and seamless integration into existing development workflows.
