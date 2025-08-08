from typing import List, TYPE_CHECKING, Optional, Dict, Any
from hashlib import md5
from blarify.utils.format_verifier import FormatVerifier
import os

from blarify.utils.relative_id_calculator import RelativeIdCalculator

if TYPE_CHECKING:
    from blarify.graph.relationship import Relationship
    from blarify.graph.node import NodeLabels
    from blarify.graph.graph_environment import GraphEnvironment


class Node:
    label: "NodeLabels"
    path: str
    name: str
    level: int
    parent: Optional["Node"]
    graph_environment: Optional["GraphEnvironment"]
    layer: str

    def __init__(
        self,
        label: "NodeLabels",
        path: str,
        name: str,
        level: int,
        parent: Optional["Node"] = None,
        graph_environment: Optional["GraphEnvironment"] = None,
        layer: str = "code",
    ) -> None:
        self.label = label
        self.path = path
        self.name = name
        self.level = level
        self.parent = parent
        self.graph_environment = graph_environment
        self.layer = layer

        if not self.is_path_format_valid():
            raise ValueError(f"Path format is not valid: {self.path}")

    def is_path_format_valid(self) -> bool:
        return FormatVerifier.is_path_uri(self.path)

    @property
    def hashed_id(self) -> str:
        return md5(self.id.encode()).hexdigest()

    @property
    def relative_id(self) -> str:
        """
        Returns the id without the graph environment prefix or root folder name
        """
        return RelativeIdCalculator.calculate(self.id)

    @property
    def id(self) -> str:
        return str(self.graph_environment or "") + self._identifier()

    @property
    def node_repr_for_identifier(self) -> str:
        raise NotImplementedError

    @property
    def pure_path(self) -> str:
        return self.path.replace("file://", "")

    @property
    def extension(self) -> str:
        return os.path.splitext(self.pure_path)[1]

    def as_object(self) -> Dict[str, Any]:
        return {
            "type": self.label.name,
            "extra_labels": [],
            "attributes": {
                "label": self.label.name,
                "path": self.path,
                "node_id": self.hashed_id,
                "node_path": self.id,
                "name": self.name,
                "level": self.level,
                "hashed_id": self.hashed_id,
                "diff_identifier": self.graph_environment.diff_identifier if self.graph_environment else "",
                "layer": self.layer,
            },
        }

    def get_relationships(self) -> List["Relationship"]:
        return []

    def filter_children_by_path(self, paths: List[str]) -> None:
        pass

    def _identifier(self) -> str:
        identifier: str = ""

        if self.parent:
            identifier += self.parent._identifier()
        identifier += self.node_repr_for_identifier

        return identifier

    def update_graph_environment(self, environment: "GraphEnvironment") -> None:
        self.graph_environment = environment

    def __str__(self) -> str:
        return self._identifier()
