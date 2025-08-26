from typing import List, Optional
from pydantic import BaseModel
from .blame_line_range_dto import BlameLineRangeDto
from .pull_request_info_dto import PullRequestInfoDto


class BlameCommitDto(BaseModel):
    """DTO for commit information from GitHub blame results."""

    sha: str
    message: str
    author: str
    author_email: Optional[str] = None
    author_login: Optional[str] = None
    timestamp: str
    url: str
    additions: Optional[int] = None
    deletions: Optional[int] = None
    line_ranges: List[BlameLineRangeDto]
    pr_info: Optional[PullRequestInfoDto] = None

    class Config:
        frozen = True
