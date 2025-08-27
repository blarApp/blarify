from pydantic import BaseModel


class CodeNodeDto(BaseModel):
    """DTO for code nodes used in GitHub blame integration."""
    
    id: str
    name: str
    label: str
    path: str
    start_line: int
    end_line: int
    
    class Config:
        frozen = True  # Make immutable for safety