from blarify.graph.node import Node


class DeletedNode(Node):
    def __init__(*args, **kwargs):
        super().__init__(*args, **kwargs)

    def _identifier(self):
        return self.path
