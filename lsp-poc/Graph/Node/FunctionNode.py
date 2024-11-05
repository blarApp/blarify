from Graph.Node import NodeLabels
from .types.DefinitionNode import DefinitionNode


class FunctionNode(DefinitionNode):
    def __init__(self, **kwargs):
        super().__init__(label=NodeLabels.FUNCTION, **kwargs)

    def __str__(self) -> str:
        return f"{self.label}({self.path}).{self.name}"

    def as_object(self) -> dict:
        obj = super().as_object()
        obj["attributes"]["start_line"] = self.node_range.start_line
        obj["attributes"]["end_line"] = self.node_range.end_line
        obj["attributes"]["text"] = self.code_text
        return obj
