from Graph.Node import Node, NodeLabels
from .DefinitionRange import DefinitionRange


class FunctionNode(Node):
    def __init__(self, path: str, name: str, definition_range: DefinitionRange):
        super().__init__(NodeLabels.FUNCTION, path)
        self.name = name
        self.definition_range = definition_range

    def __str__(self):
        return f"{self.label}({self.path}).{self.name}"
