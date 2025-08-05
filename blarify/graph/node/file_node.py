from typing import Dict, Any
from blarify.graph.node import NodeLabels
from .types.definition_node import DefinitionNode


class FileNode(DefinitionNode):
    def __init__(self, **kwargs) -> None:
        super().__init__(label=NodeLabels.FILE, **kwargs)

    @property
    def node_repr_for_identifier(self) -> str:
        return "/" + self.name

    def as_object(self) -> Dict[str, Any]:
        obj = super().as_object()
        obj["attributes"]["text"] = self.code_text
        return obj
