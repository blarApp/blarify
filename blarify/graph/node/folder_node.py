from blarify.graph.node import Node, NodeLabels
from blarify.graph.node.file_node import FileNode
from typing import Union, List, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from blarify.graph.relationship import Relationship


class FolderNode(Node):
    path: str
    name: str
    level: int

    def __init__(self, path: str, name: str, level: int, *args, **kwargs):
        self._contains = []
        super().__init__(NodeLabels.FOLDER, path, name, level, *args, **kwargs)

    @property
    def node_repr_for_identifier(self) -> str:
        return "/" + self.name

    def _remove_trailing_slash(self, path: str) -> str:
        if path.endswith("/"):
            return path[:-1]
        return path

    def relate_node_as_contain_relationship(self, node: Union[FileNode, "FolderNode"]) -> None:
        if isinstance(node, FileNode) or isinstance(node, FolderNode):
            self._contains.append(node)
        else:
            raise Exception("Folder node cannot contain node of type: " + type(node).__name__)

    def relate_nodes_as_contain_relationship(self, nodes: Sequence[Union[FileNode, "FolderNode"]]) -> None:
        for node in nodes:
            self.relate_node_as_contain_relationship(node)

    def get_relationships(self) -> List["Relationship"]:
        from blarify.graph.relationship import RelationshipCreator

        relationships = []
        for node in self._contains:
            relationships.append(RelationshipCreator.create_contains_relationship(self, node))

        return relationships

    def filter_children_by_path(self, paths: List[str]):
        self._contains = [node for node in self._contains if node.path in paths]
