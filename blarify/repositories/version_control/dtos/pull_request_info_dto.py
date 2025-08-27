from typing import Optional
from pydantic import BaseModel


class PullRequestInfoDto(BaseModel):
    """DTO for pull request information from blame results."""
    
    number: int
    title: str
    url: str
    author: Optional[str] = None
    merged_at: Optional[str] = None
    state: str = "MERGED"
    body_text: Optional[str] = None  # PR description from bodyText GraphQL field
    
    class Config:
        frozen = True