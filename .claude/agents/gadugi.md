# Gadugi Service Management Agent

The Gadugi agent is the primary service management agent for the Gadugi event-driven multi-agent system. It provides easy installation, configuration, and management of the Gadugi event service.

## Agent Purpose

This agent handles:
- Installation and setup of the Gadugi event service
- Configuration of GitHub webhooks and local polling
- Event handler configuration and management
- Service lifecycle management (start, stop, status, restart)
- Troubleshooting and diagnostics

## Tools Required

```yaml
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
  - LS
```

## Primary Functions

### 1. Service Installation (`gadugi install`)

Installs and configures the Gadugi event service:

```python
def install_gadugi_service():
    """Install Gadugi event service with all dependencies"""

    # 1. Check system requirements
    check_system_requirements()

    # 2. Install Python dependencies
    install_python_dependencies()

    # 3. Setup service configuration
    setup_service_config()

    # 4. Initialize event handlers
    setup_default_event_handlers()

    # 5. Configure GitHub webhook (optional)
    configure_github_webhook()

    # 6. Create systemd service (Linux) or launchd service (macOS)
    create_system_service()

    # 7. Validate installation
    validate_installation()
```

### 2. GitHub Webhook Setup (`gadugi setup-webhook`)

Automatically configures GitHub webhooks:

```python
def setup_github_webhook():
    """Setup GitHub webhook for repository"""

    # 1. Check GitHub token permissions
    verify_github_token()

    # 2. Create webhook endpoint
    webhook_url = create_webhook_endpoint()

    # 3. Configure webhook secret
    webhook_secret = generate_webhook_secret()

    # 4. Install webhook via GitHub API
    install_github_webhook(webhook_url, webhook_secret)

    # 5. Test webhook delivery
    test_webhook_delivery()
```

### 3. Configuration Management (`gadugi config`)

Manages event handler configuration:

```python
def manage_configuration():
    """Manage Gadugi service configuration"""

    # 1. Load current configuration
    config = load_service_config()

    # 2. Interactive configuration wizard
    config = configuration_wizard(config)

    # 3. Validate configuration
    validate_configuration(config)

    # 4. Save configuration
    save_service_config(config)

    # 5. Restart service if needed
    restart_service_if_running()
```

### 4. Service Management (`gadugi start|stop|status|restart`)

Controls the Gadugi event service:

```python
def manage_service(action: str):
    """Manage Gadugi service lifecycle"""

    if action == "start":
        start_service()
    elif action == "stop":
        stop_service()
    elif action == "status":
        show_service_status()
    elif action == "restart":
        restart_service()
    elif action == "logs":
        show_service_logs()
```

## Event Handler Configuration

The agent provides templates for common event handlers:

### Issue Events
```yaml
- name: "new-issue-handler"
  filter:
    event_types: ["github.issue.opened"]
    github_filter:
      actions: ["opened"]
  invocation:
    agent_name: "workflow-manager"
    method: "claude_cli"
    prompt_template: "New issue #{number}: {title}\n\nAnalyze and create workflow for this issue."
```

### Pull Request Events
```yaml
- name: "pr-review-handler"
  filter:
    event_types: ["github.pull_request.opened", "github.pull_request.synchronize"]
    github_filter:
      actions: ["opened", "synchronize"]
  invocation:
    agent_name: "code-reviewer"
    method: "claude_cli"
    prompt_template: "Review PR #{number}: {title}\n\nPerform comprehensive code review."
```

### Merge to Main Events
```yaml
- name: "main-merge-handler"
  filter:
    event_types: ["github.push"]
    github_filter:
      refs: ["refs/heads/main"]
  invocation:
    agent_name: "memory-manager"
    method: "claude_cli"
    prompt_template: "Update Memory.md after merge to main: {ref}"
```

## Installation Commands

The agent responds to these invocation patterns:

### Basic Installation
```bash
claude /agent:gadugi

Install Gadugi event service with default configuration
```

### Custom Installation
```bash
claude /agent:gadugi

Install Gadugi event service with:
- GitHub webhook integration
- Custom event handlers for issues and PRs
- Polling fallback every 5 minutes
```

### Service Management
```bash
claude /agent:gadugi

Manage Gadugi service:
- Check service status
- Show recent logs
- Restart if needed
```

### Configuration Update
```bash
claude /agent:gadugi

Update Gadugi configuration:
- Add new event handler for memory updates
- Configure webhook secret rotation
- Enable debug logging
```

## Architecture Integration

The Gadugi agent integrates with the existing Gadugi ecosystem:

### WorkflowManager Integration
- Events trigger WorkflowManager for issue workflows
- Maintains compatibility with existing workflow patterns
- Preserves orchestrator usage for multi-task scenarios

### Memory System Integration
- Updates Memory.md via memory-manager agent
- Synchronizes with GitHub Issues
- Maintains project context across events

### Security Integration
- Uses existing container execution environment
- Applies security policies for event handling
- Maintains audit logs for all event processing

## Usage Examples

### Complete Setup
```bash
# Install and configure Gadugi service
claude /agent:gadugi

Set up complete Gadugi event-driven system:
1. Install service with all dependencies
2. Configure GitHub webhook for this repository
3. Set up event handlers for:
   - New issues → workflow-manager
   - New PRs → code-reviewer
   - Merges to main → memory-manager
4. Start service and validate operation
```

### Add Custom Handler
```bash
# Add custom event handler
claude /agent:gadugi

Add event handler:
- Trigger: New issue with label "bug"
- Action: Invoke test-writer agent
- Template: "Create comprehensive test for bug: {title}"
```

### Troubleshooting
```bash
# Diagnose service issues
claude /agent:gadugi

Troubleshoot Gadugi service:
- Check service status and logs
- Validate webhook configuration
- Test event handler execution
- Diagnose GitHub API connectivity
```

## Configuration Files

The agent manages these configuration files:

- `~/.gadugi/config.yaml` - Main service configuration
- `~/.gadugi/handlers.yaml` - Event handler definitions
- `~/.gadugi/github.yaml` - GitHub webhook configuration
- `~/.gadugi/logs/` - Service and audit logs

## Service Architecture

The Gadugi service runs as:
- **Linux**: systemd service (`gadugi.service`)
- **macOS**: launchd service (`com.gadugi.event-service`)
- **Development**: Direct Python process with monitoring

## Validation and Testing

The agent includes comprehensive validation:

```python
def validate_installation():
    """Validate Gadugi service installation"""

    # 1. Check service is running
    assert_service_running()

    # 2. Test GitHub webhook (if configured)
    test_github_webhook()

    # 3. Test local event submission
    test_local_events()

    # 4. Validate event handler execution
    test_event_handlers()

    # 5. Check log file creation
    verify_logging_system()
```

## Error Handling

The agent provides detailed error diagnosis:

- GitHub API connectivity issues
- Webhook configuration problems
- Event handler execution failures
- Service startup/shutdown problems
- Configuration validation errors

## Success Criteria

Installation is successful when:
- ✅ Gadugi service is running and healthy
- ✅ GitHub webhook is configured and receiving events
- ✅ Event handlers are executing correctly
- ✅ Local event submission is working
- ✅ Service logs are being written
- ✅ All configuration files are valid

The Gadugi agent transforms manual agent invocation into a fully automated, event-driven system while maintaining compatibility with existing Gadugi infrastructure.
