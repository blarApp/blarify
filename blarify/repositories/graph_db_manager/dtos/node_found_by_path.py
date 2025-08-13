from pydantic import BaseModel


class NodeFoundByPathDto(BaseModel):
    node_id: str
    name: str
    label: str
    node_path: str

    def as_dict(self):
        return {"node_id": self.node_id, "name": self.name, "label": self.label, "node_path": self.node_path}