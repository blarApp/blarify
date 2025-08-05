from blarify.graph.node import Node
from blarify.utils.path_calculator import PathCalculator


class DeletedNode(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _identifier(self):
        return PathCalculator.compute_relative_path_with_prefix(self.pure_path, self.graph_environment.root_path)
