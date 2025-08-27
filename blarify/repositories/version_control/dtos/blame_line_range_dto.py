from pydantic import BaseModel


class BlameLineRangeDto(BaseModel):
    """DTO for blame line ranges."""
    
    start: int
    end: int
    
    class Config:
        frozen = True