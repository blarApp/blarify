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
    
    # Documentation relationships
    DOCUMENTS = "DOCUMENTS"  # Information node documents a code node
    EXPLAINS = "EXPLAINS"  # Information node explains another information node
    REFERENCES_DOC = "REFERENCES_DOC"  # Information node references another information node
    HAS_EXAMPLE = "HAS_EXAMPLE"  # Information node contains example of a code node
    
    # Workflow relationships
    PARTICIPATES_IN = "PARTICIPATES_IN"  # Component participates in business workflow
    WORKFLOW_STEP = "WORKFLOW_STEP"  # Execution flow between components with step_order
    TRIGGERS_ASYNC = "TRIGGERS_ASYNC"  # Async operation triggering
    COLLABORATES_WITH = "COLLABORATES_WITH"  # Components working together in workflow
    
    # 4-layer architecture relationships
    BELONGS_TO_SPEC = "BELONGS_TO_SPEC"  # Workflow belongs to specification
    BELONGS_TO_WORKFLOW = "BELONGS_TO_WORKFLOW"  # Documentation node belongs to workflow
    DESCRIBES = "DESCRIBES"  # Documentation node describes code node
