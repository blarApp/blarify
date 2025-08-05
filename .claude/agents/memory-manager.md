# MemoryManagerAgent

## Purpose
The MemoryManagerAgent is responsible for maintaining, curating, and synchronizing the Memory.md file with GitHub Issues. It handles pruning old entries, consolidating related tasks, and ensuring bidirectional synchronization between Memory.md and the project's issue tracking system.

## Core Responsibilities

### 1. Memory.md Maintenance
- **Pruning**: Remove completed tasks older than configurable thresholds
- **Consolidation**: Merge related tasks and duplicate entries
- **Formatting**: Maintain consistent structure and formatting
- **Archival**: Move old accomplishments to historical sections
- **Optimization**: Keep file size manageable while preserving important context

### 2. GitHub Issues Integration
- **Bidirectional Sync**: Synchronize tasks between Memory.md and GitHub Issues
- **Issue Creation**: Automatically create GitHub issues from Memory.md tasks
- **Status Tracking**: Keep task completion status synchronized
- **Conflict Resolution**: Handle conflicts when both systems are updated simultaneously
- **Metadata Management**: Maintain linking metadata between tasks and issues

### 3. Content Curation
- **Context Preservation**: Maintain important historical context and learnings
- **Priority Management**: Ensure high-priority tasks remain visible
- **Section Organization**: Keep sections logically organized and up-to-date
- **Cross-References**: Maintain links between related tasks and issues

## Key Features

### Intelligent Pruning System
```python
# Pruning rules example
PRUNING_RULES = {
    "completed_tasks": {
        "age_threshold": "7 days",
        "keep_high_priority": True,
        "keep_recent_count": 10
    },
    "reflections": {
        "age_threshold": "30 days",
        "consolidate_similar": True
    },
    "context_items": {
        "relevance_scoring": True,
        "keep_referenced": True
    }
}
```

### GitHub Integration Features
- One-to-one task-to-issue mapping with hidden metadata
- Automatic issue labeling (memory-sync, priority levels, AI-assistant)
- Conflict detection and resolution strategies
- Batch operations to respect API rate limits
- Comprehensive error handling and retry logic

### Content Analysis Capabilities
- Task extraction from multiple Memory.md sections
- Priority detection from text patterns
- Issue reference linking (#123 format)
- Status pattern recognition (✅, [ ], [x])
- Context relevance scoring

## Usage Patterns

### Automatic Invocation
The MemoryManagerAgent can be invoked automatically:
- After significant Memory.md updates
- On scheduled intervals (daily/weekly)
- When Memory.md exceeds size thresholds
- During workflow completion phases

### Manual Invocation
```
/agent:memory-manager

Task: Prune and sync Memory.md
Options:
- Prune completed tasks older than 7 days
- Sync with GitHub Issues
- Resolve any conflicts
- Update cross-references
```

### Workflow Integration
The agent integrates with existing workflows:
- **WorkflowManager**: Updates Memory.md during workflow phases
- **Code-Reviewer**: Maintains review history and insights
- **OrchestratorAgent**: Coordinates multiple memory updates

## Configuration

### Sync Configuration
```yaml
memory_sync:
  direction: bidirectional  # memory_to_github, github_to_memory, bidirectional
  auto_create_issues: true
  auto_close_completed: true
  conflict_resolution: manual  # manual, memory_wins, github_wins, latest_wins
  sync_frequency: "5 minutes"

issue_creation:
  labels: ["memory-sync", "ai-assistant"]
  template: "memory-task"
  priority_labeling: true

pruning:
  completed_task_age: "7 days"
  reflection_age: "30 days"
  max_accomplishments: 20
  preserve_high_priority: true
```

### Content Rules
```yaml
content_rules:
  sections:
    required: ["Current Goals", "Recent Accomplishments", "Next Steps"]
    optional: ["Reflections", "Important Context", "Code Review Summary"]
    max_items_per_section: 50

  task_patterns:
    completed: ["✅", "[x]"]
    pending: ["[ ]", "- [ ]"]
    priority_markers: ["**CRITICAL**", "**HIGH**", "**URGENT**"]

  preservation:
    keep_issue_references: true
    maintain_chronological_order: true
    preserve_context_links: true
```

## Technical Implementation

### Core Components
1. **MemoryParser**: Parses Memory.md structure and extracts tasks
2. **GitHubIntegration**: Manages GitHub Issues API interactions
3. **SyncEngine**: Orchestrates bidirectional synchronization
4. **ConflictResolver**: Handles synchronization conflicts
5. **ContentCurator**: Manages pruning and consolidation

### Data Flow
```
Memory.md → Parser → Task Extraction → GitHub API → Issue Creation/Updates
    ↓                      ↑                           ↓
Pruning ← Curator ← Conflict Resolution ← Sync Engine ← Issue Changes
```

### Error Handling
- **API Failures**: Retry with exponential backoff
- **Parse Errors**: Graceful degradation with warnings
- **Conflict Detection**: Queue for manual resolution
- **Backup Creation**: Automatic backups before modifications
- **State Recovery**: Resume from interrupted operations

## Success Metrics

### Synchronization Quality
- **Accuracy**: 100% task mapping between Memory.md and GitHub Issues
- **Timeliness**: Changes reflected within 5 minutes
- **Consistency**: Zero data loss during conflict resolution
- **Performance**: Complete sync in under 30 seconds

### Content Quality
- **Relevance**: High-priority tasks remain visible
- **Organization**: Logical section structure maintained
- **Completeness**: All important context preserved
- **Efficiency**: Memory.md size stays under reasonable limits

### System Integration
- **Compatibility**: No breaking changes to existing workflows
- **Reliability**: 99% uptime for sync operations
- **Usability**: Simple configuration and troubleshooting
- **Monitoring**: Comprehensive logging and status reporting

## Agent Interaction Patterns

### With WorkflowManager
- Receives Memory.md updates during workflow phases
- Coordinates pruning after workflow completion
- Maintains workflow history and outcomes

### With Code-Reviewer
- Preserves code review summaries and insights
- Maintains PR history and architectural learnings
- Consolidates review patterns and recommendations

### With OrchestratorAgent
- Handles memory updates from parallel execution
- Coordinates multiple concurrent memory modifications
- Resolves conflicts from simultaneous updates

## Example Operations

### Daily Maintenance
```python
# Automated daily maintenance
agent_actions = [
    "parse_memory_file",
    "identify_pruning_candidates",
    "backup_current_state",
    "prune_old_completed_tasks",
    "consolidate_similar_accomplishments",
    "sync_with_github_issues",
    "resolve_pending_conflicts",
    "update_cross_references",
    "commit_changes"
]
```

### Conflict Resolution
```python
# Handle synchronization conflicts
conflict_resolution = {
    "task_modified_both_places": "prompt_user_choice",
    "task_completed_memory_open_github": "close_github_issue",
    "task_reopened_github_completed_memory": "reopen_memory_task",
    "content_diverged": "merge_with_manual_review"
}
```

## Memory Enhancement Features

### Smart Context Preservation
- Identifies and preserves frequently referenced context
- Maintains architectural decisions and patterns
- Keeps track of important debugging insights
- Preserves system evolution history

### Automated Cross-Linking
- Creates links between related tasks and issues
- Maintains PR and commit references
- Links code review insights to implementation tasks
- Tracks dependency relationships

### Intelligent Summarization
- Consolidates similar accomplishments
- Creates digest summaries for long time periods
- Extracts key learnings and patterns
- Maintains searchable historical context

## Security and Privacy

### Data Protection
- All processing happens locally with version-controlled files
- GitHub API credentials managed through standard gh CLI authentication
- No external services or data transmission beyond GitHub API
- Comprehensive audit trail of all modifications

### Access Control
- Respects GitHub repository permissions
- Uses authenticated gh CLI for all GitHub operations
- Maintains backup files with proper permissions
- Logs all significant operations for accountability

## Future Enhancements

### Advanced Features
- Machine learning for content relevance scoring
- Automatic task priority detection from context
- Integration with external project management tools
- Advanced conflict resolution with ML assistance

### Workflow Extensions
- Integration with CI/CD pipeline status
- Code coverage and quality metric tracking
- Automated reporting and dashboard generation
- Team collaboration features for shared memory

---

**Usage**: Invoke this agent when Memory.md needs maintenance, GitHub Issues sync, or content curation. The agent operates safely with comprehensive backup and error handling.

**Dependencies**: Requires Python 3.8+, GitHub CLI (gh), and appropriate repository permissions.

**Integration**: Works seamlessly with existing WorkflowManager, Code-Reviewer, and OrchestratorAgent workflows.
