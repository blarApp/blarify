from enum import Enum


class RelationshipType(Enum):
    # Code hierarchy
    CONTAINS = "CONTAINS"
    FUNCTION_DEFINITION = "FUNCTION_DEFINITION"
    CLASS_DEFINITION = "CLASS_DEFINITION"

    # Code references
    IMPORTS = "IMPORTS"
    CALLS = "CALLS"
    INHERITS = "INHERITS"
    INSTANTIATES = "INSTANTIATES"
    TYPES = "TYPES"
    ASSIGNS = "ASSIGNS"
    USES = "USES"

    # Code diff
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    ADDED = "ADDED"

    # Workflow relationships
    WORKFLOW_STEP = "WORKFLOW_STEP"  # Execution flow between components with step_order
    BELONGS_TO_WORKFLOW = "BELONGS_TO_WORKFLOW"  # Documentation node belongs to workflow
    BELONGS_TO_SPEC = "BELONGS_TO_SPEC"  # Workflow node belongs to specification
    DESCRIBES = "DESCRIBES"  # Documentation node describes code node
    
    # Integration relationships
    MODIFIED_BY = "MODIFIED_BY"  # Code node modified by commit
    AFFECTS = "AFFECTS"  # Commit affects workflow
    INTEGRATION_SEQUENCE = "INTEGRATION_SEQUENCE"  # PR to commit sequence
