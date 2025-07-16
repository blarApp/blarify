from dataclasses import dataclass


@dataclass
class NodeFoundByNameTypeDto:
    id: str
    name: str
    label: str
    diff_text: str
    node_path: str
    text: str
    diff_identifier: str

    def get_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "diff_text": self.diff_text,
            "node_path": self.node_path,
            "text": self.text,
            "diff_identifier": self.diff_identifier,
        }
