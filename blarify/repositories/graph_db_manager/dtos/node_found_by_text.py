from pydantic import BaseModel


class NodeFoundByTextDto(BaseModel):
    id: str
    name: str
    label: str
    diff_text: str
    relevant_snippet: str
    node_path: str

    def as_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "diff_text": self.diff_text,
            "relevant_snippet": self.relevant_snippet,
            "node_path": self.node_path,
        }
