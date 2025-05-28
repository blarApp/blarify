from blarify.graph.node import NodeLabels
from blarify.stats.complexity import CodeComplexityCalculator
from .types.definition_node import DefinitionNode


class FunctionNode(DefinitionNode):
    def __init__(self, **kwargs):
        super().__init__(label=NodeLabels.FUNCTION, **kwargs)

    @property
    def node_repr_for_identifier(self) -> str:
        return "." + self.name

    def as_object(self) -> dict:
        obj = super().as_object()
        obj["attributes"]["start_line"] = self.node_range.range.start.line
        obj["attributes"]["end_line"] = self.node_range.range.end.line
        obj["attributes"]["text"] = self.code_text
        obj["attributes"]["stats_parameter_count"] = CodeComplexityCalculator.calculate_parameter_count(self._tree_sitter_node)
        return obj
