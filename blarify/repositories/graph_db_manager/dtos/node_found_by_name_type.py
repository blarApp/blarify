from dataclasses import dataclass, asdict


@dataclass
class NodeFoundByNameTypeDto:
    """Node found by name and type data transfer object."""

    node_id: str
    node_name: str
    node_type: list[str]
    file_path: str
    code: str | None = None

    def as_dict(self):
        return asdict(self)
